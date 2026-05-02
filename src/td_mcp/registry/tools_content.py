"""DAT content + custom-parameter + Python exec tools.

Part of the v1.5.0 Phase 2 module split.

Tools in this module (4):
    td_get_content         — read DAT text/table content
    td_set_content         — write DAT text/table content
    td_custom_parameters   — create custom parameter pages on COMPs
    td_exec_python         — execute Python inside TouchDesigner
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.models import CustomParametersInput, CustomParameterSpec
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_get_content")
async def td_get_content(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a DAT node", min_length=1),
    ],
) -> str:
    """Read DAT text/table content."""
    return await _tr._forward(ctx, "td_get_content", "node/content", {"path": path})


@mcp.tool(name="td_set_content")
async def td_set_content(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a DAT node", min_length=1),
    ],
    text: Annotated[
        str | None,
        Field(
            default=None,
            description="Text content to write (for Text DATs, Script DATs, etc.)",
        ),
    ] = None,
    table: Annotated[
        list[list[str]] | None,
        Field(
            default=None,
            description="Table content as 2D array of strings (for Table DATs)",
        ),
    ] = None,
) -> str:
    """Write DAT text/table content."""
    body: dict[str, Any] = {"path": path}
    if text is not None:
        body["text"] = text
    if table is not None:
        body["table"] = table
    return await _tr._forward(
        ctx,
        "td_set_content",
        "node/content/set",
        body,
        audit_event="td_set_content",
    )


@mcp.tool(name="td_custom_parameters")
async def td_custom_parameters(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a COMP with custom parameters", min_length=1),
    ],
    page: Annotated[
        str,
        Field(description="Custom page name", min_length=1, max_length=64),
    ],
    params: Annotated[
        list[CustomParameterSpec],
        Field(
            min_length=1,
            description=(
                "One or more parameter specifications to create on the page. "
                "Each spec has kind (float/int/toggle/menu/str/rgb/rgba/pulse/"
                "file/filesave/folder/chop/comp/dat/mat/header), name, and "
                "optional label/size/default/min/max."
            ),
        ),
    ],
) -> str:
    """Create or update a custom parameter page on a COMP."""
    # Re-instantiate so nested CustomParameterSpec.kind validator still runs.
    validated = CustomParametersInput(path=path, page=page, params=params)
    return await _tr._forward(
        ctx,
        "td_custom_parameters",
        "custom-parameters",
        validated.model_dump(),
        audit_event="td_custom_parameters",
    )


@mcp.tool(name="td_exec_python")
async def td_exec_python(
    ctx: Context,
    code: Annotated[
        str,
        Field(
            description=(
                "Python code to execute in TouchDesigner's Python environment. "
                "Has access to: op(), ops(), project, app, absTime, me, "
                "parent(), mod, ui, tdu. "
                "Set __result__ = <value> to return a value to the caller. "
                'Example: \'__result__ = op("/project1/noise1").par.type.ev'
                "al()'"
            ),
            min_length=1,
            max_length=50000,
        ),
    ],
    timeout_ms: Annotated[
        int | None,
        Field(
            default=None,
            description=(
                "Optional per-call execution timeout in milliseconds. "
                "When omitted, TouchDesigner uses its configured default. "
                "Bounds: 100-60000 ms."
            ),
            ge=100,
            le=60000,
        ),
    ] = None,
    include_hints: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, attach a ``hints`` block via td_get_hints. "
                "Auto-injection still fires when the code touches restricted "
                "patterns (.text=, .par.file=, imports, OS escapes)."
            ),
        ),
    ] = False,
) -> str:
    """Execute Python code inside TouchDesigner."""
    finish = _tr._start_tool(ctx, "td_exec_python")
    try:
        _tr._enforce_exec_mode(code)
        mode = _tr._current_exec_mode()
        body: dict[str, Any] = {
            "code": code,
            "exec_mode": mode,
        }
        # Forward the per-call timeout only when the caller set one. Omitting
        # the key lets the TD-side choose its configured default.
        if timeout_ms is not None:
            body["timeout_ms"] = timeout_ms
        data = await _tr._get_client(ctx).request("exec", body)
        _tr._audit_log(
            ctx,
            "td_exec_python",
            {
                "exec_mode": mode,
                "code_length": len(code),
                "timeout_ms": timeout_ms,
            },
        )
        return _tr._attach_hints(
            _tr._as_json_output(data),
            tool_name="td_exec_python",
            payload=body,
            force_query={"topic": "render_pipeline"} if include_hints else None,
        )
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_exec_python")
        return format_tool_error(exc)
    finally:
        finish()
