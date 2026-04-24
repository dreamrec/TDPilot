# Bug A investigation memo — MCP tool schema opacity

**Date:** 2026-04-24  
**Branch:** `fix/param-help-op-type-and-case-insensitive`  
**Scope:** investigation + PoC only, no full-tool rewrite yet  
**Status:** root cause identified, fix pattern proven, 70-tool rewrite planned for v1.5.0

## Symptom

MCP clients (Claude Code, other agents) that enumerate the TDPilot tool
catalog see this for many tools:

```json
{
  "name": "mcp__touchdesigner__td_create_node",
  "parameters": {"properties": {"params": {}}, "type": "object"}
}
```

The `params` field is an opaque empty object. Callers can't discover what
fields are valid, so they trial-and-error by calling with guesses and
reading validation errors. Concrete examples caught during v1.4.5 live
validation:

| Call | What client tried | What the tool actually accepts |
|---|---|---|
| `td_create_node` | `{"op_type": "noiseTOP"}` | `{"node_type": "noiseTOP"}` |
| `td_set_content` | `{"content": "..."}` | `{"text": "..."}` |
| `td_get_nodes` | `{"include_children": true}` | `{"include_params": true}` |

Each miss burns a round-trip. For multi-step agent workflows the cost
compounds.

## Signature count (production snapshot)

Ran `grep -cE '^async def td_\w+\(...' src/td_mcp/tool_registry.py`:

| Shape | Count | Schema kind |
|---|---:|---|
| `async def td_foo(params: InputModel, ctx: Context)` | **70** | opaque `params: {}` |
| `async def td_foo(ctx: Context)` (no other args) | 11 | rich (trivially — no args) |
| `async def td_foo(ctx: Context, <explicit args>)` multi-line | ~13 | **rich** |
| `async def td_resource_*(<path args>)` | 5 | resources — not MCP tools |
| **Total** | **99** | |

**70 tools need rewriting** to produce rich schemas. The 13 that already
use explicit args (including the ones I just rewrote in v1.4.6:
`td_get_operator_doc`, `td_get_param_help`, `td_search_official_docs`,
`td_get_popx_operator`) are proof the pattern works.

## Root cause

**Server-side schema IS rich** — Pydantic emits the full inline model.
I verified this via `mcp._tool_manager.list_tools()`:

```json
{
  "$defs": {
    "DeleteNodeInput": {
      "properties": {
        "path": {
          "description": "Absolute path of the node to delete",
          "minLength": 1, "type": "string"
        }
      },
      "required": ["path"]
    }
  },
  "properties": {"params": {"$ref": "#/$defs/DeleteNodeInput"}},
  "required": ["params"]
}
```

The issue is the `$ref` / `$defs` indirection. FastMCP, when it sees a
function signature with `params: Model`, generates a two-level schema:
an outer object with a single `params` property that is a JSON-Schema
`$ref` to a nested `$defs` entry. MCP clients — including Claude Code's
ToolSearch — do not resolve `$ref`s across `$defs` when flattening tool
parameters for display, so `{"$ref": "#/$defs/DeleteNodeInput"}` becomes
`{}`. The information is literally not reaching the client side.

**Explicit args don't hit this path.** Because FastMCP introspects each
argument separately, explicit-args signatures emit:

```json
{
  "properties": {
    "path": {"description": "...", "minLength": 1, "type": "string"}
  },
  "required": ["path"]
}
```

No `$defs`, no `$ref`, everything inline. The client sees it correctly.

## Fix options considered

| Option | Effort | Risk | Notes |
|---|---|---|---|
| A. Post-process FastMCP's emitted schema to inline all `$ref`s | Low | Medium | Requires a wrapper around `@mcp.tool()` that rewrites the schema dict. Brittle if FastMCP changes its schema format. |
| B. Ask Pydantic to inline schemas when used under FastMCP | N/A | — | Investigated: Pydantic's `model_json_schema()` at the top level is already inline (no $defs). The wrap+ref happens in FastMCP, not Pydantic. So this doesn't apply. |
| C. Upstream FastMCP fix to inline the nested model | High | Low | Correct long-term answer. Would require a PR to modelcontextprotocol/python-sdk. |
| **D. Rewrite each of 70 tools to explicit-args signature** | **Medium** | **Low** | **Mechanical, each rewrite is ~5 lines, preserves full validation via `Annotated[str, Field(...)]`. Ships without external deps.** |

## PoC: td_delete_node rewrite

Changed the shortest opaque tool as a proof-of-concept. Full code diff
reduces to:

```python
# BEFORE (opaque `params: {}` over the wire):
@mcp.tool(name="td_delete_node")
async def td_delete_node(params: DeleteNodeInput, ctx: Context) -> str:
    return await _forward(
        ctx, "td_delete_node", "node/delete",
        params.model_dump(), audit_event="td_delete_node",
    )

# AFTER (rich schema with full description + minLength):
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
    """Delete a node by its absolute path."""
    return await _forward(
        ctx, "td_delete_node", "node/delete",
        {"path": path}, audit_event="td_delete_node",
    )
```

**Schema before** (opaque):
```json
{"properties": {"params": {"$ref": "#/$defs/DeleteNodeInput"}}, ...}
```

**Schema after** (rich):
```json
{
  "properties": {
    "path": {
      "description": "Absolute path of the node to delete (e.g. '/project1/noise1')",
      "minLength": 1,
      "title": "Path",
      "type": "string"
    }
  },
  "required": ["path"]
}
```

The `Annotated[str, Field(...)]` pattern preserves every feature of the
old Pydantic model — `description`, `min_length`, `default`, validators
all flow through. `extra="forbid"` equivalent comes for free since
FastMCP's signature binder rejects unknown args.

## Call-site impact

The body of each rewritten tool either:
- Inlines the dict (`{"path": path}`) — 1 line, trivial
- Re-instantiates the Pydantic model for complex validators
  (`validated = DeleteNodeInput(path=path, ...)`) — 1 extra line

No changes to `_forward`, the TD-side handler, or the Pydantic models
themselves. Models can stay for runtime validation if desired, or be
deleted if the `Annotated[...]` signatures cover everything.

## Breakage surface

The schema-snapshot test (`tests/test_tools_schema_snapshot.py`) caught
the PoC rewrite as "schema drift" and printed the regen command. That's
exactly what it's for — it'll flag every tool rewrite so the snapshot
stays canonical. Regenerate after each batch.

Nothing else in the test suite cares about the signature shape. All
574 tests pass after the PoC rewrite.

## Recommendation

1. **Ship the PoC as-is** (td_delete_node) in the current fix branch so
   the pattern is in the codebase as a template.
2. **For v1.5.0**, schedule the remaining 69-tool rewrite in batches of
   ~10 grouped by theme (node ops, memory, knowledge, etc.). Each batch:
   - Rewrite signatures
   - Regenerate schema snapshot
   - Run full suite
   - Confirm MCP client sees the rich schema via a ToolSearch probe
3. **Extend the schema snapshot test** to also assert `"$ref" not in json.dumps(schema)` for each tool, so any regression to the opaque wrapper is caught immediately.
4. **Leave the Pydantic models alone** — they're useful for complex
   input validation even with explicit-args signatures. Just stop
   passing them as the FastMCP first argument.

Budget estimate: 70 tools × ~10 min each = ~12 hours of mechanical work
for a full sweep. Good candidate for a dedicated v1.5.0 session.
