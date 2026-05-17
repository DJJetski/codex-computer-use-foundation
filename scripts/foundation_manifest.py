#!/usr/bin/env python3
"""Shared install manifest for the Codex Computer Use repair package."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
USER_EXECUTABLE_MODE = 0o700

INSTALL_MANIFEST: list[dict[str, object]] = [
    {
        "source": "src/bin/codex-computer-use-guard",
        "target": ".codex/bin/codex-computer-use-guard",
        "mode": USER_EXECUTABLE_MODE,
        "kind": "python",
    },
    {
        "source": "src/bin/codex-computer-use-native-launcher",
        "target": ".codex/bin/codex-computer-use-native-launcher",
        "mode": USER_EXECUTABLE_MODE,
        "kind": "shell",
    },
    {
        "source": "src/bin/codex-computer-use-native-smoke",
        "target": ".codex/bin/codex-computer-use-native-smoke",
        "mode": USER_EXECUTABLE_MODE,
        "kind": "python",
    },
    {
        "source": "src/bin/codex-computer-use-preflight",
        "target": ".codex/bin/codex-computer-use-preflight",
        "mode": USER_EXECUTABLE_MODE,
        "kind": "python",
    },
    {
        "source": "src/bin/codex-computer-use-notify",
        "target": ".codex/bin/codex-computer-use-notify",
        "mode": USER_EXECUTABLE_MODE,
        "kind": "python",
    },
    {
        "source": "src/bin/codex-dialog-autopilot",
        "target": ".codex/bin/codex-dialog-autopilot",
        "mode": USER_EXECUTABLE_MODE,
        "kind": "python",
    },
    {
        "source": "src/bin/codex-computer-use-broker",
        "target": ".codex/bin/codex-computer-use-broker",
        "mode": USER_EXECUTABLE_MODE,
        "kind": "shell",
    },
    {
        "source": "src/skills/macos-computer-use/SKILL.md",
        "target": ".codex/skills/macos-computer-use/SKILL.md",
        "mode": 0o644,
        "kind": "text",
    },
    {
        "source": "src/skills/macos-computer-use/agents/openai.yaml",
        "target": ".codex/skills/macos-computer-use/agents/openai.yaml",
        "mode": 0o644,
        "kind": "text",
    },
    {
        "source": "src/plugin-shim/computer-use/.mcp.json",
        "target": ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/.mcp.json",
        "mode": 0o644,
        "kind": "json",
    },
    {
        "source": "src/plugin-shim/computer-use/codex-computer-use-mcp",
        "target": ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/codex-computer-use-mcp",
        "mode": USER_EXECUTABLE_MODE,
        "kind": "shell",
    },
]

SNAPSHOT_ROOT = ".codex/state/computer-use-foundation/snapshots"

OBSOLETE_SKILL_REFERENCE = "native-" "computer-use-" "hardening.md"

FOUNDATION_OBSOLETE_TARGETS = [
    f".codex/skills/macos-computer-use/references/{OBSOLETE_SKILL_REFERENCE}",
    ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/skills/computer-use/SKILL.md",
    ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/skills/computer-use/agents/openai.yaml",
    ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/skills/computer-use/agents",
    ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/skills/computer-use",
    ".codex/plugins/marketplaces/openai-bundled/plugins/computer-use/skills",
    ".codex/.tmp/bundled-marketplaces/openai-bundled/plugins/computer-use/skills/computer-use/SKILL.md",
    ".codex/.tmp/bundled-marketplaces/openai-bundled/plugins/computer-use/skills/computer-use/agents/openai.yaml",
    ".codex/.tmp/bundled-marketplaces/openai-bundled/plugins/computer-use/skills/computer-use/agents",
    ".codex/.tmp/bundled-marketplaces/openai-bundled/plugins/computer-use/skills/computer-use",
    ".codex/.tmp/bundled-marketplaces/openai-bundled/plugins/computer-use/skills",
]

FOUNDATION_OBSOLETE_GLOBS = [
    ".codex/plugins/cache/openai-bundled/computer-use/*/skills/computer-use/SKILL.md",
    ".codex/plugins/cache/openai-bundled/computer-use/*/skills/computer-use/agents/openai.yaml",
    ".codex/plugins/cache/openai-bundled/computer-use/*/skills/computer-use/agents",
    ".codex/plugins/cache/openai-bundled/computer-use/*/skills/computer-use",
    ".codex/plugins/cache/openai-bundled/computer-use/*/skills",
]

GUARD_LAUNCH_AGENT_LABEL = "io.github.codex-computer-use-foundation.guard"
DIALOG_AUTOPILOT_LAUNCH_AGENT_LABEL = "io.github.codex-computer-use-foundation.dialog-autopilot"

LEGACY_GUARD_LAUNCH_AGENT_LABELS: tuple[str, ...] = ()
LEGACY_DIALOG_AUTOPILOT_LAUNCH_AGENT_LABELS: tuple[str, ...] = ()

FOUNDATION_GENERATED_TARGETS = [
    ".codex/plugins/marketplaces/openai-bundled",
    ".codex/.tmp/bundled-marketplaces/openai-bundled",
    ".codex/plugins/cache/openai-bundled/computer-use",
    ".codex/computer-use",
    ".codex/state/computer-use-guard",
    ".codex/logs/computer-use-guard.log.jsonl",
    "Library/Application Support/CodexComputerUseGuard",
]

FOUNDATION_PURGE_STATE_TARGETS = [
    ".codex/state/computer-use-foundation",
]

DIRECT_MCP_HEADERS = [
    "mcp_servers.computer-use",
    "mcp_servers.computer-use-native",
    "mcp_servers.computer_use",
    "mcp_servers.computer_use_native",
]

SECRET_NAME_RE = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|authorization|bearer|oauth|cookie|session)",
    re.IGNORECASE,
)

SECRET_VALUE_RE = re.compile(
    r"(?i)(token|secret|password|passwd|api[_-]?key|authorization|bearer|oauth|cookie|session)"
    r"([\"'\\s:=]+)([^\"'\\s,}\\]]{6,})"
)
ABSOLUTE_HOME_PATH_RE = re.compile(r"/Users/[A-Za-z0-9._-]+")

HEADER_SECRET_RE = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([A-Za-z0-9._/-]{6,})")
ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"token|secret|password|passwd|oauth|cookie|session)\b"
    r"(\s*[:=]\s*)(['\"]?)([^'\"\s,}\]]{6,})(['\"]?)"
)


def repo_path(relative: str) -> Path:
    return REPO_ROOT / relative


def target_path(home: Path, item: dict[str, object]) -> Path:
    return home / str(item["target"])


def assert_within_home(home: Path, path: Path) -> None:
    home_resolved = home.resolve()
    candidate = Path(os.path.abspath(path))
    try:
        candidate.relative_to(home_resolved)
    except ValueError as exc:
        raise ValueError(f"refusing path outside target home: {path}") from exc


def assert_no_symlink_components(home: Path, path: Path, *, allow_leaf: bool = False) -> None:
    home_resolved = home.resolve()
    candidate = Path(os.path.abspath(path))
    relative = candidate.relative_to(home_resolved)
    parts = relative.parts[:-1] if allow_leaf else relative.parts
    current = home_resolved
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"refusing symlink in foundation-owned path: {current}")


def iter_source_files() -> Iterable[Path]:
    for item in INSTALL_MANIFEST:
        yield repo_path(str(item["source"]))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mode_octal(path: Path) -> str:
    return oct(path.stat().st_mode & 0o777)


def redact_text(text: str) -> str:
    text = ABSOLUTE_HOME_PATH_RE.sub("$HOME", text)
    text = HEADER_SECRET_RE.sub(lambda m: f"{m.group(1)}<redacted>", text)
    text = ASSIGNMENT_SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}<redacted>{m.group(5)}", text)
    return SECRET_VALUE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text)


def safe_env_home(value: str | None = None) -> Path:
    return Path(value or os.environ.get("HOME", str(Path.home()))).expanduser().resolve()
