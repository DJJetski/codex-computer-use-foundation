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
    "failure_class": "",
    "appserver_rendezvous": true,
    "operational": true,
    "second_mouse_verified": true,
    "fallback_used": false,
    "list_apps_completed": 2,
    "get_app_state_completed": 4,
    "click_completed": 2,
    "safari_click_received": true,
    "safari_type_received": true,
    "safari_input_verified": true,
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
  `ensure` cleans old duplicate native MCP clients before and after native
  smoke refresh and only then reports operational health.
- `codex-dialog-autopilot` is installed from this repo, its LaunchAgent is
  loaded, and its latest daemon health was `ok=true`.

`/Applications/Codex.app/Contents/Resources/codex mcp get computer-use` must
show:

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
- Canonical skill: `$HOME/.codex/skills/macos-computer-use/SKILL.md`
- Guard state: `$HOME/.codex/state/computer-use-guard/`
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
  `computer-use list_apps get_app_state click type_text press_key`.
- If `tool_search` exposes the namespace, prove native health with
  `mcp__computer_use__.list_apps`.
- If tools remain absent after `tool_search`, run
  `$HOME/.codex/bin/codex-computer-use-guard ensure`; if they still remain
  absent in that thread, report a native exposure blocker and use a fresh
  thread.
- No AppleScript, Accessibility scripting, screenshots, `cliclick`, Keyboard
  Maestro, Playwright, or VPN may be hidden inside the Computer Use MCP path.
- `codex-dialog-autopilot` is a separate routine-dialog operator layer. It may
  keep narrowly matched helper/AppData/browser/firewall prompts from blocking
  first-use flows, but it is not native Computer Use and is not evidence for
  `ok=true`. Strong button clicks require both an allowlisted helper process
  and allowlisted dialog text.
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
