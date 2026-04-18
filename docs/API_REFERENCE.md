# TDPilot API Reference

> Auto-generated from TDPilot v1.3.4 | 92 tools | Source: `src/td_mcp/tool_registry.py`

---

## Table of Contents

1. [Scene & Info](#1-scene--info)
2. [Node Graph -- Read](#2-node-graph--read)
3. [Node Graph -- Write](#3-node-graph--write)
4. [Parameters & Content](#4-parameters--content)
5. [Data Inspection (Screenshot, CHOP, SOP, POP)](#5-data-inspection-screenshot-chop-sop-pop)
6. [Diagnostics (Cook times, Errors, Capabilities)](#6-diagnostics-cook-times-errors-capabilities)
7. [Python Execution](#7-python-execution)
8. [Timeline & Pulse](#8-timeline--pulse)
9. [Events & Monitoring](#9-events--monitoring)
10. [Technique Memory](#10-technique-memory)
11. [Safety & Recovery (Snapshots, Param Bounds, Instability)](#11-safety--recovery-snapshots-param-bounds-instability)
12. [Macros & Planning](#12-macros--planning)
13. [Vision & Streaming](#13-vision--streaming)
14. [Official Knowledge (Docs, Snippets, Palette, Release)](#14-official-knowledge-docs-snippets-palette-release)
15. [TD 2025 Native (Python Env, Threading, Logger, TDResources, COMP Audit, Color Pipeline)](#15-td-2025-native-python-env-threading-logger-tdresources-comp-audit-color-pipeline)
16. [Server Introspection](#16-server-introspection)

---

## 1. Scene & Info

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_get_info` | Get TouchDesigner project info: version, build, project name, OS. | _(none)_ | JSON with `version`, `build`, `project_name`, `os`, etc. |
| `td_list_families` | List all available operator families (TOP, CHOP, SOP, DAT, COMP, MAT, etc.). | _(none)_ | JSON array of operator family names. |

---

## 2. Node Graph -- Read

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_get_nodes` | List child nodes at a given COMP path with optional filtering. | `path` (str, opt, default `"/"`): Absolute path to a COMP node. `family` (str, opt): Filter by family (TOP, CHOP, SOP, DAT, COMP, MAT, PANEL). `type` (str, opt): Filter by operator type (e.g. `noiseTOP`). `include_params` (bool, opt, default `false`): Include all parameters per node. `limit` (int, opt, default `100`, 1-500): Max nodes. `offset` (int, opt, default `0`): Pagination offset. `response_format` (enum, opt, default `json`): `json` or `markdown`. | JSON with `nodes` array and `has_more` flag. |
| `td_get_node_detail` | Get full detail for a single node: type, family, parameters, inputs, outputs, errors. | `path` (str, **required**): Absolute node path. `response_format` (enum, opt, default `json`): `json` or `markdown`. | JSON with `name`, `path`, `type`, `family`, `parameters`, `inputs`, `outputs`, `errors`, `warnings`, `isCOMP`. |
| `td_get_connections` | Get input/output connections for a node. | `path` (str, **required**): Absolute node path. `response_format` (enum, opt, default `json`). | JSON with connection arrays. |
| `td_search_nodes` | Search nodes by name, type, family, or all. | `query` (str, **required**): Search string (case-insensitive). `path` (str, opt, default `"/"`): Root path. `search_type` (str, opt, default `"all"`): `name`, `type`, `family`, or `all`. `limit` (int, opt, default `50`, 1-200): Max results. | JSON array of matching nodes. |

---

## 3. Node Graph -- Write

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_create_node` | Create a new operator node. | `parent_path` (str, opt, default `"/project1"`): Parent COMP path. `node_type` (str, **required**): Operator type (e.g. `noiseTOP`, `waveCHOP`, `boxSOP`). Must end with a family suffix. `name` (str, opt): Custom name. `nodeX` (int, opt): Horizontal position (multiples of 200). `nodeY` (int, opt): Vertical position. | JSON with created node info (`path`, `name`, `type`). |
| `td_delete_node` | Delete a node. | `path` (str, **required**): Absolute path of node to delete. | JSON confirmation. |
| `td_copy_node` | Copy/duplicate a node. | `source_path` (str, **required**): Source node path. `dest_parent` (str, opt): Destination parent COMP. `new_name` (str, opt): Name for the copy. | JSON with new node info. |
| `td_rename_node` | Rename a node. | `path` (str, **required**): Current absolute path. `new_name` (str, **required**, max 100 chars): New name. | JSON confirmation with new path. |
| `td_connect_nodes` | Wire two nodes together. | `source_path` (str, **required**): Source (output) node. `target_path` (str, **required**): Target (input) node. `source_index` (int, opt, default `0`): Output connector index. `target_index` (int, opt, default `0`): Input connector index. | JSON confirmation. |
| `td_disconnect` | Disconnect a node connector. | `path` (str, **required**): Node path. `connector_type` (str, opt, default `"input"`): `input` or `output`. `index` (int, opt, default `0`): Connector index. | JSON confirmation. |

---

## 4. Parameters & Content

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_get_params` | Read parameters for a node. | `path` (str, **required**): Absolute node path. `page` (str, opt): Filter by parameter page. `names` (list[str], opt): Filter to specific parameter names. `response_format` (enum, opt, default `json`). | JSON dict of parameters with `value`, `default`, `label`, `page`, etc. |
| `td_set_params` | Set parameter values (static, expression, reset, or clear expression). Safety bounds enforced. | `path` (str, **required**): Absolute node path. `params` (dict, **required**): Parameter name to value mapping. Supports 5 modes: plain static (`{'seed': 42}`), expression (`{'tx': {'expr': "op('noise1')['chan1']"}}`), explicit static (`{'seed': {'val': 42}}`), reset to default (`{'seed': {'reset': true}}`), force constant (`{'seed': {'mode': 'constant', 'val': 42}}`). | JSON confirmation; may include `safety_warnings`. |
| `td_get_content` | Read DAT text/table content. | `path` (str, **required**): Path to a DAT node. | JSON with `text` or `table` content. |
| `td_set_content` | Write DAT text/table content. | `path` (str, **required**): Path to a DAT node. `text` (str, opt): Text content for Text/Script DATs. `table` (list[list[str]], opt): 2D array for Table DATs. | JSON confirmation. |
| `td_custom_parameters` | Create or update a custom parameter page on a COMP. | `path` (str, **required**): COMP path. `page` (str, **required**, max 64 chars): Page name. `params` (list[CustomParameterSpec], **required**): One or more parameter specs. Each spec has: `kind` (str, **required**: float, int, toggle, menu, str, rgb, rgba, pulse, file, filesave, folder, chop, comp, dat, mat, header), `name` (str, **required**), `label` (str, opt), `size` (int, opt, 1-4), `order` (int, opt), `replace` (bool, opt, default `true`), `menu_names` (list[str], opt), `menu_labels` (list[str], opt), `default` (any, opt), `min` (float, opt), `max` (float, opt), `norm_min` (float, opt), `norm_max` (float, opt), `clamp_min` (bool, opt), `clamp_max` (bool, opt). | JSON confirmation. |
| `td_project_lifecycle` | Save, load, undo, redo, and undo-block management. | `action` (str, **required**): `status`, `save`, `load`, `undo`, `redo`, `start_undo_block`, `end_undo_block`, `clear_undo`. `path` (str, opt): Project file path for save/load. `save_external_toxs` (bool, opt, default `false`). `name` (str, opt): Undo block name (for `start_undo_block`). `enable` (bool, opt, default `true`): Whether undo block records state. | JSON with lifecycle result. |

---

## 5. Data Inspection (Screenshot, CHOP, SOP, POP)

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_screenshot` | Capture a TOP node as a JPEG image. Base64 payload included. Ask user before repeated captures. | `path` (str, **required**): TOP node path. `quality` (float, opt, default `0.5`, 0.0-1.0): JPEG quality. | JSON with `path`, `format`, `size_bytes`, `data_base64`, resolution. |
| `td_chop_data` | Read CHOP channel sample data. | `path` (str, **required**): CHOP node path. `channels` (list[str], opt): Channel names (all if omitted). `range` (list[int], opt, len=2): Sample range [start, end]. | JSON with channel names and sample arrays. |
| `td_geometry_data` | Read SOP/POP geometry point and primitive data. | `path` (str, **required**): SOP or POP node path. `include_points` (bool, opt, default `true`). `include_prims` (bool, opt, default `false`). `limit` (int, opt, default `500`, 1-10000): Max points/prims. | JSON with point positions and primitive data. |
| `td_pop_inspect` | Read structured POP metadata: bounds, attributes, and sampled attribute values. | `path` (str, **required**): POP node path. `include_bounds` (bool, opt, default `true`). `include_attributes` (bool, opt, default `true`). `point_attributes` (list[str], opt): Specific point attributes to sample (defaults to P, PartVel, PartAge, Noise, PartForce). `prim_attributes` (list[str], opt). `vert_attributes` (list[str], opt). `start` (int, opt, default `0`): Starting element index. `count` (int, opt, default `32`, 1-2048): Max elements per attribute. `delayed` (bool, opt, default `false`): Use delayed GPU readback. | JSON with bounds, attribute metadata, and sampled values. |
| `td_capture_frame` | Capture a single TOP frame returning metadata. Base64 data only included when `confirm=true`. | `path` (str, **required**): TOP node path. `quality` (float, opt, default `0.8`, 0.0-1.0). `confirm` (bool, opt, default `false`): Include base64 image. | JSON with `resolution`, `format`, `size_bytes`, and optionally `data_base64`. |
| `td_analyze_frame` | Analyze pixel data of a TOP node server-side (no image transfer). Modes: histogram, luminance, alpha_coverage, color_dominant, roi_diff. | `path` (str, **required**): TOP node path. `modes` (list[str], opt, default `["histogram","luminance"]`): Analysis modes. `roi` (list[int], opt): Region of interest [x, y, w, h] for roi_diff. `reference_path` (str, opt): Reference TOP for roi_diff. | JSON with per-mode analysis results. |

---

## 6. Diagnostics (Cook times, Errors, Capabilities)

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_cooking_info` | Get cooking/performance data: FPS, cook times, heaviest nodes. | `path` (str, opt, default `"/"`): Root path. `recurse` (bool, opt, default `false`). `sort_by` (str, opt, default `"cookTime"`): `cookTime` or `cpuCookTime`. `limit` (int, opt, default `20`, 1-100). | JSON with `fps`, `realTime`, `nodes` array sorted by cook time. |
| `td_get_errors` | Check for node errors and warnings. | `path` (str, opt, default `"/"`): Node path. `recurse` (bool, opt, default `true`). `max_depth` (int, opt, default `10`, 1-50): Max recursion depth. | JSON with `issues` array. |
| `td_get_capabilities` | Detect MCP server and client capabilities. | _(none)_ | JSON with `client_capabilities` (sampling, roots, elicitation support) and `runtime` config (transport, exec_mode, ports, etc.). |
| `td_get_state_vector` | Aggregated scene state: project info, timeline, health, performance, events, monitoring, safety, snapshots, jobs. Cached with configurable TTL. | `path` (str, opt, default `"/project1"`): Root path. `force_refresh` (bool, opt, default `false`): Bypass cache. | JSON with `project`, `timeline`, `health`, `performance`, `events`, `monitoring`, `safety`, `snapshots`, `jobs`, `cache` sections. |
| `td_get_timescale_state` | Derive beat/bar/phrase/section/arc phase from timeline, with BPM hint. | `bpm_hint` (float, opt, default `120.0`, 0-400). `beats_per_bar` (int, opt, default `4`, 1-32). | JSON with `timeline`, `timescale` (beat_index, bar_index, phases, seconds_to_next_beat/bar/phrase, arc_stage, tempo_health, collapse_risk, plateau_risk). |
| `td_detect_instability` | Check FPS, errors, and heavy nodes to detect instability. | `path` (str, opt, default `"/project1"`): Root path. | JSON with `unstable` flag, `signals` (fps, issues_count, heavy_nodes_count), `heavy_nodes`, `issues`, `suggested_actions`. |
| `td_describe_dynamics` | Observe temporal dynamics over a time window. Runs as async job collecting samples. | `path` (str, opt, default `"/project1"`): Root path. `observation_window` (float, opt, default `3.0`, 0.5-30.0): Duration in seconds. `sample_rate` (float, opt, default `10.0`, 1.0-60.0): Samples/sec. | JSON with `job_id`, then final result contains `samples`, `classifications` (overall_character, energy_level, predictability, fps_trend). |
| `td_audit_project` | Audit a project subtree: count nodes by family/type, detect palette components, find errors, check build compatibility. | `root_path` (str, opt, default `"/project1"`). | JSON with `total_nodes`, `by_family`, `by_op_type`, `palette_components`, `unknown_op_types`, `compat_issues`, `node_errors`. |

---

## 7. Python Execution

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_exec_python` | Execute Python code inside TouchDesigner. Set `__result__` to return a value. Subject to `TD_MCP_EXEC_MODE` safety filtering (off/restricted/standard/full). | `code` (str, **required**, max 50000 chars): Python code. Has access to `op()`, `ops()`, `project`, `app`, `absTime`, `me`, `parent()`, `mod`, `ui`, `tdu`. | JSON with `result` (the `__result__` value), `output`, `error`. |
| `td_python_help` | Get Python help documentation for a TD object or class. | `target` (str, **required**): Python object (e.g. `td`, `td.OP`, `tdu`, `td.TOP`). | JSON with help text. |
| `td_python_classes` | List available Python classes in TD runtime. | _(none)_ | JSON with class names and hierarchy. |

---

## 8. Timeline & Pulse

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_timeline` | Read current timeline state: frame, seconds, FPS, playing. | _(none)_ | JSON with `frame`, `seconds`, `fps`, `playing`. |
| `td_timeline_set` | Control timeline playback. | `action` (str, opt): `play`, `pause`, or `frame`. `frame` (int, opt, >=0): Target frame (when action=`frame`). `fps` (float, opt, 0-240): Set cook rate. | JSON confirmation. |
| `td_pulse_param` | Pulse a pulse-type parameter on a node. | `path` (str, **required**): Node path. `param` (str, **required**): Parameter name. | JSON confirmation. |

---

## 9. Events & Monitoring

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_subscribe` | Subscribe to runtime events from a TD node. Provisions WebSocket listener. | `path` (str, **required**): Node path to monitor. `event_types` (list[str], opt, default `["chop_change","par_change"]`): `chop_change`, `par_change`, `cook_complete`, `node_error`, `timeline`. `channels` (list[str], opt): Specific CHOP channels. `params` (list[str], opt): Specific parameters. `threshold` (float, opt): Delta threshold for events. `rate_limit` (float, opt, default `0.016`, 0.001-10.0): Min seconds between events. | JSON with `resource_uris`, `active_subscriptions`. |
| `td_unsubscribe` | Remove all event subscriptions for a node path. | `path` (str, **required**): Node path to stop monitoring. | JSON with `active_subscriptions` count. |
| `td_get_events` | Read recent event history from the event buffer. | `event_type` (str, opt): Filter by event type. `limit` (int, opt, default `50`, 1-1000). | JSON with `events` array and `count`. |

---

## 10. Technique Memory

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_memory_learn` | Analyze a network subtree and extract a reusable technique recipe. Auto-detects complexity: small (<10 nodes) gets full recipe, large (>20) gets structure summary only. | `path` (str, **required**): Root path of subtree. `name` (str, opt): Technique name. `description` (str, opt). `tags` (list[str], opt). `max_depth` (int, opt, default `3`, 1-10). | JSON with `technique` dict containing `recipe`, `nodes`, `connections`, `key_params`, `families`, `op_types`. |
| `td_memory_save` | Persist a technique dict to the project or global library. | `technique` (dict, **required**): Technique dict (from `td_memory_learn`). `scope` (str, opt, default `"project"`): `project` or `global`. `name` (str, opt): Override name. `description` (str, opt). `tags` (list[str], opt). `notes` (str, opt). | JSON with `technique_id`, `scope`. |
| `td_memory_recall` | Search the technique library by text query and/or tags. Returns summaries, not full recipes. | `query` (str, opt): Text search. `tags` (list[str], opt). `scope` (str, opt, default `"all"`): `project`, `global`, or `all`. `limit` (int, opt, default `20`, 1-100). | JSON with `techniques` array and `count`. |
| `td_memory_replay` | Rebuild a saved technique in a new location. Creates nodes, sets params/expressions, wires connections. Auto-validates after replay. | `technique_id` (str, **required**). `parent_path` (str, **required**): Destination COMP path. `name_prefix` (str, opt). `scope` (str, opt, default `"project"`). `force` (bool, opt, default `false`): Skip compatibility checks. | JSON with `nodes_created`, `connections_wired`, `created_paths`, `skipped_nodes`, `validation_result`. |
| `td_memory_favorite` | Mark/rate a technique (0-5 stars). | `technique_id` (str, **required**). `favorite` (bool, opt, default `true`). `rating` (int, opt, default `-1`, -1 to 5): -1 to skip. `scope` (str, opt, default `"project"`). | JSON confirmation. |
| `td_memory_promote` | Copy a project technique to the global library. | `technique_id` (str, **required**): Project technique ID. | JSON with `global_technique_id`. |
| `td_memory_preferences` | Get, set, list, or delete user preferences (color palettes, default resolutions, naming conventions, etc.). | `action` (str, **required**): `get`, `set`, `list`, or `delete`. `key` (str, opt): Preference key (required for get/set/delete). `value` (any, opt): Value (required for `set`). `scope` (str, opt, default `"project"`). | JSON with preference data. |
| `td_memory_list` | List saved techniques with optional filtering. | `scope` (str, opt, default `"all"`): `project`, `global`, or `all`. `tags` (list[str], opt). `favorites_only` (bool, opt, default `false`). `limit` (int, opt, default `50`, 1-200). | JSON with `techniques` array and `count`. |

---

## 11. Safety & Recovery (Snapshots, Param Bounds, Instability)

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_set_param_bounds` | Set numeric safety bounds for parameters. All subsequent `td_set_params` calls enforce these bounds. | `bounds` (list[ParamBound], **required**, 1-500): Each bound has `path` (str), `param` (str), `min_val` (float, opt), `max_val` (float, opt), `max_rate` (float, opt, >=0: max change/sec). `enforce_mode` (str, opt, default `"clamp"`): `clamp`, `reject`, or `warn`. | JSON with `mode`, `bounds_count`, `bounds` dict. |
| `td_clear_param_bounds` | Clear safety bounds. | `paths` (list[str], opt): Clear bounds for specific node paths. If omitted, clears all. | JSON with `cleared` count and `remaining`. |
| `td_emergency_stabilize` | Emergency action: snapshot current state, pause timeline, set safety to clamp mode. | `path` (str, opt, default `"/project1"`). | JSON with `actions` taken, `snapshot` info, `next` steps. |
| `td_snapshot_scene` | Capture a full scene snapshot: all node params, connections, and optionally a visual screenshot. | `name` (str, opt): Snapshot label. `path` (str, opt, default `"/project1"`): Root path. `include_visual` (bool, opt, default `false`). | JSON with `snapshot_id`, `name`, `timestamp`, `summary` (captured_nodes, connection_count, truncated). |
| `td_list_snapshots` | List stored snapshots. | `limit` (int, opt, default `20`, 1-100). | JSON with `snapshots` array and `count`. |
| `td_diff_snapshots` | Diff two snapshots, or a snapshot vs. live state. | `snapshot_a` (str, **required**): First snapshot ID. `snapshot_b` (str, opt): Second snapshot ID. If omitted, diffs against live state. | JSON with `diff` containing added/removed/changed nodes and params. |
| `td_restore_snapshot` | Restore parameter values from a snapshot. Restores params only -- does not add/remove nodes or connections. | `snapshot_id` (str, **required**). `partial` (list[str], opt): Subset of node paths to restore. `dry_run` (bool, opt, default `false`): Preview changes without applying. | JSON with `restored`, `skipped`, `failures`, `safety_warnings`. |

---

## 12. Macros & Planning

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_create_macro` | Instantiate a built-in macro template network. | `parent_path` (str, opt, default `"/project1"`). `macro_type` (enum, **required**): `feedback_loop`, `feedback_displacement`, `audio_reactive`, `particle_gpu`, `post_processing`. `name` (str, opt): Name prefix. `nodeX` (int, opt, default `0`). `nodeY` (int, opt, default `0`). `params` (dict, opt): Override template defaults. | JSON with created node paths and connections. |
| `td_list_macros` | List all available macro templates. | _(none)_ | JSON array of macro template descriptors. |
| `td_get_macro_params` | Inspect the parameter schema for a macro template. | `macro_type` (enum, **required**): Same enum as `td_create_macro`. | JSON with parameter names, types, defaults, and descriptions. |
| `td_plan_patch` | Generate a structured patch plan for an intent without mutating the project. Inspects current state and optionally loads a recipe. | `intent` (str, **required**): What to achieve. `target_path` (str, opt, default `"/project1"`). `recipe_id` (str, opt): Base plan on a recipe. | JSON with `plan` dict containing `steps`, `current_node_count`, `existing_names`. |
| `td_preflight_patch` | Validate a plan from `td_plan_patch` before execution. Checks target path, op type validity, name conflicts. | `plan` (dict, **required**): Plan dict from `td_plan_patch`. | JSON with `valid` bool, `errors`, `warnings`, `step_count`. |
| `td_validate_recipe` | Validate a technique recipe: check op types against knowledge corpus, verify structure, report build compatibility. | `recipe_id` (str, opt): Recipe ID to validate. `recipe` (dict, opt): Inline recipe dict. `scope` (str, opt, default `"project"`). | JSON with `valid`, `node_count`, `unknown_op_types`, `compat_issues`, `errors`, `warnings`. |

---

## 13. Vision & Streaming

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_capture_and_analyze` | Capture a TOP screenshot with optional AI analysis. Requires confirmation gate. | `path` (str, **required**): TOP node path. `quality` (float, opt, default `0.5`, 0.0-1.0). `confirm_image_capture` (bool, opt, default `false`): Must be `true` to execute. `analyze` (bool, opt, default `false`): Request AI analysis. `analysis_prompt` (str, opt). `compare_with` (str, opt): Resource URI to compare against. | JSON with `capture`, `analysis`, `token_notice`. |
| `td_monitor_visual` | Start periodic visual monitoring of a TOP node. Default mode omits base64 frames. | `path` (str, **required**): TOP path. `interval` (float, opt, default `2.0`, 0.5-30.0): Capture interval seconds. `quality` (float, opt, default `0.3`, 0.0-1.0). `include_image` (bool, opt, default `false`): Include base64 frames. `confirm_high_token_mode` (bool, opt, default `false`): Required when `include_image=true`. `auto_analyze` (bool, opt, default `false`). `analysis_prompt` (str, opt). | JSON with `monitor` config, `resource_uri`, `active_monitors`, `token_notice`. |
| `td_stop_monitor_visual` | Stop a visual monitor. | `path` (str, **required**): TOP path being monitored. | JSON with `success` and `active_monitors`. |
| `td_stream_top` | Start continuous TOP frame stream. Default mode omits base64 frames. | `path` (str, **required**): TOP path. `fps` (float, opt, default `8.0`, 0.5-60.0): Target frame rate (clamped to server max). `quality` (float, opt, default `0.25`, 0.0-1.0). `include_image` (bool, opt, default `false`). `confirm_high_token_mode` (bool, opt, default `false`): Required when `include_image=true`. `emit_unchanged` (bool, opt, default `false`): Suppress identical consecutive frames. | JSON with `stream` config, `resource_uri`, `active_streams`, `limits`. |
| `td_stop_stream_top` | Stop a TOP stream. | `path` (str, **required**): TOP path being streamed. | JSON with `success`, `active_streams`, `stats`. |
| `td_optimize_visual` | Autonomous visual goal optimization via bounded parameter search. Runs as async job. Supports pre-optimization snapshot. | `goal` (str, **required**, min 3 chars): Natural-language goal. `profile` (str, opt): `balanced`, `complexity`, `motion_rhythm`, `stability_guard`. `objective_weights` (dict[str,float], opt): e.g. `{'motion_rhythm': 0.8, 'stability': 0.4}`. `output_top` (str, **required**): TOP path as output reference. `adjustable_params` (list[AdjustableParamInput], **required**, 1-200): Each has `path` (str), `param` (str), `min_val` (float), `max_val` (float), `step` (float, opt, default `0.05`). `max_iterations` (int, opt, default `10`, 1-50). `convergence_threshold` (float, opt, default `0.8`, 0.0-1.0). `safety_profile` (str, opt, default `"balanced"`): `conservative`, `balanced`, `aggressive`. `root_path` (str, opt, default `"/project1"`). `snapshot_before` (bool, opt, default `true`). | JSON with `job_id`, `job_resource_uri`, `baseline_snapshot_id`, `goal_profile`. Final job result contains `converged`, `iterations`, `final_score`, `final_params`. |

---

## 14. Official Knowledge (Docs, Snippets, Palette, Release)

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_search_official_docs` | Search the knowledge corpus for operators, palette components, releases, or snippets. | `query` (str, **required**): Search text. `card_types` (list[str], opt): Filter by card type. `family` (str, opt): Filter by operator family. `limit` (int, opt, default `10`). | JSON with `results` array, `count`, `provenance`. |
| `td_get_operator_doc` | Get full documentation card for an operator type or live node. | `op_type` (str, opt): Operator type string. `node_path` (str, opt): Resolve type from live node. | JSON with `card` (key_params, summary, common_gotchas, etc.) and `provenance`. |
| `td_get_param_help` | Get help for a specific parameter: live metadata + knowledge card entry + current value. | `node_path` (str, **required**). `param_name` (str, **required**). | JSON with `live` param info, `card_param` enrichment, `provenance`. |
| `td_lookup_snippets` | Search OP Snippets by keyword and optional family. | `query` (str, **required**). `family` (str, opt). | JSON with `results` array, `count`, `provenance`. |
| `td_lookup_palette_component` | Look up a palette component by name or search by query. | `component_name` (str, opt): Exact name. `query` (str, opt): Search text. | JSON with `card` or `results` array, `provenance`. |
| `td_get_release_delta` | Get release notes for a specific build (defaults to current). | `build` (str, opt): Build string. | JSON with release `card` and `provenance`. |
| `td_get_build_compatibility` | Check if an operator type is compatible with a specific TD build. | `op_type` (str, **required**). `build` (str, opt): Defaults to current build. | JSON with `compatible` bool, `reason`, `provenance`. |
| `td_recommend_official_component` | Recommend official palette or built-in operator components for a given goal. | `goal` (str, **required**). | JSON with `recommendations` array (type, name, summary, when_to_use). |
| `td_find_official_example` | Search for official examples and snippets matching a query. | `query` (str, **required**). `family` (str, opt): Filter by family. | JSON with `examples` array (type, id, display_name, summary). |
| `td_explain_better_way` | Suggest better official alternatives for a given intent, with gotcha warnings. | `intent` (str, **required**). `current_plan` (str, opt): Current approach to evaluate. | JSON with `recommendation`, `official_alternative`, `gotchas`. |

---

## 15. TD 2025 Native (Python Env, Threading, Logger, TDResources, COMP Audit, Color Pipeline)

All tools in this section execute Python inside TouchDesigner. Most require `full` exec mode.

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_python_env_status` | Inspect the Python environment inside TD: version, installed packages, paths. Requires `full` exec mode. | _(none)_ | JSON with `python_version`, `executable`, `paths`, `installed_packages`. |
| `td_threading_status` | Inspect threading status: active threads, cook rate. Requires `full` exec mode. | _(none)_ | JSON with `active_thread_count`, `current_thread`, `thread_names`, `cook_rate`. |
| `td_logger_status` | Inspect Python logging config: log level, handlers, registered loggers. Requires `full` exec mode. | _(none)_ | JSON with `root_level`, `handler_count`, `handlers`, `loggers`. |
| `td_tdresources_inspect` | Inspect TDResources: fonts, icons, defaults. | `category` (str, opt): `fonts`, `icons`, `defaults`, or omit for all. | JSON with `categories` dict and `total_children`. |
| `td_component_standardize` | Audit or fix COMP standardization: required custom params (Version, Help, Creator), extension, naming. Fix mode wraps in undo block. | `path` (str, **required**): COMP path. `fix` (bool, opt, default `false`): Auto-fix issues. | JSON with `issues`, `fixed`, `has_extension`, `op_type`. |
| `td_color_pipeline` | Inspect color management pipeline: color space, gamma, display settings. | _(none)_ | JSON with `defaultParameterColorSpace`, `workingColorSpace`, `editorWindowPixelFormat`, `sdrReferenceWhiteNits`, `hdrReferenceWhiteNits`, `monitorGamma` (legacy fallback). |

---

## 16. Server Introspection

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_get_server_metrics` | Get MCP server runtime metrics: telemetry, events, streams, safety, snapshots, jobs, audit status. | _(none)_ | JSON with `runtime`, `telemetry`, `events`, `visual_monitor`, `top_stream`, `safety`, `snapshots`, `jobs`, `audit_enabled`. |
| `td_describe_surface` | Describe the MCP server surface: tool count, resource count, capabilities, version. | _(none)_ | JSON with `version`, `tool_count`, `resource_count`, `capabilities`. |

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
| `particle_gpu` | GPU particle system |
| `post_processing` | Post-processing effects chain |
