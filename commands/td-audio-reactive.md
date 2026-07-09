---
description: Build an audio-reactive visual chain in TouchDesigner — audio analysis driving live visuals, verified with a screenshot
---

Build an audio-reactive visual network in the user's TouchDesigner project and
prove it reacts. Do every step, verify every step, finish with a screenshot.

1. **Verify the connection** with `td_get_info` (on auth/connection failure,
   follow the error envelope's recovery steps and stop).
2. **Ask nothing you can discover.** If the user gave an audio source (file
   path, mic), use it; otherwise default to the audio-file route and say the
   user can swap the source afterwards.
3. **Inspect the macro schema** with `td_get_macro_params`
   `macro_type="audio_reactive"` — use the template's real parameter names,
   never guessed ones.
4. **Build it** with `td_create_macro` `macro_type="audio_reactive"` in
   `/project1`, overriding 2-3 params for a strong default look (clear beat
   response, readable motion). If the user supplied an audio file path, set it
   via `td_set_params` on the created audio-in operator (file-path params are
   safe to set through tools).
5. **Check errors** with `td_get_errors` on `/project1` and fix anything
   before continuing. Common trap: no audio device / missing file → the CHOP
   chain cooks but outputs silence; check the analysis CHOP actually carries
   non-zero channels via `td_chop_data` before declaring success.
6. **Verify visually.** `td_screenshot` the output TOP at `quality=0.25`.
   For reactivity proof, take two screenshots a moment apart — if the frames
   are identical and audio is playing, debug the chain (export/bind from the
   analysis CHOP to the visual parameters) before presenting.
7. **Present.** Show the screenshot(s), explain the signal path in one
   paragraph (audio in → analysis → parameter binding → visual), name the 2-3
   parameters the user should play with live, and how to undo.

Quality bar: this is a first impression, not a stress test — favor a chain
that visibly pulses with the music over a complex one that might break.
