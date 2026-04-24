"""Data/inspection tools — query TD state without mutation.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Tools in this module (7):
    td_screenshot       — capture a TOP as JPEG
    td_chop_data        — read CHOP channel samples
    td_geometry_data    — read SOP/POP point + prim data
    td_pop_inspect      — structured POP metadata + attribute samples
    td_cooking_info     — performance / cook-time breakdown
    td_search_nodes     — find nodes by name/type/family
    td_get_errors       — list errors + warnings in a subtree

All 7 are essentially thin ``_forward()`` wrappers that pass through to
TD endpoints. The cleanest extraction so far — only one external helper
dependency (``_tr._forward``).
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.models import SearchNodesInput
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_screenshot")
async def td_screenshot(
    ctx: Context,
    path: Annotated[
        str,
        Field(
            description=(
                "Path to a TOP node to capture as an image (e.g. '/project1/null1', '/project1/render1')"
            ),
            min_length=1,
        ),
    ],
    quality: Annotated[
        float,
        Field(
            default=0.5,
            ge=0.0,
            le=1.0,
            description=(
                "JPEG quality from 0.0 (smallest) to 1.0 (best). "
                "Default 0.5 gives good diagnostic quality at ~85KB."
            ),
        ),
    ] = 0.5,
) -> str:
    """Capture a TOP frame.

    Ask the user before repeated screenshots because each base64 image can
    consume significant tokens in model context.
    """
    return await _tr._forward(
        ctx,
        "td_screenshot",
        "screenshot",
        {"path": path, "quality": quality},
    )


@mcp.tool(name="td_chop_data")
async def td_chop_data(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a CHOP node", min_length=1),
    ],
    channels: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="List of channel names to read. If None, reads all channels.",
        ),
    ] = None,
    range: Annotated[
        list[int] | None,
        Field(
            default=None,
            description="Sample range [start, end] to read. If None, reads all samples.",
            min_length=2,
            max_length=2,
        ),
    ] = None,
) -> str:
    """Read CHOP channel data (values/samples)."""
    body: dict[str, Any] = {"path": path}
    if channels is not None:
        body["channels"] = channels
    if range is not None:
        body["range"] = range
    return await _tr._forward(ctx, "td_chop_data", "chop/data", body)


@mcp.tool(name="td_geometry_data")
async def td_geometry_data(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a SOP or POP node", min_length=1),
    ],
    include_points: Annotated[
        bool,
        Field(default=True, description="Include point position data"),
    ] = True,
    include_prims: Annotated[
        bool,
        Field(default=False, description="Include primitive data"),
    ] = False,
    limit: Annotated[
        int,
        Field(
            default=500,
            ge=1,
            le=10000,
            description="Max points/prims to return",
        ),
    ] = 500,
) -> str:
    """Read SOP/POP geometry data (points/prims)."""
    return await _tr._forward(
        ctx,
        "td_geometry_data",
        "geometry/data",
        {
            "path": path,
            "include_points": include_points,
            "include_prims": include_prims,
            "limit": limit,
        },
    )


@mcp.tool(name="td_pop_inspect")
async def td_pop_inspect(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a POP node", min_length=1),
    ],
    include_bounds: Annotated[
        bool,
        Field(
            default=True,
            description="Include POP bounds and dimension metadata",
        ),
    ] = True,
    include_attributes: Annotated[
        bool,
        Field(
            default=True,
            description="Include point/prim/vert attribute metadata",
        ),
    ] = True,
    point_attributes: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Specific point attributes to sample. If omitted, the tool "
                "samples common attributes such as P, PartVel, PartAge, "
                "Noise, and PartForce when present."
            ),
        ),
    ] = None,
    prim_attributes: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Specific primitive attributes to sample. If omitted, no "
                "primitive attribute samples are returned unless requested."
            ),
        ),
    ] = None,
    vert_attributes: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Specific vertex attributes to sample. If omitted, no "
                "vertex attribute samples are returned unless requested."
            ),
        ),
    ] = None,
    start: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Starting element index for attribute sampling",
        ),
    ] = 0,
    count: Annotated[
        int,
        Field(
            default=32,
            ge=1,
            le=2048,
            description="Max elements to sample per requested attribute",
        ),
    ] = 32,
    delayed: Annotated[
        bool,
        Field(
            default=False,
            description=("Use TouchDesigner's delayed GPU readback mode where supported to reduce stalls"),
        ),
    ] = False,
) -> str:
    """Read structured POP metadata and attribute samples."""
    return await _tr._forward(
        ctx,
        "td_pop_inspect",
        "pop/inspect",
        {
            "path": path,
            "include_bounds": include_bounds,
            "include_attributes": include_attributes,
            "point_attributes": point_attributes,
            "prim_attributes": prim_attributes,
            "vert_attributes": vert_attributes,
            "start": start,
            "count": count,
            "delayed": delayed,
        },
    )


@mcp.tool(name="td_cooking_info")
async def td_cooking_info(
    ctx: Context,
    path: Annotated[
        str,
        Field(default="/", description="Root path to inspect"),
    ] = "/",
    recurse: Annotated[
        bool,
        Field(default=False, description="Recursively inspect children"),
    ] = False,
    sort_by: Annotated[
        str,
        Field(
            default="cookTime",
            description="Sort by: 'cookTime' or 'cpuCookTime'",
        ),
    ] = "cookTime",
    limit: Annotated[
        int,
        Field(default=20, ge=1, le=100, description="Max nodes to return"),
    ] = 20,
) -> str:
    """Get cooking/performance info for a subtree."""
    return await _tr._forward(
        ctx,
        "td_cooking_info",
        "cooking",
        {
            "path": path,
            "recurse": recurse,
            "sort_by": sort_by,
            "limit": limit,
        },
    )


@mcp.tool(name="td_search_nodes")
async def td_search_nodes(
    ctx: Context,
    query: Annotated[
        str,
        Field(description="Search string (case-insensitive)", min_length=1),
    ],
    path: Annotated[
        str,
        Field(default="/", description="Root path to search from"),
    ] = "/",
    search_type: Annotated[
        str,
        Field(
            default="all",
            description="What to search: 'name', 'type', 'family', or 'all'",
        ),
    ] = "all",
    limit: Annotated[
        int,
        Field(default=50, ge=1, le=200, description="Max results"),
    ] = 50,
) -> str:
    """Search nodes by name/type/family across a subtree."""
    # Re-instantiate so the SearchNodesInput custom @field_validator on
    # ``search_type`` (must be 'name', 'type', 'family', or 'all') still runs.
    validated = SearchNodesInput(query=query, path=path, search_type=search_type, limit=limit)
    return await _tr._forward(ctx, "td_search_nodes", "search", validated.model_dump())


@mcp.tool(name="td_get_errors")
async def td_get_errors(
    ctx: Context,
    path: Annotated[
        str,
        Field(default="/", description="Node path to check"),
    ] = "/",
    recurse: Annotated[
        bool,
        Field(default=True, description="Recursively check children"),
    ] = True,
    max_depth: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=50,
            description="Max recursion depth (prevents runaway on huge projects)",
        ),
    ] = 10,
) -> str:
    """Get errors + warnings for a node (optionally recursive)."""
    return await _tr._forward(
        ctx,
        "td_get_errors",
        "node/errors",
        {"path": path, "recurse": recurse, "max_depth": max_depth},
    )
