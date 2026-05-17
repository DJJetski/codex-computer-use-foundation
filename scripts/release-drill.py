#!/usr/bin/env python3
"""Exercise the public release tarball as if it had just been downloaded."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAME = "codex-computer-use-foundation-public"


def output_tail(text: str, limit: int = 4000) -> str:
    return text if len(text) <= limit else text[-limit:]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checksum_from_file(path: Path) -> str:
    first = path.read_text(encoding="utf-8").split()
    if not first:
        raise RuntimeError(f"empty checksum file: {path}")
    digest = first[0].strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise RuntimeError(f"invalid sha256 in checksum file: {path}")
    return digest


def verify_sha256(path: Path, expected: str) -> str:
    digest = sha256_file(path)
    if digest.lower() != expected.lower():
        raise RuntimeError(f"sha256 mismatch for {path}: expected {expected.lower()} got {digest}")
    return digest


def download_release_asset(url: str, target: Path) -> Path:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise RuntimeError("release URL must use https")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - HTTPS-only release asset download.
        target.write_bytes(response.read())
    return target


def run_checked(
    commands: list[dict[str, object]],
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> str:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
        env=env,
    )
    commands.append(
        {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": completed.returncode,
            "output_tail": output_tail(completed.stdout),
        }
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}")
    return completed.stdout


def safe_extract_tarball(tarball: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError(f"unsafe tar member path: {member.name}")
            if member.issym() or member.islnk():
                raise RuntimeError(f"refusing link member in release tarball: {member.name}")
            if not (member.isfile() or member.isdir()):
                raise RuntimeError(f"refusing special member in release tarball: {member.name}")
            target = (destination / member.name).resolve()
            target.relative_to(destination_resolved)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                os.chmod(target, 0o700)
                continue
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"cannot read tar member: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            mode = 0o700 if member.mode & 0o111 else 0o600
            os.chmod(target, mode)


def build_public_release(output_dir: Path, name: str, commands: list[dict[str, object]]) -> tuple[Path, Path, str]:
    output = run_checked(
        commands,
        [
            sys.executable,
            str(REPO_ROOT / "scripts/build-public-release.py"),
            "--output-dir",
            str(output_dir),
            "--name",
            name,
        ],
        cwd=REPO_ROOT,
        timeout=120,
    )
    payload = json.loads(output)
    digest = str(payload.get("tarball_sha256") or "")
    if not digest:
        raise RuntimeError("release builder did not report tarball_sha256")
    return Path(str(payload["release_root"])).resolve(), Path(str(payload["tarball"])).resolve(), digest


def non_live_drill(package: Path, temp_home: Path, commands: list[dict[str, object]]) -> None:
    (temp_home / ".codex").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    run_checked(
        commands,
        [
            sys.executable,
            str(package / "scripts/install.py"),
            "--home",
            str(temp_home),
            "--dry-run",
            "--skip-runtime-checks",
            "--skip-postinstall",
        ],
        cwd=package,
        timeout=60,
        env=env,
    )
    run_checked(
        commands,
        [
            sys.executable,
            str(package / "scripts/install.py"),
            "--home",
            str(temp_home),
            "--yes",
            "--skip-runtime-checks",
            "--skip-postinstall",
        ],
        cwd=package,
        timeout=60,
        env=env,
    )
    run_checked(
        commands,
        [
            sys.executable,
            str(package / "scripts/verify-live-state.py"),
            "--home",
            str(temp_home),
            "--expect-installed-from-repo",
            "--skip-live-invariants",
            "--skip-launchctl",
            "--json",
        ],
        cwd=package,
        timeout=60,
        env=env,
    )


def live_drill(package: Path, home: Path, codex_app: Path, commands: list[dict[str, object]]) -> None:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    run_checked(
        commands,
        [
            sys.executable,
            str(package / "scripts/uninstall.py"),
            "--home",
            str(home),
            "--yes",
            "--purge-state",
        ],
        cwd=package,
        timeout=60,
        env=env,
    )
    run_checked(
        commands,
        [
            sys.executable,
            str(package / "scripts/install.py"),
            "--home",
            str(home),
            "--codex-app",
            str(codex_app),
            "--yes",
            "--full-ensure",
        ],
        cwd=package,
        timeout=240,
        env=env,
    )
    run_checked(
        commands,
        [
            sys.executable,
            str(package / "scripts/verify-live-state.py"),
            "--home",
            str(home),
            "--expect-installed-from-repo",
            "--require-operational",
            "--json",
        ],
        cwd=package,
        timeout=90,
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build, extract, install, and verify the generated public release")
    parser.add_argument("--output-dir", default="var/public-release", help="directory that receives the release tree")
    parser.add_argument("--name", default=DEFAULT_NAME, help="release tree directory name")
    parser.add_argument("--home", default=None, help="target home for --live; defaults to $HOME")
    parser.add_argument("--codex-app", default="/Applications/Codex.app", help="OpenAI Codex.app path for --live")
    parser.add_argument("--tarball", default=None, help="existing public release tarball to extract instead of building")
    parser.add_argument("--url", default=None, help="HTTPS public release tarball URL to download instead of building")
    parser.add_argument("--expected-sha256", default=None, help="expected SHA256 for --tarball or --url")
    parser.add_argument("--checksum-file", default=None, help="sha256 sidecar file for --tarball")
    parser.add_argument("--allow-unverified-archive", action="store_true", help="allow a local --tarball without SHA256 verification; never allowed for --url")
    parser.add_argument("--live", action="store_true", help="destructively uninstall/reinstall the real target home")
    parser.add_argument("--yes", action="store_true", help="required with --live")
    parser.add_argument("--keep-temp", action="store_true", help="keep extracted download directory for debugging")
    args = parser.parse_args()

    if args.live and not args.yes:
        print("ERROR: live release drill requires --yes", file=sys.stderr)
        return 1
    if args.tarball and args.url:
        print("ERROR: use only one of --tarball or --url", file=sys.stderr)
        return 1
    if args.url and args.allow_unverified_archive:
        print("ERROR: --url requires SHA256 verification; do not use --allow-unverified-archive for network downloads", file=sys.stderr)
        return 1
    if (args.tarball or args.url) and not (args.expected_sha256 or args.checksum_file or args.allow_unverified_archive):
        print("ERROR: --tarball/--url requires --expected-sha256, --checksum-file, or --allow-unverified-archive", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = (REPO_ROOT / output_dir).resolve()
    home = Path(args.home or os.environ.get("HOME", str(Path.home()))).expanduser().resolve()
    codex_app = Path(args.codex_app).expanduser().resolve()
    commands: list[dict[str, object]] = []
    temp_root = Path(tempfile.mkdtemp(prefix="codex-computer-use-release-drill-")).resolve()
    ok = False
    try:
        if args.url:
            release_root = None
            tarball = download_release_asset(args.url, temp_root / "downloaded-release.tar.gz")
            expected_sha256 = args.expected_sha256
        elif args.tarball:
            release_root = None
            tarball = Path(args.tarball).expanduser().resolve()
            expected_sha256 = args.expected_sha256
        else:
            release_root, tarball, expected_sha256 = build_public_release(output_dir, args.name, commands)
        if args.checksum_file:
            expected_sha256 = checksum_from_file(Path(args.checksum_file).expanduser().resolve())
        verified_sha256 = None
        if expected_sha256:
            verified_sha256 = verify_sha256(tarball, expected_sha256)
        download_dir = temp_root / "download"
        download_dir.mkdir()
        safe_extract_tarball(tarball, download_dir)
        package_name = release_root.name if release_root is not None else args.name
        package = download_dir / package_name
        if not (package / "scripts/install.py").is_file():
            raise RuntimeError(f"extracted package is missing scripts/install.py: {package}")
        if args.live:
            live_drill(package, home, codex_app, commands)
            mode = "live"
        else:
            non_live_drill(package, temp_root / "home", commands)
            mode = "temp-home"
        ok = True
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": mode,
                    "release_root": str(release_root) if release_root is not None else None,
                    "tarball": str(tarball),
                    "tarball_sha256": verified_sha256 or sha256_file(tarball),
                    "sha256_verified": verified_sha256 is not None,
                    "package": str(package),
                    "temp_root": str(temp_root),
                    "kept_temp": args.keep_temp,
                    "commands": commands,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "temp_root": str(temp_root),
                    "kept_temp": True,
                    "commands": commands,
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    finally:
        if ok and not args.keep_temp:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
