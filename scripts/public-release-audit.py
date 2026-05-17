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
HISTORY_EMAIL_GREP_RE = r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
PRIVATE_KEY_HEADER = "-----BEGIN "
HISTORY_SECRET_GREP_RES = [
    PRIVATE_KEY_HEADER + "PRIVATE KEY-----",
    PRIVATE_KEY_HEADER + "RSA PRIVATE KEY-----",
    PRIVATE_KEY_HEADER + "EC PRIVATE KEY-----",
    PRIVATE_KEY_HEADER + "OPENSSH PRIVATE KEY-----",
    r"sk-[A-Za-z0-9_-]{24,}",
    r"gh[pousr]_[A-Za-z0-9_]{24,}",
    r"xox[baprs]-[A-Za-z0-9-]{24,}",
    r"ya29\.[A-Za-z0-9_-]{24,}",
    r"authorization[[:space:]]*[:=][[:space:]]*bearer[[:space:]]+[A-Za-z0-9._-]{20,}",
    r"(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)[[:space:]]*[:=][[:space:]]*['\"]?[A-Za-z0-9._/-]{20,}",
]
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
LOCAL_ARTIFACT_NAMES = {
    ".DS_Store",
}
LOCAL_ARTIFACT_PARTS = {
    "__pycache__",
    ".pytest_cache",
}
LOCAL_ARTIFACT_SKIP_PREFIXES = (
    ".git/",
    "var/",
)
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
PUBLIC_ACCOUNT_MARKERS = {
    "DJJetski",
    "DJ Jetski",
}
EXPECTED_NATIVE_MCP_TOOLS = (
    "list_apps",
    "get_app_state",
    "click",
    "perform_secondary_action",
    "set_value",
    "select_text",
    "scroll",
    "drag",
    "press_key",
    "type_text",
)
EXPECTED_TOOL_SEARCH_QUERY = (
    "computer-use list_apps get_app_state click perform_secondary_action "
    "set_value select_text scroll drag press_key type_text"
)


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


def repo_has_own_git_metadata() -> bool:
    result = run(["git", "rev-parse", "--show-toplevel"], check=False)
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == REPO_ROOT


def git_files(include_untracked: bool) -> list[Path]:
    if not repo_has_own_git_metadata():
        return [
            path
            for path in sorted(REPO_ROOT.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(REPO_ROOT).parts
        ]
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
    allowed_public_markers = set(PUBLIC_ACCOUNT_MARKERS)
    for value in (os.environ.get("PUBLIC_RELEASE_AUDIT_ALLOWED_MARKERS") or "").split(","):
        if value.strip():
            allowed_public_markers.add(value.strip())

    def add_auto_marker(value: str | None) -> None:
        if not value:
            return
        marker = value.strip()
        if (
            marker
            and marker.lower() not in GENERIC_ACCOUNT_MARKERS
            and marker.lower() not in {item.lower() for item in allowed_public_markers}
        ):
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


def scan_local_workspace_artifacts() -> list[str]:
    findings: list[str] = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.exists():
            continue
        rel = str(path.relative_to(REPO_ROOT))
        if any(rel == prefix[:-1] or rel.startswith(prefix) for prefix in LOCAL_ARTIFACT_SKIP_PREFIXES):
            continue
        parts = set(Path(rel).parts)
        if path.name in LOCAL_ARTIFACT_NAMES or parts & LOCAL_ARTIFACT_PARTS:
            findings.append(f"local generated artifact in public workspace: {rel}")
    return findings


def scan_native_contract_consistency() -> list[str]:
    findings: list[str] = []
    guard = REPO_ROOT / "src/bin/codex-computer-use-guard"
    verifier = REPO_ROOT / "scripts/verify-live-state.py"
    docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs/WHAT-IS-COMPUTER-USE.md",
        REPO_ROOT / "docs/CAPABILITY-PARITY.md",
        REPO_ROOT / "docs/ARCHITECTURE.md",
        REPO_ROOT / "src/skills/macos-computer-use/SKILL.md",
    ]
    for path in [guard, verifier, *docs]:
        text = path.read_text(encoding="utf-8")
        missing = [tool for tool in EXPECTED_NATIVE_MCP_TOOLS if tool not in text]
        if missing:
            findings.append(f"native tool contract missing from {path.relative_to(REPO_ROOT)}: {', '.join(missing)}")
    for path in [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs/WHAT-IS-COMPUTER-USE.md",
        REPO_ROOT / "docs/RUNBOOK.md",
        REPO_ROOT / "docs/CURRENT-STATE.md",
        REPO_ROOT / "src/skills/macos-computer-use/SKILL.md",
    ]:
        text = path.read_text(encoding="utf-8")
        if EXPECTED_TOOL_SEARCH_QUERY not in text:
            findings.append(f"fresh-thread tool_search query is not the full native surface: {path.relative_to(REPO_ROOT)}")
    guard_text = guard.read_text(encoding="utf-8")
    verifier_text = verifier.read_text(encoding="utf-8")
    if "mcp_tool_surface" not in guard_text:
        findings.append("guard status does not record native MCP tool-surface status")
    if "mcp_tool_surface" not in verifier_text:
        findings.append("live verifier does not require native MCP tool-surface status")
    for path in [REPO_ROOT / "README.md", REPO_ROOT / "docs/WHAT-IS-COMPUTER-USE.md"]:
        text = path.read_text(encoding="utf-8")
        if "fallback_used=false" not in text:
            findings.append(f"public docs do not state fallback_used=false boundary: {path.relative_to(REPO_ROOT)}")
    parity = REPO_ROOT / "docs/CAPABILITY-PARITY.md"
    parity_text = parity.read_text(encoding="utf-8")
    for required in [
        "https://developers.openai.com/codex/app/computer-use",
        "https://openai.com/index/codex-for-almost-everything/",
        "https://developers.openai.com/api/docs/guides/tools-computer-use",
        "move",
        "wait",
        "screenshot",
        "Little Snitch",
        "Always Allow",
        "Foundation/Codex",
        "Generic firewall",
        "Terminal",
        "Codex itself",
        "fallback_used=false",
    ]:
        if required not in parity_text:
            findings.append(f"capability parity doc missing required term: {required}")
    return findings


def scan_release_provenance_contract() -> list[str]:
    findings: list[str] = []
    builder = REPO_ROOT / "scripts/build-public-release.py"
    drill = REPO_ROOT / "scripts/release-drill.py"
    builder_text = builder.read_text(encoding="utf-8")
    drill_text = drill.read_text(encoding="utf-8")
    required_builder_terms = [
        "enforce_clean_release_files",
        "git_dirty_public_files",
        "git_worktree_public_files_clean",
        "--allow-dirty",
    ]
    for term in required_builder_terms:
        if term not in builder_text:
            findings.append(f"release builder provenance contract missing {term}")
    if "--allow-dirty" not in drill_text:
        findings.append("release drill cannot explicitly mark dirty local drill builds")
    return findings


def scan_commit_identities(refspec: str) -> list[str]:
    if not repo_has_own_git_metadata():
        return []
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
    if not repo_has_own_git_metadata():
        return []
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
            findings.append(f"personal marker in git history: {history_match_location(first)}")
        elif result.returncode not in {1, 128}:
            findings.append(f"git grep failed for personal marker scan: {result.stderr.strip()}")
    return findings


def history_match_location(line: str) -> str:
    parts = line.split(":", 3)
    if len(parts) != 4:
        return "<redacted-location>"
    ref, path, line_no, _content = parts
    if not line_no.isdigit():
        return f"{ref[:12]}:<redacted-location>"
    return f"{ref[:12]}:{path}:{line_no}"


def git_grep_regex(pattern: str, refs: list[str], *, ignore_case: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "grep", "-I", "-n", "-E"]
    if ignore_case:
        cmd.append("-i")
    cmd.extend(["-e", pattern, *refs, "--", "."])
    return run(cmd, check=False)


def scan_history_emails(refs: list[str]) -> list[str]:
    if not refs:
        return []
    result = git_grep_regex(HISTORY_EMAIL_GREP_RE, refs, ignore_case=True)
    if result.returncode == 1:
        return []
    if result.returncode not in {0, 1}:
        return [f"git grep failed for historic email scan: {result.stderr.strip()}"]
    findings: list[str] = []
    for line in result.stdout.splitlines():
        for email in EMAIL_RE.findall(line):
            if email.lower() not in {item.lower() for item in ALLOWED_EMAILS}:
                findings.append(f"non-public email in git history: {history_match_location(line)}")
                break
    return findings


def scan_history_secrets(refs: list[str]) -> list[str]:
    if not refs:
        return []
    findings: list[str] = []
    for pattern in HISTORY_SECRET_GREP_RES:
        result = git_grep_regex(pattern, refs, ignore_case=True)
        if result.returncode == 1:
            continue
        if result.returncode != 0:
            findings.append(f"git grep failed for historic secret pattern: {result.stderr.strip()}")
            continue
        first = result.stdout.splitlines()[0] if result.stdout else ""
        findings.append(f"possible secret in git history: {history_match_location(first)}")
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
    findings.extend(scan_native_contract_consistency())
    findings.extend(scan_release_provenance_contract())
    findings.extend(scan_local_workspace_artifacts())
    if not args.skip_commit_identities:
        findings.extend(scan_commit_identities(refspec))
    refs = history_content_refs(args.all_refs)
    findings.extend(scan_history_content(refs, markers))
    if args.all_refs:
        findings.extend(scan_history_emails(refs))
        findings.extend(scan_history_secrets(refs))

    if findings:
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1
    print("public-release-audit ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
