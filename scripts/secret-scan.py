#!/usr/bin/env python3
"""Small high-signal repository secret/state scanner."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DENY_PATH_RE = re.compile(
    r"(^|/)(\.env(\.|$)|\.codex($|/)|state($|/)|snapshots?($|/)|rollback($|/)|"
    r"last-native-smoke.*\.json$|last-status\.json$|.*\.(p12|pfx|keychain|mobileprovision)$)",
    re.IGNORECASE,
)

SECRET_VALUE_PATTERNS = [
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{24,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{24,}\b"),
    re.compile(r"\bya29\.[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9._/-]{20,}"),
]


def git_files(include_untracked: bool) -> list[Path]:
    git_root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if git_root.returncode != 0 or Path(git_root.stdout.strip()).resolve() != REPO_ROOT:
        return [
            path
            for path in sorted(REPO_ROOT.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(REPO_ROOT).parts
        ]
    tracked_result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if tracked_result.returncode != 0:
        return [
            path
            for path in sorted(REPO_ROOT.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(REPO_ROOT).parts
        ]
    tracked = tracked_result.stdout.splitlines()
    files = set(tracked)
    if include_untracked:
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
        files.update(untracked)
    return [REPO_ROOT / item for item in sorted(files)]


def scan_file(path: Path) -> list[str]:
    rel = str(path.relative_to(REPO_ROOT))
    findings: list[str] = []
    if DENY_PATH_RE.search(rel):
        findings.append(f"denylisted path: {rel}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        findings.append(f"cannot read {rel}: {exc}")
        return findings
    if b"\0" in data[:4096]:
        return findings
    text = data.decode("utf-8", errors="replace")
    for index, line in enumerate(text.splitlines(), start=1):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(line):
                findings.append(f"possible secret: {rel}:{index}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan tracked repo files for accidental secrets/state")
    parser.add_argument("--include-untracked", action="store_true")
    args = parser.parse_args()

    findings: list[str] = []
    for path in git_files(include_untracked=args.include_untracked):
        if path.is_file():
            findings.extend(scan_file(path))
    if findings:
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1
    print("secret-scan ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
