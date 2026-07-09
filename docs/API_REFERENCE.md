# TDPilot API Reference

<!-- BEGIN GENERATED: tool-reference (scripts/gen_api_reference.py) -->

> TDPilot v2.0.3 | 114 tools | This region is **generated** from the FastMCP registry by `scripts/gen_api_reference.py` — do not edit it by hand. Regenerate with `uv run python scripts/gen_api_reference.py`; CI enforces freshness with `--check`. Sections group tools by their `src/td_mcp/registry/` module of origin.

## Table of Contents

1. [Scene & Server Info](#1-scene--server-info)
2. [Node Graph & Parameters](#2-node-graph--parameters)
3. [Content & Python Execution](#3-content--python-execution)
4. [Data Inspection & Diagnostics](#4-data-inspection--diagnostics)
5. [Runtime State](#5-runtime-state)
6. [Timeline, Lifecycle & Python Help](#6-timeline-lifecycle--python-help)
7. [Events & Subscriptions](#7-events--subscriptions)
8. [Technique Memory & Preferences](#8-technique-memory--preferences)
9. [User Knowledge Store](#9-user-knowledge-store)
10. [Safety & Stability](#10-safety--stability)
11. [Snapshots](#11-snapshots)
12. [Macros](#12-macros)
13. [Planning & Project Audit](#13-planning--project-audit)
14. [Patch Pipeline](#14-patch-pipeline)
15. [Vision & Frame Analysis](#15-vision--frame-analysis)
16. [Visual Monitoring & Streaming](#16-visual-monitoring--streaming)
17. [Visual Optimization & Dynamics](#17-visual-optimization--dynamics)
18. [Official & POPx Knowledge](#18-official--popx-knowledge)
19. [Recommendations](#19-recommendations)
20. [Hints](#20-hints)
21. [Component Notes](#21-component-notes)
22. [TD 2025 Native & System](#22-td-2025-native--system)
23. [Tool Batch](#23-tool-batch)
24. [Brain Planning & Transactions](#24-brain-planning--transactions)
25. [Sync, Self-Update & Activity](#25-sync-self-update--activity)

_Hand-written sections (response envelope, environment variables, exec modes, response formats, macro types) follow the generated region below._

---

## 1. Scene & Server Info

_Registry module: `src/td_mcp/registry/tools_info.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_get_capabilities` | Detect MCP client capabilities plus server/component versions and runtime config. Returns a JSON envelope. | _(none)_ | Returns a JSON envelope. |
| `td_get_info` | Get TouchDesigner project info: version, build, project name, OS. Returns a JSON envelope. | _(none)_ | Returns a JSON envelope. |
| `td_get_server_metrics` | Get MCP server runtime metrics: telemetry, events, streams, safety, snapshots, jobs. Returns a JSON envelope. | _(none)_ | Returns a JSON envelope. |
| `td_list_families` | List available operator families (TOP, CHOP, SOP, DAT, COMP, MAT, POP). Returns a JSON envelope. | _(none)_ | Returns a JSON envelope. |

---

## 2. Node Graph & Parameters

_Registry module: `src/td_mcp/registry/tools_graph.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_connect_nodes` | Connect two nodes (source output → target input). | `source_path` (string, **required**): Path of the source (output) node<br>`target_path` (string, **required**): Path of the target (input) node<br>`source_index` (integer, opt, default `0`): Output connector index on the source node (0 = first output)<br>`target_index` (integer, opt, default `0`): Input connector index on the target node (0 = first input) | JSON envelope (string). |
| `td_copy_node` | Copy/duplicate a node. | `source_path` (string, **required**): Path of the node to copy<br>`dest_parent` (string, opt, default `null`): Path of the destination parent COMP. If None, copies into the same parent.<br>`new_name` (string, opt, default `null`): Name for the copy | JSON envelope (string). |
| `td_create_node` | Create a new TouchDesigner operator. | `node_type` (string, **required**): TouchDesigner operator type to create. Examples: TOPs: 'noiseTOP', 'levelTOP', 'nullTOP', 'compositeTOP', 'feedbackTOP', 'moviefileinTOP' \| CHOPs: 'waveCHOP', 'noiseCHOP', 'nullCHOP', 'mathCHOP', 'constantCHOP', 'selectCHOP' \| SOPs: 'sphereSOP', 'boxSOP', 'gridSOP', 'lineSOP', 'nullSOP', 'transformSOP', 'noiseSOP' \| DATs: 'textDAT', 'tableDAT', 'scriptDAT', 'nullDAT', 'selectDAT', 'chopexecDAT' \| COMPs: 'baseCOMP', 'containerCOMP', 'geometryCOMP', 'cameraCOMP', 'lightCOMP' \| MATs: 'pbrMAT', 'phongMAT', 'wireframeMAT', 'constMAT'<br>`parent_path` (string, opt, default `"/project1"`): Path to the parent COMP where the node will be created<br>`name` (string, opt, default `null`): Custom name for the new node. If None, TD assigns a default name.<br>`nodeX` (integer, opt, default `null`): Horizontal position in the network editor (pixels). Use multiples of 200 for clean spacing between nodes.<br>`nodeY` (integer, opt, default `null`): Vertical position in the network editor (pixels). Use multiples of 200 for clean spacing between rows.<br>`include_hints` (boolean, opt, default `false`): If True, attach a ``hints`` block sourced from td_get_hints for the chosen op_type. Auto-injection still fires for high-risk op_types (feedbackTOP, glslTOP, geometryCOMP, …) regardless of this flag. | JSON envelope (string). |
| `td_delete_node` | Delete a node by its absolute path. | `path` (string, **required**): Absolute path of the node to delete (e.g. '/project1/noise1') | JSON envelope (string). |
| `td_disconnect` | Disconnect a node's input or output connector. | `path` (string, **required**): Path of the node to disconnect<br>`connector_type` (string, opt, default `"input"`): Which connector side to disconnect: 'input' or 'output'<br>`index` (integer, opt, default `0`): Connector index to disconnect | JSON envelope (string). |
| `td_get_connections` | Get upstream/downstream connections for a node. | `path` (string, **required**): Absolute path to the node (e.g. '/project1/noise1', '/project1/geo1/sphere1') | JSON envelope (string). |
| `td_get_node_detail` | Get detailed info about a node (type, errors, warnings, parameters). | `path` (string, **required**): Absolute path to the node (e.g. '/project1/noise1', '/project1/geo1/sphere1')<br>`response_format` (enum: `markdown`, `json`, opt, default `"json"`): Output format<br>`param_limit` (integer, opt, default `50`): Max parameters to serialize. Default 50; hard cap 200. If the node has more, the response sets parameters_truncated=true and parameters_total to the real count. Use td_get_params for the rest.<br>`include_notes` (boolean, opt, default `false`): If True, look up any per-COMP note saved via td_component_notes for this path and surface it as ``note`` in the response. Default False to keep response sizes stable.<br>`include_hints` (boolean, opt, default `false`): If True, attach a ``hints`` block via td_get_hints scoped to the inspected node's op_type and the 'inspect' response surface. Auto-injection still fires when surface-restricted hints exist for this op_type. | JSON envelope (string). |
| `td_get_nodes` | List child nodes at a path. | `path` (string, opt, default `"/"`): Absolute path to a COMP node whose children to list (e.g. '/', '/project1', '/project1/myComp')<br>`family` (string, opt, default `null`): Filter by operator family: TOP, CHOP, SOP, DAT, COMP, MAT, or PANEL<br>`type` (string, opt, default `null`): Filter by specific operator type (e.g. 'noiseTOP', 'waveCHOP', 'textDAT')<br>`include_params` (boolean, opt, default `false`): If true, include all parameters for each node (slower for large networks)<br>`limit` (integer, opt, default `100`): Max number of nodes to return<br>`offset` (integer, opt, default `0`): Pagination offset<br>`response_format` (enum: `markdown`, `json`, opt, default `"json"`): Output format | JSON envelope (string). |
| `td_get_params` | Get parameter values and metadata for a node. | `path` (string, **required**): Absolute node path<br>`page` (string, opt, default `null`): Filter by parameter page name<br>`names` (list[string], opt, default `null`): Filter to specific parameter names<br>`response_format` (enum: `markdown`, `json`, opt, default `"json"`): Output format | JSON envelope (string). |
| `td_rename_node` | Rename a node. | `path` (string, **required**): Current absolute path of the node<br>`new_name` (string, **required**): New name for the node | JSON envelope (string). |
| `td_set_params` | Set node parameters (static values or live expressions). | `path` (string, **required**): Absolute node path<br>`params` (object, **required**): Dictionary of parameter names to values. Supports five modes: • Static value (plain): {'seed': 42, 'colorr': 1.0} • Expression (reactive, updates every frame): {'seed': {'expr': 'absTime.seconds * 10'}, 'tx': {'expr': "op('noise1')['chan1']"}} • Explicit static: {'seed': {'val': 42}} • Reset to default: {'seed': {'reset': true}} — resets value and clears expression • Clear expression: {'seed': {'mode': 'constant', 'val': 42}} — force constant mode Expressions make networks ALIVE — use them for anything that should move, react, or change over time.<br>`include_hints` (boolean, opt, default `false`): If True, attach a ``hints`` block via td_get_hints. Auto-injection still fires when the params dict assigns a string to a reference-style parameter (instanceop/material/camera/lights/geometry/top/chop/sop/dat/comp).<br>`param_semantics_policy` (enum: `warn`, `block`, opt, default `"warn"`): Docs-grounded parameter safety policy for direct writes. 'warn' (default) preserves normal direct-tool behavior with attached findings — the write PROCEEDS even on invalid enum / out-of-range / bad op-reference; 'block' refuses the write before mutation when parameter semantics find invalid, unknown, or high-risk bindings. NOTE: this direct path is advisory by default. The brain/transaction path (td_brain_plan → td_brain_execute) HARD-FAILS the same contract violations. Pass 'block' here for equivalent strictness on direct writes. | JSON envelope (string). |

---

## 3. Content & Python Execution

_Registry module: `src/td_mcp/registry/tools_content.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_custom_parameters` | Create or update a custom parameter page on a COMP. | `path` (string, **required**): Path to a COMP with custom parameters<br>`page` (string, **required**): Custom page name<br>`params` (list[object], **required**): One or more parameter specifications to create on the page. Each spec has kind (float/int/toggle/menu/str/rgb/rgba/pulse/file/filesave/folder/chop/comp/dat/mat/header), name, and optional label/size/default/min/max. | JSON envelope (string). |
| `td_exec_python` | Execute Python code inside TouchDesigner. | `code` (string, **required**): Python code to execute in TouchDesigner's Python environment. Has access to: op(), ops(), project, app, absTime, me, parent(), mod, ui, tdu. Set __result__ = <value> to return a value to the caller. Example: '__result__ = op("/project1/noise1").par.type.eval()'<br>`timeout_ms` (integer, opt, default `null`): Optional per-call execution timeout in milliseconds. When omitted, TouchDesigner uses its configured default. Bounds: 100-60000 ms.<br>`include_hints` (boolean, opt, default `false`): If True, attach a ``hints`` block via td_get_hints. Auto-injection still fires when the code touches restricted patterns (.text=, .par.file=, imports, OS escapes). | JSON envelope (string). |
| `td_get_content` | Read DAT text/table content. | `path` (string, **required**): Path to a DAT node | JSON envelope (string). |
| `td_set_content` | Write DAT text/table content. | `path` (string, **required**): Path to a DAT node<br>`text` (string, opt, default `null`): Text content to write (for Text DATs, Script DATs, etc.)<br>`table` (list[list[string]], opt, default `null`): Table content as 2D array of strings (for Table DATs) | JSON envelope (string). |

---

## 4. Data Inspection & Diagnostics

_Registry module: `src/td_mcp/registry/tools_data.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_chop_data` | Read CHOP channel data (values/samples). | `path` (string, **required**): Path to a CHOP node<br>`channels` (list[string], opt, default `null`): List of channel names to read. If None, reads all channels.<br>`range` (list[integer], opt, default `null`): Sample range [start, end] to read. If None, reads all samples. | JSON envelope (string). |
| `td_cooking_info` | Get cooking/performance info for a subtree. | `path` (string, opt, default `"/"`): Root path to inspect<br>`recurse` (boolean, opt, default `false`): Recursively inspect children<br>`sort_by` (string, opt, default `"cookTime"`): Sort by: 'cookTime' or 'cpuCookTime'<br>`limit` (integer, opt, default `20`): Max nodes to return | JSON envelope (string). |
| `td_geometry_data` | Read SOP/POP geometry data (points/prims). | `path` (string, **required**): Path to a SOP or POP node<br>`include_points` (boolean, opt, default `true`): Include point position data<br>`include_prims` (boolean, opt, default `false`): Include primitive data<br>`limit` (integer, opt, default `500`): Max points/prims to return | JSON envelope (string). |
| `td_get_errors` | Get errors + warnings for a node (optionally recursive). | `path` (string, opt, default `"/"`): Node path to check<br>`recurse` (boolean, opt, default `true`): Recursively check children<br>`max_depth` (integer, opt, default `10`): Max recursion depth (prevents runaway on huge projects)<br>`include_hints` (boolean, opt, default `false`): If True, attach a ``hints`` block via td_get_hints. Auto-injection still fires when the response contains known error patterns (eg. 'Not enough sources', 'extension', 'missing input'). | JSON envelope (string). |
| `td_pop_inspect` | Read structured POP metadata and attribute samples. | `path` (string, **required**): Path to a POP node<br>`include_bounds` (boolean, opt, default `true`): Include POP bounds and dimension metadata<br>`include_attributes` (boolean, opt, default `true`): Include point/prim/vert attribute metadata<br>`point_attributes` (list[string], opt, default `null`): Specific point attributes to sample. If omitted, the tool samples common attributes such as P, PartVel, PartAge, Noise, and PartForce when present.<br>`prim_attributes` (list[string], opt, default `null`): Specific primitive attributes to sample. If omitted, no primitive attribute samples are returned unless requested.<br>`vert_attributes` (list[string], opt, default `null`): Specific vertex attributes to sample. If omitted, no vertex attribute samples are returned unless requested.<br>`start` (integer, opt, default `0`): Starting element index for attribute sampling<br>`count` (integer, opt, default `32`): Max elements to sample per requested attribute<br>`delayed` (boolean, opt, default `false`): Use TouchDesigner's delayed GPU readback mode where supported to reduce stalls | JSON envelope (string). |
| `td_screenshot` | Capture a TOP frame. | `path` (string, **required**): Path to a TOP node to capture as an image (e.g. '/project1/null1', '/project1/render1')<br>`quality` (number, opt, default `0.5`): JPEG quality from 0.0 (smallest) to 1.0 (best). Default 0.5 gives good diagnostic quality at ~85KB.<br>`save_path` (string, opt, default `null`): Optional disk destination. When set, TouchDesigner writes the image to this path and the tool returns metadata + the saved path with NO base64 payload (near-zero token cost — the cheap visual-verify loop). Accepts an absolute path under your home directory or a bare filename (saved under ~/.tdpilot/captures/). Extension must be .png/.jpg/.jpeg. | JSON envelope (string). |
| `td_search_nodes` | Search nodes across a subtree. | `query` (string, **required**): Search string (case-insensitive)<br>`path` (string, opt, default `"/"`): Root path to search from<br>`search_type` (string, opt, default `null`): DEPRECATED — prefer ``scopes``. One of 'name', 'type', 'family', 'all'. When both are set, ``scopes`` wins.<br>`scopes` (list[string], opt, default `null`): Search scopes (v1.6.0+). Any of: 'name', 'type', 'family', 'all', 'dat_text' (search DAT text contents), 'param_exprs' (search parameter expressions). Multiple scopes merge. Defaults to ['all'].<br>`limit` (integer, opt, default `50`): Max results | JSON envelope (string). |

---

## 5. Runtime State

_Registry module: `src/td_mcp/registry/tools_state.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_get_focus` | Return where the user currently is in TouchDesigner: active network pane, selection, project metadata, timeline state. Reduces the cold-start tax of needing to ask the user 'what path are you working in?' before every patch. | `include_pane_history` (boolean, opt, default `false`): Reserved for future use; pane-history capture is not yet wired. | Return where the user currently is in TouchDesigner: active network pane, selection, project metadata, timeline state. |
| `td_get_state_vector` | Aggregated scene state vector (cached for _tr.TD_STATE_VECTOR_TTL seconds). | `path` (string, opt, default `"/project1"`): Root path for aggregated diagnostics.<br>`force_refresh` (boolean, opt, default `false`): Bypass cache and fetch fresh state. | JSON envelope (string). |
| `td_get_timescale_state` | Beat/phrase derived timeline state. | `bpm_hint` (number, opt, default `null`): Optional BPM hint. Defaults to 120 when omitted.<br>`beats_per_bar` (integer, opt, default `4`): Musical beats per bar for phase calculations. | JSON envelope (string). |
| `td_locations` | Save, list, jump-to, rename, or delete named network locations per project. Storage is host-side JSON in ``~/.tdpilot/locations/<hash>.json`` and survives session restarts. Pairs with td_get_focus to give the agent + user a shared spatial vocabulary for big projects. | `action` (string, **required**): Action to perform: 'save' (capture current focus or override path), 'list' (return all per-project locations), 'go' (navigate to a saved location), 'delete' (remove by name), or 'rename'.<br>`name` (string, opt, default `null`): Location name. Required for save/go/delete/rename.<br>`new_name` (string, opt, default `null`): New name (rename action only).<br>`path` (string, opt, default `null`): Override path for the save action. Defaults to td_get_focus.active_pane_path.<br>`description` (string, opt, default `null`): Optional human-readable note (save action). | JSON envelope (string). |

---

## 6. Timeline, Lifecycle & Python Help

_Registry module: `src/td_mcp/registry/tools_runtime.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_project_lifecycle` | Save/load/undo/redo project lifecycle operations. | `action` (string, **required**): Lifecycle action: status, save, load, undo, redo, start_undo_block, end_undo_block, clear_undo<br>`path` (string, opt, default `null`): Project path for save/load. For save with no path, TouchDesigner will perform its default incremental save behavior.<br>`save_external_toxs` (boolean, opt, default `false`): Also save external tox contents on save<br>`name` (string, opt, default `null`): Undo block name when action=start_undo_block<br>`enable` (boolean, opt, default `true`): Whether a started undo block should record undo state | JSON envelope (string). |
| `td_pulse_param` | Pulse a pulse-type parameter (e.g. a button par). | `path` (string, **required**): Node path<br>`param` (string, **required**): Parameter name to pulse | JSON envelope (string). |
| `td_python_classes` | List available Python classes in the TD runtime. Returns a JSON envelope. | _(none)_ | Returns a JSON envelope. |
| `td_python_help` | Get Python help documentation for a TD class/module. | `target` (string, **required**): Python object/class to get help for (e.g. 'td', 'td.OP', 'tdu', 'td.TOP') | JSON envelope (string). |
| `td_timeline` | Read current timeline state: frame, seconds, FPS, playing. Returns a JSON envelope. | _(none)_ | Returns a JSON envelope. |
| `td_timeline_set` | Control timeline playback: play/pause, jump to frame, set FPS. | `action` (string, opt, default `null`): Timeline action: 'play', 'pause', or 'frame' (set specific frame)<br>`frame` (integer, opt, default `null`): Frame number to jump to (when action='frame')<br>`fps` (number, opt, default `null`): Set cook rate / FPS | JSON envelope (string). |

---

## 7. Events & Subscriptions

_Registry module: `src/td_mcp/registry/tools_events.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_get_events` | Read recent event history. | `event_type` (string, opt, default `null`): Optional event type filter.<br>`limit` (integer, opt, default `50`): Maximum number of events to return. | JSON envelope (string). |
| `td_subscribe` | Subscribe to runtime TD events for a node. | `path` (string, **required**): TD node path to monitor, e.g. '/project1/audio1'.<br>`event_types` (list[string], opt, default `null`): Event types: chop_change, par_change, cook_complete, node_error, timeline. Defaults to ['chop_change', 'par_change'].<br>`channels` (list[string], opt, default `null`): Specific CHOP channels to monitor. None means all channels.<br>`params` (list[string], opt, default `null`): Specific parameters to monitor. None means all tracked params.<br>`threshold` (number, opt, default `null`): Only emit events when delta exceeds this threshold.<br>`rate_limit` (number, opt, default `0.016`): Minimum seconds between repeated events from same source. | JSON envelope (string). |
| `td_unsubscribe` | Remove a node subscription. | `path` (string, **required**): TD node path to stop monitoring. | JSON envelope (string). |

---

## 8. Technique Memory & Preferences

_Registry module: `src/td_mcp/registry/tools_memory.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_memory_export` | Export the technique library as a portable JSON object for sharing or backup. | `scope` (string, opt, default `"project"`): 'project' or 'global'. | JSON envelope (string). |
| `td_memory_favorite` | Mark a technique as favorite and/or rate it (0-5). | `technique_id` (string, **required**): ID of the technique.<br>`favorite` (boolean, opt, default `true`): Set favorite status.<br>`rating` (integer, opt, default `-1`): Rating 0-5, or -1 to skip.<br>`scope` (string, opt, default `"project"`): 'project' or 'global'. | JSON envelope (string). |
| `td_memory_import` | Import techniques from an exported library (from td_memory_export). | `data` (object, **required**): Exported library data (from td_memory_export).<br>`scope` (string, opt, default `"project"`): 'project' or 'global'.<br>`overwrite` (boolean, opt, default `false`): Overwrite existing techniques with same ID. | JSON envelope (string). |
| `td_memory_learn` | Analyze a network subtree and extract a reusable technique recipe. | `path` (string, **required**): Root path of the network subtree to analyze.<br>`name` (string, opt, default `""`): Human-readable name for this technique.<br>`description` (string, opt, default `""`): What this technique does.<br>`tags` (list[string], opt, default `null`): Tags for categorization.<br>`max_depth` (integer, opt, default `3`): Max child depth to walk. | Returns the technique dict — pass it to td_memory_save to persist. |
| `td_memory_list` | List saved techniques with optional filtering by scope, tags, and favorites. | `scope` (string, opt, default `"all"`): 'project', 'global', or 'all'.<br>`tags` (list[string], opt, default `null`): Filter by tags.<br>`favorites_only` (boolean, opt, default `false`): Only return favorites.<br>`limit` (integer, opt, default `50`): Max results. | JSON envelope (string). |
| `td_memory_preferences` | Get, set, list, or delete user preferences. | `action` (string, **required**): One of: 'get', 'set', 'list', 'delete'.<br>`key` (string, opt, default `""`): Preference key (required for get/set/delete).<br>`value` (any, opt, default `null`): Value to set (required for 'set').<br>`scope` (string, opt, default `"project"`): 'project' or 'global'. | JSON envelope (string). |
| `td_memory_promote` | Copy a project technique to the global library so it's available across all projects. | `technique_id` (string, **required**): Project technique ID to promote. | JSON envelope (string). |
| `td_memory_recall` | Search the technique library by text query and/or tags. | `query` (string, opt, default `""`): Text search across names, descriptions, tags.<br>`tags` (list[string], opt, default `null`): Filter by tags.<br>`scope` (string, opt, default `"all"`): 'project', 'global', or 'all'.<br>`limit` (integer, opt, default `20`): Max results. | Returns summaries (not full recipes). Use td_memory_replay to rebuild a found technique. |
| `td_memory_replay` | Rebuild a saved technique in a new location in the TD project. | `technique_id` (string, **required**): ID of the saved technique to replay.<br>`parent_path` (string, **required**): Parent COMP path where the technique will be rebuilt.<br>`name_prefix` (string, opt, default `""`): Optional prefix for created node names.<br>`scope` (string, opt, default `"project"`): 'project' or 'global'.<br>`force` (boolean, opt, default `false`): Skip build compatibility checks and replay anyway.<br>`recreate_root` (boolean, opt, default `false`): v1.4.7 Bug V opt-in. If True and the recipe's '/' entry has family='COMP', the replay creates that wrapper COMP under parent_path first and builds all children inside it. Default False preserves the existing flat-replay behavior where '/' is aliased to parent_path (children land as siblings). Set to True when you want a faithful clone of a COMP-wrapped technique.<br>`param_semantics_policy` (enum: `warn`, `block`, opt, default `"warn"`): Docs-grounded parameter safety policy for replayed recipe params. 'warn' preserves replay behavior with attached findings; 'block' refuses risky or invalid parameter writes before any live mutation. | JSON envelope (string). |
| `td_memory_save` | Save a technique to the project or global library. | `technique` (object, **required**): Technique dict (from td_memory_learn output).<br>`scope` (string, opt, default `"project"`): 'project' or 'global'.<br>`name` (string, opt, default `""`): Override technique name.<br>`description` (string, opt, default `""`): Override description.<br>`tags` (list[string], opt, default `null`): Additional tags.<br>`notes` (string, opt, default `""`): Freeform notes about this technique. | JSON envelope (string). |

---

## 9. User Knowledge Store

_Registry module: `src/td_mcp/registry/tools_knowledge_store.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_knowledge_get` | Fetch the full markdown body + metadata for one entry. | `entry_id` (string, **required**): Entry id from td_knowledge_recall.<br>`scope` (string, opt, default `"project"`): 'project' or 'global'. | JSON envelope (string). |
| `td_knowledge_list` | List knowledge entry summaries, newest first. | `scope` (string, opt, default `"all"`): 'project' \| 'global' \| 'all'.<br>`tags` (list[string], opt, default `null`): Filter to entries with at least one of these tags.<br>`favorites_only` (boolean, opt, default `false`): If true, return only favorited entries.<br>`limit` (integer, opt, default `50`): Max results. | JSON envelope (string). |
| `td_knowledge_recall` | Search knowledge entries. Returns summaries (no full bodies). | `query` (string, opt, default `""`): Free-text search across name/description/tags/notes.<br>`tags` (list[string], opt, default `null`): Filter to entries that have at least one of these tags.<br>`scope` (string, opt, default `"all"`): 'project' \| 'global' \| 'all' (default).<br>`limit` (integer, opt, default `20`): Max results.<br>`full_text` (boolean, opt, default `false`): If true, also search the body of each entry (slower — reads files). Default false searches only metadata. | Returns summaries (no full bodies). |
| `td_knowledge_save` | Persist a free-form markdown knowledge entry. | `body` (string, **required**): Markdown body of the knowledge entry. Reference essay, math, explanations — keep under 200 KB. Split larger writeups into multiple linked entries.<br>`name` (string, opt, default `""`): Short title for the entry.<br>`description` (string, opt, default `""`): One-line summary used in search results.<br>`tags` (list[string], opt, default `null`): Lowercase tags for filtering, e.g. ['feedback', 'reaction-diffusion'].<br>`source` (string, opt, default `""`): Optional attribution — where this technique came from (e.g. 'youtube tutorial 2025-03-01', 'forum post').<br>`notes` (string, opt, default `""`): Free-form internal notes.<br>`scope` (string, opt, default `"project"`): 'project' or 'global'. Project requires TDPILOT_PROJECT_NAME. | Returns the entry id. The body is stored at |

---

## 10. Safety & Stability

_Registry module: `src/td_mcp/registry/tools_safety.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_clear_param_bounds` | Clear parameter bounds for specific paths, or all bounds if paths is None. | `paths` (list[string], opt, default `null`): Clear bounds for specific node paths (None = clear all). | JSON envelope (string). |
| `td_detect_instability` | Detect instability signals: FPS, heavy cookers, critical errors. | `path` (string, opt, default `"/project1"`): Root path to inspect. | JSON envelope (string). |
| `td_emergency_stabilize` | Emergency stabilization: pause timeline, clamp safety, capture baseline snapshot. | `path` (string, opt, default `"/project1"`): Root path to stabilize. | JSON envelope (string). |
| `td_set_param_bounds` | Set parameter safety bounds with enforcement mode. | `bounds` (list[object], **required**): One or more parameter safety bounds. Each bound has path, param, and optional min_val / max_val / max_rate.<br>`enforce_mode` (string, opt, default `"clamp"`): Enforcement mode: clamp \| reject \| warn | JSON envelope (string). |

---

## 11. Snapshots

_Registry module: `src/td_mcp/registry/tools_snapshots.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_diff_snapshots` | Diff two snapshots, or a snapshot against live state. | `snapshot_a` (string, **required**): Baseline snapshot id.<br>`snapshot_b` (string, opt, default `null`): If omitted, diff snapshot_a vs live state. | JSON envelope (string). |
| `td_list_snapshots` | List saved scene snapshots (newest first). | `limit` (integer, opt, default `20`): Max number of snapshots to return (newest first). | JSON envelope (string). |
| `td_restore_snapshot` | Restore parameter values from a previously saved snapshot. | `snapshot_id` (string, **required**): Snapshot id to restore parameter values from.<br>`partial` (list[string], opt, default `null`): Optional subset of node paths. When provided, only these nodes (and no others) have their parameters restored from the snapshot.<br>`dry_run` (boolean, opt, default `false`): Return diff only without applying.<br>`param_semantics_policy` (enum: `warn`, `block`, opt, default `"warn"`): Docs-grounded parameter safety policy for restored snapshot params. 'warn' preserves restore behavior with attached findings; 'block' refuses unsafe parameter restores before any live mutation. | JSON envelope (string). |
| `td_snapshot_scene` | Capture a scene snapshot (structure + params; optionally visual). | `name` (string, opt, default `null`): Optional snapshot label.<br>`path` (string, opt, default `"/project1"`): Root path to snapshot.<br>`include_visual` (boolean, opt, default `false`): Include screenshot payload. | JSON envelope (string). |

---

## 12. Macros

_Registry module: `src/td_mcp/registry/tools_macros.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_create_macro` | Create a macro template network. | `macro_type` (enum: `feedback_loop`, `feedback_displacement`, `audio_reactive`, `particle_gpu`, `post_processing`, **required**): Macro template to create.<br>`parent_path` (string, opt, default `"/project1"`): Parent COMP path where the macro will be instantiated.<br>`name` (string, opt, default `null`): Optional name prefix for all nodes created by this macro.<br>`nodeX` (integer, opt, default `0`): Macro origin X position in the network editor.<br>`nodeY` (integer, opt, default `0`): Macro origin Y position in the network editor.<br>`params` (object, opt, default `null`): Override template parameter defaults with custom values.<br>`param_semantics_policy` (enum: `warn`, `block`, opt, default `"warn"`): Docs-grounded parameter safety policy for macro parameter writes. 'warn' preserves macro creation with attached warnings; 'block' refuses invalid or high-risk macro param writes before setting them. | JSON envelope (string). |
| `td_get_macro_params` | Inspect parameter schema for a macro template. | `macro_type` (enum: `feedback_loop`, `feedback_displacement`, `audio_reactive`, `particle_gpu`, `post_processing`, **required**): Macro template to inspect. | JSON envelope (string). |
| `td_list_macros` | List all available macro templates (built-in plus user templates). Returns a JSON envelope. | _(none)_ | Returns a JSON envelope. |

---

## 13. Planning & Project Audit

_Registry module: `src/td_mcp/registry/tools_planning.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_audit_project` | Read-only project audit. Pair with td_brain_plan for new build/debug requests that need plan-aware changes afterward. | `root_path` (string, opt, default `"/project1"`): Root path to audit | JSON envelope (string). |
| `td_plan_patch` | Legacy compatibility planner returning the pre-v1.5 patch dict shape. For new concept-to-network TouchDesigner work, prefer td_brain_plan followed by td_brain_execute. | `intent` (string, **required**): What you want to achieve<br>`target_path` (string, opt, default `"/project1"`): Target path to plan changes for<br>`recipe_id` (string, opt, default `null`): Optional recipe ID to base plan on<br>`include_hints` (boolean, opt, default `false`): If True, attach a ``hints`` block via td_get_hints. Auto-injection still fires when the plan touches feedback, GLSL, or audio-reactive territory. | JSON envelope (string). |
| `td_preflight_patch` | Read-only validation for legacy td_plan_patch dicts. For new TDPilot-authored builds, use the BrainPlan path: td_brain_plan then td_brain_execute. | `plan` (object, **required**): Plan dict from td_plan_patch to validate | JSON envelope (string). |
| `td_validate_recipe` | Read-only recipe compatibility check. Use td_brain_plan for new grounded visual-programming requests that should become a BrainPlan. | `recipe_id` (string, opt, default `null`): Recipe ID to validate<br>`recipe` (object, opt, default `null`): Inline recipe dict to validate<br>`scope` (string, opt, default `"project"`): 'project' or 'global' | JSON envelope (string). |

---

## 14. Patch Pipeline

_Registry module: `src/td_mcp/registry/tools_patch.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_patch_apply` | Destructive compatibility/expert PatchPlan executor. Prefer td_brain_execute for BrainPlans because it is the default validated transaction path for TDPilot-authored builds. | `plan` (object, **required**): PatchPlan dict to execute<br>`label` (string, opt, default `null`): Override plan.undo_label<br>`auto_validate` (boolean, opt, default `true`): Run validate_target after apply<br>`transaction_options` (object, opt, default `null`): Optional TransactionOptions dict. When provided, td_patch_apply uses the vNext transaction executor with preflight, snapshot, validation, and rollback policy.<br>`param_semantics_policy` (enum: `warn`, `block`, opt, default `"warn"`): Docs-grounded parameter safety policy for legacy patch applies. 'warn' preserves legacy behavior and attaches findings; 'block' refuses invalid or high-risk set_params operations before mutation. | JSON envelope (string). |
| `td_patch_plan` | Compatibility/expert surface for typed PatchPlan construction. For new concept-to-network TouchDesigner builds, prefer td_brain_plan followed by td_brain_execute. | `target_root` (string, **required**): Absolute TD path the plan operates on, e.g. '/project1'<br>`intent` (string, opt, default `null`): Free-text goal; triggers heuristic macro match<br>`recipe_id` (string, opt, default `null`): Technique/recipe ID to materialize into a plan<br>`operations` (list[object], opt, default `null`): Pre-built operation list (LLM-authored)<br>`undo_label` (string, opt, default `null`): Override for the TD undo block label | JSON envelope (string). |
| `td_patch_preview` | Read-only PatchPlan preview for compatibility/expert workflows. For new visual builds, prefer td_brain_plan because it carries concept, corpus, and validation context. | `plan` (object, **required**): PatchPlan dict (from td_patch_plan)<br>`include_hints` (boolean, opt, default `false`): If True, attach a ``hints`` block via td_get_hints. Auto-injection still fires when the plan touches feedback, GLSL, or audio-reactive territory. | JSON envelope (string). |
| `td_patch_validate` | Read-only validation for patch compatibility workflows. BrainPlan workflows should use td_brain_plan and td_brain_execute so validation is tied to the authored plan. | `target_root` (string, **required**): Subtree to validate<br>`capture_frames` (list[string], opt, default `null`): TOP paths to capture; None = none (cheap) | JSON envelope (string). |
| `td_patch_variations` | Generate PatchPlan variants for compatibility/expert workflows. For new creative builds, start with td_brain_plan so variants remain grounded in a BrainPlan. | `plan` (object, **required**): Base PatchPlan dict to derive variants from<br>`n` (integer, opt, default `3`): Number of variants<br>`strategies` (list[string], opt, default `null`): None defaults to ['param_jitter']<br>`seed` (integer, opt, default `null`): RNG seed; None = random | JSON envelope (string). |

---

## 15. Vision & Frame Analysis

_Registry module: `src/td_mcp/registry/tools_vision.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_analyze_frame` | Analyze pixel data of a TOP node without transferring full image data. | `path` (string, **required**): Path to a TOP node to analyze<br>`modes` (list[string], opt, default `null`): Analysis modes: histogram, luminance, alpha_coverage, color_dominant, roi_diff. Defaults to ['histogram', 'luminance'] when omitted.<br>`roi` (list[integer], opt, default `null`): Region of interest [x, y, w, h] for roi_diff mode<br>`reference_path` (string, opt, default `null`): Reference TOP path for roi_diff mode<br>`sample_grid` (integer, opt, default `20`): Grid size used by TD-side sample() fallback and normalized quality metrics.<br>`thresholds` (object, opt, default `null`): Optional visual-quality threshold overrides.<br>`quality_mode` (boolean, opt, default `true`): If True, include normalized visual-quality metrics in the TD response. | JSON envelope (string). |
| `td_capture_frame` | Capture a single frame from a TOP node and return metadata. | `path` (string, **required**): Path to a TOP node to capture<br>`quality` (number, opt, default `0.8`): JPEG quality 0.0-1.0<br>`confirm` (boolean, opt, default `false`): If True, include base64 image in response<br>`save_path` (string, opt, default `null`): Optional disk destination. When set, TouchDesigner writes the frame to this path and the tool returns metadata + the saved path with NO base64 payload (overrides confirm). Accepts an absolute path under your home directory or a bare filename (saved under ~/.tdpilot/captures/). Extension must be .png/.jpg/.jpeg. | Returns resolution, format, and byte size. If save_path is set the frame |

---

## 16. Visual Monitoring & Streaming

_Registry module: `src/td_mcp/registry/tools_streaming.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_capture_and_analyze` | Screenshot capture with optional AI analysis. | `path` (string, **required**): Path to TOP node to capture.<br>`quality` (number, opt, default `0.5`): JPEG quality 0.0-1.0.<br>`confirm_image_capture` (boolean, opt, default `false`): Must be true to execute the capture. This is an explicit acknowledgement that image payloads can consume tokens.<br>`analyze` (boolean, opt, default `false`): Request AI analysis if sampling is supported.<br>`analysis_prompt` (string, opt, default `null`): Custom analysis prompt.<br>`compare_with` (string, opt, default `null`): Optional resource URI to compare against. | JSON envelope (string). |
| `td_monitor_visual` | Start periodic monitor for a TOP. | `path` (string, **required**): TOP path to monitor.<br>`interval` (number, opt, default `2.0`): Capture interval seconds.<br>`quality` (number, opt, default `0.3`): JPEG quality.<br>`include_image` (boolean, opt, default `false`): When false (default), monitor events omit base64 image data to reduce token usage. Set true only when you explicitly want frame payloads in context.<br>`confirm_high_token_mode` (boolean, opt, default `false`): Must be true when include_image=true. This is an explicit acknowledgement that continuous image payloads can consume many tokens.<br>`auto_analyze` (boolean, opt, default `false`): Auto analyze each capture if sampling available.<br>`analysis_prompt` (string, opt, default `null`): Optional analysis prompt. | JSON envelope (string). |
| `td_stop_monitor_visual` | Stop a running visual monitor. | `path` (string, **required**): TOP path being monitored. | JSON envelope (string). |
| `td_stop_stream_top` | Stop a running TOP stream. | `path` (string, **required**): TOP path being streamed. | JSON envelope (string). |
| `td_stream_top` | Start continuous TOP stream. | `path` (string, **required**): TOP path to stream continuously.<br>`fps` (number, opt, default `8.0`): Target stream frame rate.<br>`quality` (number, opt, default `0.25`): JPEG quality for stream frames.<br>`include_image` (boolean, opt, default `false`): When false (default), streamed resource updates omit base64 image data to reduce token usage. Set true only when you explicitly want frame payloads in context.<br>`confirm_high_token_mode` (boolean, opt, default `false`): Must be true when include_image=true. This is an explicit acknowledgement that continuous image payloads can consume many tokens.<br>`emit_unchanged` (boolean, opt, default `false`): When false, identical consecutive frames are suppressed. | JSON envelope (string). |

---

## 17. Visual Optimization & Dynamics

_Registry module: `src/td_mcp/registry/tools_optimizer.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_describe_dynamics` | Asynchronous temporal dynamics observation (frame, cooking, events). | `path` (string, opt, default `"/project1"`): Root path to observe.<br>`observation_window` (number, opt, default `3.0`): Observation duration in seconds.<br>`sample_rate` (number, opt, default `10.0`): Samples per second while observing. | JSON envelope (string). |
| `td_optimize_visual` | Autonomous visual goal optimization via bounded parameter search. | `goal` (string, **required**): Natural-language optimization goal.<br>`output_top` (string, **required**): TOP path used as output reference.<br>`adjustable_params` (list[object], **required**): Parameter search space. Each entry specifies path/param/min_val/max_val/step for a parameter the optimizer may adjust.<br>`profile` (string, opt, default `null`): Optional optimizer profile: balanced \| complexity \| motion_rhythm \| stability_guard<br>`objective_weights` (object, opt, default `null`): Optional explicit objective weights, e.g. {'motion_rhythm': 0.8, 'stability': 0.4}.<br>`max_iterations` (integer, opt, default `10`): Max iterations.<br>`convergence_threshold` (number, opt, default `0.8`): Convergence threshold.<br>`safety_profile` (string, opt, default `"balanced"`): Optimizer safety profile: conservative \| balanced \| aggressive<br>`param_semantics_policy` (enum: `warn`, `block`, opt, default `"warn"`): Docs-grounded parameter safety policy for optimizer writes. 'warn' preserves bounded search with attached findings; 'block' refuses invalid or high-risk writes before mutation.<br>`root_path` (string, opt, default `"/project1"`): Root scope for instability checks and snapshots.<br>`snapshot_before` (boolean, opt, default `true`): Capture snapshot before optimization loop starts. | JSON envelope (string). |

---

## 18. Official & POPx Knowledge

_Registry module: `src/td_mcp/registry/tools_knowledge.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_describe_surface` | Describe the MCP server surface: tool count, resource count, capabilities, version. | _(none)_ | JSON envelope (string). |
| `td_get_build_compatibility` | Check if an operator type is compatible with a specific build. | `op_type` (string, **required**)<br>`build` (string, opt, default `null`) | JSON envelope (string). |
| `td_get_operator_doc` | Get full documentation card for an operator type or a specific node. | `op_type` (string, opt, default `null`)<br>`node_path` (string, opt, default `null`) | JSON envelope (string). |
| `td_get_param_help` | Get help for a specific parameter: live metadata + knowledge card entry + current value. | `node_path` (string, **required**)<br>`param_name` (string, **required**) | JSON envelope (string). |
| `td_get_popx_operator` | Get full documentation for a POPx operator (e.g. 'Particle SIM', 'Shape Falloff'). | `operator_name` (string, **required**) | JSON envelope (string). |
| `td_get_release_delta` | Get release notes for a specific build (default: current). | `build` (string, opt, default `null`) | JSON envelope (string). |
| `td_lookup_palette_component` | Look up a palette component by name or search by query. | `component_name` (string, opt, default `null`)<br>`query` (string, opt, default `null`) | JSON envelope (string). |
| `td_lookup_snippets` | Search for OP Snippets by keyword and optional family. | `query` (string, **required**)<br>`family` (string, opt, default `null`) | JSON envelope (string). |
| `td_search_official_docs` | Search the knowledge corpus for operators, palette, releases, snippets, or articles. | `query` (string, **required**)<br>`card_types` (list[string], opt, default `null`)<br>`family` (string, opt, default `null`)<br>`limit` (integer, opt, default `10`) | JSON envelope (string). |
| `td_search_popx_docs` | Search POPx operator documentation — GPU particles, falloffs, simulations. | `query` (string, **required**)<br>`limit` (integer, opt, default `10`) | JSON envelope (string). |

---

## 19. Recommendations

_Registry module: `src/td_mcp/registry/tools_recommendations.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_explain_better_way` | Suggest better official alternatives for a given intent, with gotcha warnings. | `intent` (string, **required**): What you intend to do<br>`current_plan` (string, opt, default `null`): Current approach to evaluate | JSON envelope (string). |
| `td_find_official_example` | Search for official examples and snippets matching a query. | `query` (string, **required**): Search query for official examples<br>`family` (string, opt, default `null`): Filter by operator family: TOP, CHOP, SOP, etc. | JSON envelope (string). |
| `td_recommend_official_component` | Recommend official palette or built-in operator components for a given goal. | `goal` (string, **required**): What you want to achieve | JSON envelope (string). |

---

## 20. Hints

_Registry module: `src/td_mcp/registry/tools_hints.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_get_hints` | Return concise, source-cited hints for a topic, op_type, or intent. | `topic` (string, opt, default `null`): Topic name. Allowed values evolve with the shipped hint corpus; current topics are returned in every response under ``available_topics``. Examples: 'feedback', 'glsl', 'render_pipeline', 'audio_reactive', 'extensions'.<br>`op_type` (string, opt, default `null`): OP type to get type-specific hints (e.g., 'glslTOP', 'feedbackTOP', 'geometryCOMP'). Combines additively with ``topic`` when both are set.<br>`intent` (string, opt, default `null`): Free-text description of what you're about to do. Used to score ``intent_match`` clauses on individual hints (e.g. intent='set up trail decay' bumps the level.opacity hint).<br>`node_path` (string, opt, default `null`): Optional: path of node about to be modified. Reserved for future hints that compute against live node state.<br>`error_text` (string, opt, default `null`): Optional: error/warning text to match against ``error_match`` clauses. Mirrors what auto-injection does after a failed td_get_errors call.<br>`surface` (string, opt, default `null`): Optional response-surface filter (v1.6.2). Allowed values: 'create_node', 'set_params', 'exec', 'errors', 'plan', 'preview', 'query', 'inspect', 'screenshot'. Surface-restricted hints (those declaring ``when.surface``) only fire when the requested surface matches; hints without a surface clause fire from any surface. Auto-injection from each tool wrapper passes the tool's natural surface automatically; explicit callers pass it here to narrow results.<br>`max_hints` (integer, opt, default `8`): Cap on returned hints. Critical-priority hints win ties. | Return concise, source-cited hints for a topic, op_type, or intent. |

---

## 21. Component Notes

_Registry module: `src/td_mcp/registry/tools_notes.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_component_notes` | Per-COMP markdown notes — what this subnet does, why it's wired this way, gotchas, TODOs. External JSON storage by default; ``embed=True`` also writes a hidden Text DAT inside the COMP for portability. | `action` (string, **required**): One of: 'get' (fetch a single note), 'set' (write/overwrite), 'append' (append with timestamp divider), 'delete', 'index' (list every note for the project), 'summarize' (markdown digest).<br>`path` (string, opt, default `null`): COMP path (required for get/set/append/delete; optional for summarize as a subtree filter; omit for index/summarize-all).<br>`body` (string, opt, default `null`): Note body (markdown). Required for set/append.<br>`embed` (boolean, opt, default `false`): If True (set action only), also write a hidden Text DAT named `tdpilot_notes` inside the target COMP. Lets the note travel with the .tox/.toe but bloats save files; default is external-only.<br>`tags` (list[string], opt, default `null`): Optional tags for indexing/search (set/append actions). | JSON envelope (string). |

---

## 22. TD 2025 Native & System

_Registry module: `src/td_mcp/registry/tools_system.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_color_pipeline` | Inspect the color management pipeline in TouchDesigner: color space, gamma, display settings. | _(none)_ | JSON envelope (string). |
| `td_component_standardize` | Audit or fix COMP standardization: required custom parameters (Version, Help, Creator), extension, naming. | `path` (string, **required**): Path to COMP to audit<br>`fix` (boolean, opt, default `false`): If True, auto-fix issues (wrapped in undo block) | JSON envelope (string). |
| `td_logger_status` | Inspect the Python logging configuration inside TouchDesigner: log level, handlers, registered loggers. | _(none)_ | JSON envelope (string). |
| `td_python_env_status` | Inspect the Python environment inside TouchDesigner: version, installed packages, env manager status. | _(none)_ | JSON envelope (string). |
| `td_tdresources_inspect` | Inspect TDResources available in the TouchDesigner installation: fonts, icons, defaults. | `category` (string, opt, default `null`): Category: fonts, icons, defaults, or None for all | JSON envelope (string). |
| `td_threading_status` | Inspect the threading status inside TouchDesigner: active threads, cook rate. | _(none)_ | JSON envelope (string). |

---

## 23. Tool Batch

_Registry module: `src/td_mcp/registry/tools_batch.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_tool_batch` | Dispatch up to 8 tool calls in one model roundtrip. | `calls` (list[object], **required**): List of {tool: str, args: dict} dicts. Max 8 sub-calls. | Returns: |

---

## 24. Brain Planning & Transactions

_Registry module: `src/td_mcp/registry/tools_brain.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_brain_execute` | Use this when you already have a BrainPlan from td_brain_plan and need TDPilot to apply it transactionally with validation, rollback, and optional local learning. | `plan` (object, opt, default `null`): BrainPlan dict returned by td_brain_plan. Raw free text is not accepted here. Omit when passing plan_id instead.<br>`plan_id` (string, opt, default `null`): ID of the most recent td_brain_plan result. Server-side lookup — avoids echoing the full multi-KB plan back through the host context window (and the silent-corruption risk of hosts that re-serialize large tool arguments). Provide exactly one of plan or plan_id.<br>`transaction_policy` (string, opt, default `"rollback_on_failure"`): 'rollback_on_failure' (default), 'dry_run', or 'no_rollback'.<br>`learn_on_success` (boolean, opt, default `false`): Persist a compact validated task trace to td_knowledge_* memory.<br>`confirm_visual_payload` (boolean, opt, default `false`): Reserved for future image payload confirmation; currently no large images returned. | JSON envelope (string). |
| `td_brain_ground` | Use this when td_brain_plan returns blocked or unsupported, or when you want to author a creative BrainPlan draft yourself: it returns a read-only grounding pack (task features, corpus evidence, candidate operators, parameter contracts, operator availability, live state, exemplars, and the draft authoring contract) so you can write a draft for td_brain_propose. Do not use it for trivial single-node edits. | `intent` (string, **required**): Natural-language visual programming task to ground.<br>`target_root` (string, opt, default `"/project1"`): Absolute TD parent/root path the draft will build inside.<br>`preferred_domains` (list[string], opt, default `null`): Preferred TD data domains: TOP, CHOP, SOP, POP, DAT, COMP, MAT.<br>`include_live_state` (boolean, opt, default `true`): Include existing node names/types at target_root when TD is reachable. | JSON envelope (string). |
| `td_brain_plan` | Use this when the user asks TDPilot to build or debug a real TouchDesigner visual system and you need a grounded, non-mutating concept graph plus typed patch plan. | `intent` (string, **required**): Natural-language visual programming task.<br>`target_root` (string, opt, default `"/project1"`): Absolute TD parent/root path to plan inside.<br>`output_top` (string, opt, default `null`): Optional TOP path expected to show final visual output.<br>`constraints` (object, opt, default `null`): Optional hard constraints, e.g. palette, FPS, node count, or operators.<br>`preferred_domains` (list[string], opt, default `null`): Preferred TD data domains: TOP, CHOP, SOP, POP, DAT, COMP, MAT.<br>`validation_profile` (string, opt, default `"auto"`): Validation profile. 'auto' resolves to structural_visual_safe.<br>`include_memory` (boolean, opt, default `true`): Search local technique memory while grounding the plan.<br>`include_docs` (boolean, opt, default `true`): Use loaded DocsBrain/CardIndex operator knowledge while grounding the plan. | JSON envelope (string). |
| `td_brain_propose` | Use this when you have authored a draft candidate graph from a td_brain_ground grounding pack and need TDPilot to validate it into an executable BrainPlan. It is read-only and never mutates TouchDesigner: accepted drafts are compiled, gated by parameter semantics, and cached server-side so td_brain_execute(plan_id=...) can run them immediately; rejected drafts return machine-readable rejections to fix and retry. | `draft` (object, **required**): Host-authored draft candidate graph matching the td_brain_ground authoring_contract draft_schema (label, concepts, edges, required_ops, ...).<br>`target_root` (string, opt, default `"/project1"`): Absolute TD parent/root path the plan will build inside.<br>`validation_profile` (string, opt, default `"auto"`): Validation profile. 'auto' resolves to structural_visual_safe.<br>`intent` (string, opt, default `null`): Original natural-language intent behind the draft. Defaults to the draft label so the same intent used for td_brain_ground can be carried through. | JSON envelope (string). |
| `td_cockpit_render` | Use this when you already have BrainPlan or transaction data and want to render the optional local cockpit UI. This is read-only presentation; call td_brain_plan or td_brain_execute first for authoritative data. | `plan` (object, opt, default `null`): BrainPlan dict or td_brain_plan result to summarize.<br>`transaction_result` (object, opt, default `null`): TransactionResult dict or td_brain_execute result to summarize.<br>`trace` (object, opt, default `null`): Optional BrainTrace or trace summary.<br>`title` (string, opt, default `"TDPilot Brain Cockpit"`): Human-readable cockpit title. | JSON envelope (string). |
| `td_transaction_apply` | Use this when you need to apply an existing PatchPlan or BrainPlan with preflight, snapshot, validation, dry-run, max-op, and rollback controls. | `plan` (object, **required**): PatchPlan dict or BrainPlan dict.<br>`options` (object, opt, default `null`): TransactionOptions override. Missing fields use safe defaults. | JSON envelope (string). |

---

## 25. Sync, Self-Update & Activity

_Registry module: `src/td_mcp/registry/tools_meta.py`_

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_get_activity_log` | Recent tool-call activity from this MCP server's ring buffer. | `limit` (integer, opt, default `20`): How many recent entries to return (1–200, newest first).<br>`tool_filter` (string, opt, default `null`): If set, only return entries for this exact tool name. | Returns a JSON array of entries newest-first, each with ``ts``, ``tool``, |
| `td_self_update` | Check for and optionally install a newer TDPilot release from GitHub. | `check_only` (boolean, opt, default `true`): If True (default), only check whether a newer release exists. If False, download + install the latest .plugin/.tox to all three install paths (~/.tdpilot, plugin cache, repo). | returns ``{installed, latest, newer_available, release_url, asset_urls}``. |
| `td_sync_diagnose` | Strict version/auth sync diagnostic without exposing secret material. | `include_live` (boolean, opt, default `true`): If true, probe the live TouchDesigner WebServer.<br>`check_remote` (boolean, opt, default `false`): Reserved for compatibility; remote checks are not required. | JSON envelope (string). |
| `td_sync_status` | Report whether the local server, TD component, packages, and public surfaces are in sync. | `check_remote` (boolean, opt, default `true`): If true, also check GitHub release, npm latest, and GitHub repository description. | JSON envelope (string). |

<!-- END GENERATED: tool-reference -->

---

## Response envelope: `_read_journal` *(new in v1.6.16)*

Every successful tool response routed through the MCP dispatcher carries an
extra top-level field on its JSON envelope:

```json
{
  "...tool-specific fields...": "...",
  "_read_journal": {
    "call_count": 3,
    "first_seen_at": "2026-05-18T18:30:00Z",
    "last_seen_at":  "2026-05-18T18:32:01Z",
    "result_unchanged": true
  }
}
```

* `call_count` — how many times this session has dispatched the same tool with the same arguments.
* `result_unchanged` — `null` on the first call; `true` when the repeated result hash matches the previous one; `false` when it differs.
* The journal is **advisory only** — every call still executes against TD. The hint exists so AI agents can decide whether to re-fetch across MCP request boundaries without paying token cost on stable data.
* Bounded to 500 distinct `(tool_name, args_fingerprint)` keys; oldest-by-`last_seen_at` evicted under pressure.
* **Not** attached on error responses (4xx / `success: false` envelopes) — error responses have no meaningful "result hash" to dedupe.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TD_MCP_HOST` | `127.0.0.1` | TouchDesigner HTTP API host |
| `TD_MCP_PORT` | `9981` | TouchDesigner HTTP API port |
| `TD_MCP_WS_PORT` | `9982` | WebSocket event listener port |
| `TD_MCP_HTTP_HOST` | `127.0.0.1` | MCP server HTTP bind host |
| `TD_MCP_HTTP_PORT` | `8765` | MCP server HTTP bind port |
| `TD_MCP_TRANSPORT` | `stdio` | Transport mode: `stdio`, `streamable-http`, `sse` |
| `TD_MCP_EXEC_MODE` | `restricted` | Python execution safety: `off`, `restricted`, `standard`, `full` |
| `TD_MCP_SHARED_SECRET` | _(empty)_ | Shared secret for TD API authentication |
| `TD_MCP_REQUIRE_AUTH` | `1` | Require the shared secret on every TD API request |
| `TD_MCP_AUTOGENERATE_SECRET` | _(unset)_ | When truthy, autogenerate a missing secret into `~/.tdpilot/.tdpilot.env` |
| `TDPILOT_ENV_FILE` | `~/.tdpilot/.tdpilot.env` | Override path of the canonical shared env/secret file |
| `TD_MCP_EVENT_BUFFER` | `1000` | Max events in history buffer |
| `TD_MCP_CAPTURE_QUALITY` | `0.3` | Default JPEG quality for captures |
| `TD_MCP_STREAM_MAX_FPS` | `15.0` | Max FPS for TOP streams |
| `TD_MCP_MAX_SNAPSHOTS` | `50` | Max snapshots retained |
| `TD_MCP_STATE_VECTOR_TTL` | `2.0` | State vector cache TTL in seconds |
| `TD_MCP_SNAPSHOT_DIR` | _(empty)_ | Persistent snapshot storage directory |
| `TD_MCP_TEMPLATE_DIR` | _(empty)_ | User macro template directory |
| `TD_MCP_AUDIT_LOG` | _(empty)_ | Audit log file path |
| `TDPILOT_PROJECT_NAME` | _(empty)_ | Project name for technique memory scoping |
| `TDPILOT_MEMORY_DIR` | _(empty)_ | Base directory for technique memory storage |

### Shared-secret resolution order

Every reader of the shared secret (the MCP server, `td_client`, the TD-side
component callbacks, and the TD-side startup scripts) resolves it in the same
canonical order:

1. Explicit process env var `TD_MCP_SHARED_SECRET` (never overwritten by files).
2. The canonical env file `~/.tdpilot/.tdpilot.env` (path overridable via `TDPILOT_ENV_FILE`).

That file is THE secret file — installers write it and client configs opt in
to autogeneration (`TD_MCP_AUTOGENERATE_SECRET=1`) instead of embedding
literal secrets. `td_sync_diagnose` fingerprints the full chain and names the
winner when debugging 401s.

---

## Exec Mode Safety Levels

| Mode | Imports | Description |
|------|---------|-------------|
| `off` | All blocked | Python execution fully disabled. |
| `restricted` | All blocked | Default. No imports, no file I/O, no network calls. Blocks dangerous builtins. |
| `standard` | Allowlist only (`json`, `math`, `re`, `datetime`, `collections`, `itertools`, `functools`, `copy`, `textwrap`, `string`, `random`, `decimal`, `fractions`, `statistics`) | Safe stdlib subset. Additional builtins like `setattr`, `delattr`, `eval`, `globals`, `locals` are blocked. |
| `full` | Unrestricted | Full Python access. Required for TD 2025 Native tools (python_env_status, threading_status, logger_status). |

---

## Response Format

Tools that accept `response_format` support two modes:

- `json` (default): Structured JSON output.
- `markdown`: Human-readable markdown output (supported by `td_get_nodes`, `td_get_node_detail`, `td_get_params`).

---

## Macro Types

| Type | Description |
|------|-------------|
| `feedback_loop` | Classic feedback loop with TOP chain |
| `feedback_displacement` | Feedback with displacement mapping |
| `audio_reactive` | Audio-reactive parameter modulation |
| `particle_gpu` | POP point-field preview: source -> noise -> Null POP -> Render Simple TOP |
| `post_processing` | Post-processing effects chain |
