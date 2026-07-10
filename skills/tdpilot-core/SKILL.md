---
name: tdpilot-core
description: >
  Core patching discipline for TDPilot v2.4.0 — the AI assistant inside
  TouchDesigner. Use for all work through the td_ MCP tools: routing intent,
  inspecting live state, making safe edits, validating results, and recalling
  or learning local techniques.
---

# TDPilot Core v2.4.0 — Practical Patching Discipline (114 tools)

TDPilot works inside a real TouchDesigner project. Leave the requested scope
more usable, readable, and stable than you found it.

## Core Rule

Route before mutating. Inspect only the state needed for that route, mutate
through a typed edit or a validated BrainPlan, and finish with evidence that
tests the user's actual request. A successful tool call is not proof that a
network is correct.

## Intent Router

Choose one route before building:

| Request shape | Route |
|---|---|
| One obvious edit at a known path | Targeted read, then the typed primitive tool |
| Exact, validated topology or supported technique | `td_brain_plan` with `detail_level="summary"` |
| Artistic, multi-domain, spatial, camera/depth/fog, or implicit architecture | `td_brain_ground` → author → `td_brain_propose` |
| Existing generated system | Read ownership metadata and rebuild only proven owned scope |
| Failed transaction or unstable network | Validator/recovery workflow |
| Production or show-critical task | Load `tdpilot-production` in addition to this skill |

Pattern-shaped means the requested topology and bindings already have a proven
compiler route. Concept-shaped means the agent must decide architecture. Do not
send a concept-shaped request through the planner merely to accept a plausible
partial match.

Every material noun, modifier, behavior, input, output, spatial requirement,
binding, and quality constraint must map to a concept/module, parameter,
connection, or validation assertion. If required intent coverage is incomplete,
the plan is not executable. Continue through grounding/proposal or clarify the
genuinely unknowable fact.

## Inspect and Ground

- Start with `td_get_focus`; inspect the target root, direct connections, and
  relevant parameters. Use `td_get_state_vector` only when broad state matters.
- Use `td_tool_batch` for independent reads that can share one roundtrip. It is
  sequential convenience, not a mutation transaction.
- Read errors before work when health is unknown, at logical batch boundaries,
  after a failure, and at final completion. Do not scan after every operation.
- Before taste-critical authoring, recall relevant local evidence with
  `td_memory_recall` and `td_knowledge_recall`, or request grounding with
  `include_memory=true`. Treat knowledge prose as advice; only validated
  techniques and promoted traces may be reused automatically.
- Use the reviewed operator atlas, official cards, availability, and parameter
  semantics before inventing unfamiliar operators or parameter names.

For concept-shaped work, bind proposal review to the returned `grounding_id`.
Use only the current `authoring_contract`; examples are skeletons, never a
substitute for live grounding. Fix machine-readable proposal rejections and
re-propose. Do not execute a rejected, incomplete, stale, or semantically
unresolved plan.

## Mutation Discipline

### Valid BrainPlan route

1. Inspect the plan summary, route, coverage, risks, output, and validation
   contract.
2. Require complete intent coverage and a concrete lowering for every control
   or reference edge.
3. Execute by `plan_id` with rollback on failure. Brain transactions already
   provide snapshot, undo, validation, and rollback; do not wrap them in a
   duplicate manual transaction.
4. Read `TransactionResult`, validation evidence, rollback state, and the final
   output path before reporting completion.

### Direct primitive route

- Prove the target node and parameter first.
- Group related edits in one undo block. Snapshot before destructive or
  high-risk changes.
- Prefer `td_create_node`, `td_connect_nodes`, `td_set_params`,
  `td_custom_parameters`, and other typed tools over `td_exec_python`.
- Make the smallest reversible edit that satisfies the request.
- Validate at a logical checkpoint and close the undo block cleanly.

Never pass raw user prose to an execution tool. Never use `td_tool_batch` to
pretend several mutations are atomic.

## Graph Readability

- Inspect existing placement before adding nodes.
- Lay out signal flow left-to-right, normally 250 pixels between serial nodes
  and 200 pixels between parallel domains.
- Use stable, semantic names and finish consumable chains with a named output
  Null.
- Keep domain/control/debug groups visually distinct. Respect an existing color
  convention; otherwise use blue for sources, green for processing, orange for
  outputs, purple for control, and red for temporary diagnostics.
- Preserve nodes outside the named target and any explicitly protected paths.

## Verification Checkpoints

Validate the behavior requested, not only graph shape:

- **Graph:** required nodes, types, inputs, references, control bindings,
  ownership boundaries, and stable output.
- **Runtime:** relevant TD errors, cook health, expression/parameter readback,
  CHOP activity, and geometry or POP counts where applicable.
- **Visual:** output exists, is nonblack/nonuniform when expected, and changes
  over time when motion or reactivity was requested.
- **Performance:** check cook hotspots and FPS for production-sensitive work.
- **Preservation:** confirm protected nodes and the previous active route remain
  valid when modifying an existing system.

Use metadata analysis first. When visual proof is requested or is required to
verify the task, one low-quality inline thumbnail is allowed without a separate
confirmation roundtrip. Save diagnostic captures outside the project when
appropriate. Ask before repeated image payloads, monitoring with images, or
continuous streaming; stop streams when the check ends.

Unavailable evidence is `unverified`, not passing. If validation fails, use the
smallest assertion-specific repair or the recovery workflow. Never hide a
rollback or present a fallback image as the requested result.

## TouchDesigner Safety Facts

- OP-reference parameters must resolve to real operators. Prefer typed path
  references; use Python assignment only when the direct tool cannot express a
  proven reference style.
- Parameter names, enums, tuple shapes, and ranges come from parameter
  semantics or live inspection, not memory.
- A new TD 2025 `geometryCOMP` may contain a default POP source. Inspect its
  children before assuming SOP-based geometry or instancing.
- `td_get_errors == 0` does not prove a render is visible. Camera framing,
  geometry, material, scale, alpha, and final TOP content still need relevant
  readback or visual analysis.
- A canonical feedback loop uses a visible source, `feedbackTOP`, bounded
  `levelTOP` decay, a compositor, and a stable output. The feedback target is
  the loop compositor, not the final output Null. Prove temporal change.
- Expressions should use dependency-aware TD objects such as `me.time.seconds`
  when appropriate; avoid fragile absolute paths when a relative reference is
  possible.

## Memory and Learning

- Recall before rebuilding a taste-critical or known technique.
- Reuse only when TD build, operator availability, inputs, and validation state
  are compatible.
- Learn only after graph, runtime, and requested visual behavior pass.
- Save project-specific preferences locally. Promote globally only after
  repeated validated reuse.
- Never learn a repair fallback, partial plan, or visually weak result as a
  successful technique.

## Completion Report

Lead with the outcome. Include the exact changed scope, chosen route, stable
output, concise validation evidence, rollback status, and any residual risk.
Keep normal build summaries compact; retrieve full plans or traces only for
debugging.

## Reference Files

Load these only when the task needs them:

- `references/advanced-workflows.md` — optimization, safety, events, timescale,
  and feedback displacement.
- `references/preset-systems-and-ui.md` — preset, morphing, control UI, and
  performance patterns.
- `references/external-sync-and-control.md` — Link, MIDI, DAW routing, and
  cross-plugin control.

## Pressure Scenarios

- Pressure: A creative prompt resembles one known keyword. Classify the whole
  request; use ground → author → propose when the known pattern cannot cover
  every required facet.
- Pressure: A user asks for speed. Batch independent reads and use summary
  responses, but keep coverage, transaction, and final validation gates.
- Pressure: A mutation call succeeds. Do not declare completion until the
  request-specific checkpoint proves the resulting state.

## Common Mistakes

- Treating `td_brain_plan` as the mandatory entry for every non-trivial task.
- Executing a plan with incomplete coverage or an ignored control/reference
  edge.
- Re-reading the same live state or scanning errors after every primitive op.
- Asking permission for one necessary thumbnail, or streaming images without
  permission.
- Claiming visual success from zero TD errors alone.
- Saving unvalidated work to memory.
