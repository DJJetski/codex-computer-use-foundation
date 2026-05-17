# Contributing

This project repairs and verifies native Codex Computer Use on macOS. Changes
should preserve the native plugin path, avoid hidden GUI fallbacks, and keep
machine-local state out of the repository.

## Local Setup

Use a normal clone of this repository. The checkout is source; the installed
runtime lives under the target user's `$HOME/.codex`.

Preview an install:

```bash
scripts/install.py --dry-run
```

Run the portable local checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
scripts/install.py --dry-run
scripts/build-public-release.py
scripts/release-drill.py
scripts/secret-scan.py --include-untracked
scripts/public-release-audit.py --include-untracked --all-refs
git diff --check
```

Run live operational verification only on a Mac with Codex installed:

```bash
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
~/.codex/bin/codex-computer-use-guard ensure
```

## Pull Requests

Keep pull requests narrow and include:

- what changed and why
- which release or safety invariant is affected
- the exact checks run and their result
- any live Mac verification that was intentionally skipped

Do not include raw `$HOME/.codex` state, rollback snapshots, smoke result JSON,
OAuth data, cookies, tokens, local app bundles, `.env` files, or generated
release artifacts under `var/`.

## Contribution License

By submitting a contribution, you agree that your contribution is licensed
under the Apache License 2.0, unless you clearly state otherwise before the
contribution is merged.

Funding is disabled for the current public release surface. If donations are
enabled later, they remain optional and separate from contribution review, and
do not buy support, maintainer availability, merge priority, or security
response priority.

## Security Reports

Do not open a public issue for a vulnerability, bypass, token exposure, or
privacy-sensitive report. Follow `SECURITY.md` and keep logs redacted.
