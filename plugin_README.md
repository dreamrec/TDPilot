# TDPilot — TouchDesigner AI Assistant Plugin

TDPilot v2.0.0 provides 110 MCP tools for live control of TouchDesigner projects from Claude, Codex, and other MCP clients. The headline is the vNext visual programming brain: `td_brain_plan` grounds intent in real TD operators, hints, docs, memory, and live state; `td_brain_execute` mutates only from a valid BrainPlan; `td_transaction_apply` adds transactional rollback and validation to typed patch plans; and `td_cockpit_render` exposes an optional read-only cockpit UI for plan, validation, rollback, and trace summaries.

The 1.6 observability layer remains: `_read_journal` hints, a 200-entry `activity_log` ring buffer mirrored into `/local/mcp_server/activity_log`, and `td_self_update` for syncing the `.tox` across repo, plugin cache, and `~/.tdpilot/`.

## Components

### MCP Server
- **touchdesigner** — Connects to TDPilot MCP server via `npx tdpilot` (stdio transport)

### Skills
- **tdpilot-core** — Core patching discipline: 110-tool reference, node layout, color coding, expressions, error verification, visual checks, technique memory, knowledge corpus, custom parameters, project lifecycle, POP inspection, agent activity log, self-update, and the brain transaction loop
- **tdpilot-production** — Production-safe workflow: staged edits, undo blocks, snapshots, completion gates, failure protocol
- **tdpilot-brain-explorer / builder / validator / recovery / release** — Specialized v2 brain skills for inspect-before-mutate work, BrainPlan construction, validation, recovery, and release auditing
- **popx-touchdesigner** — POPX workflow skill for 59 GPU-accelerated operators. References must be built locally from your own licensed POPx copy (see `references/BUILD.md`)

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

## v1.1 Features
- `td_custom_parameters` — Declarative custom parameter pages on COMPs
- `td_project_lifecycle` — Save/load/undo/redo/undo-blocks
- `td_pop_inspect` — POP-native data inspection and attribute sampling
- Structured JSON results from `td_exec_python`
