# Runbook

Use this when Codex is installed but native Computer Use is missing, not exposed
in a fresh thread, timing out, or suspect after Codex/app/plugin/macOS changes.
The runbook repairs and validates the native path; it does not switch to
fallback automation as the solution.

If you need the non-operator explanation first, read
`docs/WHAT-IS-COMPUTER-USE.md`.

## Normal Fresh-Thread Procedure

1. Load the canonical Computer Use skill:
   `~/.codex/skills/macos-computer-use/SKILL.md`
2. If `mcp__computer_use__` is not visible, call `tool_search` for:

   ```text
   computer-use list_apps get_app_state click type_text press_key
   ```

3. If the namespace appears, immediately prove native operation:

   ```text
   mcp__computer_use__.list_apps
   ```

4. Continue only with native `mcp__computer_use__` tools for native-only tasks.
5. Do not switch to `cliclick`, screenshots, AppleScript, Accessibility,
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

If the only failure is `failure_class=stale_native_smoke`, run full `ensure`.
That is the intended fail-closed refresh path.

## Source Repo Verification

From the source repo:

```bash
cd codex-computer-use-foundation
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
scripts/install.py --dry-run
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
scripts/secret-scan.py --include-untracked
```

Use `scripts/install.py --yes --full-ensure` to reinstall manifest-owned live
files from the repo and prove the native path. Its rollback snapshot also
captures config, LaunchAgent, bootstrap backups, and Computer Use plugin
routing files that postinstall can mutate.

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

## Fast Startup Repair

```bash
~/.codex/bin/codex-computer-use-guard ensure-config --quiet
```

Use this only for structural repair. It is intentionally fast and does not prove
native operation by itself.

## Authoritative Smoke

```bash
~/.codex/bin/codex-computer-use-guard fresh-smoke | jq '{ok,fresh,appserver_rendezvous,operational,second_mouse_verified,failure_class,fallback_used,list_apps_completed,get_app_state_completed,click_completed,safari_click_received,safari_type_received,safari_input_verified,cleanup_keypress_ok,smoke_cleanup,unstructured_stdout_lines}'
```

Expected:

- `ok=true`
- `appserver_rendezvous=true`
- `operational=true`
- `second_mouse_verified=true`
- `fallback_used=false`
- `safari_input_verified=true`
- `cleanup_keypress_ok=true`
- `smoke_cleanup.errors=[]`
- `unstructured_stdout_lines=0`

## Preflight For A Planned GUI Task

```bash
~/.codex/bin/codex-computer-use-preflight status | jq '{ok, structural_ok, runtime_probe_ok, service_runtime_ok, health_layers, native_smoke: .native_smoke | {ok,fresh,failure_class,fallback_used}}'
```

## MCP Routing Check

```bash
/Applications/Codex.app/Contents/Resources/codex mcp get computer-use
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

## Native MCP Process Cleanup

After closing old Codex threads or subagents, stale native MCP clients can be
checked without touching live duplicate transports:

```bash
~/.codex/bin/codex-computer-use-guard cleanup-mcp-clients | jq '{cleanup, after}'
```

If old duplicate clients are still present under the same active Codex
AppServer and you intentionally want to close those old transports, use the
explicit operator flag:

```bash
~/.codex/bin/codex-computer-use-guard cleanup-mcp-clients --force-duplicates | jq '{cleanup, after}'
```

Do not run the forced variant while another active thread is in the middle of a
native Computer Use task.

Full `~/.codex/bin/codex-computer-use-guard ensure` now applies that duplicate
cleanup with a short grace window before reporting health. `status` remains
read-only. `ok=true` requires `mcp_client_ownership.ok=true`; duplicate
`SkyComputerUseClient mcp` groups are treated as a real operational blocker,
not a cosmetic diagnostic.

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
4. If still absent, run full `ensure`.
5. If still absent in the same thread but guard is green, open a fresh thread or
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

## Safe Destructive Drill Ideas

Only run these when intentionally testing self-healing:

- disable `computer-use@openai-bundled` in config and let LaunchAgent repair it
- remove a cached plugin copy and run full `ensure`
- temporarily move the main guard and confirm bootstrap restore

Do not run these during normal work. Always verify status and backup sync
afterward.
