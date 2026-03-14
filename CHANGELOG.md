# Changelog

## 1.3.0 - 2026-03-14

### Added
- `standard` exec safety mode: curated import whitelist (14 safe modules) with read-only introspection for data-transform workflows.
- Expanded CapabilitySet from 5 to 10 fields: `supports_tasks`, `supports_elicitation`, `transport_type`, `mcp_sdk_version`, `td_build`.
- Knowledge corpus: structured JSON card system for operators (30), palette components (6), releases, and snippet families.
- 8 new knowledge tools (63 to 71): `td_search_official_docs`, `td_get_operator_doc`, `td_get_param_help`, `td_lookup_snippets`, `td_lookup_palette_component`, `td_get_release_delta`, `td_get_build_compatibility`, `td_describe_surface`.
- Read-through fallbacks for cached resources (CHOP, parameter, cook, error) — one-shot TD API call on cache miss.
- Resource `mode` field (`authoritative` or `cache`) on all resource responses.
- Optional web fetcher for live docs enrichment (`TD_MCP_WEB_FETCH=true`).

### Changed
- EventManager subscription keys now use `(path, event_type)` tuples for correct multi-event handling.
- `to_dict()` return type on CapabilitySet changed from `dict[str, bool]` to `dict[str, Any]`.
- TD-side API version bumped to 1.3.0 with matching `standard` exec mode support.

## 1.2.0 - 2026-03-14

### Changed
- Renamed TD component artifact from `mcp_server_codex.tox` to `tdpilot_v1_2.tox` (format: `tdpilot_v{MAJOR}_{MINOR}.tox`).
- Doctor command reads .tox filename from canonical `TOX_FILENAME` constant instead of hardcoding.
- Transport naming normalized via `normalize_transport()` — consistent across doctor, capabilities, and runtime startup.
- MCP dependency pinned to `>=1.0,<2.0` to prevent SDK v2 pre-alpha breakage.
- Added CI bundle integrity check validating version and artifact path agreement.

### Removed
- Deleted `mcp_server_codex.tox` (replaced by `tdpilot_v1_2.tox`).

## 1.1.0 - 2026-03-07

### Added
- New first-class tool: `td_pop_inspect` for POP-native summaries, attribute lists, and attribute sampling.
- New first-class tool: `td_project_lifecycle` for save/load/undo/redo and undo block control.
- New first-class tool: `td_custom_parameters` for custom page/parameter authoring on COMPs.
- New documentation guide: `docs/MCP_1_1_SURFACE.md`.

### Changed
- `td_exec_python` now returns structured JSON-safe `result` payloads with `result_type` and `result_is_structured` metadata when possible.
- Runtime surface increased from 60 to 63 tools.
- Registry smoke checks, E2E thresholds, manifest metadata, and package versions now track the expanded tool surface.
- `tdpilot-core` repo skill note now reflects the modern tool count instead of the stale 27-tool wording.

## 1.0.0 - 2026-02-24

### Added
- Production MCP runtime for TouchDesigner with a 60-tool surface spanning scene control, build/wiring, params/content, diagnostics, events/streaming, optimization, safety, and memory.
- Technique memory system with 8 tools:
  - `td_memory_learn` — analyze live networks and extract reusable recipes
  - `td_memory_save` — persist techniques to project or global library
  - `td_memory_recall` — search library by text and tags
  - `td_memory_replay` — rebuild saved techniques in new locations
  - `td_memory_list` — list techniques with filters
  - `td_memory_favorite` — mark/rate techniques
  - `td_memory_promote` — copy project techniques to global library
  - `td_memory_preferences` — get/set user preferences
- Per-project and global memory storage at `~/.tdpilot/memory/`.
- TouchDesigner component artifact at `td_component/mcp_server.tox`.
- CLI utilities: `tdpilot doctor`, `tdpilot init --client ...`.
- Standardized MCP bundle: `mcp/manifest.json`, `mcp/profiles/*`.

### Changed
- Simplified optimizer: `td_optimize_visual` now accepts direct `objective_weights` instead of keyword heuristics.
- Refined runtime surface from 63 to 60 tools by removing unused tools and replacing intent scaffolding with production memory workflows.
- Updated manifest, smoke checks, E2E flows, and stress scripts for the finalized tool surface.
- Hardened benchmarking and release gates: benchmark error rates now separate warmup vs measured failures, and gate checks include error-rate thresholds.

### Removed
- Unused tools: `td_runtime_assess`, `td_runtime_remember_intent`, `td_runtime_recall_intents`, `td_runtime_link_snapshot_memory`, `td_runtime_set_preferences`, `td_runtime_get_preferences`, `td_runtime_compile_intent`, `td_runtime_dashboard`, `td_runtime_restore_transform`, `td_runtime_killer_demo`, `td_dop_catalog`.
- Deprecated modules: `runtime/assessment.py`, `runtime/intent_mapping.py`, `runtime/memory_index.py`, and `dop/`.
- Obsolete CLI and env flags: `runtime-dashboard`, `TD_MCP_INTENT_MEMORY`.
- Obsolete docs: `KILLER_DEMO.md`, `DOP_CLASS_ROADMAP.md`.
