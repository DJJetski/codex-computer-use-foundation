#!/usr/bin/env python3
"""Create a redacted, read-only inventory of the live Computer Use install."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

from foundation_manifest import INSTALL_MANIFEST, mode_octal, redact_text, safe_env_home, sha256_file, target_path


def run(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=timeout,
    )


def file_inventory(home: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in INSTALL_MANIFEST:
        target = target_path(home, item)
        row: dict[str, object] = {"target": str(item["target"]), "exists": target.exists()}
        if target.exists():
            row.update(
                {
                    "mode": mode_octal(target),
                    "sha256": sha256_file(target),
                    "size": target.stat().st_size,
                    "is_symlink": target.is_symlink(),
                }
            )
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a redacted live Computer Use inventory")
    parser.add_argument("--home", default=None, help="target home directory; defaults to $HOME")
    parser.add_argument("--output", default=None, help="optional output JSON path; stdout if omitted")
    parser.add_argument("--include-status", action="store_true", help="include redacted guard status output")
    parser.add_argument(
        "--include-private-paths",
        action="store_true",
        help="include absolute local paths; default output replaces the target home with $HOME",
    )
    args = parser.parse_args()

    home = safe_env_home(args.home)
    payload: dict[str, object] = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "home": str(home) if args.include_private_paths else "$HOME",
        "macos": platform.mac_ver()[0],
        "platform": platform.platform(),
        "files": file_inventory(home),
    }
    codex_app = Path("/Applications/Codex.app")
    payload["codex_app_exists"] = codex_app.is_dir()
    config = home / ".codex/config.toml"
    if config.is_file():
        payload["config_redacted"] = redact_text(config.read_text(encoding="utf-8", errors="replace"))
    if args.include_status:
        guard = home / ".codex/bin/codex-computer-use-guard"
        if guard.is_file() and home == Path.home().resolve():
            result = run([str(guard), "status"], timeout=30)
            payload["guard_status_returncode"] = result.returncode
            payload["guard_status_redacted"] = redact_text(result.stdout)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        out = Path(args.output).expanduser().resolve()
        cwd = Path.cwd().resolve()
        allowed_repo_var = cwd / "var"
        if out.is_relative_to(cwd) and not out.is_relative_to(allowed_repo_var):
            raise SystemExit("refusing to write live inventory inside tracked repo paths; use var/ (ignored) or another path")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
