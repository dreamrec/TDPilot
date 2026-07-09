---
name: tdpilot-brain-builder
description: >
  Use when the user asks to build, extend, or transform a non-trivial
  TouchDesigner network with TDPilot brain tools.
---

# TDPilot Brain Builder

Use this skill when the user asks TDPilot to build, extend, or transform a
TouchDesigner network and the task is more than a single obvious parameter edit.

## Core Rule

Do not mutate TouchDesigner directly from free text. Turn intent into a
`BrainPlan` first, then execute that plan. A blocked plan must never be
executed — but a blocked plan is not the end of the task either: your next
move is to author the plan yourself through the ground -> propose loop below.

## The One Loop

Every non-trivial build follows one loop with two entry paths:

1. Inspect the live project first:
   - `td_get_focus`
   - `td_get_state_vector`
   - `td_get_nodes` for the target root
   - `td_get_errors` when health is unknown

2. Ask the brain to plan:
   - Call `td_brain_plan(intent, target_root, output_top, constraints, preferred_domains, validation_profile)`.
   - Check the returned concept graph, operator families, risks, missing facts, docs, hints, and memory evidence.

3. **On success** (no `blocked_questions`, non-empty operations):
   - Call `td_brain_execute(plan_id=<plan.id>, transaction_policy="rollback_on_failure")`.

4. **On blocked or unsupported** (`blocked_questions` non-empty, or the plan is
   empty because no compiler route exists): do not execute it, and do not stop.
   Author the plan yourself:
   - Call `td_brain_ground(intent, target_root)` and read the grounding pack:
     `task_features`, `corpus_evidence`, `candidate_operators` (with key params
     and gotchas), `param_semantics` (the only param values that survive),
     `operator_availability`, `live_state`, `exemplars`, and the
     `authoring_contract` that spells out the exact draft schema.
   - Author a draft candidate graph JSON using ONLY operators from
     `candidate_operators`/`operator_availability` and param values inside the
     `param_semantics` contracts (see the worked example below).
   - Call `td_brain_propose(draft, target_root)`. On rejection, read the
     machine-readable `rejections` (each has `code`, `subject`, `fix`), fix the
     draft, and re-propose. On acceptance, check
     `plan_summary.stripped_params`: any param value without a known semantics
     contract was silently STRIPPED, not rejected — re-author if a stripped
     value mattered.
   - Call `td_brain_execute(plan_id=<returned plan_id>)`.

5. Verify completion:
   - Read the returned `TransactionResult`.
   - Confirm validation profile, TD errors, cook health, parameter readback, output path, and rollback outcome.
   - Use one targeted screenshot or TOP analysis when visual correctness matters.

Only truly unanswerable questions (ambiguous target root, an external device
the user has not named, a hard operator gap in this TD build) go back to the
user. Everything else is authorable from the grounding pack.

## Worked Example: Draft For td_brain_propose

A valid audio-reactive feedback draft (params are real registry-backed
values — `analyzeCHOP.function` enum `rmspower`, `levelTOP.opacity` in [0,1],
`feedbackTOP.top` an op-path ref via `${path:...}`):

```json
{
  "label": "Audio-reactive feedback trails",
  "profiles": ["audio_reactive", "feedback"],
  "concepts": [
    {"id": "audio", "label": "Audio input", "role": "source", "domain": "CHOP",
     "op_type": "audiofileinCHOP", "params": {"volume": 1.0}},
    {"id": "analyze", "label": "RMS analysis", "role": "process", "domain": "CHOP",
     "op_type": "analyzeCHOP", "params": {"function": "rmspower"}},
    {"id": "level_ctl", "label": "Control output", "role": "output", "domain": "CHOP",
     "op_type": "nullCHOP"},
    {"id": "source", "label": "Noise source", "role": "source", "domain": "TOP",
     "op_type": "noiseTOP", "params": {"period": 4.0}},
    {"id": "feedback", "label": "Feedback buffer", "role": "feedback", "domain": "TOP",
     "op_type": "feedbackTOP", "params": {"top": "${path:composite}"}},
    {"id": "decay", "label": "Trail decay", "role": "process", "domain": "TOP",
     "op_type": "levelTOP", "params": {"opacity": 0.92}},
    {"id": "composite", "label": "Composite merge", "role": "process", "domain": "TOP",
     "op_type": "compositeTOP", "params": {"operand": "add"}},
    {"id": "output", "label": "Stable output", "role": "output", "domain": "TOP",
     "op_type": "nullTOP"}
  ],
  "edges": [
    {"source": "audio", "target": "analyze", "kind": "data"},
    {"source": "analyze", "target": "level_ctl", "kind": "data"},
    {"source": "level_ctl", "target": "decay", "kind": "control"},
    {"source": "source", "target": "composite", "kind": "data"},
    {"source": "feedback", "target": "decay", "kind": "data"},
    {"source": "decay", "target": "composite", "kind": "data"},
    {"source": "composite", "target": "feedback", "kind": "feedback"},
    {"source": "composite", "target": "output", "kind": "data"}
  ],
  "required_ops": ["audiofileinCHOP", "analyzeCHOP", "nullCHOP", "noiseTOP",
                   "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
  "validation_needs": ["audio_signal_activity", "feedback_output_readback"],
  "explanation": "RMS drives trail decay; recursive feedback composited over noise."
}
```

Rules the review gate enforces: `data` edges wire same-family inputs; use
`reference`/`control` edges plus `${path:concept_id}` op-path params for
cross-family links; every op needs an official docs card; end each chain in a
stable output null.

## Planning Standards

- Prefer grounded concepts over isolated node recipes.
- Require explicit target root and output TOP when the result needs to feed a larger system.
- Use docsbrain/card-index evidence before creating unfamiliar operators.
- Use machine-readable hints as constraints, not as decorative prose.
- Preserve local-first behavior. Do not require hosted LLMs, accounts, embeddings, or cloud services.
- Do not pass raw user text to execution tools; `td_brain_execute` accepts only a valid plan or `plan_id`.
- Use `learn_on_success=true` only when the validation report passes and the result is reusable.

## Concept-to-node Atlas Workflow

The packaged 656-card reviewed operator atlas has a zero-concept backlog across
CHOP, COMP, DAT, MAT, POP, SOP, and TOP. Treat it as the first stop for turning
an abstract visual idea into concrete TouchDesigner nodes.

When intent is abstract:

1. Name the data domains involved: texture/TOP, channel/CHOP, table/DAT,
   geometry/SOP, particle/POP, material/MAT, or component/COMP.
2. Use the atlas/card-index, docsbrain, and Official Derivative docs URLs to
   choose candidate operators and parameters before inventing a node chain.
3. choose the smallest operator chain that expresses the concept, then add
   controls, diagnostics, and outputs around it.
4. Carry atlas `key_concepts`, `key_params`, and `common_gotchas` into the
   BrainPlan risks, validation checks, and parameter choices.
5. If the atlas cannot ground the concept in real operators for the current TD
   build, `td_brain_ground` still returns the closest candidate operators —
   author the draft from those instead of improvising unverified node names.

## Compiler-Backed Planning Workflow

For supported multi-domain prompts, `td_brain_plan` may return a
compiler-backed concept plan. Inspect the compiler evidence before execution:

- `compiled_task` states domains, motifs, capabilities, risks, and docs facts.
- `candidate_graphs` show pattern resolver choices, scores, required operators,
  substitutions, and blocked alternatives.
- The availability matrix explains missing operators, live-family omissions, and
  safe substitutions before a `PatchPlan` exists.
- parameter semantics must pass before mutation; unsafe OP refs, ranges, enums,
  or tuple shapes are hard stops.
- validation probes and assembly macros should match the selected profiles:
  named outputs, component shell, controls, debug taps, notes, and layout are
  part of the readable network contract.

If any compiler-backed evidence is absent, stale, or under-grounded, switch to
the ground -> author -> propose loop instead of filling gaps by hand.

## Valid Networks

A good BrainPlan states:

- Visual intent and selected concept profile.
- Concept nodes and semantic edges.
- Concrete TD operators and parameters.
- Dependency-ordered patch operations.
- Expected output TOP or affected root.
- Validation profile and concept-specific checks.
- Recovery path with snapshot and undo behavior.

## Stop Conditions

Blocked plans must not be executed. Before falling back to the user, exhaust
the ground -> author -> propose loop. Only stop and ask when:

- The target root is genuinely ambiguous and the user must choose.
- The task depends on an external device or network source the user has not
  declared (`constraints.device_sources`).
- Required operators are missing from the current TD build and
  `operator_availability` offers no viable substitute.
- The plan exceeds transaction limits.
- The user asks for live visual payloads and `confirm_visual_payload` is false.

## Pressure Scenarios

- Pressure: The user says "just build it fast" but the target root or output is unclear. Inspect first, call `td_brain_plan`, and if it blocks on a genuinely ambiguous root, ask — otherwise run the ground -> author -> propose loop instead of guessing.
- Pressure: `td_brain_plan` returns blocked/unsupported for a creative prompt. Do not surrender and do not hand-build nodes: call `td_brain_ground`, author a draft from `candidate_operators` + `param_semantics`, validate with `td_brain_propose`, then `td_brain_execute(plan_id=...)`.
- Pressure: `td_brain_propose` accepts the draft but `plan_summary.stripped_params` is non-empty. Do not shrug it off — the stripped values were doing creative work; re-author with registry-backed params or accept the defaults deliberately.
- Pressure: A partial `BrainPlan` looks plausible but has missing operators or stale live-state assumptions. Do not execute; refresh TD state or re-ground and re-propose.

## Common Mistakes

- Creating nodes with low-level graph tools for a non-trivial network before producing a `BrainPlan`.
- Treating `blocked_questions` as the end of the task instead of the entry point to the `td_brain_ground` -> draft -> `td_brain_propose` loop.
- Ignoring `plan_summary.stripped_params` after a propose — the plan executes without those values.
- Authoring drafts with operators that are not in `candidate_operators` or that `operator_availability` marks unavailable.
- Treating a successful apply call as proof of correctness without reading validation, TD errors, and rollback status.
- Saving memory from a visually weak or validation-failed result.
