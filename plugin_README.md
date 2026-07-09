# TDPilot — TouchDesigner AI Assistant Plugin

TDPilot v2.1.0 provides 114 MCP tools for live control of TouchDesigner projects from Claude, Codex, and other MCP clients. The headline is the vNext visual programming brain: `td_brain_plan` grounds intent in real TD operators, hints, docs, memory, live state, and a 656-card reviewed operator atlas with zero-concept backlog; `td_brain_execute` mutates only from a valid BrainPlan; `td_transaction_apply` adds transactional rollback and validation to typed patch plans; `td_cockpit_render` exposes an optional read-only cockpit UI for plan, validation, rollback, and trace summaries; `td_sync_status` reports server/live-component/package drift in one call; and `td_sync_diagnose` gives strict live endpoint/version/auth fingerprint diagnostics.

The 1.6 observability layer remains: `_read_journal` hints, a 200-entry `activity_log` ring buffer mirrored into `/local/mcp_server/activity_log`, and `td_self_update` for syncing the `.tox` across repo, plugin cache, and `~/.tdpilot/`.

## Components

### MCP Server
- **touchdesigner** — Connects to TDPilot MCP server via `npx tdpilot` (stdio transport)

### Skills
- **tdpilot-core** — Core patching discipline: 114-tool reference, node layout, color coding, expressions, error verification, visual checks, technique memory, knowledge corpus, custom parameters, project lifecycle, POP inspection, agent activity log, self-update, sync diagnostics, and the brain transaction loop
- **tdpilot-production** — Production-safe workflow: staged edits, undo blocks, snapshots, completion gates, failure protocol
- **tdpilot-brain-explorer / builder / validator / recovery / release** — Specialized v2 brain skills for inspect-before-mutate work, BrainPlan construction, validation, recovery, and release auditing
- **popx-touchdesigner** — POPX workflow skill for 59 GPU-accelerated operators. References must be built locally from your own licensed POPx copy (see `references/BUILD.md`)

### Packaged Add-ons
- **Reviewed operator atlas** — 656 structured operator cards across CHOP, COMP, DAT, MAT, POP, SOP, and TOP. The zero-concept backlog is closed, so agents can use Official Derivative docs, reviewed `key_concepts`, `key_params`, and gotchas to move from concept-to-node instead of guessing.
- **Concept-to-node eval gate** — A 50+ case concept-to-node golden eval corpus is checked by `scripts/eval_brain_golden.py`, covering compiler-backed patterns, assembly macros, generated-code diagnostics, device-source prompts, and stable/debug output conventions.
- **Brain skills and agents** — Codex and Claude Code get the same explorer, builder, validator, recovery, and release workflows, with deterministic local hooks.
- **Local knowledge packs** — The core atlas ships with TDPilot. Optional packs such as POPX remain local add-ons and must be built from user-owned licensed documentation.

### Commands
- **/td-check** — Run a comprehensive health check on the current TD project
- **/td-snapshot** — Create a safety snapshot of the current scene

## Setup

### Prerequisites
- TouchDesigner running with TDPilot MCP component loaded
- Node.js installed (for `npx tdpilot`)

### Environment
The MCP server connects to TouchDesigner via HTTP/WebSocket:
- `TD_MCP_HOST` — default `127.0.0.1`
- `TD_MCP_PORT` — default `9981`
- `TD_MCP_WS_PORT` — default `9982`

### Loading TDPilot in TouchDesigner

**Recommended (persistent across projects):**
1. Open TouchDesigner
2. Drag-and-drop `td_component/tdpilot.tox` into the `/local` container
3. The MCP server starts automatically and persists across project opens

**Alternative (setup script):**
```python
# In TD Textport — auto-installs into /local
exec(open("/path/to/TDPilot/setup_mcp_in_td.py").read(), globals(), globals())
```

**Per-project install:**
Import `td_component/tdpilot.tox` directly into your project root.

The TOX file is included in this plugin under `td_component/tdpilot.tox`.

## Usage

Once installed, TDPilot skills activate automatically whenever you mention TouchDesigner, TD, TOPs, CHOPs, SOPs, or any TD-related topic. Use `/td-check` for quick health checks and `/td-snapshot` before major changes.

For abstract prompts, ask the agent to use the reviewed atlas and Official Derivative docs to turn the idea concept-to-node, then run `td_brain_plan` before any mutation.

## v1.1 Features
- `td_custom_parameters` — Declarative custom parameter pages on COMPs
- `td_project_lifecycle` — Save/load/undo/redo/undo-blocks
- `td_pop_inspect` — POP-native data inspection and attribute sampling
- Structured JSON results from `td_exec_python`
