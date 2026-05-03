# TDPilot — TouchDesigner AI Assistant Plugin

TDPilot v1.6.5 provides 103 MCP tools for live control of TouchDesigner projects from Claude (plus the v1.6.1 expanded hint corpus — 19 packs / 63 hints — with v1.6.2 surface routing for response-context-aware hints), plus a one-button-install panel inside the `.tox` itself (drag-drop into TD, click "Bootstrap All", done). v1.6.5 fixes the "panel still says 1.5.3 after restart" class of bug: the TD-startup script now sweeps both `/local` AND `/project1` for stale tdpilot/mcp_server COMPs (regardless of which name they're saved under) and reloads the fresh .tox into the same parent the previous COMP lived at, preserving the user's UI position. Also adds a CI gate locking `API_VERSION` to `__version__` so a missing Edit during a release can never silently ship.

## Components

### MCP Server
- **touchdesigner** — Connects to TDPilot MCP server via `npx tdpilot` (stdio transport)

### Skills
- **tdpilot-core** — Core patching discipline: 103-tool reference, node layout, color coding, expressions, error verification, visual checks, technique memory, knowledge corpus, v1.1 features (custom parameters, project lifecycle, POP inspection)
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
