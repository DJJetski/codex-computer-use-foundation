#!/usr/bin/env python3
"""Remove Codex Computer Use repair-package runtime state from a home tree."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from foundation_manifest import (
    DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL,
    DIRECT_MCP_HEADERS,
    FOUNDATION_GENERATED_TARGETS,
    FOUNDATION_OBSOLETE_TARGETS,
    FOUNDATION_PURGE_STATE_TARGETS,
    GUARD_LAUNCH_AGENT_LABEL,
    INSTALL_MANIFEST,
    assert_no_symlink_components,
    assert_within_home,
    safe_env_home,
    target_path,
)


def launch_agent_label(path: Path) -> str:
    try:
        with path.open("rb") as fh:
            payload = plistlib.load(fh)
        label = str(payload.get("Label") or "").strip()
    except Exception:
        label = ""
    return label or path.stem


def launch_agent_paths(home: Path) -> list[Path]:
    launch_agents = home / "Library" / "LaunchAgents"
    paths = {
        launch_agents / f"{GUARD_LAUNCH_AGENT_LABEL}.plist",
        launch_agents / f"{DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL}.plist",
    }
    return sorted(paths)


def foundation_paths(home: Path, *, purge_state: bool) -> list[Path]:
    paths = [target_path(home, item) for item in INSTALL_MANIFEST]
    paths.extend(home / rel for rel in FOUNDATION_OBSOLETE_TARGETS)
    paths.extend(home / rel for rel in FOUNDATION_GENERATED_TARGETS)
    paths.extend(launch_agent_paths(home))
    if purge_state:
        paths.extend(home / rel for rel in FOUNDATION_PURGE_STATE_TARGETS)
    unique: dict[str, Path] = {}
    symlink_roots = [path for path in paths if path.is_symlink()]
    for path in paths:
        if any(path != root and root in path.parents for root in symlink_roots):
            continue
        assert_within_home(home, path)
        assert_no_symlink_components(home, path, allow_leaf=True)
        unique[str(path)] = path
    return sorted(unique.values(), key=lambda item: len(item.parts), reverse=True)


def find_section(lines: list[str], header: str) -> tuple[int, int] | None:
    bracketed = f"[{header}]"
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == bracketed)
    except StopIteration:
        return None
    end = start + 1
    while end < len(lines) and not lines[end].lstrip().startswith("["):
        end += 1
    return start, end


def remove_section(lines: list[str], header: str) -> bool:
    changed = False
    while True:
        section = find_section(lines, header)
        if section is None:
            return changed
        start, end = section
        del lines[start:end]
        while start < len(lines) and start > 0 and lines[start].strip() == "" and lines[start - 1].strip() == "":
            del lines[start]
        changed = True


def scrub_config(home: Path, *, dry_run: bool) -> list[str]:
    config = home / ".codex" / "config.toml"
    assert_within_home(home, config)
    assert_no_symlink_components(home, config)
    if not config.is_file():
        return []
    original = config.read_text(encoding="utf-8", errors="replace")
    lines = original.splitlines()
    actions: list[str] = []
    for header in DIRECT_MCP_HEADERS:
        if remove_section(lines, header):
            actions.append(f"remove direct MCP alias [{header}] from {config}")
    if remove_section(lines, 'plugins."computer-use@openai-bundled"'):
        actions.append(f"remove computer-use plugin stanza from {config}")
    marketplace = find_section(lines, "marketplaces.openai-bundled")
    if marketplace is not None:
        start, end = marketplace
        section_text = "\n".join(lines[start:end])
        if ".codex/plugins/marketplaces/openai-bundled" in section_text:
            del lines[start:end]
            actions.append(f"remove foundation-owned marketplace stanza from {config}")
    filtered: list[str] = []
    for line in lines:
        if "codex-computer-use-notify" in line and line.lstrip().startswith("notify"):
            actions.append(f"remove foundation-owned notify hook from {config}")
            continue
        filtered.append(line)
    updated = "\n".join(filtered).rstrip() + "\n"
    if updated == original:
        return []
    if not dry_run:
        tmp = config.with_name(f".{config.name}.tmp-{os.getpid()}")
        tmp.write_text(updated, encoding="utf-8")
        os.replace(tmp, config)
    return [f"would {action}" if dry_run else action for action in actions]


def unload_launch_agent(path: Path, *, home: Path, dry_run: bool) -> list[str]:
    if not path.exists():
        return []
    label = launch_agent_label(path)
    actions = [f"unload LaunchAgent {label}"]
    if dry_run:
        return [f"would {action}" for action in actions]
    if home == Path.home().resolve():
        subprocess.run(
            ["/bin/launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3,
        )
    return actions


def remove_path(path: Path, *, dry_run: bool) -> str | None:
    if not path.exists() and not path.is_symlink():
        return None
    action = f"remove {path}"
    if dry_run:
        return f"would {action}"
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    return action


def main() -> int:
    parser = argparse.ArgumentParser(description="Uninstall native Codex Computer Use repair runtime files")
    parser.add_argument("--home", default=None, help="target home directory; defaults to $HOME")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--purge-state", action="store_true", help="also remove foundation snapshot/state directories")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print("ERROR: writes require --yes", file=sys.stderr)
        return 1

    home = safe_env_home(args.home)
    actions: list[str] = []
    for path in launch_agent_paths(home):
        assert_within_home(home, path)
        actions.extend(unload_launch_agent(path, home=home, dry_run=args.dry_run))
    actions.extend(scrub_config(home, dry_run=args.dry_run))
    for path in foundation_paths(home, purge_state=args.purge_state):
        assert_within_home(home, path)
        action = remove_path(path, dry_run=args.dry_run)
        if action:
            actions.append(action)
    print(
        json.dumps(
            {"ok": True, "dry_run": args.dry_run, "home": str(home), "purge_state": args.purge_state, "actions": actions},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
