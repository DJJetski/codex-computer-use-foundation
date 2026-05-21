# Operational State

This file defines the release health contract for a correctly installed native
Codex Computer Use repair runtime.

For the user-facing explanation of what Computer Use is and why this package
repairs the native path instead of replacing it with fallback automation, see
`docs/WHAT-IS-COMPUTER-USE.md`.

## Status

A compatible installation is considered operational only when the guard and
verifier report `ok=true` with fresh native smoke for the current Mac, current
user profile, and current Codex/macOS versions. This is current evidence, not a
permanent guarantee against future Codex, plugin, or macOS changes.

The important distinction is:

- `structural_ok=true` means routing, cache, marketplace, launcher, runtime, and
  config are repaired.
- `ok=true` means structural health, clean native MCP client ownership, and
  fresh authoritative native smoke from the Codex-context MCP path.
- `operational_state.state=structural_ok_needs_fresh_native_smoke` means the
  local repair layer is in place, but native operation still needs a full
  `ensure`, `tool_search`, or fresh Codex thread before it can be treated as
  current evidence.
- `operational_state.state=native_computer_use_ready` means the installed route
  has current native evidence. It does not prove that an already-open Codex
  thread kept a live MCP transport after repair; that thread still needs a
  successful `mcp__computer_use__.list_apps` call, or the user should open a
  fresh Codex thread.

The system must not report full success just because the config looks right.
Full success requires real native calls and no duplicate native MCP clients
under the same Codex AppServer parent.

Fresh smoke is deliberately time-limited. If `status` becomes `ok=false` with
`failure_class=stale_native_smoke`, the system is failing closed as designed.
Run full `$HOME/.codex/bin/codex-computer-use-guard ensure`; when runtime
readiness is healthy it refreshes the smoke and returns to `ok=true`.

## Release Health Contract

A release is healthy only after installing from the public release tree with
`scripts/install.py --yes --full-ensure` and then running
`scripts/verify-live-state.py --expect-installed-from-repo
--require-operational --json`. The guard status should have this shape:

```json
{
  "ok": true,
  "structural_ok": true,
  "health_layers": {
    "configured": true,
    "discoverable": true,
    "runtime_ready": true,
    "mcp_client_ownership": true,
    "appserver_rendezvous": true,
    "operational": true,
    "second_mouse_verified": true
  },
  "native_smoke": {
    "ok": true,
    "fresh": true,
    "age_fresh": true,
    "smoke_context_matches": true,
    "failure_class": "",
    "appserver_rendezvous": true,
    "operational": true,
    "second_mouse_verified": true,
    "fallback_used": false,
    "smoke_target": "com.apple.calculator",
    "target_frontmost_seen": true,
    "target_not_frontmost_verified": false,
    "list_apps_completed": 2,
    "get_app_state_completed": 2,
    "click_completed": 2,
    "coordinate_click_attempts": 0,
    "calculator_click_verified": true,
    "calculator_display_verified": true,
    "cleanup_keypress_ok": true,
    "smoke_cleanup": {
      "current_removed": true,
      "errors": []
    },
    "unstructured_stdout_lines": 0
  }
}
```

Expected high-level result:

- `scripts/verify-live-state.py --expect-installed-from-repo
  --require-operational --json` returned `ok=true`.
- Manifest-owned live files matched the repo source.
- Failed verifier checks: none.
- `mcp_client_ownership.ok=true` with no duplicate parent groups. Full
  `ensure` first cleans orphaned native MCP clients, then collapses duplicate
  native MCP client groups under the same Codex AppServer parent by keeping the
  newest client and removing older duplicate transports. Duplicate parent
  groups remain fail-closed evidence until `ensure`, explicit cleanup, or a
  thread restart removes them.
- Current live validation on Codex 26.519.22136 with Computer Use plugin
  1.0.799 reports the Calculator target as not frontmost during the native
  smoke, with `target_not_frontmost_verified=true`. The value is recorded as
  evidence, not assumed, because older plugin builds have reported different
  frontmost state during the same smoke flow.
- Native interaction health is decided from structured MCP evidence, not only
  from the final assistant success line. Calculator cleanup is still attempted
  with `press_key`, but closing the temporary Calculator window is best-effort;
  the required proof is native `list_apps`, `get_app_state`, element-index
  `click`, `type_text`, display verification, cleanup keypress completion, and
  `fallback_used=false`.
- Google Chrome can be validated separately with
  `$HOME/.codex/bin/codex-computer-use-guard chrome-smoke`. Current live
  validation on Codex 26.519.22136 with Computer Use plugin 1.0.799 uses native
  `get_app_state`, `press_key`, and `set_value` against `com.google.Chrome`
  and records the result in `chrome_smoke`. This Chrome smoke is additional
  target-app evidence; it is not a fallback and does not replace the generic
  Calculator health smoke.
- The official Codex Chrome Extension route is reported separately as
  `chrome_plugin` and can be checked with
  `$HOME/.codex/bin/codex-computer-use-guard chrome-plugin-status`. The guard
  keeps `chrome@openai-bundled` enabled and checks the bundled plugin helper
  scripts for the native host manifest and active-profile extension install,
  but it does not install the Chrome extension or native host outside the
  official Codex Plugins setup flow.
- `codex-dialog-autopilot` is installed from this repo, its LaunchAgent is
  loaded, and its latest daemon health was `ok=true`.

The persisted Codex app path must point at the OpenAI Codex bundle
(`com.openai.codex`). Its MCP routing must show:

```bash
CODEX_APP="$(cat "$HOME/.codex/state/computer-use-guard/codex-app-path" 2>/dev/null || printf '/Applications/Codex.app')"
"$CODEX_APP/Contents/Resources/codex" mcp get computer-use
```

```text
computer-use
  enabled: true
  transport: stdio
  command: $HOME/.codex/bin/codex-computer-use-native-launcher
  args: mcp
```

## Live Runtime Paths

- Guard: `$HOME/.codex/bin/codex-computer-use-guard`
- Native launcher: `$HOME/.codex/bin/codex-computer-use-native-launcher`
- Preflight helper: `$HOME/.codex/bin/codex-computer-use-preflight`
- Fresh smoke helper: `$HOME/.codex/bin/codex-computer-use-native-smoke`
- Notify wrapper: `$HOME/.codex/bin/codex-computer-use-notify`
- Dialog operator helper: `$HOME/.codex/bin/codex-dialog-autopilot`
- Chrome smoke state:
  `$HOME/.codex/state/computer-use-guard/last-chrome-smoke.json`
- Canonical skill: `$HOME/.codex/skills/macos-computer-use/SKILL.md`
- Guard state: `$HOME/.codex/state/computer-use-guard/`
- Persisted Codex app path:
  `$HOME/.codex/state/computer-use-guard/codex-app-path`
- LaunchAgent:
  `~/Library/LaunchAgents/io.github.codex-computer-use-foundation.guard.plist`
- Bootstrap/backup root:
  `~/Library/Application Support/CodexComputerUseGuard/`

## Critical Invariants

- Normal exposure is plugin-only. Do not add direct `computer-use` MCP aliases
  to `$HOME/.codex/config.toml`.
- The cached Computer Use plugin `.mcp.json` must route to
  `$HOME/.codex/bin/codex-computer-use-native-launcher`.
- The cached and mirrored Computer Use plugin must not publish a `skills/`
  entry; the only visible Computer Use skill is the canonical
  `$HOME/.codex/skills/macos-computer-use/SKILL.md` entry.
- The native launcher must `exec` the patched OpenAI `SkyComputerUseClient mcp`
  in the same process after fast guard repair. It must not spawn the native
  client as a detached child.
- Manifest-owned runtime files should be installed from this repo with
  `scripts/install.py`; avoid direct hand-edits in `$HOME/.codex`.
- `ensure-config` is structural. It repairs startup/config/cache state,
  bootstrap assets, and the guard LaunchAgent, but it does not prove native
  operation by itself.
- Full `ensure` may refresh stale or missing smoke when structural/runtime
  readiness exists.
- Fresh-thread absence of `mcp__computer_use__` is not automatically failure.
  First call `tool_search` for
  `computer-use list_apps get_app_state click perform_secondary_action set_value select_text scroll drag press_key type_text`.
- If `tool_search` exposes the namespace, prove native health with
  `mcp__computer_use__.list_apps`.
- If `mcp__computer_use__` is visible but native calls return
  `Transport closed`, treat the current thread as stale MCP transport state.
  Do not use fallbacks as proof; run full `ensure` if needed and retry from a
  fresh Codex thread.
- If tools remain absent after `tool_search`, run
  `$HOME/.codex/bin/codex-computer-use-guard ensure`; if they still remain
  absent in that thread, report a native exposure blocker and use a fresh
  thread.
- No AppleScript, Accessibility scripting, screenshots, `cliclick`, Keyboard
  Maestro, Playwright, or VPN may be hidden inside the Computer Use MCP path.
- Native app-level safety refusals are target policy boundaries, not structural
  repair failures. The known example is `com.apple.Terminal`: it may appear in
  `list_apps` while native `get_app_state`, click, or typing is refused for
  safety reasons. For repo-local shell/Git work, use Codex command execution
  directly; do not drive Terminal through AppleScript or another GUI fallback as
  a substitute for native Computer Use.
- `codex-dialog-autopilot` is a separate routine-dialog operator layer. It may
  keep narrowly matched helper/AppData/browser prompts from blocking first-use
  flows, but it is not native Computer Use and is not evidence for `ok=true`.
  Strong button clicks require both an allowlisted helper process and
  allowlisted dialog text. Generic firewall and network rule prompts remain
  explicit operator decisions. A separate restricted Foundation/Codex network
  path may handle matching Little Snitch prompts for this repair system after
  local Automation/Accessibility access exists; denylisted
  privacy/security/TCC/admin/password/account/payment/cloud text still wins,
  and routine prompts never get unattended `Always Allow`.
- VPN is separate. Do not connect VPN just to use Computer Use.
- Target OpenAI Codex as `/Applications/Codex.app` or `com.openai.codex`; never
  as plain `Codex` or `CODEX`.

## Why This Works

The runtime depends on several invariants being true at the same time:

1. Fresh threads must use `tool_search` before declaring Computer Use absent.
2. `ok=true` must require fresh native smoke, not just structural config.
3. Stale or missing smoke must be refreshed by full `ensure`.
4. `codex exec --json` parsing must accept new structured JSON event types.
5. `ensure-config` and full `ensure` must share the same file lock.
6. Direct MCP aliases must stay absent to avoid duplicate native clients.
7. The launcher must preserve the Codex AppServer rendezvous by using `exec`.
8. Backups, LaunchAgent, hooks, and bootstrapper must survive Codex rewrites and
   accidental deletion.
