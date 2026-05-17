# Codex Computer Use Foundation

This repo is the source of truth for the installable native Codex Computer Use
repair system. It is for Macs where Codex is installed but native Computer Use
is missing, not exposed in fresh threads, timing out, or otherwise not working
through the official native path. The product runtime installs into the current
user's `$HOME/.codex` because Codex and the bundled Computer Use plugin expect
that layout.

Start here for new threads:

1. Read `README.md`, then `docs/CURRENT-STATE.md`.
2. Use `docs/RUNBOOK.md` for diagnostics and `docs/INSTALL.md` for clone
   installs.
3. Treat `src/` as source and `$HOME/.codex` as installed runtime. Do not
   hand-edit live files except for urgent diagnosis; put durable changes in
   this repo and reinstall.

Important invariants:

- Native Computer Use is plugin-only. Do not add direct
  `[mcp_servers.computer-use*]` aliases to `$HOME/.codex/config.toml`.
- The bundled Computer Use plugin must not publish a `skills/` entry. Keep
  MCP discovery in the plugin `.mcp.json`, and keep the canonical visible skill
  at `$HOME/.codex/skills/macos-computer-use/SKILL.md` so users see one
  Computer Use skill.
- The native launcher must `exec` the OpenAI `SkyComputerUseClient mcp` in the
  same process. Do not spawn it as a child process for normal MCP use.
- Do not hide AppleScript, Accessibility, `cliclick`, screenshots, Playwright,
  Keyboard Maestro, or VPN inside the Computer Use MCP path.
- `codex-dialog-autopilot` is a separate operator-dialog layer for narrow local
  allow/OK/helper/firewall prompts. It is not native Computer Use
  health and must not be used as a Computer Use fallback.
- Fresh native success requires authoritative Codex-context smoke, not just
  structural config.
- If a fresh thread does not show `mcp__computer_use__`, try `tool_search` for
  `computer-use list_apps get_app_state click type_text press_key` before
  declaring native tool exposure unavailable.

Verification before completion:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
scripts/install.py --dry-run
scripts/verify-live-state.py --expect-installed-from-repo --require-operational --json
scripts/secret-scan.py --include-untracked
scripts/public-release-audit.py --include-untracked --all-refs --enforce-public-surface
git status --short --branch --untracked-files=all
```

Commit only task-owned files. Push only when the user asked for GitHub-backed
cloneability or explicitly requested a push.
