"""Shared error formatting helpers for MCP tool responses."""

from __future__ import annotations

import json

from td_mcp.td_client import TouchDesignerAPIError, TouchDesignerConnectionError


def _recovery_hints_for(message: str) -> list[dict]:
    """Look up error_recovery hints matching the given message.

    Returns a list of {id, priority, rule, next_tools} dicts. Empty list
    when no patterns match or when the hints subsystem is unavailable
    (defensive: a hints-system failure must NOT prevent error reporting).
    """
    if not isinstance(message, str) or not message.strip():
        return []
    try:
        from td_mcp.hints.loader import default_registry  # local import to avoid cycles at startup

        registry = default_registry()
        matches = registry.find(surface="error_recovery", error_text=message)
    except Exception:  # noqa: BLE001 — hints lookup must never block error reporting
        return []
    out: list[dict] = []
    for m in matches:
        hint = m.hint
        out.append(
            {
                "id": hint.id,
                "priority": hint.priority,
                "rule": hint.rule.strip(),
                "next_tools": list(hint.next_tools or []),
            }
        )
    return out


def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    body: dict = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
    hints = _recovery_hints_for(message)
    if hints:
        body["error"]["recovery_hints"] = hints
    return body


def _error_payload(code: str, message: str, details: dict | None = None) -> str:
    return json.dumps(_error_body(code, message, details), indent=2)


def format_tool_error_dict(exc: Exception) -> dict:
    """Return the machine-readable error envelope as a dict.

    Use this in tools annotated ``-> dict`` that run under FastMCP
    structured_output: those wrap the return value in a DictModel and call
    model_validate, so returning the JSON *string* form (``format_tool_error``)
    raises a pydantic ValidationError on every exception path and destroys the
    error/troubleshooting/recovery-hints payload exactly when the caller needs
    it (e.g. TouchDesigner not running).
    """
    if isinstance(exc, TouchDesignerConnectionError):
        return _error_body(
            "TD_CONNECTION_ERROR",
            "Cannot connect to TouchDesigner.",
            {
                "reason": str(exc),
                "troubleshooting": [
                    "Is TouchDesigner running?",
                    "Is the MCP WebServer component imported and active?",
                    "Is port 9981 correct?",
                    "Try restarting TouchDesigner.",
                ],
            },
        )

    if isinstance(exc, TouchDesignerAPIError):
        if exc.status_code == 401:
            # The single most expensive recurring failure in the field:
            # shared-secret drift between the client config and the TD
            # component. A generic envelope here has historically cost
            # users multi-hour debugging sessions.
            return _error_body(
                "TD_AUTH_ERROR",
                "TouchDesigner rejected the request: authentication failed "
                "(HTTP 401). The MCP server's TD_MCP_SHARED_SECRET does not "
                "match the secret the TD component loaded.",
                {
                    "status_code": 401,
                    "api_details": exc.details or {},
                    "troubleshooting": [
                        "Run td_sync_diagnose first — it fingerprints the "
                        "secret/config chain and names the mismatched layer.",
                        "Secrets live in TWO places that drift independently: "
                        "the client config env block (.mcp.json / "
                        ".mcp.json.local) and ~/.tdpilot/.tdpilot.env. Both "
                        "must hold the same TD_MCP_SHARED_SECRET.",
                        "Check for a zombie server still holding port 9981 "
                        "from an earlier session (macOS: `lsof -i :9981`; "
                        "Windows: `Get-NetTCPConnection -LocalPort 9981`) "
                        "and kill leaked `npm exec tdpilot` processes.",
                        "After fixing the secret, toggle the TD component's "
                        "webserver `active` parameter off/on (or restart "
                        "TouchDesigner) so it reloads the env file.",
                    ],
                },
            )
        return _error_body(
            "TD_API_ERROR",
            str(exc),
            {
                "status_code": exc.status_code,
                "api_details": exc.details or {},
            },
        )

    if isinstance(exc, PermissionError):
        return _error_body("PERMISSION_DENIED", str(exc))

    if isinstance(exc, ValueError):
        return _error_body("INVALID_INPUT", str(exc))

    return _error_body(
        "INTERNAL_ERROR",
        f"{type(exc).__name__}: {str(exc)}",
    )


def format_tool_error(exc: Exception) -> str:
    """Return a consistent machine-readable error envelope as a JSON string.

    For tools annotated ``-> str``. Tools annotated ``-> dict`` (structured
    output) must use :func:`format_tool_error_dict` instead.
    """
    return json.dumps(format_tool_error_dict(exc), indent=2)
