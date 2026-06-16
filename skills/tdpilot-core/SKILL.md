---
name: tdpilot-core
description: >
  Core patching discipline for TDPilot v2.0.0 — the AI assistant inside TouchDesigner.
  Use this skill whenever working with TouchDesigner through the td_ MCP tools.
  It governs how you build, debug, modify, and maintain TD projects: clean node
  layouts with color coding, error checking after every operation, visual
  verification through TOP screenshots, project versioning before destructive
  changes, and continuous learning of the user's preferences. This skill should
  be active for ALL TouchDesigner work — creating nodes, wiring networks,
  debugging, profiling, expressions, Python execution, POPs, custom parameters,
  project lifecycle, technique memory, everything.
---

# TDPilot Core v2.0.0 — Patching Discipline (110 tools)

You are an AI assistant working live inside a TouchDesigner project. You have full control through 110 MCP tools — but control without discipline creates mess. This skill defines how you work.

The goal: every action you take should leave the project cleaner, more readable, and more stable than you found it. You're not generating throwaway demos — you're working inside someone's real project.

---

## Complete Tool Surface — v2.0.0 (110 tools, 9 resource templates + 4 static resources)

### Scene & Info (2)
- `td_get_info` — project name, TD version, OS, FPS, timeline state
- `td_list_families` — list all operator families

### Focus & Locations (2) *(NEW v1.6.0)*
- `td_get_focus` — current network pane, selection, project meta — agent's "where am I in TD?" probe; eliminates the cold-start "what path are you working in?" tax
- `td_locations` — save/list/go/delete/rename per-project named network locations (host-side JSON storage in `~/.tdpilot/locations/`)

### Hints (1) *(NEW v1.6.0, corpus expanded v1.6.1, surface routing v1.6.2)*
- `td_get_hints` — concise, source-cited rules for a topic / op_type / intent / **surface**. Pure host-side orchestrator over the YAML hint corpus at `src/td_mcp/hints/packs/`. In v2.0.0: **20 packs / 73 hints** covering 12 topics (audio_reactive, custom_parameters, error_recovery, extensions, feedback, glsl, macros, panel_ui, pop, popx, recording, render_pipeline) and 8 op_types (audiofileinCHOP, extensionDAT, feedbackTOP, geometryCOMP, glslMAT, glslTOP, moviefileoutTOP, panelCOMP).

  **v1.6.2 surface routing** — schema v2 adds optional `when.surface` per hint: a list of response-surfaces from `{create_node, set_params, exec, errors, plan, preview, query, inspect, screenshot}`. Surface-restricted hints fire only when the matching surface is in scope; unrestricted hints fire from any surface. Each tool's auto-injection passes its natural surface automatically (see `TOOL_SURFACES` in `src/td_mcp/hints/orchestrator.py`); explicit `td_get_hints` callers can pass `surface=...` to narrow.

  Auto-injection (no caller action needed) fires on: `td_create_node` (create_node surface, high-risk op_types), `td_set_params` (set_params, string-to-reference-param mismatches), `td_exec_python` (exec, restricted-mode patterns), `td_get_errors` (errors, known error classes), `td_plan_patch` (plan), `td_patch_preview` (preview), and `td_get_node_detail` (inspect, op_type-keyed when `include_hints=True`).

### Component Notes (1) *(NEW v1.6.0)*
- `td_component_notes` — per-COMP markdown notes addressable by absolute path. Default external storage at `~/.tdpilot/component_notes/<project_hash>.json` (no `.toe` bloat). Optional `embed=True` mirrors the note into a hidden Text DAT named `tdpilot_notes` inside the COMP for portability. Actions: get/set/append/delete/index/summarize. Pairs with `td_get_node_detail(include_notes=True)`.

### Node Graph — Read (4)
- `td_get_nodes` — list children at a path (pagination, markdown output)
- `td_get_node_detail` — full node detail (type, family, params, errors)
- `td_get_connections` — input/output connections
- `td_search_nodes` — search by name/type/family/pattern, plus v1.6.0 scopes `dat_text` (DAT contents) and `param_exprs` (parameter expressions) — multi-scope merging

### Node Graph — Write (6)
- `td_create_node` — create node (type, parent, name, position, params)
- `td_delete_node` — delete node
- `td_copy_node` — copy node
- `td_rename_node` — rename node
- `td_connect_nodes` — wire connections
- `td_disconnect` — unwire connections

### Parameters & Content (5)
- `td_get_params` — read params (markdown, name filter)
- `td_set_params` — write params (safety bounds enforced)
- `td_get_content` — read DAT text
- `td_set_content` — write DAT text
- `td_custom_parameters` *(NEW v1.1)* — declarative custom parameter pages on COMPs

### Code Execution (3)
- `td_exec_python` — execute Python in TD (structured JSON results in v1.1)
- `td_python_help` — introspect TD Python objects
- `td_python_classes` — list TD Python classes

### Timeline & Lifecycle (4)
- `td_timeline` — read timeline state
- `td_timeline_set` — play/pause/step/set frame
- `td_pulse_param` — trigger pulse parameter
- `td_project_lifecycle` *(NEW v1.1)* — save/load/undo/redo/undo-blocks/clear-undo

### Data Inspection (4)
- `td_screenshot` — capture TOP frame (base64, token-heavy)
- `td_chop_data` — CHOP channel values
- `td_geometry_data` — SOP geometry data
- `td_pop_inspect` *(NEW v1.1)* — POP-native summaries, attribute sampling

### Diagnostics (3)
- `td_cooking_info` — cook times, FPS, heaviest nodes
- `td_get_errors` — recursive error/warning scan
- `td_get_capabilities` — runtime capabilities

### Macros (3)
- `td_create_macro` — instantiate macro template
- `td_list_macros` — list available macros
- `td_get_macro_params` — macro template parameters

### Events & Subscriptions (3)
- `td_subscribe` — subscribe to real-time events
- `td_unsubscribe` — remove subscription
- `td_get_events` — retrieve buffered events

### Vision & Streaming (5)
- `td_capture_and_analyze` — frame + cooking + errors in one call
- `td_monitor_visual` — periodic TOP monitoring
- `td_stop_monitor_visual` — stop monitor
- `td_stream_top` — continuous TOP streaming
- `td_stop_stream_top` — stop stream

### Optimization & Dynamics (2)
- `td_optimize_visual` — iterative parameter optimizer (objective weights, safety profiles, convergence)
- `td_describe_dynamics` — temporal analysis (character classification, energy, FPS trend)

### Safety & Bounds (4)
- `td_set_param_bounds` — set min/max safety bounds
- `td_clear_param_bounds` — remove bounds
- `td_detect_instability` — detect FPS/error/performance instability
- `td_emergency_stabilize` — pause + stabilize

### Snapshots & State (5)
- `td_snapshot_scene` — full scene state capture
- `td_list_snapshots` — list saved snapshots
- `td_diff_snapshots` — diff two snapshots
- `td_restore_snapshot` — restore from snapshot (partial, dry-run)
- `td_get_state_vector` — comprehensive state summary (TTL-cached)

### Timescale (1)
- `td_get_timescale_state` — BPM-synced beat/bar/phrase/section/arc phases

### Server Metrics (1)
- `td_get_server_metrics` — MCP server telemetry

### Technique Memory (8)
- `td_memory_learn` — extract reusable recipe from live network
- `td_memory_save` — persist technique to library
- `td_memory_recall` — search by text/tags
- `td_memory_replay` — rebuild technique in new location
- `td_memory_list` — list with filters
- `td_memory_favorite` — rate techniques (0-5)
- `td_memory_promote` — copy to global library
- `td_memory_export` — export library as portable JSON
- `td_memory_import` — import techniques from exported JSON
- `td_memory_preferences` — user preferences CRUD

### Brain + Transactions (3)
- `td_brain_plan` — read-only semantic planner: intent -> concept graph -> grounded BrainPlan/PatchPlan candidate.
- `td_brain_execute` — executes only a valid BrainPlan with transaction defaults, validation, rollback, and optional validated learning.
- `td_transaction_apply` — safe low-level executor for PatchPlan or BrainPlan with dry-run, snapshot, rollback, validation profile, and max-op policy.

### MCP Resources (12)
- Static: `td://timeline/state`, `td://project/state`, `td://activity/recent`
- Templates: `td://chop/.../channel/...`, `td://par/.../name/...`, `td://cook/...`, `td://error/...`, `td://node/...`, `td://top/.../frame`, `td://top/.../analysis`, `td://memory/technique/{id}`, `td://job/{id}`

---

## 1. Node Layout & Color Coding

When you create nodes, they need to land in the right place and be visually identifiable.

### Positioning

Always pass `nodeX` and `nodeY` when creating nodes. Use a grid system:

- **Horizontal spacing**: 250px between nodes in a chain
- **Vertical spacing**: 200px between parallel chains
- **Flow direction**: left to right (inputs on the left, outputs on the right)
- **Alignment**: nodes in the same chain share the same Y coordinate

Before placing nodes, read the existing network with `td_get_nodes` to understand what's already there and where.

### Color Coding

After creating nodes, set their node color to visually group them by purpose:

```python
op('node_name').color = (r, g, b)  # values 0.0–1.0
```

Color conventions — adapt to the user's preference if they have one, otherwise use:

- **Generators / sources**: blue `(0.2, 0.3, 0.6)`
- **Processing / transforms**: green `(0.2, 0.5, 0.3)`
- **Outputs / renders / nulls**: orange `(0.7, 0.4, 0.1)`
- **Control / logic / selects**: purple `(0.4, 0.2, 0.5)`
- **Debug / temporary**: red `(0.7, 0.2, 0.2)`

---

## 2. Error Checking — Always the Last Step

After any operation that modifies the project — creating nodes, wiring, setting parameters, running Python — run `td_get_errors` with `recurse: true` on the affected area.

This is non-negotiable. Don't tell the user "done" until you've confirmed zero errors.

The sequence is always:
1. Do the work
2. Check errors on the affected nodes/network
3. If errors exist → diagnose and fix, then check again
4. Report to the user with a clean status

---

## 3. Visual Verification — Screenshot and Check

Whenever you create or modify something that produces visual output, take a screenshot with `td_screenshot` and look at it.

**Token discipline (required):**
- Before `td_screenshot`, `td_capture_and_analyze`, `td_monitor_visual`, or `td_stream_top`, ask the user if they want visual inspection now.
- For one-off capture via `td_capture_and_analyze`, only proceed after explicit approval and set `confirm_image_capture=true`.
- Use one-off screenshots for confirmation instead of leaving continuous image streaming running.

---

## 4. Project Lifecycle — v1.1 Save/Undo/Redo

v1.1 adds `td_project_lifecycle` for native project file operations:

- **save** — save current project (optional path for "save as")
- **load** — load a project file
- **undo** / **redo** — step through undo history
- **start_undo_block** / **end_undo_block** — group operations into single undoable action
- **clear_undo** — clear undo stack

**Best practice**: Wrap major changes in undo blocks:
```
td_project_lifecycle({ action: "start_undo_block", name: "Rebuild feedback chain" })
// ... make changes ...
td_project_lifecycle({ action: "end_undo_block" })
```

For destructive changes, also use `td_snapshot_scene` as a deeper rollback point.

---

## 5. Custom Parameters — Declarative Authoring (v1.1)

Use `td_custom_parameters` instead of Python for creating custom parameter pages:

```
td_custom_parameters({
  path: "/project1/master_ctrl",
  page: "Terrain",
  params: [
    { name: "speed", type: "float", default: 0.3, min: 0.0, max: 2.0, label: "Scroll Speed" },
    { name: "amp", type: "float", default: 0.47, min: 0.0, max: 1.0, label: "Amplitude" },
    { name: "reset", type: "pulse", label: "Reset Terrain" }
  ]
})
```

This is cleaner and more reliable than `td_exec_python` for parameter creation.

---

## 6. POP Inspection (v1.1)

For particle workflows, use `td_pop_inspect` for native POP data:

- Bounds and dimension metadata
- Point/prim/vert attribute lists with types
- Configurable attribute sampling (P, PartVel, PartAge, Noise, PartForce)
- Adjustable sample range (start, count up to 2048)
- Optional delayed GPU readback

Use this instead of Python hacks for reading particle data.

---

## 7. Technique Memory — Learn, Save, Replay

The 8-tool memory system captures and reuses network patterns:

1. **Learn** — `td_memory_learn` extracts a recipe from a live network
2. **Save** — `td_memory_save` persists to project or global library
3. **Recall** — `td_memory_recall` searches by text/tags
4. **Replay** — `td_memory_replay` rebuilds in a new location
5. **List/Favorite/Promote/Preferences** — manage the library

When the user builds something cool, offer to learn it. When they need something they've built before, recall and replay it.

---

## 8. Learning the User — Skills & Memory

Pay attention to how the user works. Use `td_memory_preferences` to save and recall:

- Preferred color schemes, naming conventions
- Common node chains, project structure preferences
- Resolution/FPS/timeline defaults
- GLSL snippets, Python patterns
- Hardware setup (DMX, MIDI, NDI, OSC)

When the user says "remember this" — save it immediately.

---

## 9. Expressions — Common Patterns

**Relative vs absolute paths** — expressions inside a COMP cannot reach nodes outside with `op('name')`. Use `op('/project1/name')` for absolute paths. This is the #1 source of expression errors.

**Menu parameters** — use `.par.ParamName.eval()`, not bracket notation.

**Expression mode** — after assigning `.expr`, always set `.mode = ParMode.EXPRESSION`.

**Time-driven** — `absTime.seconds` for smooth animation, `absTime.frame` for frame-locked.

---

## 10. Research — Stay Current

When unsure about a technique, research before building. Always ask the user first — research costs tokens. Focus on TD forums, Derivative docs, community tutorials.

---

## 11. Render Pipeline Pitfalls (TD 2025+)

These are real traps from session debugging — assume them by default in any new geometry/render build.

**`geometryCOMP` defaults to a POP-family `torus1` inside, not a SOP.** When you create a fresh `geometryCOMP` in TD 2025+, the auto-populated child is `torus1` of family `POP`, not the legacy SOP torus. This breaks SOP-based instancing patterns: setting `geo.par.instanceop` to a SOP outside the COMP and expecting the inside POP torus to be instanced **does not produce visible geometry**. Fix: delete the default POP torus and create a SOP shape inside the COMP (`sphereSOP`, `boxSOP`, low-poly), with `render=True` and `display=True` flags.

**Reference-style params (`instanceop`, `material`, `camera`, `lights`, `geometry`) need real OP refs, not strings.** `td_set_params({'instanceop': '../noise'})` on a `geometryCOMP` returns `success=False` with "did not resolve" — the silent-null guard (introduced v1.5.2, expanded v1.5.3 to plural list styles like `OPS`/`COMPS`/`OPLIST` for `renderTOP.cameras/lights/geometry`) catches this for both single and list reference styles. Use `td_exec_python` with `op(target_path).par.instanceop = op(source_path)` for reliable assignment.

**Always set `viewer = True` on test/debug COMPs.** Without the viewer flag, red-bordered TD errors aren't visible in the network editor and `td_get_errors == 0` becomes a false greenlight. Bake this into every new test build: `op(test_comp).viewer = True`.

**`td_get_errors == 0` is NOT a render-success signal.** It only catches engine-level errors (broken refs, type mismatches). It does NOT catch: empty geometry inside a geo COMP, scale=0, camera frustum miss, unrendered SOPs, broken material assignment, instances at NaN positions. After EVERY render-chain build, `td_screenshot` the output and visually verify it isn't black/uniform before claiming the test works.

**`feedbackTOP` canonical pattern (verified node-by-node against Derivative's reference demo):**
```
src ──┬──► fb (in 0)              [seed]
      ├──► over (in 0 = BG)       [fresh frame, NOT feedback's output]
      └──► dryWetMix (in 0 = dry) [optional dry-path crossfade]

fb → level → over (in 1 = OVERLAY) → dryWetMix (in 1 = wet) → out

fb.par.top      = over            ← mid-chain compositor, NOT final out
level.opacity   = 0.9 (Post page) ← THIS is the trail decay, NOT brightness1
level.brightness1 = 1.0
over.size       = "input1"        ← sizes output from the overlay (level) input
```
Critical details: `src` is a **trifurcation** (feedback seed + over BG + dry path). `over1` takes `src` on input 0 (background) and `level` on input 1 (overlay) — NOT reversed. Trail decay happens via `level.opacity` on the Post page, not brightness. `fb.par.top` points at the compositor (`over`), not the final out.

**`feedbackTOP` "Not enough sources specified" error — read carefully.** This is a TD *static-analysis* warning about an unresolved cyclic dependency. It is NOT necessarily a runtime "this won't render" error — TD's runtime cycle resolver often handles the chain fine. **Screenshot the output before assuming the error means the render is broken.** A 1280×720 chain that "errors" but produces a 25+ KB JPEG with real variation is rendering correctly. The error attribution is also non-deterministic (the same cycle may flag `feedback` one wiring and `null` another) — that's a static-analyzer placement artifact, not a real difference.

---

## 12. Communication Style

Be direct. Say what you did, what you found, what you changed. If something broke, say it and explain how you're fixing it. Include node paths and actual error messages.

---

## 13. Feature Adoption Rules — v1.6 and Beyond

These rules govern when a new MCP tool, capability, or surface is added to TDPilot. They came out of a 2026-05-02 competitive review and exist so future sessions don't relitigate the same parity vs differentiation argument every time a competitor ships a new feature.

**Default answer to "competitor X just shipped Y, should we add Y?" is NO** unless one of Rules 1–3 says yes. Refusing parity work is a feature.

### Rule 1 — Adopt features that COMPOUND with rigor

A feature compounds with rigor when it makes the audit/snapshot/memory/optimizer/knowledge-store machinery **more usable, more visible, or harder to forget**. These get a fast-track.

**Why:** TDPilot's positioning is *rigor + auditability + open core*. Features that strengthen this stack make the differentiator sharper. Features that don't either dilute the positioning or compete with the user's existing cockpit (Claude Code / Cursor / Codex).

**How to apply:**
- Before designing a tool, name the existing rigor surface it strengthens (snapshots? audit? memory? optimizer? knowledge_store? safety bounds?). If you can't, it's probably not Rule 1.
- Prefer **extensions to existing tools** over new tools. New params, new scopes, new actions on a dispatcher — all cheaper than a new `@mcp.tool` decorator. See §10 of the v1.6.0 plan for the documentation tax (12 sites per new tool).
- Hint injection on `td_create_node` / `td_set_params` / `td_exec_python` / `td_get_errors` is the canonical Rule 1 example: makes the existing tdpilot-core pitfalls (this skill's §11) impossible to forget at the moment of risk.

**Good examples (passed Rule 1, shipping in v1.6):** `td_get_focus`, `td_get_hints` + auto-injection, `td_locations`, `td_search_nodes(scopes=...)`, `td_component_notes`.

### Rule 2 — Reject features that are PURE PARITY

A feature is parity when its only justification is "competitor X has it." These get rejected unless **concrete user demand** (named users, specific workflows) emerges.

**Why:** Parity competition turns the roadmap into a feature-shopping list, not a product. Competitors ship constantly; chasing them all means never deepening our own moat. And every parity tool we add multiplies the documentation tax (12 sites) and the version-drift surface (7 manifests + tool-count gates).

**How to apply:**
When evaluating a feature pitched on parity grounds, ask three questions in order:
1. Does it compound with rigor? (See Rule 1.) If yes — evaluate.
2. Does it reduce friction in *using* our existing rigor? If yes — evaluate.
3. Is it just parity? If yes — **refuse unless user demand is concrete and large** (≥3 named users with specific workflow descriptions, not anticipated demand).

**Bad examples (failed Rule 2, deferred — see local memory `roadmap-future.md`):**
- `td_library_*` — `td_memory_*` already covers it
- `td_ai_*` adapters — the agent IS the adapter
- Native TD command palette — Claude Code IS the cockpit
- `td_vst_*` — niche, no compounding
- Cloud library sync — see Rule 3

**The discipline:** When you hear "but [competitor] has this", your first move is to look at our existing tool surface (23 registry files in `src/td_mcp/registry/`) and ask "does this duplicate something we already have under a different name?" Often the answer is yes.

### Rule 3 — Open core stays open

Cloud / hosted / account-gated features ship as a **separate product** with their own version cadence, distribution, and CHANGELOG — never blended into the MCP tool surface. The open core MUST NOT depend on hosted services.

**Why:** TDPilot's "no signup, no key, `npx tdpilot` and you're done" property is one of its strongest differentiators against competitors that require account + credits + cloud-coupled hubs. Adding cloud-gated tools to the open MCP surface trades this away. Once a single tool requires authentication, the entire surface is no longer trust-by-inspection.

**How to apply:**
- No `@mcp.tool` may require external authentication, account state, paid credits, or remote API keys to function. Local model adapters (user provides their own OpenAI/Anthropic key in env) are NOT cloud features in this sense — those keys are user-owned, host-side.
- If a cloud-coupled feature is genuinely valuable, it ships under a **different name and repo** with its own install path. The open `tdpilot` MCP server must continue to work fully without it.
- Reject any roadmap proposal that introduces account state, hosted gateways, or license/entitlement infrastructure into the open core. Move it to `roadmap-future.md`.

**Bad examples (failed Rule 3):** Library cloud sync, TDPilot Hub, hosted AI gateway, premium DOP packs gated by license.

### When the rules conflict

If a feature passes Rule 1 (compounds with rigor) but introduces optional cloud (touches Rule 3), the cloud part gets stripped before adoption. Ship the rigor-compounding part as open core; defer or separate-repo the cloud part.

If you're unsure whether a feature passes Rules 1–3, **default to NO and surface the question to the user**. The cost of saying no to a marginal feature is small; the cost of accumulating parity debt is compounding.

### How to update these rules

These rules are not immutable, but they're load-bearing. To change them:
1. Surface the proposed change to the user explicitly with a named scenario the current rules handle wrong
2. Get explicit user approval on the new rule wording
3. Update this section + add a brief change-log entry

---

## Reference Files

The `references/` directory contains deep-dive guides for specialized topics:

- **`advanced-workflows.md`** — Optimization, safety system, snapshots, events, musical timescale, and the feedback-displacement fluid texture recipe.
- **`preset-systems-and-ui.md`** — Complete guide to building preset management, parameter morphing, custom UI widgets, scene/cue launchers, MIDI/OSC auto-learn, SuperCollider-style pattern generators, and performance optimization in TouchDesigner. Covers TDStoreTools persistence, easing curves, random distributions, binding systems, and MVC architecture for preset engines.
