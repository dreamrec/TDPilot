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


def _error_payload(code: str, message: str, details: dict | None = None) -> str:
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
    return json.dumps(body, indent=2)


def format_tool_error(exc: Exception) -> str:
    """Return a consistent machine-readable error envelope as JSON string."""
    if isinstance(exc, TouchDesignerConnectionError):
        return _error_payload(
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
        return _error_payload(
            "TD_API_ERROR",
            str(exc),
            {
                "status_code": exc.status_code,
                "api_details": exc.details or {},
            },
        )

    if isinstance(exc, PermissionError):
        return _error_payload("PERMISSION_DENIED", str(exc))

    if isinstance(exc, ValueError):
        return _error_payload("INVALID_INPUT", str(exc))

    return _error_payload(
        "INTERNAL_ERROR",
        f"{type(exc).__name__}: {str(exc)}",
    )
