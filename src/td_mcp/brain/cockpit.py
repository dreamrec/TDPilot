"""Render-only cockpit payload helpers for TDPilot brain results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

COCKPIT_RESOURCE_URI = "ui://tdpilot/cockpit.html"


def build_cockpit_payload(
    *,
    plan: dict[str, Any] | None = None,
    transaction_result: dict[str, Any] | None = None,
    trace: dict[str, Any] | None = None,
    title: str = "TDPilot Brain Cockpit",
) -> dict[str, Any]:
    """Return compact, widget-friendly state for the optional cockpit UI."""
    brain_plan = _unwrap(plan, "plan")
    tx_result = _unwrap(transaction_result, "result")
    transaction_payload = transaction_result if isinstance(transaction_result, dict) else {}
    validation_report = _first_dict(
        tx_result.get("validation_report"), transaction_payload.get("validation_report")
    )

    return {
        "schema_version": 1,
        "mode": "render_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "plan": _plan_summary(brain_plan),
        "transaction": _transaction_summary(tx_result),
        "validation": _validation_summary(validation_report),
        "rollback": _rollback_summary(tx_result),
        "trace": trace or {},
    }


def cockpit_html() -> str:
    """Return a tiny host-agnostic MCP Apps HTML cockpit."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TDPilot Brain Cockpit</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #101417;
      color: #eef3f6;
    }
    body { margin: 0; background: #101417; }
    .shell { padding: 16px; display: grid; gap: 12px; }
    header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
    h1 { font-size: 18px; line-height: 1.2; margin: 0; font-weight: 700; }
    .subtitle { color: #a8b4bc; font-size: 12px; margin-top: 4px; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
    .panel { border: 1px solid #2b3840; background: #151c20; border-radius: 8px; padding: 12px; min-width: 0; }
    .panel h2 { font-size: 12px; text-transform: uppercase; color: #93a4ad; margin: 0 0 8px; letter-spacing: 0; }
    .value { font-size: 18px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .small { font-size: 12px; color: #b8c4cb; overflow-wrap: anywhere; }
    .status { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 8px; font-size: 12px; border: 1px solid #41505a; }
    .ok { color: #95e0b2; border-color: #276646; }
    .warn { color: #ffd38a; border-color: #876227; }
    .bad { color: #ff9e9e; border-color: #7a3333; }
    .wide { grid-column: 1 / -1; }
    .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    ul { margin: 0; padding-left: 18px; }
    li { margin: 3px 0; }
    code { color: #d5edf9; }
    @media (max-width: 720px) {
      .grid, .cols { grid-template-columns: 1fr; }
      header { display: block; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1 id="title">TDPilot Brain Cockpit</h1>
        <div class="subtitle" id="intent">No BrainPlan loaded.</div>
      </div>
      <span class="status" id="status">idle</span>
    </header>
    <section class="grid">
      <article class="panel"><h2>Profile</h2><div class="value" id="profile">-</div></article>
      <article class="panel"><h2>Operators</h2><div class="value" id="ops">0</div></article>
      <article class="panel"><h2>Patch Ops</h2><div class="value" id="patchOps">0</div></article>
      <article class="panel"><h2>Validation</h2><div class="value" id="validation">-</div></article>
      <article class="panel wide">
        <h2>Plan</h2>
        <div class="cols">
          <div class="small"><strong>Target</strong><br><code id="target">-</code></div>
          <div class="small"><strong>Output</strong><br><code id="output">-</code></div>
        </div>
      </article>
      <article class="panel wide">
        <h2>Risk And Recovery</h2>
        <div class="cols">
          <div><div class="small"><strong>Risks</strong></div><ul id="risks"></ul></div>
          <div><div class="small"><strong>Rollback</strong></div><ul id="rollback"></ul></div>
        </div>
      </article>
      <article class="panel wide">
        <h2>Operators Used</h2>
        <div class="small" id="operatorList">-</div>
      </article>
    </section>
  </main>
  <script>
    const data = window.openai?.toolOutput || {};
    const plan = data.plan || {};
    const tx = data.transaction || {};
    const validation = data.validation || {};
    const rollback = data.rollback || {};
    const setText = (id, value) => {
      document.getElementById(id).textContent = value == null || value === "" ? "-" : String(value);
    };
    const list = (id, items) => {
      const el = document.getElementById(id);
      el.innerHTML = "";
      const rows = Array.isArray(items) && items.length ? items : ["none"];
      rows.slice(0, 8).forEach((item) => {
        const li = document.createElement("li");
        li.textContent = typeof item === "string" ? item : JSON.stringify(item);
        el.appendChild(li);
      });
    };
    const status = tx.status || (plan.blocked_questions?.length ? "blocked" : "planned");
    setText("title", data.title || "TDPilot Brain Cockpit");
    setText("intent", plan.intent);
    setText("profile", plan.profile);
    setText("ops", plan.operator_count || 0);
    setText("patchOps", plan.operation_count || 0);
    setText("validation", validation.status || (tx.validation_failed ? "failed" : "pending"));
    setText("target", plan.target_root);
    setText("output", plan.output_top);
    setText("operatorList", (plan.operators || []).join(", "));
    const statusEl = document.getElementById("status");
    statusEl.textContent = status;
    statusEl.classList.add(tx.validation_failed || rollback.needs_manual_recovery ? "bad" : status === "warnings" ? "warn" : "ok");
    list("risks", [...(plan.risk_flags || []), ...(plan.missing_facts || []), ...(plan.blocked_questions || [])]);
    list("rollback", [
      `performed: ${Boolean(rollback.performed)}`,
      `manual recovery: ${Boolean(rollback.needs_manual_recovery)}`,
      rollback.snapshot_id ? `snapshot: ${rollback.snapshot_id}` : null,
      rollback.error ? `error: ${rollback.error}` : null,
    ].filter(Boolean));
  </script>
</body>
</html>
"""


def _unwrap(value: dict[str, Any] | None, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    nested = value.get(key)
    if isinstance(nested, dict):
        return nested
    return value


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    task = _first_dict(plan.get("task"))
    graph = _first_dict(plan.get("concept_graph"))
    patch_plan = _first_dict(plan.get("patch_plan"))
    operations = patch_plan.get("operations") if isinstance(patch_plan.get("operations"), list) else []
    operators = graph.get("operators") if isinstance(graph.get("operators"), list) else []
    concept_nodes = graph.get("concepts") if isinstance(graph.get("concepts"), list) else graph.get("nodes")
    concept_edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    return {
        "id": plan.get("id"),
        "intent": task.get("intent") or plan.get("intent"),
        "target_root": task.get("target_root") or plan.get("target_root"),
        "output_top": task.get("output_top") or plan.get("output_top"),
        "profile": graph.get("profile") or plan.get("profile"),
        "validation_profile": plan.get("validation_profile"),
        "operators": operators,
        "operator_count": len(operators),
        "operation_count": len(operations),
        "concept_nodes": concept_nodes if isinstance(concept_nodes, list) else [],
        "concept_edges": concept_edges,
        "grounding_evidence": _list(plan.get("grounding_evidence"))[:24],
        "risk_flags": _list(plan.get("risk_flags")),
        "blocked_questions": _list(plan.get("blocked_questions")),
        "missing_facts": _list(plan.get("missing_facts")),
        "corpus_evidence": _corpus_evidence_summary(plan.get("corpus_evidence")),
        "substitution_explanations": _substitution_explanations_summary(
            plan.get("substitution_explanations")
        ),
    }


def _transaction_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "trace_id": result.get("trace_id"),
        "validation_failed": bool(result.get("validation_failed")),
        "rollback_performed": bool(result.get("rollback_performed")),
        "needs_manual_recovery": bool(result.get("needs_manual_recovery")),
        "snapshot_id": result.get("before_snapshot_id"),
        "after_snapshot_id": result.get("after_snapshot_id"),
        "failed_op": result.get("failed_op"),
        "error": result.get("error"),
    }


def _validation_summary(report: dict[str, Any]) -> dict[str, Any]:
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    return {
        "status": report.get("status") or ("failed" if issues else "unknown"),
        "issue_count": len(issues),
        "issues": issues[:20],
        "checks": report.get("checks") if isinstance(report.get("checks"), list) else [],
    }


def _rollback_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "performed": bool(result.get("rollback_performed")),
        "needs_manual_recovery": bool(result.get("needs_manual_recovery")),
        "snapshot_id": result.get("before_snapshot_id"),
        "failed_op": result.get("failed_op"),
        "error": result.get("rollback_error") or result.get("error"),
    }


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _corpus_evidence_summary(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "evidence_id": item.get("evidence_id"),
                "source": item.get("source"),
                "op_type": item.get("op_type"),
                "display_name": item.get("display_name"),
                "docs_url": item.get("docs_url"),
                "key_params": _list(item.get("key_params"))[:6],
                "matched_terms": _list(item.get("matched_terms"))[:8],
                "score": item.get("score"),
            }
        )
    return rows


def _substitution_explanations_summary(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "missing_op": item.get("missing_op"),
                "replacement_target": item.get("replacement_target"),
                "replacement_ops": _list(item.get("replacement_ops")),
                "confidence": item.get("confidence"),
                "requires_approval": bool(item.get("requires_approval")),
                "approval_state": item.get("approval_state"),
                "approval_evidence": _list(item.get("approval_evidence")),
                "availability_reason": item.get("availability_reason"),
                "tradeoffs": _list(item.get("tradeoffs")),
                "official_sources": _list(item.get("official_sources")),
                "summary": item.get("summary"),
            }
        )
    return rows


__all__ = ["COCKPIT_RESOURCE_URI", "build_cockpit_payload", "cockpit_html"]
