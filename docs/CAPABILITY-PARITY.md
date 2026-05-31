# Native Capability Parity

This project repairs and validates the native Codex app Computer Use path. Its
parity target is the Computer Use plugin surface that OpenAI ships with Codex,
not a separate AppleScript, browser, pointer, or Accessibility automation stack.

## Official Baseline

OpenAI's Codex app Computer Use documentation says the feature lets Codex see
and operate graphical macOS interfaces after the Computer Use plugin is
installed and normal Screen Recording and Accessibility permissions are
granted. OpenAI lists good fits such as desktop app testing, browser tasks,
graphical bug reproduction, app settings changes, visual inspection of data
sources, background work while the user keeps working elsewhere, and workflows
that span more than one app:

- <https://developers.openai.com/codex/app/computer-use>
- <https://openai.com/index/codex-for-almost-everything/>

The same OpenAI docs also state important boundaries: app approvals are
separate from macOS permissions, Codex can act only in apps the user allows,
users should stay present for sensitive flows, and Computer Use can view screen
content, take screenshots, and interact with windows, menus, keyboard input, and
clipboard state in the target app. The docs also state that Computer Use cannot
automate terminal apps or Codex itself, authenticate as an administrator, or
approve security and privacy permission prompts on the computer.

Those boundaries are part of parity. This package must not make a public user
believe it can bypass OpenAI approvals, macOS privacy controls, account
protection, network/firewall products, or security prompts.

## Codex App MCP Tool Surface

The Codex app exposes native Computer Use through MCP tools. The current native
surface verified from the installed OpenAI Computer Use plugin is:

| Native MCP tool | Capability |
| --- | --- |
| `list_apps` | Discover running and recently used apps. |
| `get_app_state` | Start an app-use session if needed, then return the target app window state, screenshot, and accessibility tree. |
| `click` | Click by accessibility element index or screenshot coordinates. `click_count` covers double-click style interaction. |
| `perform_secondary_action` | Invoke a secondary accessibility action exposed by an element. |
| `set_value` | Set the value of a settable accessibility element. |
| `select_text` | Select text or place the text cursor in supported text elements. |
| `scroll` | Scroll a target element by pages in a direction. |
| `drag` | Drag between screenshot coordinates. |
| `press_key` | Press keys and key combinations. |
| `type_text` | Type literal text through the native tool path. |

The guard, verifier, public audit, README, runbook, and canonical skill all use
this exact list. The same list was verified against the installed Codex
26.519.31651 / Computer Use plugin 1.0.799 runtime. A missing tool fails
discovery before the runtime can report full health.

The guard also validates each expected argument contract:
`get_app_state.app`, `click.app` plus `click.element_index`,
`perform_secondary_action.app` plus `element_index` plus `action`,
`set_value.app` plus `element_index` plus `value`,
`select_text.app` plus `element_index`, `scroll.app` plus `element_index` plus
`direction`, `drag.app` plus `from_x`/`from_y`/`to_x`/`to_y`,
`press_key.app` plus `key`, and `type_text.app` plus `text`. Full parity is not
claimed when a tool name exists but its native parameters are missing or the
fields that the official schema marks required are no longer required.

## API Computer Use Versus Codex App Computer Use

OpenAI's API Computer Use guide describes model actions such as `click`,
`double_click`, `scroll`, `type`, `wait`, `keypress`, `drag`, `move`, and
`screenshot` for custom harnesses:

- <https://developers.openai.com/api/docs/guides/tools-computer-use>

That API action list is not a one-to-one list of Codex app MCP tool names. In
the Codex app plugin:

- `double_click` maps to `click` with a multi-click count.
- `type` maps to `type_text`.
- `keypress` maps to `press_key`.
- `screenshot` and app inspection are provided by `get_app_state`.
- `wait` is agent control flow, not a separate Codex app MCP tool.
- `move` is not currently exposed as a standalone Codex app MCP tool.

Therefore this project should not invent extra MCP tools named `move`, `wait`,
or `screenshot` to appear more complete. Exact parity means preserving and
validating the native tool surface that the bundled OpenAI Codex app plugin
actually publishes.

OpenAI's app-level documentation mentions screenshots, menus, keyboard input,
and clipboard state as target-app interaction surfaces. In the current bundled
Codex app MCP plugin, screenshots and app state are exposed through
`get_app_state`, keyboard input through `press_key` and `type_text`, menu-like
or secondary UI operations through `click` or `perform_secondary_action`, and
there is no standalone clipboard MCP tool. If the bundled plugin adds one, the
expected tool list and audits should change with it.

## Background And The Native Second Pointer

OpenAI describes background Computer Use as Codex seeing, clicking, and typing
with its own cursor while multiple agents work on a Mac without interfering
with the user's own work in other apps. This package verifies the same class of
native operation by requiring fresh native smoke evidence with
`fallback_used=false`.

The release smoke intentionally opens Calculator with `open -g`, returns focus
to Codex when possible, targets Calculator by bundle id, and proves native
`click`, `type_text`, and `press_key` behavior without relying on the frontmost
app. For health evidence, the smoke uses
accessibility element indexes from `get_app_state` so a passing result proves
semantic app-state control; coordinate clicks remain part of the normal native
tool surface. The payload records whether Calculator appeared frontmost during
the smoke so non-frontmost evidence is visible instead of assumed. Current live
validation on Computer Use plugin 1.0.799 verified the Calculator target as not
frontmost.

The installed route can be healthy while an already-open Codex thread still has
stale MCP transport state from before repair. If `mcp__computer_use__` is
visible but a call returns `Transport closed`, parity is proven only after a
fresh thread or another live thread successfully calls `mcp__computer_use__.list_apps`.
The smoke cleanup is best-effort; native parity is based on structured MCP
events and fallback-free interaction evidence, not on a brittle final text
marker about whether the temporary Calculator window closed.

## Locked Computer Use Boundary

OpenAI now documents locked computer use as an optional Codex app mode that can
let an active trusted Computer Use turn continue after the Mac locks. The
official flow is enabled in Codex settings and uses an OpenAI-installed macOS
authorization plug-in with a short-lived, scoped unlock attempt.

That capability is outside this repair package's parity target. Foundation
repairs the plugin routing, native launcher, runtime copy, permission-facing
diagnostics, and live native smoke evidence for ordinary unlocked Codex app
Computer Use. It must not install, alter, validate, or claim support for the
locked-use authorization plug-in. If locked computer use is needed, use Codex's
own Computer Use settings and OpenAI's setup flow; this repo should only verify
that the normal native MCP route remains healthy before or after that separate
Codex-managed setup.

## Tool Exposure Versus Guard Discovery

Fresh or already-open Codex threads can expose the native tool namespace lazily,
and after app/plugin updates the active thread UI may show only part of the
native tool schema. Do not downgrade the public parity target from that partial
current-thread rendering alone. The authoritative local check is the guard's
Codex-context `tools/list` discovery plus fresh MCP smoke evidence. The current
expected MCP surface remains `list_apps`, `get_app_state`, `click`,
`perform_secondary_action`, `set_value`, `select_text`, `scroll`, `drag`,
`press_key`, and `type_text`.

If `tools/list` shows those names but omits expected input-schema entries,
treat that as native discovery failure. Search/address field work must stay on
native `set_value` or `type_text` only when the original native tool contract is
present; an operator fallback does not repair or prove the native surface.
During full `ensure`, local discovery failure from a missing tool or broken
input schema causes one forced rebuild of the local Computer Use cache,
marketplace plugin copy, runtime copy, compatibility patch, and LaunchServices
registration from the installed Codex bundle, then a second `tools/list` probe.
This repairs local corruption and stale materialization. It deliberately cannot
invent MCP tools or arguments that the bundled OpenAI plugin no longer
publishes.

## Google Chrome Native Use

Chrome is a supported native Computer Use target when the app is allowed by
Codex and macOS permissions are in place. The guard includes a separate
Chrome-specific smoke for tasks that depend on the user's normal Google Chrome
app/profile. That smoke opens a temporary Chrome tab, uses native
`get_app_state`, `press_key`, and `set_value` against `com.google.Chrome`, then
verifies the token through fresh native app state. It does not use Browser Use,
Playwright, AppleScript, Accessibility scripting, screenshots, or coordinate
fallbacks.

Current live validation on Codex 26.519.31651 with Computer Use plugin 1.0.799
showed that `type_text` can fail against Chrome's address/search field with
`Missing required argument: text` even when the native tool-call arguments
include `text`. For that specific settable Chrome field, native parity is better
served by `set_value`, because it remains inside the official Computer Use MCP
surface and is verifiable in `get_app_state`.

## Codex Chrome Extension Boundary

OpenAI now documents a separate Codex Chrome Extension path for browser work
that needs the user's signed-in Chrome state. That path is not the same as
native Computer Use and it is not the in-app Browser plugin:

- local development servers, file-backed previews, and public pages that do not
  require sign-in should use the in-app browser first;
- signed-in websites, existing Chrome tabs, browser extensions, cookies, and
  Chrome-profile state should use the official `chrome@openai-bundled` plugin
  and Codex Chrome Extension;
- desktop GUI tasks outside browser-page automation should continue to use
  native Computer Use when the target app is allowed.

The guard reports this extension route separately as `chrome_plugin` and through
`codex-computer-use-guard chrome-plugin-status`. It keeps the bundled Chrome
plugin discoverable and enabled in Codex config and checks the official plugin
helper scripts for the native host manifest and active-profile extension
install. The primary install route is OpenAI's Codex Plugins setup flow. If that
flow fails to materialize Chrome's extension/native-host state, the explicit
`codex-computer-use-guard chrome-extension-force-install --yes` fallback can
write the per-user native host manifest and Chrome `ExtensionInstallForcelist`
policy from the bundled Chrome plugin metadata. It also writes Chrome's
documented per-user `External Extensions/<extension-id>.json` Web Store update
file for Macs where user-default force-install policy alone is not enough. That
fallback is never hidden inside native Computer Use health and is not part of
normal `ensure`, because it changes Chrome extension installation state.

The guard also keeps the bundled in-app Browser plugin route
`browser@openai-bundled` enabled, removes stale disabled-tool entries for the
legacy `browser-use@openai-bundled` id, caches the official Browser plugin
copy, and reports this route separately as `browser_plugin` through
`codex-computer-use-guard browser-plugin-status`. Browser plugin health is not
native Computer Use health and must not be used as fallback evidence for
`ok=true`.

The smoke does not claim arbitrary control of minimized windows, off-Space
windows, invisible windows, Terminal, Codex itself, administrator prompts, or
security/privacy dialogs. If OpenAI expands the Codex app MCP surface or
documents additional native behavior, the expected tool list, smoke, docs, and
audits should be updated together.

## Dialog Operator Boundary

`codex-dialog-autopilot` is a separate operator convenience layer for narrow,
routine local helper prompts. It is not native Computer Use and must never be
used as evidence for `ok=true`.

It may click only allowlisted routine prompts after both the helper process and
visible dialog text match the safe allowlist. Denylisted text wins before any
click. Denylisted classes include privacy, security, TCC, Screen Recording,
Accessibility, App Data, administrator credentials, Keychain,
account/cloud/payment dialogs, and their German equivalents. Unattended
`Always Allow` remains disabled for this routine path.

Little Snitch and similar firewall or identity-verification prompts are not
native Computer Use capabilities and must not be used as native health
evidence. This repository does include a separate restricted operator path for
Foundation/Codex repair network prompts after the user has granted local
Automation/Accessibility access. That path may click `Always Allow` only when
the dialog owner is Little Snitch and the visible text matches Foundation/Codex
repair identifiers such as Codex Computer Use, SkyComputerUse,
CodexComputerUseGuard, `codex-computer-use`, `com.openai.codex`,
`chatgpt.com`, `openai.com`, localhost, or 127.0.0.1. Generic firewall,
account, payment, privacy, TCC, administrator, password, Keychain, cloud, and
security prompts remain operator decisions.
