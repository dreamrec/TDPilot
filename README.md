```
████████╗██████╗ ██████╗ ██╗██╗      ██████╗ ████████╗
╚══██╔══╝██╔══██╗██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
   ██║   ██║  ██║██████╔╝██║██║     ██║   ██║   ██║
   ██║   ██║  ██║██╔═══╝ ██║██║     ██║   ██║   ██║
   ██║   ██████╔╝██║     ██║███████╗╚██████╔╝   ██║
   ╚═╝   ╚═════╝ ╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝
```

# TDPilot Runtime v1.3.0

**TDPilot Runtime** is an MCP server for TouchDesigner.
It lets an AI agent inspect, build, wire, optimize, and stabilize live TD networks with real tool calls — and now remember what works.

`#tdpilot` `#touchdesigner` `#mcp` `#livepatch` `#audioreactive` `#realtime`

## Documentation

- Production manual: `docs/MANUAL.md`
- New surface guide: `docs/MCP_1_1_SURFACE.md`
- Release notes: `CHANGELOG.md`

## What This Is

- A practical control layer between AI agents and TouchDesigner.
- A structured toolset for scene edits, diagnostics, event monitoring, and recovery.
- A workflow-oriented MCP built for iterative patch development, not one-shot guessing.
- A technique memory system that learns from your projects and builds a reusable library.
- 71-tool runtime surface with knowledge corpus, job resources, memory, optimizer, safety, POPx inspection, project lifecycle control, and custom parameter authoring.

## What's New In 1.3

- **Knowledge corpus** — Structured JSON cards for 30 operators, 6 palette components, release notes. Query with `td_search_official_docs`, `td_get_operator_doc`, `td_get_param_help`, and more.
- **`standard` exec safety** — New middle-tier mode between `restricted` and `full`. Allows 14 safe data-transform imports (json, math, re, datetime, etc.) while blocking system access.
- **Expanded capabilities** — CapabilitySet now reports MCP Tasks support, transport type, SDK version, and TD build number.
- **Resource read-through** — Cached resources now attempt a live TD API call on cache miss instead of returning empty.
- **`td_describe_surface`** — Single tool to inspect the full MCP surface: tool count, resource count, capabilities, version.

## What's New In 1.1

- `td_pop_inspect` adds first-class POP metadata and attribute sampling instead of forcing POP debugging through SOP-shaped geometry reads.
- `td_project_lifecycle` adds save/load/undo/redo and undo-block control without falling back to ad hoc Python snippets.
- `td_custom_parameters` adds direct custom page/parameter authoring for COMPs.
- `td_exec_python` now returns structured result payloads when possible instead of forcing everything through `str(...)`.

## Core Thinking Model (How To Think With This MCP)

Use this loop for every non-trivial task:

1. **Inspect first** — Read current state before touching anything. Start with `td_get_info`, `td_get_nodes`, `td_get_node_detail`, `td_get_params`.

2. **Check memory** — Before building from scratch, use `td_memory_recall` to check if a similar technique already exists in the library.

3. **Build in small steps** — Create or modify one chunk at a time. Prefer: create -> wire -> set params -> verify.

4. **Learn and save** — When you discover a reusable network pattern, use `td_memory_learn` to extract the recipe and `td_memory_save` to persist it.

5. **Validate at the end** — Always run `td_get_errors` on the affected root. Report warnings/errors and fix before marking done.

6. **Control token cost** — Prefer metadata checks over continuous image payloads. Ask the user before enabling high-token frame streaming.

## Tool Map (63 Tools)

### 1) Scene + Timeline + Project Lifecycle
Use for global context, playback control, save/load, and undo operations.

- `td_get_info`, `td_list_families`, `td_timeline`, `td_timeline_set`, `td_project_lifecycle`

### 2) Network Build + Wiring
Use for creating, moving, renaming, connecting, and pruning structure.

- `td_get_nodes`, `td_get_node_detail`, `td_search_nodes`
- `td_create_node`, `td_delete_node`, `td_copy_node`, `td_rename_node`
- `td_connect_nodes`, `td_disconnect`, `td_get_connections`

### 3) Parameters + DAT Content
Use for patch logic, expressions, config tables, scripts, and trigger pulses.

- `td_get_params`, `td_set_params`, `td_pulse_param`
- `td_get_content`, `td_set_content`, `td_custom_parameters`

### 4) Diagnostics + Capture
Use for proving behavior instead of assuming behavior.

- `td_screenshot`, `td_chop_data`, `td_geometry_data`, `td_pop_inspect`
- `td_cooking_info`, `td_get_errors`
- `td_exec_python`, `td_python_help`, `td_python_classes`

Structured exec note: `td_exec_python` now returns JSON-safe `result`, `result_type`, and `result_is_structured` fields. Use it for lightweight structured probes before reaching for stdout parsing.

### 5) Events + Streaming
Use for reactive and continuous workflows.

- `td_subscribe`, `td_unsubscribe`, `td_get_events`
- `td_capture_and_analyze`
- `td_monitor_visual`, `td_stop_monitor_visual`
- `td_stream_top`, `td_stop_stream_top`

Token guidance: start with `include_image=false` for monitors/streams. Use image payloads only when visual detail is explicitly required. Prefer `td_screenshot` for single checks.

### 6) Optimization + Dynamics
Use for quality passes and temporal behavior analysis.

- `td_optimize_visual` — now accepts direct `objective_weights` (e.g. `{"stability": 0.8, "complexity": 0.2}`)
- `td_describe_dynamics`

### 7) Safety + Recovery
Use for guardrails, emergency control, and rollback confidence.

- `td_set_param_bounds`, `td_clear_param_bounds`
- `td_detect_instability`, `td_emergency_stabilize`
- `td_snapshot_scene`, `td_list_snapshots`, `td_diff_snapshots`, `td_restore_snapshot`
- `td_get_state_vector`, `td_get_timescale_state`

### 8) Technique Memory
Use for learning, saving, and replaying reusable network patterns.

- `td_memory_learn` — Analyze a live network subtree and extract a portable recipe. Auto-detects complexity: small/medium networks get full recipes with all params and expressions; large networks get structure summaries + key params.
- `td_memory_save` — Persist a technique to the project or global library.
- `td_memory_recall` — Search the library by text query and/or tags. Returns summaries.
- `td_memory_replay` — Rebuild a saved technique in a new location. Creates nodes, sets parameters and expressions, wires connections.
- `td_memory_list` — List all saved techniques with optional filtering.
- `td_memory_favorite` — Mark techniques as favorites and rate them (0-5).
- `td_memory_promote` — Copy a project-level technique to the global library for use across all projects.
- `td_memory_preferences` — Get/set user preferences (color palettes, default resolutions, naming conventions, etc.)

Memory storage lives at `~/.tdpilot/memory/` with per-project and global scopes:
```
~/.tdpilot/memory/
  global/
    techniques.json
    preferences.json
  projects/
    {project_name}/
      techniques.json
      preferences.json
```

## How To Use It (Practical Workflow)

1. Connect MCP client to TDPilot.
2. Ask for current project state.
3. Request a scoped patch goal.
4. Let agent apply changes in batches.
5. Require end-of-task `td_get_errors` check.
6. Save snapshot at stable milestone.
7. When you find something worth keeping: learn it, save it, rate it.

## What It Is Good At

- Building and refactoring operator networks quickly.
- Inspecting modern POP systems with attribute-aware reads.
- Converting high-level creative goals into concrete TD graph operations.
- Audio-reactive/control-system patch scaffolding.
- Automated cleanup, relayout, and consistency passes.
- Diagnosing wiring/parameter/runtime errors with direct evidence.
- Remembering what works and reusing it across projects.

## What It Is Not Good At

- Replacing artistic direction by itself.
- High-level show design without iterative user feedback.
- Unlimited always-on image streaming without token impact.
- Ignoring TD-specific context (operator families, cook behavior, timing model).
- "One shot perfect patch" generation in complex scenes.

## Network Design Protocol (Default Aesthetic Rules)

When generating or reorganizing networks: use color coding by role, keep clean spacing and avoid overlaps, group nodes into functional clusters, preserve clear flow direction, name nodes by purpose, and run `td_get_errors` after edits.

## Quick Setup

Recommended runtime (no manual Python setup in client config):

```bash
npx -y tdpilot
```

Local development runtime:

```bash
git clone https://github.com/dreamrec/TDPilot.git
cd TDPilot
uv sync
uv run tdpilot
```

TouchDesigner side component: `td_component/tdpilot_v1_2.tox`

One-command setup helpers: macOS `./install.sh`, Windows `./install.ps1`

## MCP Bundle (Standardized)

TDPilot ships a standard bundle in-repo:

- `mcp/manifest.json`
- `mcp/profiles/claude-desktop.json`, `cursor.json`, `generic.json`

Auto-generate client config:

```bash
tdpilot init --client claude-desktop
tdpilot init --client cursor --output ./cursor_mcp_config.json
tdpilot init --client generic --print-only
```

## Doctor Command

Run a final environment/runtime check:

```bash
tdpilot doctor
tdpilot doctor --json
```

## Environment Variables

- `TD_MCP_HOST` (default `127.0.0.1`)
- `TD_MCP_PORT` (default `9981`)
- `TD_MCP_WS_PORT` (default `9982`)
- `TD_MCP_TRANSPORT` (`stdio` or `streamable_http`)
- `TD_MCP_HTTP_PORT` (default `8765`)
- `TD_MCP_CAPTURE_QUALITY` (default `0.3`)
- `TD_MCP_STREAM_MAX_FPS` (default `15.0`)
- `TD_MCP_EXEC_MODE` (`off`, `restricted`, `full`)
- `TDPILOT_PROJECT_NAME` (set to enable per-project technique memory)
- `TDPILOT_MEMORY_DIR` (override default `~/.tdpilot/memory/` path)

## Test Suite

Run the test suite:

```bash
uv run --extra dev pytest tests/ -v
```

## Reliability Habit

Treat this as mandatory for every meaningful task: before edits inspect, during edits take small reversible steps, after edits run `td_get_errors`, before risky changes snapshot.

## License

MIT

```
┌─────────────────────────────────────────────────────────────────────┐
│ dreamrec // TDPilot // live laugh love                             │
└─────────────────────────────────────────────────────────────────────┘
```
