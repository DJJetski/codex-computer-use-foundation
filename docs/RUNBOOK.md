# Runbook

Use this when Codex is installed but native Computer Use is missing, not exposed
in a fresh thread, timing out, or suspect after Codex/app/plugin/macOS changes.
The runbook repairs and validates the native path; it does not switch to
fallback automation as the solution.

If you need the non-operator explanation first, read
`docs/WHAT-IS-COMPUTER-USE.md`.
If you need to compare this package with OpenAI's documented Computer Use
capabilities, read `docs/CAPABILITY-PARITY.md`.

## Normal Fresh-Thread Procedure

1. Load the canonical Computer Use skill:
   `~/.codex/skills/macos-computer-use/SKILL.md`
2. If `mcp__computer_use__` is not visible, call `tool_search` for:

   ```text
   computer-use list_apps get_app_state click perform_secondary_action set_value select_text scroll drag press_key type_text
   ```

3. If the namespace appears, immediately prove native operation:

   ```text
   mcp__computer_use__.list_apps
   ```

4. Continue only if that native call succeeds. If it returns
   `Transport closed`, the current thread has stale MCP transport state; run
   full `ensure` if needed, then retry from a fresh Codex thread.
5. If the current thread exposes only part of the tool schema after
   `tool_search`, run the guard status or verifier before changing the parity
   target. The guard's Codex-context `tools/list` check is the authoritative
   local discovery proof for the full native surface.
6. Continue only with native `mcp__computer_use__` tools for native-only tasks.
7. Do not switch to `cliclick`, screenshots, AppleScript, Accessibility,
   Keyboard Maestro, or browser automation unless the user explicitly chooses a
   fallback operator path.

## Quick Health

```bash
~/.codex/bin/codex-computer-use-guard status | jq '{ok, structural_ok, health_layers, native_smoke: .native_smoke | {ok,fresh,age_seconds,failure_class,fallback_used}}'
```

Expected:

- `ok=true`
- `structural_ok=true`
- all health layers true
- native smoke fresh and fallback-free
- `mcp_tool_schema_contract.ok=true`, with no missing expected argument
  properties or schema-required fields for native `set_value`, `type_text`,
  `click`, `press_key`, `scroll`, `drag`, `select_text`,
  `perform_secondary_action`, or `get_app_state`

If `structural_ok=true` but `ok=false`, inspect `operational_state`. A state of
`structural_ok_needs_fresh_native_smoke` means the repair layer is present, but
the current machine still needs full `ensure`, `tool_search`, or a fresh Codex
thread before native operation is proven.

If the only failure is `failure_class=stale_native_smoke`, run full `ensure`.
That is the intended fail-closed refresh path.

If the full tool list is present but `mcp_tool_schema_contract.ok=false`, treat
the installed native surface as broken. Do not use Safari, Chrome, AppleScript,
or coordinate automation as evidence that native Computer Use works; repair the
native route and retry from a fresh Codex thread.

## Full Repair And Validation

```bash
~/.codex/bin/codex-computer-use-guard ensure
```

Use this when:

- native tools are absent after `tool_search`
- native calls time out
- current thread reports `Transport closed`
- `status` shows stale/missing/non-operational smoke
- plugin/cache/config was rewritten
- Codex was updated

Full `ensure` may run fresh native smoke if structural/runtime readiness exists.
It can also replace duplicate or stale native MCP clients, so an already-open
thread may keep a closed transport even after the installed route is healthy.
When that happens, use a fresh Codex thread as the canonical post-repair proof.

## Fast Startup Repair

```bash
~/.codex/bin/codex-computer-use-guard ensure-config --quiet
```

Use this only for structural repair. It is intentionally fast and does not prove
native operation by itself.

## Authoritative Smoke

```bash
~/.codex/bin/codex-computer-use-guard fresh-smoke | jq '{ok,fresh,appserver_rendezvous,operational,second_mouse_verified,failure_class,fallback_used,smoke_target,target_not_frontmost_verified,list_apps_completed,get_app_state_completed,click_completed,coordinate_click_attempts,calculator_click_verified,calculator_display_verified,cleanup_keypress_ok,smoke_cleanup,unstructured_stdout_lines}'
```

Expected:

- `ok=true`
- `appserver_rendezvous=true`
- `operational=true`
- `second_mouse_verified=true`
- `fallback_used=false`
- `smoke_target=com.apple.calculator`
- `target_not_frontmost_verified=true` when macOS honors the focus-restore step
- `coordinate_click_attempts=0`
- `calculator_click_verified=true`
- `calculator_display_verified=true`
- `cleanup_keypress_ok=true`
- `smoke_cleanup.errors=[]`
- `unstructured_stdout_lines=0`

The cleanup step is intentionally best-effort. A passing smoke proves native
interaction through structured MCP evidence and attempts to close the temporary
Calculator surface, but it does not fail merely because the final assistant text
does not say that the app quit.

## Native Chrome Smoke

Use this when the task specifically depends on the user's normal Google Chrome
app/profile:

```bash
~/.codex/bin/codex-computer-use-guard chrome-smoke | jq '{ok,fresh,failure_class,fallback_used,smoke_target,list_apps_completed,get_app_state_completed,set_value_completed,press_key_completed,chrome_seen,chrome_set_value_verified,success_marker,unstructured_stdout_lines}'
```

Expected:

- `ok=true`
- `fallback_used=false`
- `smoke_target=com.google.Chrome`
- `chrome_seen=true`
- `chrome_set_value_verified=true`
- `set_value_completed>=1`
- `press_key_completed>=2`
- `success_marker=true`
- `unstructured_stdout_lines=0`

The Chrome smoke uses native `set_value` for Chrome's settable address/search
field. Current Computer Use plugin 1.0.799 can reject `type_text` on that field
with `Missing required argument: text` even when the argument is present; that
does not justify a fallback browser automation path.

## Chrome Extension Plugin Status

Use this when a task needs the official Codex Chrome Extension path for a
signed-in Chrome profile:

```bash
~/.codex/bin/codex-computer-use-guard chrome-plugin-status | jq '{ok,plugin_enabled,disabled,marketplace_ok,extension_id,native_host:{ok,exit_code,error},extension:{ok,exit_code,installed,enabled,selectedProfileDirectory,error},chrome_running:{ok,running},next_step}'
```

Expected for extension-backed Chrome use:

- `ok=true`
- `plugin_enabled=true`
- `disabled=false`
- `marketplace_ok=true`
- `native_host.ok=true`
- `extension.ok=true`

This diagnostic follows the official Chrome plugin boundary. It may enable the
Codex Chrome plugin in config through `ensure-config`. The primary install path
is OpenAI's documented Codex Plugins setup flow:
<https://developers.openai.com/codex/app/chrome-extension>.

The normal guard repair paths keep the local native host manifest,
`ExtensionInstallForcelist`, and per-user `External Extensions` file present
once the bundled Chrome plugin cache is healthy:

```bash
~/.codex/bin/codex-computer-use-guard ensure-config | jq '{structural_ok,chrome_plugin:{ok,native_host:{ok,error},force_install_policy,external_extension,auto_repair}}'
~/.codex/bin/codex-computer-use-guard ensure | jq '{ok,chrome_plugin:{ok,native_host:{ok,error},force_install_policy,external_extension,auto_repair}}'
```

If that flow still leaves the native host or active-profile extension missing,
use the explicit force-install fallback:

```bash
~/.codex/bin/codex-computer-use-guard chrome-extension-force-install --yes | jq '{ok,changed,manifest_install:{ok,manifest_path,host_config_path,error},policy_after,external_after,next_step}'
```

The fallback writes the per-user Chrome native-messaging host manifest for the
bundled Codex Chrome plugin, adds the Codex Chrome Extension to Chrome's
`ExtensionInstallForcelist` policy, and writes Chrome's documented per-user
`External Extensions/<extension-id>.json` Web Store update file. After it
succeeds, restart Chrome, confirm the extension shows Connected, and then start
a fresh Codex thread.

## Preflight For A Planned GUI Task

```bash
~/.codex/bin/codex-computer-use-preflight status | jq '{ok, structural_ok, runtime_probe_ok, service_runtime_ok, health_layers, native_smoke: .native_smoke | {ok,fresh,failure_class,fallback_used}}'
```

## MCP Routing Check

```bash
CODEX_APP="$(cat "$HOME/.codex/state/computer-use-guard/codex-app-path" 2>/dev/null || printf '/Applications/Codex.app')"
"$CODEX_APP/Contents/Resources/codex" mcp get computer-use
```

Expected command:

```text
~/.codex/bin/codex-computer-use-native-launcher
```

## LaunchAgent Check

```bash
plutil -lint ~/Library/LaunchAgents/io.github.codex-computer-use-foundation.guard.plist
launchctl print gui/$(id -u)/io.github.codex-computer-use-foundation.guard
plutil -lint ~/Library/LaunchAgents/io.github.codex-computer-use-foundation.dialog-autopilot.plist
launchctl print gui/$(id -u)/io.github.codex-computer-use-foundation.dialog-autopilot
```

Expected:

- plist is valid
- launchd job exists
- recent exits are successful

If the LaunchAgent plist or bootstrap files were deleted, reinstall the
foundation runtime from the repo checkout or downloaded package:

```bash
scripts/install.py --yes --full-ensure
```

On success, that recreates the LaunchAgent, bootstrap backups, marketplace
mirror, plugin shim, and fresh native smoke evidence. `ensure-config` can
restore structural files, but structural repair alone is not native success;
full success still requires a fresh native smoke run with `fallback_used=false`.

## Native MCP Process Cleanup

After closing old Codex threads or subagents, stale native MCP clients can be
checked without touching live duplicate transports:

```bash
~/.codex/bin/codex-computer-use-guard cleanup-mcp-clients | jq '{cleanup, after}'
```

Full `~/.codex/bin/codex-computer-use-guard ensure` runs the same duplicate
native MCP cleanup after native smoke: it keeps the newest client per Codex
AppServer parent and removes older duplicate transports so the next fresh
thread starts from a single native MCP owner.

If you want to do only that cleanup without running the full repair path, use
the explicit operator flag:

```bash
~/.codex/bin/codex-computer-use-guard cleanup-mcp-clients --force-duplicates | jq '{cleanup, after}'
```

Do not run the forced variant while another active thread is in the middle of a
native Computer Use task. `status` remains read-only. `ok=true` requires
`mcp_client_ownership.ok=true`; duplicate `SkyComputerUseClient mcp` groups are
treated as a real operational blocker, not a cosmetic diagnostic.

## Background Use And Second Pointer Expectations

Healthy native Computer Use can target an allowed app without relying on the
frontmost app. The release smoke attempts to prove this by opening Calculator
with `open -g`, returning focus to Codex, targeting Calculator by bundle id,
and requiring native click and type evidence with `fallback_used=false`. The
payload records `target_not_frontmost_verified` so this distinction is visible
instead of assumed.

Do not treat that proof as permission to use fallback automation, and do not
overread it as a guarantee for minimized windows, invisible windows, off-Space
windows, Terminal, Codex itself, administrator prompts, or
security/privacy/network/firewall dialogs. Those remain outside the unattended
native health contract. The separate dialog autopilot may still handle narrowly
matched Foundation/Codex Little Snitch prompts for this repair system after the
user has granted local Automation/Accessibility access; that is operator
plumbing, not native Computer Use evidence.

## Locked Computer Use

OpenAI's Codex app has a separate locked computer use mode for active trusted
Computer Use turns after the Mac locks. Treat that as Codex-managed product
setup, not Foundation repair work. This repo must not install, modify, or
validate the locked-use authorization plug-in. If a user needs locked use, first
verify ordinary native Computer Use with `ensure` or `fresh-smoke`, then enable
locked use from Codex settings and follow OpenAI's prompts.

## Backup Check

```bash
cmp -s ~/.codex/bin/codex-computer-use-guard "$HOME/Library/Application Support/CodexComputerUseGuard/codex-computer-use-guard.backup" && echo guard_backup_in_sync
cmp -s ~/.codex/bin/codex-dialog-autopilot "$HOME/Library/Application Support/CodexComputerUseGuard/codex-dialog-autopilot.backup" && echo dialog_autopilot_backup_in_sync
```

Expected:

```text
guard_backup_in_sync
dialog_autopilot_backup_in_sync
```

## Crash Check

```bash
find ~/Library/Logs/DiagnosticReports ~/Library/Logs/CrashReporter -name 'SkyComputerUse*' -mmin -10 -print
```

Expected:

- no output after a healthy run

Older crash reports can exist from previous dyld/runtime failures. Only fresh
crashes matter for current health.

## If A New Thread Says Tools Are Missing

1. Do not use fallback automation.
2. Call `tool_search` for the native Computer Use terms.
3. If exposed, call native `list_apps`.
4. If only a partial tool schema appears, compare against guard
   `tools/list`/verifier output before treating parity as changed.
5. If still absent, run full `ensure`.
6. If still absent in the same thread but guard is green, open a fresh thread or
   restart Codex. Current-thread tool metadata may have loaded before repair.

## If Guard Says `structural_ok=true` But `ok=false`

Inspect native smoke:

```bash
~/.codex/bin/codex-computer-use-guard status | jq '.native_smoke'
```

Common classes:

- `no_native_smoke_record`: run full `ensure` or `fresh-smoke`.
- `stale_native_smoke`: run full `ensure`; it should refresh.
- `native_smoke_timeout`: inspect process/log state, then run full `ensure`.
- `native_fallback_used`: reject the run; repeat native-only smoke.
- `native_smoke_no_structured_events`: parser/event format issue or non-JSON
  output pollution.

## If Native Calls Hang

1. Do not add direct MCP aliases.
2. Do not run standalone terminal `tools/call list_apps` as authoritative
   proof.
3. Run:

   ```bash
   ~/.codex/bin/codex-computer-use-guard ensure
   ```

4. Check recent crash reports.
5. Check `mcp_client_ownership` in guard status for stale duplicate clients.
6. Prefer a fresh Codex thread after the guard is green.

## If A Target App Is Safety-Blocked

`list_apps` can succeed while a specific app is still refused by the native
Computer Use server. The known case is Terminal:

```text
Computer Use is not allowed to use the app 'com.apple.Terminal' for safety reasons.
```

That message means the native route is present, but the target app is blocked by
upstream native policy. It is not fixed by opening Terminal with AppleScript,
Accessibility scripting, `cliclick`, Keyboard Maestro, or another GUI fallback.
Those paths are not native Computer Use and must not satisfy a native-only task.

For repo-local shell or Git work, use Codex command execution directly. If
general native tools fail on safe apps too, run full `ensure`; if only Terminal
is refused, keep the native repair state separate from the Terminal target
policy boundary.

## Safe Destructive Drill Ideas

Only run these when intentionally testing self-healing:

- disable `computer-use@openai-bundled` in config and let LaunchAgent repair it
- remove a cached plugin copy and run full `ensure`
- temporarily move the main guard and confirm bootstrap restore

Do not run these during normal work. Always verify status and backup sync
afterward.
