# Publication Notes

This project has two publication surfaces:

- the source repository, which may be private or public depending on maintainer
  choice
- the generated download package under `var/public-release/`, which is
  the end-user distribution surface

Public wording should stay centered on the user problem: Codex is installed on
a Mac, but native Computer Use is not working yet. The package exists to repair
and validate that native path, not to advertise a separate automation framework.

## Repository Presentation

The GitHub repository page should be easy to understand before it becomes
technical. Start the README with the text heading `Codex Computer Use
Foundation`, the short description, navigation links, and a copy-pasteable
install path. Do not put hero images, SVG diagrams, release cards, or other
design-heavy assets on the repo page.

The first public screen is for users, not maintainers. It should describe
native Computer Use missing or failing, local repair, verification, and the
fresh-thread check. Keep packaging and publication language in maintainer-only
sections.

## GitHub Release Readiness

The repository includes `SECURITY.md`, `CONTRIBUTING.md`, GitHub issue and pull
request templates, `LICENSE`, `.github/FUNDING.yml`, Dependabot configuration
for GitHub Actions, and CI that runs the portable release-safety checks.

The source repository and generated download package are licensed under Apache
License 2.0. Keep the root `LICENSE` file in the download package so
GitHub and release consumers can detect the license without reading secondary
documentation.

Funding is disabled for the current public release surface to avoid publishing
a personal sponsor handle. Do not require payment, follows, stars, or social
actions for access to the public release. If a maintainer later adds a funding
entry, do not describe donations as buying support, maintenance, warranty, or
priority response unless a separate paid offering is deliberately created.

GitHub-hosted settings still require owner/admin action. Before a public
release, enable the applicable security features for the target repository:
private vulnerability reporting or another private security contact, secret
scanning, push protection, Dependabot alerts, branch protection or rulesets for
`main`, and CodeQL/code scanning when the repository visibility and plan support
it.

For this repository, publication should match a solo-maintainer workflow. The
public can download, inspect, fork, and propose changes, but direct write access
stays limited to the owner or explicitly trusted collaborators. Do not require
a second approving reviewer for maintainer-owned updates. Do not configure a
required status check that blocks direct maintainer pushes before GitHub can
create the new commit's check run. Local hooks and CI should still run the
safety checks, but they should not turn normal owner publishing into a
multi-person approval process.

## Public-Safety Rules

- Keep personal home paths, local usernames, personal emails, machine snapshots,
  rollback bundles, raw `$HOME/.codex` state, OAuth data, cookies, and smoke
  JSON out of Git.
- Keep commit identities, release notes, generated tarballs, and public docs
  free of the maintainer's personal name, home path, local username, and
  personal email address.
- Protect downloaders: publish only the installable source surface, scripts,
  docs, tests, release assets, and checksums that a user can inspect and run
  without receiving local machine state or hidden automation.
- Keep LaunchAgent labels generic:
  `io.github.codex-computer-use-foundation.guard` and
  `io.github.codex-computer-use-foundation.dialog-autopilot`.
- Keep native Computer Use plugin-only. Do not add direct
  `[mcp_servers.computer-use*]` aliases.
- Keep skills and installer-owned runtime helpers in `src/` so a clone has the
  full installable source surface.

## Required Audit

Before publishing, run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
scripts/install.py --dry-run
scripts/secret-scan.py --include-untracked
scripts/public-release-audit.py --include-untracked --all-refs --enforce-public-surface
scripts/build-public-release.py
scripts/release-drill.py
git diff --check
git status --short --branch --untracked-files=all
```

The public release audit checks both files and Git commit identities. If it
fails on historical commits, publish only a sanitized history.

## Public Release Surface

`scripts/build-public-release.py` writes a sanitized source tree and tarball
under `var/public-release/`. That generated tree is the packaged distribution
surface. Once the GitHub repository is public, the checked-in source tree is
also public. Keep private maintainer notes outside the tracked repository. The
builder still excludes `docs/internal/`, local inventories, rollback snapshots,
raw smoke state, non-installable `src/` research files, and other
machine-local artifacts if those paths are reintroduced by mistake.

The builder also writes a SHA256 sidecar next to the tarball. Publish both the
tarball and its `.sha256` file as release assets. The builder defaults to
tracked files only and normalizes tar uid, gid, owner names, and member mtimes.
The release manifest records file hashes, source commit, exact tag when built
from a tag, source repository, and GitHub run id when present. Use
`SOURCE_DATE_EPOCH=<epoch>` only when deliberately overriding the source
timestamp for reproducible rebuilds.

Release tags should be annotated tags at the audited commit. If a tag is not
signed, say that explicitly in the release notes. Release notes should include:
the commit SHA, tag, tarball SHA256, whether live Mac verification passed, and
which audit commands ran.

Test the generated tree as if it were downloaded:

```bash
cd var/public-release/codex-computer-use-foundation-public
scripts/install.py --dry-run
scripts/install.py --yes --full-ensure
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
```

Or use the packaged drill:

```bash
scripts/release-drill.py
scripts/release-drill.py --live --yes
```

The first command proves package portability in a clean temporary home. The
`--live --yes` command is maintainer-only and destructive for the selected
home; it is the release-engineering proof for the real native path.

For a GitHub release consumer, publish the generated tarball and use:

```bash
curl -L -o /tmp/codex-computer-use-foundation-public.tar.gz \
  https://github.com/DJJetski/codex-computer-use-foundation/releases/latest/download/codex-computer-use-foundation-public.tar.gz
curl -L -o /tmp/codex-computer-use-foundation-public.tar.gz.sha256 \
  https://github.com/DJJetski/codex-computer-use-foundation/releases/latest/download/codex-computer-use-foundation-public.tar.gz.sha256
cd /tmp
shasum -a 256 -c codex-computer-use-foundation-public.tar.gz.sha256
mkdir -p /tmp/codex-computer-use-foundation-release
tar -xzf /tmp/codex-computer-use-foundation-public.tar.gz -C /tmp/codex-computer-use-foundation-release
cd /tmp/codex-computer-use-foundation-release/codex-computer-use-foundation-public
scripts/install.py --yes --full-ensure
```

## Maintainer-Only Surface

The public repository can contain:

- installable scripts in `scripts/`
- runtime helpers in `src/bin/`
- the canonical Computer Use skill in `src/skills/macos-computer-use/`
- the Computer Use plugin MCP shim in `src/plugin-shim/computer-use/`
- tests and verification scripts
- public docs for install, architecture, runbook, migration, and release

Neither the repository nor the generated public release should contain app
bundles, live Codex state, rollback snapshots, secrets, private maintainer
forensics, or machine-local smoke results.
