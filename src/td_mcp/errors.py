"""Shared error formatting helpers for MCP tool responses."""

from __future__ import annotations

import json

from td_mcp.td_client import TouchDesignerAPIError, TouchDesignerConnectionError


def _error_payload(code: str, message: str, details: dict | None = None) -> str:
    return json.dumps(
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        },
        indent=2,
    )


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
