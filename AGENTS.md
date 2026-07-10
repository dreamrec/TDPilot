# TDPilot Agent Guide

## Default Workflow

For TouchDesigner work, use the TDPilot brain skills:

- `tdpilot-brain-explorer` for read-only project discovery.
- `tdpilot-brain-builder` for non-trivial network construction.
- `tdpilot-brain-validator` for concept, graph, runtime, and visual checks.
- `tdpilot-brain-recovery` after failed transactions or unstable TD state.
- `tdpilot-brain-release` before publishing MCP surface or plugin changes.

## TouchDesigner Safety

- Inspect the relevant live scope before mutating; batch independent reads when useful.
- Route exact validated patterns through `td_brain_plan`.
- Route artistic, multi-domain, spatial, camera/depth/fog, or implicit architecture through `td_brain_ground` → author → `td_brain_propose`.
- Execute only valid plans: call `td_brain_execute` or `td_transaction_apply`, not raw free text.
- Treat incomplete intent coverage and unresolved semantic edges as execution hard stops. A blocked pattern plan may continue through the concept-authoring route.
- Check errors at logical checkpoints and completion, not after every primitive operation.
- Learn only validated outcomes.

## Verification

Run focused tests for changed areas, then:

```bash
uv run pytest -q
uv run python scripts/eval_brain_golden.py
uv run python scripts/brain_live_smoke.py --dry-run
uv run python scripts/audit_brain_skills.py
uv run python scripts/audit_plugin_surface.py
uv run python scripts/smoke_mcp_registry.py
uv run python scripts/check_versions.py
```

If TouchDesigner is available, add `uv run python scripts/brain_live_smoke.py --live`.
If TouchDesigner is not running, state that live smoke validation was not run.
