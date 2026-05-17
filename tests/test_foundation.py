from __future__ import annotations

import json
import os
import hashlib
import importlib.machinery
import importlib.util
import io
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from foundation_manifest import (  # noqa: E402
    DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL,
    DIRECT_MCP_HEADERS,
    FOUNDATION_OBSOLETE_GLOBS,
    FOUNDATION_OBSOLETE_TARGETS,
    GUARD_LAUNCH_AGENT_LABEL,
    INSTALL_MANIFEST,
    redact_text,
    repo_path,
    target_path,
)


ABSOLUTE_HOME_MARKER = "/" + "Users/"


def load_guard_module():
    path = repo_path("src/bin/codex-computer-use-guard")
    loader = importlib.machinery.SourceFileLoader("codex_computer_use_guard_under_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load guard module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FoundationTests(unittest.TestCase):
    def test_manifest_sources_exist_and_modes_are_declared(self) -> None:
        for item in INSTALL_MANIFEST:
            with self.subTest(source=item["source"]):
                source = repo_path(str(item["source"]))
                self.assertTrue(source.is_file(), source)
                self.assertIsInstance(item["mode"], int)
                if int(item["mode"]) & 0o111:
                    self.assertTrue(os.access(source, os.X_OK), source)

    def test_python_sources_compile(self) -> None:
        for item in INSTALL_MANIFEST:
            if item.get("kind") != "python":
                continue
            with self.subTest(source=item["source"]):
                source = repo_path(str(item["source"]))
                compile(source.read_text(encoding="utf-8"), str(source), "exec")

    def test_shell_entrypoints_are_portable_and_exec_preserving(self) -> None:
        paths = [
            repo_path("src/bin/codex-computer-use-native-launcher"),
            repo_path("src/bin/codex-computer-use-broker"),
            repo_path("src/plugin-shim/computer-use/codex-computer-use-mcp"),
        ]
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(ABSOLUTE_HOME_MARKER, text)
                self.assertIn("$HOME/.codex", text)
                self.assertIn("exec ", text)
                self.assertNotIn("osascript", text)
                self.assertNotIn("cliclick", text)

    def test_dialog_autopilot_is_manifest_owned_but_mcp_separate(self) -> None:
        manifest_sources = {str(item["source"]) for item in INSTALL_MANIFEST}
        self.assertIn("src/bin/codex-dialog-autopilot", manifest_sources)
        self.assertFalse(any(source.startswith("src/skills/macos-computer-use/references/") for source in manifest_sources))
        text = repo_path("src/bin/codex-dialog-autopilot").read_text(encoding="utf-8")
        self.assertIn("operator safety net", text)
        self.assertIn("codex-dialog-autopilot", text)
        self.assertNotIn("SkyComputerUseClient mcp", text)
        self.assertNotIn("mcpServers", text)
        safe_process_line = next(line for line in text.splitlines() if line.startswith("set safeProcessNames"))
        for broad_app in ["Google Chrome", "Safari", "Terminal", "iTerm2", "Keyboard Maestro", "SecurityAgent", "securityagent"]:
            self.assertNotIn(broad_app, safe_process_line)
        safe_needles_line = next(line for line in text.splitlines() if line.startswith("set safeNeedles"))
        for privacy_needle in ["Datenschutz und Sicherheit", "Daten aus anderen Apps", "App-Daten", "control", "steuern"]:
            self.assertNotIn(privacy_needle, safe_needles_line)
        strong_buttons_line = next(line for line in text.splitlines() if line.startswith("set strongButtons"))
        self.assertNotIn("Trust", strong_buttons_line)
        self.assertNotIn("Vertrauen", strong_buttons_line)
        self.assertIn("isStrongButton and processIsSafe and textIsSafe", text)
        self.assertNotIn("isStrongButton and (processIsSafe or textIsSafe)", text)

    def test_guard_generates_portable_shell_wrappers(self) -> None:
        guard = repo_path("src/bin/codex-computer-use-guard").read_text(encoding="utf-8")
        guard_module = load_guard_module()
        launcher = repo_path("src/bin/codex-computer-use-native-launcher").read_text(encoding="utf-8")
        self.assertEqual(launcher, guard_module._native_launcher_text())
        self.assertIn('exec "$HOME/.codex/bin/codex-computer-use-native-launcher" "$@"', guard)
        self.assertIn('"$HOME/.codex/bin/codex-computer-use-guard" ensure-config', guard)
        self.assertLess(
            guard.index('$HOME/.codex/computer-use/Codex Computer Use.app'),
            guard.index('$HOME/.codex/plugins/marketplaces/openai-bundled/plugins/computer-use'),
        )
        self.assertIn('$HOME/.codex/plugins/cache/openai-bundled/computer-use"/*/', guard)
        self.assertIn('for native_binary in "${native_candidates[@]}"; do', guard)
        self.assertIn('"cleanup-mcp-clients"', guard)
        self.assertIn("post_smoke_mcp_cleanup = cleanup_stale_mcp_clients(kill_duplicates=False)", guard)
        self.assertIn('"post_smoke_mcp_cleanup": post_smoke_mcp_cleanup', guard)
        self.assertNotIn("${{", guard)

    def test_ensure_config_repairs_persistence_layer(self) -> None:
        guard = repo_path("src/bin/codex-computer-use-guard").read_text(encoding="utf-8")
        ensure_config_branch = guard[guard.index('elif command in {"ensure-config", "repair-config"}') :]
        self.assertIn("launch_agent_changed, launch_agent_loaded = ensure_launch_agent()", ensure_config_branch)
        self.assertIn('"launch_agent_loaded": launch_agent_loaded', ensure_config_branch)
        self.assertIn('"bootstrap_exists": BOOTSTRAP.is_file()', ensure_config_branch)
        self.assertIn('"guard_backup_exists": GUARD_BACKUP.is_file()', ensure_config_branch)

    def test_guard_health_fails_closed_on_duplicate_mcp_clients(self) -> None:
        guard = load_guard_module()
        health = guard._health_layers(
            configured=True,
            discoverable=True,
            runtime_ready=True,
            native_smoke={
                "appserver_rendezvous": True,
                "operational": True,
                "second_mouse_verified": True,
            },
            ownership={"ok": False},
        )
        self.assertFalse(health["mcp_client_ownership"])
        self.assertFalse(health["appserver_rendezvous"])
        self.assertFalse(health["operational"])
        self.assertFalse(health["second_mouse_verified"])

    def test_guard_duplicate_mcp_cleanup_keeps_newest_client_per_parent(self) -> None:
        guard = load_guard_module()
        parent = os.getpid()
        killed: list[int] = []
        guard._processes_matching = lambda needle: [
            (101, parent, "/tmp/SkyComputerUseClient mcp"),
            (102, parent, "/tmp/SkyComputerUseClient mcp"),
            (103, parent, "/tmp/SkyComputerUseClient mcp"),
        ]
        guard._process_age_seconds = lambda pid: {101: 120, 102: 90, 103: 5}[pid]
        guard._kill_pid = lambda pid: killed.append(pid) or True

        cleanup = guard.cleanup_stale_mcp_clients(kill_duplicates=True)

        self.assertEqual(sorted(killed), [101, 102])
        self.assertEqual(cleanup["running"], 3)
        self.assertEqual(cleanup["skipped_young"], [])

    def test_guard_default_mcp_cleanup_does_not_kill_active_duplicates(self) -> None:
        guard = load_guard_module()
        parent = os.getpid()
        killed: list[int] = []
        guard._processes_matching = lambda needle: [
            (201, parent, "/tmp/SkyComputerUseClient mcp"),
            (202, parent, "/tmp/SkyComputerUseClient mcp"),
        ]
        guard._process_age_seconds = lambda pid: 120
        guard._kill_pid = lambda pid: killed.append(pid) or True

        cleanup = guard.cleanup_stale_mcp_clients(kill_duplicates=False)

        self.assertEqual(killed, [])
        self.assertEqual(cleanup["running"], 2)

    def test_native_smoke_cleanup_removes_temp_text_files(self) -> None:
        guard = load_guard_module()
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            current = temp_dir / "codex-cu-native-smoke-123-456.txt"
            stale = temp_dir / "codex-cu-native-smoke-111-222.txt"
            unrelated = temp_dir / "not-a-smoke.txt"
            current.write_text("current", encoding="utf-8")
            stale.write_text("stale", encoding="utf-8")
            unrelated.write_text("keep", encoding="utf-8")

            cleanup = guard._cleanup_native_smoke_temp_files(current)

            self.assertEqual(cleanup["errors"], [])
            self.assertEqual(cleanup["removed_count"], 2)
            self.assertTrue(cleanup["current_removed"])
            self.assertFalse(current.exists())
            self.assertFalse(stale.exists())
            self.assertTrue(unrelated.exists())

    def test_textedit_close_no_windows_counts_as_cleanup_evidence(self) -> None:
        guard = load_guard_module()
        events = [
            {
                "type": "item.completed",
                "item": {
                    "type": "mcp_tool_call",
                    "server": "computer-use",
                    "tool": "press_key",
                    "arguments": {"app": "com.apple.TextEdit", "key": "super+w"},
                    "status": "failed",
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": "Computer Use server error -10005: noWindowsAvailable",
                            }
                        ]
                    },
                },
            }
        ]

        self.assertEqual(guard._mcp_tool_attempt_count(events, "press_key"), 1)
        self.assertFalse(
            guard._press_key_completed_for(events, app="com.apple.TextEdit", key="super+w")
        )
        self.assertTrue(guard._textedit_close_reported_no_windows(events))
        self.assertTrue(
            guard._press_key_reported_no_windows(events, app="com.apple.TextEdit", key="super+w")
        )

    def test_native_smoke_uses_safari_input_not_textedit_save(self) -> None:
        guard_source = repo_path("src/bin/codex-computer-use-guard").read_text(encoding="utf-8")
        smoke_body = guard_source[
            guard_source.index("success_line =")
            : guard_source.index('cmd = [str(OPENAI_CODEX_EXEC), "exec", "--skip-git-repo-check", "--json", prompt]')
        ]

        self.assertIn("Native Smoke Input", smoke_body)
        self.assertIn("Call computer-use/type_text with app com.apple.Safari", smoke_body)
        self.assertNotIn("com.apple.TextEdit", smoke_body)
        self.assertNotIn("super+s", smoke_body)

    def test_mcp_tool_result_contains_finds_safari_token_evidence(self) -> None:
        guard = load_guard_module()
        events = [
            {
                "type": "item.completed",
                "item": {
                    "type": "mcp_tool_call",
                    "server": "computer-use",
                    "tool": "get_app_state",
                    "arguments": {"app": "com.apple.Safari"},
                    "status": "completed",
                    "result": {"content": [{"type": "text", "text": "Value: TOKEN-123"}]},
                },
            }
        ]

        self.assertTrue(
            guard._mcp_tool_result_contains(events, "get_app_state", "TOKEN-123", app="com.apple.Safari")
        )
        self.assertFalse(
            guard._mcp_tool_result_contains(events, "get_app_state", "TOKEN-123", app="com.apple.TextEdit")
        )

    def test_launch_agent_labels_are_public_safe(self) -> None:
        self.assertEqual(GUARD_LAUNCH_AGENT_LABEL, "io.github.codex-computer-use-foundation.guard")
        self.assertEqual(
            DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL,
            "io.github.codex-computer-use-foundation.dialog-autopilot",
        )
        for path in [
            repo_path("src/bin/codex-computer-use-guard"),
            repo_path("src/bin/codex-dialog-autopilot"),
            repo_path("scripts/install.py"),
            repo_path("scripts/verify-live-state.py"),
        ]:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(
                    "io.github.codex-computer-use-foundation" in text
                    or "GUARD_LAUNCH_AGENT_LABEL" in text
                    or "DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL" in text
                )
                self.assertNotIn(ABSOLUTE_HOME_MARKER, text)

    def test_plugin_shim_mcp_json_stays_relative(self) -> None:
        payload = json.loads(repo_path("src/plugin-shim/computer-use/.mcp.json").read_text(encoding="utf-8"))
        server = payload["mcpServers"]["computer-use"]
        self.assertEqual(server["command"], "./codex-computer-use-mcp")
        self.assertEqual(server["args"], ["mcp"])
        self.assertEqual(server["cwd"], ".")

    def test_plugin_shim_does_not_publish_visible_skill_source(self) -> None:
        manifest_sources = {str(item["source"]) for item in INSTALL_MANIFEST}
        self.assertFalse(any(source.startswith("src/plugin-shim/computer-use/skills/") for source in manifest_sources))
        self.assertFalse(repo_path("src/plugin-shim/computer-use/skills/computer-use/SKILL.md").exists())
        self.assertIn(
            ".codex/plugins/cache/openai-bundled/computer-use/*/skills/computer-use/SKILL.md",
            FOUNDATION_OBSOLETE_GLOBS,
        )

    def test_github_issue_config_disables_blank_security_bypass(self) -> None:
        issue_config = repo_path(".github/ISSUE_TEMPLATE/config.yml").read_text(encoding="utf-8")
        self.assertIn("blank_issues_enabled: false", issue_config)
        self.assertIn("privately-reporting-a-security-vulnerability", issue_config)
        self.assertIn("adding-a-security-policy", issue_config)

    def test_guard_suppresses_plugin_skill_publication(self) -> None:
        module = load_guard_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical = root / ".codex" / "skills" / "macos-computer-use" / "SKILL.md"
            canonical.parent.mkdir(parents=True)
            canonical.write_text("---\nname: computer-use\n---\n", encoding="utf-8")
            plugin = root / "plugin"
            manifest = plugin / ".codex-plugin" / "plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps({"name": "computer-use", "version": "1.0.0", "mcpServers": "./.mcp.json", "skills": "./skills/"})
                + "\n",
                encoding="utf-8",
            )
            skill = plugin / "skills" / "computer-use" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: computer-use-shim\n---\n", encoding="utf-8")
            agent_metadata = skill.parent / "agents" / "openai.yaml"
            agent_metadata.parent.mkdir()
            agent_metadata.write_text('interface:\n  display_name: "Computer Use Shim"\n', encoding="utf-8")

            old_canonical = module.CANONICAL_COMPUTER_USE_SKILL
            try:
                module.CANONICAL_COMPUTER_USE_SKILL = canonical
                self.assertTrue(module.ensure_plugin_skill_suppressed(plugin))
                self.assertTrue(module._plugin_skill_suppressed_ok(plugin))
            finally:
                module.CANONICAL_COMPUTER_USE_SKILL = old_canonical

            self.assertFalse((plugin / "skills" / "computer-use").exists())
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertNotIn("skills", payload)

    def test_installer_and_verifier_against_temp_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            (home / ".codex").mkdir()
            install = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "install.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--skip-runtime-checks",
                    "--skip-postinstall",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            for item in INSTALL_MANIFEST:
                target = target_path(home, item)
                self.assertTrue(target.is_file(), target)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), int(item["mode"]), target)
            verify = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "verify-live-state.py"),
                    "--home",
                    str(home),
                    "--expect-installed-from-repo",
                    "--skip-live-invariants",
                    "--skip-launchctl",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(verify.returncode, 0, verify.stdout)
            payload = json.loads(verify.stdout)
            self.assertTrue(payload["ok"])

    def test_installer_scrubs_direct_aliases_and_foundation_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "\n".join(
                    [
                        'notify = ["{}/.codex/bin/codex-computer-use-notify", "turn-ended"]'.format(home),
                        "",
                        '[plugins."computer-use@openai-bundled"]',
                        "enabled = true",
                        "",
                        "[marketplaces.openai-bundled]",
                        'source_type = "local"',
                        f'source = "{home}/.codex/plugins/marketplaces/openai-bundled"',
                        "",
                        "[mcp_servers.computer-use]",
                        f'command = "{home}/.codex/bin/codex-computer-use-native-launcher"',
                        'args = ["mcp"]',
                        "",
                        "[plugins.\"browser@openai-bundled\"]",
                        "enabled = true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            install = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "install.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--skip-runtime-checks",
                    "--skip-postinstall",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            updated = config.read_text(encoding="utf-8")
            self.assertNotIn("codex-computer-use-notify", updated)
            self.assertNotIn('[plugins."computer-use@openai-bundled"]', updated)
            self.assertNotIn("[marketplaces.openai-bundled]", updated)
            for header in DIRECT_MCP_HEADERS:
                self.assertNotIn(f"[{header}]", updated)
            self.assertIn('[plugins."browser@openai-bundled"]', updated)

    def test_installer_removes_obsolete_internal_reference_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            for relative in FOUNDATION_OBSOLETE_TARGETS:
                target = home / relative
                if target.suffix:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("old internal troubleshooting history\n", encoding="utf-8")
                else:
                    target.mkdir(parents=True, exist_ok=True)
            install = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "install.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--skip-runtime-checks",
                    "--skip-postinstall",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            payload = json.loads(install.stdout)
            self.assertTrue(any("remove obsolete installed file" in action for action in payload["actions"]))
            for relative in FOUNDATION_OBSOLETE_TARGETS:
                self.assertFalse((home / relative).exists(), relative)

    def test_uninstall_removes_manifest_generated_state_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "\n".join(
                    [
                        'notify = ["{}/.codex/bin/codex-computer-use-notify", "turn-ended"]'.format(home),
                        "",
                        '[plugins."computer-use@openai-bundled"]',
                        "enabled = true",
                        "",
                        "[marketplaces.openai-bundled]",
                        'source_type = "local"',
                        f'source = "{home}/.codex/plugins/marketplaces/openai-bundled"',
                        "",
                        "[mcp_servers.computer-use-native]",
                        f'command = "{home}/.codex/bin/codex-computer-use-native-launcher"',
                        'args = ["mcp"]',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            for item in INSTALL_MANIFEST:
                target = target_path(home, item)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("installed\n", encoding="utf-8")
            generated = [
                home / ".codex/plugins/marketplaces/openai-bundled",
                home / ".codex/.tmp/bundled-marketplaces/openai-bundled",
                home / ".codex/plugins/cache/openai-bundled/computer-use",
                home / ".codex/computer-use",
                home / ".codex/state/computer-use-guard",
                home / ".codex/state/computer-use-foundation",
                home / "Library/Application Support/CodexComputerUseGuard",
            ]
            for path in generated:
                path.mkdir(parents=True, exist_ok=True)
                (path / "marker").write_text("x\n", encoding="utf-8")
            unrelated_launch_agent = home / "Library/LaunchAgents/com.example.codex-computer-use-guard.plist"
            expected_launch_agent = home / f"Library/LaunchAgents/{GUARD_LAUNCH_AGENT_LABEL}.plist"
            unrelated_launch_agent.parent.mkdir(parents=True, exist_ok=True)
            unrelated_launch_agent.write_text(
                '<?xml version="1.0"?><plist version="1.0"><dict><key>Label</key><string>com.example.codex-computer-use-guard</string></dict></plist>',
                encoding="utf-8",
            )
            expected_launch_agent.write_text(
                f'<?xml version="1.0"?><plist version="1.0"><dict><key>Label</key><string>{GUARD_LAUNCH_AGENT_LABEL}</string></dict></plist>',
                encoding="utf-8",
            )
            uninstall = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "uninstall.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--purge-state",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            for item in INSTALL_MANIFEST:
                self.assertFalse(target_path(home, item).exists(), item["target"])
            for path in generated:
                self.assertFalse(path.exists(), path)
            self.assertTrue(unrelated_launch_agent.exists())
            self.assertFalse(expected_launch_agent.exists())
            updated = config.read_text(encoding="utf-8")
            self.assertNotIn("codex-computer-use-notify", updated)
            self.assertNotIn("computer-use@openai-bundled", updated)
            self.assertNotIn("mcp_servers.computer-use-native", updated)

    def test_public_release_package_installs_from_clean_temp_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            release_out = tmp_path / "release"
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(release_out),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            package = release_out / "public"
            self.assertTrue((package / "scripts/install.py").is_file())
            self.assertTrue((package / "CONTRIBUTING.md").is_file())
            self.assertTrue((package / "LICENSE").is_file())
            self.assertTrue((package / "SECURITY.md").is_file())
            self.assertTrue((package / "docs/WHAT-IS-COMPUTER-USE.md").is_file())
            self.assertTrue((package / ".github/FUNDING.yml").is_file())
            self.assertTrue((package / ".github/workflows/ci.yml").is_file())
            self.assertFalse((package / "docs/internal").exists())
            self.assertFalse((package / "src/skills/macos-computer-use/references").exists())
            home = tmp_path / "home"
            (home / ".codex").mkdir(parents=True)
            install = subprocess.run(
                [
                    sys.executable,
                    str(package / "scripts/install.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--skip-runtime-checks",
                    "--skip-postinstall",
                ],
                cwd=package,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            verify = subprocess.run(
                [
                    sys.executable,
                    str(package / "scripts/verify-live-state.py"),
                    "--home",
                    str(home),
                    "--expect-installed-from-repo",
                    "--skip-live-invariants",
                    "--skip-launchctl",
                    "--json",
                ],
                cwd=package,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(verify.returncode, 0, verify.stdout)

    def test_public_release_manifest_and_tarball_have_sha256_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(tmp_path / "release"),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            payload = json.loads(build.stdout)
            tarball = Path(payload["tarball"])
            checksum_file = Path(payload["checksum_file"])
            digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
            self.assertEqual(payload["tarball_sha256"], digest)
            self.assertTrue(checksum_file.is_file())
            self.assertIn(digest, checksum_file.read_text(encoding="utf-8"))
            manifest = json.loads((tmp_path / "release" / "public" / "PUBLIC_RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 3)
            self.assertIn("git_commit", manifest)
            self.assertIn("git_tag", manifest)
            self.assertIn("github_run_id", manifest)
            self.assertIn("source_repository", manifest)
            self.assertFalse(any(path.startswith("docs/internal/") for path in manifest["files"]))
            self.assertFalse(any(path.startswith("src/skills/macos-computer-use/references/") for path in manifest["files"]))
            self.assertEqual(
                manifest["file_sha256"]["README.md"],
                hashlib.sha256((tmp_path / "release" / "public" / "README.md").read_bytes()).hexdigest(),
            )

    def test_public_release_tarball_metadata_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(tmp_path / "release"),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            payload = json.loads(build.stdout)
            with tarfile.open(payload["tarball"], "r:gz") as archive:
                for member in archive.getmembers():
                    self.assertEqual(member.uid, 0, member.name)
                    self.assertEqual(member.gid, 0, member.name)
                    self.assertEqual(member.uname, "root", member.name)
                    self.assertEqual(member.gname, "wheel", member.name)
                    self.assertEqual(member.mtime, 0, member.name)

    def test_build_public_release_uses_tracked_files_by_default(self) -> None:
        module_path = SCRIPTS / "build-public-release.py"
        loader = importlib.machinery.SourceFileLoader("build_public_release_under_test", str(module_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)

        calls: list[list[str]] = []

        def fake_run(cmd: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        old_run = module.run
        try:
            module.run = fake_run
            module.tracked_files()
            module.tracked_files(include_untracked=True)
        finally:
            module.run = old_run

        self.assertEqual(calls[0], ["git", "ls-files", "--cached"])
        self.assertEqual(calls[1], ["git", "ls-files", "--cached", "--others", "--exclude-standard"])

    def test_release_drill_exercises_extracted_tarball_from_clean_temp_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            drill = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "release-drill.py"),
                    "--output-dir",
                    str(tmp_path / "release"),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(drill.returncode, 0, drill.stdout)
            payload = json.loads(drill.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["mode"], "temp-home")
            self.assertTrue(Path(payload["tarball"]).is_file())
            self.assertTrue(payload["sha256_verified"])
            command_texts = [" ".join(item["cmd"]) for item in payload["commands"]]
            self.assertTrue(any("scripts/install.py" in item for item in command_texts), payload)
            self.assertTrue(any("scripts/verify-live-state.py" in item for item in command_texts), payload)
            package = Path(payload["package"])
            package_commands = [item for item in payload["commands"] if "scripts/install.py" in " ".join(item["cmd"]) or "scripts/verify-live-state.py" in " ".join(item["cmd"])]
            self.assertTrue(all(Path(str(item["cwd"])) == package for item in package_commands), payload)

    def test_release_drill_refuses_live_without_yes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            drill = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "release-drill.py"),
                    "--output-dir",
                    str(Path(tmp) / "release"),
                    "--name",
                    "public",
                    "--live",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(drill.returncode, 0, drill.stdout)
            self.assertIn("live release drill requires --yes", drill.stdout)

    def test_release_drill_refuses_existing_tarball_without_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tarball = Path(tmp) / "public.tar.gz"
            tarball.write_bytes(b"not a tarball\n")
            drill = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "release-drill.py"),
                    "--tarball",
                    str(tarball),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(drill.returncode, 0, drill.stdout)
            self.assertIn("requires --expected-sha256", drill.stdout)

    def test_release_drill_rejects_malformed_checksum_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tarball = Path(tmp) / "public.tar.gz"
            checksum = Path(tmp) / "public.tar.gz.sha256"
            tarball.write_bytes(b"not a tarball\n")
            checksum.write_text("not-a-sha\n", encoding="utf-8")
            drill = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "release-drill.py"),
                    "--tarball",
                    str(tarball),
                    "--checksum-file",
                    str(checksum),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(drill.returncode, 0, drill.stdout)
            self.assertIn("invalid sha256", drill.stdout)

    def test_release_drill_rejects_http_url(self) -> None:
        drill = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "release-drill.py"),
                "--url",
                "http://example.invalid/public.tar.gz",
                "--expected-sha256",
                "0" * 64,
                "--name",
                "public",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertNotEqual(drill.returncode, 0, drill.stdout)
        self.assertIn("release URL must use https", drill.stdout)

    def test_release_drill_requires_sha_for_downloaded_archives(self) -> None:
        drill = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "release-drill.py"),
                "--url",
                "https://example.invalid/public.tar.gz",
                "--allow-unverified-archive",
                "--name",
                "public",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertNotEqual(drill.returncode, 0, drill.stdout)
        self.assertIn("requires SHA256 verification", drill.stdout)

    def test_release_drill_rejects_path_escaping_tarball(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tarball = Path(tmp) / "escape.tar.gz"
            with tarfile.open(tarball, "w:gz") as archive:
                info = tarfile.TarInfo("../escape.txt")
                data = b"escape\n"
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
            drill = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "release-drill.py"),
                    "--tarball",
                    str(tarball),
                    "--expected-sha256",
                    digest,
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(drill.returncode, 0, drill.stdout)
            self.assertIn("unsafe tar member path", drill.stdout)

    def test_release_drill_rejects_link_member_tarball(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tarball = Path(tmp) / "link.tar.gz"
            with tarfile.open(tarball, "w:gz") as archive:
                root = tarfile.TarInfo("public")
                root.type = tarfile.DIRTYPE
                archive.addfile(root)
                link = tarfile.TarInfo("public/link")
                link.type = tarfile.SYMTYPE
                link.linkname = "/tmp/target"
                archive.addfile(link)
            digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
            drill = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "release-drill.py"),
                    "--tarball",
                    str(tarball),
                    "--expected-sha256",
                    digest,
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(drill.returncode, 0, drill.stdout)
            self.assertIn("refusing link member", drill.stdout)

    def test_release_drill_rejects_special_member_tarball(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tarball = Path(tmp) / "special.tar.gz"
            with tarfile.open(tarball, "w:gz") as archive:
                root = tarfile.TarInfo("public")
                root.type = tarfile.DIRTYPE
                archive.addfile(root)
                fifo = tarfile.TarInfo("public/fifo")
                fifo.type = tarfile.FIFOTYPE
                archive.addfile(fifo)
            digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
            drill = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "release-drill.py"),
                    "--tarball",
                    str(tarball),
                    "--expected-sha256",
                    digest,
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(drill.returncode, 0, drill.stdout)
            self.assertIn("refusing special member", drill.stdout)

    def test_build_public_release_refuses_non_release_directory_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            protected = tmp_path / "protected"
            protected.mkdir()
            (protected / "keep.txt").write_text("keep\n", encoding="utf-8")
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(tmp_path),
                    "--name",
                    "protected",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(build.returncode, 0, build.stdout)
            self.assertTrue((protected / "keep.txt").is_file())

    def test_build_public_release_refuses_tampered_owned_directory_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(tmp_path / "release"),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            readme = tmp_path / "release" / "public" / "README.md"
            readme.write_text("tampered\n", encoding="utf-8")
            rebuild = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(tmp_path / "release"),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(rebuild.returncode, 0, rebuild.stdout)
            self.assertEqual(readme.read_text(encoding="utf-8"), "tampered\n")

    def test_build_public_release_refuses_non_release_tarball_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            protected_tarball = tmp_path / "protected.tar.gz"
            protected_tarball.write_text("keep\n", encoding="utf-8")
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(tmp_path / "release"),
                    "--name",
                    "public",
                    "--tarball",
                    str(protected_tarball),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(build.returncode, 0, build.stdout)
            self.assertEqual(protected_tarball.read_text(encoding="utf-8"), "keep\n")

    def test_build_public_release_refuses_non_release_tarball_inside_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            output_dir = tmp_path / "release"
            output_dir.mkdir()
            protected_tarball = output_dir / "protected.tar.gz"
            protected_tarball.write_text("keep\n", encoding="utf-8")
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(output_dir),
                    "--name",
                    "public",
                    "--tarball",
                    str(protected_tarball),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(build.returncode, 0, build.stdout)
            self.assertIn("refusing to replace non-release tarball", build.stdout)
            self.assertEqual(protected_tarball.read_text(encoding="utf-8"), "keep\n")

    def test_build_public_release_replaces_owned_tarball(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            for _ in range(2):
                build = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "build-public-release.py"),
                        "--output-dir",
                        str(tmp_path / "release"),
                        "--name",
                        "public",
                    ],
                    cwd=REPO_ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(build.returncode, 0, build.stdout)
            self.assertTrue((tmp_path / "release" / "public.tar.gz").is_file())

    def test_build_public_release_replaces_owned_directory_with_finder_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(tmp_path / "release"),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            finder_metadata = tmp_path / "release" / "public" / ".DS_Store"
            finder_metadata.write_text("finder metadata\n", encoding="utf-8")
            rebuild = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(tmp_path / "release"),
                    "--name",
                    "public",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(rebuild.returncode, 0, rebuild.stdout)
            self.assertFalse(finder_metadata.exists())

    def test_build_public_release_refuses_path_escaped_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(Path(tmp) / "release"),
                    "--name",
                    "../escaped",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(build.returncode, 0, build.stdout)
            self.assertIn("single safe directory name", build.stdout)

    def test_build_public_release_refuses_spoofed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            protected = tmp_path / "protected"
            protected.mkdir()
            (protected / "PUBLIC_RELEASE_MANIFEST.json").write_text(
                '{"name":"protected","files":[]}\n',
                encoding="utf-8",
            )
            (protected / "keep.txt").write_text("keep\n", encoding="utf-8")
            build = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build-public-release.py"),
                    "--output-dir",
                    str(tmp_path),
                    "--name",
                    "protected",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(build.returncode, 0, build.stdout)
            self.assertTrue((protected / "keep.txt").is_file())

    def test_build_public_release_works_without_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            source_copy = tmp_path / "source"
            shutil.copytree(
                REPO_ROOT,
                source_copy,
                ignore=shutil.ignore_patterns(".git", "var", "__pycache__", ".pytest_cache"),
            )
            internal_src = source_copy / "src/internal-release-sentinel.txt"
            internal_src.write_text("do not publish\n", encoding="utf-8")
            build = subprocess.run(
                [
                    sys.executable,
                    str(source_copy / "scripts/build-public-release.py"),
                    "--output-dir",
                    str(tmp_path / "release"),
                    "--name",
                    "public",
                ],
                cwd=source_copy,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            package = tmp_path / "release" / "public"
            self.assertFalse((package / "src/internal-release-sentinel.txt").exists())
            home = tmp_path / "home"
            (home / ".codex").mkdir(parents=True)
            install = subprocess.run(
                [
                    sys.executable,
                    str(package / "scripts/install.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--skip-runtime-checks",
                    "--skip-postinstall",
                ],
                cwd=package,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stdout)

    def test_verifier_detects_disabled_computer_use_tool_suggest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[other]\ndisabled_tools = ["something-else"]\n[tool_suggest]\ndisabled_tools = ["computer-use@openai-bundled"]\n',
                encoding="utf-8",
            )
            verify = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "verify-live-state.py"),
                    "--home",
                    str(home),
                    "--skip-launchctl",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(verify.returncode, 0, verify.stdout)
            payload = json.loads(verify.stdout)
            matching = [item for item in payload["checks"] if item["name"] == "computer-use not disabled in tool_suggest"]
            self.assertEqual(len(matching), 1)
            self.assertFalse(matching[0]["ok"])

    def test_guard_scrubs_string_form_disabled_computer_use_tool_suggest(self) -> None:
        guard = load_guard_module()
        config = "\n".join(
            [
                '[plugins."computer-use@openai-bundled"]',
                "enabled = true",
                "",
                "[tool_suggest]",
                'disabled_tools = ["other-tool", "computer-use@openai-bundled", { type = "plugin", id = "computer-use@openai-bundled" }]',
            ]
        ) + "\n"

        scrubbed = guard._scrub_computer_use_disabled_tool(config)

        self.assertIn('[plugins."computer-use@openai-bundled"]', scrubbed)
        self.assertIn('"other-tool"', scrubbed)
        disabled_arrays = re.findall(r"disabled_tools\s*=\s*\[(.*?)\]", scrubbed, re.DOTALL)
        self.assertFalse(any("computer-use@openai-bundled" in item for item in disabled_arrays))
        self.assertFalse(guard._computer_use_disabled(scrubbed))

    def test_installer_refuses_manifest_target_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            victim = home / "victim.txt"
            victim.write_text("keep\n", encoding="utf-8")
            target = home / ".codex/bin/codex-computer-use-guard"
            target.parent.mkdir(parents=True)
            target.symlink_to(victim)
            install = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "install.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--skip-runtime-checks",
                    "--skip-postinstall",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(install.returncode, 0, install.stdout)
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep\n")

    def test_installer_refuses_symlinked_codex_home_before_scrubbing_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            outside = Path(tmp).resolve() / "outside"
            outside_config = outside / "config.toml"
            outside.mkdir(parents=True)
            outside_config.write_text('[plugins."computer-use@openai-bundled"]\nenabled = true\n', encoding="utf-8")
            home.mkdir()
            (home / ".codex").symlink_to(outside, target_is_directory=True)
            install = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "install.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--skip-runtime-checks",
                    "--skip-postinstall",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(install.returncode, 0, install.stdout)
            self.assertIn("symlink", install.stdout)
            self.assertIn("computer-use@openai-bundled", outside_config.read_text(encoding="utf-8"))

    def test_uninstall_unlinks_generated_symlink_without_deleting_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            victim = home / "victim-dir"
            victim.mkdir()
            (victim / "keep.txt").write_text("keep\n", encoding="utf-8")
            link = home / ".codex/plugins/marketplaces/openai-bundled"
            link.parent.mkdir(parents=True)
            link.symlink_to(victim, target_is_directory=True)
            uninstall = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "uninstall.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--purge-state",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertFalse(link.exists())
            self.assertTrue((victim / "keep.txt").is_file())

    def test_uninstall_refuses_symlinked_parent_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            outside = Path(tmp).resolve() / "outside"
            victim = outside / "marketplaces/openai-bundled"
            victim.mkdir(parents=True)
            (victim / "keep.txt").write_text("keep\n", encoding="utf-8")
            (home / ".codex").mkdir(parents=True)
            (home / ".codex/plugins").symlink_to(outside, target_is_directory=True)
            uninstall = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "uninstall.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--purge-state",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertTrue((victim / "keep.txt").is_file())

    def test_uninstall_refuses_symlinked_codex_home_before_scrubbing_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            outside = Path(tmp).resolve() / "outside"
            outside.mkdir(parents=True)
            outside_config = outside / "config.toml"
            outside_config.write_text('[plugins."computer-use@openai-bundled"]\nenabled = true\n', encoding="utf-8")
            home.mkdir()
            (home / ".codex").symlink_to(outside, target_is_directory=True)
            uninstall = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "uninstall.py"),
                    "--home",
                    str(home),
                    "--yes",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertIn("symlink", uninstall.stdout)
            self.assertIn("computer-use@openai-bundled", outside_config.read_text(encoding="utf-8"))

    def test_rollback_removes_files_created_by_fresh_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            (home / ".codex").mkdir()
            install = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "install.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--skip-runtime-checks",
                    "--skip-postinstall",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            snapshot = json.loads(install.stdout)["snapshot"]
            rollback = subprocess.run(
                [sys.executable, str(SCRIPTS / "rollback.py"), snapshot, "--home", str(home), "--yes"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(rollback.returncode, 0, rollback.stdout)
            for item in INSTALL_MANIFEST:
                self.assertFalse(target_path(home, item).exists(), item["target"])

    def test_rollback_restores_config_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text("[plugins]\noriginal = true\n", encoding="utf-8")
            install = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "install.py"),
                    "--home",
                    str(home),
                    "--yes",
                    "--skip-runtime-checks",
                    "--skip-postinstall",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            snapshot = json.loads(install.stdout)["snapshot"]
            config.write_text("[plugins]\nchanged = true\n", encoding="utf-8")
            rollback = subprocess.run(
                [sys.executable, str(SCRIPTS / "rollback.py"), snapshot, "--home", str(home), "--yes"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(rollback.returncode, 0, rollback.stdout)
            self.assertEqual(config.read_text(encoding="utf-8"), "[plugins]\noriginal = true\n")

    def test_rollback_refuses_backup_path_escaping_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = root / "home"
            snapshot = root / "snapshot"
            home.mkdir()
            snapshot.mkdir()
            (root / "outside.txt").write_text("outside\n", encoding="utf-8")
            (snapshot / "manifest.json").write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "target": ".codex/bin/codex-computer-use-guard",
                                "existed": True,
                                "backup": "../outside.txt",
                                "mode": "0o755",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            rollback = subprocess.run(
                [sys.executable, str(SCRIPTS / "rollback.py"), str(snapshot), "--home", str(home), "--yes"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(rollback.returncode, 0, rollback.stdout)
            self.assertIn("escapes snapshot", rollback.stdout)

    def test_redaction_covers_toml_and_authorization_headers(self) -> None:
        dummy_key = "abcdef" + "1234567890"
        dummy_token = "ghp_" + "abcdefghijklmnopqrstuvwx"
        text = f'api_key = "{dummy_key}"\nAuthorization: Bearer {dummy_token}\npath = "/Users/privateuser/.codex/config.toml"\n'
        redacted = redact_text(text)
        self.assertNotIn(dummy_key, redacted)
        self.assertNotIn(dummy_token, redacted)
        self.assertNotIn("/Users/privateuser", redacted)
        self.assertIn("$HOME/.codex/config.toml", redacted)
        self.assertIn("<redacted>", redacted)

    def test_snapshot_live_state_redacts_home_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            (home / ".codex").mkdir(parents=True)
            snap = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "snapshot-live-state.py"),
                    "--home",
                    str(home),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(snap.returncode, 0, snap.stdout)
            payload = json.loads(snap.stdout)
            self.assertEqual(payload["home"], "$HOME")
            self.assertNotIn(str(home), snap.stdout)

            private = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "snapshot-live-state.py"),
                    "--home",
                    str(home),
                    "--include-private-paths",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(private.returncode, 0, private.stdout)
            self.assertEqual(json.loads(private.stdout)["home"], str(home))

    def test_secret_scan_detects_local_state_and_tokens(self) -> None:
        module_path = SCRIPTS / "secret-scan.py"
        loader = importlib.machinery.SourceFileLoader("secret_scan_under_test", str(module_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        fixture = REPO_ROOT / ".env.secret-scan-test"
        token = "sk-" + "a" * 32
        try:
            fixture.write_text(f"OPENAI_API_KEY={token}\n", encoding="utf-8")
            findings = module.scan_file(fixture)
            self.assertTrue(any("denylisted path" in finding for finding in findings), findings)
            self.assertTrue(any("possible secret" in finding for finding in findings), findings)
        finally:
            fixture.unlink(missing_ok=True)

    def test_public_release_audit_accepts_extra_personal_markers(self) -> None:
        module_path = SCRIPTS / "public-release-audit.py"
        loader = importlib.machinery.SourceFileLoader("public_release_audit_under_test", str(module_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        old_value = os.environ.get("PUBLIC_RELEASE_AUDIT_EXTRA_MARKERS")
        try:
            os.environ["PUBLIC_RELEASE_AUDIT_EXTRA_MARKERS"] = "Private Handle,another-marker"
            module = importlib.util.module_from_spec(spec)
            assert spec is not None and spec.loader is not None
            spec.loader.exec_module(module)
            markers = module.personal_markers()
            self.assertIn("Private Handle", markers)
            self.assertIn("another-marker", markers)
        finally:
            if old_value is None:
                os.environ.pop("PUBLIC_RELEASE_AUDIT_EXTRA_MARKERS", None)
            else:
                os.environ["PUBLIC_RELEASE_AUDIT_EXTRA_MARKERS"] = old_value

    def test_public_release_audit_ignores_generic_ci_account_markers(self) -> None:
        module_path = SCRIPTS / "public-release-audit.py"
        loader = importlib.machinery.SourceFileLoader("public_release_audit_ci_under_test", str(module_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        old_user = os.environ.get("USER")
        old_logname = os.environ.get("LOGNAME")
        try:
            os.environ["USER"] = "runner"
            os.environ["LOGNAME"] = "runner"
            module = importlib.util.module_from_spec(spec)
            assert spec is not None and spec.loader is not None
            spec.loader.exec_module(module)
            markers = module.personal_markers()
            self.assertNotIn("runner", markers)
        finally:
            if old_user is None:
                os.environ.pop("USER", None)
            else:
                os.environ["USER"] = old_user
            if old_logname is None:
                os.environ.pop("LOGNAME", None)
            else:
                os.environ["LOGNAME"] = old_logname


if __name__ == "__main__":
    unittest.main()
