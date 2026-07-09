# TDPilot Deprecations

This document tracks tool surfaces that are deprecated and scheduled for
removal, plus how to migrate off them. Nothing listed here is removed yet —
deprecated tools remain fully registered and functional until their stated
removal release. The tool count is unchanged by deprecation (still 114).

## Legacy patch/plan pipeline → BrainPlan pipeline

**Status:** Deprecated. **Slated for removal:** v3.0.

The pre-BrainPlan planning/patch tools are superseded by the grounded BrainPlan
pipeline (`td_brain_plan` → `td_brain_execute`, with `td_brain_ground` →
`td_brain_propose` as the host-authored fallback). Their `@mcp.tool`
descriptions now carry the prefix:

> `(Legacy — prefer td_brain_plan → td_brain_execute; slated for removal in v3.0.)`

### Deprecated tools

| Legacy tool | Role | Replacement |
| --- | --- | --- |
| `td_plan_patch` | Build the pre-v1.5 patch **dict** shape | `td_brain_plan` (returns a typed `BrainPlan`) |
| `td_preflight_patch` | Validate a `td_plan_patch` dict | `td_brain_plan` (grounding + validation are built in) |
| `td_validate_recipe` | Read-only recipe compatibility check | `td_brain_plan` / `td_brain_ground` |
| `td_patch_plan` | Compatibility/expert typed `PatchPlan` construction | `td_brain_plan` |
| `td_patch_preview` | Read-only `PatchPlan` preview | `td_brain_plan` (carries concept/corpus/validation context) |
| `td_patch_apply` | Destructive `PatchPlan` executor | `td_brain_execute` (default validated transaction path) |
| `td_patch_validate` | Read-only patch-target validation | `td_brain_plan` + `td_brain_execute` |
| `td_patch_variations` | Generate `PatchPlan` variants | `td_brain_plan` (variants stay grounded in a `BrainPlan`) |

`td_transaction_apply` is **not** deprecated. It is the low-level transaction
executor that `td_brain_execute` wraps; use it directly only when you already
hold a ready `PatchPlan`/`BrainPlan` and want raw preflight/snapshot/dry-run/
rollback controls.

## Migration

### Legacy patch **dict** → `BrainPlan`

Old flow (deprecated):

```
td_plan_patch(intent=..., target_path=...)   # -> pre-v1.5 patch dict
td_preflight_patch(plan=<dict>)              # -> validation
# ...then a manual apply
```

New flow:

```
td_brain_plan(intent=..., target_root=...)   # -> typed BrainPlan (grounded, validated)
td_brain_execute(plan_id=<id>)               # -> transactional apply + optional learning
```

- `intent` maps directly.
- `target_path` → `target_root`.
- A recipe/technique starting point that previously went through
  `td_validate_recipe` should instead be surfaced to `td_brain_plan`
  (via memory recall) or drafted with `td_brain_ground` → `td_brain_propose`.
- `td_brain_plan` already folds in the preflight/validation that
  `td_preflight_patch` / `td_patch_validate` provided separately, so those
  become unnecessary.

### Patch family (`td_patch_*`) → brain family (`td_brain_*`)

| Legacy call | Brain-family equivalent |
| --- | --- |
| `td_patch_plan(...)` | `td_brain_plan(...)` |
| `td_patch_preview(plan=...)` | inspect the `td_brain_plan` result (non-mutating) |
| `td_patch_apply(plan=...)` | `td_brain_execute(plan=... or plan_id=...)` |
| `td_patch_validate(path=...)` | validation is carried by `td_brain_plan` |
| `td_patch_variations(plan=...)` | re-run `td_brain_plan` with varied constraints |

If you must stay on the low-level layer during migration, a ready
`PatchPlan`/`BrainPlan` can be applied through `td_transaction_apply`, which
`td_patch_apply` and `td_brain_execute` both build on.

## Removal criteria

These tools will be removed in **v3.0** once:

1. The BrainPlan pipeline covers every workflow the legacy tools served
   (planning, preview, validation, apply, variations).
2. No shipped skill, prompt, doc, or eval references the legacy tools as a
   primary path.
3. A full release cycle has carried the deprecation prefix so integrators had
   notice.

Removing them will also drop the tool count below 114; that bump is part of the
v3.0 release checklist, not this deprecation notice.
