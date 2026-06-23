from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_audit_module():
    path = ROOT / "scripts" / "audit_param_semantics_risks.py"
    spec = importlib.util.spec_from_file_location("audit_param_semantics_risks", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_param_semantics_risk_audit_accepts_current_registry():
    module = _load_audit_module()

    report = module.audit_param_semantics_risks()
    direct = {(item["op_type"], item["name"]) for item in report["direct_risk_parameters"]}
    validation_only = {(item["op_type"], item["name"]) for item in report["validation_only_parameters"]}

    assert report["ok"] is True
    assert report["contract"] == "high_cook_risk_direct_param_coverage_v1"
    assert report["unclassified_high_cook_risk_parameters"] == []
    assert ("datexecuteDAT", "active") in direct
    assert ("mqttclientDAT", "password") in direct
    assert ("mqttclientDAT", "verifycert") in direct
    assert ("webclientDAT", "active") in direct
    assert ("webclientDAT", "stream") in direct
    assert ("mqttclientDAT", "netaddress") in validation_only
