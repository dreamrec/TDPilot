---
name: tdpilot-production
description: >
  Production-grade TouchDesigner MCP workflow for TDPilot v1.3.2 (90 tools):
  staged edits with undo blocks, rollback safety via snapshots, token-efficient
  diagnostics, strict completion gates, and v1.1 features including
  td_project_lifecycle (save/undo/redo), td_custom_parameters (declarative
  param authoring), and td_pop_inspect (POP-native data inspection).
---

# TDPilot Production v1.3.2

## Use This Skill When
- The user asks for reliable, production-safe network edits.
- The task affects live performance, show-critical logic, or many nodes.
- The user asks for "stable", "ship-ready", "realistic", or "production" workflows.

## Non-Negotiable Output Contract
- Make small, reversible edit batches wrapped in undo blocks.
- Keep token usage controlled (no continuous image payloads unless explicitly approved).
- End every meaningful mutation task with verification evidence.
- Report unresolved risks explicitly.

## Production Workflow

### 1) Preflight and Scope Lock
- Call `td_get_info` and `td_get_capabilities`.
- Inspect only the target scope first (`td_get_nodes`, `td_get_node_detail`, `td_get_params`).
- For comprehensive overview: `td_get_state_vector` returns project, timeline, health, performance, events, monitoring, safety, snapshots, and jobs in one call.
- Confirm exact root path and objective before mutation.

### 2) Safety Baseline
- Create a rollback point with `td_snapshot_scene`.
- For risky parameters, set bounds first with `td_set_param_bounds`.
- If scene health is unknown, run `td_detect_instability` before large edits.
- Start an undo block: `td_project_lifecycle({ action: "start_undo_block", name: "description" })`.

### 3) Mutation Strategy
- Apply edits in batches of one structural step: create → connect → parameterize → validate.
- Prefer deterministic parameter sets over arbitrary Python execution.
- Use `td_custom_parameters` (v1.1) for custom param pages instead of `td_exec_python`.
- Use `td_exec_python` only when no direct tool path exists.
- For POP data, use `td_pop_inspect` (v1.1) instead of Python hacks.

### 4) Continuous Verification
- After each batch, run:
  - `td_get_errors` on affected root
  - `td_cooking_info` (or `td_get_state_vector`) for performance signal
- If instability rises, pause and rollback or clamp before continuing.

### 5) Token-Efficient Visual Checks
- Default: metadata-only monitoring (`include_image=false`).
- Use one-off `td_screenshot` for targeted visual confirmation.
- Enable streaming image payloads only after explicit user approval.

### 6) Technique Reuse Rules
- Check existing memory first with `td_memory_recall`.
- Save only proven reusable patterns with `td_memory_learn` + `td_memory_save`.
- Promote to global (`td_memory_promote`) only after repeated successful reuse.

### 7) Completion Gates (Must Pass)
- No unacknowledged critical errors in `td_get_errors`.
- Performance remains acceptable for the stated context.
- Snapshot/rollback path exists and is documented.
- End the undo block: `td_project_lifecycle({ action: "end_undo_block" })`.
- Final response includes: changed scope, verification evidence, and residual risks.

## Failure Protocol
- On unsafe drift or rising errors:
  1. Pause timeline if needed (`td_emergency_stabilize` or `td_timeline_set`).
  2. Restore with `td_restore_snapshot` or `td_project_lifecycle({ action: "undo" })`.
  3. Report root cause and smallest next safe step.

## v1.1 Lifecycle Features
- **Undo blocks**: Wrap major operations in `start_undo_block`/`end_undo_block` so the user can Ctrl+Z the entire batch as one step.
- **Project save**: `td_project_lifecycle({ action: "save" })` — save before destructive ops.
- **Undo/redo**: Quick rollback without snapshots for recent changes.

## Handoff Format
- `Scope`: exact root/components changed.
- `Actions`: structural and parameter edits made.
- `Validation`: error + performance checks run and outcomes.
- `Rollback`: snapshot id and/or undo block name, restore instructions.
- `Risks`: what is still uncertain or deferred.
