```
████████╗██████╗ ██████╗ ██╗██╗      ██████╗ ████████╗
╚══██╔══╝██╔══██╗██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
   ██║   ██║  ██║██████╔╝██║██║     ██║   ██║   ██║
   ██║   ██║  ██║██╔═══╝ ██║██║     ██║   ██║   ██║
   ██║   ██████╔╝██║     ██║███████╗╚██████╔╝   ██║
   ╚═╝   ╚═════╝ ╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝
```

# TDPilot Runtime v1.3.4

**TDPilot Runtime** is an MCP server for TouchDesigner.
It lets an AI agent inspect, build, wire, optimize, and stabilize live TD networks with real tool calls — and now remember what works.

`#tdpilot` `#touchdesigner` `#mcp` `#livepatch` `#audioreactive` `#realtime`

## Documentation

- Getting started: `docs/GETTING_STARTED.md`
- User guide: `docs/USER_GUIDE.md`
- Memory guide: `docs/MEMORY_GUIDE.md`
- Production manual: `docs/MANUAL.md`
- API reference: `docs/API_REFERENCE.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- MCP 1.1 surface: `docs/MCP_1_1_SURFACE.md`
- Release notes: `CHANGELOG.md`

## What This Is

- A practical control layer between AI agents and TouchDesigner.
- A structured toolset for scene edits, diagnostics, event monitoring, and recovery.
- A workflow-oriented MCP built for iterative patch development, not one-shot guessing.
- A technique memory system that learns from your projects and builds a reusable library.
- 92-tool runtime surface with knowledge corpus, vision diagnostics, TD 2025 native inspection, official recommendations, job resources, memory, optimizer, safety, POPx inspection, project lifecycle control, and custom parameter authoring.

## Start Here: Core Workflow

You don't need all 92 tools. Start with these and expand as needed:

| Step | Tools | What You're Doing |
|------|-------|-------------------|
| **Inspect** | `td_get_info`, `td_get_nodes`, `td_get_params`, `td_get_errors` | Understand current state before touching anything |
| **Check memory** | `td_memory_recall` | See if a reusable technique already exists |
| **Build** | `td_create_node`, `td_connect_nodes`, `td_set_params` | Make changes in small, reversible steps |
| **Verify** | `td_get_errors`, `td_cooking_info`, `td_screenshot` | Prove the change worked |
| **Protect** | `td_snapshot_scene`, `td_restore_snapshot` | Save milestones, roll back if needed |
| **Remember** | `td_memory_learn`, `td_memory_save` | Save successful patterns for reuse |

**The loop:** Inspect -> Build -> Verify -> Snapshot -> Repeat.

Everything else (vision, streaming, optimization, planning, TD2025 inspection) builds on top of this core.

## What's New In 1.3.4

- **Vision diagnostics** — `td_capture_frame` and `td_analyze_frame` for MCP-side and TD-side pixel analysis (histogram, luminance, alpha, dominant color, ROI diff).
- **TD 2025 native tools** — 6 tools for Python env, threading, logger, TDResources, COMP standardization, and color pipeline inspection.
- **Official recommendations** — `td_recommend_official_component`, `td_find_official_example`, `td_explain_better_way` search the knowledge corpus for safer official approaches.
- **Enhanced recipe capture** — Recipes now include `td_build`, `required_op_types`, `external_assets`, and `layout` for portability validation.
- **Pre-replay checks** — `td_memory_replay` blocks replay when required operator types are missing from the target TD install.

## What's New In 1.3.0

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

## Tool Map (88 Tools)

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
- `td_memory_export` — Export the technique library as a portable JSON object for sharing or backup.
- `td_memory_import` — Import techniques from an exported library (from `td_memory_export`).
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

### 9. Macros & Planning (7)
| Tool | Purpose |
|------|---------|
| `td_create_macro` | Create a reusable macro from a template |
| `td_list_macros` | List available macros |
| `td_get_macro_params` | Get macro parameter schema |
| `td_plan_patch` | Plan a multi-step network patch |
| `td_preflight_patch` | Pre-validate a patch plan |
| `td_validate_recipe` | Validate a technique recipe |
| `td_audit_project` | Audit project subtree |

### 10. Vision & Streaming (7)
| Tool | Purpose |
|------|---------|
| `td_capture_frame` | Capture a single frame from a TOP |
| `td_analyze_frame` | Analyze frame content (colors, regions) |
| `td_monitor_visual` | Start continuous visual monitoring |
| `td_stop_monitor_visual` | Stop visual monitoring |
| `td_stream_top` | Stream TOP output via WebSocket |
| `td_stop_stream_top` | Stop TOP streaming |
| `td_optimize_visual` | Get optimization suggestions for visuals |

### 11. Knowledge Corpus (7)
| Tool | Purpose |
|------|---------|
| `td_search_official_docs` | Search official TD documentation |
| `td_get_operator_doc` | Get detailed operator documentation |
| `td_get_param_help` | Get parameter-level help |
| `td_lookup_snippets` | Find code snippets by topic |
| `td_lookup_palette_component` | Look up Palette component info |
| `td_get_release_delta` | Get changes between TD builds |
| `td_get_build_compatibility` | Check operator build compatibility |

### 12. Server Introspection (3)
| Tool | Purpose |
|------|---------|
| `td_get_capabilities` | Report server capabilities |
| `td_get_server_metrics` | Get server performance metrics |
| `td_describe_surface` | Describe the full tool surface |

### 13. Recommendations (3)
| Tool | Purpose |
|------|---------|
| `td_recommend_official_component` | Suggest official components |
| `td_find_official_example` | Find relevant official examples |
| `td_explain_better_way` | Suggest better approaches |

### 14. TD 2025 Native (6)
| Tool | Purpose |
|------|---------|
| `td_python_env_status` | Inspect Python environment in TD |
| `td_threading_status` | Check threading configuration |
| `td_logger_status` | Inspect TD logger state |
| `td_tdresources_inspect` | Inspect TDResources categories |
| `td_component_standardize` | Audit/fix COMP standards |
| `td_color_pipeline` | Inspect color management pipeline |

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

### TouchDesigner Side

Run the setup script once inside the TD Textport:

```python
exec(open("/path/to/TDPilot/setup_mcp_in_td.py").read(), globals(), globals())
```

This installs the MCP component into `/local/mcp_server` by default, which means it **persists across project opens** within the same TD session. You only need to run this once — every project you open afterward will already have TDPilot available.

To install into a specific project instead: `os.environ["TD_MCP_PARENT_PATH"] = "/project1"` before running.

Alternatively, drag-and-drop `td_component/tdpilot_v1_3.tox` into `/local` manually.

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

- `TD_MCP_HOST` (default `127.0.0.1` — supports hostnames like `desktop-3lurf0p.tail88651a.ts.net`)
- `TD_MCP_PORT` (default `9981`)
- `TD_MCP_SCHEME` (default `http` — set to `https` for Tailscale HTTPS or TLS-enabled setups)
- `TD_MCP_WS_PORT` (default `9982`)
- `TD_MCP_TRANSPORT` (`stdio` or `streamable_http`)
- `TD_MCP_HTTP_PORT` (default `8765`)
- `TD_MCP_CAPTURE_QUALITY` (default `0.3`)
- `TD_MCP_STREAM_MAX_FPS` (default `15.0`)
- `TD_MCP_EXEC_MODE` (`off`, `restricted`, `standard`, `full`)
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
