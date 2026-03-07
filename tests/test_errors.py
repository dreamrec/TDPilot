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
