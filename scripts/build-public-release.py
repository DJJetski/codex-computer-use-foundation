#!/usr/bin/env python3
"""Build a sanitized public source release tree from the maintainer repo."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

sys.dont_write_bytecode = True

from foundation_manifest import INSTALL_MANIFEST


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAME = "codex-computer-use-foundation-public"
RELEASE_MANIFEST = "PUBLIC_RELEASE_MANIFEST.json"
RELEASE_GENERATOR = "scripts/build-public-release.py"
MANIFEST_SCHEMA_VERSION = 3
IGNORABLE_EXISTING_RELEASE_FILES = {".DS_Store"}

PUBLIC_EXACT = {
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/dependabot.yml",
    ".github/FUNDING.yml",
    ".github/pull_request_template.md",
    ".github/workflows/ci.yml",
    ".gitattributes",
    ".gitignore",
    ".githooks/pre-push",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "docs/ARCHITECTURE.md",
    "docs/CURRENT-STATE.md",
    "docs/INSTALL.md",
    "docs/RUNBOOK.md",
    "docs/WHAT-IS-COMPUTER-USE.md",
    "scripts/build-public-release.py",
    "scripts/foundation_manifest.py",
    "scripts/install-git-hooks.py",
    "scripts/install.py",
    "scripts/public-release-audit.py",
    "scripts/release-drill.py",
    "scripts/rollback.py",
    "scripts/secret-scan.py",
    "scripts/snapshot-live-state.py",
    "scripts/uninstall.py",
    "scripts/verify-live-state.py",
    "tests/test_foundation.py",
}

PUBLIC_INSTALL_SOURCES = frozenset(str(item["source"]) for item in INSTALL_MANIFEST)

DENY_PREFIXES = (
    ".git/",
    "docs/internal/",
    "rollback/",
    "scratch/",
    "snapshots/",
    "state/",
    "var/",
)

DENY_PARTS = {
    ".codex",
    "__pycache__",
    ".pytest_cache",
}


def run(cmd: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_epoch() -> int:
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch:
        try:
            return int(source_date_epoch)
        except ValueError as exc:
            raise RuntimeError(f"invalid SOURCE_DATE_EPOCH: {source_date_epoch!r}") from exc
    result = run(["git", "show", "-s", "--format=%ct", "HEAD"])
    if result.returncode == 0 and result.stdout.strip().isdigit():
        return int(result.stdout.strip())
    return 0


def release_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(release_epoch()))


def git_output(args: list[str]) -> str:
    result = run(["git", *args])
    return result.stdout.strip() if result.returncode == 0 else ""


def git_commit() -> str:
    return git_output(["rev-parse", "HEAD"])


def git_tag() -> str:
    env_ref = os.environ.get("GITHUB_REF_TYPE"), os.environ.get("GITHUB_REF_NAME")
    if env_ref[0] == "tag" and env_ref[1]:
        return env_ref[1]
    return git_output(["describe", "--exact-match", "--tags", "HEAD"])


def source_repository() -> str:
    # Repository owner names can be personal handles. Keep public release
    # packages privacy-preserving by default; maintainers may opt in during a
    # release workflow after deciding the source URL is intentionally public.
    value = os.environ.get("CODEX_PUBLIC_SOURCE_REPOSITORY", "").strip()
    if not value or "@" in value:
        return ""
    return value


def tracked_files(*, include_untracked: bool = False) -> list[str]:
    cmd = ["git", "ls-files", "--cached"]
    if include_untracked:
        cmd.extend(["--others", "--exclude-standard"])
    result = run(cmd)
    if result.returncode != 0:
        return sorted(
            str(path.relative_to(REPO_ROOT))
            for path in REPO_ROOT.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(REPO_ROOT).parts
        )
    return sorted(line for line in result.stdout.splitlines() if line)


def is_public_path(path: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    return path in PUBLIC_INSTALL_SOURCES


def deny_reason(path: str) -> str | None:
    if any(path.startswith(prefix) for prefix in DENY_PREFIXES):
        return "denylisted release path"
    parts = set(Path(path).parts)
    if parts & DENY_PARTS:
        return "denylisted path component"
    if path.endswith((".env", ".secret", ".secrets")):
        return "secret-like file suffix"
    return None


def release_files(*, include_untracked: bool = False) -> list[str]:
    files: list[str] = []
    for path in tracked_files(include_untracked=include_untracked):
        reason = deny_reason(path)
        if reason and is_public_path(path):
            raise RuntimeError(f"public allowlist includes {reason}: {path}")
        if reason:
            continue
        if is_public_path(path):
            files.append(path)
    missing = sorted(path for path in PUBLIC_EXACT if not (REPO_ROOT / path).is_file())
    if missing:
        raise RuntimeError("missing public release files: " + ", ".join(missing))
    return files


def path_has_symlink_component(root: Path, path: Path) -> bool:
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def validate_release_name(name: str) -> None:
    path = Path(name)
    if path.name != name or name in {"", ".", ".."} or ".." in path.parts:
        raise RuntimeError(f"release name must be a single safe directory name: {name!r}")


def copy_release(files: list[str], release_root: Path, *, dry_run: bool, allow_legacy_owned: bool) -> None:
    if dry_run:
        return
    if release_root.exists():
        if not existing_release_dir_is_owned(release_root, allow_legacy=allow_legacy_owned):
            raise RuntimeError(f"refusing to replace non-release directory: {release_root}")
        shutil.rmtree(release_root)
    release_root.mkdir(parents=True)
    for rel in files:
        source = REPO_ROOT / rel
        if source.is_symlink() or path_has_symlink_component(REPO_ROOT, source):
            raise RuntimeError(f"refusing symlinked public source path: {rel}")
        target = release_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    file_hashes = {rel: sha256_file(release_root / rel) for rel in files}
    manifest = {
        "created_at": release_timestamp(),
        "file_sha256": file_hashes,
        "generated_by": RELEASE_GENERATOR,
        "git_commit": git_commit(),
        "git_tag": git_tag(),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "name": release_root.name,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source_repository": source_repository(),
        "files": files,
    }
    (release_root / RELEASE_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def existing_release_dir_is_owned(release_root: Path, *, allow_legacy: bool = False) -> bool:
    manifest_path = release_root / RELEASE_MANIFEST
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(manifest, dict):
        return False
    if manifest.get("name") != release_root.name:
        return False
    manifest_files = sorted(str(item) for item in manifest.get("files", []))
    actual_files = sorted(
        str(path.relative_to(release_root))
        for path in release_root.rglob("*")
        if path.is_file()
        and path.relative_to(release_root) != Path(RELEASE_MANIFEST)
        and path.name not in IGNORABLE_EXISTING_RELEASE_FILES
    )
    if actual_files != manifest_files:
        return False
    if manifest.get("generated_by") != RELEASE_GENERATOR:
        return False
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        return allow_legacy
    manifest_hashes = manifest.get("file_sha256")
    if not isinstance(manifest_hashes, dict):
        return False
    if sorted(str(item) for item in manifest_hashes) != manifest_files:
        return False
    for rel, expected in manifest_hashes.items():
        if sha256_file(release_root / str(rel)) != str(expected):
            return False
    return True


def member_is_safe(member_name: str, release_name: str) -> bool:
    path = Path(member_name)
    if path.is_absolute() or ".." in path.parts:
        return False
    return member_name == release_name or member_name.startswith(f"{release_name}/")


def existing_release_tarball_is_owned(tarball: Path, release_name: str, *, allow_legacy: bool = False) -> bool:
    try:
        with tarfile.open(tarball, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                if not member_is_safe(member.name, release_name):
                    return False
                if member.issym() or member.islnk():
                    return False
                if not (member.isfile() or member.isdir()):
                    return False
            actual_files = sorted(
                member.name.removeprefix(f"{release_name}/")
                for member in members
                if member.isfile() and member.name != f"{release_name}/{RELEASE_MANIFEST}"
            )
            manifest_file = archive.extractfile(f"{release_name}/{RELEASE_MANIFEST}")
            if manifest_file is None:
                return False
            manifest = json.loads(manifest_file.read().decode("utf-8"))
            if not isinstance(manifest, dict):
                return False
            if manifest.get("name") != release_name:
                return False
            manifest_files = sorted(str(item) for item in manifest.get("files", []))
            if actual_files != manifest_files:
                return False
            if manifest.get("generated_by") != RELEASE_GENERATOR:
                return False
            if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
                return allow_legacy
            manifest_hashes = manifest.get("file_sha256")
            if not isinstance(manifest_hashes, dict):
                return False
            if sorted(str(item) for item in manifest_hashes) != manifest_files:
                return False
            for rel, expected in manifest_hashes.items():
                member_file = archive.extractfile(f"{release_name}/{rel}")
                if member_file is None:
                    return False
                digest = hashlib.sha256(member_file.read()).hexdigest()
                if digest != str(expected):
                    return False
    except Exception:
        return False
    return True


def checksum_path_for(tarball: Path) -> Path:
    return tarball.with_name(f"{tarball.name}.sha256")


def write_tarball_checksum(tarball: Path) -> tuple[str, Path]:
    digest = sha256_file(tarball)
    checksum_path = checksum_path_for(tarball)
    checksum_path.write_text(f"{digest}  {tarball.name}\n", encoding="utf-8")
    return digest, checksum_path


def _normalized_tar_info(path: Path, arcname: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(arcname)
    stat = path.stat()
    info.mode = stat.st_mode & 0o777
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "wheel"
    info.mtime = 0
    if path.is_dir():
        info.type = tarfile.DIRTYPE
    else:
        info.size = stat.st_size
    return info


def add_normalized_tree(archive: tarfile.TarFile, release_root: Path) -> None:
    archive.addfile(_normalized_tar_info(release_root, release_root.name))
    for path in sorted(release_root.rglob("*"), key=lambda item: str(item.relative_to(release_root))):
        arcname = f"{release_root.name}/{path.relative_to(release_root)}"
        info = _normalized_tar_info(path, arcname)
        if path.is_dir():
            archive.addfile(info)
            continue
        with path.open("rb") as fh:
            archive.addfile(info, fh)


def make_tarball(release_root: Path, tarball: Path, *, dry_run: bool, allow_legacy_owned: bool) -> tuple[str | None, Path]:
    checksum_path = checksum_path_for(tarball)
    if dry_run:
        return None, checksum_path
    tarball.parent.mkdir(parents=True, exist_ok=True)
    if tarball.exists():
        if not existing_release_tarball_is_owned(tarball, release_root.name, allow_legacy=allow_legacy_owned):
            raise RuntimeError(f"refusing to replace non-release tarball: {tarball}")
        tarball.unlink()
    with tarball.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gzip_file:
            with tarfile.open(fileobj=gzip_file, mode="w") as archive:
                add_normalized_tree(archive, release_root)
    return write_tarball_checksum(tarball)


def audit_release(release_root: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    denied = [str(path.relative_to(release_root)) for path in release_root.rglob("*") if deny_reason(str(path.relative_to(release_root)))]
    if denied:
        raise RuntimeError("release contains denied paths: " + ", ".join(sorted(denied)))
    result = run([sys.executable, "scripts/secret-scan.py", "--include-untracked"], cwd=release_root)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "release secret scan failed")
    public_audit = run(
        [sys.executable, "scripts/public-release-audit.py", "--include-untracked", "--enforce-public-surface"],
        cwd=release_root,
    )
    if public_audit.returncode != 0:
        raise RuntimeError(public_audit.stderr.strip() or public_audit.stdout.strip() or "release public audit failed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a sanitized public release tree and tarball")
    parser.add_argument("--output-dir", default="var/public-release", help="directory that receives the release tree")
    parser.add_argument("--name", default=DEFAULT_NAME, help="release tree directory name")
    parser.add_argument("--tarball", default=None, help="tar.gz path; defaults beside output tree")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="include untracked allowlisted files; default release builds use tracked files only",
    )
    args = parser.parse_args()

    try:
        files = release_files(include_untracked=args.include_untracked)
        validate_release_name(args.name)
        output_dir = Path(args.output_dir).expanduser()
        if not output_dir.is_absolute():
            output_dir = REPO_ROOT / output_dir
        default_output_dir = (REPO_ROOT / "var/public-release").resolve()
        allow_legacy_owned = output_dir.resolve() == default_output_dir
        release_root = (output_dir / args.name).resolve()
        try:
            release_root.relative_to(output_dir.resolve())
        except ValueError as exc:
            raise RuntimeError(f"release root escaped output directory: {release_root}") from exc
        tarball_arg = Path(args.tarball).expanduser() if args.tarball else release_root.with_suffix(".tar.gz")
        tarball = tarball_arg if tarball_arg.is_absolute() else output_dir / tarball_arg
        tarball = tarball.resolve()
        if args.tarball:
            try:
                tarball.relative_to(output_dir.resolve())
            except ValueError as exc:
                raise RuntimeError(f"tarball must be inside output directory: {tarball}") from exc
        copy_release(files, release_root, dry_run=args.dry_run, allow_legacy_owned=allow_legacy_owned)
        audit_release(release_root, dry_run=args.dry_run)
        tarball_sha256, checksum_path = make_tarball(
            release_root,
            tarball,
            dry_run=args.dry_run,
            allow_legacy_owned=allow_legacy_owned,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "dry_run": args.dry_run,
                "release_root": str(release_root),
                "tarball": str(tarball),
                "tarball_sha256": tarball_sha256,
                "checksum_file": str(checksum_path),
                "file_count": len(files),
                "files": files,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
