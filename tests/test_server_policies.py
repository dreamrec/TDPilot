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
    # Exec mode is now sourced from the TD_MCP_EXEC_MODE env var at call time
    # (was: monkey-patched on td_mcp.server.TD_EXEC_MODE via a sys.modules hack).
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "off")
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


# ---------------------------------------------------------------------------
# Auth startup config — regression for v1.4.3
# .mcp.json ships with TD_MCP_REQUIRE_AUTH=1 and no secret; the plugin install
# path reads it directly and never runs install.sh/install.ps1, so the server
# would start happily and every authenticated request would 401. Fix:
# verify_auth_config() raises loud at startup if required-but-missing.
# ---------------------------------------------------------------------------


def test_verify_auth_config_refuses_auth_required_without_secret(monkeypatch):
    monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

    with pytest.raises(RuntimeError) as exc:
        server.verify_auth_config()
    msg = str(exc.value)
    assert "TD_MCP_SHARED_SECRET" in msg
    assert "install" in msg.lower()


def test_verify_auth_config_accepts_auth_required_with_secret(monkeypatch):
    monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "x" * 32)
    server.verify_auth_config()  # must not raise


def test_verify_auth_config_accepts_auth_disabled_without_secret(monkeypatch):
    monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "0")
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    server.verify_auth_config()  # must not raise


def test_verify_auth_config_accepts_auth_unset(monkeypatch):
    monkeypatch.delenv("TD_MCP_REQUIRE_AUTH", raising=False)
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    server.verify_auth_config()  # must not raise


def test_verify_auth_config_accepts_truthy_require_values(monkeypatch):
    for value in ("1", "true", "yes", "TRUE", "Yes"):
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", value)
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "secret-value")
        server.verify_auth_config()

        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
        with pytest.raises(RuntimeError):
            server.verify_auth_config()


def test_verify_auth_config_treats_whitespace_secret_as_missing(monkeypatch):
    monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "   ")
    with pytest.raises(RuntimeError):
        server.verify_auth_config()
