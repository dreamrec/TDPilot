# TDPilot API Reference

> TDPilot v2.0.3 | 114 tools | Hand-maintained reference — the canonical source of truth is the `@mcp.tool` registrations under `src/td_mcp/registry/`. If this document and the code disagree, the code wins.

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
10. [Technique Memory & User Knowledge Store](#10-technique-memory--user-knowledge-store)
11. [Safety & Recovery (Snapshots, Param Bounds, Instability)](#11-safety--recovery-snapshots-param-bounds-instability)
12. [Macros & Planning](#12-macros--planning)
13. [Vision & Streaming](#13-vision--streaming)
14. [Official Knowledge (Docs, Snippets, Palette, Release)](#14-official-knowledge-docs-snippets-palette-release)
15. [TD 2025 Native (Python Env, Threading, Logger, TDResources, COMP Audit, Color Pipeline)](#15-td-2025-native-python-env-threading-logger-tdresources-comp-audit-color-pipeline)
16. [Server Introspection](#16-server-introspection)
17. [Brain Planning, Transactions, And Cockpit](#17-brain-planning-transactions-and-cockpit)

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

## 10. Technique Memory & User Knowledge Store

Two parallel persistence surfaces — **technique memory** for replayable network recipes, **user knowledge store** *(new in v1.5.3)* for free-form markdown reference essays (prose + math).

### 10a. Technique memory (replayable network recipes)

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

### 10b. User knowledge store (markdown reference essays) — new in v1.5.3

For prose-with-math reference content (BZ reaction equations, feedback recipes, "why this approach works" essays). Storage at `~/.tdpilot/knowledge/{global,projects/<safe_name>}/entries/<uuid>.md` with metadata in adjacent `index.json`. Body capped at 200 KB per entry — split larger writeups into linked entries.

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_knowledge_save` | Persist a free-form markdown knowledge entry. Body stored at `entries/<id>.md`, metadata in `index.json`. Local-only, never pushed. | `body` (str, **required**, min 1 char, max 200 KB UTF-8): Markdown body. `name` (str, opt): Short title. `description` (str, opt): One-line summary used in search results. `tags` (list[str], opt): Lowercase, e.g. `['feedback', 'reaction-diffusion']`. `source` (str, opt): Attribution (e.g. "youtube tutorial", "blog post"). `notes` (str, opt). `scope` (str, opt, default `"project"`): `project` or `global`. Project requires `TDPILOT_PROJECT_NAME`. | JSON with `success`, `id`, `scope`, `stats`. |
| `td_knowledge_recall` | Search knowledge entries by query and/or tags. Returns summaries (no bodies — use `td_knowledge_get` to fetch a body). | `query` (str, opt): Free-text across name/description/tags/source/notes. `tags` (list[str], opt): At-least-one-match. `scope` (str, opt, default `"all"`): `project`, `global`, or `all`. `limit` (int, opt, default `20`, 1-100). `full_text` (bool, opt, default `false`): If true, also reads each body file (slower but more thorough). | JSON with `success`, `count`, `results` array of summaries. |
| `td_knowledge_get` | Fetch the full markdown body + metadata for one entry. | `entry_id` (str, **required**, min 1 char): Entry id from `td_knowledge_recall`. `scope` (str, opt, default `"project"`): `project` or `global`. | JSON with `success`, `entry` (full record + `body` field). Returns `success=False` with error if not found. |
| `td_knowledge_list` | List entry summaries newest-first with optional filtering. | `scope` (str, opt, default `"all"`): `project`, `global`, or `all`. `tags` (list[str], opt): At-least-one-match filter. `favorites_only` (bool, opt, default `false`). `limit` (int, opt, default `50`, 1-200). | JSON with `success`, `count`, `results` array, `stats` dict. |

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
| `td_tool_batch` | Dispatch up to 8 tool calls in a single model roundtrip. Sequential execution; per-call failures don't abort siblings. Backport from deepseek-v4. | `calls` (list[dict], **required**, max 8): Each entry is `{tool: str, args: dict}`. | JSON with `ok: true`, `count` (int), `results` array of `{tool, ok, result, error, elapsed_ms}`. |
| `td_get_activity_log` *(new in v1.6.16)* | Return recent tool-call activity from a 200-entry server-side ring buffer (mirrored to in-TD Table DAT `/local/mcp_server/activity_log`). | `limit` (int, default 20, 1-200), `tool_filter` (str, optional, exact tool name match). | JSON with `schema_version`, `count`, `max_buffer`, `entries[]` (newest first; each entry has `ts`, `tool`, `args_summary`, `result_summary`, `duration_ms`, `ok`). |
| `td_self_update` *(new in v1.6.16)* | Check (and optionally install) the latest TDPilot release from GitHub. Pure-stdlib so it also runs from TD Textport via `python -m td_mcp.self_updater`. | `check_only` (bool, default `True`). When `False`, downloads the asset and writes it to the three install paths (repo working-tree, Claude Code plugin cache, `~/.tdpilot/`). | JSON with `installed`, `latest`, `newer_available`, `release_url`, `follow_up` (re-run-setup_mcp_in_td.py reminder). When `check_only=False` and an update happened: `installed_to[]`, `md5{path: hash}`, `bytes_written`. |
| `td_sync_status` *(new in v2.0.3)* | Report whether the server, live TD component, `.tox`, plugin caches, npm/GitHub releases, and public GitHub description are in sync. | `check_remote` (bool, default `True`): include GitHub/npm/repository checks. | JSON with `server`, `touchdesigner`, `tox`, `plugin_caches`, `remote`, `github_repo`, `overall`, and actionable `recommendations[]`. |
| `td_sync_diagnose` *(new in v2.0.3)* | Diagnose local/live version, endpoint, package, plugin-cache, and shared-secret fingerprint drift without exposing secret values. | `include_live` (bool, default `True`): query the running TD endpoint when available; `check_remote` (bool, default `False`): include remote version checks. | JSON with `local`, `installed_package`, `plugin_caches`, `running_mcp`, `touchdesigner`, `auth`, `overall`, and actionable `recommendations[]`. |

### Response envelope: `_read_journal` *(new in v1.6.16)*

Every successful tool response routed through the MCP dispatcher now carries an
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

## 17. Brain Planning, Transactions, And Cockpit

| Tool | Description | Parameters | Returns |
|------|-------------|------------|---------|
| `td_brain_plan` *(new in v2.0.0)* | Read-only planner for non-trivial TouchDesigner visual programming tasks. Produces a grounded `BrainPlan` with concept graph, typed patch plan, risks, missing facts, blocked questions, and validation profile. | `intent` (str, required), `target_root` (str, default `/project1`), `output_top` (str, optional), `constraints` (object, optional), `preferred_domains` (array, optional), `validation_profile` (str, default `auto`), `include_memory` (bool, default `true`), `include_docs` (bool, default `true`). | Structured JSON with `success` and `plan`. Blocked plans include `blocked_questions` and must not be executed. |
| `td_brain_ground` *(new)* | Read-only grounding pack for the host-authored draft loop. Compiles the intent into task features, gathers cited corpus evidence, up to 12 candidate operator cards (op_type, family, summary, key params, gotchas), the known parameter contracts for those operators, live operator availability, existing nodes at the target root, 1-2 pattern exemplars, and the draft `authoring_contract` accepted by `td_brain_propose`. Use it when `td_brain_plan` returns blocked/unsupported or when you want to author a creative plan yourself; skip it for trivial single-node edits. | `intent` (str, required), `target_root` (str, default `/project1`), `preferred_domains` (array, optional), `include_live_state` (bool, default `true`). | Structured JSON with `success` and `grounding_pack` (`task_features`, `corpus_evidence`, `candidate_operators`, `param_semantics`, `operator_availability`, `live_state`, `exemplars`, `authoring_contract`). Degrades gracefully when TD is unreachable (`operator_availability`/`live_state` report `available: false` with a reason). |
| `td_brain_propose` *(new)* | Read-only validation of a host-authored draft candidate graph — it never mutates TouchDesigner. Runs the deterministic review gate (schema, official docs, operator availability, parameter-semantics strip), compiles accepted drafts into a full `BrainPlan`, and caches it server-side so `td_brain_execute(plan_id=...)` works immediately. Param values without a known semantics contract are STRIPPED (not rejected) and surfaced in `plan_summary.stripped_params`. | `draft` (object, required — see the td_brain_ground `authoring_contract`), `target_root` (str, default `/project1`), `validation_profile` (str, default `auto`), `intent` (str, optional — defaults to the draft label). | On acceptance: `success: true`, `plan_id`, compact `plan_summary` (profile, operators, operation_count, review_status/score, `stripped_params`), and the full `plan`. On rejection: `success: false` with machine-readable `rejections` (code/subject/message/fix) plus the reviewer `review` payload to iterate on. |
| `td_brain_execute` *(new in v2.0.0)* | Executes any schema-valid `BrainPlan` — typically authored by `td_brain_plan`, but a host agent may also submit a plan it authored itself — using transaction defaults, validation, rollback, trace export, and optional validated learning. Blocked plans (non-empty `blocked_questions`) are refused. | `plan` (object, required), `transaction_policy` (`rollback_on_failure`, `dry_run`, or `no_rollback`, default `rollback_on_failure`), `learn_on_success` (bool, default `false`), `confirm_visual_payload` (bool, default `false`). | Structured JSON with transaction `result`, `trace`, `trace_export_path`, and optional `learned_memory_id`. |
| `td_transaction_apply` *(new in v2.0.0)* | Safe executor for an existing `PatchPlan` or `BrainPlan` with preflight, snapshot, dry-run, max-op, dependency ordering, validation, and rollback options. | `plan` (object, required), `options` (`TransactionOptions`, optional). | Structured JSON with transaction status, validation report, rollback state, snapshot ids, failed op, and manual recovery flag when needed. |
| `td_cockpit_render` *(new in v2.0.0)* | Read-only MCP Apps payload for the optional TDPilot Brain Cockpit. It renders plan, transaction, validation, rollback, and trace summaries without becoming authoritative state. | `plan` (object, optional), `transaction_result` (object, optional), `trace` (object, optional), `title` (str, default `TDPilot Brain Cockpit`). | Structured JSON with `cockpit` payload and `ui://tdpilot/cockpit.html` output template metadata. |

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
| `particle_gpu` | POP point-field preview: source -> noise -> Null POP -> Render Simple TOP |
| `post_processing` | Post-processing effects chain |
