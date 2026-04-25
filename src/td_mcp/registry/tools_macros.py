"""Macro template tools.

Part of the v1.5.0 Phase 2 module split.

Tools in this module (3):
    td_create_macro      — instantiate a macro template (feedback, etc.)
    td_list_macros       — enumerate available macro templates
    td_get_macro_params  — inspect parameter schema for a macro
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.models import MacroType
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_create_macro")
async def td_create_macro(
    ctx: Context,
    macro_type: Annotated[
        MacroType,
        Field(description="Macro template to create."),
    ],
    parent_path: Annotated[
        str,
        Field(
            default="/project1",
            description="Parent COMP path where the macro will be instantiated.",
        ),
    ] = "/project1",
    name: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional name prefix for all nodes created by this macro.",
        ),
    ] = None,
    nodeX: Annotated[
        int,
        Field(
            default=0,
            description="Macro origin X position in the network editor.",
        ),
    ] = 0,
    nodeY: Annotated[
        int,
        Field(
            default=0,
            description="Macro origin Y position in the network editor.",
        ),
    ] = 0,
    params: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description="Override template parameter defaults with custom values.",
        ),
    ] = None,
) -> str:
    """Create a macro template network."""
    finish = _tr._start_tool(ctx, "td_create_macro")
    try:
        engine = _tr._get_macro_engine(ctx)
        data = await engine.create_macro(
            parent_path=parent_path,
            macro_type=macro_type.value,
            name_prefix=name,
            node_x=nodeX,
            node_y=nodeY,
            overrides=params,
        )
        _tr._audit_log(
            ctx,
            "td_create_macro",
            {
                "macro_type": macro_type.value,
                "parent_path": parent_path,
                "name_prefix": name,
            },
        )
        return _tr._as_json_output(data)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_create_macro")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_list_macros")
async def td_list_macros(ctx: Context) -> str:
    finish = _tr._start_tool(ctx, "td_list_macros")
    try:
        data = _tr._get_macro_engine(ctx).list_macros()
        return _tr._as_json_output(data)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_list_macros")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_macro_params")
async def td_get_macro_params(
    ctx: Context,
    macro_type: Annotated[
        MacroType,
        Field(description="Macro template to inspect."),
    ],
) -> str:
    """Inspect parameter schema for a macro template."""
    finish = _tr._start_tool(ctx, "td_get_macro_params")
    try:
        data = _tr._get_macro_engine(ctx).get_macro_params(macro_type.value)
        return _tr._as_json_output(data)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_macro_params")
        return format_tool_error(exc)
    finally:
        finish()
