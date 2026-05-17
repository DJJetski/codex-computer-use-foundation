# Codex Computer Use Foundation

Repair and validation kit for native OpenAI Codex Computer Use on macOS.

Use this repository when Codex is installed on a Mac, but native Computer Use is
missing, does not appear in fresh threads, times out, loses its native MCP tool
transport, or cannot reliably control the local Mac through the official native
Computer Use path.

It targets the concrete failures people hit in real Codex sessions. Common
ways this shows up include "Codex Computer Use not working on macOS", "OpenAI
Codex Computer Use missing", "Computer Use tools not showing up", "Codex cannot
click or type", "Codex can see the screen but cannot control the app",
"Codex MCP Computer Use not found", "`computer_use` tools missing",
`mcp__computer_use__` missing or not found, `computer-use@openai-bundled`
disabled or not discoverable, `tool_search` not exposing `computer-use`,
`tools/list` not showing Computer Use, `list_apps`, `get_app_state`, `click`,
`type_text`, or `press_key` unavailable, `SkyComputerUseClient mcp` timing out
or hanging, `SkyComputerUseService` first-use prompts blocking setup,
`Transport closed`, `procNotFound`, duplicate native MCP clients, stale native
smoke, and native "second mouse" verification failing after Codex, plugin, or
macOS changes.

## What Computer Use Is

Computer Use is the capability that lets Codex inspect and operate a real Mac
GUI through tools such as app listing, app-state inspection, clicking, typing,
scrolling, dragging, and key presses.

Native Codex Computer Use is the official OpenAI Computer Use plugin path for
Codex on macOS. Instead of driving the Mac by moving the user's visible pointer
or replaying brittle coordinates, Codex talks to the native Computer Use MCP
server. That native server keeps the Codex AppServer, AppleEvent, and Mach
rendezvous needed for real Mac control.

In this repo, "second mouse" means the native path has proven GUI-action
evidence from the Codex MCP context, not a fallback script pretending to be
native. The guard only reports full success when fresh native smoke verifies
real native operations and `second_mouse_verified=true`.

For a plain-language overview, read
[`docs/WHAT-IS-COMPUTER-USE.md`](docs/WHAT-IS-COMPUTER-USE.md).

## Why Native Beats Fallback Automation

Tools such as Haindy, `cliclick`, AppleScript, Accessibility scripting,
Keyboard Maestro, screenshots, browser automation, and Playwright can be useful
operator paths for specific tasks. They are not the same thing as native Codex
Computer Use.

Native Computer Use is better for Codex-first work because:

- It is exposed as Codex MCP tools, so agents can discover and call it directly.
- It uses the official OpenAI Computer Use client instead of a parallel local
  automation stack.
- It can inspect app state and act through the native Computer Use channel
  rather than relying on screen coordinates alone.
- It preserves the Codex AppServer rendezvous that native tool calls need.
- It can provide "second mouse" behavior that fallback pointer automation
  cannot honestly claim.
- It gives machine-readable health evidence instead of "the cursor moved, so it
  probably worked."

Fallback tools remain valuable when the user explicitly chooses a fallback
operator path. This package does not hide them inside the native MCP route and
does not count them as native success.

## The Problem This Fixes

Native Computer Use does not work out of the box on every Mac. Common failure
classes include:

- the `computer-use@openai-bundled` plugin is disabled or not discoverable
- the OpenAI Codex desktop app is installed, but Computer Use tools are missing
- fresh Codex threads do not expose `mcp__computer_use__` until `tool_search`
  lazy-loads it
- `tool_search` finds no `computer-use` tools, or the MCP namespace never
  appears
- Codex reports no `list_apps`, `get_app_state`, `click`, `type_text`,
  `press_key`, `scroll`, or `drag` tool for desktop control
- native Computer Use calls hang, time out, return `Transport closed`, or lose
  the MCP transport
- Codex appears able to inspect a screenshot but cannot reliably click, type,
  scroll, drag, press keys, or operate the target app
- local marketplace or plugin-cache routing points at the wrong command
- direct `[mcp_servers.computer-use*]` aliases create duplicate native clients
- stale `SkyComputerUseClient mcp` processes poison new tool calls
- the native launcher starts the client as a child process and loses rendezvous
- local runtime copies or LaunchServices registrations drift after Codex updates
- macOS permission prompts or helper dialogs block first-use flows
- a macOS/Codex runtime mismatch needs the guard-owned compatibility repair

This repo makes the repair reviewable, versioned, reproducible, and portable.
It installs a small source-owned runtime into the current user's `$HOME/.codex`,
because Codex and the bundled Computer Use plugin expect that layout.

It does not patch `/Applications/Codex.app`, bypass macOS privacy permissions,
install VPN routing, add hidden GUI fallbacks, or upload local state.

## What Gets Installed

The source repo is the source of truth. `$HOME/.codex` is the installed runtime.
Run the installer instead of hand-editing live files.

Main installed pieces:

| Installed path | Purpose |
| --- | --- |
| `$HOME/.codex/bin/codex-computer-use-guard` | Repairs config, marketplace, plugin cache, runtime copy, LaunchAgents, process ownership, and health evidence. |
| `$HOME/.codex/bin/codex-computer-use-native-launcher` | Fast preflight repair, then `exec`s the official patched `SkyComputerUseClient mcp` in the same process. |
| `$HOME/.codex/bin/codex-computer-use-native-smoke` | Compatibility entrypoint for guard-owned native smoke. |
| `$HOME/.codex/bin/codex-computer-use-preflight` | Read-only health preflight before GUI work. |
| `$HOME/.codex/bin/codex-computer-use-notify` | Fail-open notification wrapper with stale helper cleanup. |
| `$HOME/.codex/bin/codex-dialog-autopilot` | Separate narrow local dialog helper for routine allow/OK/helper/firewall/AppData prompts. Not native Computer Use. |
| `$HOME/.codex/skills/macos-computer-use/SKILL.md` | The one visible Computer Use skill users and agents should load. |
| `$HOME/.codex/plugins/marketplaces/openai-bundled/plugins/computer-use/.mcp.json` | Plugin MCP shim that routes Codex plugin loading to the native launcher. |

Generated local state includes guard status, fresh native smoke evidence,
rollback snapshots, LaunchAgents, bootstrap backups, marketplace mirrors, plugin
cache repair, and a LaunchServices runtime copy. These are machine-local and
must not be published.

## Skills And Discovery

Codex skills are instruction files that tell agents when and how to use a
capability. This package installs one human-facing skill:

```text
$HOME/.codex/skills/macos-computer-use/SKILL.md
```

The bundled Computer Use plugin still provides the MCP server, but its duplicate
plugin `skills/` entry is suppressed. Users should see one clear Computer Use
skill, not a plugin shim plus a local skill competing with each other.

Fresh threads may not show `mcp__computer_use__` immediately. That can be normal
lazy loading. The correct first move is:

```text
tool_search: computer-use list_apps get_app_state click type_text press_key
```

If the namespace appears, prove native operation with
`mcp__computer_use__.list_apps`. If it still does not appear, run the guard
repair path before choosing any fallback.

## Quick Install

Preview:

```bash
scripts/install.py --dry-run
```

Install and run full native validation:

```bash
scripts/install.py --yes --full-ensure
```

Verify the installed runtime:

```bash
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
```

Install instructions for a GitHub release tarball are in
[`docs/INSTALL.md`](docs/INSTALL.md).

## Current Verdict

Native Computer Use is considered operational for the current Mac, current
user profile, and current Codex/macOS versions when the installed guard reports
`ok=true` with fresh native smoke. This package repairs and validates known
native routing failures; it cannot promise that future Codex or macOS releases
will never introduce new failures.

Full success requires:

- `configured=true`
- `discoverable=true`
- `runtime_ready=true`
- `mcp_client_ownership=true`
- `appserver_rendezvous=true`
- `operational=true`
- `second_mouse_verified=true`
- fresh native smoke from the Codex MCP context
- `fallback_used=false`

If `status` later reports `ok=false` only because
`failure_class=stale_native_smoke`, that is fail-closed behavior, not a
regression. Run:

```bash
$HOME/.codex/bin/codex-computer-use-guard ensure
```

## Public Release Package

Build a sanitized public release tree and tarball:

```bash
scripts/build-public-release.py
```

The generated tree under `var/public-release/` excludes internal forensic
notes, troubleshooting history, local state, snapshots, app bundles, tokens,
cookies, OAuth data, and raw smoke JSON. It contains the installable runtime
source, public docs, tests, and release tooling needed by a consumer. Release
builds default to tracked files only, normalize tar metadata, and write a
SHA256 sidecar for the tarball.

Test the package like a downloaded release:

```bash
scripts/release-drill.py
```

Maintainer-only live proof, which destructively uninstalls and reinstalls
foundation-owned runtime state in the target home:

```bash
scripts/release-drill.py --live --yes
```

## License And Funding

This project is licensed under the Apache License 2.0. See `LICENSE`.

Use of the project is free and does not require payment. Funding is disabled
for the public release surface unless a maintainer deliberately adds a
non-personal donation channel later. Donations, if ever enabled, do not create
a support, maintenance, warranty, or priority-response obligation.

## Documentation

- [`docs/WHAT-IS-COMPUTER-USE.md`](docs/WHAT-IS-COMPUTER-USE.md)
- [`docs/INSTALL.md`](docs/INSTALL.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/CURRENT-STATE.md`](docs/CURRENT-STATE.md)
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
- [`docs/RELEASE-CHECKLIST.md`](docs/RELEASE-CHECKLIST.md)
- [`docs/PUBLICATION.md`](docs/PUBLICATION.md)
- [`AGENTS.md`](AGENTS.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SECURITY.md`](SECURITY.md)
