---
name: tdpilot-brain-release
description: >
  Use when reviewing TDPilot brain, MCP surface, schema, prompt, resource,
  skill, agent, hook, or plugin changes before release.
---

# TDPilot Brain Release Auditor

Use this skill before any vNext brain release, plugin package update, or public
surface handoff.

## Core Rule

Release only evidence, not confidence. Every public surface change needs a
matching test, manifest/schema update, package artifact path, and local-first
constraint check.

## Required Checks

- Tool count and manifest:
  - `mcp/manifest.json` matches registered `@mcp.tool` and `@mcp.resource` decorators.
  - `src/td_mcp/release_gates.py` matches the new minimum tool count.
  - `tests/fixtures/tool_schemas.json` is regenerated for intentional tool schema changes.

- Brain behavior:
  - `td_brain_plan` is read-only.
  - `td_brain_execute` accepts only a valid `BrainPlan`.
  - `td_transaction_apply` enforces max op count, dry run, snapshot, rollback, and validation options.
  - Blocked plans never mutate.

- Correctness:
  - Unit tests cover schema validation, concept graph validity, profile routing, rollback paths, and severity classification.
  - Fake TD tests cover success, apply failure rollback, validation failure rollback, stale state, missing operators, name conflicts, snapshot failure, and nested undo refusal.
  - Golden evals pass with `uv run python scripts/eval_brain_golden.py`.
  - Brain smoke dry-run passes with `uv run python scripts/brain_live_smoke.py --dry-run`.
  - Live TD smoke planning runs with `uv run python scripts/brain_live_smoke.py --live` when TouchDesigner is available.
  - Brain atlas coverage passes with `uv run python scripts/audit_brain_atlas.py`.

- Packaging:
  - Codex skills and custom agents point users toward the brain loop.
  - Claude plugin agents and hooks are deterministic and local.
  - Plugin surface audit passes with `uv run python scripts/audit_plugin_surface.py`.
  - Complete plugin release gates include `scripts/check_release_gates.py` with
    `--plugin-surface-report` and `--require-plugin-surface`.
  - When TouchDesigner is available, complete release gates also include the
    captured live-smoke report with `--brain-live-smoke-report` and
    `--require-live-smoke`.
  - The open MCP core has no hosted LLM dependency.

## Minimum Local Test Set

Run these before handoff:

```bash
uv run pytest tests/models/test_brain_models.py tests/brain/test_planner.py tests/brain/test_transaction.py tests/test_brain_tools.py -q
uv run pytest tests/test_tools_contract.py tests/test_tools_schema_snapshot.py tests/test_resource_fallbacks.py -q
uv run python scripts/eval_brain_golden.py
uv run python scripts/brain_live_smoke.py --dry-run
uv run python scripts/audit_brain_atlas.py
uv run python scripts/audit_brain_skills.py
uv run python scripts/audit_plugin_surface.py
uv run python scripts/smoke_mcp_registry.py
```

For a plugin or public-surface release, capture the brain and plugin reports.
`--require-complete` demands SIX reports — brain eval, brain smoke (dry), brain
LIVE smoke, operator availability, plugin surface, and param-semantics risk —
and the live-smoke report must show a real mutation (`mutated_td=true` plus a
passing `transactional_generated_code_smoke`). Two of those (brain LIVE smoke
and operator availability) can ONLY be produced against a running TouchDesigner,
so the complete gate CANNOT pass without a live TD.

Local reports (no TD needed):

```bash
uv run python scripts/eval_brain_golden.py > /tmp/tdpilot_brain_eval.json
uv run python scripts/brain_live_smoke.py --dry-run > /tmp/tdpilot_brain_smoke.json
uv run python scripts/audit_plugin_surface.py --root . > /tmp/tdpilot_plugin_surface.json
uv run python scripts/audit_param_semantics_risks.py > /tmp/tdpilot_param_semantics_risk.json
```

Live reports (TouchDesigner MUST be running — these mutate the live project and clean up):

```bash
uv run python scripts/brain_live_smoke.py --live --transactional-generated-code > /tmp/tdpilot_brain_live_smoke.json
uv run python scripts/sample_operator_availability.py --out /tmp/tdpilot_operator_availability.json --store-root .
```

Complete gate (needs all six reports above):

```bash
uv run python scripts/check_release_gates.py \
  --brain-eval-report /tmp/tdpilot_brain_eval.json \
  --brain-smoke-report /tmp/tdpilot_brain_smoke.json \
  --brain-live-smoke-report /tmp/tdpilot_brain_live_smoke.json \
  --operator-availability-report /tmp/tdpilot_operator_availability.json \
  --plugin-surface-report /tmp/tdpilot_plugin_surface.json \
  --param-semantics-risk-report /tmp/tdpilot_param_semantics_risk.json \
  --require-complete
```

If TouchDesigner is not running you CANNOT run the complete gate: run the local
reports plus the non-complete checks above, and state explicitly that live
smoke, operator availability, and therefore strict release-completeness were
NOT verified.

## Pressure Scenarios

- Pressure: Tool counts pass but plugin skills, agents, hooks, or MCP config changed. Run `uv run python scripts/audit_brain_skills.py` and `uv run python scripts/audit_plugin_surface.py` before release.
- Pressure: A live TD smoke run is unavailable. Do not call release complete; report dry-run evidence and the exact reason live smoke was skipped.

## Common Mistakes

- Updating a tool schema without regenerating `tests/fixtures/tool_schemas.json`.
- Shipping root skills that differ from `.agents/skills` or `plugins/tdpilot/skills`.
- Shipping plugin MCP config with a personal path instead of a plugin-root placeholder.
- Treating green unit tests as proof that Codex/Claude packaging still includes the new brain artifacts.
