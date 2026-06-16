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
`BrainPlan` first, then execute that plan.

## Workflow

1. Inspect the live project first:
   - `td_get_focus`
   - `td_get_state_vector`
   - `td_get_nodes` for the target root
   - `td_get_errors` when health is unknown

2. Ask the brain to plan:
   - Call `td_brain_plan(intent, target_root, output_top, constraints, preferred_domains, validation_profile)`.
   - Treat `blocked_questions` as a hard stop. Ask the user or inspect more; do not guess.
   - Check the returned concept graph, operator families, risks, missing facts, docs, hints, and memory evidence.

3. Execute only a valid plan:
   - Call `td_brain_execute(plan, transaction_policy="rollback_on_failure")`.
   - Use `learn_on_success=true` only when the validation report passes and the result is reusable.
   - Do not pass raw user text to execution tools.

4. Verify completion:
   - Read the returned `TransactionResult`.
   - Confirm validation profile, TD errors, cook health, parameter readback, output path, and rollback outcome.
   - Use one targeted screenshot or TOP analysis when visual correctness matters.

## Planning Standards

- Prefer grounded concepts over isolated node recipes.
- Require explicit target root and output TOP when the result needs to feed a larger system.
- Use docsbrain/card-index evidence before creating unfamiliar operators.
- Use machine-readable hints as constraints, not as decorative prose.
- Preserve local-first behavior. Do not require hosted LLMs, accounts, embeddings, or cloud services.

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

Stop before mutation when:

- The target root is ambiguous.
- The requested concept cannot be grounded in available operator families.
- Required operators are missing for the current TD build.
- The plan exceeds transaction limits.
- The user asks for live visual payloads and `confirm_visual_payload` is false.

## Pressure Scenarios

- Pressure: The user says "just build it fast" but the target root or output is unclear. Inspect first, call `td_brain_plan`, and treat `blocked_questions` as a hard stop.
- Pressure: A partial `BrainPlan` looks plausible but has missing operators or stale live-state assumptions. Do not execute; refresh TD state or ask for the missing fact.

## Common Mistakes

- Creating nodes with low-level graph tools for a non-trivial network before producing a `BrainPlan`.
- Treating a successful apply call as proof of correctness without reading validation, TD errors, and rollback status.
- Saving memory from a visually weak or validation-failed result.
