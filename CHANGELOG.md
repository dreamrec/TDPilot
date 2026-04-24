# Changelog

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
