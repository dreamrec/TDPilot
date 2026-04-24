"""Lint-style regression: no MCP tool should reintroduce the opaque
``params: InputModel`` signature pattern that Bug A (v1.5.0) eliminated.

Each tool's MCP schema (as emitted by FastMCP's tool manager) must have its
argument properties at the top level, not wrapped in a single ``params`` key
that points at a ``$ref`` (which MCP clients don't resolve — they collapse
it to an opaque ``{}``).

Pins the 69-tool migration done in v1.5.0 commits 98045bb..0b8afa1 (Bug A
batches 1-6) + the final 12-tool Batch 7 so no future PR can silently
reintroduce the pattern.

See docs/superpowers/reports/2026-04-24-bug-a-opaque-params-investigation.md
for the full investigation, and the v1.5.0 execution plan at
docs/superpowers/plans/2026-04-24-v1.5.0-execution-plan.md (Chunk 2 Task
2.8) for the hardening spec.
"""

from __future__ import annotations

import asyncio
import json

import td_mcp.server as server


def test_no_tool_has_opaque_params_wrapper():
    """Every MCP tool must expose explicit property names, not a single
    opaque ``params`` key that dereferences to a model ``$ref``.

    If this fails, a new tool (or a regression on an existing one) is back
    on the pre-v1.5.0 ``async def td_foo(params: InputModel, ctx: Context)``
    signature pattern. Rewrite the signature to
    ``async def td_foo(ctx: Context, <explicit args>)`` using the
    ``Annotated[T, Field(...)]`` pattern. Re-instantiate the Pydantic model
    inside the body if it has custom ``@field_validator`` decorators.
    """
    tools = asyncio.run(server.mcp.list_tools())
    offenders: list[str] = []
    for tool in tools:
        schema = tool.inputSchema or {}
        props = schema.get("properties", {})
        # The distinctive Bug-A signature: properties has exactly one entry
        # called "params" AND the schema references $defs (i.e., FastMCP
        # wrapped a Pydantic model under a $ref).
        if list(props.keys()) == ["params"] and "$ref" in json.dumps(props):
            offenders.append(tool.name)

    assert not offenders, (
        f"These tools are back on the pre-v1.5.0 opaque-params pattern: "
        f"{offenders}. Rewrite to explicit args. See "
        f"docs/superpowers/reports/2026-04-24-bug-a-opaque-params-investigation.md."
    )


def test_every_tool_schema_has_field_descriptions():
    """Migrated schemas should describe what each field is for.

    Most fields should carry a ``description``. Zero-arg tools (e.g.
    ``td_timeline``, ``td_python_classes``, ``td_color_pipeline``) naturally
    have zero properties and nothing to describe — those are fine. Tools
    with properties SHOULD describe them so the flat-schema win from Bug A
    actually helps MCP clients.
    """
    tools = asyncio.run(server.mcp.list_tools())
    missing_descriptions: list[str] = []

    for tool in tools:
        schema = tool.inputSchema or {}
        props = schema.get("properties", {})
        for field_name, field_spec in props.items():
            if not isinstance(field_spec, dict):
                continue
            # $ref fields inherit descriptions from the referenced definition
            # (e.g. ResponseFormat enum, ParamBound sub-model). Skip them
            # since FastMCP doesn't copy the sub-definition description up.
            if "$ref" in field_spec:
                continue
            if not field_spec.get("description"):
                missing_descriptions.append(f"{tool.name}.{field_name}")

    # Threshold of 25 accommodates pre-Bug-A explicit tools that historically
    # lacked Field descriptions (21 known fields across tools like
    # td_search_official_docs, td_get_operator_doc, td_lookup_snippets, etc.).
    # Those were NOT introduced by the Bug A migration — they were always
    # explicit, just under-documented. Tightening this threshold to <10 is a
    # good v1.5.0 polish task once those tools get proper Field descriptions.
    assert len(missing_descriptions) < 25, (
        f"Too many fields lack Field(description=...): "
        f"{missing_descriptions[:20]} (total {len(missing_descriptions)}). "
        f"Each rewritten tool should annotate its fields for clients."
    )
