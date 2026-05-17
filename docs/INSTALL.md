# Clone Install

This repo is an installable source distribution for repairing native Codex
Computer Use on macOS.

The expected user has already installed Codex, but native Computer Use does not
work yet or is not reliably exposed to fresh Codex threads. The installer
rebuilds the local plugin routing and runtime support needed for the official
native Computer Use path; it does not replace native Computer Use with fallback
automation.

It installs into the current user's `$HOME/.codex` because Codex and the
bundled Computer Use plugin expect that runtime layout. The repo is the source
of truth; `$HOME/.codex` is the installed runtime. The installer computes all
targets from the target process `HOME` and does not embed maintainer-specific
absolute home paths.

If you are deciding whether this package is relevant, start with
`docs/WHAT-IS-COMPUTER-USE.md`. The short version: this package repairs the
official native Codex Computer Use route. It does not replace Computer Use with
Haindy, `cliclick`, AppleScript, screenshots, Playwright, Keyboard Maestro, or
another fallback automation stack.

## Install From A Checkout

Preview first:

```bash
scripts/install.py --dry-run
```

Install source files and run structural repair, including the guard
LaunchAgent/bootstrap persistence layer:

```bash
scripts/install.py --yes
```

This prepares restart self-healing but does not prove live native operation.
Use `--full-ensure` for the recommended install path.

Install and prove the full native path, including guard `ensure` and fresh
native smoke when the guard decides refresh is needed:

```bash
scripts/install.py --yes --full-ensure
```

## Install On Another Mac

Prerequisites:

- macOS
- Python 3 available as `python3`
- OpenAI Codex installed at `/Applications/Codex.app`
- Codex has been opened at least once so `$HOME/.codex` exists. If it has not,
  open Codex once, close it, then run the installer.
- Apple command-line tools may be required on macOS/Codex combinations that
  need the guard's Swift priority-escalation shim repair. The guard checks
  this only when the dyld failure is detected.
- the user accepts any normal one-time macOS permissions required by native
  Computer Use; this package does not grant or bypass those permissions

Then clone the repo and run:

```bash
git clone https://github.com/DJJetski/codex-computer-use-foundation.git
cd codex-computer-use-foundation
python3 --version
scripts/install.py --dry-run
scripts/install.py --yes --full-ensure
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
```

On slow first-run machines or machines waiting on normal Codex/macOS helper
startup, extend postinstall timeouts instead of rerunning half-completed
commands:

```bash
scripts/install.py --yes --full-ensure --ensure-config-timeout 120 --full-ensure-timeout 420
```

If Codex is installed somewhere other than `/Applications/Codex.app`, pass
`--codex-app /path/to/Codex.app`. The installer validates the bundle identifier
before running the guard.

After installation, open a fresh Codex thread and use the native fresh-thread
procedure in `docs/RUNBOOK.md`.

## Install From A Public Release

After a GitHub release exists, download the public tarball and its `.sha256`
sidecar:

```bash
curl -L -o /tmp/codex-computer-use-foundation-public.tar.gz <release-asset-url>
curl -L -o /tmp/codex-computer-use-foundation-public.tar.gz.sha256 <checksum-asset-url>
cd /tmp
shasum -a 256 -c codex-computer-use-foundation-public.tar.gz.sha256
mkdir -p /tmp/codex-computer-use-foundation-release
tar -xzf /tmp/codex-computer-use-foundation-public.tar.gz -C /tmp/codex-computer-use-foundation-release
cd /tmp/codex-computer-use-foundation-release/codex-computer-use-foundation-public
scripts/install.py --dry-run
scripts/install.py --yes --full-ensure
```

Codex can follow the same steps when given the release asset URL. The package
contains all installer source files; it must not depend on this private working
tree.

For a local proof of that flow from a generated tarball:

```bash
scripts/release-drill.py
```

For a downloaded tarball, use the published SHA256:

```bash
scripts/release-drill.py --tarball /tmp/codex-computer-use-foundation-public.tar.gz --expected-sha256 <published-sha256>
```

## What The Installer Does

- Validates source files and Python syntax.
- Refuses non-macOS or missing `/Applications/Codex.app` unless explicitly
  running a temp-home test with `--skip-runtime-checks`, or validates the path
  passed with `--codex-app`.
- Snapshots and removes direct Computer Use MCP aliases and stale
  foundation-owned config stanzas before reinstalling.
- Creates a rollback snapshot under:

  ```text
  $HOME/.codex/state/computer-use-foundation/snapshots/
  ```

- The rollback snapshot includes manifest-owned files plus sensitive live
  repair surfaces that postinstall can mutate, including
  `$HOME/.codex/config.toml`, the guard and dialog LaunchAgents, bootstrap
  backups, and Computer Use plugin routing files. Treat rollback snapshots as
  local machine state, not publishable artifacts.
- Atomically installs only the manifest-owned files from `src/`.
- Runs `codex-computer-use-guard ensure-config --quiet` unless
  `--skip-postinstall` is used.
- Runs full `codex-computer-use-guard ensure` when `--full-ensure` is used.
  That full pass also asks the guard to install/report the separate
  `codex-dialog-autopilot` LaunchAgent where local Accessibility permission
  allows it.
- The postinstall timeouts default to 60 seconds for `ensure-config` and 240
  seconds for full `ensure`. They can be overridden with
  `--ensure-config-timeout`, `--full-ensure-timeout`,
  `CODEX_CU_INSTALL_ENSURE_CONFIG_TIMEOUT`, or
  `CODEX_CU_INSTALL_FULL_ENSURE_TIMEOUT`.

## Installed Runtime Inventory

The install manifest owns these source-to-runtime files:

| Source path | Installed path | Why it exists |
| --- | --- | --- |
| `src/bin/codex-computer-use-guard` | `$HOME/.codex/bin/codex-computer-use-guard` | Main repair, status, self-healing, native smoke, LaunchAgent, process cleanup, and health calculation command. |
| `src/bin/codex-computer-use-native-launcher` | `$HOME/.codex/bin/codex-computer-use-native-launcher` | Plugin MCP command. It runs fast guard repair and then `exec`s `SkyComputerUseClient mcp` in the same process. |
| `src/bin/codex-computer-use-native-smoke` | `$HOME/.codex/bin/codex-computer-use-native-smoke` | Compatibility wrapper for guard-owned native smoke. |
| `src/bin/codex-computer-use-preflight` | `$HOME/.codex/bin/codex-computer-use-preflight` | Read-only health preflight for planned GUI work. |
| `src/bin/codex-computer-use-notify` | `$HOME/.codex/bin/codex-computer-use-notify` | Notification wrapper that fails open and cleans stale notification helpers. |
| `src/bin/codex-dialog-autopilot` | `$HOME/.codex/bin/codex-dialog-autopilot` | Separate allowlisted local dialog helper. It is not native Computer Use and is not native health evidence. |
| `src/bin/codex-computer-use-broker` | `$HOME/.codex/bin/codex-computer-use-broker` | Broker compatibility wrapper kept under the same source-owned runtime boundary. |
| `src/skills/macos-computer-use/SKILL.md` | `$HOME/.codex/skills/macos-computer-use/SKILL.md` | The one visible Computer Use skill. It tells Codex agents how to prefer, repair, and verify native Computer Use. |
| `src/skills/macos-computer-use/agents/openai.yaml` | `$HOME/.codex/skills/macos-computer-use/agents/openai.yaml` | Skill metadata for the Codex skill picker. |
| `src/plugin-shim/computer-use/.mcp.json` | `$HOME/.codex/plugins/marketplaces/openai-bundled/plugins/computer-use/.mcp.json` | Plugin MCP metadata that points Codex plugin loading at the local native launcher. |
| `src/plugin-shim/computer-use/codex-computer-use-mcp` | `$HOME/.codex/plugins/marketplaces/openai-bundled/plugins/computer-use/codex-computer-use-mcp` | Plugin-local wrapper that preserves portable plugin routing. |

The guard may also create or repair these generated local surfaces:

| Generated path | Why it exists |
| --- | --- |
| `$HOME/.codex/state/computer-use-guard/` | Machine-readable status and native smoke evidence. |
| `$HOME/.codex/state/computer-use-foundation/snapshots/` | Rollback snapshots for install recovery. Local only. |
| `$HOME/.codex/plugins/marketplaces/openai-bundled` | Stable local mirror of the bundled marketplace that Codex can load. |
| `$HOME/.codex/.tmp/bundled-marketplaces/openai-bundled` | Startup mirror used by Codex during plugin discovery. |
| `$HOME/.codex/plugins/cache/openai-bundled/computer-use` | Official plugin cache copy repaired for local routing/runtime compatibility. |
| `$HOME/.codex/computer-use/` | LaunchServices runtime copy for the native Computer Use app bundle. |
| `~/Library/LaunchAgents/io.github.codex-computer-use-foundation.guard.plist` | Fast self-healing guard at login and after local Codex/plugin/config rewrites. |
| `~/Library/LaunchAgents/io.github.codex-computer-use-foundation.dialog-autopilot.plist` | Optional narrow dialog helper daemon. |
| `~/Library/Application Support/CodexComputerUseGuard/` | Guard/dialog bootstrap backups used when live runtime files are deleted or truncated. |

## Uninstall / Fresh Install Drill

To simulate a machine before this foundation was installed, remove
foundation-owned files and generated state:

```bash
scripts/uninstall.py --dry-run --purge-state
scripts/uninstall.py --yes --purge-state
```

This removes manifest-owned files, the local bundled-marketplace mirror,
Computer Use cache/runtime copies, guard state, LaunchAgents, bootstrap
backups, and foundation-owned config stanzas. It does not remove the Codex app
or unrelated `$HOME/.codex` settings.

## What The Installer Does Not Do

- It does not edit TCC databases.
- It does not modify `/Applications/Codex.app`.
- It does not bypass macOS privacy prompts or grant permissions without the
  user's normal macOS approval flow.
- It does not approve privacy, account, cloud, security, payment, TCC,
  password, or SecurityAgent prompts through the dialog helper.
- It does not spoof signatures or entitlements on the OpenAI app bundle. On
  macOS/Codex combinations with the known Swift runtime gap, an explicitly
  enabled compatibility path may ad-hoc sign local copied runtime bundles under
  `$HOME/.codex` only; the original OpenAI app remains untouched.
- It does not add VPN, browser, AppleScript, Accessibility, `cliclick`,
  screenshots, Playwright, or Keyboard Maestro as hidden Computer Use fallbacks.
- It does not commit or upload snapshots.
- It does not copy app bundles or the whole `$HOME/.codex` tree into this repo.

## Portability Notes

- The guard LaunchAgent label is
  `io.github.codex-computer-use-foundation.guard`. That stable identifier is
  intentionally generic and works on another Mac.
- The dialog helper LaunchAgent label is currently
  `io.github.codex-computer-use-foundation.dialog-autopilot` for the same
  reason.
- Codex is expected at `/Applications/Codex.app` by default. If it is installed
  elsewhere, pass `--codex-app /path/to/Codex.app`; the installer validates
  that the bundle identifier is `com.openai.codex` and persists that app path
  under `$HOME/.codex/state/computer-use-guard/codex-app-path` so later
  LaunchAgent repair and plugin launches use the same validated Codex app.
- `codex-dialog-autopilot` is source-owned and manifest-installed, but it is
  not part of the native Computer Use MCP path and is not a native operational
  health gate. It exists only for narrow local allow/OK/helper/firewall/AppData
  prompts.

## Verify

Read-only source and live-state verifier with operational native evidence:

```bash
scripts/verify-live-state.py --require-operational --json
```

Verify that manifest-owned live files match this repo source:

```bash
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
```

Generate a redacted live inventory:

```bash
scripts/snapshot-live-state.py > /tmp/codex-computer-use-inventory.json
```

Do not commit raw inventories or rollback snapshots.

## Rollback

If an install needs to be rolled back, choose the latest snapshot:

```bash
ls -1 "$HOME/.codex/state/computer-use-foundation/snapshots"
```

Preview:

```bash
scripts/rollback.py "$HOME/.codex/state/computer-use-foundation/snapshots/<snapshot>" --dry-run
```

Restore:

```bash
scripts/rollback.py "$HOME/.codex/state/computer-use-foundation/snapshots/<snapshot>" --yes
```

Run the guard after rollback:

```bash
"$HOME/.codex/bin/codex-computer-use-guard" ensure
```
