---
description: Create a safety snapshot of the current scene before destructive changes
---

Use `td_snapshot_scene` to create a named snapshot of the current TouchDesigner
state. This captures node structure, parameters, and content so the scene can be
restored with `td_restore_snapshot` if a subsequent edit goes wrong.

Recommended workflow:
1. Name the snapshot something descriptive (e.g. "pre-refactor", "before-param-bounds").
2. Confirm via `td_list_snapshots` that it was written.
3. Proceed with the edit.
4. If the edit is bad, call `td_restore_snapshot` with that name.

This is cheaper than saving the .toe file and does not block the TD UI.
