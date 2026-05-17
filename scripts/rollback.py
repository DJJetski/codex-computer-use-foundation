#!/usr/bin/env python3
"""Restore files from an installer snapshot."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from foundation_manifest import assert_no_symlink_components, assert_within_home, safe_env_home


def safe_symlink_target(home: Path, link_path: Path, raw_target: object) -> str:
    link_target = str(raw_target or "")
    if not link_target or "\x00" in link_target:
        raise ValueError(f"refusing empty or invalid symlink target for {link_path}")
    candidate = Path(link_target)
    resolved = candidate if candidate.is_absolute() else link_path.parent / candidate
    resolved = Path(os.path.abspath(resolved))
    try:
        resolved.relative_to(home.resolve())
    except ValueError as exc:
        raise ValueError(f"refusing symlink target outside home: {link_path} -> {link_target}") from exc
    return link_target


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback a Codex Computer Use repair install snapshot")
    parser.add_argument("snapshot", help="snapshot directory containing manifest.json")
    parser.add_argument("--home", default=None, help="target home directory; defaults to $HOME")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print("ERROR: writes require --yes", file=sys.stderr)
        return 1

    home = safe_env_home(args.home)
    snapshot = Path(args.snapshot).expanduser().resolve()
    manifest_path = snapshot / "manifest.json"
    if not manifest_path.is_file():
        print(f"ERROR: missing snapshot manifest: {manifest_path}", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actions: list[str] = []
    for item in manifest.get("files", []):
        target = home / item["target"]
        assert_within_home(home, target)
        assert_no_symlink_components(home, target, allow_leaf=True)
        if not item.get("existed", True):
            actions.append(f"remove newly installed {target}")
            if not args.dry_run and (target.exists() or target.is_symlink()):
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            continue
        if item.get("directory"):
            actions.append(f"restore directory metadata {target}")
            if not args.dry_run:
                target.mkdir(parents=True, exist_ok=True)
                os.chmod(target, int(str(item.get("mode", "0o755")), 8))
            continue
        backup = snapshot / item["backup"]
        try:
            Path(os.path.abspath(backup)).relative_to(snapshot)
        except ValueError:
            print(f"ERROR: backup path escapes snapshot: {backup}", file=sys.stderr)
            return 1
        try:
            assert_no_symlink_components(snapshot, backup)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if not backup.is_file():
            print(f"ERROR: missing backup file: {backup}", file=sys.stderr)
            return 1
        actions.append(f"restore {backup} -> {target}")
        if args.dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        if item.get("symlink"):
            try:
                link_target = safe_symlink_target(home, target, item.get("link_target"))
            except ValueError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
            os.symlink(link_target, target)
            continue
        tmp = target.with_name(f".{target.name}.rollback-{os.getpid()}")
        shutil.copy2(backup, tmp)
        os.chmod(tmp, int(str(item.get("mode", "0o644")), 8))
        os.replace(tmp, target)
    print(json.dumps({"ok": True, "dry_run": args.dry_run, "actions": actions}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
