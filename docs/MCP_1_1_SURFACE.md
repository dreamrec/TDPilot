# TDPilot 1.1 Surface Guide

TDPilot 1.1 turns several high-friction TouchDesigner workflows into first-class MCP tools.

The practical goal is simple: fewer `td_exec_python` workarounds, better POP debugging, cleaner save/load control, and direct custom UI authoring.

## 1. What Changed

The runtime surface grows from 60 to 63 tools with three new top-level capabilities:

- `td_pop_inspect`
- `td_project_lifecycle`
- `td_custom_parameters`

It also upgrades `td_exec_python` so returned values are structured when they can be represented safely as JSON.

## 2. POPx

`td_pop_inspect` is the new POPx surface.

Why it exists:

- POPs are not just SOPs on the GPU.
- Generic geometry reads are not enough for particle debugging.
- Modern POP workflows need counts, attribute lists, changed attributes, and sampled attribute values.

What it returns:

- POP summary: points, prims, verts, allocation counts, dimension, line-strip limits
- Bounds when requested
- Point, primitive, and vertex attribute metadata
- Sampled values for requested attributes

Recommended workflow:

1. Call `td_pop_inspect` with defaults to get a fast summary.
2. Request only the attributes you care about for debugging.
3. Use `delayed=true` for repeated sampling on heavy GPU POPs.
4. Use `td_cooking_info` and `td_get_errors` alongside POP reads for performance debugging.

Example:

```json
{
  "path": "/project1/particles1",
  "point_attributes": ["P", "PartVel", "PartAge"],
  "count": 16,
  "delayed": true
}
```

## 3. Project Lifecycle

`td_project_lifecycle` provides first-class save/load/undo/redo control.

Supported actions:

- `status`
- `save`
- `load`
- `undo`
- `redo`
- `start_undo_block`
- `end_undo_block`
- `clear_undo`

Why it matters:

- Save/load/undo are not edge features in real TD work.
- These actions need explicit tooling because they shape how safe large edits are.
- Undo blocks let an agent group several related actions into one user-readable undo step.

Examples:

```json
{ "action": "status" }
```

```json
{ "action": "save", "path": "/shows/gh/gh_v06.toe", "save_external_toxs": true }
```

```json
{ "action": "start_undo_block", "name": "Build panoramic output controls" }
```

## 4. Custom Parameters

`td_custom_parameters` creates or updates custom parameter pages on COMPs.

Current supported kinds:

- `float`
- `int`
- `toggle`
- `menu`
- `str`
- `rgb`
- `rgba`
- `pulse`
- `file`
- `filesave`
- `folder`
- `chop`
- `comp`
- `dat`
- `mat`
- `header`

Supported metadata:

- labels
- display order
- tuple size for numeric params
- replace behavior
- defaults
- numeric min/max and normalized ranges
- clamp flags
- menu names and labels

Example:

```json
{
  "path": "/project1/master_ctrl",
  "page": "GHLook",
  "params": [
    { "kind": "float", "name": "panoramaweight", "label": "Panorama Weight", "default": 1.0, "min": 0.0, "max": 1.0 },
    { "kind": "rgb", "name": "clubtint", "label": "Club Tint", "default": [1.0, 0.65, 0.35] },
    { "kind": "toggle", "name": "favorcontinuity", "label": "Favor Continuity", "default": true }
  ]
}
```

## 5. Structured Python Results

`td_exec_python` still matters for advanced workflows, but it is no longer forced to flatten everything to strings.

Successful calls now return:

- `result`
- `result_type`
- `result_is_structured`
- `stdout`
- `stderr`

Use this for:

- compact structured probes
- quick operator/property introspection
- returning small dictionaries or lists from TD-side checks

Still avoid using it as a substitute for dedicated tools when a first-class tool exists.

## 6. Recommended Production Pattern

For non-trivial changes:

1. `td_project_lifecycle` with `status`
2. `td_snapshot_scene`
3. Build or modify structure
4. `td_custom_parameters` if UI is part of the workflow
5. `td_pop_inspect` if POP behavior is relevant
6. `td_get_errors`
7. `td_cooking_info`
8. `td_project_lifecycle` with `save`

## 7. What Still Is Not Solved

TDPilot 1.1 is stronger, but a few gaps remain:

- No atomic multi-tool transaction layer
- No dedicated low-cost TOP histogram / alpha / ROI inspector yet (planned for v1.3.2)
- Full Python mode is still configuration-driven through `TD_MCP_EXEC_MODE`
- Custom parameter editing is now first-class, but not every parameter-type nuance in TouchDesigner is wrapped yet

Real sessions also exposed several quality-of-life gaps that do not block work, but do slow it down:

- ~~No direct `list_tools` or `describe_tools` endpoint to verify the live MCP surface from inside a session~~ **Resolved in v1.3.0:** `td_describe_surface` returns live tool count, resource count, capabilities, and version.
- ~~No "expanded Python" middle ground that allows safe helpers like `json`, basic builtins, and small probes without enabling fully unrestricted execution~~ **Resolved in v1.3.0:** `standard` exec mode allows 14 curated safe imports with read-only introspection.
- Wiring still benefits from first-class tools for `connect input N` and `disconnect input N`, instead of falling back to Python connector workarounds
- Custom parameter creation is covered, but page-level operations such as create, remove, replace, and reorder should also be first-class
- Recursive inspection is not yet uniform across node, connection, and error queries, which makes deeper scene audits less predictable
- Imported tox workflows would benefit from warning filtering that separates scene-breaking errors from harmless sync or inactive-branch warnings
- Visual verification still needs a lighter-weight mode for low-token thumbnails or fast passive checks
- Snapshot persistence is available, but the safest production behavior would be stronger default persistence around risky edits
- Event-style subscriptions are still absent, so many monitoring tasks rely on polling rather than change-driven updates

## 8. Direction

The next frontier is not just "more tools".

It is a more explicit visual intent layer:

- project-scoped art direction memory
- panoramic composition rules
- safer batched edit transactions
- low-cost visual diagnostics

The near-term quality-of-life priorities are equally clear:

- ~~make the live tool surface self-describing~~ (v1.3.0: `td_describe_surface`)
- ~~add a safer middle tier between restricted and unrestricted Python~~ (v1.3.0: `standard` exec mode)
- expose common wiring and parameter-page edits as first-class tools
- standardize recursive inspection arguments and output shape
- classify warnings by operational severity
- make visual verification cheaper and easier to invoke during iteration
- reduce reliance on polling with subscription-style state change hooks
- bias the runtime toward safer default persistence during destructive edits

That is how the MCP moves from "capable" to "production-native".

## 9. Maintenance Rule

This guide should stay live.

When real production sessions expose something meaningful, repeated, or clearly worth improving, add it here instead of leaving it as conversational context only.

Good additions include:

- missing first-class tools that repeatedly force Python workarounds
- schema mismatches or inconsistent argument patterns across related tools
- warning or error cases that create noise during active TD work
- visual verification gaps that slow iteration or increase token cost
- persistence, safety, or undo behaviors that should be safer by default
- quality-of-life improvements that materially reduce friction in normal sessions

Prefer notes grounded in actual use over speculative feature lists.
