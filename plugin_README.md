# TDPilot — TouchDesigner AI Assistant Plugin

TDPilot v1.6.11 provides 104 MCP tools for live control of TouchDesigner projects from Claude (plus a 20-pack / 73-hint corpus — expanded in v1.6.1 and again in v1.6.11 with error_recovery hints — with v1.6.2 surface routing for response-context-aware hints), plus a one-button-install panel inside the `.tox` itself (drag-drop into TD, click "Bootstrap All", done). v1.6.10 closes the auto-update gap that v1.6.6 left open: the v1.6.6 `_save_toe_with_externaltox` mechanism only protected the canonical `~/.tdpilot/tdpilot_default.toe` autoload — user-created `.toe` files in arbitrary locations had a frozen embedded COMP body that wouldn't auto-update. v1.6.10 adds a "Pin this project to disk .tox" pulse + a Body status row in the panel that detects frozen-body state. Click once on any open project → externaltox attached → save with `saveExternalToxs=False` → reopen .toe → fresh content. From that point on, `npx tdpilot@latest` + TD relaunch = automatic update for that project, just like the canonical autoload.

## Components

### MCP Server
- **touchdesigner** — Connects to TDPilot MCP server via `npx tdpilot` (stdio transport)

### Skills
- **tdpilot-core** — Core patching discipline: 104-tool reference, node layout, color coding, expressions, error verification, visual checks, technique memory, knowledge corpus, v1.1 features (custom parameters, project lifecycle, POP inspection)
- **tdpilot-production** — Production-safe workflow: staged edits, undo blocks, snapshots, completion gates, failure protocol
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
