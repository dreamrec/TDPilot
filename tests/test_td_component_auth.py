import importlib.util
import os
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "td_component" / "mcp_webserver_callbacks.py"


def _load_callbacks_module(secret: str, require_auth: str = "1"):
    os.environ["TD_MCP_SHARED_SECRET"] = secret
    os.environ["TD_MCP_REQUIRE_AUTH"] = require_auth
    spec = importlib.util.spec_from_file_location("td_cb_test", str(MODULE_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_check_auth_refuses_when_secret_missing_and_required(monkeypatch):
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    module = _load_callbacks_module("", require_auth="1")

    err = module._check_auth_error({})

    assert err is not None
    assert "TD_MCP_SHARED_SECRET" in err


def test_check_auth_allows_when_secret_disabled_and_auth_not_required(monkeypatch):
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    module = _load_callbacks_module("", require_auth="0")

    assert module._check_auth_error({}) is None


def test_check_auth_rejects_missing_secret_header(monkeypatch):
    module = _load_callbacks_module("super-secret")

    err = module._check_auth_error({"headers": {}})

    assert err is not None
    assert "Unauthorized" in err


def test_check_auth_accepts_x_td_mcp_secret(monkeypatch):
    module = _load_callbacks_module("super-secret")

    err = module._check_auth_error({"headers": {"X-TD-MCP-Secret": "super-secret"}})

    assert err is None


def test_check_auth_accepts_bearer_token(monkeypatch):
    module = _load_callbacks_module("super-secret")

    err = module._check_auth_error({"headers": {"Authorization": "Bearer super-secret"}})

    assert err is None


def test_constant_time_equals_matches(monkeypatch):
    module = _load_callbacks_module("super-secret")

    assert module._constant_time_equals("abc", "abc") is True
    assert module._constant_time_equals("abc", "abd") is False
    assert module._constant_time_equals("abc", "abcd") is False
    assert module._constant_time_equals("", "") is True
    assert module._constant_time_equals("abc", None) is False


def test_check_auth_wrong_secret_rejected(monkeypatch):
    module = _load_callbacks_module("super-secret")

    err = module._check_auth_error({"headers": {"X-TD-MCP-Secret": "wrong-secret"}})

    assert err is not None
    assert "Unauthorized" in err


# --- Regression tests for audit A-1 ------------------------------------
# Before A-1, SHARED_SECRET/REQUIRE_AUTH were captured at module import time
# and subsequent env changes had no effect. This caused a 3-hour debugging
# session where reloading the .tox couldn't pick up env changes.
# These tests ensure env is re-read per-request.


def test_auth_picks_up_env_change_after_import(monkeypatch):
    module = _load_callbacks_module("initial-secret")

    # Sanity: initial-secret works
    err = module._check_auth_error({"headers": {"X-TD-MCP-Secret": "initial-secret"}})
    assert err is None

    # Change secret in env, without re-importing the module
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "rotated-secret")

    # Old secret must now fail
    err_old = module._check_auth_error({"headers": {"X-TD-MCP-Secret": "initial-secret"}})
    assert err_old is not None

    # New secret must succeed — proves env is re-read each call
    err_new = module._check_auth_error({"headers": {"X-TD-MCP-Secret": "rotated-secret"}})
    assert err_new is None


def test_auth_picks_up_require_auth_toggle_after_import(monkeypatch):
    # Start with auth required + no secret → refusal
    module = _load_callbacks_module("", require_auth="1")
    assert module._check_auth_error({}) is not None

    # Flip REQUIRE_AUTH to 0 at runtime; should now allow
    monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "0")
    assert module._check_auth_error({}) is None
