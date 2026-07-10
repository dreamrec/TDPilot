---
name: tdpilot-brain-builder
description: >
  Use when the user asks to build, extend, or transform a non-trivial
  TouchDesigner network with TDPilot brain tools.
---

# TDPilot Brain Builder

Use this skill for non-trivial TouchDesigner construction or transformation.
Load `tdpilot-production` separately only for production/show-safe work.

## Core Rule

Classify the whole request before choosing a brain route. Exact validated
patterns may use `td_brain_plan`; artistic, multi-domain, spatial, camera/depth,
fog, or architecture-shaped requests go directly through ground → author →
propose. Execute only a valid plan with complete intent coverage and fully
lowered semantic edges.

## One Build Loop, Two Brain Routes

### 1. Inspect only what changes the plan

- Start with `td_get_focus`, the target root, direct connections, and relevant
  parameters/errors.
- Use `td_get_state_vector` only when broad project health or performance is
  relevant.
- Put independent reads in `td_tool_batch`; never batch mutations as a fake
  transaction.
- Establish the exact target root, protected paths, desired stable output, and
  any external device/file dependency.

### 2. Extract the requirements

List every material capability, input, output, constraint, spatial feature,
behavior, quality, binding, and validation need. Each required facet must have
evidence from a concept/module, parameter, connection, binding, or assertion.
Do not let one recognized keyword hide the rest of a multi-domain request.

### 3A. Pattern-shaped route

Use this only when TDPilot has an exact validated topology or technique
composition for the complete request:

1. Call `td_brain_plan(..., detail_level="summary")`.
2. Inspect `route`, `intent_coverage`, required operators, output, risks, and
   validation contract.
3. Execute only when required coverage is complete, operations are nonempty,
   and `unresolved_semantic_edges` is empty.
4. If it returns `host_authored`, `clarify`, incomplete coverage, or an
   unsupported combination, continue with route 3B. Never execute the partial
   match.

### 3B. Concept-shaped route

1. Before taste-critical authoring, recall compatible evidence with
   `td_memory_recall` and `td_knowledge_recall`, or call grounding with
   `include_memory=true`.
2. Call `td_brain_ground` with the full intent, target root, constraints,
   desired output, mode, and `trace_level="summary"`.
3. Read the returned `grounding_id`, task facets, live state, corpus evidence,
   ranked candidate operators, parameter semantics, availability, recall
   bundle, exemplars, and exact `authoring_contract`.
4. Author the smallest draft that covers every required facet. Candidate
   operators are ranked suggestions, not permission to invent unavailable or
   undocumented operators: additions still require an official card, live
   availability, and parameter semantics.
5. Call `td_brain_propose` with the same `grounding_id`,
   `draft_schema_version="2"`, and `detail_level="summary"`.
6. On rejection, fix the machine-readable cause and re-propose. On acceptance,
   check server-recomputed coverage and any stripped parameters. A host claim
   that coverage is complete is never authoritative.

Only read `references/progressive-drafts.md` when authoring a draft. It contains
compact 2D and 3D skeletons; the current grounding pack's authoring contract
always wins if the schema has evolved.

### 4. Enforce semantic edges

- Every control edge requires one explicit binding.
- The supported bounded CHOP reference shape is
  `{"mode":"chop_reference_expression","source_channel":0,"target_param":"brightness1"}`;
  a safe channel name may replace the index.
- The target parameter must be registry-backed and numeric. Resolve static
  value conflicts before proposal.
- A reference edge requires an explicit OP-reference parameter.
- No semantic edge may be silently ignored. Unsupported binding targets block
  execution rather than becoming decorative prose.

### 5. Execute and validate

- Execute only by accepted `plan_id`, normally with rollback on failure.
- Read the complete `TransactionResult`: applied state, validation report,
  rollback result, stable output, and residual risk.
- Check errors at logical checkpoints and completion, not after every operation.
- Prove requested signal activity, binding/expression readback, graph shape,
  output content, and temporal change. One low-quality thumbnail is appropriate
  when visual proof is required; ask before repeated images or streaming.
- Learn only a reusable result whose graph, runtime, and requested visual
  behavior passed.

Only truly unanswerable facts go back to the user: an ambiguous root or output,
an unnamed external device/file, or a hard operator gap with no compatible
substitute.

## Concept-to-node Atlas Workflow

The packaged 656-card reviewed operator atlas has a zero-concept backlog across
CHOP, COMP, DAT, MAT, POP, SOP, and TOP and cites Official Derivative sources.

1. Name every data domain required by the complete intent.
2. Use atlas concepts, official cards, availability, key parameters, and
   gotchas to ground candidates.
3. From accepted candidates, choose the smallest operator chain that covers the request, then add stable
   outputs, controls, and only the diagnostics required by validation.
4. Carry compatibility and gotchas into risks and assertions.
5. If the current TD build cannot realize the concept, return a specific gap;
   do not improvise an operator or silently reduce scope.

## Compiler-Backed Planning Workflow

For a pattern route, inspect the compiler evidence before execution:

- `compiled_task` and intent coverage represent the full request.
- `candidate_graphs` and the pattern resolver explain technique selection.
- The availability matrix and parameter semantics prove the operators and
  writes are valid for the current build.
- validation probes must test the actual requested behavior.
- Legacy assembly macros may appear in old plans; they are not proof that an
  artistic or multi-domain request is complete.

Switch to ground → author → propose whenever compiler evidence is absent,
stale, incomplete, or under-grounded.

## Valid Plan Contract

A plan is executable only when it provides:

- Full compiled intent and server-recomputed complete coverage.
- Concrete concepts/modules, operators, parameters, and dependency order.
- Lowered data, feedback, reference, and control edges.
- A stable output or exact affected root.
- Request-specific graph/runtime/visual validation.
- Transaction and rollback policy.

Legacy plans without v2 coverage remain supported, but shipped v2 workflows
must not use that absence to bypass the coverage gate.

## Stop Conditions

Do not execute when:

- Required coverage is incomplete or semantic edges remain unresolved.
- Proposal review rejects the draft or strips a creatively essential value.
- Live state invalidates a plan precondition.
- Required operators or safe substitutions are unavailable.
- The plan exceeds transaction limits.
- Visual streaming or repeated image payloads lack user approval.

## Pressure Scenarios

- Pressure: The user says “just build it fast.” Batch independent reads and use
  summary detail, but keep route classification, coverage, transaction, and
  final validation gates.
- Pressure: `td_brain_plan` recognizes “audio” but omits requested particles,
  depth, fog, or rendering. Treat it as incomplete and use ground → author →
  propose.
- Pressure: Proposal review accepts the graph but reports stripped parameters.
  Re-author any value that materially affects the concept.
- Pressure: A control edge looks obvious. Do not assume it compiles; require a
  concrete binding and prove target readback.

## Common Mistakes

- Calling `td_brain_plan` first for every non-trivial request.
- Treating `blocked_questions` as the end instead of checking whether the
  ground/propose route can resolve the task.
- Authoring from one family while ignoring other required domains.
- Copying an example without the live grounding contract.
- Executing with incomplete coverage, ignored semantic edges, or stale state.
- Saving a partial or visually weak result to memory.
