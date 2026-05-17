# What Is Codex Computer Use?

Computer Use is the part of Codex that can operate a real Mac GUI. It lets an
agent inspect running apps, read app state, click controls, type text, press
keys, scroll, drag, and complete workflows that do not have a simpler API.

Native Codex Computer Use is the official OpenAI Computer Use path inside
Codex. On macOS it is exposed through the bundled Computer Use plugin and its
MCP server, backed by the OpenAI native Computer Use client.

This repository is a repair and validation system for that native path.
For the exact parity target, official-source summary, API action-name mapping,
and dialog operator boundary, see `docs/CAPABILITY-PARITY.md`.

## Native Computer Use In Plain English

When native Computer Use works, Codex is not just guessing where to click from a
screenshot. Codex can ask the native tool layer which apps exist, inspect the
target app, and send actions through the native Computer Use channel.

That matters because GUI work is fragile. A visible cursor click can miss when a
window moves, focus changes, a dialog appears, or a coordinate is slightly off.
Native Computer Use gives Codex a better control plane for local Mac work and a
better way to verify that the action really happened.

## How Verification Works

This project treats native interaction evidence as a concrete health claim, not
as marketing.

The guard reports `second_mouse_verified=true` only after fresh native smoke
proves that the Codex MCP path completed real native GUI actions without using a
fallback. That evidence must come from the native Computer Use route, not from
`cliclick`, AppleScript, Accessibility scripting, screenshots, Keyboard Maestro,
Playwright, or a browser automation profile.

The important distinction is:

- Native Computer Use: Codex calls the official Computer Use MCP tools and the
  native client performs the action.
- Fallback automation: another tool moves the pointer, sends keys, scripts UI
  elements, or drives a browser on Codex's behalf.

Fallback automation can be useful. It is just not native Computer Use.

## How This Differs From Haindy, cliclick, AppleScript, And Similar Tools

Haindy, `cliclick`, AppleScript, Accessibility scripting, Keyboard Maestro,
screenshot automation, and Playwright all have places where they are useful.
They are often good operator tools when a user explicitly chooses a fallback.

They are weaker as a replacement for native Codex Computer Use because they
usually sit outside Codex's official Computer Use MCP path. They can move the
visible pointer, replay coordinates, depend on frontmost-app focus, require
separate permissions, or produce success signals that are hard for Codex to
trust.

Native Codex Computer Use is better for Codex-native work because it is:

- discoverable through Codex tool loading
- designed for Codex MCP tool calls
- tied to the OpenAI native Computer Use client
- able to preserve the Codex AppServer / AppleEvent / Mach rendezvous
- validated by machine-readable native smoke evidence
- separated from explicit fallback operator paths

This repo keeps that boundary strict. It repairs native Computer Use; it does
not hide fallback tools behind the native tool name.

## Why Native Computer Use Does Not Work For Everyone

Codex and the Computer Use plugin rely on several local pieces working together:
Codex config, plugin metadata, marketplace mirrors, plugin cache, native runtime
copies, LaunchServices registration, the native client, macOS permissions, and
fresh thread tool discovery.

On some Macs one or more of those pieces drift. Common symptoms include:

- "Codex Computer Use not working" even though Codex itself is installed
- "OpenAI Codex Computer Use missing" or "Computer Use tools not showing up"
- Codex can view the desktop or a screenshot but cannot click, type, scroll,
  drag, press keys, or control the target app
- Codex has no `list_apps`, `get_app_state`, `click`, `type_text`,
  `press_key`, `scroll`, or `drag` tool for native desktop control
- `mcp__computer_use__` is not visible in a new Codex thread
- `tool_search` cannot expose Computer Use tools
- native calls hang, time out, lose MCP transport, report `Transport closed`, or
  return `procNotFound`
- `computer-use@openai-bundled` is disabled, absent, or not discoverable
- `SkyComputerUseClient mcp` is started more than once under the same Codex
  AppServer
- `SkyComputerUseClient mcp` hangs, exits, times out, or leaves stale duplicate
  processes behind
- a wrapper starts the native client as a child process and loses rendezvous
- Codex updates rewrite plugin cache or marketplace state
- macOS helper dialogs block first-use setup
- local runtime compatibility checks fail after a macOS or Codex update

The foundation installer and guard repair those local failure modes where they
can be repaired safely from user-owned files.

## Native Tool Surface

The installed Computer Use plugin exposes the native Codex Mac control surface
as MCP tools. This project treats the complete tool list as part of health:

| Tool | Native capability |
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

The guard fails discovery if any of those tools are missing. The live smoke
test then proves a safe subset through Safari because it should not perform
destructive or broad UI actions just to prove installation health.

## What This Repo Does

This repo installs source-owned repair files into `$HOME/.codex`, then validates
the official native Computer Use path.

It does:

- keep `computer-use@openai-bundled` enabled and discoverable
- remove direct Computer Use MCP aliases that create duplicate native clients
- mirror and patch local plugin marketplace routing
- route the plugin MCP command to the native launcher
- make the launcher `exec` `SkyComputerUseClient mcp` in the same process
- maintain a guard LaunchAgent and bootstrap backup
- clean stale duplicate native MCP clients
- install one canonical Computer Use skill
- suppress duplicate plugin skill publication
- record layered health and fresh native smoke evidence
- keep fallback tools out of native success reporting

It does not:

- patch `/Applications/Codex.app`
- bypass macOS privacy controls
- edit TCC databases
- install VPN routing
- upload local inventories, smoke records, rollback snapshots, tokens, cookies,
  or OAuth data
- treat `cliclick`, AppleScript, Accessibility, screenshots, Keyboard Maestro,
  browser automation, or Playwright as native Computer Use

## How To Use It

From a checkout or release package:

```bash
scripts/install.py --dry-run
scripts/install.py --yes --full-ensure
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
```

Then open a fresh Codex thread. If Computer Use tools are not visible, ask
Codex to search for:

```text
computer-use list_apps get_app_state click perform_secondary_action set_value select_text scroll drag press_key type_text
```

If `mcp__computer_use__` appears, prove it with:

```text
mcp__computer_use__.list_apps
```

If tools are still absent, run:

```bash
$HOME/.codex/bin/codex-computer-use-guard ensure
```

and retry from a fresh Codex thread if the current thread loaded tool metadata
before the repair completed.

## Quick FAQ

### What does this fix?

It fixes local native Codex Computer Use exposure and runtime failures on macOS:
missing `mcp__computer_use__`, missing `computer-use` MCP tools, broken
`computer-use@openai-bundled` discovery, duplicate `SkyComputerUseClient mcp`
processes, stale native smoke, native MCP timeouts, `Transport closed`,
`procNotFound`, and failed second-mouse verification.

### Is this a replacement for Haindy, cliclick, AppleScript, or Keyboard Maestro?

No. Those tools can be useful explicit fallbacks, but they are not the official
native OpenAI Codex Computer Use path. This project repairs the native path
instead of disguising fallback automation as Computer Use.

### Does this make Codex click and type through the visible mouse?

No. Full success means the native Computer Use MCP route works and verifies real
GUI action evidence. Moving the user's visible pointer with `cliclick` or a
script is not counted as native Computer Use.

The guard's live native smoke may still show Codex's native second pointer
while it proves the official route. That is different from a coordinate script:
the proof targets Safari by bundle id through `computer-use` tools and requires
`fallback_used=false`.

The smoke proves non-frontmost native app action. It does not claim arbitrary
control of minimized windows, invisible windows, off-Space windows, Terminal,
Codex itself, administrator prompts, or security/privacy/network/firewall
dialogs.

### Does this help when Codex cannot click, type, scroll, drag, or press keys on my Mac?

Yes, if the failure is in native Codex Computer Use exposure or runtime health.
The guard checks whether the Computer Use plugin is discoverable, whether
`mcp__computer_use__` can appear in a fresh thread, whether native tools such as
`list_apps`, `get_app_state`, `click`, `perform_secondary_action`, `set_value`,
`select_text`, `scroll`, `drag`, `press_key`, and `type_text` exist, and whether
native smoke proves GUI actions through the official path.

### What if Computer Use is installed but no MCP tools appear?

That usually means Codex did not expose the bundled Computer Use plugin to the
thread, the local plugin cache or marketplace mirror drifted, or duplicate
direct MCP aliases started conflicting `SkyComputerUseClient mcp` processes.
Run the guard, then retry discovery in a fresh Codex thread.

### Why open a fresh Codex thread after repair?

Codex tool discovery can happen before the plugin metadata is repaired. A fresh
thread gives Codex another chance to expose `mcp__computer_use__` and the native
Computer Use tools after the guard reports healthy state.
