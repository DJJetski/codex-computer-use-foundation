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
users should stay present for sensitive flows, and Computer Use cannot automate
terminal apps or Codex itself, authenticate as an administrator, or approve
security and privacy permission prompts on the computer.

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
this exact list. A missing tool fails discovery before the runtime can report
full health.

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

## Background And The Native Second Pointer

OpenAI describes background Computer Use as Codex seeing, clicking, and typing
with its own cursor while multiple agents work on a Mac without interfering
with the user's own work in other apps. This package verifies the same class of
native operation by requiring fresh native smoke evidence with
`fallback_used=false`.

The release smoke intentionally opens a local Safari test page with `open -g`,
targets Safari by bundle id, and proves native `click`, `type_text`, and
`press_key` behavior without relying on the frontmost app. That verifies
non-frontmost native action through the official route.

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
Accessibility, App Data, administrator credentials, Keychain, network/firewall
rules, Little Snitch, account/cloud/payment dialogs, and their German
equivalents. Unattended `Always Allow` remains disabled.

Little Snitch and similar firewall or identity-verification prompts are
operator decisions. A user or explicit task-specific operator action can choose
the narrow rule, but the public unattended autopilot must not disable or approve
those controls automatically.

