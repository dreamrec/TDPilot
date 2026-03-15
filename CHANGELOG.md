# Changelog

## 1.3.4 - 2026-03-15

### Added
- **Brain installer system** — modular one-click installer with dynamic manifest and interactive brain picker.
  - `brains_manifest.json` — single source of truth for all available brains (Google Drive file IDs, sizes, tools, skills).
  - `active.json` runtime gating — only selected brains load at startup; missing brains = silent skip, zero errors.
  - `_get_active_brains()` / `brain_is_active()` — backward-compatible brain loading (no active.json = load everything).
- POPx brain MCP tools (88→90 tools):
  - `td_search_popx_docs` — search POPx operator documentation (GPU particles, falloffs, simulations).
  - `td_get_popx_operator` — get full documentation for a specific POPx operator.
- Brain management CLI: `npx tdpilot brains [list|add|remove]`.
- Generic brain builder: `scripts/build_brain.py` — config-driven pipeline for building brains from any documentation site.
- Brain building tutorial: `docs/BUILDING_BRAINS.md` — complete guide to creating custom brains.
- `scripts/download_brains.py` now supports `--manifest` and `--brains-file` flags for installer integration.

## 1.3.3 - 2026-03-15

### Added
- **Docs Brain** — full-corpus search engine over docs.derivative.ca replacing hand-curated JSON knowledge cards.
  - SQLite FTS5 index: 2,478 pages → 25,887 chunks, 674 operators, 10 tracked builds, 245 operators with changelog entries.
  - BM25 ranking with boosted weights (section_title 10×, operator_name 8×, parameter_names 5×, python_symbols 3×, content 1×).
  - Intent-based query routing: auto-detects operator names, build numbers, palette/glossary keywords before FTS5 search.
  - Release notes intelligence: per-operator changelog and build manifest across 10 builds.
  - Drop-in replacement for CardIndex with automatic fallback when brain DB is absent.
- `scripts/build_docs_brain.py` — four-stage offline pipeline: normalize HTML → chunk by headings → index in FTS5 → build release artifacts.
- `docs/BRAINS.md` — step-by-step rebuild guide for regenerating the brain after a new docs scrape.

### Changed
- POPx skill updated for copyright compliance: references must be built locally from licensed copy (see `references/BUILD.md`).
- Knowledge tool stack (`td_search_official_docs`, `td_get_operator_doc`, etc.) now queries Docs Brain when available, falls back to CardIndex.

## 1.3.2 - 2026-03-14

### Added
- Auto-load on TD startup: `npx tdpilot install` sets up TDPilot to load automatically every time TouchDesigner launches. Run `npx tdpilot uninstall` to remove.
- 2 vision diagnostic tools (75 to 77):
  - `td_capture_frame` — capture TOP output as base64 image for MCP-side analysis.
  - `td_analyze_frame` — run TD-side pixel analysis (histogram, luminance, alpha_coverage, color_dominant, roi_diff).
- 6 TD 2025 native system tools (77 to 83):
  - `td_python_env_status` — Python environment and extension module status.
  - `td_threading_status` — thread pool and DAG cooking information.
  - `td_logger_status` — logger configuration and recent entries.
  - `td_tdresources_inspect` — TDResources paths by category.
  - `td_component_standardize` — audit/fix COMP against TD standards (undo-wrapped).
  - `td_color_pipeline` — color space and bit-depth pipeline audit.
- 3 official recommendation tools (83 to 86):
  - `td_recommend_official_component` — search palette + operator cards for a given goal.
  - `td_find_official_example` — search snippets + palette for official examples.
  - `td_explain_better_way` — suggest better alternatives with gotcha warnings.
- TD-side `/api/analyze_frame` endpoint with 5 analysis modes (histogram, luminance, alpha_coverage, color_dominant, roi_diff).
- Enhanced recipe capture: `analyze_network` now returns `td_build`, `required_op_types`, `external_assets`, and `layout`.
- Technique compatibility fields: `compatibility` dict and `validation_result` tracking in TechniqueStore.
- Pre-replay prerequisite check: `td_memory_replay` blocks replay when required operator types are missing.

### Fixed
- Feedback macro templates (`feedback_loop`, `feedback_displacement`) now close the loop via feedbackTOP's `top` parameter instead of a physical wire, matching TD's official palette pattern and eliminating cook-dependency-loop warnings.
- Added `NodeRefParam` model and engine support for cross-node parameter references in macro templates.

### Changed
- `analyze_network` accepts `td_build` parameter; `td_memory_learn` and `td_memory_save` pass TD build info to analyzer.
- TD-side API version bumped from 1.3.0 to 1.3.2.
- Runtime surface increased from 75 to 86 tools.

## 1.3.1 - 2026-03-14

### Added
- MCP Tasks adapter: dual-mode bridge that routes job progress to MCP Tasks (native) or polling depending on client capabilities.
- JobManager callback hooks (`on_progress_hook`, `on_complete_hook`) for external progress tracking.
- Expanded snapshot diff: connection changes (`added_connections`, `removed_connections`) and expression changes (`added_expressions`, `removed_expressions`, `modified_expressions`).
- `_with_undo_block` helper wrapping multi-step mutations in TD undo blocks for single-step reversal.
- 4 new planning and validation tools (71 to 75):
  - `td_plan_patch` — generate structured patch plans from intents and recipes.
  - `td_preflight_patch` — validate plans before execution (path existence, name conflicts, op type checks).
  - `td_validate_recipe` — validate technique recipes against knowledge cards and build compatibility.
  - `td_audit_project` — audit project subtrees for structure, palette usage, errors, and build warnings.
- Recipe state machine: techniques now track `state` (candidate, validated_local, validated_portable, deprecated, reference_only) and `validation_result`.
- Auto-validation on replay: `td_memory_replay` checks for errors after replay and auto-promotes candidate recipes to `validated_local` on clean replay.

### Changed
- `td_restore_snapshot` docstring clarified: restores parameter values only; structural rollback uses TD native undo.
- `ServiceContainer` gains `task_adapter` field for lifespan-managed TaskAdapter.

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
