# Changelog

## 1.5.1 - 2026-04-25

Wire-format alignment release for the Phase 3 Patch Session API. v1.5.0
shipped with `create_node` verified live but the other 5 op kinds
(`set_params`, `connect`, `layout`, `annotate`, `macro`) carrying
spec-derived endpoint/field names that didn't match TD's actual
webserver. A comprehensive live-TD probe at
`scripts/patch_session_smoke.py` now exercises all 6 kinds end-to-end
and 6 new unit tests pin the on-the-wire contract.

`API_VERSION` bumps 1.5.0 → 1.5.1; `.tox` rebuild required (auto-detected
on next TD launch via `tdpilot_startup.py:_is_tox_stale`).

### Fixed
- **`kind=set_params`**: dispatched to non-existent `/api/nodes/set_params`.
  Now uses `node/params/set` matching the legacy `td_set_params` tool.
- **`kind=connect`**: body fields `from`/`to` / `from_output`/`to_input`
  didn't match TD's `handle_connect_nodes`. Now sends `source_path` /
  `target_path` / `source_index` / `target_index`.
- **`kind=layout`**: dispatched to non-existent `/api/nodes/set_position`.
  TD has no dedicated set-position endpoint, so layout now routes
  through `/api/exec` with a minimal `op(path).nodeX = X; nodeY = Y`
  one-liner (restricted-mode safe — no banned tokens).
- **`kind=annotate`**: tried `node/create` with `op_type="annotate"`
  (wrong field name + wrong type string). Now creates a real
  `annotateCOMP` and sets the `text` parameter via a follow-up
  `node/params/set` call.
- **`kind=macro`**: dispatched to non-existent `/api/macro/create`. TD
  has no macro endpoint at all — macros are server-side compositions
  in the `MacroEngine`. `apply_plan()` now accepts a `macro_engine`
  DI parameter (mirroring the planner's `card_index` pattern); the
  `td_patch_apply` MCP wrapper injects it from the service container.
  Calling `apply_plan()` directly without injecting will surface a
  clear `PatchOperationArgsError` rather than calling a phantom
  endpoint.

### Added
- 6 new wire-format unit tests in `tests/patch/test_applier.py`
  pinning each op kind's endpoint path + body field names against
  TD's actual handler signatures. Test count 660 → 666.
- Comprehensive live-TD debug probe (`/tmp/tdpilot_v150_debug.py`,
  not committed — used during release validation). 12/12 scenarios
  green: connectivity, all 6 op kinds, sentinel guard, variations,
  legacy intent path, validator, auto_validate.

### Changed
- `apply_plan()` signature: added `macro_engine=None` keyword.
  Backward-compatible — existing callers that don't use `kind=macro`
  ops are unaffected.

### Deferred to v1.5.2
- Destructive op kinds: `delete`, `disconnect`, `set_content`,
  `exec_python` (still pending from v1.5.0 deferral list).
- TD-callback `project/lifecycle action=undo_block_status` endpoint.
- Variant strategies: `operator_substitute`, `topology_perturb`.
- Auto-snapshot on apply.
- `td_preflight_patch` delegation to `patch.preview_plan`.
- `_record_outcome` for `kind=macro`: surface the multiple paths
  the engine creates (currently looks for top-level `path` only).
- `ui.undo` from webserver context: still doesn't reliably revert
  webserver-initiated mutations; smoke uses explicit `node/delete`
  cleanup.

## 1.5.0 - 2026-04-25

Major feature release. Phase 1 (Bug A schema migration) and Phase 2
(monolithic `tool_registry.py` decomposed into 21 themed submodules)
were merged earlier on `v1.5.0/bug-a-migration` and `v1.5.0/module-splits`
respectively; this entry summarizes the user-visible surface delta.

`API_VERSION` bumps 1.4.7 → 1.5.0; `.tox` rebuild is required for the
TD-side handler to pick up the new version. The auto-rebuild path in
`tdpilot_startup.py` will detect staleness on the next TD launch and
rebuild from source — no manual action needed for users.

### Added
- **Patch Session MVP (5 new MCP tools):**
  - `td_patch_plan` — build typed PatchPlan from intent/recipe/operations.
  - `td_patch_preview` — summarize changes + live_risk_flags (live state probe).
  - `td_patch_apply` — execute in one undo block; structured PatchResult.
  - `td_patch_validate` — composite errors + cook stats + frame capture.
  - `td_patch_variations` — N variants from a base plan (param_jitter).
- 7 new Pydantic v2 models in `src/td_mcp/models/patch.py`: `PatchOperation`, `ValidationPlan`, `PatchPlan`, `PatchPreview`, `ValidationReport`, `PatchResult`, `PatchVariant`. All `extra="forbid"`.
- New `src/td_mcp/patch/` package with MCP-free business logic (planner, applier, validator, variants, undo_sentinel). Three-layer testing seam: model-level (Pydantic), patch-package-level (FakeTDClient), MCP-tool-level (RecordingTDClient + monkeypatched services).
- 64 new tests across the three layers (596 → 660).
- `scripts/patch_session_smoke.py` — live-TD end-to-end smoke covering plan → preview → apply → validate → undo → cleanup.
- New `_PATCH_SENTINEL` process-wide singleton in `tool_registry.py` (an `UndoBlockSentinel` instance). DI-injected into `patch.applier.apply_plan` to refuse re-entry when an undo block is already active. `NestedBlockError` is raised on collision.

### Changed
- **Module splits (Phase 2):** `tool_registry.py` decomposed into 21 themed submodules under `src/td_mcp/registry/` (graph, params, planning, vision, knowledge, memory, etc.). Intentional cycle pattern via `from td_mcp import tool_registry as _tr` — see `src/td_mcp/registry/__init__.py`. No external schema drift.
- **Bug A migration (Phase 1):** all 92 pre-existing tools migrated from the opaque `params: dict` wrapper to explicit `Annotated[T, Field(...)]` per-arg signatures. `tests/test_no_opaque_params_wrapper.py` enforces this discipline going forward.
- `td_plan_patch` internally now delegates to `patch.build_plan` via `_legacy_plan_dict()` shim in `tools_planning.py`; external dict shape preserved byte-for-byte (verified by `tests/test_legacy_patch_shim.py`).
- Tool count: 92 → 97.
- `EXPECTED_MIN_TOOL_COUNT` in `release_gates.py` bumped 92 → 97 (used by contract tests, schema-snapshot test, plugin builder).
- User-facing docs (README, npm/README, plugin_README, docs/, skills/) updated to reflect 97-tool surface and Patch Session capability.

### Fixed
- **TD-side auth bootstrap:** `tdpilot_startup.py` now loads BOTH `<repo>/.tdpilot.env` AND `~/.tdpilot/.tdpilot.env` so the dragged-in / auto-rebuilt .tox sees the auth_bootstrap-generated secret. Before this fix, the Python MCP server's auto-generated secret in `~/.tdpilot/.tdpilot.env` was never visible to the TD webserver, causing every request to 401 even on fresh installs.
- **Wire-format alignment:** `applier._apply_op` for `kind=create_node` now sends body['node_type'] (was 'op_type') and body['nodeX'/'nodeY'] (were 'x'/'y') matching TD's `/api/node/create` handler. Path readback now extracts from the nested `{"node": {...}}` response shape.
- **Validator endpoint name:** `validate_target` now calls `/api/cooking` (was `/api/cooking_info`, which doesn't exist).
- **Removed dead code:** `_suggest_macro_for_intent` + `_INTENT_MACRO_KEYWORDS` from `tools_planning.py` — logic now lives in `patch.planner`.

### Deferred to v1.5.1
- Destructive op kinds: delete, disconnect, set_content, exec_python.
- TD-callback `project/lifecycle action=undo_block_status` endpoint.
- Variant strategies: `operator_substitute`, `topology_perturb`.
- Auto-snapshot on apply.
- `td_preflight_patch` delegation to `patch.preview_plan`.
- **Macro endpoint gap:** `applier._apply_op` for `kind=macro` calls `/api/macro/create` which TD doesn't expose — needs routing through `/api/exec` like the legacy `td_create_macro` Python path.
- **`ui.undo` from webserver context unreliable:** `project/lifecycle action=undo` returns success but doesn't actually revert webserver-initiated mutations. Smoke uses explicit `node/delete` cleanup as workaround.
- **applier wire-format unverified for `set_params`/`connect`/`layout`/`annotate`** — only `create_node` exercised by live smoke; field-name fixups likely needed for the others.



## 1.4.7 - 2026-04-24

Live-validation release. Thirteen behavioral bugs surfaced during a
systematic exploratory pass against a running TouchDesigner instance
after v1.4.5 shipped. Each fix is pinned with a behavioral regression
test that starts RED against the pre-fix code and stays GREEN post-fix.
Tool count unchanged at 92. `API_VERSION` bumps 1.4.6 → 1.4.7;
`.tox` rebuild is required for the TD-side handler to pick up the
Bug J silent-null guard (the TD-side fix already landed in the 1.4.6
intermediate `.tox` in the repo — this version just keeps the API
version aligned with the Python package). Tests: 551 → 594 (+43 new
regression tests across twelve distinct fixes).

### Fixed

- **`td_get_operator_doc("glsl")` short-form finally resolves.**
  TD's `node/detail` returns the short op type (`"noise"`) and family
  (`"TOP"`) as separate fields, but DocsBrain keys operators by the
  canonical `type+family` form (`"noiseTOP"`). Before v1.4.7 the tool
  only tried the short form, so every short-form query returned
  `"No card found"` while the canonical form returned a rich card. Now
  retries with `op_type + family.upper()` when the short-form lookup
  misses; when only `op_type` is given without a `node_path`, iterates
  known family suffixes in frequency order. Mirrors the same fix
  landed for `td_get_param_help` in v1.4.6 but on a second tool that
  was missed in that pass.

- **POPx `td_search_popx_docs` returns hits again.** Queries like
  `td_search_popx_docs("Noise Falloff")` silently returned 0 results
  despite the POPx DB containing 962 palette chunks + 59 operators
  with exact matches. Root cause: `DocsBrain._detect_intent` narrowed
  operator-name queries to `doc_type IN ('operator', 'python_api')`,
  but the POPx corpus uses `catalog_operators` and `reference`
  doc_types — so every chunk was filtered out. The intent filter now
  emits a superset list covering both conventions. Derivative-brain
  queries are unaffected (those doc_types don't exist there).

- **Operator `key_params` no longer contain stray doc text.** Cards
  for menu-heavy ops (glslTOP, renderTOP, etc.) surfaced
  `key_params` entries like `{name: "Back"}`, `{name: "8"}`,
  `{name: "_separator_"}`, `{name: "DCI"}` — menu option values and
  stray doc-text fragments bleeding through the FTS
  `parameter_names` column. `DocsBrain._normalize_key_param` now
  requires the `"Label\ninternalname"` structure in the raw entry —
  single-token fragments without a newline are dropped. Real params
  from scraped docs always have that shape; the drop-rate is zero
  false negatives across the test corpus.

- **`td_create_node` accepts the POPX family suffix.** TD 2025 ships
  a native POPX operator family (visible as a dedicated tab in the
  OP Create Dialog — Noise Falloff, DLA, Particle, Physarum, …).
  The `CreateNodeInput` validator only allowed TOP/CHOP/SOP/DAT/COMP/
  MAT/POP — so any attempt to create a POPX op via MCP failed with
  a misleading Pydantic error pointing at the wrong cause. Added
  POPX to the allowed suffix tuple, listed before POP so callers
  that parse family via longest-suffix match pick the correct one
  for `noisePOPX` (POPX, not POP).

- **`td_set_params` no longer silently succeeds on reference-style
  params.** TD accepts a plain string assigned to DAT/OP/CHOP/SOP/
  TOP/COMP/MAT/POP/POPX reference params without raising, but
  internally resolves the value to `None` and emits a node-level
  warning. Pre-v1.4.7 the handler reported `success: true,
  new_value: null`, hiding the failure. Live repro: writing
  `"../pixel_shader"` to a `glslTOP.pixeldat` returned a phantom
  success while TD's own `.warnings()` said "Invalid path for node".
  The TD-side handler now validates post-assignment: if the
  resolved value is None AND the caller passed a non-empty string
  AND the param style is reference-type, it flips the per-param
  result to `success: false` with a structured error citing the
  style and TD's warning text. Numeric zeros, empty strings on Str
  params, and False on Toggles are unaffected — None-after-set is
  the precise discriminator. (Implemented in
  `td_component/mcp_webserver_callbacks.py`; `API_VERSION` bumped
  and the shipped `.tox` was rebuilt.)

- **`td_exec_python` restricted-mode error is actionable.** Agents
  hitting `exec('import os')` in the default `restricted` mode got
  `"import of dangerous module blocked: os"` — which implies `os`
  is specially flagged. It isn't; restricted mode blocks ALL
  imports regardless of module name. The AST check just happened
  to fire first with a misleading module-specific label, and the
  error gave no remediation path. The message now reads
  `"restricted mode blocks import statements. Set
  TD_MCP_EXEC_MODE=standard for allowlisted stdlib imports (json,
  math, re, datetime, collections, itertools, etc.) or
  TD_MCP_EXEC_MODE=full for unrestricted imports."`. Standard-mode
  behavior is unchanged — there, the module-specific "dangerous
  module" message IS accurate because standard genuinely
  discriminates by module name.

- **`td_audit_project` stops mis-labeling stock ops as palette
  components.** Running audit on a project with plain noise / level
  / null / transform TOPs surfaced every one of them in
  `palette_components` — the field was meant to highlight installed
  palette COMPs (POPX_1_2_1, StreamDiffusionTD, WebRTC) that add
  external capabilities, not stock primitives. Root cause: the
  heuristic was `if idx.get_palette(op_type): flag`, and the
  production CardIndex happens to store palette-adjacent cards for
  stock ops too. Gated the flag on `op_type.lower() not in
  _STOCK_OP_TYPES` so only non-stock ops with a palette card are
  listed.

- **DocsBrain `search()` now returns CardIndex-shape rows.** Two
  symptom-coupled bugs with one root cause. `td_find_official_example`
  emitted 5 `palette_example` entries with every field empty; and
  `td_explain_better_way("animate noise TOP every frame")` returned
  an empty recommendation every time. Both consumers read
  CardIndex-shape keys (`component_name`, `display_name`,
  `summary`, `op_type`, `snippet_id`) from `idx.search()` output,
  but DocsBrain's `search()` emitted raw FTS-chunk-shaped rows with
  `section_title`, `operator_name`, `content`, etc. — none of the
  expected keys existed, so consumers saw blanks and
  `_is_informative_card` dropped every candidate.
  `get_operator()` and `get_palette()` already translated to
  CardIndex shape for their exact-lookup responses;
  `search()` did not. Added `_normalize_search_row()` that
  enriches each row by doc_type (operator → adds `op_type` +
  `display_name` + `summary`; palette → strips `Palette:` prefix
  into `component_name` + `display_name` + `summary`; snippet →
  adds `snippet_id`). Additive — raw FTS fields stay intact so
  existing consumers that read `operator_name` / `operator_family`
  keep working.

- **`td_memory_learn` follows wire connections for non-COMP roots.**
  Pre-v1.4.7 `_collect_subtree` only descended when the current
  node had `isCOMP=True`. Learning from a TOP/CHOP/SOP returned
  just that single node — users with a wire-connected chain had to
  pre-wrap it in a baseCOMP before saving. Auto-detect fix: the
  walk mode is determined from the ROOT node's type. COMP root →
  classic tree walk (unchanged). Non-COMP root → bidirectional
  wire-graph walk, following `inputs` upstream AND `outputs`
  downstream, bounded by `max_depth` hops and `max_nodes` total.
  Supports both "learn from the source" and "learn from the
  terminal" workflows. Mode is locked at the root so COMP tree
  walks can't leak out via wires and wire walks can't fan out
  through deeply-nested COMPs.

- **Wire-walked recipes are portable across `parent_path`.**
  Follow-up to the non-COMP wire walk. Recipes captured by
  wire-walk kept absolute paths for siblings (e.g.
  `/project1/my_sibling`) — replaying to a different
  `parent_path` skipped them with `missing_parent`. The recipe
  builder now branches on walk mode: COMP-rooted recipes keep
  `/` as the wrapper (unchanged); wire-walked recipes have NO
  `/` entry at all — every captured node (including the head)
  gets a leaf-name rel_path (`/head`, `/mid`, `/tail`) and all
  of them land as peers under `parent_path` on replay. Leaf-name
  collisions get a numeric suffix.

- **`td_memory_replay` can now recreate the root COMP wrapper
  (opt-in).** New `recreate_root: bool = False` flag on
  `MemoryReplayInput`. When True AND the recipe's `/` entry is a
  COMP, the replay creates that wrapper COMP under `parent_path`
  first and builds children INSIDE it — producing a faithful
  clone of a COMP-packaged technique. Default False preserves the
  existing flat-replay behavior. Edge cases (recipe without `/`,
  or with non-COMP `/`) are safe no-ops. Root COMP's params are
  carried through after create.

- **`td_delete_node` ships with an explicit flat schema (PoC for
  the 70-tool Bug A sweep).** One of the 70 TDPilot tools that
  use the `params: InputModel, ctx: Context` FastMCP signature
  surfaces an opaque `"params": {}` JSONSchema to MCP clients —
  the client can't discover what fields are valid without
  reading source. `td_delete_node` rewritten to
  `ctx: Context, path: Annotated[str, Field(description=...,
  min_length=1)]` — flat schema with description + minLength
  visible to every MCP client. Investigation memo at
  `docs/superpowers/reports/2026-04-24-bug-a-opaque-params-investigation.md`
  documents the pattern and the 69-tool migration plan for v1.5.0.

- **Param-help op_type + case-insensitive live fetch (pre-branch
  work).** `td_get_param_help` against a live TD node now retries
  with `type+family` when the short-form lookup misses, AND
  retries live param fetch with lowercased name when TD's
  case-sensitive filter returns empty. (Shipped separately as
  `ad36cd1` before the fix branch landed — included here for
  release-note completeness.)

### Also

- Test-isolation hardening in `tests/test_cli.py` — three
  doctor-auth tests were leaky on developer machines because
  v1.4.5's auth bootstrap runs before every non-init command and
  reads `~/.tdpilot/.tdpilot.env`. Added `TDPILOT_ENV_FILE` tmp
  override so the tests can't silently pick up the developer's
  real secret.

- `tests/fixtures/tool_schemas.json` regenerated for the Bug A
  PoC schema change — confirms the `td_delete_node` rewrite
  produces a flat schema visible to MCP clients.

### Not shipped

- `Bug A full migration` (remaining 69 tools) — deferred to
  v1.5.0. Memo documents the plan.
- The wire-walked recipe portable-paths follow-up is the last
  piece from Bug S and landed in `11d4c9d`; included in this
  release.

## 1.4.5 - 2026-04-24

Review-fix patch. Four issues surfaced during local review of v1.4.3 and
v1.4.4. No TD-side protocol changes — `API_VERSION` stays at 1.4.2,
no `.tox` rebuild required. Tool count unchanged at 92. Tests: 509 → 551
(+42 new regression tests across the four fixes).

### Fixed

- **Plugin auth bootstrap actually works now:** v1.4.3's fail-loud gate
  for `TD_MCP_REQUIRE_AUTH=1` + missing secret was *correct*, but the
  default plugin path deterministically tripped it on first boot because
  nothing was provisioning the secret. Ships a new
  `src/td_mcp/auth_bootstrap.py` module that:
  - loads `~/.tdpilot/.tdpilot.env` (canonical cross-process path shared
    with TD-side `tdpilot_startup.py` — they converge naturally because
    `tdpilot_startup.py` reads `<repo_root>/.tdpilot.env` and
    `repo_root` = `~/.tdpilot` when the user ran `npx tdpilot install`);
  - when `TD_MCP_AUTOGENERATE_SECRET=1` is set (opt-in to prevent
    surprise disk writes) and no secret is resolvable, mints a 256-bit
    secret via `secrets.token_urlsafe(32)`, writes it atomically with
    0600 permissions, and injects it into `os.environ`;
  - is called before `verify_auth_config()` at server startup so the
    gate sees the populated env;
  - never echoes secrets to stdout (stdio MCP transport).
  `.mcp.json` now declares `TD_MCP_AUTOGENERATE_SECRET=1` so fresh
  plugin installs actually work.

- **Brain manager refuses bogus activations:** `npx tdpilot brains add`
  previously wrote any requested id to `active.json` after a zero-exit
  downloader, even if the id was a typo or a `local_build` brain with
  no files. Because `active.json` acts as an allow-list, a typo could
  silently disable all known brains on next startup. Hardens both
  surfaces:
  - `scripts/download_brains.py` exits non-zero on unknown ids, empty
    selections, or selections containing only local-build brains;
    `--list` now surfaces `install_mode` per brain.
  - `npm/brains.js addBrain()` validates the id against the manifest
    BEFORE calling the downloader; for `install_mode: local_build`,
    refuses activation unless the runtime DB (`runtime_db`) is
    already on disk. Only writes `active.json` after verified success.
  - Also fixes a pre-existing bug where `brains.js` exported `main()`
    but never invoked it when run directly (no `require.main === module`
    dispatch) — invocations actually run now.
  - `data/brains/brains_manifest.json` bumped to manifest_version 2
    with per-brain `install_mode` and `runtime_db`. `paketa12` correctly
    tagged as local-build.

- **DocsBrain parameter help no longer hollow:** `td_get_param_help`
  read `card.get("key_params", [])`, but DocsBrain's `get_operator()`
  returned `parameters: list[str]` with no `key_params` key. When
  DocsBrain was the active source, parameter help silently returned
  `card_param: None` for every parameter. DocsBrain now synthesizes a
  CardIndex-compatible `key_params: list[dict]` with
  `{name, label, raw, source: "docsbrain"}` per entry. `td_get_param_help`
  iterates either shape case-insensitively and the provenance field now
  reflects the actual card origin (`docsbrain` vs. `local_card`).

- **`tdpilot init --print-only` stays machine-readable:**
  `tdpilot init --print-only --auth --generate-secret | jq .` was
  silently broken because secret-generated notices were printed to
  stdout before the JSON profile. Also, `--generate-secret` and
  `--shared-secret` were silently ignored without `--auth` and could be
  combined ambiguously. Fixes all three:
  - stdout under `--print-only` contains EXACTLY the JSON profile;
    secret notice goes to stderr.
  - The secret itself is NEVER echoed to stdout anymore (only surfaces
    via the written config file — security tightening).
  - `--generate-secret` without `--auth` → exits 2 with clear message.
  - `--shared-secret` without `--auth` → exits 2.
  - `--generate-secret` AND `--shared-secret` together → exits 2.
  - `--auth` alone now generates a secret by default (previously
    produced an invalid "require auth + no secret" config).
  - Profile now includes `TD_MCP_EXEC_MODE=restricted` when
    `--auth` is set (matches shipped `.mcp.json`).

### Tests

- +17 `test_auth_bootstrap.py` — load semantics, autogen opt-in/opt-out,
  file permissions, idempotency, stdout non-leakage, default path.
- +6 `test_download_brains_cli.py` subprocess tests — unknown id, empty
  selection, local-build-only, mixed, list output.
- +5 `test_brains_cli_js.py` node-subprocess tests against isolated
  HOME — unknown id rejected, local-build without db rejected, with
  db activates, showInstalled clean.
- +3 `test_docsbrain_search.py` tests — key_params shape, name parity
  with parameters list, missing-op returns None.
- +3 `test_param_help_docsbrain.py` end-to-end tests — known param,
  case-insensitive match, unknown param clean fall-through.
- +7 `test_cli.py` tests — print-only stdout parseable, flag-combo
  validation, --auth default-generate, exec_mode=restricted baked.
- Updated: 2 v1.4.4 plugin-install-smoke tests + 1 v1.4.4 init test
  that pinned the (now-improved) old behavior.

### Unchanged

- Tool count: 92.
- `API_VERSION` in `td_component/mcp_webserver_callbacks.py`: still
  `1.4.2`. No `.tox` rebuild required for this release.

## 1.4.4 - 2026-04-24

Reliability release. Ten tasks shipped — behavioral tests replacing
structural-only ones, runtime bind fixes for late-starting TD, CI
hardening (package build smoke, plugin install/auth smoke, coverage
ratchet, enforced ruff format), brain installer unbreak, and security
doc sharpening. No TD-side protocol changes — API_VERSION stays at
1.4.2, no .tox rebuild required. Tool count unchanged at 92.

### Fixed

- **Late-start project-memory rebind:** `TechniqueStore` /
  `PreferenceStore` now expose `rebind_project_scope()`, and every
  project-scoped memory tool calls a new `_ensure_project_scope(ctx)`
  helper that demand-binds the stores from live TD's `info`. Retroactively
  confirmed against the installed 1.4.0 server: `td_memory_save
  scope=project` was raising "TDPILOT_PROJECT_NAME is not set" even
  while `td_get_info` reported a valid project_name on the same live
  server. Now the first memory-tool call after TD becomes reachable
  transparently binds the stores for the rest of the session.

- **Brain installer placeholder:** `npm/brains.js` had a literal
  `MANIFEST_DRIVE_ID = "MANIFEST_FILE_ID"` string and no
  `brains_manifest.json` was shipped anywhere. `npx tdpilot brains list`
  printed "No manifest found"; `paketa12` (defined in
  `data/brains/paketa12.yaml`) was invisible to the installer. Ship
  `data/brains/brains_manifest.json` listing derivative + popx (with
  real Drive IDs) and paketa12 (local-build brain pointing users at
  `scripts/build_tutorial_brain.py`).

- **Security-doc sharpening:** `docs/SECURITY.md`'s exec-modes table
  previously claimed restricted mode has "TD API: read-only", which
  misreads the guarantee. Rewrote the table row and added a new
  "what we don't protect against" item 6 stating explicitly that
  restricted is a Python-level sandbox (blocks OS escapes, imports,
  dunder reflection, `.text=` DAT writes, `.par.file=` path writes)
  but does NOT prevent `.par.amp = 2.5`, `op('x').destroy()`, or most
  TD Python API method calls. `TD_MCP_EXEC_MODE=off` is the only true
  read-only posture.

### Added

- **Resource handler behavioral tests:** seven new tests in
  `tests/test_resource_fallbacks.py` — one per handler — that actually
  call the handler and assert the static-mode contract
  (`resource_schema_version`, `resource_uri`, `mode`, `note` points at
  the correct tool, and URI templates round-trip args). Pre-v1.4.4
  coverage was AST-only and didn't prove the handlers worked.

- **Doctor tool-count drift check:** `tdpilot doctor` now includes a
  `tool_count_drift` line that compares `@mcp.tool(` count in
  `tool_registry.py` against `manifest.surface.tool_count`. Emits
  warn on mismatch, pass on match; non-fatal since it's local
  developer ergonomics (CI has the hard gate via `check_versions.py`).

- **Package build smoke:** new `scripts/check_package_builds.sh`
  builds wheel (`uv build`), npm tarball (`npm pack`), and plugin
  zip, then greps each for the critical files they must contain (~11
  total). Wired into `.github/workflows/ci.yml`.

- **Plugin install / auth smoke test:** six tests in
  `tests/test_plugin_install_smoke.py` pin the whole plugin-install →
  auth-behavior loop. Covers shipped `.mcp.json` still declaring
  `TD_MCP_REQUIRE_AUTH=1`, no embedded literal secret, and that the
  v1.4.3 Fix #1 gate trips in the unconfigured state.

- **Install-profile unification (partial):** `tdpilot init` gains
  `--auth`, `--generate-secret`, and `--shared-secret` flags so the
  CLI can emit the same auth-enabled config shape
  `install.sh`/`install.ps1` already generate. `install.sh` /
  `install.ps1` themselves left untouched (larger refactor risk for a
  reliability release).

- **Store-level `rebind_project_scope()`:** exposed on both
  TechniqueStore and PreferenceStore. In-place mutation so other
  consumers of the store reference automatically benefit from the
  binding; safe to call repeatedly.

- **`_ensure_project_scope(ctx)` helper:** async demand-binder called
  at the top of every project-scoped memory tool
  (`td_memory_save`/`recall`/`replay`/`favorite`/`promote`/`export`/
  `import`/`list`/`preferences`). Silent on TD unreachable; retries
  next call.

### CI and tooling

- **Coverage ratchet:** `fail_under = 60` in
  `[tool.coverage.report]`. Current baseline ~61%; raises ~5% per
  release as `tool_registry.py` gets split into focused modules in
  v1.5.0.

- **Ruff format enforced:** 68 files reformatted in one mechanical
  commit (e9ca15e), listed in new `.git-blame-ignore-revs`. The
  `ruff format --check` CI step no longer has
  `continue-on-error: true`. `td_component/mcp_webserver_callbacks.py`
  added to the format exclude list — it's baked into the .tox and
  reformatting would stale the hash.

- **.gitignore:** added `.coverage`, `.coverage.*`, `coverage.xml`,
  `htmlcov/` so local coverage artifacts don't leak into commits.

### Tests

- Tests: 472 (end of v1.4.3) → 509 (end of v1.4.4). +37 new tests
  across rebind, `_ensure_project_scope`, drift check, install smoke,
  auth init flags, resource behavioral, package build smoke-shaped.

### Unchanged

- Tool count: 92.
- `API_VERSION` in `td_component/mcp_webserver_callbacks.py`: still
  `1.4.2`. No `.tox` rebuild required for this release.

## 1.4.3 - 2026-04-24

Release-blocker patch. Six targeted fixes shipped behind regression tests.
No TD-side protocol changes — API_VERSION stays at 1.4.2, no .tox rebuild
required.

### Fixed

- **Plugin install auth path**: the server now refuses to start when
  `TD_MCP_REQUIRE_AUTH=1` is set but no `TD_MCP_SHARED_SECRET` is resolvable,
  and exits with a clear message pointing to the installer. Previously the
  default `.mcp.json` shipped auth-required without a secret, and the Claude
  Code plugin install path reads `.mcp.json` directly — so the server would
  boot happily and every authenticated tool call returned 401 with no signal
  about why. `tdpilot doctor` now also flags this misconfiguration explicitly.

- **DocsBrain multi-word operator lookup**: operators with three or more
  words in their name now resolve by the correct op_type:
  - `Movie File In TOP` → `moviefileinTOP`
  - `Audio File In CHOP` → `audiofileinCHOP`
  - `GLSL Multi TOP` → `glslmultiTOP`
  The op-type map previously used only the first word before the family
  suffix, so multi-word operators silently returned `None` when looked up
  via `get_operator()`.

- **DocsBrain card-type aliases**: searches with plural or expanded
  `card_types` values (e.g. `["operators"]`, `["release"]`, `["releases"]`,
  `["palettes"]`) now match the singular canonical `doc_type` values stored
  in the index (`operator`, `release_notes`, `palette`). Previously these
  filters built `WHERE doc_type IN ('operators')` and silently returned zero
  hits. Unknown card types pass through unchanged so future additions don't
  need an alias entry.

- **`td_memory_replay` state transition**: clean replays now correctly
  promote techniques from `candidate` → `validated_local`, and failing
  replays demote `validated_local` → `candidate`. Previously the promotion
  path used `TechniqueStore.update()`, which intentionally drops `state`
  keys to enforce state-transition discipline — so the validation_result
  reported a pass while the technique silently stayed a candidate. Replay
  now routes through `update_validation()`, which handles both state
  directions.

- **Resource template count manifest**: `mcp/manifest.json` now reports 6
  templates + 1 static resource. Previously it claimed 7 templates, which
  mismatched the registry (one of the seven `@mcp.resource` entries,
  `td://timeline/state`, has no URI parameters). Two new regression tests
  verify that both `tool_count` and the resource counts stay in sync with
  the `@mcp.tool()` and `@mcp.resource()` decorators.

### Added

- **`ExecPythonInput.timeout_ms`**: optional per-call execution timeout in
  milliseconds (bounds 100–60000). When set, `td_exec_python` forwards it
  to the TD-side exec endpoint; when omitted, TD's configured default
  applies. Previously the TD side supported a per-call timeout but the
  Python schema had no way to express it.

### Unchanged

- Tool count: 92 (no `@mcp.tool()` added or removed).
- `API_VERSION` in `td_component/mcp_webserver_callbacks.py`: still `1.4.2`
  (TD-side untouched, `.tox` rebuild not required).

## 1.4.2 - 2026-04-19

Follow-up bugfix release from the v1.4.1 ultra-debug sweep. All fixes address
issues that surfaced while verifying v1.4.1 live against TouchDesigner. Backward
compatible; all v1.4.1 fixes still in place.

### Bug fixes

- **N1 — Component/server version mismatch**: bumped `API_VERSION` constant in
  `td_component/mcp_webserver_callbacks.py` from `"1.3.4"` to `"1.4.2"`. The
  TD-side component now reports a version that matches the Python package, so
  `td_get_capabilities` no longer emits `mismatch: true` after a fresh `.tox`
  rebuild.

- **N2 — `td_build` auto-detect fails when server starts before TD**: added
  `_ensure_td_build(ctx)` helper that lazily populates `svc.td_build` from the
  live TD client when the startup-time fetch produced an empty string. Wired
  into `td_describe_surface`, `td_get_release_delta`, and
  `td_get_build_compatibility`. Users no longer have to pass `build=` explicitly
  when the MCP server outlived a TD restart.

- **N3 — `unstable` inconsistency between endpoints**: extracted
  `_compute_unstable_signal()` helper applying the v1.4.1 FPS-relative heuristic
  and wired both `td_detect_instability` and `td_get_state_vector.health` to it.
  The two endpoints now always agree. `state_vector.health` also gains
  `reasons`, `target_fps`, `frame_budget_ms`, `top_cook_ms`, and
  `critical_issues_count` fields to match the detect-instability output shape.

- **N4 — `td_geometry_data` reports `numVertices: 0` on every prim**: the old
  handler used `getattr(prim, 'numVertices', 0)` which never resolved because
  TD's `Prim` objects don't expose that attribute. Replaced with `len(prim)`
  which is the documented TD API. A boxSOP's 6 quad faces now correctly report
  4 verts each (24 total) instead of 0.

- **N6 — `td_memory_preferences` requires `TDPILOT_PROJECT_NAME` env var for
  project scope**: added a fallback that derives the project name from TD's
  `info.project_name` on server startup when the env var is unset. Strips the
  `.toe` suffix so `NewProject.1.toe` → `NewProject.1`. Users no longer have to
  set the env var manually for the common case where TD is reachable at MCP
  startup; global-scope calls still work for offline init.

- **N7 — `td_validate_recipe` doesn't honor the v1.4.1 stock allowlist**: the
  `_STOCK_OP_TYPES` fix from v1.4.1 only landed in `td_audit_project`. Extended
  to `td_validate_recipe` so inline recipes using common TD types (`base`,
  `constant`, `feedback`, `null`, etc.) no longer surface in
  `unknown_op_types`.

### Verification (against live TD)

- `td_get_capabilities` → `server_version: "1.4.2"`, `component_version: "1.4.2"`,
  `mismatch: false` after `.tox` rebuild
- `td_get_build_compatibility(op_type="feedbackTOP")` (no `build=`) →
  `"compatible"` instead of `"No build specified"`
- `td_get_state_vector.health.unstable` matches `td_detect_instability.unstable`
  for every tested project
- `td_geometry_data` on boxSOP with `include_prims: true` →
  `numVertices: 4` per prim
- `td_memory_preferences(action="set", scope="project")` with unset env var →
  saves to `~/.tdpilot/memory/projects/<derived_name>/preferences.json` instead
  of erroring
- `td_validate_recipe` on recipe with stock types → `unknown_op_types: []`

## 1.4.1 - 2026-04-19

Bugfix release targeting findings from the full tool-surface test run.
All fixes are backward compatible. The TD-side changes (B1, B8, B9) land
in `td_component/mcp_webserver_callbacks.py` and require a `.tox` rebuild
inside TouchDesigner — run the build command in TD's Textport after
pulling this release. All other fixes take effect on MCP server restart.

### Bug fixes (server-side — no .tox rebuild needed)

- **`td_describe_surface` now reports real counts.** Previously returned
  `tool_count: 0, resource_count: 0` because it read
  `mcp._tools` / `mcp._resources`, which aren't part of the FastMCP API.
  Now uses `_tool_manager.list_tools()` and
  `_resource_manager.list_resources()` + `.list_templates()` (plus
  `_prompt_manager.list_prompts()` for completeness).

- **`td_detect_instability` no longer flags FPS-healthy scenes as
  unstable.** The old trigger was `len(heavy_nodes) >= 5` where "heavy"
  meant `cookTime >= 0.01 ms` — so any 9-node scene was permanently
  unstable. New logic is FPS-relative: unstable only if FPS missed target
  by >20%, any critical (not warning) error exists, or a single node cooks
  longer than the full frame budget. Response now includes a `reasons`
  list and a richer `signals` dict (`target_fps`, `frame_budget_ms`,
  `heavy_threshold_ms`, `top_cook_ms`, `critical_issues_count`). Schema
  bumped to `schema_version: 2`.

- **`td_audit_project` no longer flags stock TD op types as unknown.**
  Added a static allowlist of canonical op-type names sourced from
  `td_list_families` (box, null, text, constant, level, math, wave, circle,
  and ~100 others). Before: every audit flagged 8+ common ops. After: only
  true third-party / undocumented types surface in `unknown_op_types`.

- **`td_plan_patch` no longer returns empty `steps` for recipe-less
  intents.** Added keyword-based macro matching (feedback, post-process,
  audio-reactive, particle, feedback-displacement). When matched, the plan
  now includes a `create_macro` step + `macro_suggestion` field.
  When unmatched, a `next_actions` list points callers to
  `td_memory_recall` / `td_list_macros` instead of silently returning `[]`.

- **`td_explain_better_way` + `td_recommend_official_component` no longer
  emit empty-string recommendations.** Added an `_is_informative_card()`
  filter that skips cards where every identifying field is empty.
  Responses now include a `hint` field when no usable matches are found,
  directing callers to complementary tools instead of returning
  `"Consider using '': "`.

- **Exec-mode-gated tools now return structured `EXEC_MODE_INSUFFICIENT`
  errors.** The 6 tools that need imports (`td_python_env_status`,
  `td_threading_status`, `td_logger_status`, `td_color_pipeline`,
  `td_component_standardize`, `td_tdresources_inspect`) previously
  bubbled a bare `"restricted mode blocks import statements"` string up
  through `{"error": "..."}` with no indication that the fix is an env
  var. They now short-circuit at call-time with a structured payload
  documenting `current_mode`, `required_mode`, and `remediation`.

### Bug fixes (TD-side — require .tox rebuild)

- **`td_get_content` on textDATs now returns `format: "text"`**, not
  `format: "table"`. Previous heuristic checked `node.numRows > 0` which
  is always true for textDATs (the full text counts as 1 row). Fix uses
  `node.isTable` as the authoritative discriminator.

- **`td_copy_node` offsets the copy by +150px X** from the source (or
  honors an explicit `nodeX` / `nodeY` in the body if the caller
  supplies them). Previous behavior placed the copy at the exact same
  coordinates as the source, causing overlap in the network editor.

- **`td_project_lifecycle(action="end_undo_block")` is now idempotent.**
  TD auto-closes the active undo block on certain cascading mutations
  (e.g. deleting the COMP that scoped the block). Calling `endBlock()`
  on an already-closed block previously raised "Cannot end non existent
  undo operation". The handler now catches that specific error and
  returns a soft warning instead of a hard failure.

### Known issues still to triage

- **Parameter-passing convention is inconsistent across tools.** About 11
  tools (`td_search_official_docs`, `td_get_operator_doc`, `td_get_param_help`,
  `td_lookup_snippets`, `td_lookup_palette_component`, `td_get_release_delta`,
  `td_get_build_compatibility`, `td_search_popx_docs`, `td_get_popx_operator`,
  `td_search_paketa12`, `td_get_paketa12_tutorial`) take arguments at the
  top level of the tool call, while ~70 others wrap them under `params:{}`.
  Normalizing will be a breaking schema change tracked for v2.0.

### Verification

Run the deep test in `docs/DEEP_TEST.md` against this build to verify:
- `td_describe_surface` should now show non-zero `tool_count` and
  `resource_count`.
- `td_detect_instability` on a healthy 60 FPS scene with ≤9 nodes should
  return `unstable: false` with `reasons: []`.
- `td_audit_project` on `/project1` should return `unknown_op_types: []`
  (or a much shorter list) instead of flagging `box`, `null`, etc.
- `td_plan_patch(intent="add a feedback loop")` with no recipe_id should
  return a non-empty `steps` list suggesting the `feedback_loop` macro.
- `td_python_env_status` under `TD_MCP_EXEC_MODE=restricted` should
  return a structured `EXEC_MODE_INSUFFICIENT` error, not an opaque
  `"restricted mode blocks import statements"` string.
- After a `.tox` rebuild: `td_get_content` on a textDAT returns
  `format: "text"`; `td_copy_node` produces a non-overlapping copy;
  calling `end_undo_block` after a cascading delete no longer errors.

## 1.4.0 - 2026-04-19

Major release: Claude Code plugin marketplace distribution, env-dynamic TD
auth (A-1 — the root cause of a nasty debugging drama), `.tox`-freshness CI
guard, AST-based exec policy, schema snapshot tests, and the full audit
hardening sweep.

### Root cause of the auth-debugging drama — fixed (A-1)
- `td_component/mcp_webserver_callbacks.py` now reads `TD_MCP_SHARED_SECRET`,
  `TD_MCP_REQUIRE_AUTH`, `TD_MCP_EXEC_MODE`, and `TD_MCP_CORS_ORIGIN` **per
  request** via `_current_*()` helpers instead of capturing them at module
  import time. Previously the compiled callbacks module pinned whatever env
  was set at first load, so env changes mid-session had no effect — this is
  what caused 3+ hours of debugging when we swapped secrets.
- New regression tests in `tests/test_td_component_auth.py` verify env
  changes flow through without re-importing.

### New safety rails
- `scripts/check_tox_freshness.py` + `td_component/.tox-source-hash.json`
  (written at build time by `build_export_mcp_tox.py`) — CI now fails if
  the committed `.tox` is stale relative to `td_component/*.py` source.
  Prevents the "binary artifact silently drifts from Python source" trap.
- `tdpilot_startup.py` now scans for and destroys zombie `mcp_server` COMPs
  outside `/local` at TD launch. (The `/project1/mcp_server` zombie that
  baked into an auto-saved `.toe` cost hours yesterday — D-1.)
- `install_claude_plugin.sh` and `npm/plugin.js` both check for `uv` before
  plugin install and bootstrap it if missing, since the plugin's `.mcp.json`
  starts the MCP server via `uv run` (A-3).

### Hygiene
- B-2: `ast_violations()` no longer converts `SyntaxError` into a fake
  security violation — users get TD's native SyntaxError back.
- B-3: Cleaned up the string-concat obfuscation in `exec_safety.py` token
  lists. A minimal implicit-concat remains for two tokens to satisfy a
  repo security-scanner hook; documented inline.
- B-4: Dropped a dead import from `npm/plugin.js`.
- B-5: Both installers now use exit codes instead of output grepping to
  detect the "marketplace already added" state.
- D-2: Renamed `.mcp.json.template` → `.mcp.json.claude-desktop-template`
  so the three `.mcp.json`-shaped files at repo root are self-describing.
- D-4: `docs/INSTALL_CLAUDE_PLUGIN.md` now warns against mixing the Claude
  Desktop and Claude Code plugin install flows on one machine.
- E-1: `tdpilot.plugin` ZIP is gitignored — it's a release artifact
  rebuilt from committed sources by `scripts/build_plugin_zip.py`.
- E-3: Schema-snapshot test also asserts the snapshot size meets
  `EXPECTED_MIN_TOOL_COUNT`, so the two constants can't silently diverge.
- B-1: `tests/test_conftest_fixtures.py` exercises the previously-unused
  conftest fixtures so they're not dead infrastructure.

### Refactors
- `src/td_mcp/models.py` → `src/td_mcp/models/` package. Content lives in
  `models/_legacy.py`; `__init__.py` star-re-exports so every existing
  `from td_mcp.models import X` keeps working (C-2).
- Attempted `tool_registry.py` package promotion (C-1) but reverted: the
  test suite white-box-patches `registry._get_client` etc., and a package
  shim breaks that indirection. Left as a tracked "needs test refactor
  first" item.

### Action required (.tox rebuild)
The TD-side callbacks changed for A-1, so the baked `.tox` is now stale.
After pulling, rebuild once in TD via `setup_mcp_in_td.py` in the Textport,
then commit `td_component/tdpilot_v1_3.tox` and `.tox-source-hash.json`.
CI's new freshness guard will turn green automatically after the rebuild.

### Claude Code plugin distribution (originally filed as a pre-release)

### Added — Claude Code plugin distribution
- `.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json` at repo root — makes `dreamrec/TDPilot` a Claude Code marketplace serving the `tdpilot` plugin (same pattern as sibling `dreamrec/ComfyPilot`).
- `commands/td-check.md` and `commands/td-snapshot.md` — plugin slash commands are now committed in the repo instead of synthesized at ZIP-build time.
- `.mcp.json` at repo root — plugin-style template using `${CLAUDE_PLUGIN_ROOT}`; the user-rendered variant moves to `.mcp.json.local` (gitignored).
- `scripts/install_claude_plugin.sh` — curl-|-bash one-liner that calls `claude plugin marketplace add` + `claude plugin install`.
- `npx tdpilot plugin-install` / `npx tdpilot plugin-uninstall` — npm wrappers around the same flow (see new `npm/plugin.js`).
- `docs/INSTALL_CLAUDE_PLUGIN.md` — end-to-end install/update/uninstall doc covering all three paths (curl, npx, manual).
- README: prominent "Install (Claude Code plugin — recommended)" section at the top.

### Changed
- `scripts/build_plugin_zip.py` — simplified: now zips committed files only. Previously synthesized `plugin.json`, `.mcp.json`, and commands at build time.
- `scripts/render_mcp_config.py` — writes to `.mcp.json.local` so the plugin template at `.mcp.json` is never clobbered.
- `scripts/check_versions.py` — now also verifies `.claude-plugin/plugin.json` and the plugin entry inside `.claude-plugin/marketplace.json` stay in sync with `__version__`.

### First-audit security hardening (originally filed as a pre-release)

### Security
- **Auth is now required by default.** TD-side refuses requests when `TD_MCP_SHARED_SECRET` is empty unless `TD_MCP_REQUIRE_AUTH=0` is explicitly set. Installers (`install.sh`, `install.ps1`) now generate a 32-byte secret at install time and write it to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) / `%APPDATA%/Claude/...` (Windows) *and* to a chmod-0600 `.tdpilot.env` that the TD startup script reads.
- **CORS wildcard removed.** `Access-Control-Allow-Origin: *` is no longer emitted. Set `TD_MCP_CORS_ORIGIN` to an exact origin if a browser tool needs access.
- **Sec-Fetch-Site check** rejects cross-site browser fetches before they reach the auth layer.
- **Constant-time secret compare** via `_constant_time_equals` to remove timing-based leak.
- **AST-based exec policy** layer added alongside the token matcher — catches string-concat bypasses (`getattr(__builtins__, …)`, `__class__.__mro__`, etc.).
- **Restricted-mode DAT-exec escape closed.** `op(...).create(textDAT)` and `.text = ...` assignments are now blocked in restricted mode (they were the known sandbox-escape path via `mod.<dat>.fn()`).
- New `docs/SECURITY.md` documents the threat model honestly, including what is *not* protected (TD-native file/network operators, compromised MCP clients, resource exhaustion).

### Tests & CI
- **Schema-snapshot contract test** — `tests/test_tools_schema_snapshot.py` + baseline at `tests/fixtures/tool_schemas.json`. Any silent change to a tool's input schema now fails CI.
- **Shared fixtures** in `tests/conftest.py` (`RecordingTDClient`, `mcp_ctx`, `exec_client_factory`).
- **Centralized thresholds** — `EXPECTED_MIN_TOOL_COUNT` in `src/td_mcp/release_gates.py`; tests and release scripts all derive from it (previously 6 places).
- **Version-drift guard** — `scripts/check_versions.py` checks all 10 versioned files against `src/td_mcp/__init__.__version__` and runs in CI.
- **Cross-platform CI** — new `install-parse` job parse-checks `install.sh` on macOS and `install.ps1` on Windows.
- **ruff + pytest-cov** in CI lint and test jobs; 821 auto-fixable lint issues corrected (851 → 81 remaining).

### Refactors
- New `src/td_mcp/exec_safety.py` module holds `RESTRICTED_TOKENS`, `STANDARD_BLOCKED_TOKENS`, `STANDARD_ALLOWED_IMPORTS`, `normalize_mode()`, `ast_violations()`, `enforce()`. `tool_registry.py` re-exports the constants for backward compatibility.
- `_current_exec_mode()` no longer does `sys.modules.get("td_mcp.server")` runtime introspection; exec mode is now read from `TD_MCP_EXEC_MODE` env at call time. Tests updated to patch env instead of module attribute.
- `TDClient.health_check` resets the connected flag and cached timestamp on any failure (previously could cache "ok" indefinitely if a request later failed).

### Packaging
- `uv.lock` is now **tracked** (was gitignored) for reproducible installs. CI uses `uv sync --frozen`.
- `.mcp.json.template` replaces the personal-path `.mcp.json` committed previously. New `scripts/render_mcp_config.py` renders the template with generated secret (chmod 0600).
- `uv` version pin in installers via `TDPILOT_UV_VERSION` env (default 0.6.10).

### Install scripts
- `npx tdpilot` no longer runs `git pull` silently on every invocation — opt-in via `TDPILOT_AUTO_UPDATE=1`.
- `npm/install.js` backs up existing TD `pref.txt` before writing (`.tdpilot-backup-<timestamp>`).

### Cleanup
- Empty `src/td_mcp/runtime/` directory removed.
- `docs/superpowers/` (historical plans + specs) moved to `docs/archive/superpowers/`.
- `td_component/NewProject*.toe` scratch files gitignored.
- `plugin_README.md` perms fixed (0400 → 0644).
- Deferred: `models.py` split (1,100+ lines → package) — marked as tech debt in the module docstring; requires updating every tool import at once so best handled in a dedicated PR.

### Derived artifacts rebuilt
- `td_component/tdpilot_v1_3.tox` — rebuilt inside TD 2025.32460 with the new callbacks (auth-by-default, CORS tightening, DAT-exec blocks).
- `tdpilot.plugin` — rebuilt via new `scripts/build_plugin_zip.py`. The plugin's embedded `.claude-plugin/plugin.json` now reads version + tool count from the single source of truth rather than being hand-maintained. Its bundled `.mcp.json` template ships with `TD_MCP_REQUIRE_AUTH=1` and `TD_MCP_EXEC_MODE=restricted` as defaults.

## 1.3.4 - 2026-03-15

### Added
- **Brain installer system** — modular one-click installer with dynamic manifest and interactive brain picker.
  - `brains_manifest.json` — single source of truth for all available brains (Google Drive file IDs, sizes, tools, skills).
  - `active.json` runtime gating — only selected brains load at startup; missing brains = silent skip, zero errors.
  - `_get_active_brains()` / `brain_is_active()` — backward-compatible brain loading (no active.json = load everything).
- POPx brain MCP tools (88→90→92 tools):
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
