# Contributing to TDPilot

Thanks for helping make the most rigorously verified TouchDesigner AI tool
better. This guide covers the practical rules; the architecture story lives
in [CONTEXT.md](CONTEXT.md) and the security posture in
[docs/SECURITY.md](docs/SECURITY.md).

## Quick start

```bash
git clone https://github.com/dreamrec/TDPilot.git
cd TDPilot
uv sync --all-extras          # Python 3.11+ via uv
uv run pytest -q              # full suite, no TouchDesigner required
```

Most of the suite runs against a fake TD client — you do not need
TouchDesigner installed to contribute server-side code. Live-TD checks are a
separate opt-in tier (`scripts/brain_live_smoke.py --live`).

## Before you push

CI runs both ruff gates — run both locally or the lint job will fail:

```bash
uv run ruff check src tests scripts td_component
uv run ruff format --check src tests scripts td_component
uv run pytest -q
```

## The rules that surprise people

- **Tool count is gated.** `EXPECTED_MIN_TOOL_COUNT` in
  `src/td_mcp/release_gates.py` is the single source of truth. Adding or
  removing an `@mcp.tool` means bumping it (tests import it).
- **Tool schemas are snapshot-tested.** If you intentionally change a tool
  signature, regenerate the fixture:
  `TDPILOT_UPDATE_SCHEMA=1 uv run pytest tests/test_tools_schema_snapshot.py`.
- **Every `@mcp.tool` carries `ToolAnnotations` and a real description.**
  `tests/test_tools_contract.py` enforces it: pass
  `annotations=ToolAnnotations(readOnlyHint=…, destructiveHint=…,
  idempotentHint=…, openWorldHint=…)` on the decorator, and give the tool a
  description/docstring of at least 40 chars. Classify by behaviour:
  a pure read is `readOnlyHint=True, destructiveHint=False`; anything that can
  delete/overwrite/reset live state is `readOnlyHint=False, destructiveHint=True`;
  set `openWorldHint=True` when the tool reads or mutates the live TouchDesigner
  scene, `False` for server-local data (docs corpus, technique memory, hints,
  notes, metrics). The contract test additionally requires every
  `td_get_*`/`td_list_*`/`td_search_*`/`td_describe_*` tool to be `readOnlyHint=True`
  and every `*delete*`/`*disconnect*`/`*restore*`/`*emergency*`/`*clear*` tool
  (plus `td_project_lifecycle`) to be `destructiveHint=True`.
- **`td_component/*.py` files are baked into a binary.** The nine files in
  `_TOX_SOURCE_FILES` (see `td_component/build_tdpilot_tox.py`) are compiled
  into `td_component/tdpilot.tox`, which can only be rebuilt inside a running
  TouchDesigner session. If you touch them, say so in the PR —
  `scripts/check_tox_freshness.py` will fail CI until a maintainer rebuilds.
- **Skills ship as mirrors.** `skills/` and `plugins/tdpilot/skills/` must
  stay in sync — edit both or CI packaging checks fail.
- **Docs don't carry counts.** Don't hardcode tool/pack/hint counts in prose;
  docs-truth tests fail on stale counts. Point to the live query instead.
- **`docs/API_REFERENCE.md` is generated.** The tool tables between the
  `BEGIN/END GENERATED` markers come from the FastMCP registry — never edit
  them by hand. After changing any tool signature/docstring, run
  `uv run python scripts/gen_api_reference.py` and commit the result;
  CI runs the script's `--check` mode and fails on a stale doc. Prose outside
  the markers (env vars, exec modes, envelope notes) is still hand-written.
- **No personal paths.** `scripts/check_no_personal_paths.sh` runs in CI;
  run it after `git add`, not before.

## What contributions land fastest

1. **Technique recipes** — a working TD technique with real parameter values
   and a verification screenshot (see the technique-share issue template).
   These ship as knowledge, not code, and need no review of the tool surface.
2. **Hint packs** — YAML rules in `src/td_mcp/hints/packs/` (gotchas,
   param renames, recovery routes) with a cited source.
3. **Bug fixes with a failing test first.**
4. **Operator atlas corrections** — wrong param names or ranges in cards.

New MCP tools are the slowest path — TDPilot deliberately resists tool-count
growth (see the deferred-roadmap notes in `skills/tdpilot-core/SKILL.md` §13).
Open a Discussion first before building one.

## Reporting

- Bugs → GitHub issue with `tdpilot doctor --json` output (the template asks).
- Security vulnerabilities → **private** GHSA report, not a public issue
  (see [docs/SECURITY.md](docs/SECURITY.md)).
- Ideas / show-and-tell → GitHub Discussions.

## Code style

Follow the file you're editing. Python is ruff-formatted (line length per
`pyproject.toml`), fully typed at public boundaries, and tests live in
`tests/` mirroring the module layout. Error returns from tools go through
`format_tool_error_dict` / `format_tool_error` — never bare
`{"error": str(exc)}` dicts in new code.
