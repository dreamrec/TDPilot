---
description: Read-only annotated tour of your existing TouchDesigner project — architecture, signal flow, problems, and quick wins
---

Give the user a clear, honest map of the TouchDesigner project they already
have open. This is strictly read-only — do not create, modify, or delete
anything.

1. **Verify the connection** with `td_get_info` (project name, build, FPS).
2. **Audit.** Call `td_audit_project` for the structural overview, then
   `td_get_nodes` on `/project1` (and the 2-3 largest child COMPs) to map the
   real network. Use `td_get_errors` recursively for problems and
   `td_cooking_info` for the performance hot spots.
3. **Identify the spine.** Find the main signal path(s): sources → processing
   → output (final TOP / output window). Note dead ends and orphaned nodes.
4. **Report** in this shape, concise and jargon-light:
   - **What this project is:** one-paragraph read of its purpose and style.
   - **Signal flow:** the main chain(s), named node by node.
   - **Problems found:** errors, warnings, broken references — each with the
     one-line fix.
   - **Performance:** the top cook-time offenders and whether they matter at
     the project's FPS.
   - **Three quick wins:** concrete, small improvements you could make on
     request (each one tool call away — but do NOT do them now).
5. **Offer next steps:** "want me to fix any of these?" plus `/td-snapshot`
   before any edits.

If the project is empty or nearly empty, say so and point to `/td-first-wow`
instead of padding an empty audit.
