# TDPilot Agent Guide

## Default Workflow

For TouchDesigner work, use the TDPilot brain skills:

- `tdpilot-brain-explorer` for read-only project discovery.
- `tdpilot-brain-builder` for non-trivial network construction.
- `tdpilot-brain-validator` for concept, graph, runtime, and visual checks.
- `tdpilot-brain-recovery` after failed transactions or unstable TD state.
- `tdpilot-brain-release` before publishing MCP surface or plugin changes.

## TouchDesigner Safety

- Inspect before mutating: `td_get_focus`, `td_get_state_vector`, `td_get_nodes`, `td_get_errors`.
- Plan before building: call `td_brain_plan` for non-trivial visual-programming tasks.
- Execute only valid plans: call `td_brain_execute` or `td_transaction_apply`, not raw free text.
- Treat `blocked_questions` as a hard stop.
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
