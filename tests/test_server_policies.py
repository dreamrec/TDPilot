import pytest

import td_mcp.server as server
from td_mcp.safety import SafetyManager


def test_restricted_exec_violation_detects_import():
    violation = server._restricted_exec_violation("import os\n__result__ = 1")
    assert violation is not None
    assert "import" in violation


def test_restricted_exec_violation_allows_basic_td_code():
    violation = server._restricted_exec_violation("__result__ = op('/project1/noise1').par.amp.eval()")
    assert violation is None


def test_enforce_exec_mode_off(monkeypatch):
    monkeypatch.setattr(server, "TD_EXEC_MODE", "off")
    with pytest.raises(PermissionError):
        server._enforce_exec_mode("__result__ = 1")


def test_apply_safety_to_set_params_clamps_numeric_values():
    safety = SafetyManager()
    safety.set_mode("clamp")
    safety.set_bound("/project1/noise1/amp", min_val=0.0, max_val=1.0, max_rate=None)

    adjusted, warnings = server._apply_safety_to_set_params(
        safety,
        "/project1/noise1",
        {"amp": 2.5, "seed": {"expr": "absTime.seconds"}},
    )

    assert adjusted["amp"] == 1.0
    assert adjusted["seed"] == {"expr": "absTime.seconds"}
    assert warnings
