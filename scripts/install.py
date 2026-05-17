#!/usr/bin/env python3
"""Install the Codex Computer Use repair package into the target user's home."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

from foundation_manifest import (
    DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL,
    DIRECT_MCP_HEADERS,
    FOUNDATION_OBSOLETE_TARGETS,
    FOUNDATION_OBSOLETE_GLOBS,
    GUARD_LAUNCH_AGENT_LABEL,
    INSTALL_MANIFEST,
    LEGACY_DIALOG_AUTOPILOT_LAUNCH_AGENT_LABELS,
    LEGACY_GUARD_LAUNCH_AGENT_LABELS,
    REPO_ROOT,
    SNAPSHOT_ROOT,
    assert_no_symlink_components,
    assert_within_home,
    mode_octal,
    repo_path,
    safe_env_home,
    sha256_file,
    target_path,
)


def launch_agent_target(label: str) -> str:
    return f"Library/LaunchAgents/{label}.plist"


SNAPSHOT_EXTRA_TARGETS = [
    ".codex/config.toml",
    *FOUNDATION_OBSOLETE_TARGETS,
    launch_agent_target(GUARD_LAUNCH_AGENT_LABEL),
    launch_agent_target(DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL),
    *(launch_agent_target(label) for label in LEGACY_GUARD_LAUNCH_AGENT_LABELS),
    *(launch_agent_target(label) for label in LEGACY_DIALOG_AUTOPILOT_LAUNCH_AGENT_LABELS),
    "Library/Application Support/CodexComputerUseGuard/codex-computer-use-guard.backup",
    "Library/Application Support/CodexComputerUseGuard/codex-computer-use-broker.backup",
    "Library/Application Support/CodexComputerUseGuard/codex-dialog-autopilot.backup",
    "Library/Application Support/CodexComputerUseGuard/codex-dialog-autopilot-bootstrap",
]

SNAPSHOT_EXTRA_GLOBS = [
    ".codex/plugins/cache/openai-bundled/computer-use/*/.mcp.json",
    ".codex/.tmp/bundled-marketplaces/openai-bundled/plugins/computer-use/.mcp.json",
    ".codex/.tmp/bundled-marketplaces/openai-bundled/plugins/computer-use/codex-computer-use-mcp",
    *FOUNDATION_OBSOLETE_GLOBS,
]


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def run(cmd: list[str], *, timeout: int, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=timeout,
        env=env,
    )


def compile_python_sources() -> list[str]:
    errors: list[str] = []
    for item in INSTALL_MANIFEST:
        if item.get("kind") != "python":
            continue
        source = repo_path(str(item["source"]))
        try:
            compile(source.read_text(encoding="utf-8"), str(source), "exec")
        except SyntaxError as exc:
            errors.append(f"{source}: {exc}")
    return errors


def validate_sources() -> list[str]:
    errors: list[str] = []
    for item in INSTALL_MANIFEST:
        source = repo_path(str(item["source"]))
        if not source.is_file():
            errors.append(f"missing source: {source}")
            continue
        if item.get("kind") == "json":
            try:
                json.loads(source.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON in {source}: {exc}")
    errors.extend(compile_python_sources())
    launcher = repo_path("src/bin/codex-computer-use-native-launcher").read_text(encoding="utf-8")
    if 'exec "$native_binary" "$@"' not in launcher:
        errors.append("native launcher must exec SkyComputerUseClient in-process")
    return errors


def codex_bundle_id(codex_app: Path) -> str:
    info_plist = codex_app / "Contents" / "Info.plist"
    with info_plist.open("rb") as fh:
        payload = plistlib.load(fh)
    return str(payload.get("CFBundleIdentifier") or "").strip()


def validate_target(home: Path, *, codex_app: Path, skip_runtime_checks: bool) -> list[str]:
    errors: list[str] = []
    if platform.system() != "Darwin" and not skip_runtime_checks:
        errors.append("target is not macOS; use --skip-runtime-checks only for tests")
    if not skip_runtime_checks:
        if not codex_app.is_dir():
            errors.append(f"missing Codex app: {codex_app}")
        else:
            try:
                bundle_id = codex_bundle_id(codex_app)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"cannot inspect Codex app bundle: {codex_app}: {exc}")
            else:
                if bundle_id != "com.openai.codex":
                    errors.append(f"{codex_app} has bundle id {bundle_id!r}, expected 'com.openai.codex'")
    codex_home = home / ".codex"
    if codex_home.is_symlink():
        errors.append(f"{codex_home} is a symlink; refusing to install through symlinked .codex")
    if codex_home.exists() and not codex_home.is_dir():
        errors.append(f"{codex_home} exists but is not a directory")
    for item in INSTALL_MANIFEST:
        try:
            assert_within_home(home, target_path(home, item))
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def snapshot_targets(home: Path) -> list[Path]:
    targets = [target_path(home, item) for item in INSTALL_MANIFEST]
    targets.extend(home / rel for rel in SNAPSHOT_EXTRA_TARGETS)
    for pattern in SNAPSHOT_EXTRA_GLOBS:
        targets.extend((home / ".").glob(pattern))
    unique: dict[str, Path] = {}
    for target in targets:
        assert_within_home(home, target)
        assert_no_symlink_components(home, target, allow_leaf=True)
        unique[str(target)] = target
    return list(unique.values())


def make_snapshot(home: Path, *, dry_run: bool) -> Path | None:
    if dry_run:
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    snapshot_dir = home / SNAPSHOT_ROOT / stamp
    files_dir = snapshot_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, object] = {
        "created_at": stamp,
        "home": str(home),
        "repo": str(REPO_ROOT),
        "files": [],
        "redacted_config_present": False,
    }
    for target in snapshot_targets(home):
        assert_within_home(home, target)
        relative_target = str(target.relative_to(home))
        row: dict[str, object] = {"target": relative_target, "existed": target.exists()}
        if target.exists():
            if target.is_dir() and not target.is_symlink():
                row["directory"] = True
                row["mode"] = mode_octal(target)
                manifest["files"].append(row)
                continue
            backup = files_dir / relative_target
            backup.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                backup.write_text(f"symlink -> {os.readlink(target)}\n", encoding="utf-8")
                row["symlink"] = True
                row["link_target"] = os.readlink(target)
            else:
                shutil.copy2(target, backup)
            if relative_target == ".codex/config.toml":
                os.chmod(backup, 0o600)
            row["backup"] = str(backup.relative_to(snapshot_dir))
            row["mode"] = oct(target.lstat().st_mode & 0o777) if target.is_symlink() else mode_octal(target)
            if not target.is_symlink():
                row["sha256"] = sha256_file(target)
        manifest["files"].append(row)
        if relative_target == ".codex/config.toml" and target.exists():
            manifest["config_present"] = True
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot_dir


def atomic_install_file(source: Path, target: Path, mode: int, *, dry_run: bool) -> str:
    if dry_run:
        return f"would install {source} -> {target}"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    shutil.copy2(source, tmp)
    os.chmod(tmp, mode)
    os.replace(tmp, target)
    return f"installed {target}"


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
    if not config.exists():
        return []
    original = config.read_text(encoding="utf-8", errors="replace")
    lines = original.splitlines()
    actions: list[str] = []
    for header in DIRECT_MCP_HEADERS:
        if remove_section(lines, header):
            actions.append(f"remove direct MCP alias [{header}] from {config}")
    if remove_section(lines, 'plugins."computer-use@openai-bundled"'):
        actions.append(f"remove stale computer-use plugin stanza from {config}")
    marketplace = find_section(lines, "marketplaces.openai-bundled")
    if marketplace is not None:
        start, end = marketplace
        section_text = "\n".join(lines[start:end])
        if ".codex/plugins/marketplaces/openai-bundled" in section_text:
            del lines[start:end]
            actions.append(f"remove foundation-owned openai-bundled marketplace stanza from {config}")
    filtered: list[str] = []
    for line in lines:
        if "codex-computer-use-notify" in line and line.lstrip().startswith("notify"):
            actions.append(f"remove foundation-owned notify hook from {config}")
            continue
        filtered.append(line)
    updated = "\n".join(filtered).rstrip() + "\n"
    if updated == original:
        return []
    if dry_run:
        return [f"would {action}" for action in actions]
    tmp = config.with_name(f".{config.name}.tmp-{os.getpid()}")
    tmp.write_text(updated, encoding="utf-8")
    os.replace(tmp, config)
    return actions


def install_files(home: Path, *, dry_run: bool) -> list[str]:
    actions: list[str] = []
    for item in INSTALL_MANIFEST:
        source = repo_path(str(item["source"]))
        target = target_path(home, item)
        mode = int(item["mode"])
        assert_within_home(home, target)
        assert_no_symlink_components(home, target)
        actions.append(atomic_install_file(source, target, mode, dry_run=dry_run))
    return actions


def remove_obsolete_targets(home: Path, *, dry_run: bool) -> list[str]:
    actions: list[str] = []
    targets = [home / relative for relative in FOUNDATION_OBSOLETE_TARGETS]
    for pattern in FOUNDATION_OBSOLETE_GLOBS:
        targets.extend((home / ".").glob(pattern))
    unique = {str(target): target for target in targets}
    for target in sorted(unique.values(), key=lambda path: len(path.parts), reverse=True):
        assert_within_home(home, target)
        assert_no_symlink_components(home, target, allow_leaf=True)
        if not target.exists() and not target.is_symlink():
            continue
        if target.is_dir() and not target.is_symlink():
            try:
                if any(target.iterdir()):
                    actions.append(f"leave non-empty obsolete directory {target}")
                    continue
            except OSError:
                actions.append(f"leave unreadable obsolete directory {target}")
                continue
        action = f"remove obsolete installed file {target}"
        actions.append(f"would {action}" if dry_run else action)
        if dry_run:
            continue
        if target.is_dir() and not target.is_symlink():
            target.rmdir()
        else:
            target.unlink()
        stop = home / ".codex" / "skills" / "macos-computer-use"
        parent = target.parent
        while parent != stop and parent.is_dir():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return actions


def postinstall(
    home: Path,
    *,
    full_ensure: bool,
    codex_app: Path,
    ensure_config_timeout: int,
    full_ensure_timeout: int,
) -> int:
    guard = home / ".codex" / "bin" / "codex-computer-use-guard"
    if not guard.is_file():
        return fail(f"installed guard not found: {guard}")
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_CU_CODEX_APP"] = str(codex_app)
    ensure_config = run([str(guard), "ensure-config", "--quiet"], timeout=ensure_config_timeout, env=env)
    if ensure_config.returncode != 0:
        print(ensure_config.stdout.rstrip(), file=sys.stderr)
        return fail("ensure-config failed")
    if full_ensure:
        ensure = run([str(guard), "ensure"], timeout=full_ensure_timeout, env=env)
        print(ensure.stdout.rstrip())
        if ensure.returncode != 0:
            return fail("full ensure failed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the native Codex Computer Use repair package")
    parser.add_argument("--home", default=None, help="target home directory; defaults to $HOME")
    parser.add_argument("--codex-app", default="/Applications/Codex.app", help="OpenAI Codex.app path")
    parser.add_argument("--dry-run", action="store_true", help="validate and print intended actions without writing")
    parser.add_argument("--yes", action="store_true", help="required for writes")
    parser.add_argument("--skip-runtime-checks", action="store_true", help="allow temp-home tests without Codex.app checks")
    parser.add_argument("--skip-postinstall", action="store_true", help="copy files but do not run guard repair")
    parser.add_argument("--full-ensure", action="store_true", help="after install, run full guard ensure including smoke refresh when safe")
    parser.add_argument(
        "--ensure-config-timeout",
        type=int,
        default=int(os.environ.get("CODEX_CU_INSTALL_ENSURE_CONFIG_TIMEOUT", "60")),
        help="seconds to allow postinstall ensure-config; env CODEX_CU_INSTALL_ENSURE_CONFIG_TIMEOUT",
    )
    parser.add_argument(
        "--full-ensure-timeout",
        type=int,
        default=int(os.environ.get("CODEX_CU_INSTALL_FULL_ENSURE_TIMEOUT", "240")),
        help="seconds to allow --full-ensure; env CODEX_CU_INSTALL_FULL_ENSURE_TIMEOUT",
    )
    args = parser.parse_args()

    home = safe_env_home(args.home)
    codex_app = Path(args.codex_app).expanduser().resolve()
    if not args.dry_run and not args.yes:
        return fail("writes require --yes; use --dry-run to preview")
    if args.ensure_config_timeout < 1 or args.full_ensure_timeout < 1:
        return fail("timeouts must be positive seconds")

    errors = validate_sources() + validate_target(home, codex_app=codex_app, skip_runtime_checks=args.skip_runtime_checks)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    snapshot_dir = make_snapshot(home, dry_run=args.dry_run)
    scrub_actions = scrub_config(home, dry_run=args.dry_run)
    obsolete_actions = remove_obsolete_targets(home, dry_run=args.dry_run)
    actions = install_files(home, dry_run=args.dry_run)
    payload = {
        "ok": True,
        "dry_run": args.dry_run,
        "home": str(home),
        "codex_app": str(codex_app),
        "snapshot": str(snapshot_dir) if snapshot_dir else None,
        "actions": scrub_actions + obsolete_actions + actions,
        "postinstall": not args.skip_postinstall and not args.dry_run,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.dry_run or args.skip_postinstall:
        return 0
    return postinstall(
        home,
        full_ensure=args.full_ensure,
        codex_app=codex_app,
        ensure_config_timeout=args.ensure_config_timeout,
        full_ensure_timeout=args.full_ensure_timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
