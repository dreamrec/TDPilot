# TDPilot v1.5.3 Production Manual

This manual is for people who need real output in TouchDesigner, not theory. It explains what TDPilot does well, what it does not do, and how to run it with repeatable production discipline.

## 1. Product Reality Check

### What TDPilot is strong at

- Live graph operations: creating, wiring, renaming, and parameterizing nodes quickly.
- Tight inspect -> edit -> verify loops using diagnostics and error tools.
- Recoverability: snapshots, diff, restore, and safety boundaries.
- Technique reuse: memory tools convert successful subnet patterns into reusable recipes.
- Team consistency: shared naming, tags, and preference memory reduce random drift between sessions.
- **Typed patch sessions (v1.5.0):** plan → preview → apply → validate → undo flow with sentinel-guarded undo blocks, name-collision readback, and live-state risk flags. Each patch is a typed `PatchPlan` value object that can be inspected, varied (`td_patch_variations`), and replayed.

### What TDPilot is not

- Not an autonomous art director: it still needs clear constraints and aesthetic direction.
- Not a replacement for TouchDesigner expertise on GPU budgets, operator semantics, and final look tuning.
- Not a guaranteed one-shot generator for large legacy networks. For complex patches, it works best as an incremental co-pilot.
- Not visual "magic" by default: if you skip screenshot/monitor checks, you are flying blind.

### Compared to common alternatives

- Versus generic chat-only assistants: TDPilot can execute real TD operations and validate live state.
- Versus one-off Python scripts: TDPilot keeps an interactive tool surface with safety, diagnostics, memory, and replay.
- Versus ad-hoc manual workflows: TDPilot gives a consistent operating loop that is easier to hand off and scale.

## 2. System Architecture (Operational View)

- MCP client (Claude Desktop/Cursor/other) issues tool calls.
- TDPilot server (`tdpilot run`) brokers calls, validates inputs, and handles memory/safety logic.
- TouchDesigner WebServer DAT receives HTTP operations.
- Optional WebSocket path handles stream/event updates.

Core ports (defaults):

- HTTP control: `9981`
- WS events/streaming: `9982`

## 3. Setup for Production

1. Install and configure client profile:

```bash
uv run tdpilot init --client claude-desktop
```

2. Load the TDPilot component in TouchDesigner (once per session):

```python
# In TD Textport — installs into /local by default (persists across project opens)
exec(open("/path/to/TDPilot/setup_mcp_in_td.py").read(), globals(), globals())
```

Or drag-and-drop `td_component/tdpilot.tox` into `/local` manually.

3. Run environment diagnostics before sessions:

```bash
uv run tdpilot doctor --skip-td-check
```

4. If TouchDesigner is running and component is loaded, run full health:

```bash
uv run tdpilot doctor --strict
```

5. Keep repo-local execution in production scripts:

```bash
uv run --directory /ABS/PATH/TDPilot tdpilot run
```

## 3.1 Features Added Since v1.1

- POPx: use `td_pop_inspect` for POP-native counts, attribute metadata, and sampled values.
- Project lifecycle: use `td_project_lifecycle` for save/load/undo/redo instead of ad hoc Python snippets.
- Custom UI authoring: use `td_custom_parameters` to create pages and parameters on COMPs.
- Structured Python probes: `td_exec_python` now returns JSON-safe results when possible.

## 4. Standard Working Loop (Use This Every Time)

1. Inspect first.
2. Check memory before rebuilding known patterns.
3. Make small edits.
4. Validate with errors/cooking/visual checks.
5. Learn + save successful patterns.
6. Snapshot for rollback points before risky changes.

Minimum inspect stack:

- `td_get_info`
- `td_get_nodes`
- `td_get_node_detail`
- `td_get_params`

Minimum validation stack:

- `td_get_errors`
- `td_cooking_info`
- `td_screenshot` (or monitor tools when needed)

## 5. Workflow Ladders

### Beginner workflow: build a small effect chain safely

1. Read context: `td_get_info`, `td_get_nodes`.
2. Create one node at a time: `td_create_node`.
3. Wire one connection at a time: `td_connect_nodes`.
4. Set only required params first: `td_set_params`.
5. Verify no errors: `td_get_errors`.
6. Capture a check image: `td_screenshot`.

Rule: avoid bulk edits until you can verify each stage.

### Intermediate workflow: stabilize a patch under load

1. Snapshot current state: `td_snapshot_scene`.
2. Inspect hotspots: `td_cooking_info`, `td_get_errors`.
3. Apply bounded fixes (parameter bounds, simplification).
4. Run `td_detect_instability` and optionally `td_emergency_stabilize`.
5. Diff against snapshot: `td_diff_snapshots`.
6. If degraded, restore immediately: `td_restore_snapshot`.

Rule: always keep one known-good snapshot when optimizing live.

### Advanced workflow: memory-driven production system

1. Extract reusable technique:
   - `td_memory_learn` on successful subnet.
2. Persist with quality metadata:
   - `td_memory_save` with `name`, `description`, strong tags, and notes.
3. Discover and filter techniques:
   - `td_memory_recall` and `td_memory_list`.
4. Rebuild in new context:
   - `td_memory_replay` with `parent_path` and optional prefix.
5. Curate:
   - `td_memory_favorite` and rating.
6. Promote patterns across shows/projects:
   - `td_memory_promote` to global scope.

Rule: memory quality depends on curation discipline, not volume.

## 6. Practical Production Scenarios

### Scenario A: Rapid audiovisual prototype (1-2 hours)

- Goal: produce a demo network with controllable motion and stable playback.
- Flow:
  1. Build base graph quickly (`td_create_node`, `td_connect_nodes`).
  2. Expose performance-critical parameters (`td_set_params`).
  3. Validate FPS and issues (`td_cooking_info`, `td_get_errors`).
  4. Save reusable rhythm or modulation subnet (`td_memory_learn`, `td_memory_save`).

Success metric: repeatable result with no unresolved errors and a stored technique ready for reuse.

### Scenario B: Recovery during technical rehearsal

- Goal: recover from instability without losing show state.
- Flow:
  1. Take immediate snapshot.
  2. Run instability analysis and inspect heavy nodes.
  3. Apply minimal fix set.
  4. Re-check timeline stability and render health.
  5. Roll back if performance does not recover.

Success metric: faster return to stable output than manual forensic editing.

### Scenario C: Building a reusable studio style library

- Goal: convert one-off creative wins into production assets.
- Flow:
  1. Standardize naming conventions and tags.
  2. Save techniques project-local first.
  3. Rate/favorite proven techniques.
  4. Promote only validated techniques to global.
  5. Keep preference keys for defaults (palette, resolution, naming).

Success metric: new projects start from known-good building blocks, not blank experiments.

## 7. Memory Deep Dive

### Memory scopes

- `project` scope: techniques/preferences tied to a specific project name.
- `global` scope: techniques/preferences reusable across all projects.

### Where memory is stored

Default path:

```text
~/.tdpilot/memory/
  global/
    techniques.json
    preferences.json
  projects/
    <project_name>/
      techniques.json
      preferences.json
```

Path and project overrides:

- `TDPILOT_MEMORY_DIR`: overrides base memory directory.
- `TDPILOT_PROJECT_NAME`: selects the current project memory namespace.

### How technique storage works

- Each saved technique gets a UUID.
- Records include metadata (`name`, `description`, `tags`, `notes`, timestamps, rating/favorite flags).
- Recipe payload is stored under `technique`.
- Writes are atomic-style (`.tmp` then replace), reducing corruption risk.

### Replay behavior and limits

- Small/medium analyzed networks include full recipe and can be replayed.
- Large networks are stored as structure summary + key params only.
- Replaying a large network returns an explicit error and guidance fields (`key_params`, `families`, `op_types`).

### Preference memory

- Key-value store for defaults and style conventions.
- Supports get/set/list/delete.
- Keep keys stable and intentional (example: `palette.primary`, `naming.top_prefix`).

## 8. Good Practice for Memory and Team Work

- Save only techniques that are tested and visually validated.
- Use tags as retrieval strategy, not decoration (`audio-reactive`, `feedback-safe`, `show-opener`).
- Require a useful description and notes for every saved technique.
- Rate after real usage, not right after creation.
- Promote to global only after at least one successful reuse.
- Prune stale or low-value entries periodically.
- Back up `~/.tdpilot/memory/` before major refactors.

## 9. Tooling Patterns That Increase Throughput

- Prefer inspect-first tools before write operations.
- Use snapshot/restore around high-risk changes.
- Keep visual monitoring token-aware:
  - start with metadata-only modes
  - request images only when visual confirmation is necessary
- Use `td_exec_python` in restricted, minimal snippets; avoid broad side effects.

## 10. Release and Operations Checklist

### Before release

1. Run tests:

```bash
uv run pytest -q
```

2. Run registry smoke check:

```bash
uv run python scripts/smoke_mcp_registry.py
```

3. Run live runtime and end-to-end suites:

```bash
uv run python scripts/runtime_stress_matrix.py --out reports/runtime_stress_matrix.json
uv run python scripts/full_td_mcp_e2e.py --strict-events --out reports/e2e_live.json
```

4. Generate benchmark and soak reports:

```bash
uv run python scripts/bench_tools.py --out reports/bench_tools.json
uv run python scripts/soak_events.py --out reports/soak_events.json
```

5. Evaluate release gates:

```bash
uv run python scripts/check_release_gates.py --bench-report reports/bench_tools.json --soak-report reports/soak_events.json --require-complete
```

### During live production

1. Snapshot before risky edits.
2. Keep one operator focused on validation signals (errors/FPS/monitor output).
3. Record reusable wins into memory before ending session.

### After session

1. Promote only proven techniques.
2. Export library with `td_memory_export` for backup or sharing with teammates.
3. Note unresolved weak points for next iteration.

## 11. Common Failure Modes and Fixes

- `Technique not found` on replay:
  - Check `scope` and `technique_id`.
  - Confirm `TDPILOT_PROJECT_NAME` is set correctly for project-scoped entries.

- Replay creates partial network:
  - Inspect `skipped_nodes` and `skipped_connections` in replay response.
  - Resolve missing parent/container assumptions.

- Replay blocked for large technique:
  - Use returned `key_params` and structure summaries to rebuild intentionally.
  - Then re-learn smaller reusable subnets for future replay.

- Inconsistent behavior across machines:
  - Align environment variables and memory base path.
  - Avoid embedding user-specific absolute filesystem paths in saved notes or content.

## 12. Final Production Principle

Treat TDPilot as an execution system with memory, not a prompt toy. The strongest outcomes come from disciplined loops: inspect, apply small changes, validate, and curate what works.
