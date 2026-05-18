"""Meta tools — agent observability + server self-management.

Two server-local tools that don't talk to TouchDesigner over MCP:

* ``td_get_activity_log`` — recent tool-call history (server-side ring
  buffer). Useful for Claude to inspect what it's done in this session
  across MCP request boundaries.
* ``td_self_update`` — check for and install a newer TDPilot release
  from GitHub. Closes the long-running staleness problem documented in
  ``CLAUDE.md`` (seven artifact layers go stale silently).

Neither tool requires a live TD connection or an exec-mode privilege —
they introspect or mutate server-local state only. That's why they live
in a dedicated module instead of ``tools_info.py`` or ``tools_system.py``.

Part of the v1.6.16 surface (tool count 104 → 106).
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_get_activity_log")
async def td_get_activity_log(
    ctx: Context,
    limit: Annotated[
        int,
        Field(
            default=20,
            ge=1,
            le=200,
            description="How many recent entries to return (1–200, newest first).",
        ),
    ] = 20,
    tool_filter: Annotated[
        str | None,
        Field(
            default=None,
            description="If set, only return entries for this exact tool name.",
        ),
    ] = None,
) -> str:
    """Recent tool-call activity from this MCP server's ring buffer.

    Returns a JSON array of entries newest-first, each with ``ts``, ``tool``,
    ``args_summary``, ``result_summary``, ``duration_ms``, ``ok``. The buffer
    holds the most recent 200 calls; older entries are evicted.

    Pairs with the in-TD ``activity_log`` Table DAT mirror so the same data
    is also wireable into a live visual patch.
    """
    finish = _tr._start_tool(ctx, "td_get_activity_log")
    try:
        from td_mcp import activity_log

        entries = activity_log.snapshot(limit=limit, tool_filter=tool_filter)
        payload = {
            "schema_version": 1,
            "count": len(entries),
            "max_buffer": activity_log.MAX_ENTRIES,
            "entries": entries,
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_activity_log")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_self_update")
async def td_self_update(
    ctx: Context,
    check_only: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), only check whether a newer release exists. "
                "If False, download + install the latest .plugin/.tox to all "
                "three install paths (~/.tdpilot, plugin cache, repo)."
            ),
        ),
    ] = True,
) -> str:
    """Check for and optionally install a newer TDPilot release from GitHub.

    Default behavior (``check_only=True``) hits the GitHub releases API and
    returns ``{installed, latest, newer_available, release_url, asset_urls}``.
    Set ``check_only=False`` to actually download and install — this writes
    to ``~/.tdpilot/td_component/tdpilot.tox``, the Claude Code plugin cache,
    and the repo working-tree (when running from a clone). On success returns
    md5 fingerprints for each install path so the caller can verify sync.

    Network-only — does not touch TouchDesigner. Safe to run when TD is closed.
    """
    finish = _tr._start_tool(ctx, "td_self_update")
    try:
        from td_mcp import self_updater

        result = self_updater.run(check_only=check_only)
        return _tr._as_json_output(result)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_self_update")
        return format_tool_error(exc)
    finally:
        finish()
