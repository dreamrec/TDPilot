---
name: tdpilot-brain-recovery
description: >
  Use when a TDPilot brain or patch transaction fails, rollback is incomplete,
  TouchDesigner becomes unstable, or a broken network needs repair.
---

# TDPilot Brain Recovery

Use this skill when a transaction fails, validation fails, TD errors rise, or a
network needs repair after an attempted build.

## Core Rule

Do not continue building on an uncertain failed state. Recover, verify, then
plan from fresh live state.

## First Response

Do not continue building. Stabilize and recover.

1. Read the last `TransactionResult` or activity log.
2. Identify the failed op, snapshot id, rollback status, and validation issues.
3. Inspect the affected root with `td_get_nodes`, `td_get_errors`, and
   `td_cooking_info`.

## Recovery Order

1. If the transaction already rolled back cleanly, verify the root and report.
2. If rollback used TD undo, confirm the intended nodes are gone or restored.
3. If snapshot restore is needed, use the snapshot id from the transaction.
4. If `needs_manual_recovery=true`, stop automatic mutation and report:
   - snapshot id
   - failed op
   - affected root
   - remaining TD errors
   - smallest safe next manual or assisted step

## Repair Planning

After recovery, build a new plan from the recovered state. Do not reuse a stale
BrainPlan unless live state still matches the plan preconditions.

## What To Avoid

- Do not stack another large mutation on top of an uncertain failed state.
- Do not learn failed techniques.
- Do not hide rollback failures behind a generic success message.
- Do not use broad Python cleanup when structural TD tools can remove or restore
  exact nodes.

## Pressure Scenarios

- Pressure: A transaction partially applied and the user asks to "try again." Read rollback status, inspect the affected root, and refuse a second large mutation until recovery is verified.
- Pressure: `needs_manual_recovery=true` appears with a snapshot id. Stop automatic mutation and report the snapshot, failed op, affected root, and smallest safe next step.

## Common Mistakes

- Reusing a stale `BrainPlan` after rollback or manual edits changed live state.
- Calling learning tools for a failed or rolled-back technique.
- Reporting success when rollback worked but validation after rollback was never checked.
