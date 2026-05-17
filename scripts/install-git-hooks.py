#!/usr/bin/env python3
"""Enable repo-local Git hooks."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=REPO_ROOT, check=True)
    print("configured core.hooksPath=.githooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
