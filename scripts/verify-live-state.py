#!/usr/bin/env python3
"""Read-only verifier for native Codex Computer Use installation invariants."""

from __future__ import annotations

import argparse
import json
import os
import platform
import plistlib
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from foundation_manifest import (
    DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL,
    DIRECT_MCP_HEADERS,
    GUARD_LAUNCH_AGENT_LABEL,
    INSTALL_MANIFEST,
    LEGACY_DIALOG_AUTOPILOT_LAUNCH_AGENT_LABELS,
    LEGACY_GUARD_LAUNCH_AGENT_LABELS,
    REPO_ROOT,
    mode_octal,
    redact_text,
    repo_path,
    safe_env_home,
    sha256_file,
    target_path,
)


FORBIDDEN_FALLBACK_WORDS = [
    "cliclick",
    "osascript",
    "System Events",
    "Keyboard Maestro",
    "screencapture",
    "playwright",
]
ABSOLUTE_HOME_RE = re.compile(r"/" + r"Users/[A-Za-z0-9._-]+")


def run(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=timeout,
    )


def check(condition: bool, name: str, detail: str = "") -> dict[str, object]:
    return {"ok": bool(condition), "name": name, "detail": detail}


def source_checks() -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for item in INSTALL_MANIFEST:
        source = repo_path(str(item["source"]))
        checks.append(check(source.is_file(), f"source exists: {item['source']}"))
        if not source.is_file():
            continue
        if int(item["mode"]) & 0o111:
            checks.append(check(os.access(source, os.X_OK), f"source executable: {item['source']}", mode_octal(source)))
        if item.get("kind") == "python":
            try:
                compile(source.read_text(encoding="utf-8"), str(source), "exec")
                checks.append(check(True, f"py_compile: {item['source']}"))
            except SyntaxError as exc:
                checks.append(check(False, f"py_compile: {item['source']}", str(exc)))
        if item.get("kind") == "json":
            try:
                json.loads(source.read_text(encoding="utf-8"))
                checks.append(check(True, f"json valid: {item['source']}"))
            except json.JSONDecodeError as exc:
                checks.append(check(False, f"json valid: {item['source']}", str(exc)))
    for source in [
        repo_path("src/bin/codex-computer-use-native-launcher"),
        repo_path("src/bin/codex-computer-use-broker"),
        repo_path("src/plugin-shim/computer-use/codex-computer-use-mcp"),
        repo_path("src/bin/codex-computer-use-native-smoke"),
    ]:
        text = source.read_text(encoding="utf-8")
        checks.append(check(ABSOLUTE_HOME_RE.search(text) is None, f"portable source path: {source.relative_to(REPO_ROOT)}"))
    launcher = repo_path("src/bin/codex-computer-use-native-launcher").read_text(encoding="utf-8")
    checks.append(check('exec "$native_binary" "$@"' in launcher, "launcher execs native client in-process"))
    checks.append(check(not any(word in launcher for word in FORBIDDEN_FALLBACK_WORDS), "launcher has no fallback automation"))
    return checks


def installed_file_checks(home: Path, *, expect_repo_source: bool) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for item in INSTALL_MANIFEST:
        target = target_path(home, item)
        source = repo_path(str(item["source"]))
        checks.append(check(target.is_file(), f"installed file exists: {item['target']}"))
        if not target.is_file():
            continue
        checks.append(check((target.stat().st_mode & 0o777) == int(item["mode"]), f"installed mode: {item['target']}", mode_octal(target)))
        if int(item["mode"]) & 0o111:
            checks.append(check(os.access(target, os.X_OK), f"installed executable: {item['target']}"))
        if expect_repo_source:
            checks.append(
                check(
                    sha256_file(target) == sha256_file(source),
                    f"installed matches repo source: {item['target']}",
                    f"target={sha256_file(target)} source={sha256_file(source)}",
                )
            )
    return checks


def config_checks(home: Path) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    config = home / ".codex" / "config.toml"
    checks.append(check(config.is_file(), "config exists"))
    if not config.is_file():
        return checks
    text = config.read_text(encoding="utf-8", errors="replace")
    for header in DIRECT_MCP_HEADERS:
        checks.append(check(f"[{header}]" not in text, f"direct MCP alias absent: [{header}]"))
    disabled_arrays = re.findall(r"disabled_tools\s*=\s*\[(.*?)\]", text, re.DOTALL)
    checks.append(check(not any("computer-use@openai-bundled" in item for item in disabled_arrays), "computer-use not disabled in tool_suggest"))
    return checks


def mcp_checks(home: Path) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    expected_launcher = str(home / ".codex" / "bin" / "codex-computer-use-native-launcher")
    marketplace_mcp = home / ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/.mcp.json"
    marketplace_manifest = home / ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/.codex-plugin/plugin.json"
    marketplace_skill = home / ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/skills/computer-use/SKILL.md"
    if marketplace_mcp.is_file():
        payload = json.loads(marketplace_mcp.read_text(encoding="utf-8"))
        server = payload.get("mcpServers", {}).get("computer-use", {})
        checks.append(check(server.get("command") == "./codex-computer-use-mcp", "marketplace .mcp.json uses relative wrapper"))
        checks.append(check(server.get("args") == ["mcp"], "marketplace .mcp.json passes mcp arg"))
        checks.append(check(server.get("cwd") == ".", "marketplace .mcp.json uses local cwd"))
    else:
        checks.append(check(False, "marketplace .mcp.json exists"))
    if marketplace_manifest.is_file():
        manifest = json.loads(marketplace_manifest.read_text(encoding="utf-8"))
        checks.append(check("skills" not in manifest, "marketplace plugin does not publish duplicate skill"))
    else:
        checks.append(check(False, "marketplace plugin manifest exists"))
    checks.append(check(not marketplace_skill.exists(), "marketplace duplicate Computer Use skill absent"))
    cache_files = sorted((home / ".codex/plugins/cache/openai-bundled/computer-use").glob("*/.mcp.json"))
    checks.append(check(bool(cache_files), "cached plugin .mcp.json exists"))
    for cache_file in cache_files[-3:]:
        cache_manifest = cache_file.parent / ".codex-plugin" / "plugin.json"
        cache_skill = cache_file.parent / "skills" / "computer-use" / "SKILL.md"
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        server = payload.get("mcpServers", {}).get("computer-use", {})
        checks.append(check(server.get("command") == expected_launcher, f"cached .mcp.json launcher path: {cache_file.parent.name}"))
        checks.append(check(server.get("args") == ["mcp"], f"cached .mcp.json mcp arg: {cache_file.parent.name}"))
        if cache_manifest.is_file():
            manifest = json.loads(cache_manifest.read_text(encoding="utf-8"))
            checks.append(check("skills" not in manifest, f"cached plugin does not publish duplicate skill: {cache_file.parent.name}"))
        else:
            checks.append(check(False, f"cached plugin manifest exists: {cache_file.parent.name}"))
        checks.append(check(not cache_skill.exists(), f"cached duplicate Computer Use skill absent: {cache_file.parent.name}"))
    return checks


def launchagent_checks(home: Path, *, skip_launchctl: bool) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    plist_path = home / "Library/LaunchAgents" / f"{GUARD_LAUNCH_AGENT_LABEL}.plist"
    checks.append(check(plist_path.is_file(), "guard LaunchAgent plist exists"))
    for legacy_label in LEGACY_GUARD_LAUNCH_AGENT_LABELS:
        legacy_path = home / "Library/LaunchAgents" / f"{legacy_label}.plist"
        checks.append(check(not legacy_path.exists(), f"legacy guard LaunchAgent absent: {legacy_label}"))
    if not plist_path.is_file():
        return checks
    try:
        payload = plistlib.loads(plist_path.read_bytes())
        checks.append(check(payload.get("Label") == GUARD_LAUNCH_AGENT_LABEL, "guard LaunchAgent label"))
        env = payload.get("EnvironmentVariables", {})
        checks.append(check(bool(env.get("CODEX_CU_CODEX_APP")), "LaunchAgent persists Codex app path"))
        args = payload.get("ProgramArguments", [])
        checks.append(check(args[:1] == [str(home / "Library/Application Support/CodexComputerUseGuard/codex-computer-use-guard-bootstrap")], "LaunchAgent bootstrap path"))
        checks.append(check("ensure-config" in args, "LaunchAgent runs ensure-config"))
        checks.append(check(payload.get("StartInterval") == 5, "LaunchAgent 5-second backstop"))
    except Exception as exc:
        checks.append(check(False, "LaunchAgent plist parse", str(exc)))
    if not skip_launchctl and platform.system() == "Darwin" and home == Path.home().resolve():
        result = run(["launchctl", "print", f"gui/{os.getuid()}/{GUARD_LAUNCH_AGENT_LABEL}"], timeout=5)
        checks.append(check(result.returncode == 0, "LaunchAgent loaded", result.stdout.splitlines()[0] if result.stdout else ""))
        for legacy_label in LEGACY_GUARD_LAUNCH_AGENT_LABELS:
            legacy_result = run(["launchctl", "print", f"gui/{os.getuid()}/{legacy_label}"], timeout=5)
            checks.append(check(legacy_result.returncode != 0, f"legacy guard LaunchAgent not loaded: {legacy_label}"))
    return checks


def dialog_autopilot_checks(home: Path, *, skip_launchctl: bool) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    autopilot = home / ".codex/bin/codex-dialog-autopilot"
    bootstrap = home / "Library/Application Support/CodexComputerUseGuard/codex-dialog-autopilot-bootstrap"
    backup = home / "Library/Application Support/CodexComputerUseGuard/codex-dialog-autopilot.backup"
    plist_path = home / "Library/LaunchAgents" / f"{DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL}.plist"
    checks.append(check(autopilot.is_file(), "dialog autopilot executable exists"))
    checks.append(check(bootstrap.is_file(), "dialog autopilot bootstrap exists"))
    checks.append(check(backup.is_file(), "dialog autopilot backup exists"))
    checks.append(check(plist_path.is_file(), "dialog autopilot LaunchAgent plist exists"))
    for legacy_label in LEGACY_DIALOG_AUTOPILOT_LAUNCH_AGENT_LABELS:
        legacy_path = home / "Library/LaunchAgents" / f"{legacy_label}.plist"
        checks.append(check(not legacy_path.exists(), f"legacy dialog autopilot LaunchAgent absent: {legacy_label}"))
    if autopilot.is_file() and backup.is_file():
        checks.append(check(sha256_file(autopilot) == sha256_file(backup), "dialog autopilot backup in sync"))
    if plist_path.is_file():
        try:
            payload = plistlib.loads(plist_path.read_bytes())
            checks.append(check(payload.get("Label") == DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL, "dialog autopilot LaunchAgent label"))
            args = payload.get("ProgramArguments", [])
            checks.append(check(args[:1] == [str(bootstrap)], "dialog autopilot LaunchAgent bootstrap path"))
            checks.append(check("daemon" in args, "dialog autopilot LaunchAgent runs daemon"))
            checks.append(check(payload.get("KeepAlive") is True, "dialog autopilot LaunchAgent keepalive"))
        except Exception as exc:
            checks.append(check(False, "dialog autopilot LaunchAgent plist parse", str(exc)))
    if not skip_launchctl and platform.system() == "Darwin" and home == Path.home().resolve():
        result = run(["launchctl", "print", f"gui/{os.getuid()}/{DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL}"], timeout=5)
        checks.append(check(result.returncode == 0, "dialog autopilot LaunchAgent loaded", result.stdout.splitlines()[0] if result.stdout else ""))
        for legacy_label in LEGACY_DIALOG_AUTOPILOT_LAUNCH_AGENT_LABELS:
            legacy_result = run(["launchctl", "print", f"gui/{os.getuid()}/{legacy_label}"], timeout=5)
            checks.append(check(legacy_result.returncode != 0, f"legacy dialog autopilot LaunchAgent not loaded: {legacy_label}"))
    return checks


def backup_checks(home: Path) -> list[dict[str, object]]:
    guard = home / ".codex/bin/codex-computer-use-guard"
    backup = home / "Library/Application Support/CodexComputerUseGuard/codex-computer-use-guard.backup"
    broker = home / ".codex/bin/codex-computer-use-broker"
    broker_backup = home / "Library/Application Support/CodexComputerUseGuard/codex-computer-use-broker.backup"
    checks = [check(backup.is_file(), "guard bootstrap backup exists")]
    if guard.is_file() and backup.is_file():
        checks.append(check(sha256_file(guard) == sha256_file(backup), "guard backup in sync"))
    checks.append(check(broker_backup.is_file(), "broker bootstrap backup exists"))
    if broker.is_file() and broker_backup.is_file():
        checks.append(check(sha256_file(broker) == sha256_file(broker_backup), "broker backup in sync"))
    return checks


def guard_status_checks(home: Path, *, require_operational: bool) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    guard = home / ".codex/bin/codex-computer-use-guard"
    if not guard.is_file() or home != Path.home().resolve():
        return [], None
    result = run([str(guard), "status"], timeout=30)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [check(False, "guard status JSON", result.stdout[-400:])], None
    checks = [check(result.returncode == 0, "guard status exits zero", f"returncode={result.returncode}")]
    if require_operational:
        layers = payload.get("health_layers") or {}
        checks.extend(
            [
                check(bool(payload.get("ok")), "guard ok=true"),
                check(bool(payload.get("structural_ok")), "guard structural_ok=true"),
                check(all(bool(v) for v in layers.values()), "all guard health layers true", str(layers)),
            ]
        )
        smoke = payload.get("native_smoke") or {}
        checks.extend(
            [
                check(bool(smoke.get("ok")), "native smoke ok=true"),
                check(bool(smoke.get("fresh")), "native smoke fresh=true"),
                check(smoke.get("fallback_used") is False, "native smoke fallback_used=false"),
                check(smoke.get("unstructured_stdout_lines") == 0, "native smoke has no unstructured stdout"),
            ]
        )
    return checks, payload


def redacted_payload(payload: dict[str, object], home: Path) -> dict[str, object]:
    text = json.dumps(payload, sort_keys=True)
    text = text.replace(str(home), "$HOME")
    text = redact_text(text)
    return json.loads(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify native Codex Computer Use repair live state")
    parser.add_argument("--home", default=None, help="target home directory; defaults to $HOME")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--expect-installed-from-repo", action="store_true")
    parser.add_argument("--skip-live-invariants", action="store_true", help="only verify repo source and manifest-installed files")
    parser.add_argument("--require-operational", action="store_true")
    parser.add_argument("--skip-launchctl", action="store_true")
    parser.add_argument(
        "--include-private-paths",
        action="store_true",
        help="include absolute local paths in JSON output; default replaces the target home with $HOME",
    )
    args = parser.parse_args()

    home = safe_env_home(args.home)
    checks: list[dict[str, object]] = []
    checks.extend(source_checks())
    checks.extend(installed_file_checks(home, expect_repo_source=args.expect_installed_from_repo))
    status = None
    if not args.skip_live_invariants:
        checks.extend(config_checks(home))
        checks.extend(mcp_checks(home))
        checks.extend(launchagent_checks(home, skip_launchctl=args.skip_launchctl))
        checks.extend(dialog_autopilot_checks(home, skip_launchctl=args.skip_launchctl))
        checks.extend(backup_checks(home))
        guard_checks, status = guard_status_checks(home, require_operational=args.require_operational)
        checks.extend(guard_checks)
    ok = all(item["ok"] for item in checks)
    payload = {"ok": ok, "home": str(home), "checks": checks}
    if status is not None:
        payload["guard_status_summary"] = {
            "ok": status.get("ok"),
            "structural_ok": status.get("structural_ok"),
            "health_layers": status.get("health_layers"),
            "operational_state": status.get("operational_state"),
            "dialog_autopilot": {
                key: (status.get("dialog_autopilot") or {}).get(key)
                for key in ["ok", "launch_agent_loaded", "accessibility_ok"]
            },
            "native_smoke": {
                key: (status.get("native_smoke") or {}).get(key)
                for key in ["ok", "fresh", "age_seconds", "failure_class", "fallback_used"]
            },
        }
    if args.json:
        if not args.include_private_paths:
            payload = redacted_payload(payload, home)
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for item in checks:
            prefix = "ok" if item["ok"] else "FAIL"
            print(f"{prefix} {item['name']}{': ' + item['detail'] if item.get('detail') else ''}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
