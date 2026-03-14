# TDPilot — TouchDesigner AI Assistant Plugin

TDPilot v1.2 provides 63 MCP tools for live control of TouchDesigner projects from Claude. This plugin makes TDPilot's skills and MCP server configuration permanently available across all Cowork sessions.

## Components

### MCP Server
- **touchdesigner** — Connects to TDPilot MCP server via `npx tdpilot` (stdio transport)

### Skills
- **tdpilot-core** — Core patching discipline: 63-tool reference, node layout, color coding, expressions, error verification, visual checks, technique memory, v1.1 features (custom parameters, project lifecycle, POP inspection)
- **tdpilot-production** — Production-safe workflow: staged edits, undo blocks, snapshots, completion gates, failure protocol
- **popx-touchdesigner** — POPX operator knowledge base: 59 GPU-accelerated operators (generators, falloffs, modifiers, tools, simulations), 54 shipped examples with working values, full reference corpus, and search tools for building POPX-based particle/instance setups

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
1. Open your TD project
2. Import `td_component/tdpilot_v1_2.tox` (bundled in this plugin) into your project
3. The MCP server starts automatically on the configured ports

The TOX file is included in this plugin under `td_component/tdpilot_v1_2.tox`.

## Usage

Once installed, TDPilot skills activate automatically whenever you mention TouchDesigner, TD, TOPs, CHOPs, SOPs, or any TD-related topic. Use `/td-check` for quick health checks and `/td-snapshot` before major changes.

## v1.1 Features
- `td_custom_parameters` — Declarative custom parameter pages on COMPs
- `td_project_lifecycle` — Save/load/undo/redo/undo-blocks
- `td_pop_inspect` — POP-native data inspection and attribute sampling
- Structured JSON results from `td_exec_python`
