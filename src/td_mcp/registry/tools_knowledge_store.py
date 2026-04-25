"""User knowledge tools (td_knowledge_*) — free-form markdown essays.

Parallel surface to ``tools_memory.py`` (td_memory_*) but for prose-with-math
reference content rather than replayable network recipes. Storage lives at
~/.tdpilot/knowledge/{global,projects/<name>}/ — fully local, never published.

Tools in this module:
    td_knowledge_save     — create or update a markdown entry
    td_knowledge_recall   — search by query/tags
    td_knowledge_get      — fetch full body by id
    td_knowledge_list     — list summaries (no body)

Same circular-import / module-attribute lookup pattern as the rest of registry/.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_knowledge_save")
async def td_knowledge_save(
    ctx: Context,
    body: Annotated[
        str,
        Field(
            description=(
                "Markdown body of the knowledge entry. Reference essay, math, "
                "explanations — keep under 200 KB. Split larger writeups into "
                "multiple linked entries."
            ),
            min_length=1,
        ),
    ],
    name: Annotated[
        str,
        Field(default="", description="Short title for the entry."),
    ] = "",
    description: Annotated[
        str,
        Field(default="", description="One-line summary used in search results."),
    ] = "",
    tags: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=("Lowercase tags for filtering, e.g. ['feedback', 'reaction-diffusion']."),
        ),
    ] = None,
    source: Annotated[
        str,
        Field(
            default="",
            description=(
                "Optional attribution — where this technique came from "
                "(e.g. 'paketa12 MBGA tutorial 2025-03-01')."
            ),
        ),
    ] = "",
    notes: Annotated[
        str,
        Field(default="", description="Free-form internal notes."),
    ] = "",
    scope: Annotated[
        str,
        Field(
            default="project",
            description="'project' or 'global'. Project requires TDPILOT_PROJECT_NAME.",
        ),
    ] = "project",
) -> str:
    """Persist a free-form markdown knowledge entry.

    Returns the entry id. The body is stored at
    ~/.tdpilot/knowledge/<scope>/entries/<id>.md and the metadata in
    index.json. Local-only, never pushed anywhere.
    """
    finish = _tr._start_tool(ctx, "td_knowledge_save")
    try:
        store = _tr._get_knowledge_store(ctx)
        entry_id = store.add(
            body,
            name=name,
            description=description,
            tags=tags,
            source=source,
            notes=notes,
            scope=scope,
        )
        _tr._audit_log(
            ctx,
            "td_knowledge_save",
            {
                "id": entry_id,
                "name": name,
                "scope": scope,
                "tags": tags or [],
                "body_bytes": len(body.encode("utf-8")),
            },
        )
        return _tr._as_json_output(
            {
                "success": True,
                "id": entry_id,
                "scope": scope,
                "stats": store.stats(),
            }
        )
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_knowledge_save")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_knowledge_recall")
async def td_knowledge_recall(
    ctx: Context,
    query: Annotated[
        str,
        Field(default="", description="Free-text search across name/description/tags/notes."),
    ] = "",
    tags: Annotated[
        list[str] | None,
        Field(default=None, description="Filter to entries that have at least one of these tags."),
    ] = None,
    scope: Annotated[
        str,
        Field(default="all", description="'project' | 'global' | 'all' (default)."),
    ] = "all",
    limit: Annotated[
        int,
        Field(default=20, ge=1, le=100, description="Max results."),
    ] = 20,
    full_text: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If true, also search the body of each entry (slower — reads files). "
                "Default false searches only metadata."
            ),
        ),
    ] = False,
) -> str:
    """Search knowledge entries. Returns summaries (no full bodies).

    Use ``td_knowledge_get`` afterward to fetch a specific entry's body.
    """
    finish = _tr._start_tool(ctx, "td_knowledge_recall")
    try:
        store = _tr._get_knowledge_store(ctx)
        results = store.search(
            query=query,
            tags=tags,
            scope=scope,
            limit=limit,
            full_text=full_text,
        )
        return _tr._as_json_output(
            {
                "success": True,
                "count": len(results),
                "results": results,
            }
        )
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_knowledge_recall")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_knowledge_get")
async def td_knowledge_get(
    ctx: Context,
    entry_id: Annotated[
        str,
        Field(description="Entry id from td_knowledge_recall.", min_length=1),
    ],
    scope: Annotated[
        str,
        Field(default="project", description="'project' or 'global'."),
    ] = "project",
) -> str:
    """Fetch the full markdown body + metadata for one entry."""
    finish = _tr._start_tool(ctx, "td_knowledge_get")
    try:
        store = _tr._get_knowledge_store(ctx)
        entry = store.get(entry_id, scope=scope)
        if entry is None:
            return _tr._as_json_output(
                {
                    "success": False,
                    "error": f"Entry not found: {entry_id} (scope={scope})",
                }
            )
        return _tr._as_json_output({"success": True, "entry": entry})
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_knowledge_get")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_knowledge_list")
async def td_knowledge_list(
    ctx: Context,
    scope: Annotated[
        str,
        Field(default="all", description="'project' | 'global' | 'all'."),
    ] = "all",
    tags: Annotated[
        list[str] | None,
        Field(default=None, description="Filter to entries with at least one of these tags."),
    ] = None,
    favorites_only: Annotated[
        bool,
        Field(default=False, description="If true, return only favorited entries."),
    ] = False,
    limit: Annotated[
        int,
        Field(default=50, ge=1, le=200, description="Max results."),
    ] = 50,
) -> str:
    """List knowledge entry summaries, newest first."""
    finish = _tr._start_tool(ctx, "td_knowledge_list")
    try:
        store = _tr._get_knowledge_store(ctx)
        results = store.list_entries(
            scope=scope,
            tags=tags,
            favorites_only=favorites_only,
            limit=limit,
        )
        out: dict[str, Any] = {
            "success": True,
            "count": len(results),
            "results": results,
            "stats": store.stats(),
        }
        return _tr._as_json_output(out)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_knowledge_list")
        return format_tool_error(exc)
    finally:
        finish()
