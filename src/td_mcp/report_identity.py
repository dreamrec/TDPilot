"""Canonical identity stamps for release-evidence reports."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from td_mcp import __version__
from td_mcp.release_gates import EXPECTED_MIN_TOOL_COUNT


def stamp_report_identity(
    report: Mapping[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Return *report* bound to the running candidate and current tool surface.

    Release gates reject reports without these fields, reports produced by a
    different version/tool surface, and reports older than the freshness
    window.  Producers call this at the end so the timestamp describes the
    completed evidence rather than the start of a potentially long audit.
    """

    completed_at = generated_at or datetime.now(timezone.utc)
    return {
        **dict(report),
        "version": __version__,
        "tool_count": EXPECTED_MIN_TOOL_COUNT,
        "generated_at": completed_at.astimezone(timezone.utc).isoformat(),
    }


__all__ = ["stamp_report_identity"]
