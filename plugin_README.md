# TDPilot — TouchDesigner AI Assistant Plugin

TDPilot v2.4.0 provides 114 MCP tools for live control of TouchDesigner projects from Claude, Codex, and other MCP clients. Its practical-intelligence brain uses two truthful routes: `td_brain_plan` compiles exact validated patterns, while artistic, multi-domain, spatial, and implicit architecture goes through `td_brain_ground` → host authoring → `td_brain_propose`. Only accepted BrainPlans with complete intent coverage execute through `td_brain_execute`; `td_transaction_apply` provides transactional rollback and validation for typed patch plans. Grounding stays local and uses live state, memory, official evidence, and the 656-card reviewed operator atlas with zero-concept backlog.

The 1.6 observability layer remains: `_read_journal` hints, a 200-entry `activity_log` ring buffer mirrored into `/local/mcp_server/activity_log`, and `td_self_update` for syncing the `.tox` across repo, plugin cache, and `~/.tdpilot/`.

## Components

### MCP Server
- **touchdesigner** — Connects to TDPilot MCP server via `npx tdpilot` (stdio transport)

### Skills
- **tdpilot-core** — Compact intent router for the 114-tool reference surface: targeted inspection, typed edits, brain-route selection, checkpoint validation, visual proof, rollback, and local memory
- **tdpilot-production** — Production-safe workflow: staged edits, undo blocks, snapshots, completion gates, failure protocol
- **tdpilot-brain-explorer / builder / validator / recovery** — Public brain skills for read-only discovery, pattern or concept routing, request-specific validation, and recovery
- **popx-touchdesigner** — POPX workflow skill for 59 GPU-accelerated operators. References must be built locally from your own licensed POPx copy (see `references/BUILD.md`)

### Packaged Add-ons
- **Reviewed operator atlas** — 656 structured operator cards across CHOP, COMP, DAT, MAT, POP, SOP, and TOP. The zero-concept backlog is closed, so agents can use Official Derivative docs, reviewed `key_concepts`, `key_params`, and gotchas to move from concept-to-node instead of guessing.
- **Concept-to-node eval gate** — A 50+ case concept-to-node golden eval corpus is checked by `scripts/eval_brain_golden.py`, covering compiler-backed patterns, assembly macros, generated-code diagnostics, device-source prompts, and stable/debug output conventions.
- **Brain skills and agents** — Codex and Claude Code get the same public explorer, builder, validator, and recovery workflows, with deterministic local transaction hooks.
- **Local knowledge packs** — The core atlas ships with TDPilot. Optional packs such as POPX remain local add-ons and must be built from user-owned licensed documentation.

### Commands
- **/td-concept** — Ground, author, review, execute, and validate an artistic or multi-domain concept
- **/td-first-wow** — Build and prove a seeded moving feedback visual
- **/td-audio-reactive** — Build and prove a real audio-to-visual binding
- **/td-explain-patch** — Explain the current network without mutating it
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

Once installed, TDPilot skills activate automatically whenever you mention TouchDesigner, TD, TOPs, CHOPs, SOPs, or any TD-related topic. Use `/td-concept <idea>` for creative builds, `/td-check` for quick health checks, and `/td-snapshot` before risky direct edits.

Exact validated patterns use `td_brain_plan`. Abstract, artistic, multi-domain, spatial, camera/depth/fog, or implicit architecture uses the reviewed atlas and Official Derivative evidence through `td_brain_ground` → author → `td_brain_propose`. In either route, execute only complete accepted plans and validate the actual result.

## v1.1 Features
- `td_custom_parameters` — Declarative custom parameter pages on COMPs
- `td_project_lifecycle` — Save/load/undo/redo/undo-blocks
- `td_pop_inspect` — POP-native data inspection and attribute sampling
- Structured JSON results from `td_exec_python`
