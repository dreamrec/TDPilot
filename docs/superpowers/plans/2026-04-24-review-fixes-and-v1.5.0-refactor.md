# Review Fix Patch + v1.5.0 Refactor Plan

Date: 2026-04-24
Current reviewed head: `73add011`

## Goal

Fix the four review findings from the v1.4.4 local review, then use v1.5.0 to turn TDPilot from a large working MCP surface into a modular, safer, more creative TouchDesigner patching system.

The practical north star:

1. Install should be boring and deterministic.
2. Knowledge and memory should never silently return hollow results.
3. Patching should feel like a creative workflow: plan, preview, apply, validate, iterate, and learn.
4. Public tool names and existing user workflows should remain stable unless there is a clear migration path.

## Release Shape

Use two releases:

- `v1.4.5`: Review-fix patch. No broad refactors. Fix the four findings with tests.
- `v1.5.0`: Architecture and creative patching release. Split the monoliths, add a patch-session layer, and raise the reliability floor.

## v1.4.5: Review-Fix Patch

### Fix 1: Plugin auth bootstrap must actually work

Problem:

- `.mcp.json` sets `TD_MCP_REQUIRE_AUTH=1`.
- The Claude Code plugin install paths do not provision `TD_MCP_SHARED_SECRET`.
- The new startup gate correctly fails loud, but that means the default plugin path now deterministically fails unless the user manually edits env.
- TD-side auth also needs the same secret as the MCP server. Fixing only the Python process is not enough.

Preferred implementation:

1. Add a small shared auth bootstrap module:
   - New file: `src/td_mcp/auth_bootstrap.py`
   - Responsibilities:
     - Locate repo/plugin root.
     - Load `.tdpilot.env` before auth verification.
     - Generate a strong `TD_MCP_SHARED_SECRET` when explicitly allowed.
     - Write `.tdpilot.env` atomically with restrictive permissions where supported.

2. Update `.mcp.json` for plugin use:
   - Keep `TD_MCP_REQUIRE_AUTH=1`.
   - Add an explicit opt-in flag such as `TD_MCP_AUTOGENERATE_SECRET=1`.
   - Add `TD_MCP_ENV_FILE=${CLAUDE_PLUGIN_ROOT}/.tdpilot.env` if Claude plugin variable expansion supports it.
   - If variable expansion is not reliable, derive the env path from `TD_MCP_REPO_ROOT` / current plugin root inside Python.

3. Update Python server startup:
   - Before `verify_auth_config()`, load `.tdpilot.env`.
   - If auth is required, secret is missing, and autogeneration is enabled, generate and persist the secret.
   - Re-run env load or inject the generated secret into `os.environ`.
   - Keep fail-loud behavior when autogeneration is not enabled.

4. Update TD setup paths:
   - `setup_mcp_in_td.py` should load or generate the same `.tdpilot.env` before building/loading the component.
   - `tdpilot_startup.py` already loads `.tdpilot.env`; keep that path and add tests around it if possible.
   - Plugin docs should make the Textport setup script the required first-time setup for auth-enabled plugin installs.
   - Demote raw drag-and-drop to "advanced/manual" unless the `.tox` can load the env file itself.

5. Update `npx tdpilot plugin-install` and `scripts/install_claude_plugin.sh`:
   - After plugin install, print the auth model clearly.
   - If the plugin cache path can be found, pre-create `.tdpilot.env`.
   - If not, explain that `setup_mcp_in_td.py` creates it on the TD side before first use.

Tests:

- Python tests:
  - Missing secret + auth required + no autogenerate still fails.
  - Missing secret + auth required + autogenerate writes `.tdpilot.env` and passes.
  - Existing `.tdpilot.env` is loaded before `verify_auth_config()`.
  - Env variable secret wins over file secret.
  - Generated secret is not logged to stdout during normal server startup.

- TD setup script tests:
  - Source-level or small helper tests for `.tdpilot.env` parse/write if the logic is factored into plain Python functions.

- Plugin smoke tests:
  - Shipped `.mcp.json` no longer represents an impossible configuration.
  - `tdpilot doctor` passes when pointed at a temp plugin root with autogeneration enabled.

Acceptance:

- Fresh plugin install has a deterministic path to a matching MCP/TD secret.
- The default plugin instructions no longer lead to startup failure.
- Manual auth-disabled local development remains possible, but not the default secure path.

Fallback option:

- If plugin env autogeneration cannot be made reliable, change the Claude Code plugin profile to explicit local no-auth mode and document it honestly. Desktop installers should remain auth-enabled. This is less secure, but better than a broken secure-by-default claim.

### Fix 2: Brain manager must validate installability

Problem:

- `npm/brains.js addBrain()` writes any requested id to `active.json` after a zero downloader exit.
- `scripts/download_brains.py` exits 0 when all requested ids are unknown.
- `paketa12` has `files: []`, so it can be marked installed without a usable DB.
- Because `active.json` acts as an allow-list, a typo can disable all known brains on next startup.

Implementation:

1. Extend `data/brains/brains_manifest.json`:
   - Add `install_mode`: `"download"` or `"local_build"`.
   - Add `runtime_db` for each brain, for example `data/normalized/derivative/docsbrain.db`.
   - For `paketa12`, use `install_mode: "local_build"` and `runtime_db: "data/normalized/paketa12/paketa12brain.db"`.

2. Harden `npm/brains.js`:
   - Read the manifest before calling the downloader.
   - Reject unknown brain ids with a non-zero exit and list valid ids.
   - For `install_mode: "local_build"`:
     - If `runtime_db` exists, allow activation without download.
     - If missing, print build instructions and exit non-zero.
   - Only write to `active.json` after install or verified local activation succeeds.
   - Add a `brains activate <id>` command if activation of prebuilt local DBs should be explicit.

3. Harden `scripts/download_brains.py`:
   - If any selected ids are unknown, exit non-zero.
   - If `brains_to_download` is empty after filtering, exit non-zero.
   - If a selected manifest entry has no downloadable files and no local-build mode, exit non-zero.
   - Return a clear status summary.

4. Runtime safety:
   - Consider filtering unknown ids in `_get_active_brains()` only if a manifest can be located cheaply.
   - At minimum, log unknown active brain ids so users know why expected brains did not load.

Tests:

- Node-level tests or subprocess tests:
  - `brains add not_a_real_brain` exits non-zero and does not write `active.json`.
  - `brains add paketa12` exits non-zero when DB missing and prints local-build instructions.
  - `brains add paketa12` activates only when `runtime_db` exists.
  - `brains add derivative` calls downloader and writes active only on success.

- Python downloader tests:
  - Unknown ids exit non-zero.
  - Empty selected list exits non-zero.
  - Manifest entries load correctly.

Acceptance:

- `active.json` cannot be polluted by typos.
- Local-build brains are represented honestly.
- `npx tdpilot brains list` shows available brains and install mode.

### Fix 3: DocsBrain parameter help must enrich `td_get_param_help`

Problem:

- `td_get_param_help` scans only `card["key_params"]`.
- `CardIndex` JSON cards use `key_params`.
- `DocsBrain.get_operator()` returns `parameters`, not `key_params`.
- With full DocsBrain active, parameter help silently returns `card_param: None`.

Implementation:

1. Add a normalization helper:
   - Location: either `src/td_mcp/knowledge/adapter.py` or inside `DocsBrain`.
   - Function shape:
     - `normalize_operator_card(card: dict) -> dict`
     - Ensure the result has `key_params`.
     - Preserve original `parameters`.

2. Normalize in `DocsBrain.get_operator()`:
   - Build `key_params` from the FTS parameter list.
   - For DocsBrain parameter strings, parse the likely parameter name from the last non-empty line.
   - Keep a `raw` field so no information is lost.
   - Example:
     - Raw: `"Output\nResolution\noutputresolution"`
     - Normalized: `{"name": "outputresolution", "label": "Output Resolution", "raw": "...", "source": "docsbrain"}`

3. Make `td_get_param_help` robust:
   - Use the normalized card shape.
   - If `key_params` is missing, fall back to `parameters`.
   - Match case-insensitively.
   - Return a `card_param` object that says whether it came from `local_card` or `docsbrain`.

4. Add optional future enrichment:
   - Find the chunk mentioning that parameter and include a short `note`.
   - Do this only if it can be done cheaply without bloating responses.

Tests:

- `DocsBrain.get_operator("noiseTOP")` returns `key_params`.
- `td_get_param_help(..., param_name="outputresolution")` returns a DocsBrain-derived `card_param`.
- Existing JSON-card CardIndex behavior still works.
- Unknown parameters still return `card_param: None` without error.

Acceptance:

- Full DocsBrain and fallback CardIndex produce compatible operator-card shapes.
- Parameter help is no longer hollow when DocsBrain is active.

### Fix 4: `tdpilot init --print-only` must remain machine-readable

Problem:

- `tdpilot init --print-only --auth --generate-secret` prints secret log lines to stdout before JSON.
- The stdout stream is no longer valid JSON.
- `--generate-secret` / `--shared-secret` are documented as requiring `--auth`, but currently they are silently ignored without `--auth`.

Implementation:

1. Add init argument validation:
   - `--generate-secret` and `--shared-secret` without `--auth` should fail.
   - `--generate-secret` and `--shared-secret` together should fail.

2. Make `--auth` ergonomic:
   - Best UX: `--auth` with no provided secret generates a secret by default.
   - Keep `--generate-secret` as an explicit alias for clarity/backward compatibility.
   - If a "require auth but omit secret" mode is still needed for tests, hide it behind an explicit developer flag, not the normal user path.

3. Preserve stdout JSON:
   - If `args.print_only` is true, stdout contains exactly the JSON profile.
   - Secret notices go to stderr.
   - File-writing mode can keep user-facing notices on stdout.

4. Improve config output:
   - Include `TD_MCP_EXEC_MODE=restricted` when auth is enabled unless the user overrides.
   - Consider `--exec-mode` flag with choices `off`, `restricted`, `standard`, `full`.

Tests:

- `tdpilot init --print-only --auth` stdout parses as JSON.
- Secret notice for print-only goes to stderr.
- `--generate-secret` without `--auth` exits non-zero.
- `--shared-secret` without `--auth` exits non-zero.
- `--generate-secret` plus `--shared-secret` exits non-zero.
- `--auth` with no secret emits auth + generated secret.

Acceptance:

- `tdpilot init --print-only ... | jq .` works.
- The CLI does not silently ignore security flags.

### v1.4.5 Release Gates

Run:

```bash
uv run ruff check .
uv run ruff format --check src tests scripts td_component
uv run --with pytest-cov python -m pytest --cov=src/td_mcp --cov-report=term
uv run python scripts/check_versions.py
uv run python scripts/check_tox_freshness.py
uv run python scripts/smoke_mcp_registry.py
bash scripts/check_no_personal_paths.sh
bash scripts/check_package_builds.sh --cleanup
TD_MCP_REQUIRE_AUTH=0 uv run tdpilot doctor --skip-td-check
```

If TD-side callback behavior changes, rebuild `.tox` inside TouchDesigner and update the freshness hash.

## v1.5.0: Architecture Refactor

### Design Constraints

- Keep public MCP tool names stable.
- Keep schema snapshots as a compatibility gate.
- Do not rewrite behavior and architecture in the same commit.
- Split files behind compatibility shims so external imports keep working.
- Make the refactor measurable: coverage, import time, tool count, schema count, and smoke tests.

### Module Split 1: `tool_registry.py`

Current issue:

- `src/td_mcp/tool_registry.py` is too large and mixes service startup, helpers, resources, and all tool groups.
- Coverage is still low because the file is too broad to test surgically.

Target structure:

```text
src/td_mcp/registry/
  __init__.py
  app.py                  # owns FastMCP instance and register_all()
  context.py              # _get_services, _get_client, service helpers
  resources.py            # all td:// resources
  telemetry.py            # _start_tool, error recording helpers
  tools/
    core.py               # info, health, nodes, params
    graph.py              # create/connect/delete/layout
    exec.py               # td_exec_python and safety integration
    project.py            # lifecycle, undo, timeline
    memory.py             # technique/preference tools
    knowledge.py          # docs/cards/brains tools
    vision.py             # screenshots, monitor, streaming
    planning.py           # plan/analyze/macro tools
    dynamics.py           # optimizer/dynamics tools
    td2025.py             # native TD 2025+ tools
```

Registration pattern:

- Each module exposes `register(mcp: FastMCP) -> None`.
- `registry.app.register_all(mcp)` imports modules and registers tools.
- `tool_registry.py` remains as a compatibility shim:
  - Creates/exports `mcp`.
  - Imports/registers all modules.
  - Re-exports commonly imported helpers during v1.5.x.

Testing:

- Tool schema snapshot must not change during pure split commits.
- Registry smoke must still report 92 tools, 6 resource templates, 1 static resource.
- Add per-module tests for registration and key helper behavior.

Acceptance:

- No single registry module over about 900 lines.
- Coverage for newly split modules above 75%.
- `tool_registry.py` becomes a shim, not the place new code is added.

### Module Split 2: Models

Current issue:

- `src/td_mcp/models/_legacy.py` is a giant compatibility pile.

Target structure:

```text
src/td_mcp/models/
  __init__.py             # re-export stable public names
  core.py
  graph.py
  params.py
  exec.py
  memory.py
  knowledge.py
  vision.py
  planning.py
  dynamics.py
  td2025.py
  _legacy.py              # temporary re-export shim, deprecated
```

Steps:

1. Move models by domain without changing class names.
2. Keep `models.__init__` re-exporting everything.
3. Keep `_legacy.py` importing from the new modules for one release.
4. Add tests that all old imports still work.
5. In v1.6.0, consider deprecating direct `_legacy` imports.

Acceptance:

- No behavior/schema drift.
- Tool schema snapshot unchanged unless intentionally adding new tools.

### Module Split 3: TD Component Callback Source

Current issue:

- `td_component/mcp_webserver_callbacks.py` is a 3,000+ line TD-side monolith.
- It is hard to test, hard to format, and expensive to touch because `.tox` freshness matters.

Target structure:

```text
td_component_src/
  callbacks_main.py
  auth.py
  router.py
  serialization.py
  node_ops.py
  param_ops.py
  exec_ops.py
  project_ops.py
  monitor_ops.py
  geometry_ops.py
  td2025_ops.py

td_component/mcp_webserver_callbacks.py
  # generated/bundled TD runtime file
```

Build approach:

- Add `scripts/build_td_callbacks.py`.
- It concatenates or bundles `td_component_src` into the single TD DAT-compatible file.
- The generated file is committed because the `.tox` build needs it.
- Add a header saying "generated from td_component_src".

Testing:

- Unit-test pure helper modules in normal Python.
- Add generated-file freshness check, similar to `.tox` freshness.
- Keep TD runtime globals isolated behind adapter functions.

Acceptance:

- Most TD-side logic becomes testable without TouchDesigner.
- `.tox` rebuilds happen only for real TD-side behavior changes.

## v1.5.0: Creative Patching Layer

The refactor should not only make code tidier. It should unlock a better way to work.

### New Concept: Patch Session

Add a first-class "patch session" abstraction around multi-step creative edits.

Patch session lifecycle:

1. Inspect current graph.
2. Draft a patch plan.
3. Preview operations and risks.
4. Apply inside one undo block.
5. Validate with errors, cook stats, and optional frame capture.
6. Offer keep/revise/undo.
7. Save successful result as technique memory.

Suggested models:

```text
PatchPlan
  id
  intent
  target_root
  operations[]
  required_ops[]
  risk_flags[]
  undo_label
  validation_plan

PatchOperation
  kind: create_node | set_params | connect | layout | annotate | macro
  target
  args
  depends_on[]

PatchResult
  status
  created_paths
  changed_params
  validation
  before_snapshot_id
  after_snapshot_id
  undo_label
```

Suggested tools:

- `td_patch_plan`: turn an intent into a structured patch plan.
- `td_patch_preview`: summarize exactly what will change.
- `td_patch_apply`: apply the plan in one undo block.
- `td_patch_validate`: run errors/cook/frame checks after apply.
- `td_patch_variations`: generate 2-4 plan variants from the same intent.

This can start as an internal layer used by existing tools before exposing all of it as public MCP tools.

### Creative Recipe Library

Ship a small set of high-quality creative patch recipes. Do not make them demos; make them useful building blocks.

Initial recipes:

- Feedback trails TOP network.
- Audio-reactive displacement.
- Instancing field with noise controls.
- GLSL-ready reaction diffusion scaffold.
- Particle/POPx attractor field when POPx brain is available.
- Pixel sorting / slit-scan starter.
- Palette-driven color remapper.
- Camera + render + post stack.

Each recipe should include:

- Required operators.
- Parameters exposed as controls.
- Layout strategy.
- Validation checks.
- Knowledge links from DocsBrain where relevant.
- Memory tags for future recall.

### Better Validation Loop

After every patch apply:

- `td_get_errors` on target root.
- Cook/fps summary.
- Optional capture/analyze for visual non-blankness.
- Operator compatibility check against current TD build.
- State diff from before/after snapshots.

Return:

- `status`: `clean`, `warnings`, `broken`.
- `next_actions`: concrete repair suggestions.
- `undo_available`: true/false.

### Knowledge-Aware Patching

Use the DocsBrain and recipe library to make better decisions:

- Before creating an operator, check current build compatibility.
- When setting uncommon parameters, include source/provenance.
- When a user asks for an effect, retrieve relevant snippets/recipes first.
- When POPx/paketa12 brains are active, allow creative suggestions grounded in those sources.

### Memory That Learns From Success

When a patch validates cleanly:

- Offer to save it as a project technique.
- Auto-tag with operators, families, visual goal, and complexity.
- Store before/after summary and validation result.
- Later, `td_memory_recall` can suggest real prior project patterns before generating new ones.

## v1.5.0 Delivery Plan

### Phase 1: Refactor Without Behavior Change

Tasks:

- Split registry modules behind `tool_registry.py` shim.
- Split model modules behind `_legacy.py` shim.
- Move shared helpers into `registry/context.py`, `registry/telemetry.py`, and `registry/resources.py`.
- Keep schema snapshot unchanged.

Acceptance:

- 92 tools unchanged.
- Resource counts unchanged.
- Full suite green.
- Coverage floor raised to 65 if practical.

### Phase 2: TD Callback Source Split

Tasks:

- Create `td_component_src`.
- Add callback bundler script.
- Generate current `td_component/mcp_webserver_callbacks.py`.
- Add freshness check for generated callback file.
- Rebuild `.tox` only after behavior-affecting TD changes.

Acceptance:

- Generated callback matches source bundle.
- TD component freshness checks stay meaningful.
- Unit tests cover auth/router/exec helpers outside TD.

### Phase 3: Patch Session MVP

Tasks:

- Define patch plan/result models.
- Implement internal planner and applier for a small operation set:
  - create node
  - set params
  - connect
  - layout
  - annotate/comment/color
- Wrap apply in undo block.
- Record before/after snapshot.
- Validate after apply.

Acceptance:

- One end-to-end test with fake TD client.
- One live TD smoke script for a small visual patch.
- No public schema churn unless tools are intentionally added.

### Phase 4: Creative Recipe Pack

Tasks:

- Add 6-8 curated recipes.
- Add recipe tests against fake TD client.
- Add docs and examples.
- Add macro-to-patch-plan adapter so recipes use the same apply/validate pipeline.

Acceptance:

- User can ask for a feedback trail, audio reactive rig, or instancing field and get a structured, undoable, validated patch.

### Phase 5: Release Polish

Tasks:

- Update README and docs around the new patch flow.
- Add `/td-patch` and `/td-variations` slash-command docs if plugin commands support it.
- Run live TD E2E, benchmark, soak, and package smoke.
- Raise coverage ratchet if stable.

Acceptance:

- Fresh install works.
- Patch workflow works.
- Existing 92-tool workflows still work.
- The release feels like a practical creative upgrade, not just a code cleanup.

## Practical Priority Order

1. Fix auth bootstrap first. Nothing matters if first install fails.
2. Fix brain activation second. Broken brain allow-lists create confusing invisible behavior.
3. Fix DocsBrain parameter normalization third. It makes knowledge tools feel real instead of decorative.
4. Fix `init --print-only` fourth. It is small but important for trust in CLI behavior.
5. Split Python registry and models.
6. Split TD callback source.
7. Build patch session MVP.
8. Ship creative recipes.

## Non-Goals

- Do not add many new public tools before the registry split is stable.
- Do not hide auth failures again; either bootstrap correctly or document local no-auth mode.
- Do not claim resources are live until they really are.
- Do not treat `td_exec_python` as the main creative interface. Prefer typed graph operations and patch plans.
- Do not make the recipe system a pile of opaque Python snippets. Recipes should be structured and inspectable.

