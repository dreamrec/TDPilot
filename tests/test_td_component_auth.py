import importlib.util
import os
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "td_component" / "mcp_webserver_callbacks.py"


def _load_callbacks_module(secret: str):
    os.environ["TD_MCP_SHARED_SECRET"] = secret
    spec = importlib.util.spec_from_file_location("td_cb_test", str(MODULE_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_check_auth_allows_when_secret_disabled(monkeypatch):
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    module = _load_callbacks_module("")

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
