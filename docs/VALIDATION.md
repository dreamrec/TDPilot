# Reproducible TDPilot validation

Run from the checkout you intend to distribute. Use its frozen environment and
its canonical `td_component/tdpilot.tox` in TouchDesigner. Start with
`scripts/diagnose_live_sync.py --live --pretty`: every active runtime should use
the same source, version and canonical authentication file. Reconnect stale
TDPilot sessions through their owning clients; do not kill unrelated processes.

## Offline checks

```bash
uv sync --frozen --all-extras
uv run --frozen pytest -q
uv run --frozen ruff check src tests scripts td_component
uv run --frozen ruff format --check src tests scripts td_component
uv run --frozen python scripts/check_versions.py
uv run --frozen python scripts/check_tox_freshness.py
uv run --frozen python scripts/gen_api_reference.py --check
uv run --frozen python scripts/audit_brain_atlas.py
uv run --frozen python scripts/audit_brain_skills.py
uv run --frozen python scripts/smoke_mcp_registry.py
bash scripts/check_package_builds.sh
```

Store the six strict-gate reports in a new ignored directory. The live commands
mutate only owned scratch, verify cleanup, and require advancing TD frames.
Inspect the project and record timeline state/errors before testing. If you
temporarily play or seek the timeline, restore that state afterward.

```bash
mkdir -p reports/qualification
uv run --frozen python scripts/eval_brain_golden.py > reports/qualification/golden.json
uv run --frozen python scripts/brain_live_smoke.py --dry-run > reports/qualification/dry.json
uv run --frozen python scripts/audit_plugin_surface.py > reports/qualification/plugins.json
uv run --frozen python scripts/audit_param_semantics_risks.py > reports/qualification/risks.json
uv run --frozen python scripts/brain_live_smoke.py --live --transactional-generated-code > reports/qualification/live.json
uv run --frozen python scripts/sample_operator_availability.py --out reports/qualification/availability.json --store-root reports/qualification
uv run --frozen python scripts/check_release_gates.py \
  --brain-eval-report reports/qualification/golden.json \
  --brain-smoke-report reports/qualification/dry.json \
  --brain-live-smoke-report reports/qualification/live.json \
  --operator-availability-report reports/qualification/availability.json \
  --plugin-surface-report reports/qualification/plugins.json \
  --param-semantics-risk-report reports/qualification/risks.json \
  --require-complete
```

Also run `scripts/qualify_atomic_transactions.py`, `scripts/qualify_sdk2.py` and
`scripts/qualify_control_bindings.py --live` when changing transactions,
dispatch, transports, or component code. Record fresh MCP discovery from the
actual client launchers. Check final TD errors and verify original project
children as well as all owned scratch cleanup.

## Reading performance evidence

`performance_summary` measures the owned generated-code fixture. The separate
`incident_performance_summary` measures the incident fixture. Their target roots
and measurement scope are explicit. The latter's result also contributes to
incident-replay success.

`project_performance_summary` is a passive diagnostic of `/project1`. It can
correctly return `missing_metrics` for an empty, paused or idle project. It is
not substituted for an actively measured release fixture. Investigate its
failures before making performance claims about a real show.

The bridge can be inspected separately with the cooking endpoint at the
loaded TDPilot component. Its small dispatcher should cook on requests; the
large `callbacks` module should retain its compile count between ordinary
requests. Changing callback source legitimately incurs a new warmup compile.

All steady intervals must have advancing absolute frames and fresh target cook
timestamps. A local timeline wrap or backward seek must not be confused with
an application restart. Older components without absolute cook timestamps
remain conservative and cannot claim fresh measurements across a wrap.
