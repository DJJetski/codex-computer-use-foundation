<h1 align="center">Codex Computer Use Foundation</h1>

<p align="center">
  <strong>Repair native OpenAI Codex Computer Use on macOS when tools are missing, hidden, timing out, or unable to click and type.</strong>
</p>

<p align="center">
  <a href="#quick-install">Quick Install</a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="docs/INSTALL.md">Install Guide</a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="docs/RUNBOOK.md">Runbook</a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="docs/CAPABILITY-PARITY.md">Parity</a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="SECURITY.md">Security</a>
</p>

## What This Is

Codex Computer Use Foundation is a macOS repair and validation kit for the
official native OpenAI Codex Computer Use path.

Use it when Codex is installed, but native Computer Use does not appear in a
fresh thread, `mcp__computer_use__` is missing, Computer Use tools time out, or
Codex cannot control Mac apps through the native tool surface listed below.

This can help both machines where Computer Use worked before and machines where
native Computer Use has never worked after installing Codex.

## Why Native Computer Use Matters

Native Computer Use is not just a visible mouse script. When it works, Codex can
discover apps, inspect app state, click, type, press keys, scroll, drag, set UI
values, select text, and use secondary actions through the official Computer Use
MCP path.

Fallbacks such as Haindy, `cliclick`, AppleScript, Accessibility scripting,
Keyboard Maestro, screenshots, and Playwright can be useful when a user
explicitly chooses an operator fallback. They are weaker as replacements because
they can depend on screen coordinates, frontmost-app focus, extra permissions,
browser or profile state, or signals Codex cannot verify as native MCP
evidence.

This project repairs and verifies the native OpenAI Codex Computer Use path
instead of disguising fallbacks as Computer Use. Full success requires fresh
native evidence and `fallback_used=false`.

## Quick Install

Requirements:

- macOS with Python 3 available as `python3`
- `git` for the clone command, or use the latest GitHub download path in
  [`docs/INSTALL.md`](docs/INSTALL.md)
- OpenAI Codex installed and opened at least once
- Codex normally at `/Applications/Codex.app`, or a path you can pass with
  `--codex-app`

```bash
git clone https://github.com/DJJetski/codex-computer-use-foundation.git
cd codex-computer-use-foundation
python3 --version
scripts/install.py --dry-run
scripts/install.py --yes --full-ensure
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
```

`--full-ensure` runs a live native smoke test. It opens Calculator in the
background, returns focus to Codex when possible, targets Calculator by bundle
id, and uses native app-state element indexes for the click targets. It can
still show Codex's native second pointer while it proves click and type
operations. Run it when a short local GUI verification is acceptable.

If Codex is not installed at `/Applications/Codex.app`, pass the app path once:

```bash
scripts/install.py --yes --full-ensure --codex-app /path/to/Codex.app
```

The installer persists that validated Codex app path for later Codex restarts
and Mac reboots.

## Symptoms This Helps With

People usually find this project while searching for:

- OpenAI Codex Computer Use not working on macOS
- Codex Computer Use tools missing
- `mcp__computer_use__` not showing up
- `computer-use@openai-bundled` disabled or not discoverable
- Codex cannot click, type, scroll, drag, or press keys
- Codex Computer Use never worked after install
- Codex Computer Use stopped working after update
- `SkyComputerUseClient mcp` timeout
- `Transport closed` or `procNotFound`
- Computer Use fails after a Codex, plugin, or macOS update
- fresh Codex thread does not expose native Computer Use tools

## What It Repairs

| Area | Result |
| --- | --- |
| Plugin discovery | Keeps the bundled `computer-use@openai-bundled` plugin enabled and discoverable. |
| MCP routing | Routes the Computer Use plugin to the native launcher and removes duplicate direct MCP aliases. |
| Native launcher | Uses `exec` so `SkyComputerUseClient mcp` keeps the Codex AppServer, AppleEvent, and Mach rendezvous context. |
| Runtime state | Repairs local marketplace mirrors, plugin cache, runtime copy, LaunchServices registration, and stale native client processes. |
| Persistence | Installs a user LaunchAgent and bootstrap backup so structural repair runs after Codex rewrites, Codex restarts, and Mac reboots. |
| Verification | Requires the full native MCP tool surface and fresh native smoke evidence before reporting full operational health. |
| Boundaries | Keeps fallback automation separate from native Computer Use success. |

## What It Does Not Do

This project does not replace Codex and does not modify
`/Applications/Codex.app`.

It does not grant macOS permissions, edit TCC databases, approve privacy
dialogs, approve security prompts, approve generic network/firewall decisions,
change account settings, install VPN routing, upload local state, or hide
AppleScript, Accessibility scripting, screenshots, Playwright, Keyboard
Maestro, Haindy, or `cliclick` inside the native Computer Use MCP path. The
separate dialog helper can handle narrowly matched Foundation/Codex repair
network prompts, including Little Snitch prompts, after the user has granted
the local automation permission; that helper is not native Computer Use health.

It is for troubleshooting and stabilizing native Computer Use routing. It is
not a way to bypass OpenAI usage policies, OpenAI safety checks, macOS privacy
controls, account protections, or third-party security controls.

OpenAI also documents locked computer use as a separate Codex app setting for
active trusted Computer Use turns after the Mac locks. This project does not
install or validate that authorization plug-in path; it only repairs and proves
the ordinary native MCP route.

## Safety And Privacy

The runtime installs into the current user's `$HOME/.codex` because that is the
layout Codex uses for local plugins, skills, and MCP metadata. The repo is the
source of truth; `$HOME/.codex` is the installed runtime.

Rollback snapshots and live verifier output can contain local paths and config
state. Do not post raw `$HOME/.codex` files, rollback snapshots, smoke JSON, or
full local verifier output in public issues. `snapshot-live-state.py` and
`verify-live-state.py --json` redact local home paths by default.

On some macOS/Codex combinations, a local copied Computer Use runtime under
`$HOME/.codex` may need an explicitly enabled Swift compatibility repair after
the native runtime probe proves it is necessary. That compatibility path leaves
the original OpenAI Codex app bundle untouched and is documented in
[`docs/INSTALL.md`](docs/INSTALL.md) and [`SECURITY.md`](SECURITY.md).

## How Verification Works

The guard reports full success only when the current Mac, current user profile,
and current Codex/macOS versions have fresh native evidence.

Full health requires:

- repaired structural routing
- full native Computer Use MCP tool surface discoverable
- no duplicate native MCP client ownership conflict
- native runtime ready
- fresh native smoke from the Codex MCP context
- fallback automation not used

If structural repair is healthy but native smoke is missing or stale, the guard
fails closed and tells you to run full `ensure`, use `tool_search`, or open a
fresh Codex thread.

If the guard is healthy but the already-open thread returns `Transport closed`
from `mcp__computer_use__`, treat that current thread as stale MCP state. Open a
fresh Codex thread and prove the native path again with
`mcp__computer_use__.list_apps`; do not switch to fallback automation.

## Release Evidence

Each published release is built from a sanitized source package, not from a
maintainer's live `$HOME/.codex` runtime. The release checks include unit tests,
installer dry-run, live installed-state verification, secret scan, public
release audit, package build, and release drill against a temporary home.

Release notes describe the exact capability and validation changes for that
package. Start with the latest note:
[`docs/releases/v0.1.12.md`](docs/releases/v0.1.12.md).

## Native Tool Surface

The guard does not treat a partial tool list as healthy. The native launcher
must expose this complete MCP surface:

| Tool | What Codex can do through native Computer Use |
| --- | --- |
| `list_apps` | Discover running and available apps. |
| `get_app_state` | Inspect the allowed target app state. |
| `click` | Click native UI targets. |
| `perform_secondary_action` | Use a secondary/context action where supported. |
| `set_value` | Set a supported UI value directly. |
| `select_text` | Select text in supported controls. |
| `scroll` | Scroll within the target app. |
| `drag` | Drag through the native tool path. |
| `press_key` | Press keys and key chords. |
| `type_text` | Type text through the native tool path. |

The live smoke test intentionally exercises a safe subset in Calculator.
Tool-surface parity is checked separately with `tools/list`, so a missing
`scroll`, `drag`, `set_value`, `select_text`, or secondary action tool fails
discovery before full health can pass.

For tasks that specifically depend on the user's normal Google Chrome
app/profile, run the separate native Chrome smoke:

```bash
$HOME/.codex/bin/codex-computer-use-guard chrome-smoke
```

That smoke stays inside the native Computer Use MCP surface and verifies Chrome
through `get_app_state`, `press_key`, and `set_value`.

For the official Codex Chrome Extension path, use the separate extension
diagnostic:

```bash
$HOME/.codex/bin/codex-computer-use-guard chrome-plugin-status
```

This checks that the bundled `chrome@openai-bundled` plugin is enabled, the
local marketplace mirror contains the Chrome plugin, the Chrome native host
manifest is present, and the active Chrome profile has the Codex Chrome
Extension installed and enabled. It does not install the extension or native
host; if those checks fail, re-add the Chrome plugin from Codex Plugins and
follow the official setup flow.

## Fresh Thread Check

After install or repair, open a fresh Codex thread. If native tools are not
visible yet, ask Codex to search for this exact tool surface:

```text
computer-use list_apps get_app_state click perform_secondary_action set_value select_text scroll drag press_key type_text
```

If `mcp__computer_use__` appears, prove the native path with:

```text
mcp__computer_use__.list_apps
```

If tools are still absent, run:

```bash
$HOME/.codex/bin/codex-computer-use-guard ensure
```

Then retry from a fresh Codex thread.

If the namespace appears but `list_apps` returns `Transport closed`, the current
thread loaded stale MCP transport state before repair completed. Run `ensure`
if needed, then retry from a fresh Codex thread.

## Documentation

| Start Here | Details |
| --- | --- |
| [`docs/WHAT-IS-COMPUTER-USE.md`](docs/WHAT-IS-COMPUTER-USE.md) | What native Codex Computer Use is and what this project repairs |
| [`docs/CAPABILITY-PARITY.md`](docs/CAPABILITY-PARITY.md) | Exact native MCP parity target, API action-name mapping, background-use proof, and dialog boundaries |
| [`docs/INSTALL.md`](docs/INSTALL.md) | Clone, install, verify, update, uninstall, and rollback steps |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Troubleshooting commands for missing tools, timeouts, and stale smoke |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the installer, guard, launcher, and plugin route fit together |
| [`docs/CURRENT-STATE.md`](docs/CURRENT-STATE.md) | The health contract for a working installation |
| [`SECURITY.md`](SECURITY.md) | Security boundaries, reporting, and privacy expectations |

## License

This project is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).

Use of the project is free and does not require payment.
