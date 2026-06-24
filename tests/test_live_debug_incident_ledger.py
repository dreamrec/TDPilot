from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "tests" / "fixtures" / "td_live_debug_incident_2026_06_24.json"


def test_live_debug_incident_ledger_covers_all_recorded_bugs() -> None:
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))

    bugs = payload["bugs"]
    ids = [item["id"] for item in bugs]

    assert payload["schema_version"] == 1
    assert payload["source_report"] == "reports/td_live_deep_test_2026-06-24.md"
    assert ids == [f"BUG-{index:03d}" for index in range(1, 46)]
    unresolved = [item["id"] for item in bugs if item.get("resolution") in {"untriaged", "documented_open"}]
    assert unresolved == []
    assert not [item for item in bugs if not item.get("evidence_kind")]


def test_live_debug_incident_ledger_has_required_bug_groups() -> None:
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    groups = {item["group"] for item in payload["bugs"]}

    assert {
        "version_auth_update",
        "planner_collapse",
        "transaction_rollback_validation",
        "exec_operator_param_schema",
        "visual_qa",
        "panel_ui",
        "performance",
    }.issubset(groups)


def test_replay_live_debug_incident_dry_run_is_machine_readable() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "replay_live_debug_incident.py"),
            "--dry-run",
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == 1
    assert payload["mode"] == "dry_run"
    assert payload["ok"] is True
    assert payload["bug_count"] == 45
    assert payload["representative_checks"]["visual_black_frame"]["status"] == "covered"
    assert payload["representative_checks"]["panel_callback_wiring"]["status"] == "covered"
    assert payload["representative_checks"]["sync_drift"]["status"] == "covered"
    assert payload["representative_checks"]["macro_truthfulness"]["status"] == "covered"
    assert payload["representative_checks"]["rollback_readback"]["status"] == "covered"
    assert payload["representative_checks"]["operator_param_semantics"]["status"] == "covered"
