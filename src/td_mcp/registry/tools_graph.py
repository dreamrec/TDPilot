"""Graph tools — node manipulation (list, detail, params, create, delete, connect, …).

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

This is the single largest extraction so far — the node-manipulation
surface is the heart of TDPilot's MCP tool offering.

Tools in this module (11):
    td_get_nodes           — list children at a path
    td_get_node_detail     — full detail for one node (type, errors, params)
    td_get_params          — get param values + metadata
    td_set_params          — set params (static / expressions)
    td_create_node         — create a new operator
    td_delete_node         — remove a node
    td_copy_node           — duplicate into same or different parent
    td_rename_node         — rename a node
    td_connect_nodes       — wire output→input
    td_disconnect          — remove a connector wire
    td_get_connections     — list upstream/downstream wires
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.models import (
    ConnectNodesInput,
    CreateNodeInput,
    DisconnectInput,
    ResponseFormat,
)
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_get_nodes")
async def td_get_nodes(
    ctx: Context,
    path: Annotated[
        str,
        Field(
            default="/",
            description=(
                "Absolute path to a COMP node whose children to list "
                "(e.g. '/', '/project1', '/project1/myComp')"
            ),
        ),
    ] = "/",
    family: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by operator family: TOP, CHOP, SOP, DAT, COMP, MAT, or PANEL",
        ),
    ] = None,
    type: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by specific operator type (e.g. 'noiseTOP', 'waveCHOP', 'textDAT')",
        ),
    ] = None,
    include_params: Annotated[
        bool,
        Field(
            default=False,
            description="If true, include all parameters for each node (slower for large networks)",
        ),
    ] = False,
    limit: Annotated[
        int,
        Field(default=100, ge=1, le=500, description="Max number of nodes to return"),
    ] = 100,
    offset: Annotated[
        int,
        Field(default=0, ge=0, description="Pagination offset"),
    ] = 0,
    response_format: Annotated[
        ResponseFormat,
        Field(default=ResponseFormat.JSON, description="Output format"),
    ] = ResponseFormat.JSON,
) -> str:
    """List child nodes at a path."""
    finish = _tr._start_tool(ctx, "td_get_nodes")
    try:
        body: dict[str, Any] = {
            "path": path,
            "include_params": include_params,
            "limit": limit,
            "offset": offset,
        }
        if family is not None:
            body["family"] = family
        if type is not None:
            body["type"] = type
        data = await _tr._get_client(ctx).request("nodes", body)
        if response_format == ResponseFormat.MARKDOWN:
            return _tr._format_nodes_markdown(data.get("nodes", []), f"Children of {path}")
        return _tr._as_json_output(data)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_nodes")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_node_detail")
async def td_get_node_detail(
    ctx: Context,
    path: Annotated[
        str,
        Field(
            description=("Absolute path to the node (e.g. '/project1/noise1', '/project1/geo1/sphere1')"),
            min_length=1,
        ),
    ],
    response_format: Annotated[
        ResponseFormat,
        Field(default=ResponseFormat.JSON, description="Output format"),
    ] = ResponseFormat.JSON,
    param_limit: Annotated[
        int,
        Field(
            default=50,
            ge=1,
            le=200,
            description=(
                "Max parameters to serialize. Default 50; hard cap 200. "
                "If the node has more, the response sets parameters_truncated=true "
                "and parameters_total to the real count. Use td_get_params for the rest."
            ),
        ),
    ] = 50,
    include_notes: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, look up any per-COMP note saved via td_component_notes "
                "for this path and surface it as ``note`` in the response. "
                "Default False to keep response sizes stable."
            ),
        ),
    ] = False,
    include_hints: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, attach a ``hints`` block via td_get_hints scoped to "
                "the inspected node's op_type and the 'inspect' response "
                "surface. Auto-injection still fires when surface-restricted "
                "hints exist for this op_type."
            ),
        ),
    ] = False,
) -> str:
    """Get detailed info about a node (type, errors, warnings, parameters).

    The parameters dict is capped at param_limit entries (default 50, hard
    ceiling 200) — full COMP serialization can blow past 80 KB. Use
    td_get_params with name/page filters when you need the rest.

    When ``include_notes=True``, any markdown note saved via
    ``td_component_notes`` for this path is attached as a ``note`` field.
    """
    finish = _tr._start_tool(ctx, "td_get_node_detail")
    try:
        data = await _tr._get_client(ctx).request(
            "node/detail",
            {"path": path, "param_limit": param_limit},
        )
        if include_notes and isinstance(data, dict):
            try:
                from td_mcp import component_notes_store, locations_store

                project_name = data.get("project_name") or data.get("project") or None
                project_hash, _ = locations_store.derive_project_id(project_name)
                store = component_notes_store.ComponentNotesStore()
                note = store.get(project_hash, path)
                if note:
                    data["note"] = note
            except Exception:
                # Notes lookup is best-effort; never break detail fetches.
                pass
        if response_format == ResponseFormat.MARKDOWN:
            lines = [f"## {data.get('name', '?')} (`{data.get('path', '?')}`)"]
            lines.append(f"- Type: {data.get('type', '?')} ({data.get('family', '?')})")
            if data.get("errors"):
                lines.append(f"- Errors: {data['errors']}")
            if data.get("warnings"):
                lines.append(f"- Warnings: {data['warnings']}")
            if data.get("note"):
                note = data["note"]
                if isinstance(note, dict):
                    lines.append("\n### Note")
                    lines.append((note.get("body") or "").strip())
            if data.get("parameters"):
                lines.append(_tr._format_params_markdown(data["parameters"], path))
            md_output = "\n".join(lines)
            return _tr._attach_hints(
                md_output,
                tool_name="td_get_node_detail",
                payload={"path": path, "op_type": data.get("type") if isinstance(data, dict) else None},
                force_query={"op_type": data.get("type")}
                if include_hints and isinstance(data, dict) and data.get("type")
                else None,
            )
        return _tr._attach_hints(
            _tr._as_json_output(data),
            tool_name="td_get_node_detail",
            payload={"path": path, "op_type": data.get("type") if isinstance(data, dict) else None},
            force_query={"op_type": data.get("type")}
            if include_hints and isinstance(data, dict) and data.get("type")
            else None,
        )
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_node_detail")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_params")
async def td_get_params(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Absolute node path", min_length=1),
    ],
    page: Annotated[
        str | None,
        Field(default=None, description="Filter by parameter page name"),
    ] = None,
    names: Annotated[
        list[str] | None,
        Field(default=None, description="Filter to specific parameter names"),
    ] = None,
    response_format: Annotated[
        ResponseFormat,
        Field(default=ResponseFormat.JSON, description="Output format"),
    ] = ResponseFormat.JSON,
) -> str:
    """Get parameter values and metadata for a node."""
    finish = _tr._start_tool(ctx, "td_get_params")
    try:
        body: dict[str, Any] = {"path": path}
        if page is not None:
            body["page"] = page
        if names is not None:
            body["names"] = names
        data = await _tr._get_client(ctx).request("node/params", body)
        if response_format == ResponseFormat.MARKDOWN:
            return _tr._format_params_markdown(data.get("parameters", {}), path)
        return _tr._as_json_output(data)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_params")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_set_params")
async def td_set_params(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Absolute node path", min_length=1),
    ],
    params: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Dictionary of parameter names to values. Supports five modes:\n"
                "• Static value (plain): {'seed': 42, 'colorr': 1.0}\n"
                "• Expression (reactive, updates every frame): "
                "{'seed': {'expr': 'absTime.seconds * 10'}, "
                "'tx': {'expr': \"op('noise1')['chan1']\"}}\n"
                "• Explicit static: {'seed': {'val': 42}}\n"
                "• Reset to default: {'seed': {'reset': true}} — "
                "resets value and clears expression\n"
                "• Clear expression: {'seed': {'mode': 'constant', 'val': 42}} — "
                "force constant mode\n\n"
                "Expressions make networks ALIVE — use them for anything that "
                "should move, react, or change over time."
            ),
            min_length=1,
        ),
    ],
    include_hints: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, attach a ``hints`` block via td_get_hints. "
                "Auto-injection still fires when the params dict assigns "
                "a string to a reference-style parameter "
                "(instanceop/material/camera/lights/geometry/top/chop/sop/dat/comp)."
            ),
        ),
    ] = False,
) -> str:
    """Set node parameters (static values or live expressions)."""
    finish = _tr._start_tool(ctx, "td_set_params")
    try:
        adjusted, warnings = _tr._apply_safety_to_set_params(
            _tr._get_safety_manager(ctx),
            path,
            dict(params),
        )
        body = {"path": path, "params": adjusted}

        data = await _tr._get_client(ctx).request("node/params/set", body)
        if warnings:
            data["safety_warnings"] = warnings

        _tr._audit_log(
            ctx,
            "td_set_params",
            {
                "path": path,
                "param_count": len(adjusted),
                "warnings": warnings,
            },
        )
        return _tr._attach_hints(
            _tr._as_json_output(data),
            tool_name="td_set_params",
            payload=body,
            force_query={"topic": "render_pipeline"} if include_hints else None,
        )
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_set_params")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_create_node")
async def td_create_node(
    ctx: Context,
    node_type: Annotated[
        str,
        Field(
            description=(
                "TouchDesigner operator type to create. Examples: "
                "TOPs: 'noiseTOP', 'levelTOP', 'nullTOP', 'compositeTOP', "
                "'feedbackTOP', 'moviefileinTOP' | "
                "CHOPs: 'waveCHOP', 'noiseCHOP', 'nullCHOP', 'mathCHOP', "
                "'constantCHOP', 'selectCHOP' | "
                "SOPs: 'sphereSOP', 'boxSOP', 'gridSOP', 'lineSOP', 'nullSOP', "
                "'transformSOP', 'noiseSOP' | "
                "DATs: 'textDAT', 'tableDAT', 'scriptDAT', 'nullDAT', "
                "'selectDAT', 'chopexecDAT' | "
                "COMPs: 'baseCOMP', 'containerCOMP', 'geometryCOMP', "
                "'cameraCOMP', 'lightCOMP' | "
                "MATs: 'pbrMAT', 'phongMAT', 'wireframeMAT', 'constMAT'"
            ),
            min_length=1,
        ),
    ],
    parent_path: Annotated[
        str,
        Field(
            default="/project1",
            description="Path to the parent COMP where the node will be created",
        ),
    ] = "/project1",
    name: Annotated[
        str | None,
        Field(
            default=None,
            description="Custom name for the new node. If None, TD assigns a default name.",
        ),
    ] = None,
    nodeX: Annotated[
        int | None,
        Field(
            default=None,
            description=(
                "Horizontal position in the network editor (pixels). "
                "Use multiples of 200 for clean spacing between nodes."
            ),
        ),
    ] = None,
    nodeY: Annotated[
        int | None,
        Field(
            default=None,
            description=(
                "Vertical position in the network editor (pixels). "
                "Use multiples of 200 for clean spacing between rows."
            ),
        ),
    ] = None,
    include_hints: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, attach a ``hints`` block sourced from td_get_hints "
                "for the chosen op_type. Auto-injection still fires for "
                "high-risk op_types (feedbackTOP, glslTOP, geometryCOMP, …) "
                "regardless of this flag."
            ),
        ),
    ] = False,
) -> str:
    """Create a new TouchDesigner operator."""
    # Re-instantiate so the CreateNodeInput custom @field_validator on
    # ``node_type`` (family-suffix check: TOP/CHOP/SOP/DAT/COMP/MAT/POPX/POP)
    # still runs. ``Annotated[str, Field(...)]`` captures min_length/description
    # but not cross-field or custom validators.
    validated = CreateNodeInput(
        parent_path=parent_path,
        node_type=node_type,
        name=name,
        nodeX=nodeX,
        nodeY=nodeY,
    )
    payload = validated.model_dump(exclude_none=True)
    raw = await _tr._forward(
        ctx,
        "td_create_node",
        "node/create",
        payload,
        audit_event="td_create_node",
    )
    return _tr._attach_hints(
        raw,
        tool_name="td_create_node",
        payload=payload,
        force_query={"op_type": node_type} if include_hints else None,
    )


@mcp.tool(name="td_delete_node")
async def td_delete_node(
    ctx: Context,
    path: Annotated[
        str,
        Field(
            description="Absolute path of the node to delete (e.g. '/project1/noise1')",
            min_length=1,
        ),
    ],
) -> str:
    """Delete a node by its absolute path.

    v1.4.6 Bug A PoC: explicit-args signature instead of the old
    ``params: DeleteNodeInput`` wrapper. FastMCP wraps ``params: Model``
    signatures under a ``params: {"$ref": ...}`` property that MCP clients
    collapse to an opaque ``{}``. Explicit args produce a flat schema the
    client can render directly — callers see ``path`` as a required
    string with description and min_length instead of having to guess.
    The ``Annotated[str, Field(...)]`` pattern carries the same validation
    the old Pydantic model had.
    """
    return await _tr._forward(
        ctx,
        "td_delete_node",
        "node/delete",
        {"path": path},
        audit_event="td_delete_node",
    )


@mcp.tool(name="td_copy_node")
async def td_copy_node(
    ctx: Context,
    source_path: Annotated[
        str,
        Field(description="Path of the node to copy", min_length=1),
    ],
    dest_parent: Annotated[
        str | None,
        Field(
            default=None,
            description=("Path of the destination parent COMP. If None, copies into the same parent."),
        ),
    ] = None,
    new_name: Annotated[
        str | None,
        Field(default=None, description="Name for the copy"),
    ] = None,
) -> str:
    """Copy/duplicate a node."""
    body: dict[str, Any] = {"source_path": source_path}
    if dest_parent is not None:
        body["dest_parent"] = dest_parent
    if new_name is not None:
        body["new_name"] = new_name
    return await _tr._forward(
        ctx,
        "td_copy_node",
        "node/copy",
        body,
        audit_event="td_copy_node",
    )


@mcp.tool(name="td_rename_node")
async def td_rename_node(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Current absolute path of the node", min_length=1),
    ],
    new_name: Annotated[
        str,
        Field(description="New name for the node", min_length=1, max_length=100),
    ],
) -> str:
    """Rename a node."""
    return await _tr._forward(
        ctx,
        "td_rename_node",
        "node/rename",
        {"path": path, "new_name": new_name},
        audit_event="td_rename_node",
    )


@mcp.tool(name="td_connect_nodes")
async def td_connect_nodes(
    ctx: Context,
    source_path: Annotated[
        str,
        Field(description="Path of the source (output) node", min_length=1),
    ],
    target_path: Annotated[
        str,
        Field(description="Path of the target (input) node", min_length=1),
    ],
    source_index: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Output connector index on the source node (0 = first output)",
        ),
    ] = 0,
    target_index: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Input connector index on the target node (0 = first input)",
        ),
    ] = 0,
) -> str:
    """Connect two nodes (source output → target input)."""
    return await _tr._forward(
        ctx,
        "td_connect_nodes",
        "node/connect",
        {
            "source_path": source_path,
            "target_path": target_path,
            "source_index": source_index,
            "target_index": target_index,
        },
        audit_event="td_connect_nodes",
    )


@mcp.tool(name="td_disconnect")
async def td_disconnect(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path of the node to disconnect", min_length=1),
    ],
    connector_type: Annotated[
        str,
        Field(
            default="input",
            description="Which connector side to disconnect: 'input' or 'output'",
        ),
    ] = "input",
    index: Annotated[
        int,
        Field(default=0, ge=0, description="Connector index to disconnect"),
    ] = 0,
) -> str:
    """Disconnect a node's input or output connector."""
    # Re-instantiate so the DisconnectInput custom @field_validator on
    # ``connector_type`` (must be 'input' or 'output') still runs.
    validated = DisconnectInput(path=path, connector_type=connector_type, index=index)
    return await _tr._forward(
        ctx,
        "td_disconnect",
        "node/disconnect",
        validated.model_dump(),
        audit_event="td_disconnect",
    )


@mcp.tool(name="td_get_connections")
async def td_get_connections(
    ctx: Context,
    path: Annotated[
        str,
        Field(
            description=("Absolute path to the node (e.g. '/project1/noise1', '/project1/geo1/sphere1')"),
            min_length=1,
        ),
    ],
) -> str:
    """Get upstream/downstream connections for a node."""
    return await _tr._forward(
        ctx,
        "td_get_connections",
        "node/connections",
        {"path": path},
    )
