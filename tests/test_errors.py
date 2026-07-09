import json

from td_mcp.errors import format_tool_error
from td_mcp.td_client import TouchDesignerAPIError, TouchDesignerConnectionError


def test_format_tool_error_connection_envelope():
    raw = format_tool_error(TouchDesignerConnectionError("dial failed"))
    payload = json.loads(raw)

    assert payload["success"] is False
    assert payload["error"]["code"] == "TD_CONNECTION_ERROR"
    assert "troubleshooting" in payload["error"]["details"]


def test_format_tool_error_api_envelope():
    raw = format_tool_error(TouchDesignerAPIError("bad request", status_code=400, details={"foo": "bar"}))
    payload = json.loads(raw)

    assert payload["success"] is False
    assert payload["error"]["code"] == "TD_API_ERROR"
    assert payload["error"]["details"]["status_code"] == 400


def test_format_tool_error_value_error_envelope():
    raw = format_tool_error(ValueError("invalid"))
    payload = json.loads(raw)

    assert payload["error"]["code"] == "INVALID_INPUT"


def test_format_tool_error_401_gets_dedicated_auth_envelope():
    """401 is the most expensive recurring field failure (secret drift).

    It must NOT collapse into the generic TD_API_ERROR envelope: the agent
    needs the recovery route (td_sync_diagnose, both secret file paths, the
    zombie-port check) in-band to fix it in one turn.
    """
    raw = format_tool_error(TouchDesignerAPIError("Unauthorized", status_code=401, details={}))
    payload = json.loads(raw)

    assert payload["success"] is False
    assert payload["error"]["code"] == "TD_AUTH_ERROR"
    details = payload["error"]["details"]
    assert details["status_code"] == 401
    joined = " ".join(details["troubleshooting"])
    assert "td_sync_diagnose" in joined
    assert ".tdpilot.env" in joined
    assert "9981" in joined
    # The auto-attached hint pack should route to the diagnostic too.
    hints = payload["error"].get("recovery_hints", [])
    assert any("td_sync_diagnose" in h.get("next_tools", []) for h in hints)


def test_format_tool_error_non_401_api_error_stays_generic():
    raw = format_tool_error(TouchDesignerAPIError("boom", status_code=500, details={}))
    payload = json.loads(raw)

    assert payload["error"]["code"] == "TD_API_ERROR"
