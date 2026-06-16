---
name: tdpilot-brain-explorer
description: >
  Use when investigating an unfamiliar TouchDesigner project, target root,
  selected nodes, errors, operator availability, or planning context.
---

# TDPilot Brain Explorer

Use this skill before build, debug, validation, or recovery work when the live
TouchDesigner state is not already clear.

## Core Rule

Stay read-only. Exploration produces facts and constraints, not edits.

## Discovery Path

1. Locate context:
   - `td_get_focus`
   - `td_get_state_vector`
   - `td_get_nodes` on the likely root
   - `td_get_connections` for candidate outputs

2. Check health:
   - `td_get_errors` with recursion on the target root
   - `td_cooking_info` for cook/performance signal
   - `td_list_families` when operator availability matters

3. Gather grounding evidence:
   - `td_get_node_detail(include_hints=true)` for high-risk operators
   - `td_get_hints(topic=..., surface="inspect")`
   - DocsBrain/operator cards for unfamiliar operator or parameter choices
   - `td_memory_recall` for similar validated techniques

4. Return an exploration brief:
   - target root and likely output TOP/CHOP/COMP
   - existing structure and naming constraints
   - relevant errors/warnings
   - available operator families
   - docs/hints/memory evidence
   - whether `td_brain_plan` has enough facts or needs user clarification

## Stop Conditions

Stop and ask or inspect more when:

- The active network pane and requested target root disagree.
- Multiple plausible output nodes exist.
- Required operators are unavailable.
- Existing errors could make validation misleading.
- A requested visual payload would be large and the user has not approved it.

## Pressure Scenarios

- Pressure: The user asks to build immediately in an unfamiliar project. Stay read-only and return enough state for `td_brain_plan` instead of mutating.
- Pressure: Focus, selected nodes, and the requested root point to different places. Report the ambiguity and gather one more concrete fact before planning.

## Common Mistakes

- Treating memory recall or hints as live-state evidence.
- Inspecting only screenshots while ignoring TD errors, cook health, and operator families.
- Returning a build recommendation without naming the target root, output candidate, and blocking uncertainty.
