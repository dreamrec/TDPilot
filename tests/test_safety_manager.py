import pytest

from td_mcp.safety import SafetyManager


def test_safety_clamps_min_max_bounds():
    manager = SafetyManager()
    manager.set_mode("clamp")
    manager.set_bound("/project1/noise1/amp", min_val=0.0, max_val=1.0, max_rate=None)

    value, warning = manager.apply("/project1/noise1/amp", 2.5)

    assert value == 1.0
    assert warning is not None
    assert "max bound" in warning


def test_safety_reject_mode_raises():
    manager = SafetyManager()
    manager.set_mode("reject")
    manager.set_bound("/project1/noise1/amp", min_val=0.0, max_val=1.0, max_rate=None)

    with pytest.raises(ValueError):
        manager.apply("/project1/noise1/amp", 2.5)


def test_safety_rate_limit_clamps(monkeypatch):
    now = [100.0]

    def fake_time():
        return now[0]

    monkeypatch.setattr("td_mcp.safety.manager.time.time", fake_time)

    manager = SafetyManager()
    manager.set_mode("clamp")
    manager.set_bound("/project1/level1/opacity", min_val=None, max_val=None, max_rate=2.0)

    first, _ = manager.apply("/project1/level1/opacity", 0.0)
    assert first == 0.0

    now[0] = 100.1  # 100ms later => max delta = 0.2
    second, warning = manager.apply("/project1/level1/opacity", 5.0)

    assert abs(second - 0.2) < 1e-9
    assert warning is not None
    assert "rate-limited" in warning
