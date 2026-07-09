---
description: Build your first moving visual in TouchDesigner — a guided 2-minute demo that proves the whole TDPilot loop works
---

Build the user's first moving TouchDesigner visual, end to end, and show them
the result. This is a guided recipe — do every step, verify every step, and
finish with a screenshot in the conversation. Target: under 2 minutes.

1. **Verify the connection.** Call `td_get_info`. If it fails with an auth or
   connection error, follow the error envelope's troubleshooting steps
   (`td_sync_diagnose` first) and tell the user exactly what to fix — do not
   continue blind.
2. **Inspect the macro schema.** Call `td_get_macro_params` with
   `macro_type="feedback_loop"` so you know the template's real parameter
   names and defaults — do not guess parameter names from memory.
3. **Build it.** Call `td_create_macro` with `macro_type="feedback_loop"`,
   `parent_path="/project1"`, a friendly `name`, and 2-3 tasteful `params`
   overrides from the schema you just read (favor: visible motion, saturated
   color, medium feedback decay — nothing epileptic).
4. **Check for errors.** Call `td_get_errors` on `/project1`. If anything
   errors, fix it before proceeding — a broken first demo is worse than a
   slow one.
5. **Verify visually.** Call `td_screenshot` on the macro's output TOP with
   `quality=0.25` (thumbnail is enough to verify). Confirm the render is not
   black/empty. If it is black, debug (display flag, cook state, resolution)
   and re-screenshot — never present an unverified result.
6. **Present.** Show the screenshot, tell the user which nodes were created
   and where, and offer the two natural next steps: "make it audio-reactive"
   (`/td-audio-reactive`) and "explain what you built" — plus how to undo
   everything (the created macro container can be deleted in one call, and
   snapshots exist via `/td-snapshot`).

If TouchDesigner is not running or has no project open, say so plainly and
give the one-line fix (open TD, then re-run `/td-first-wow`).
