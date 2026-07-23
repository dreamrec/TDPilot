---
name: tdpilot-production
description: >
  Production-grade TouchDesigner MCP workflow for TDPilot v2.4.1 (114 tools):
  show-safe routing, bounded inspection, staged transactions, rollback,
  performance checks, preservation assertions, and evidence-based handoff.
---

# TDPilot Production v2.4.1

Use this skill in addition to `tdpilot-core` when work is show-critical,
performance-sensitive, destructive, broad in scope, or explicitly requested as
stable, production-ready, or show-safe.

## Core Rule

Protect the running project and its active output. Prove the target and
preservation boundary, use the correct brain route, apply the smallest staged
change, and accept it only when graph, runtime, visual, performance, and
preservation checks pass.

## Production Workflow

### 1. Scope and preflight

- Inspect focus, exact target root, direct connections, active output, and
  protected paths. Use `td_get_info`/`td_get_capabilities` only when build or
  capability compatibility matters.
- Read current errors and performance once for a baseline.
- Batch independent reads with `td_tool_batch`; keep mutations transactional.
- Record device, resolution, FPS, latency, and output-routing constraints.
- Treat an ambiguous active route, missing external device, or unproven
  ownership boundary as a blocking question.

### 2. Choose the build route

- One proven edit at a known path may use a typed primitive tool.
- An exact compiler-backed pattern may use `td_brain_plan`.
- Artistic, multi-domain, spatial, or implicit architecture goes directly
  through `td_brain_ground` → author → `td_brain_propose`.
- Require complete intent coverage and concrete lowering for control/reference
  edges before execution. A partial plan is not a production fallback.

Recall compatible local techniques before taste-critical authoring. Memory and
knowledge may inform a proposal, but only validated techniques or promoted
traces may compile automatically.

### 3. Safety baseline

Brain execution already provides snapshot, undo, validation, and rollback; do
not surround it with redundant manual wrappers. For direct primitive edits:

- Snapshot before destructive or broad changes.
- Start one named undo block around a coherent batch.
- Set bounds before modifying show-sensitive numeric controls.
- Keep the prior active path intact until a replacement is validated.

### 4. Apply in logical batches

- Prefer deterministic typed operations over arbitrary Python.
- Keep source, processing, control, render, and output stages independently
  inspectable.
- End each module with a stable named output and preserve external consumers.
- Check errors and readback at logical batch boundaries, on failure, and at
  completion—not after every individual create/connect/set call.
- If errors or cook cost rise materially, stop the next batch and diagnose or
  roll back.

For show-safe work, build in staging, validate there, then use only a guarded
route swap (`route_swap`) whose old connection, new connection, and rollback behavior are
explicit. Never delete the previous path as part of the swap.

### 5. Validation contract

Require evidence appropriate to the request:

- Graph: topology, references, bindings, outputs, ownership, protected nodes.
- Runtime: TD errors, cook health, expression readback, signal/geometry/POP
  activity.
- Visual: nonblack/nonuniform content, temporal change, and expected response.
- Performance: FPS trend, cook hotspots, resolution, viewers/always-cook state.
- Preservation: active output and protected paths remain within the agreed
  tolerance.

Start with metadata. One low-quality thumbnail is appropriate when visual proof
is required. Ask before repeated image payloads or continuous monitoring.
Unavailable evidence remains explicitly unverified.

### 6. Failure and repair

- Use the smallest repair tied to the failed assertion.
- Re-run affected assertions plus final critical assertions.
- Respect the plan's repair budget; never enter an unbounded fix loop.
- Roll back on unsafe drift, unknown failure, preservation failure, or exhausted
  repair budget.
- After rollback or manual edits, refresh live state before reusing any plan.

## Completion Gates

- Required intent coverage is complete.
- No unacknowledged critical TD errors remain.
- Requested runtime and visual behavior is proven.
- Performance is acceptable for the declared context.
- Protected nodes and active routing pass preservation checks.
- Rollback status and previous-path availability are known.

## Handoff Format

- `Outcome`: what is now usable.
- `Scope`: exact roots/modules changed.
- `Route`: direct, pattern, or concept-authoring.
- `Validation`: graph/runtime/visual/performance/preservation evidence.
- `Rollback`: transaction result or snapshot/undo identifier.
- `Risks`: unresolved or unavailable evidence.

## Pressure Scenarios

- Pressure: The show starts soon. Reduce ambition and batch reads, but do not
  bypass staging, preservation, or rollback gates.
- Pressure: A replacement validates in staging. Do not delete the old path;
  switch through a guarded route operation and retain rollback data.
- Pressure: The result looks plausible but performance was not measured. Keep
  it unapproved for show-safe use until cook/FPS evidence is available.

## Common Mistakes

- Running every non-trivial request through the pattern planner.
- Taking redundant snapshots around an already transactional BrainPlan.
- Calling `td_get_errors` after every primitive rather than at checkpoints.
- Replacing the live route before staging validation passes.
- Treating a static plan-structure probe as runtime or visual proof.
