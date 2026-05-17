#!/usr/bin/env python3
"""Check that the repo is safe to publish from the current branch."""

from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_RELEASE_MANIFEST = "PUBLIC_RELEASE_MANIFEST.json"
PUBLIC_AUTHOR_NAME = "Codex Computer Use Foundation"
PUBLIC_AUTHOR_EMAIL = "codex-computer-use-foundation@example.invalid"
ALLOWED_EMAILS = {PUBLIC_AUTHOR_EMAIL}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SURFACE_DENY_PREFIXES = (
    ".git/",
    "docs/internal/",
    "rollback/",
    "scratch/",
    "snapshots/",
    "state/",
    "var/",
)
SURFACE_DENY_PARTS = {
    ".codex",
    "__pycache__",
    ".pytest_cache",
}
GENERIC_ACCOUNT_MARKERS = {
    "actions",
    "admin",
    "build",
    "builder",
    "ci",
    "github",
    "macos",
    "root",
    "runner",
    "user",
    "users",
}


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def git_lines(cmd: list[str]) -> list[str]:
    result = run(cmd, check=False)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result.stdout.splitlines()


def git_files(include_untracked: bool) -> list[Path]:
    listed = run(["git", "ls-files"], check=False)
    if listed.returncode != 0:
        return [
            path
            for path in sorted(REPO_ROOT.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(REPO_ROOT).parts
        ]
    files = set(listed.stdout.splitlines())
    if include_untracked:
        files.update(git_lines(["git", "ls-files", "--others", "--exclude-standard"]))
    return [REPO_ROOT / item for item in sorted(files)]


def personal_markers() -> list[str]:
    home = Path.home().resolve()
    markers = {str(home)}

    def add_auto_marker(value: str | None) -> None:
        if not value:
            return
        marker = value.strip()
        if marker and marker.lower() not in GENERIC_ACCOUNT_MARKERS:
            markers.add(marker)

    add_auto_marker(home.name)
    for value in (os.environ.get("USER"), os.environ.get("LOGNAME"), getpass.getuser()):
        add_auto_marker(value)
    for key in ("PUBLIC_RELEASE_AUDIT_EXTRA_MARKERS", "PUBLIC_AUDIT_EXTRA_MARKERS"):
        for value in (os.environ.get(key) or "").split(","):
            if value.strip():
                markers.add(value.strip())
    for git_key in ("user.name", "user.email"):
        result = run(["git", "config", "--get", git_key], check=False)
        if result.returncode == 0 and result.stdout.strip():
            value = result.stdout.strip()
            if value not in {PUBLIC_AUTHOR_NAME, PUBLIC_AUTHOR_EMAIL}:
                add_auto_marker(value)
    return sorted(marker for marker in markers if marker and len(marker) >= 4)


def scan_file(path: Path, markers: list[str]) -> list[str]:
    rel = str(path.relative_to(REPO_ROOT))
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [f"cannot read {rel}: {exc}"]
    if b"\0" in data[:4096]:
        return []
    text = data.decode("utf-8", errors="replace")
    lower = text.lower()
    findings: list[str] = []
    for marker in markers:
        if marker.lower() in lower:
            findings.append(f"personal marker in file: {rel}: {marker}")
    for index, line in enumerate(text.splitlines(), start=1):
        for email in EMAIL_RE.findall(line):
            if email.lower() not in {item.lower() for item in ALLOWED_EMAILS}:
                findings.append(f"non-public email in file: {rel}:{index}: {email}")
    return findings


def surface_deny_reason(path: str) -> str | None:
    if any(path.startswith(prefix) for prefix in SURFACE_DENY_PREFIXES):
        return "denylisted public surface path"
    parts = set(Path(path).parts)
    if parts & SURFACE_DENY_PARTS:
        return "denylisted public surface component"
    if path.endswith((".env", ".secret", ".secrets")):
        return "secret-like file suffix"
    return None


def scan_public_surface(files: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        rel = str(path.relative_to(REPO_ROOT))
        reason = surface_deny_reason(rel)
        if reason:
            findings.append(f"{reason}: {rel}")
    return findings


def scan_commit_identities(refspec: str) -> list[str]:
    result = run(
        [
            "git",
            "log",
            refspec,
            "--format=%H%x00%an%x00%ae%x00%cn%x00%ce",
        ],
        check=False,
    )
    if result.returncode != 0:
        if "not a git repository" in result.stderr.lower():
            return []
        return [f"git log failed for {refspec}: {result.stderr.strip() or result.stdout.strip()}"]
    findings: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split("\0")
        if len(parts) != 5:
            continue
        commit, author_name, author_email, committer_name, committer_email = parts
        if author_name != PUBLIC_AUTHOR_NAME or committer_name != PUBLIC_AUTHOR_NAME:
            findings.append(f"non-public commit name: {commit[:12]}")
        if author_email != PUBLIC_AUTHOR_EMAIL or committer_email != PUBLIC_AUTHOR_EMAIL:
            findings.append(f"non-public commit email: {commit[:12]}")
    return findings


def history_content_refs(all_refs: bool) -> list[str]:
    if not all_refs:
        return ["HEAD"]
    result = run(["git", "rev-list", "--all"], check=False)
    if result.returncode != 0:
        return []
    refs = result.stdout.splitlines()
    return refs or ["HEAD"]


def scan_history_content(refs: list[str], markers: list[str]) -> list[str]:
    findings: list[str] = []
    if not refs:
        return findings
    for marker in markers:
        result = run(["git", "grep", "-I", "-n", "-i", "-F", marker, *refs, "--", "."], check=False)
        if result.returncode == 0:
            first = result.stdout.splitlines()[0] if result.stdout else marker
            findings.append(f"personal marker in git history: {first}")
        elif result.returncode not in {1, 128}:
            findings.append(f"git grep failed for marker {marker!r}: {result.stderr.strip()}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit current branch for public-release personal traces")
    parser.add_argument("--include-untracked", action="store_true")
    parser.add_argument("--all-refs", action="store_true", help="scan all local refs instead of HEAD history")
    parser.add_argument(
        "--skip-commit-identities",
        action="store_true",
        help="skip commit author/committer checks, for example on synthetic pull-request merge commits",
    )
    parser.add_argument(
        "--enforce-public-surface",
        action="store_true",
        help="also fail if generated public-release denylisted paths are present",
    )
    args = parser.parse_args()

    refspec = "--all" if args.all_refs else "HEAD"
    markers = personal_markers()
    files = git_files(include_untracked=args.include_untracked)
    findings: list[str] = []
    for path in files:
        if path.is_file():
            findings.extend(scan_file(path, markers))
    if args.enforce_public_surface or (REPO_ROOT / PUBLIC_RELEASE_MANIFEST).is_file():
        findings.extend(scan_public_surface(files))
    if not args.skip_commit_identities:
        findings.extend(scan_commit_identities(refspec))
    findings.extend(scan_history_content(history_content_refs(args.all_refs), markers))

    if findings:
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1
    print("public-release-audit ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
