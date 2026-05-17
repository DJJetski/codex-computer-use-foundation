# Release Checklist

Use this before tagging or pushing a verified public release of the native
Codex Computer Use repair package.

## Portable Source Checks

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
scripts/install.py --dry-run
git diff --check
scripts/secret-scan.py --include-untracked
scripts/public-release-audit.py --include-untracked --all-refs
git status --short --branch --untracked-files=all
```

Expected:

- Unit tests pass.
- The installer dry-run does not require live Codex runtime mutation.
- The secret and public release audits show no findings.
- The working tree contains only intentional release changes.

## Generated Package Checks

```bash
scripts/build-public-release.py
scripts/release-drill.py
```

Expected:

- The generated public tree excludes `docs/internal/`, app bundles, rollback
  snapshots, raw smoke JSON, OAuth data, cookies, and `$HOME/.codex` state.
- The builder uses tracked files by default, writes
  `PUBLIC_RELEASE_MANIFEST.json`, normalizes tar metadata, and writes the
  `.sha256` sidecar.
- The non-live drill extracts the tarball and installs from the extracted copy
  into a clean temporary home.

## Live Mac Checks

Run these on the maintainer Mac or a sacrificial Mac with Codex installed. They
mutate foundation-owned runtime state under the selected home.

```bash
scripts/install.py --yes --full-ensure
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
~/.codex/bin/codex-computer-use-guard ensure
```

Optional destructive release-engineering proof:

```bash
scripts/release-drill.py --live --yes
```

Expected:

- Guard `ok=true`, `structural_ok=true`, all health layers true.
- Native smoke is fresh, fallback-free, and `second_mouse_verified=true`.
- The guard LaunchAgent and bootstrap backup are installed and loaded.
- `stale_native_smoke` is treated as fail-closed evidence, not as success.

Then verify the repo does not contain machine state or secrets:

```bash
rg -n -i 'last-native-smoke|\\.env|\\.codex/state|rollback|snapshot' .
```

Expected secret scan result:

- Matches in docs or source comments are acceptable only when they describe
  denylisted words or redaction policy.
- Raw credentials, OAuth data, cookies, smoke state JSON, snapshots, rollback
  bundles, and local state files are never acceptable.

## Publication Policy

The generated tree under `var/public-release/` is the tarball release surface,
and the checked-in repository is also a public surface once GitHub visibility is
public. Keep internal notes outside the tracked repository. The release builder
still deny-lists `docs/internal/` so a future accidental reintroduction fails
audit. Non-installable research or troubleshooting files under `src/` must also
stay out of the public tree; only install-manifest source files are copied from
`src/`.

Current public-release portability constraints:

- Uses `/Applications/Codex.app` by default; non-default locations must be
  passed with `--codex-app` and still validate as `com.openai.codex`.
- Assumes the target user has installed Codex, but native Computer Use may not
  be working before this package is installed.
- Uses neutral LaunchAgent labels `io.github.codex-computer-use-foundation.guard`
  and `io.github.codex-computer-use-foundation.dialog-autopilot`.
- May require Apple command-line tools if the target Mac needs the Swift shim
  repair path.

Before publishing a public artifact:

- Confirm `LICENSE` is present, detected as Apache-2.0, and names the intended
  copyright holder.
- Confirm README first screen explains what native Codex Computer Use is, why
  the native second-mouse path is different from fallback tools, and which
  failure modes this package repairs.
- Confirm `.github/FUNDING.yml` is either disabled or points only to a
  maintainer-approved non-personal voluntary donation channel.
- Confirm GitHub CI is green on the release commit.
- Build the public release with `scripts/build-public-release.py`.
- Publish both `codex-computer-use-foundation-public.tar.gz` and
  `codex-computer-use-foundation-public.tar.gz.sha256`.
- Run `scripts/release-drill.py` to prove the tarball installs from an
  extracted download copy into a clean temporary home.
- Install from `var/public-release/codex-computer-use-foundation-public`, not
  from maintainer working-tree internals.
- Confirm `docs/internal/` is absent from the Git index and generated tree, and
  non-manifest `src/` files are absent from the generated tree.

Before pushing a private source repo:

- Confirm the remote URL is the intended repo.
- Enable hooks once with `scripts/install-git-hooks.py`.
- Confirm `git remote -v` is configured.
- Confirm `git status --short --branch --untracked-files=all` shows only the
  intended committed state.
- Do not push rollback snapshots, raw inventories, `.env` files, or any part of
  `~/.codex`.

Recommended GitHub repository settings before a public release:

- Enable private vulnerability reporting or another private security contact
  before making the repository public.
- Enable secret scanning and push protection where available.
- Enable Dependabot alerts.
- Protect `main` with pull request review, required CI, required conversation
  resolution, deletion protection, and force-push protection.
- Consider CodeQL/code scanning after confirming the repository visibility and
  plan support it.

## Maintainer Privacy

- Confirm public docs, issue templates, release notes, generated manifests, and
  tarball contents do not include personal home paths, personal email addresses,
  raw usernames, OAuth data, smoke JSON, or machine-local logs.
- If a personal legal name, handle, or funding account is intentionally public,
  treat that as an explicit release decision and keep it out of automated
  support artifacts.
- Use `PUBLIC_RELEASE_AUDIT_EXTRA_MARKERS=name,handle,email` when checking any
  additional private markers before publication.
