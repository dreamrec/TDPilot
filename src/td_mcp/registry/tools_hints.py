"""Hints tool — concise, source-cited rules surfaced at the moment of risk.

``td_get_hints`` is a thin orchestrator over ``src/td_mcp/hints/`` packs.
It does NOT touch TouchDesigner — pure host-side reads from the YAML
hint corpus.

The same engine powers automatic hint injection on high-risk tools
(``td_create_node``, ``td_set_params``, ``td_exec_python``,
``td_get_errors``, ``td_plan_patch``, ``td_patch_preview``); see
``src/td_mcp/hints/orchestrator.py:auto_inject_hints``.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.hints import query_hints
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_get_hints")
async def td_get_hints(
    ctx: Context,
    topic: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Topic name. Allowed values evolve with the shipped hint corpus; "
                "current topics are returned in every response under "
                "``available_topics``. Examples: 'feedback', 'glsl', "
                "'render_pipeline', 'audio_reactive', 'extensions'."
            ),
        ),
    ] = None,
    op_type: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "OP type to get type-specific hints (e.g., 'glslTOP', "
                "'feedbackTOP', 'geometryCOMP'). Combines additively with "
                "``topic`` when both are set."
            ),
        ),
    ] = None,
    intent: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Free-text description of what you're about to do. Used to "
                "score ``intent_match`` clauses on individual hints (e.g. "
                "intent='set up trail decay' bumps the level.opacity hint)."
            ),
        ),
    ] = None,
    node_path: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional: path of node about to be modified. Reserved for "
                "future hints that compute against live node state."
            ),
        ),
    ] = None,
    error_text: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional: error/warning text to match against ``error_match`` "
                "clauses. Mirrors what auto-injection does after a failed "
                "td_get_errors call."
            ),
        ),
    ] = None,
    surface: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional response-surface filter (v1.6.2). Allowed values: "
                "'create_node', 'set_params', 'exec', 'errors', 'plan', "
                "'preview', 'query', 'inspect', 'screenshot'. Surface-restricted "
                "hints (those declaring ``when.surface``) only fire when the "
                "requested surface matches; hints without a surface clause "
                "fire from any surface. Auto-injection from each tool wrapper "
                "passes the tool's natural surface automatically; explicit "
                "callers pass it here to narrow results."
            ),
        ),
    ] = None,
    max_hints: Annotated[
        int,
        Field(
            default=8,
            ge=1,
            le=20,
            description="Cap on returned hints. Critical-priority hints win ties.",
        ),
    ] = 8,
) -> str:
    """Return concise, source-cited hints for a topic, op_type, or intent.

    Sources include hint packs shipped under ``src/td_mcp/hints/packs/``
    (skill pitfalls, canonical recipes), with future expansion to live
    knowledge-store essays. Every hint cites its source.

    The response shape:

        {
          "topic": ...,
          "op_type": ...,
          "confidence": 0.87,
          "hints": [
            {"id": ..., "priority": "critical|useful|context", "rule": ...,
             "source": "tdpilot-core §11", "source_kind": "skill_pitfall"},
            ...
          ],
          "next_tools": ["td_get_param_help", "td_screenshot"],
          "hint_pack_version": "v1.6.0-1",
          "available_topics": [...],
          "available_op_types": [...]
        }
    """
    finish = _tr._start_tool(ctx, "td_get_hints")
    try:
        result: dict[str, Any] = query_hints(
            topic=topic,
            op_type=op_type,
            intent=intent,
            node_path=node_path,
            error_text=error_text,
            surface=surface,
            max_hints=max_hints,
        )
        return _tr._as_json_output(result)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_hints")
        return format_tool_error(exc)
    finally:
        finish()
