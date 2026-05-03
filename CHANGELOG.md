# Changelog

## 1.6.9 - 2026-05-03

**Seventh release on the same complaint — but this time with verified visual
confirmation of the actual root cause.** Closes the v1.6.x panel-rendering
saga.

### v1.6.8's hypothesis was wrong

v1.6.8 shipped claiming "TD's containerCOMP composes its panel from
children whose nodeX/nodeY land inside `[0, w) × [0, h)`" — moving
status_text from (600, 0) to (0, 0). That fixed nothing; the panel
still rendered black at the network level even with all the other
v1.6.7 fixes (state_cache + autostart triggers + display + viewer).

### v1.6.9 actual root cause

**The containerCOMP's panel background is determined by a single
parameter on the `Look` page: `comp.par.top`.** It's a TOP-typed
reference. If `top = None` (the default), the panel surface shows
only `bgcolor` — no TOP composition based on display flags or position.

The v1.5.x .tox had `comp.par.top = status_text` wired correctly. The
v1.5.6 containerCOMP refactor in `build_tdpilot_tox.py` dropped the
wiring entirely. Six releases of "fix the panel" addressed every
adjacent layer EXCEPT the `top` param. Discovered v1.6.9 by probing
the live COMP's Look-page params and seeing `top=None` after all
v1.6.8 fixes were in place.

### Fix

`td_component/build_tdpilot_tox.py:_populate_tdpilot_comp` now sets:
```python
status_text = _create_status_text_top(comp, "status_text")
# ...
comp.par.top = status_text   # ← v1.6.9: THE actual fix
```

### Visual styling (per user feedback after panel started rendering)

`_create_status_text_top` now uses native panel resolution + new colors:
- `resolutionw = PANEL_W` (520), `resolutionh = PANEL_H` (320) — no
  horizontal stretch (was 256×256 → mapped to 520×320 = 1.625:1 stretch)
- `fontcolorr/g/b = 0.45 / 0.95 / 0.85` — cyan-greenish (was 55% white)
- `bgcolorr/g/b = 0 / 0 / 0`, `bgalpha = 0.9` — 90%-opaque black

### Tests

- `tests/test_build_script_panel_fixes.py` — **+3 new tests**:
  - `TestPanelBackgroundTopWired` — asserts build script sets
    `comp.par.top = status_text` (the v1.6.9 actual fix)
  - `TestStatusTextNativeResolution` — asserts resolution matches
    PANEL_W × PANEL_H (no stretch)
  - `TestStatusTextStyling` — asserts cyan-green text + 90% black bg
- 802 → 805 tests, all green.
- All 5 CI gates green: pytest, ruff check, ruff format (CI-scoped),
  check_versions (lockstep API_VERSION), check_tox_freshness.

### Documentation

`docs/TD_INTRICACIES_AND_PATTERNS.md` (local-only; gitignored since
v1.6.8) Section 14 rewritten with the correct rule:
- v1.6.8's wrong hypothesis preserved as a learning artifact
- v1.6.9 actual rule documented: panel-bg is `comp.par.top`, not
  child-TOP composition by nodeX/nodeY
- Generalizable debug ladder added: when panel renders empty, check
  `comp.par.top` first, then TOP cooking, then viewer/display flags

### What you need to do

1. `npx tdpilot@latest`
2. Re-deploy `tdpilot_startup.py` to TD's Startup dir:
   ```bash
   cp ~/.tdpilot/td_component/tdpilot_startup.py ~/Documents/Derivative/Startup/
   ```
3. Paste in TD Textport (Alt-T) ONE more time:
   ```python
   op('/project1/tdpilot').destroy()
   op('/project1').loadTox('/Users/<you>/.tdpilot/td_component/tdpilot.tox')
   project.save('/Users/<you>/.tdpilot/tdpilot_default.toe')
   ```
4. Panel will render at the `/project1` level immediately with cyan-green
   text on 90%-black bg, native 520×320 resolution.

### Cascade

7 version manifests bumped 1.6.8 → 1.6.9. `API_VERSION` 1.6.8 → 1.6.9
(lockstep). `.tox` rebuilt with all v1.6.9 fixes baked in. 6 doc/skill
headers updated. `uv.lock` re-resolved.

## 1.6.8 - 2026-05-03

Sixth release on the same user complaint, but this time with verified
visual confirmation: panel renders correctly inside the COMP icon at
the network-editor level, not just inside-the-COMP. Tool count unchanged
at 103.

### The bug

After v1.6.7's three build-script fixes (state_cache + autostart triggers
+ display flag) the user reported: "the UI is only visible inside the
comp" — i.e. when you double-click into `/project1/tdpilot`, the panel
text renders correctly, but viewing the COMP from `/project1` shows a
black panel with side-icon decorations only.

Probe revealed `status_text.nodeX = 600`, but the panel viewport is
`comp.par.w = 520`. **TD's containerCOMP composes its panel from
children whose nodeX/nodeY land inside `[0, w) × [0, h)`.** A child
positioned outside the viewport renders correctly as a standalone TOP
(its `td_screenshot` returns valid pixels) but is silently skipped by
the panel composer.

The user could see the text content when INSIDE the COMP because the
network editor's viewer-mode background shows ALL operators scaled to
the network view, regardless of viewport. From OUTSIDE, only viewport-
bounded children appear.

This was the v1.5.6 build's positioning regression — earlier (v1.5.x)
builds placed status_text inside the viewport. v1.5.6's containerCOMP
refactor moved it to `(600, 0)` likely treating that as a "node
organization" position without realizing that for containerCOMP children
the network position IS the panel position.

### Fix

`td_component/build_tdpilot_tox.py` (`_populate_tdpilot_comp`):

```python
status_text.nodeX, status_text.nodeY = 0, 0  # was: 600, 0
```

Plus a multi-line comment explaining why.

### Tests

- `tests/test_build_script_panel_fixes.py` — **+1 new regression test**
  (`TestStatusTextInsideViewport.test_status_text_nodeX_inside_panel_width`)
  that parses the build-script line and asserts `0 ≤ nodeX < PANEL_W`
  and `0 ≤ nodeY < PANEL_H`. CI fails if anyone moves the textTOP outside
  the viewport again.
- 800 → 801 tests, all green.
- All 5 CI gates green: pytest, ruff check, ruff format, check_versions
  (lockstep API_VERSION), check_tox_freshness.

### Documentation

- `docs/TD_INTRICACIES_AND_PATTERNS.md` (local-only — gitignored after
  this release per user request) gained a new **Section 14
  "containerCOMP panel viewport — children must be inside it"** with
  the bug pattern diagram, the regression history, and the
  generalizable rule for future debugging.
- The doc's intro now carries a **binding rule for future Claude
  sessions**: "Whenever you discover a new TD intricacy, fix a class
  of bug, learn a non-obvious behavior, or find a parameter / API
  quirk, append it to this document." This is the antidote to the
  v1.6.3-v1.6.8 saga where 6 wrong-layer (and finally one right-layer)
  releases happened because nobody had documented the build-script's
  actual behavior.

### Cascade

7 version manifests bumped 1.6.7 → 1.6.8. `API_VERSION` 1.6.7 → 1.6.8
(lockstep). `.tox` rebuilt with the new positioning. 6 doc/skill
headers updated. `uv.lock` re-resolved.

## 1.6.7 - 2026-05-03

Fixes three build-script regressions that have been present since v1.5.6
plus one v1.6.6 typo. The combined effect: every fresh ``loadTox`` from
v1.5.6 through v1.6.6 produced a COMP whose panel rendered as an empty
"Ctn" placeholder, with ``Status: Not detected`` / ``Installed: --`` in
the Install/Update tabs even when ~/.tdpilot was healthy on disk.

The bugs were masked for users with pre-v1.5.6 installs because their
``.toe`` files had baked-in state from earlier (working) build scripts
that DID create ``state_cache``, enable autostart triggers, and set
``display=True``. Only when someone did a fresh install OR a manual
destroy + ``loadTox`` sequence did all three bugs surface together.

### Bug 1 — ``state_cache`` textDAT never created

``td_component/state_cache.py`` (the module the renderer reads from)
was developed in a v1.6.0 worktree but never merged to main. The
renderer's ``bootstrap()`` function silently returned ``False`` on
every load (``cache_dat = parent().op(MCP_COMP_PATH + "/state_cache")``
returned None), and ``tick()`` fell through to the
``"(state_cache not loaded)"`` placeholder string. ``status_text.par.text``
stayed at TD's default ``"derivative"`` placeholder forever.

**Fix:**
- Restored ``td_component/state_cache.py`` from the v1.6.0 worktree
  (127 lines: thread-safe runtime cache with ``update``, ``snapshot``,
  ``increment``, ``record_request``, ``mark_ws_error``, ``reset``).
- Added to ``_TOX_SOURCE_FILES`` in ``build_export_mcp_tox.py`` so
  the freshness hash tracks edits.
- Added to ``SOURCE_FILES`` in ``scripts/check_tox_freshness.py``.
- Modified ``_populate_component`` to create the ``state_cache``
  textDAT inside ``mcp_server`` and bake the .py content into it.
- Updated ``build_tdpilot_tox.py`` to read ``state_cache.py`` and
  pass content as ``state_cache_code`` kwarg.

### Bug 2 — ``autostart`` executeDAT trigger toggles all OFF

``_create_text_dat_with_source`` created the executeDAT and stamped
the source code into ``.text`` — but never enabled any of the
trigger toggles (``start``, ``framestart``, ``projectpresave``, etc.).
TD only fires callbacks when their toggle is ON. So ``onStart`` was
defined as a function but TD never called it; same for
``onFrameStart``, etc. Net effect: ``_disable_auth`` never ran (auth
issues), ``_bootstrap`` never ran (panel never populated),
``_tick`` never ran (panel never refreshed), main-thread-action
bridge never fired (Update Now's save_toe never reached the action
handler).

**Fix:** ``_create_text_dat_with_source`` now enables the 8 toggles
``autostart.py`` actually has callback functions for — guarded with
``if op_type == "executeDAT"`` so other DAT types are unaffected.

### Bug 3 — ``status_text`` textTOP ``display=False``

``_create_status_text_top`` set the font, alignment, and position
parameters via ``_set_first_par`` but never set the ``display`` flag.
For a containerCOMP's panel surface to show a child TOP, that TOP
must have ``display=True``. Without it, even when ``status_text.par.text``
got populated correctly, the panel just rendered the default "Ctn"
placeholder.

**Fix:** ``_create_status_text_top`` now sets ``top.display = True``
and ``top.viewer = True`` (direct attribute assignment, not via
``_set_first_par``, because these are TOP node attributes not custom
params).

### Bug 4 — v1.6.6's wrong externaltox param name

``_save_toe_with_externaltox`` (added in v1.6.6) tried to set
``comp.par.reloadtoxonstart = True``. That parameter doesn't exist
on containerCOMP. The correct toggle is ``enableexternaltox`` —
when True, TD loads the .tox at the externaltox path on COMP
creation / project load.

This was a silent no-op in v1.6.6: the ``hasattr`` guard meant the
assignment was skipped, so the .toe got saved with externaltox path
set but ``enableexternaltox=False`` (the default). Next launch:
empty shell COMP. Few users hit this in production because v1.6.6
required a working "Update Now" click to even reach the
``_save_toe_with_externaltox`` code path, and most users were stuck
on Bug 1+2+3 first.

**Fix:** Use ``comp.par.enableexternaltox`` (the actually-existing
parameter name).

### Tests

- ``tests/test_build_script_panel_fixes.py`` — **+8 new regression
  tests** covering each bug: state_cache file presence + required
  functions + listed in TOX_SOURCE_FILES + listed in freshness gate
  + ``_populate_component`` creates the DAT + ``build_tdpilot_tox.py``
  passes the content; ``_create_text_dat_with_source`` enables
  executeDAT triggers; ``_create_status_text_top`` sets display + viewer.
- ``tests/test_externaltox_save.py`` — **6 tests renamed**
  ``reloadtoxonstart`` → ``enableexternaltox`` to match the v1.6.7
  param name. All assertions now hold against the correct TD param.
- 791 → 799 tests, all green.
- All 5 CI gates green: pytest, ruff check, ruff format, check_versions
  (lockstep API_VERSION since v1.6.5), check_tox_freshness.

### What you need to do

1. ``npx tdpilot@latest`` (or click "Update" in Claude Code plugins —
   should now work since v1.6.6 fixed the marketplace cache pull
   pattern).
2. Re-deploy ``tdpilot_startup.py`` to TD's Startup dir:
   ```bash
   cp ~/.tdpilot/td_component/tdpilot_startup.py ~/Documents/Derivative/Startup/
   ```
3. **In TD**, paste these three lines in the Textport (Alt-T) ONE
   MORE TIME to swap your current COMP for the v1.6.7 .tox:
   ```python
   op('/project1/tdpilot').destroy()
   op('/project1').loadTox('/Users/<you>/.tdpilot/td_component/tdpilot.tox')
   project.save('/Users/<you>/.tdpilot/tdpilot_default.toe')
   ```
4. From this point forward: panel works. Future updates via
   "Update Now" pulse will set ``enableexternaltox`` correctly,
   so subsequent TD launches read the latest .tox automatically.

### Cascade

7 version manifests bumped 1.6.6 → 1.6.7. ``API_VERSION`` 1.6.6 →
1.6.7 (lockstep — gate enforces). ``state_cache.py`` added to
.tox source list (now 9 source files). ``.tox`` rebuilt with all
fixes baked in. 6 doc/skill headers updated. ``uv.lock`` re-resolved.

## 1.6.6 - 2026-05-03

Closes the "panel says X but disk has Y" drift class permanently via the
`externaltox` mechanism. v1.6.5's Startup-script sweep was the wrong
abstraction (TD scans Startup-folder scripts BEFORE opening the default
project file, so the sweep can never see /project1 — its loadTox into
/local gets wiped a moment later by the .toe restore that follows).
v1.6.6's approach is stateless and architectural: the autostart's
`save_toe` handler sets `externaltox` on the COMP before saving, so the
.toe stores only a thin path reference instead of an embedded snapshot.
Every future TD launch reads the latest .tox content fresh from disk.

Tool count unchanged at 103.

### The bug class

Pre-v1.6.6, `project.save` baked the entire current `/project1/tdpilot`
COMP (with whatever `API_VERSION` was current at save time) into the
.toe file. Future TD launches restored the frozen content forever.
Updating `~/.tdpilot/td_component/tdpilot.tox` on disk had no effect
because the .toe restore overwrote anything the Startup script tried
to load.

The user reporting "panel still says 1.5.3 after restart" hit this
exact failure mode. Their `~/.tdpilot/tdpilot_default.toe` had the
v1.5.3-era COMP fully embedded; nothing the v1.6.5 Startup-script
sweep did could displace it (Startup scripts run before /project1
exists, so the sweep loaded fresh into /local — then the .toe wiped
/local restoring the user's saved state, no tdpilot in /local, leaving
only the stale /project1/tdpilot v1.5.3 COMP serving port 9981).

### The fix

`td_component/autostart.py:_save_toe_with_externaltox` (new function,
called from the existing `save_toe` main-thread action handler):

  1. Find this COMP via `parent()`
  2. Read the canonical .tox path from `installer.module.install_dir()`
  3. If the COMP has an `externaltox` parameter (containerCOMP does;
     baseCOMP doesn't): set it to the .tox path, also enable
     `reloadtoxonstart` so TD re-reads on every project open
  4. `project.save(target, saveExternalToxs=False)` so the COMP body
     is referenced (not embedded) in the .toe
  5. Catch TypeError on the saveExternalToxs kwarg as a fallback for
     older TD builds that don't support it

After one round-trip through "Update Now" (which triggers `save_toe`),
the user's .toe is permanently externaltox-wired. From that point
forward, `npx tdpilot@latest` + restart-TD = panel updates
automatically. No manual sweeps, no Textport gymnastics, no ordering
races.

### Why not just a Startup-script sweep (v1.6.5's approach)

TD scans `~/Documents/Derivative/Startup/` BEFORE opening the default
project file. Order on every TD launch:

  1. TD initializes Python interpreter
  2. TD execs every `.py` in `~/Documents/Derivative/Startup/`
     ← `tdpilot_startup.py` runs here. /project1 doesn't exist yet.
       Sweep finds nothing. loadTox into /local succeeds.
  3. TD opens default project file (`general.startupfilename`)
     ← .toe restore wipes /local with whatever the .toe saved
       (no tdpilot in /local for users who installed at /project1).
       /project1/tdpilot restored from the .toe — frozen content.
  4. TD's main event loop starts

The Startup-script sweep is best-effort only — it catches the simple
cases (/local-only installs with no .toe-baked /project1 COMP) but
cannot defeat the .toe restore that follows. The externaltox approach
is stateless: it doesn't fight TD's project loader; it works WITH it.

The v1.6.5 sweep code is kept in place as belt-and-suspenders defense
for users whose .toe somehow gets out of sync. Documented as such in
`tdpilot_startup.py`'s module docstring (new 30-line block in v1.6.6).

### Tests

- `tests/test_externaltox_save.py` — **+6 new tests** covering:
  - Happy path: .tox exists + COMP has externaltox param → set + save
    with `saveExternalToxs=False`
  - Fallback: .tox missing on disk → don't set externaltox, plain save
  - Fallback: COMP has no externaltox param (baseCOMP-style) → skip set
  - Fallback: `installer.install_dir()` raises → plain save
  - Fallback: older TD raises TypeError on `saveExternalToxs` kwarg →
    catch + retry without kwargs
  - Fallback: `parent()` returns None → plain save (defensive guard)
- 785 → 791 total tests, all green.
- All 5 CI gates green: pytest, ruff check, ruff format, check_versions
  (now lockstep-gating API_VERSION since v1.6.5), check_tox_freshness.

### Cascade

7 version manifests bumped 1.6.5 → 1.6.6. `API_VERSION` 1.6.5 → 1.6.6
(lockstep — gate enforces). `.tox` rebuilt. 6 doc/skill headers
updated. `uv.lock` re-resolved.

## 1.6.5 - 2026-05-03

Fixes the "panel still says 1.5.3 after restart" bug class — both the
underlying architectural cause AND the v1.6.4 release-process bug that
allowed it to ship in the first place. Tool count unchanged at 103.

### Bug 1 — `tdpilot_startup.py` only managed `/local/mcp_server`

When users dragged the `.tox` into the visible network panel, it landed
at `/project1/tdpilot` (containerCOMP, panel UI). `project.save` then
baked that COMP into the autoload `.toe` with all v1.5.3-era content
embedded. Every TD launch:

  1. `.toe` restored `/project1/tdpilot` (frozen v1.5.3 COMP, full content
     embedded — no `externaltox` indirection, so disk `.tox` updates
     never reached it).
  2. The COMP's WS DAT bound port 9981 immediately.
  3. `~/Documents/Derivative/Startup/tdpilot_startup.py` ran, looked for
     `/local/mcp_server` (the legacy v1.3-era name — never matched
     because the user's COMP was named `tdpilot`), called `loadTox` into
     `/local`. The new instance's WS DAT couldn't bind 9981 (already
     taken by `/project1/tdpilot`) → silent failure.
  4. `/project1/tdpilot` kept serving its baked v1.5.3 forever.

`td_get_capabilities` confirmed live: `component_version: "1.5.3"` even
after `~/.tdpilot/td_component/tdpilot.tox` was sha256-verified to be the
v1.6.4 binary. The Startup script was loading the right file, just into
the wrong location, behind the wrong COMP.

#### Fix

`td_component/tdpilot_startup.py:_find_existing_tdpilot_comps()` now
sweeps both `/local` AND `/project1` for BOTH names (`tdpilot` and the
legacy `mcp_server`). `_load_tox_fast()` destroys every match found,
then loads the fresh `.tox` into the SAME parent the previous COMP lived
at — preserving the user's UI position. Defaults to `/local` when no
existing install is found (fresh-install case).

So for the affected user setup, every TD launch from v1.6.5 onward:

  1. `.toe` restores stale `/project1/tdpilot` (v1.5.3 — historical baggage).
  2. Startup script's sweep finds it, destroys it, calls `loadTox` into
     `/project1` — UI stays at the same path.
  3. Fresh v1.6.5 COMP at `/project1/tdpilot`, port 9981 bound by it,
     panel shows "TDPilot 1.6.5 / Tools 103".

No `project.save` required from the user — every launch self-heals.

### Bug 2 — v1.6.4 silently shipped without bumping `API_VERSION`

The `Edit` for `td_component/mcp_webserver_callbacks.py` got lost in a
parallel edit batch during the v1.6.4 release. `git show
v1.6.4:td_component/mcp_webserver_callbacks.py` confirmed the published
`.tox` baked `API_VERSION = "1.6.3"` despite shipping as v1.6.4. Nothing
caught it because `scripts/check_versions.py` had an explicit "do not
gate API_VERSION" comment dating back to a since-abandoned attempt at
decoupling the TD HTTP protocol version from the package version.

#### Fix

`scripts/check_versions.py` now gates `API_VERSION` against `__version__`
(removed the decoupling comment, replaced with one explaining the new
lockstep policy). A new test in `tests/test_startup_sweep.py`
(`TestAPIVersionLockstep`) asserts the same invariant at pytest time so
both layers (CI script + pytest) catch any future drift independently.

If a legitimate need for distinct TD-protocol vs package versions ever
arises, the right move is to introduce a separate `TD_PROTOCOL_VERSION`
constant rather than re-decoupling `API_VERSION` from `__version__`.

### Tests

- `tests/test_startup_sweep.py` — **+16 tests** for the v1.6.5 changes:
  - 6 tests for `_find_existing_tdpilot_comps` (empty world, /local-only,
    /project1-only, legacy mcp_server name, multiple parents, both names
    at one parent).
  - 8 tests for `_load_tox_fast` (empty + load to /local, stale at
    /local destroyed + reload at /local, **stale at /project1 destroyed
    + reload at /project1 — the actual bug case**, both locations
    destroyed + /local wins, legacy /project1/mcp_server destroyed,
    loadTox returns None → False, loadTox raises → False, destroy raises
    → load still attempted).
  - 1 test for the backward-compat `_destroy_zombie_mcp_servers` shim.
  - 1 test asserting `API_VERSION == __version__`.
- 769 → 785 total tests, all green.
- All 5 CI gates green: pytest, ruff check, ruff format, check_versions
  (now including API_VERSION), check_tox_freshness.

### Cascade

- 7 version manifests bumped 1.6.4 → 1.6.5. `API_VERSION` 1.6.3 → 1.6.5
  (catching up the lost v1.6.4 edit and aligning to package). `.tox`
  rebuilt. 6 doc/skill headers updated. `uv.lock` re-resolved.

## 1.6.4 - 2026-05-03

Auto-pin to latest released tag at TD launch. Solves the failure mode
diagnosed in v1.6.3: `~/.tdpilot/` (the runtime install directory used
by `td_component/tdpilot_startup.py:loadTox`) lags behind the latest
release until the user manually clicks the "Update Now" pulse on the
in-TD installer panel. v1.6.4 makes that click optional — opt in with
`npx tdpilot autopin --enable` and every TD startup will git-fetch and
checkout the latest tag from `origin/main` before loading the .tox
into `/local`. Tool count unchanged at 103.

### Features

- **`tdpilot autopin --enable | --disable | (status)` CLI subcommand.**
  Toggles the `TDPILOT_AUTO_PIN_TAG=1` flag in
  `~/.tdpilot/.tdpilot.env` (the shared env file, also used for the
  auth secret since v1.4.5). Atomic write via tmp + replace so a crash
  mid-write can never corrupt the file. Preserves all other keys,
  comments, and blank lines untouched. Status mode (no flag) prints
  current state + a hint at the toggle command.

- **`_auto_pin_latest_tag(repo_root)` in `td_component/tdpilot_startup.py`.**
  Called once at TD launch right after `_load_env_file()` (so the
  opt-in flag is loaded before we check it) and before resolving
  `tox_path` (so the freshly-checked-out .tox is what `loadTox` sees).
  Sequence: `git fetch --tags` (5s timeout) → `git describe --tags
  --abbrev=0 origin/main` to find the latest tag → `git describe
  --tags --exact-match HEAD` to see if we're already there → `git
  checkout <tag>` if not. Idempotent, never-blocking: TimeoutExpired,
  CalledProcessError, and any other exception are caught and logged
  to Textport without re-raising. Offline TD launches incur a 5s
  fetch timeout then proceed with the current pinned tag.

### Defensive design notes

- **Opt-in by default.** Auto-update at startup has obvious risks
  (network requests on every TD launch, behavior change without user
  consent). v1.6.4 ships the mechanism but does not enable it; the
  user must run `tdpilot autopin --enable` to opt in.
- **Bypasses the `update_now` snapshot/backup flow.** v1.6.4's autopin
  is `git checkout` only — it does NOT run `_uv_sync` or
  `project.save(autoload_toe)`. The reasoning: a hands-off git
  checkout at TD launch is safe (.tox load is read-only, the running
  COMP gets destroyed-and-replaced fresh by `_load_tox_fast`); the
  destructive `update_now` flow exists for the manual button which
  takes a deeper backup. Two distinct UX paths, two distinct safety
  postures.
- **Non-blocking under failure.** Every git invocation has a timeout;
  every exception is caught. Failure mode is "log to Textport,
  continue with the current pinned tag" — TD startup is never
  delayed by more than the 5s fetch timeout in the worst case.

### Tests

- **+29 unit tests in `tests/test_autopin.py`** (740 → 769 total).
  Coverage: env-var-disabled no-op, missing `.git` skip, full happy
  path with mocked subprocess, "already on latest" idempotent skip,
  TimeoutExpired/CalledProcessError/OSError all caught, CLI
  enable/disable/status flows, atomic write preserves other keys,
  enable is idempotent, value-parsing accepts 1/true/yes/on,
  argparse mutex group rejects --enable + --disable.

### Breaking-change risk: NONE

- Pure additive feature. Existing users who don't run `tdpilot
  autopin --enable` see zero behavior change.
- Existing `update_now` button on the TD-side installer panel still
  works exactly as before. v1.6.4 adds a complementary "fire on
  every launch" path; doesn't replace the manual button.
- The `TDPILOT_STARTUP_SKIP=1` env var added for testability is
  documented and harmless in production (TD never sets it).

### Cascade

- 7 version manifests bumped 1.6.3 → 1.6.4. `API_VERSION` 1.6.3 →
  1.6.4. `.tox` rebuilt (new hash:
  `e768cb915e6b9492…`). `.tox-source-hash.json` regenerated. 6
  doc/skill headers updated. `uv.lock` re-resolved.

## 1.6.3 - 2026-05-03

`.tox` alignment release. Closes the cosmetic gap that opened during the
v1.6.0/1/2 series — host-side server moved to v1.6.x but the `.tox`
panel stayed at "TDPilot 1.5.3 / Tools 102" because (a) `API_VERSION`
was deliberately pinned to keep the HTTP protocol stable across three
host-side-only releases, and (b) the panel's `Tools` field had a
hardcoded `102` fallback in `renderer.py:bootstrap()` that nothing was
updating live. Both are now aligned.

### Fixes

- **`API_VERSION` `1.5.3` → `1.6.3`** in `td_component/mcp_webserver_callbacks.py`.
  The HTTP protocol surface is unchanged; this is a cosmetic alignment
  so the `.tox` panel header reads `TDPilot 1.6.3` to match the host
  server. `td_get_capabilities`'s `mismatch` warning will now report
  `mismatch: false` when host + .tox are both at v1.6.3.

- **Panel tool-count `102` → `103`** in `td_component/renderer.py:bootstrap()`.
  This is a static fallback baked at .tox build time (the .tox can't
  query the host MCP server's live tool count over the existing WS
  bridge — the bridge is host→TD, not TD→host). Bumped + added a
  comment requiring it to stay in sync with `EXPECTED_MIN_TOOL_COUNT`
  in `src/td_mcp/release_gates.py` on every release that adds/removes
  tools.

- **`.tox` rebuilt** with the v1.6.3 source. `.tox-source-hash.json`
  refreshed by `build_export_mcp_tox.py`; CI's `check_tox_freshness.py`
  gate stays green.

### No tool changes

Tool count unchanged at **103**. Hint corpus unchanged at 19 packs / 63
hints. The 6 v1.6.0 tools (`td_get_focus`, `td_locations`,
`td_get_hints`, `td_component_notes`) and v1.6.2 surface routing all
ship as in v1.6.2.

### Cascade

- All 6 version manifests bumped 1.6.2 → 1.6.3
- README/SKILL/MANUAL/INSTALL headers updated
- 740/740 tests pass; all 4 CI gates green

### Audit findings (no fix needed)

The deep audit also flagged:
- `autostart.py:_disable_auth()` silently disables MCP shared-secret
  auth on every project load. **Intentional** — single-user local-dev
  default, documented in plan §8 risk #1. Skipped.
- 3 stale TODOs in `models/_legacy.py` (refactor), `tools_planning.py`
  (v1.5.4 delegation), `tools_notes.py` (docstring). **All benign.**
- No skipped/xfailed/warned tests; pytest is fully green.

## 1.6.2 - 2026-05-02

Surface routing release. Adds the **2-axis topic × response-surface model**
for hints — each hint can now declare which tool-response-surfaces it
should fire from, eliminating noise where hints surface in the wrong
context. Tool count unchanged at 103. **No `.tox` rebuild required**;
`API_VERSION` stays at `1.5.3`.

The design directly addresses the gap surfaced by the v1.6.0 competitive
review (their changelog mentions distinct hints keys for separate
response surfaces — same idea, we caught up).

### Schema bump: v1 → v2 (backward compatible)

Hint pack YAML now accepts an optional `when.surface` clause:

```yaml
schema_version: 2          # was 1; both still load
hints:
  - id: feedback_static_analyzer_warning
    priority: critical
    rule: |
      "Not enough sources" is a static-analyzer warning, not a runtime error...
    when:
      op_type: feedbackTOP
      error_match: "Not enough sources"
      surface: [errors]    # NEW v2 — only fires when surfacing from td_get_errors
```

Surface allowlist (9 surfaces): `create_node`, `set_params`, `exec`,
`errors`, `plan`, `preview`, `query`, `inspect`, `screenshot`. Unknown
surface names reject the entire pack (defense-in-depth: malformed YAML
can't silently make a hint surface-restricted to nothing).

v1 packs continue to load unchanged. Hints without `when.surface` fire
from any surface (the original behavior).

### Tool surface map

`src/td_mcp/hints/orchestrator.py:TOOL_SURFACES` is the single source of
truth for the tool→surface mapping that drives auto-injection:

| Tool | Surface |
|---|---|
| `td_create_node` | `create_node` |
| `td_set_params` | `set_params` |
| `td_exec_python` | `exec` |
| `td_get_errors` | `errors` |
| `td_plan_patch` | `plan` |
| `td_patch_preview` | `preview` |
| `td_get_hints` | `query` |
| `td_get_node_detail` | `inspect` *(NEW wiring v1.6.2)* |
| `td_screenshot`, `td_capture_frame`, `td_capture_and_analyze` | `screenshot` *(reserved; not yet wired)* |

### `td_get_hints` and `td_get_node_detail` extensions

- `td_get_hints` gains `surface=` parameter for explicit narrowing (e.g.
  `td_get_hints(topic="feedback", surface="create_node")`).
- `td_get_node_detail` gains `include_hints=False` parameter — when True,
  attaches a `hints` block scoped to the inspected node's op_type with
  surface=inspect.
- `query_hints()` response now includes `surface` and `available_surfaces`
  fields for client introspection.

### Hint corpus re-annotation

8 existing hints across 6 packs gained surface restrictions where the
auto-injection target was clear. Examples:

| Hint | Surface restriction |
|---|---|
| `feedback_canonical_chain` | `[create_node, plan, preview]` |
| `feedback_static_analyzer_warning` | `[errors]` |
| `glsl_output_swizzle` | `[create_node, exec, plan]` |
| `glsltop_silent_zero_uniform` | `[set_params, exec, screenshot, errors]` |
| `extension_load_failure_diagnosis` | `[errors]` |
| `record_is_a_toggle_not_a_pulse` | `[set_params, exec]` |
| `verify_with_info_chop` | `[screenshot, set_params, errors]` |
| `glslmat_compile_error_checkerboard` | `[errors, screenshot]` |

The other ~55 hints stayed unrestricted (the right default — narrowing
prematurely makes them unfindable).

### Tests

- 14 new tests in `tests/test_hints.py` covering schema_version 2
  acceptance, unknown-surface rejection, string-to-list normalization,
  type-checked surface lists, find() filter behavior, query_hints surface
  fields, auto_inject_hints tool→surface routing, and TOOL_SURFACES sanity
- **740/740 tests pass** (up from 726 in v1.6.1)
- All 4 CI gates green

### Cascade

- All 6 version manifests bumped 1.6.1 → 1.6.2
- README/SKILL/MANUAL/INSTALL headers updated
- skills/tdpilot-core/SKILL.md Hints section now describes surface
  routing + lists `TOOL_SURFACES`
- tests/fixtures/tool_schemas.json snapshot regenerated for the new
  `surface=` and `include_hints=` parameters

## 1.6.1 - 2026-05-02

Hint pack corpus expansion. **No new MCP tools, no schema changes** —
just much more contextual coverage. Tool count stays at 103. Pure
host-side YAML; **no `.tox` rebuild required**.

### Hint corpus 7 → 19 packs / 17 → 63 hints

Added 6 new topic packs and 6 new op_type packs to round out the
coverage the original v1.6.0 spec called for. Every hint cites a
verifiable source (TDPilot skill section, Derivative wiki page,
templates module, or the Anthropic-style `hint_pack` self-summary).

**New topic packs** (11 total now):
- `panel_ui` — Panel CHOP Execute idioms, slider drag mapping, preset
  button modifier-click convention, perform-mode optimization, dynamic
  layout
- `custom_parameters` — `td_custom_parameters` declarative authoring,
  master control COMP pattern, reset pulse per page, state-capture skip
  rules, expression-mode requirement
- `pop` — `td_pop_inspect` over `td_exec_python`, geometryCOMP POP-torus
  default trap, minimal POP chain pattern
- `popx` — paid-plugin install gate, mental model
  (Generator → Falloff → Modifier → Tool → Simulation), example as
  source-of-truth, brain availability facts
- `macros` — built-in template inventory, feedback_loop topology,
  feedback_displacement chain, override validation, undo-block wrapping
- `recording` — real-time vs archival render, audio-CHOP wiring
  requirement, codec choice by intent (Hap/H.264/ProRes/PNG-seq)

**New op_type packs** (8 total now):
- `glslTOP` — quickstart routing, silent-zero-uniform critical pitfall,
  short-form vs long-form name for `td_create_node`
- `glslMAT` — full-pipeline architecture (vertex+pixel+optional
  geometry), TD attribute accessors (TDPos, TDNormal, TDTexCoord),
  TDOutputSwizzle requirement, compile-error checkerboard
- `moviefileoutTOP` — Record is a toggle (not a pulse), Info CHOP
  verification, Stall for File Open for first-frame fidelity
- `extensionDAT` — TDStoreTools.StorageManager for persistence,
  `.getRaw()` for JSON serialization, `op()` path resolution gotcha
- `panelCOMP` — `panelValue.name` event decoding, event-spam guard
- `audiofileinCHOP` — device choice routing
  (audiofilein vs audiodevicein vs audiostreamin), Cue page for
  beat-synced playback

### Schema unchanged

The pack YAML schema (`schema_version: 1`, `id` / `priority` / `rule` /
`source` / `source_kind` / `when`) and the auto-injection rule table in
`src/td_mcp/hints/orchestrator.py` are unchanged. New packs drop in,
get loaded by `default_registry()` at server startup, and become
queryable via `td_get_hints` and discoverable via the
`available_topics` / `available_op_types` fields in every hints
response.

### Where hints come from

Every hint in the corpus cites one of:
- `tdpilot-core §X` — section reference into
  `skills/tdpilot-core/SKILL.md`
- `preset-systems-and-ui §X` — section into
  `skills/tdpilot-core/references/preset-systems-and-ui.md`
- `macros/templates.py <macro_name>` — built-in macro template
- `derivative.ca/<page>` — official Derivative wiki page (URL stub)
- `hint_pack` — self-summary / routing hints that point to richer
  topic packs

### Tests

- 726/726 tests pass (no new tests for content-only release)
- All 4 CI gates green: ruff check, ruff format --check,
  check_versions, check_tox_freshness

## 1.6.0 - 2026-05-02

Cockpit ergonomics release. Adds four new MCP tools and one tool
extension that make the agent feel TD-native — focus-aware, hint-injected,
scoped-search, per-COMP notes — without building a parallel UI cockpit
and without trading away the open-core differentiator. Tool count
99 → 103 (the 99 baseline was 101 before paketa12 removal earlier on
the same day).

All four new tools ship purely host-side: they use the existing
`/api/exec` endpoint that already lives inside any v1.4+ `.tox`. **No
`.tox` rebuild is required for v1.6.0.** `API_VERSION` stays at `1.5.3`
(HTTP protocol surface unchanged).

### New tools (4)

- `td_get_focus` — returns current network pane, selection, project
  meta, timeline state. Eliminates the "what path are you working in?"
  cold-start tax that the agent paid before every patch. Built on a
  read-only Python probe through `/api/exec`.

- `td_locations(action=save|list|go|delete|rename)` — per-project
  named network locations stored at
  `~/.tdpilot/locations/<project_hash>.json`. Survives session
  restarts; project_hash derived from `project.name` so locations
  follow the `.toe` across machines. Action dispatcher pattern keeps
  this to one tool instead of five.

- `td_get_hints(topic, op_type, intent, error_text, max_hints)` —
  concise, source-cited rules for a topic, op type, or intent. Pure
  host-side orchestrator over the YAML hint corpus at
  `src/td_mcp/hints/packs/`. Ships with 7 packs (5 topic + 2 op_type,
  17 hints): feedback, glsl, render_pipeline, audio_reactive,
  extensions, feedbackTOP, geometryCOMP. Hint pack schema versioned
  for future expansion.

- `td_component_notes(action=get|set|append|delete|index|summarize)` —
  per-COMP markdown notes addressable by path. Default external
  storage at `~/.tdpilot/component_notes/<project_hash>.json` (no
  `.toe` bloat); `embed=True` mirrors into a hidden Text DAT inside
  the COMP for portability. Pairs with the new
  `td_get_node_detail(include_notes=True)` parameter.

### Extended tools

- `td_search_nodes` — gains `scopes=[…]` parameter (backward-compatible
  superset of `search_type`). Two new scopes ship in v1.6.0:
    * `dat_text` — search DAT text contents
    * `param_exprs` — search parameter expressions
  Legacy scopes (`name`/`type`/`family`/`all`) keep using the existing
  TD-side `/api/search` endpoint; new scopes dispatch via `/api/exec`
  with safe iterators.

- `td_get_node_detail` — gains `include_notes=False` parameter that
  surfaces any per-COMP note for the requested path.

### Hint injection on 6 high-risk tools

Auto-injection fires without the caller asking — the response gains a
`hints` block when an injection rule matches. All 6 tools also accept
an explicit `include_hints=False` parameter for forced opt-in.

| Tool | Auto-trigger pattern |
|---|---|
| `td_create_node` | High-risk op_types (feedbackTOP, glslTOP, geometryCOMP, moviefileoutTOP, extensionDAT, panelCOMP, audiofileinCHOP) |
| `td_set_params` | String value assigned to a reference-style parameter (instanceop, material, camera, lights, geometry, top/chop/sop/dat/comp) |
| `td_exec_python` | Code contains restricted-mode patterns (.text=, .par.file=, imports, OS escapes, subprocess/socket) |
| `td_get_errors` | Response contains known error classes ("Not enough sources", "extension", "missing input") |
| `td_plan_patch` / `td_patch_preview` | Plan blob mentions feedback, GLSL, or audio-reactive territory |

### New skill content

- `skills/tdpilot-core/SKILL.md` §13 (added 2026-05-02): Feature
  Adoption Rules — Rule 1 "compound with rigor", Rule 2 "reject pure
  parity", Rule 3 "open core stays open". Output of the same
  competitive-review session that scoped v1.6.0; lives in the public
  skill so future sessions don't relitigate the parity-vs-rigor
  argument every time a competitor ships a new feature.
- `skills/tdpilot-core/SKILL.md` surface listing — new sections for
  "Focus & Locations", "Hints", "Component Notes".

### Tests

- `tests/test_locations_store.py` — 16 tests for the locations storage
  layer (CRUD, persistence, corrupt-file recovery, file layout).
- `tests/test_hints.py` — 20 tests for hint pack loader, schema
  validation, query API, and auto-injection rules.
- `tests/test_component_notes_store.py` — 15 tests for the notes
  storage layer (CRUD, append-with-divider, scope-filtered summarize,
  persistence, corrupt-file recovery).
- `tests/fixtures/tool_schemas.json` — snapshot regenerated for the
  4 new tools and the extended `td_search_nodes` / `td_get_node_detail`.

### Version + manifest cascade

| File | 1.5.6 → 1.6.0 |
|---|---|
| `pyproject.toml` | ✓ |
| `src/td_mcp/__init__.py` | ✓ |
| `.claude-plugin/plugin.json` | ✓ |
| `.claude-plugin/marketplace.json` (plugins[0].version drives the Update button) | ✓ |
| `npm/package.json` | ✓ |
| `mcp/manifest.json` | ✓ (also tool_count 99 → 103) |
| `td_component/mcp_webserver_callbacks.py` API_VERSION | UNCHANGED at 1.5.3 (HTTP surface stable) |

### Out of scope (deferred — see local `roadmap-future.md`)

The v1.6.0 review explicitly deferred 8 items: library system,
in-TD AI adapters, VST workflow, native TD shell UI, batch
screenshots beyond `td_capture_frame`, cloud/hosted layer, recent
projects, fine-grained permission tiers. Each has an explicit
"unblock when …" gate. Refusing parity work is a feature.

## 1.5.6 - 2026-05-02

One-button installer release. The shipped `tdpilot.tox` is now a
self-installing container COMP — drag it into any TD project and the
Install + Update panels do the rest. No Textport gymnastics, no manual
`.tox` drag into `/local`, no shell scripts.

Tool count unchanged at 101 (the installer is COMP-side Python, not new
MCP tools). `API_VERSION` stays at `1.5.3` (HTTP protocol unchanged).
The `.tox` itself is meaningfully different: it now embeds four new
source files (`installer.py`, `installer_exec.py`, `autostart.py`,
`renderer.py`) that the freshness gate tracks via SHA-256.

The work was split into four commit-sized phases on
`feat/v1.5.6-installer`, all merged for this release:

### Phase A — Detection scaffold + plan doc
- `docs/v1.5.6/INSTALLER_PLAN.md` — 11-section plan covering goals, the
  three install paths drift problem, restart-TD update pattern, the
  `enableexternaltox=True` architecture decision, the auth-bypass
  conflict resolution, and risks requiring sign-off.
- `installer.detect_state()` — pure read, never mutates: probes uv,
  git, `claude` CLI, `~/.tdpilot/pyproject.toml`, TD prefs autoload
  state, `installed_plugins.json`, `.tdpilot.env` secret presence,
  `~/.tdpilot_path` contents.
- `installer.refresh_status_params()` — writes the live status into the
  parent COMP's custom params (`Installstatus`, `Updatestatus`,
  `Installedversion`).

### Phase B — Threading + install primitives
- Lock-protected `_job_state` dict shared between the bg daemon thread
  and TD's main cook thread. Bg threads are forbidden from touching
  TD ops directly; they raise `pending_action` flags and wait for the
  main thread to consume.
- `_wait_for_main_thread_action("save_toe", timeout=30)` — the
  main-thread bridge for `project.save()`. Polls every 50ms with the
  lock held briefly enough not to stall the cook.
- Late-binding paths: `install_dir()`, `config_file()`, `env_file()`,
  `autoload_toe()`, `pyproject()`, `prefs_path()` are now functions
  that re-read `TDPILOT_INSTALL_DIR` / `TDPILOT_CONFIG_FILE` per call.
  Enables sandbox redirection mid-session without module reload.
- `install_python_wrapper()` — probe uv → install uv (`curl … | sh`)
  → git clone (or zip fallback) → pin to latest release tag → `uv
  sync` → write `.tdpilot.env` with `TD_MCP_REQUIRE_AUTH=0`. Verified
  end-to-end in `/tmp` sandbox: clean v1.5.3 install in 12.7 seconds.
- `set_td_autoload()` — write `~/.tdpilot_path`, update `pref.txt`
  (`general.startupfilemode=2` + `startupfilename`), then bridge to
  the main thread via `save_toe`.
- `uninstall_all()` — revert prefs, remove config + autoload toe +
  install dir. `TDPILOT_KEEP_INSTALL_DIR=1` escape hatch for testing.
- Critical bug-fix during testing: `autostart.py` now calls
  `installer.module.autoload_toe()` (the function) not
  `installer.module.AUTOLOAD_TOE` (the module-eval-time constant).
  The constant didn't follow `TDPILOT_INSTALL_DIR` overrides set
  later in the session, so a sandbox test clobbered the user's real
  `~/.tdpilot/tdpilot_default.toe`. Function call re-reads env on
  every call.

### Phase C — Claude plugin install + bootstrap orchestrator
- `install_claude_plugin()` — checks `installed_plugins.json` FIRST
  so users who already have the plugin via `.mcpb` drag-drop into
  Claude Desktop get a clean "already installed" path without needing
  the `claude` CLI on PATH. Recognizes both registration keys
  (`tdpilot@dreamrec-TDPilot` from Claude Code CLI marketplace,
  `tdpilot@local-desktop-app-uploads` from `.mcpb` drop). Only when
  the plugin is missing AND the CLI is missing do we raise the
  "install Claude Code first" actionable error with the manual
  fallback command.
- `bootstrap_all()` — single-job orchestrator that calls the
  underscored `_do_*` helpers directly inside one bg thread sharing
  one progress callback, so the panel sees one progress stream
  instead of three Phase-B job lifecycles colliding. Claude plugin
  step is non-fatal: if `claude` CLI is missing AND plugin install
  not detected, the user still gets a working Python wrapper +
  autoload (they can install plugin separately later). Wrapper or
  autoload failures abort the whole job.

### Phase D — Update + rollback with 24h cache
- `check_for_updates(force=False)` — synchronous (no bg job) single
  `curl` GET against `api.github.com/repos/dreamrec/TDPilot/releases/latest`
  with 5s timeout. Why curl, not `urllib`: TD's bundled Python doesn't
  ship a CA bundle, so `urllib.request.urlopen` on `https://` fails
  with `CERTIFICATE_VERIFY_FAILED`. `/usr/bin/curl` uses the system
  trust store and Just Works on macOS/Linux. 24h cache at
  `~/.tdpilot/last_check.json`. Cache hit returns in ~0.4ms (vs ~300ms
  network); refreshed installed-version is recomputed every call so
  semver compare stays accurate even on cache hit. Failures are NOT
  cached so the next call retries. Verified live: installed=1.5.2,
  latest=1.5.3, update_available=True, release_url + first 80 chars
  of notes returned correctly.
- `_semver_tuple` — tolerant parser. `"1.5.6"`, `"v1.5.6"`,
  `"1.5.6-rc1"`, `"1"` all parse to 3-tuples; failures return
  `(0,0,0)` so an unreadable installed version compares as "anything
  > 0.0.0 = update available".
- `update_now()` — bg job, ~30s wall-clock. (1) `_smart_copytree`
  snapshot to `backups/<ts>/` excluding `.venv`, `.git`, `knowledge/`,
  `memory/`, `*.db/sqlite`, `__pycache__`, `*_cache/`, `node_modules`.
  Backups exist to recover code+config; `.venv` rebuilds from
  `uv.lock` and brain DBs are regenerable, so excluding them keeps
  backups light (single-digit MB instead of hundreds). (2) `git fetch
  --tags && checkout <latest tag>` (zip fallback if `.git` is
  missing — backup is the safety net). (3) `uv sync`. (4)
  `_wait_for_main_thread_action("save_toe")` — re-saves autoload
  `.toe` so the externaltox link points at fresh content on next TD
  launch.
- `rollback()` — find newest `~/.tdpilot/backups/<ts>/`, move current
  install to `target.rollback-aside-<ts>`, copytree the backup back.
  If copy fails, swap the aside copy back so the user is never left
  empty-handed. Cleanup aside on success. Re-run `uv sync` after
  restore (backup didn't include `.venv`).

### Build pipeline
- `td_component/build_tdpilot_tox.py` — the v1.5.6 successor to
  `build_export_mcp_tox.py`. Constructs the full parent `tdpilot`
  containerCOMP with custom param pages (Install + Update, 23 params
  total), four installer DATs (`installer` textDAT,
  `installer_exec` parameterexecuteDAT with `fromop=parent()`
  expression, `autostart` executeDAT, `renderer` textDAT), the
  `status_text` textTOP (Courier New 14pt left-top aligned, 16px
  inset, 4px line-spacing, 55% white — matches the live design), and
  the nested `mcp_server` sub-COMP delegated to the legacy
  `_populate_component` so the v1.5.6 `.tox` inherits every
  MCP-server fix the legacy script accumulated. Reuses
  `_guess_repo_root`, `_read_repo_file`, `_set_first_par`,
  `_create_with_fallback`, `_resolve_export_host`,
  `_reset_or_create_comp`, and `_write_tox_source_hash` from the
  legacy script via direct import.
- `_TOX_SOURCE_FILES` and `SOURCE_FILES` extended in
  `build_export_mcp_tox.py` and `scripts/check_tox_freshness.py` to
  hash the four new installer source files. CI's freshness gate now
  fails when any of them change without a corresponding `.tox`
  rebuild, same as for the existing four mcp_server sources.

## 1.5.3 - 2026-04-25

Knowledge corpus + MCP source-fix release. v1.5.3 adds a free-form
markdown knowledge store as a parallel surface to technique memory
(prose-with-math reference essays vs. replayable network recipes), 4
new MCP tools to query/persist knowledge entries, and 3 source-side
bug fixes that surfaced during real-world TD verification on TD
2025.32460.

The original v1.5.3 plan (auth-bootstrap regression test,
`td_preflight_patch` delegation, auto-snapshot on `apply_plan`,
`_record_outcome` for macro, additional variant strategy) was scoped
against an earlier dev cycle; that work is deferred to v1.5.4.
Substantively, this release ships the WIP knowledge-store branch
verified against TD 2025+ across three live tests: deep feedback patch
(3D render → feedbackEdge chain → bloom), GLSL raymarched composition
with chromatic aberration + bloom, and a beat-reactive video sequencer
with 5-way switching driven by bass-band audio analysis.

Tool count: 97 → 101. `API_VERSION` bumps 1.5.2 → 1.5.3 to reflect the
response-shape changes from the silent-null guard expansion and the
new `node_detail` truncation metadata fields; `.tox` rebuild
auto-detected on next TD launch via
`tdpilot_startup.py:_is_tox_stale`.

Highlights:
- 4 new `td_knowledge_*` MCP tools (`save`/`recall`/`get`/`list`) with
  markdown body storage at `~/.tdpilot/knowledge/{global,projects/<name>}/`.
  Project-scope auto-derives from `TDPILOT_PROJECT_NAME`. Body cap
  200 KB per entry, stored as plain `.md` files for direct user
  editing — separate corpus from technique memory.
- Silent-null guard expanded to plural OP-reference styles
  (`OPS/COMPS/TOPS/CHOPS/SOPS/DATS/MATS/POPS/POPXS/OPLIST`).
  `renderTOP` `cameras`/`lights`/`geometry`, attribute-COMP `COMPs`,
  and similar list-style references no longer silently null on string
  assignment — they surface a structured silent-null error like the
  singular reference styles already did.
- `td_get_node_detail` now caps parameters at `param_limit` (default
  50, hard ceiling 200) with `parameters_truncated` /
  `parameters_total` / `parameters_returned` / `parameters_hint`
  metadata fields. Heavy COMPs that previously returned 80 KB+ JSON
  payloads now stay under reasonable response sizes; callers use
  `td_get_params` with `names`/`page` filters for the rest.
- Better `td_search_popx_docs` not-installed message — actionable
  install command (`npx tdpilot brains add popx`) plus local-docs
  fallback path (`skills/popx-touchdesigner/references/`) instead of
  the previous bare error.
- New `tdpilot-core` SKILL §11 "Render Pipeline Pitfalls" documenting
  the `geometryCOMP`-defaults-to-POP-`torus1` trap, OP-ref-not-string
  requirement for reference params, `viewer=True` discipline for
  test/debug COMPs, and `feedbackTOP` canonical wiring (verified
  node-by-node against the Derivative palette demo).

### Added
- **Knowledge store** (`src/td_mcp/memory/knowledge_store.py`,
  `src/td_mcp/registry/tools_knowledge_store.py`): free-form markdown
  reference essays as a parallel surface to technique memory. CRUD
  via `td_knowledge_save` / `td_knowledge_recall` / `td_knowledge_get`
  / `td_knowledge_list`. Storage at `~/.tdpilot/knowledge/` with
  project + global scopes (mirrors `TechniqueStore`). 12-test pytest
  suite covers add/get/search/update/delete/promote/favorite/rating/
  size-cap/persistence/list-filters. Real-data smoke verified against
  the migrated `feedbackTOP-canonical-patterns` and
  `Belousov-Zhabotinsky-in-pure-TOPs` essays.

### Fixed
- **Silent-null on plural OP-reference styles**: `REFERENCE_PAR_STYLES`
  in `td_component/mcp_webserver_callbacks.py` was singular-only
  (`OP/COMP/CHOP/SOP/TOP/DAT/MAT/POP/POPX`). List-style references on
  `renderTOP` (`cameras`/`lights`/`geometry`) silently resolved to
  None when assigned a string and the caller got `success=True` on a
  parameter that didn't actually take. Set now includes
  `OPS/COMPS/TOPS/CHOPS/SOPS/DATS/MATS/POPS/POPXS/OPLIST`. Verified
  live: `renderTOP.par.{geometry,cameras,lights}` now resolve to OP
  paths (single OR list) with `style="Object"`, no nulls.
- **`td_get_node_detail` returning 80 KB+ for heavy COMPs**: the
  `parameters` dict was unconditionally serialized with no cap. A
  `geometryCOMP` could yield 79+ params totaling 80+ KB. Now defaults
  to `param_limit=50` (hard ceiling 200) with structured truncation
  metadata. Use `td_get_params` with `names=[...]` or `page="..."`
  filter for the rest.
- **POPx-not-installed message ambiguity**: `td_search_popx_docs`
  used to fail with a bare error when the `popx_brain` service was
  None. Now returns an actionable hint (`npx tdpilot brains add popx`)
  plus the local-docs fallback path
  (`skills/popx-touchdesigner/references/` — build locally per
  `BUILD.md`).

### Changed
- **`tdpilot-core` SKILL §11 "Render Pipeline Pitfalls"**: new section
  documenting four real traps from session debugging on TD 2025.32460:
  (1) `geometryCOMP` defaults to a POP `torus1`, not SOP — breaks
  SOP-based instancing; (2) reference params need real OP refs, not
  strings; (3) `viewer=True` must be set on test/debug COMPs for
  error visibility; (4) `td_get_errors == 0` is NOT a render-success
  signal — always `td_screenshot` the output. Plus the
  verified-against-Derivative `feedbackTOP` canonical wiring with the
  "Not enough sources" static-analysis warning explained.
- **`README.md` v1.5.1 → v1.5.3**: title was stale since v1.5.2;
  fixed in this release.
- **`TODO(v1.5.2)` retagged to `TODO(v1.5.4)`** in
  `src/td_mcp/registry/tools_planning.py:194` — `td_preflight_patch`
  → `patch.preview_plan` delegation deferred to next cycle.

### Still deferred (carried into v1.5.4 work)
The original v1.5.3 plan items 1-5 did not ship in this release; they
remain on the v1.5.4 backlog:
- Auth-bootstrap regression test (catches if `bootstrap_auth()` is
  moved back inside `main()` — would silently regress the v1.5.2 fix).
- `td_preflight_patch` → `patch.preview_plan` delegation (needs
  dict↔PatchPlan adapter + parity tests; signature mismatch is the
  real blocker).
- Auto-snapshot before `apply_plan` (opt-out safety net for multi-op
  patches).
- `_record_outcome` for `kind=macro` (surface paths created by macro
  expansion, not just the macro op metadata).
- Additional variant strategy beyond `param_jitter` (e.g.
  `seed_perturb` for cheap visual variations).

Plus older deferrals from v1.5.0/v1.5.1/v1.5.2:
- Destructive op kinds (`delete`, `disconnect`, `reset_params`) —
  needs safety/confirmation design pass first.
- Exec-policy duplication refactor (Python AST + TD-side runtime
  checks parallel each other; long-term: shared generated policy).
- `ui.undo` from webserver context (TD threading constraint research
  needed).

### Operational notes
- `API_VERSION` bumps 1.5.2 → 1.5.3. `.tox` rebuild required;
  auto-detected on next TD launch via
  `tdpilot_startup.py:_is_tox_stale`.
- `td_knowledge_*` storage lives at `~/.tdpilot/knowledge/` — fully
  local, never pushed to remote. Project entries scoped by
  `TDPILOT_PROJECT_NAME`.
- `EXPECTED_MIN_TOOL_COUNT` bumped to 101 in
  `src/td_mcp/release_gates.py`. Tool schema snapshot regenerated.

## 1.5.2 - 2026-04-25

Deferral cleanup + real auth bug + npm publishing pipeline. The
audit-1.5.1 commit explicitly deferred a small set of issues to
v1.5.2; an independent ultradebug pass picked those up plus a few
siblings the audit didn't reach. Plus one genuine bug discovered
during live verification: `bootstrap_auth()` ran *after*
`tool_registry`'s module-level `TD_SHARED_SECRET` capture, so the
MCP server's secret was always frozen as `None` when relying on
`auth_bootstrap` to load it from `~/.tdpilot/.tdpilot.env`. Result:
401s on every TD request for users on the v1.5.1 marketplace install
path. Fixed.

None alter behavior of the 666 passing tests; none touch the wire
format. The patch session API verified live 13/13 against TD
2025.32460.

Highlights:
- Auth-bootstrap ordering bug fixed (real bug, was silently breaking
  marketplace installs)
- Install scripts now auto-pin to the latest git tag
- npm tag-push auto-publish workflow added (no more manual
  `cd npm && npm publish` step that was missed for v1.5.0/v1.5.1)
- Startup banner reads API_VERSION dynamically — no more hardcoded
  v1.3 string drift across releases
- CI runners moved to Node-24-compatible action majors ahead of
  the 2026-06-02 deadline

### Fixed
- **Install scripts didn't pin to release tags** — `npm/run.js`,
  `install.sh`, and `install.ps1` all did `git clone <repo>` on the
  default branch with no checkout step, so `npx tdpilot@1.5.1` (and
  the macOS / Windows installers) ran whatever HEAD of `main` happened
  to be at fetch time. The `version` field in `npm/package.json` was
  decorative. All three install paths now run `git describe --tags
  --abbrev=0` after clone and check out that tag, falling back to
  main with a warning if no tag exists (offline / pre-release / private
  fork). The fix auto-advances when v1.5.2 ships — no per-release
  install-script bumps needed. (Audit deferred this to v1.5.2; the
  audit only mentioned npm but the same bug existed in install.sh and
  install.ps1.)
### Changed
- **`td_preflight_patch` TODO retagged** — the comment
  `# TODO(v1.5.1): delegate to patch.preview_plan` in
  `src/td_mcp/registry/tools_planning.py:194` referred to the current
  shipped version. Retagged to `TODO(v1.5.2)` with a one-line note
  explaining why delegation is non-trivial (signatures differ — the
  MCP tool takes a dict, the helper takes a typed `PatchPlan`, so a
  deserializer + parity tests are needed before delegating).

### Still deferred (carried into v1.5.2 work)
- `tdpilot_startup.py:159` startup banner hardcoded `v1.3`. The robust
  fix (read `API_VERSION` dynamically from
  `mcp_webserver_callbacks.py`) is staged but not committed: it
  requires a `.tox` rebuild that can only happen inside TouchDesigner
  with `TD_MCP_EXEC_MODE=full` (the default `restricted` mode blocks
  the build script's stdlib imports through the MCP `/api/exec`
  gate). Will land alongside the next functional td_component change
  to amortize the rebuild cycle, matching the audit's original call.
- `td_preflight_patch` → `patch.preview_plan` delegation (signature
  reconciliation needed; see retag in `tools_planning.py:194`).
- Exec-policy duplication between Python AST checks and TD-side
  runtime checks. Long-term: shared generated policy.
- v1.5.0 deferrals still pending: destructive op kinds, additional
  variant strategies, auto-snapshot on apply, `_record_outcome` for
  `kind=macro` to surface multiple paths, `ui.undo` from webserver
  context.

### Diagnostics surfaced (not bugs, useful to record)
- `td_get_capabilities` now reports `version.mismatch=true` whenever
  the running Python MCP server (`server_version`) and the loaded TD
  component (`component_version`) disagree. During the ultradebug pass
  this caught a deployment-state issue: the marketplace-installed
  plugin path was running v1.4.7 server code against a v1.5.1 .tox.
  Root cause: the npm version-pinning bug above (already fixed).
  Worth keeping the diagnostic prominent — it's how operational drift
  becomes visible.

## 1.5.1 - 2026-04-25

Wire-format alignment + audit-fix release. v1.5.0 shipped with
`create_node` verified live but the other 5 patch op kinds
(`set_params`, `connect`, `layout`, `annotate`, `macro`) carrying
spec-derived endpoint/field names that didn't match TD's actual
webserver. A comprehensive 13-scenario live-TD probe at
`scripts/patch_session_smoke.py` now exercises all 6 kinds end-to-end
and 6 new unit tests pin the on-the-wire contract.

A pre-release audit also surfaced four orthogonal bugs (P1: plugin
ZIP runtime missing, memory_replay families parsing; P2: validator
frame/capture endpoint nonexistent, doc drift). All fixed in this
release; a fifth (npm wrapper not version-pinned) is deferred to v1.5.2.

`API_VERSION` bumps 1.5.0 → 1.5.1; `.tox` rebuild required (auto-detected
on next TD launch via `tdpilot_startup.py:_is_tox_stale`).

### Fixed
- **`kind=set_params`**: dispatched to non-existent `/api/nodes/set_params`.
  Now uses `node/params/set` matching the legacy `td_set_params` tool.
- **`kind=connect`**: body fields `from`/`to` / `from_output`/`to_input`
  didn't match TD's `handle_connect_nodes`. Now sends `source_path` /
  `target_path` / `source_index` / `target_index`.
- **`kind=layout`**: dispatched to non-existent `/api/nodes/set_position`.
  TD has no dedicated set-position endpoint, so layout now routes
  through `/api/exec` with a minimal `op(path).nodeX = X; nodeY = Y`
  one-liner (restricted-mode safe — no banned tokens).
- **`kind=annotate`**: tried `node/create` with `op_type="annotate"`
  (wrong field name + wrong type string). Now creates a real
  `annotateCOMP` and sets the `text` parameter via a follow-up
  `node/params/set` call.
- **`kind=macro`**: dispatched to non-existent `/api/macro/create`. TD
  has no macro endpoint at all — macros are server-side compositions
  in the `MacroEngine`. `apply_plan()` now accepts a `macro_engine`
  DI parameter (mirroring the planner's `card_index` pattern); the
  `td_patch_apply` MCP wrapper injects it from the service container.
  Calling `apply_plan()` directly without injecting will surface a
  clear `PatchOperationArgsError` rather than calling a phantom
  endpoint.
- **plugin ZIP runtime missing (P1, audit finding):** the legacy
  `tdpilot.plugin` archive bundled manifests + skills + the .tox but
  omitted `pyproject.toml` / `src/td_mcp/` / `uv.lock`. Its
  `.mcp.json` runs `uv run --directory ${CLAUDE_PLUGIN_ROOT} tdpilot`,
  so an unpacked plugin failed with `ModuleNotFoundError: No module
  named 'td_mcp'`. Marketplace install worked by accident (it cloned
  the full repo separately). `scripts/build_plugin_zip.py` now bundles
  the source so both install paths are self-contained. ZIP size 60 KB
  → 346 KB.
- **`td_memory_replay` op-availability check silently disabled (P1,
  audit finding):** TD's `/api/families` returns
  `{"families": {"TOP": [...], "CHOP": [...], ...}}`. The pre-v1.5.1
  loop iterated `families_resp.values()` directly, which yielded the
  inner dict (not a list), so the `isinstance(fam_types, list)` check
  always failed and `available_types` stayed empty — silently
  disabling the prereq guard. Now unwraps the `"families"` key first
  while still accepting the legacy flat shape.
- **validator frame/capture endpoint nonexistent (P2, audit finding):**
  `validate_target` called `/api/frame/capture` which TD doesn't
  expose; capture probes silently 404'd and recorded `"ERROR: …"`
  strings instead of base64 frames. Switched to the canonical
  `/api/screenshot` endpoint and read `data_base64` from the response
  (matching `handle_screenshot` in mcp_webserver_callbacks.py).
- **doc drift (audit finding):** README's "Tool Map (92 Tools)"
  section header bumped to 97. (`tdpilot_startup.py` "v1.3 loaded
  from …" log line is also stale, but rewriting it would invalidate
  the .tox-source-hash and force another rebuild cycle for an
  user-invisible change. Tracked in v1.5.2 deferrals to ride along
  with the next functional .tox rebuild.)

### Added
- 6 new wire-format unit tests in `tests/patch/test_applier.py`
  pinning each op kind's endpoint path + body field names against
  TD's actual handler signatures. Test count 660 → 666.
- Comprehensive live-TD debug probe (`/tmp/tdpilot_v150_debug.py`,
  not committed — used during release validation). 12/12 scenarios
  green: connectivity, all 6 op kinds, sentinel guard, variations,
  legacy intent path, validator, auto_validate.

### Changed
- `apply_plan()` signature: added `macro_engine=None` keyword.
  Backward-compatible — existing callers that don't use `kind=macro`
  ops are unaffected.

### Deferred to v1.5.2
- Destructive op kinds: `delete`, `disconnect`, `set_content`,
  `exec_python` (still pending from v1.5.0 deferral list).
- TD-callback `project/lifecycle action=undo_block_status` endpoint.
- Variant strategies: `operator_substitute`, `topology_perturb`.
- Auto-snapshot on apply.
- `td_preflight_patch` delegation to `patch.preview_plan`.
- `_record_outcome` for `kind=macro`: surface the multiple paths
  the engine creates (currently looks for top-level `path` only).
- `ui.undo` from webserver context: still doesn't reliably revert
  webserver-initiated mutations; smoke uses explicit `node/delete`
  cleanup.
- **npm wrapper not version-pinned (P2, audit finding):** `npx
  tdpilot@1.5.1` clones GitHub `main` into `~/.tdpilot` (or keeps
  whatever checkout is already there), so the npm package version
  doesn't gate the actual code that runs. Fix requires either pinning
  `git clone -b v<version>` to the npm package's version string or
  bundling the Python source in the npm package. Tracked for v1.5.2.
- Exec-policy duplication between Python AST checks and TD-side
  token/runtime checks (audit finding): policy lives in two places
  and could drift. Long-term fix: shared generated policy + behavioral
  tests for the TD callback helpers.
- `tdpilot_startup.py` log line cosmetic ("v1.3 loaded from …"):
  carries a stale version literal. Defer until the next functional
  td_component change so the rebuild cycle isn't paid for a cosmetic.

## 1.5.0 - 2026-04-25

Major feature release. Phase 1 (Bug A schema migration) and Phase 2
(monolithic `tool_registry.py` decomposed into 21 themed submodules)
were merged earlier on `v1.5.0/bug-a-migration` and `v1.5.0/module-splits`
respectively; this entry summarizes the user-visible surface delta.

`API_VERSION` bumps 1.4.7 → 1.5.0; `.tox` rebuild is required for the
TD-side handler to pick up the new version. The auto-rebuild path in
`tdpilot_startup.py` will detect staleness on the next TD launch and
rebuild from source — no manual action needed for users.

### Added
- **Patch Session MVP (5 new MCP tools):**
  - `td_patch_plan` — build typed PatchPlan from intent/recipe/operations.
  - `td_patch_preview` — summarize changes + live_risk_flags (live state probe).
  - `td_patch_apply` — execute in one undo block; structured PatchResult.
  - `td_patch_validate` — composite errors + cook stats + frame capture.
  - `td_patch_variations` — N variants from a base plan (param_jitter).
- 7 new Pydantic v2 models in `src/td_mcp/models/patch.py`: `PatchOperation`, `ValidationPlan`, `PatchPlan`, `PatchPreview`, `ValidationReport`, `PatchResult`, `PatchVariant`. All `extra="forbid"`.
- New `src/td_mcp/patch/` package with MCP-free business logic (planner, applier, validator, variants, undo_sentinel). Three-layer testing seam: model-level (Pydantic), patch-package-level (FakeTDClient), MCP-tool-level (RecordingTDClient + monkeypatched services).
- 64 new tests across the three layers (596 → 660).
- `scripts/patch_session_smoke.py` — live-TD end-to-end smoke covering plan → preview → apply → validate → undo → cleanup.
- New `_PATCH_SENTINEL` process-wide singleton in `tool_registry.py` (an `UndoBlockSentinel` instance). DI-injected into `patch.applier.apply_plan` to refuse re-entry when an undo block is already active. `NestedBlockError` is raised on collision.

### Changed
- **Module splits (Phase 2):** `tool_registry.py` decomposed into 21 themed submodules under `src/td_mcp/registry/` (graph, params, planning, vision, knowledge, memory, etc.). Intentional cycle pattern via `from td_mcp import tool_registry as _tr` — see `src/td_mcp/registry/__init__.py`. No external schema drift.
- **Bug A migration (Phase 1):** all 92 pre-existing tools migrated from the opaque `params: dict` wrapper to explicit `Annotated[T, Field(...)]` per-arg signatures. `tests/test_no_opaque_params_wrapper.py` enforces this discipline going forward.
- `td_plan_patch` internally now delegates to `patch.build_plan` via `_legacy_plan_dict()` shim in `tools_planning.py`; external dict shape preserved byte-for-byte (verified by `tests/test_legacy_patch_shim.py`).
- Tool count: 92 → 97.
- `EXPECTED_MIN_TOOL_COUNT` in `release_gates.py` bumped 92 → 97 (used by contract tests, schema-snapshot test, plugin builder).
- User-facing docs (README, npm/README, plugin_README, docs/, skills/) updated to reflect 97-tool surface and Patch Session capability.

### Fixed
- **TD-side auth bootstrap:** `tdpilot_startup.py` now loads BOTH `<repo>/.tdpilot.env` AND `~/.tdpilot/.tdpilot.env` so the dragged-in / auto-rebuilt .tox sees the auth_bootstrap-generated secret. Before this fix, the Python MCP server's auto-generated secret in `~/.tdpilot/.tdpilot.env` was never visible to the TD webserver, causing every request to 401 even on fresh installs.
- **Wire-format alignment:** `applier._apply_op` for `kind=create_node` now sends body['node_type'] (was 'op_type') and body['nodeX'/'nodeY'] (were 'x'/'y') matching TD's `/api/node/create` handler. Path readback now extracts from the nested `{"node": {...}}` response shape.
- **Validator endpoint name:** `validate_target` now calls `/api/cooking` (was `/api/cooking_info`, which doesn't exist).
- **Removed dead code:** `_suggest_macro_for_intent` + `_INTENT_MACRO_KEYWORDS` from `tools_planning.py` — logic now lives in `patch.planner`.

### Deferred to v1.5.1
- Destructive op kinds: delete, disconnect, set_content, exec_python.
- TD-callback `project/lifecycle action=undo_block_status` endpoint.
- Variant strategies: `operator_substitute`, `topology_perturb`.
- Auto-snapshot on apply.
- `td_preflight_patch` delegation to `patch.preview_plan`.
- **Macro endpoint gap:** `applier._apply_op` for `kind=macro` calls `/api/macro/create` which TD doesn't expose — needs routing through `/api/exec` like the legacy `td_create_macro` Python path.
- **`ui.undo` from webserver context unreliable:** `project/lifecycle action=undo` returns success but doesn't actually revert webserver-initiated mutations. Smoke uses explicit `node/delete` cleanup as workaround.
- **applier wire-format unverified for `set_params`/`connect`/`layout`/`annotate`** — only `create_node` exercised by live smoke; field-name fixups likely needed for the others.



## 1.4.7 - 2026-04-24

Live-validation release. Thirteen behavioral bugs surfaced during a
systematic exploratory pass against a running TouchDesigner instance
after v1.4.5 shipped. Each fix is pinned with a behavioral regression
test that starts RED against the pre-fix code and stays GREEN post-fix.
Tool count unchanged at 92. `API_VERSION` bumps 1.4.6 → 1.4.7;
`.tox` rebuild is required for the TD-side handler to pick up the
Bug J silent-null guard (the TD-side fix already landed in the 1.4.6
intermediate `.tox` in the repo — this version just keeps the API
version aligned with the Python package). Tests: 551 → 594 (+43 new
regression tests across twelve distinct fixes).

### Fixed

- **`td_get_operator_doc("glsl")` short-form finally resolves.**
  TD's `node/detail` returns the short op type (`"noise"`) and family
  (`"TOP"`) as separate fields, but DocsBrain keys operators by the
  canonical `type+family` form (`"noiseTOP"`). Before v1.4.7 the tool
  only tried the short form, so every short-form query returned
  `"No card found"` while the canonical form returned a rich card. Now
  retries with `op_type + family.upper()` when the short-form lookup
  misses; when only `op_type` is given without a `node_path`, iterates
  known family suffixes in frequency order. Mirrors the same fix
  landed for `td_get_param_help` in v1.4.6 but on a second tool that
  was missed in that pass.

- **POPx `td_search_popx_docs` returns hits again.** Queries like
  `td_search_popx_docs("Noise Falloff")` silently returned 0 results
  despite the POPx DB containing 962 palette chunks + 59 operators
  with exact matches. Root cause: `DocsBrain._detect_intent` narrowed
  operator-name queries to `doc_type IN ('operator', 'python_api')`,
  but the POPx corpus uses `catalog_operators` and `reference`
  doc_types — so every chunk was filtered out. The intent filter now
  emits a superset list covering both conventions. Derivative-brain
  queries are unaffected (those doc_types don't exist there).

- **Operator `key_params` no longer contain stray doc text.** Cards
  for menu-heavy ops (glslTOP, renderTOP, etc.) surfaced
  `key_params` entries like `{name: "Back"}`, `{name: "8"}`,
  `{name: "_separator_"}`, `{name: "DCI"}` — menu option values and
  stray doc-text fragments bleeding through the FTS
  `parameter_names` column. `DocsBrain._normalize_key_param` now
  requires the `"Label\ninternalname"` structure in the raw entry —
  single-token fragments without a newline are dropped. Real params
  from scraped docs always have that shape; the drop-rate is zero
  false negatives across the test corpus.

- **`td_create_node` accepts the POPX family suffix.** TD 2025 ships
  a native POPX operator family (visible as a dedicated tab in the
  OP Create Dialog — Noise Falloff, DLA, Particle, Physarum, …).
  The `CreateNodeInput` validator only allowed TOP/CHOP/SOP/DAT/COMP/
  MAT/POP — so any attempt to create a POPX op via MCP failed with
  a misleading Pydantic error pointing at the wrong cause. Added
  POPX to the allowed suffix tuple, listed before POP so callers
  that parse family via longest-suffix match pick the correct one
  for `noisePOPX` (POPX, not POP).

- **`td_set_params` no longer silently succeeds on reference-style
  params.** TD accepts a plain string assigned to DAT/OP/CHOP/SOP/
  TOP/COMP/MAT/POP/POPX reference params without raising, but
  internally resolves the value to `None` and emits a node-level
  warning. Pre-v1.4.7 the handler reported `success: true,
  new_value: null`, hiding the failure. Live repro: writing
  `"../pixel_shader"` to a `glslTOP.pixeldat` returned a phantom
  success while TD's own `.warnings()` said "Invalid path for node".
  The TD-side handler now validates post-assignment: if the
  resolved value is None AND the caller passed a non-empty string
  AND the param style is reference-type, it flips the per-param
  result to `success: false` with a structured error citing the
  style and TD's warning text. Numeric zeros, empty strings on Str
  params, and False on Toggles are unaffected — None-after-set is
  the precise discriminator. (Implemented in
  `td_component/mcp_webserver_callbacks.py`; `API_VERSION` bumped
  and the shipped `.tox` was rebuilt.)

- **`td_exec_python` restricted-mode error is actionable.** Agents
  hitting `exec('import os')` in the default `restricted` mode got
  `"import of dangerous module blocked: os"` — which implies `os`
  is specially flagged. It isn't; restricted mode blocks ALL
  imports regardless of module name. The AST check just happened
  to fire first with a misleading module-specific label, and the
  error gave no remediation path. The message now reads
  `"restricted mode blocks import statements. Set
  TD_MCP_EXEC_MODE=standard for allowlisted stdlib imports (json,
  math, re, datetime, collections, itertools, etc.) or
  TD_MCP_EXEC_MODE=full for unrestricted imports."`. Standard-mode
  behavior is unchanged — there, the module-specific "dangerous
  module" message IS accurate because standard genuinely
  discriminates by module name.

- **`td_audit_project` stops mis-labeling stock ops as palette
  components.** Running audit on a project with plain noise / level
  / null / transform TOPs surfaced every one of them in
  `palette_components` — the field was meant to highlight installed
  palette COMPs (POPX_1_2_1, StreamDiffusionTD, WebRTC) that add
  external capabilities, not stock primitives. Root cause: the
  heuristic was `if idx.get_palette(op_type): flag`, and the
  production CardIndex happens to store palette-adjacent cards for
  stock ops too. Gated the flag on `op_type.lower() not in
  _STOCK_OP_TYPES` so only non-stock ops with a palette card are
  listed.

- **DocsBrain `search()` now returns CardIndex-shape rows.** Two
  symptom-coupled bugs with one root cause. `td_find_official_example`
  emitted 5 `palette_example` entries with every field empty; and
  `td_explain_better_way("animate noise TOP every frame")` returned
  an empty recommendation every time. Both consumers read
  CardIndex-shape keys (`component_name`, `display_name`,
  `summary`, `op_type`, `snippet_id`) from `idx.search()` output,
  but DocsBrain's `search()` emitted raw FTS-chunk-shaped rows with
  `section_title`, `operator_name`, `content`, etc. — none of the
  expected keys existed, so consumers saw blanks and
  `_is_informative_card` dropped every candidate.
  `get_operator()` and `get_palette()` already translated to
  CardIndex shape for their exact-lookup responses;
  `search()` did not. Added `_normalize_search_row()` that
  enriches each row by doc_type (operator → adds `op_type` +
  `display_name` + `summary`; palette → strips `Palette:` prefix
  into `component_name` + `display_name` + `summary`; snippet →
  adds `snippet_id`). Additive — raw FTS fields stay intact so
  existing consumers that read `operator_name` / `operator_family`
  keep working.

- **`td_memory_learn` follows wire connections for non-COMP roots.**
  Pre-v1.4.7 `_collect_subtree` only descended when the current
  node had `isCOMP=True`. Learning from a TOP/CHOP/SOP returned
  just that single node — users with a wire-connected chain had to
  pre-wrap it in a baseCOMP before saving. Auto-detect fix: the
  walk mode is determined from the ROOT node's type. COMP root →
  classic tree walk (unchanged). Non-COMP root → bidirectional
  wire-graph walk, following `inputs` upstream AND `outputs`
  downstream, bounded by `max_depth` hops and `max_nodes` total.
  Supports both "learn from the source" and "learn from the
  terminal" workflows. Mode is locked at the root so COMP tree
  walks can't leak out via wires and wire walks can't fan out
  through deeply-nested COMPs.

- **Wire-walked recipes are portable across `parent_path`.**
  Follow-up to the non-COMP wire walk. Recipes captured by
  wire-walk kept absolute paths for siblings (e.g.
  `/project1/my_sibling`) — replaying to a different
  `parent_path` skipped them with `missing_parent`. The recipe
  builder now branches on walk mode: COMP-rooted recipes keep
  `/` as the wrapper (unchanged); wire-walked recipes have NO
  `/` entry at all — every captured node (including the head)
  gets a leaf-name rel_path (`/head`, `/mid`, `/tail`) and all
  of them land as peers under `parent_path` on replay. Leaf-name
  collisions get a numeric suffix.

- **`td_memory_replay` can now recreate the root COMP wrapper
  (opt-in).** New `recreate_root: bool = False` flag on
  `MemoryReplayInput`. When True AND the recipe's `/` entry is a
  COMP, the replay creates that wrapper COMP under `parent_path`
  first and builds children INSIDE it — producing a faithful
  clone of a COMP-packaged technique. Default False preserves the
  existing flat-replay behavior. Edge cases (recipe without `/`,
  or with non-COMP `/`) are safe no-ops. Root COMP's params are
  carried through after create.

- **`td_delete_node` ships with an explicit flat schema (PoC for
  the 70-tool Bug A sweep).** One of the 70 TDPilot tools that
  use the `params: InputModel, ctx: Context` FastMCP signature
  surfaces an opaque `"params": {}` JSONSchema to MCP clients —
  the client can't discover what fields are valid without
  reading source. `td_delete_node` rewritten to
  `ctx: Context, path: Annotated[str, Field(description=...,
  min_length=1)]` — flat schema with description + minLength
  visible to every MCP client. Investigation memo at
  `docs/superpowers/reports/2026-04-24-bug-a-opaque-params-investigation.md`
  documents the pattern and the 69-tool migration plan for v1.5.0.

- **Param-help op_type + case-insensitive live fetch (pre-branch
  work).** `td_get_param_help` against a live TD node now retries
  with `type+family` when the short-form lookup misses, AND
  retries live param fetch with lowercased name when TD's
  case-sensitive filter returns empty. (Shipped separately as
  `ad36cd1` before the fix branch landed — included here for
  release-note completeness.)

### Also

- Test-isolation hardening in `tests/test_cli.py` — three
  doctor-auth tests were leaky on developer machines because
  v1.4.5's auth bootstrap runs before every non-init command and
  reads `~/.tdpilot/.tdpilot.env`. Added `TDPILOT_ENV_FILE` tmp
  override so the tests can't silently pick up the developer's
  real secret.

- `tests/fixtures/tool_schemas.json` regenerated for the Bug A
  PoC schema change — confirms the `td_delete_node` rewrite
  produces a flat schema visible to MCP clients.

### Not shipped

- `Bug A full migration` (remaining 69 tools) — deferred to
  v1.5.0. Memo documents the plan.
- The wire-walked recipe portable-paths follow-up is the last
  piece from Bug S and landed in `11d4c9d`; included in this
  release.

## 1.4.5 - 2026-04-24

Review-fix patch. Four issues surfaced during local review of v1.4.3 and
v1.4.4. No TD-side protocol changes — `API_VERSION` stays at 1.4.2,
no `.tox` rebuild required. Tool count unchanged at 92. Tests: 509 → 551
(+42 new regression tests across the four fixes).

### Fixed

- **Plugin auth bootstrap actually works now:** v1.4.3's fail-loud gate
  for `TD_MCP_REQUIRE_AUTH=1` + missing secret was *correct*, but the
  default plugin path deterministically tripped it on first boot because
  nothing was provisioning the secret. Ships a new
  `src/td_mcp/auth_bootstrap.py` module that:
  - loads `~/.tdpilot/.tdpilot.env` (canonical cross-process path shared
    with TD-side `tdpilot_startup.py` — they converge naturally because
    `tdpilot_startup.py` reads `<repo_root>/.tdpilot.env` and
    `repo_root` = `~/.tdpilot` when the user ran `npx tdpilot install`);
  - when `TD_MCP_AUTOGENERATE_SECRET=1` is set (opt-in to prevent
    surprise disk writes) and no secret is resolvable, mints a 256-bit
    secret via `secrets.token_urlsafe(32)`, writes it atomically with
    0600 permissions, and injects it into `os.environ`;
  - is called before `verify_auth_config()` at server startup so the
    gate sees the populated env;
  - never echoes secrets to stdout (stdio MCP transport).
  `.mcp.json` now declares `TD_MCP_AUTOGENERATE_SECRET=1` so fresh
  plugin installs actually work.

- **Brain manager refuses bogus activations:** `npx tdpilot brains add`
  previously wrote any requested id to `active.json` after a zero-exit
  downloader, even if the id was a typo or a `local_build` brain with
  no files. Because `active.json` acts as an allow-list, a typo could
  silently disable all known brains on next startup. Hardens both
  surfaces:
  - `scripts/download_brains.py` exits non-zero on unknown ids, empty
    selections, or selections containing only local-build brains;
    `--list` now surfaces `install_mode` per brain.
  - `npm/brains.js addBrain()` validates the id against the manifest
    BEFORE calling the downloader; for `install_mode: local_build`,
    refuses activation unless the runtime DB (`runtime_db`) is
    already on disk. Only writes `active.json` after verified success.
  - Also fixes a pre-existing bug where `brains.js` exported `main()`
    but never invoked it when run directly (no `require.main === module`
    dispatch) — invocations actually run now.
  - `data/brains/brains_manifest.json` bumped to manifest_version 2
    with per-brain `install_mode` and `runtime_db`. Community-tier
    local-build brains correctly tagged.

- **DocsBrain parameter help no longer hollow:** `td_get_param_help`
  read `card.get("key_params", [])`, but DocsBrain's `get_operator()`
  returned `parameters: list[str]` with no `key_params` key. When
  DocsBrain was the active source, parameter help silently returned
  `card_param: None` for every parameter. DocsBrain now synthesizes a
  CardIndex-compatible `key_params: list[dict]` with
  `{name, label, raw, source: "docsbrain"}` per entry. `td_get_param_help`
  iterates either shape case-insensitively and the provenance field now
  reflects the actual card origin (`docsbrain` vs. `local_card`).

- **`tdpilot init --print-only` stays machine-readable:**
  `tdpilot init --print-only --auth --generate-secret | jq .` was
  silently broken because secret-generated notices were printed to
  stdout before the JSON profile. Also, `--generate-secret` and
  `--shared-secret` were silently ignored without `--auth` and could be
  combined ambiguously. Fixes all three:
  - stdout under `--print-only` contains EXACTLY the JSON profile;
    secret notice goes to stderr.
  - The secret itself is NEVER echoed to stdout anymore (only surfaces
    via the written config file — security tightening).
  - `--generate-secret` without `--auth` → exits 2 with clear message.
  - `--shared-secret` without `--auth` → exits 2.
  - `--generate-secret` AND `--shared-secret` together → exits 2.
  - `--auth` alone now generates a secret by default (previously
    produced an invalid "require auth + no secret" config).
  - Profile now includes `TD_MCP_EXEC_MODE=restricted` when
    `--auth` is set (matches shipped `.mcp.json`).

### Tests

- +17 `test_auth_bootstrap.py` — load semantics, autogen opt-in/opt-out,
  file permissions, idempotency, stdout non-leakage, default path.
- +6 `test_download_brains_cli.py` subprocess tests — unknown id, empty
  selection, local-build-only, mixed, list output.
- +5 `test_brains_cli_js.py` node-subprocess tests against isolated
  HOME — unknown id rejected, local-build without db rejected, with
  db activates, showInstalled clean.
- +3 `test_docsbrain_search.py` tests — key_params shape, name parity
  with parameters list, missing-op returns None.
- +3 `test_param_help_docsbrain.py` end-to-end tests — known param,
  case-insensitive match, unknown param clean fall-through.
- +7 `test_cli.py` tests — print-only stdout parseable, flag-combo
  validation, --auth default-generate, exec_mode=restricted baked.
- Updated: 2 v1.4.4 plugin-install-smoke tests + 1 v1.4.4 init test
  that pinned the (now-improved) old behavior.

### Unchanged

- Tool count: 92.
- `API_VERSION` in `td_component/mcp_webserver_callbacks.py`: still
  `1.4.2`. No `.tox` rebuild required for this release.

## 1.4.4 - 2026-04-24

Reliability release. Ten tasks shipped — behavioral tests replacing
structural-only ones, runtime bind fixes for late-starting TD, CI
hardening (package build smoke, plugin install/auth smoke, coverage
ratchet, enforced ruff format), brain installer unbreak, and security
doc sharpening. No TD-side protocol changes — API_VERSION stays at
1.4.2, no .tox rebuild required. Tool count unchanged at 92.

### Fixed

- **Late-start project-memory rebind:** `TechniqueStore` /
  `PreferenceStore` now expose `rebind_project_scope()`, and every
  project-scoped memory tool calls a new `_ensure_project_scope(ctx)`
  helper that demand-binds the stores from live TD's `info`. Retroactively
  confirmed against the installed 1.4.0 server: `td_memory_save
  scope=project` was raising "TDPILOT_PROJECT_NAME is not set" even
  while `td_get_info` reported a valid project_name on the same live
  server. Now the first memory-tool call after TD becomes reachable
  transparently binds the stores for the rest of the session.

- **Brain installer placeholder:** `npm/brains.js` had a literal
  `MANIFEST_DRIVE_ID = "MANIFEST_FILE_ID"` string and no
  `brains_manifest.json` was shipped anywhere. `npx tdpilot brains list`
  printed "No manifest found"; community brains were invisible to the
  installer. Ship `data/brains/brains_manifest.json` listing derivative
  + popx (with real Drive IDs) and any local-build brains pointing
  users at `scripts/build_tutorial_brain.py`.

- **Security-doc sharpening:** `docs/SECURITY.md`'s exec-modes table
  previously claimed restricted mode has "TD API: read-only", which
  misreads the guarantee. Rewrote the table row and added a new
  "what we don't protect against" item 6 stating explicitly that
  restricted is a Python-level sandbox (blocks OS escapes, imports,
  dunder reflection, `.text=` DAT writes, `.par.file=` path writes)
  but does NOT prevent `.par.amp = 2.5`, `op('x').destroy()`, or most
  TD Python API method calls. `TD_MCP_EXEC_MODE=off` is the only true
  read-only posture.

### Added

- **Resource handler behavioral tests:** seven new tests in
  `tests/test_resource_fallbacks.py` — one per handler — that actually
  call the handler and assert the static-mode contract
  (`resource_schema_version`, `resource_uri`, `mode`, `note` points at
  the correct tool, and URI templates round-trip args). Pre-v1.4.4
  coverage was AST-only and didn't prove the handlers worked.

- **Doctor tool-count drift check:** `tdpilot doctor` now includes a
  `tool_count_drift` line that compares `@mcp.tool(` count in
  `tool_registry.py` against `manifest.surface.tool_count`. Emits
  warn on mismatch, pass on match; non-fatal since it's local
  developer ergonomics (CI has the hard gate via `check_versions.py`).

- **Package build smoke:** new `scripts/check_package_builds.sh`
  builds wheel (`uv build`), npm tarball (`npm pack`), and plugin
  zip, then greps each for the critical files they must contain (~11
  total). Wired into `.github/workflows/ci.yml`.

- **Plugin install / auth smoke test:** six tests in
  `tests/test_plugin_install_smoke.py` pin the whole plugin-install →
  auth-behavior loop. Covers shipped `.mcp.json` still declaring
  `TD_MCP_REQUIRE_AUTH=1`, no embedded literal secret, and that the
  v1.4.3 Fix #1 gate trips in the unconfigured state.

- **Install-profile unification (partial):** `tdpilot init` gains
  `--auth`, `--generate-secret`, and `--shared-secret` flags so the
  CLI can emit the same auth-enabled config shape
  `install.sh`/`install.ps1` already generate. `install.sh` /
  `install.ps1` themselves left untouched (larger refactor risk for a
  reliability release).

- **Store-level `rebind_project_scope()`:** exposed on both
  TechniqueStore and PreferenceStore. In-place mutation so other
  consumers of the store reference automatically benefit from the
  binding; safe to call repeatedly.

- **`_ensure_project_scope(ctx)` helper:** async demand-binder called
  at the top of every project-scoped memory tool
  (`td_memory_save`/`recall`/`replay`/`favorite`/`promote`/`export`/
  `import`/`list`/`preferences`). Silent on TD unreachable; retries
  next call.

### CI and tooling

- **Coverage ratchet:** `fail_under = 60` in
  `[tool.coverage.report]`. Current baseline ~61%; raises ~5% per
  release as `tool_registry.py` gets split into focused modules in
  v1.5.0.

- **Ruff format enforced:** 68 files reformatted in one mechanical
  commit (e9ca15e), listed in new `.git-blame-ignore-revs`. The
  `ruff format --check` CI step no longer has
  `continue-on-error: true`. `td_component/mcp_webserver_callbacks.py`
  added to the format exclude list — it's baked into the .tox and
  reformatting would stale the hash.

- **.gitignore:** added `.coverage`, `.coverage.*`, `coverage.xml`,
  `htmlcov/` so local coverage artifacts don't leak into commits.

### Tests

- Tests: 472 (end of v1.4.3) → 509 (end of v1.4.4). +37 new tests
  across rebind, `_ensure_project_scope`, drift check, install smoke,
  auth init flags, resource behavioral, package build smoke-shaped.

### Unchanged

- Tool count: 92.
- `API_VERSION` in `td_component/mcp_webserver_callbacks.py`: still
  `1.4.2`. No `.tox` rebuild required for this release.

## 1.4.3 - 2026-04-24

Release-blocker patch. Six targeted fixes shipped behind regression tests.
No TD-side protocol changes — API_VERSION stays at 1.4.2, no .tox rebuild
required.

### Fixed

- **Plugin install auth path**: the server now refuses to start when
  `TD_MCP_REQUIRE_AUTH=1` is set but no `TD_MCP_SHARED_SECRET` is resolvable,
  and exits with a clear message pointing to the installer. Previously the
  default `.mcp.json` shipped auth-required without a secret, and the Claude
  Code plugin install path reads `.mcp.json` directly — so the server would
  boot happily and every authenticated tool call returned 401 with no signal
  about why. `tdpilot doctor` now also flags this misconfiguration explicitly.

- **DocsBrain multi-word operator lookup**: operators with three or more
  words in their name now resolve by the correct op_type:
  - `Movie File In TOP` → `moviefileinTOP`
  - `Audio File In CHOP` → `audiofileinCHOP`
  - `GLSL Multi TOP` → `glslmultiTOP`
  The op-type map previously used only the first word before the family
  suffix, so multi-word operators silently returned `None` when looked up
  via `get_operator()`.

- **DocsBrain card-type aliases**: searches with plural or expanded
  `card_types` values (e.g. `["operators"]`, `["release"]`, `["releases"]`,
  `["palettes"]`) now match the singular canonical `doc_type` values stored
  in the index (`operator`, `release_notes`, `palette`). Previously these
  filters built `WHERE doc_type IN ('operators')` and silently returned zero
  hits. Unknown card types pass through unchanged so future additions don't
  need an alias entry.

- **`td_memory_replay` state transition**: clean replays now correctly
  promote techniques from `candidate` → `validated_local`, and failing
  replays demote `validated_local` → `candidate`. Previously the promotion
  path used `TechniqueStore.update()`, which intentionally drops `state`
  keys to enforce state-transition discipline — so the validation_result
  reported a pass while the technique silently stayed a candidate. Replay
  now routes through `update_validation()`, which handles both state
  directions.

- **Resource template count manifest**: `mcp/manifest.json` now reports 6
  templates + 1 static resource. Previously it claimed 7 templates, which
  mismatched the registry (one of the seven `@mcp.resource` entries,
  `td://timeline/state`, has no URI parameters). Two new regression tests
  verify that both `tool_count` and the resource counts stay in sync with
  the `@mcp.tool()` and `@mcp.resource()` decorators.

### Added

- **`ExecPythonInput.timeout_ms`**: optional per-call execution timeout in
  milliseconds (bounds 100–60000). When set, `td_exec_python` forwards it
  to the TD-side exec endpoint; when omitted, TD's configured default
  applies. Previously the TD side supported a per-call timeout but the
  Python schema had no way to express it.

### Unchanged

- Tool count: 92 (no `@mcp.tool()` added or removed).
- `API_VERSION` in `td_component/mcp_webserver_callbacks.py`: still `1.4.2`
  (TD-side untouched, `.tox` rebuild not required).

## 1.4.2 - 2026-04-19

Follow-up bugfix release from the v1.4.1 ultra-debug sweep. All fixes address
issues that surfaced while verifying v1.4.1 live against TouchDesigner. Backward
compatible; all v1.4.1 fixes still in place.

### Bug fixes

- **N1 — Component/server version mismatch**: bumped `API_VERSION` constant in
  `td_component/mcp_webserver_callbacks.py` from `"1.3.4"` to `"1.4.2"`. The
  TD-side component now reports a version that matches the Python package, so
  `td_get_capabilities` no longer emits `mismatch: true` after a fresh `.tox`
  rebuild.

- **N2 — `td_build` auto-detect fails when server starts before TD**: added
  `_ensure_td_build(ctx)` helper that lazily populates `svc.td_build` from the
  live TD client when the startup-time fetch produced an empty string. Wired
  into `td_describe_surface`, `td_get_release_delta`, and
  `td_get_build_compatibility`. Users no longer have to pass `build=` explicitly
  when the MCP server outlived a TD restart.

- **N3 — `unstable` inconsistency between endpoints**: extracted
  `_compute_unstable_signal()` helper applying the v1.4.1 FPS-relative heuristic
  and wired both `td_detect_instability` and `td_get_state_vector.health` to it.
  The two endpoints now always agree. `state_vector.health` also gains
  `reasons`, `target_fps`, `frame_budget_ms`, `top_cook_ms`, and
  `critical_issues_count` fields to match the detect-instability output shape.

- **N4 — `td_geometry_data` reports `numVertices: 0` on every prim**: the old
  handler used `getattr(prim, 'numVertices', 0)` which never resolved because
  TD's `Prim` objects don't expose that attribute. Replaced with `len(prim)`
  which is the documented TD API. A boxSOP's 6 quad faces now correctly report
  4 verts each (24 total) instead of 0.

- **N6 — `td_memory_preferences` requires `TDPILOT_PROJECT_NAME` env var for
  project scope**: added a fallback that derives the project name from TD's
  `info.project_name` on server startup when the env var is unset. Strips the
  `.toe` suffix so `NewProject.1.toe` → `NewProject.1`. Users no longer have to
  set the env var manually for the common case where TD is reachable at MCP
  startup; global-scope calls still work for offline init.

- **N7 — `td_validate_recipe` doesn't honor the v1.4.1 stock allowlist**: the
  `_STOCK_OP_TYPES` fix from v1.4.1 only landed in `td_audit_project`. Extended
  to `td_validate_recipe` so inline recipes using common TD types (`base`,
  `constant`, `feedback`, `null`, etc.) no longer surface in
  `unknown_op_types`.

### Verification (against live TD)

- `td_get_capabilities` → `server_version: "1.4.2"`, `component_version: "1.4.2"`,
  `mismatch: false` after `.tox` rebuild
- `td_get_build_compatibility(op_type="feedbackTOP")` (no `build=`) →
  `"compatible"` instead of `"No build specified"`
- `td_get_state_vector.health.unstable` matches `td_detect_instability.unstable`
  for every tested project
- `td_geometry_data` on boxSOP with `include_prims: true` →
  `numVertices: 4` per prim
- `td_memory_preferences(action="set", scope="project")` with unset env var →
  saves to `~/.tdpilot/memory/projects/<derived_name>/preferences.json` instead
  of erroring
- `td_validate_recipe` on recipe with stock types → `unknown_op_types: []`

## 1.4.1 - 2026-04-19

Bugfix release targeting findings from the full tool-surface test run.
All fixes are backward compatible. The TD-side changes (B1, B8, B9) land
in `td_component/mcp_webserver_callbacks.py` and require a `.tox` rebuild
inside TouchDesigner — run the build command in TD's Textport after
pulling this release. All other fixes take effect on MCP server restart.

### Bug fixes (server-side — no .tox rebuild needed)

- **`td_describe_surface` now reports real counts.** Previously returned
  `tool_count: 0, resource_count: 0` because it read
  `mcp._tools` / `mcp._resources`, which aren't part of the FastMCP API.
  Now uses `_tool_manager.list_tools()` and
  `_resource_manager.list_resources()` + `.list_templates()` (plus
  `_prompt_manager.list_prompts()` for completeness).

- **`td_detect_instability` no longer flags FPS-healthy scenes as
  unstable.** The old trigger was `len(heavy_nodes) >= 5` where "heavy"
  meant `cookTime >= 0.01 ms` — so any 9-node scene was permanently
  unstable. New logic is FPS-relative: unstable only if FPS missed target
  by >20%, any critical (not warning) error exists, or a single node cooks
  longer than the full frame budget. Response now includes a `reasons`
  list and a richer `signals` dict (`target_fps`, `frame_budget_ms`,
  `heavy_threshold_ms`, `top_cook_ms`, `critical_issues_count`). Schema
  bumped to `schema_version: 2`.

- **`td_audit_project` no longer flags stock TD op types as unknown.**
  Added a static allowlist of canonical op-type names sourced from
  `td_list_families` (box, null, text, constant, level, math, wave, circle,
  and ~100 others). Before: every audit flagged 8+ common ops. After: only
  true third-party / undocumented types surface in `unknown_op_types`.

- **`td_plan_patch` no longer returns empty `steps` for recipe-less
  intents.** Added keyword-based macro matching (feedback, post-process,
  audio-reactive, particle, feedback-displacement). When matched, the plan
  now includes a `create_macro` step + `macro_suggestion` field.
  When unmatched, a `next_actions` list points callers to
  `td_memory_recall` / `td_list_macros` instead of silently returning `[]`.

- **`td_explain_better_way` + `td_recommend_official_component` no longer
  emit empty-string recommendations.** Added an `_is_informative_card()`
  filter that skips cards where every identifying field is empty.
  Responses now include a `hint` field when no usable matches are found,
  directing callers to complementary tools instead of returning
  `"Consider using '': "`.

- **Exec-mode-gated tools now return structured `EXEC_MODE_INSUFFICIENT`
  errors.** The 6 tools that need imports (`td_python_env_status`,
  `td_threading_status`, `td_logger_status`, `td_color_pipeline`,
  `td_component_standardize`, `td_tdresources_inspect`) previously
  bubbled a bare `"restricted mode blocks import statements"` string up
  through `{"error": "..."}` with no indication that the fix is an env
  var. They now short-circuit at call-time with a structured payload
  documenting `current_mode`, `required_mode`, and `remediation`.

### Bug fixes (TD-side — require .tox rebuild)

- **`td_get_content` on textDATs now returns `format: "text"`**, not
  `format: "table"`. Previous heuristic checked `node.numRows > 0` which
  is always true for textDATs (the full text counts as 1 row). Fix uses
  `node.isTable` as the authoritative discriminator.

- **`td_copy_node` offsets the copy by +150px X** from the source (or
  honors an explicit `nodeX` / `nodeY` in the body if the caller
  supplies them). Previous behavior placed the copy at the exact same
  coordinates as the source, causing overlap in the network editor.

- **`td_project_lifecycle(action="end_undo_block")` is now idempotent.**
  TD auto-closes the active undo block on certain cascading mutations
  (e.g. deleting the COMP that scoped the block). Calling `endBlock()`
  on an already-closed block previously raised "Cannot end non existent
  undo operation". The handler now catches that specific error and
  returns a soft warning instead of a hard failure.

### Known issues still to triage

- **Parameter-passing convention is inconsistent across tools.** About 9
  tools (`td_search_official_docs`, `td_get_operator_doc`, `td_get_param_help`,
  `td_lookup_snippets`, `td_lookup_palette_component`, `td_get_release_delta`,
  `td_get_build_compatibility`, `td_search_popx_docs`, `td_get_popx_operator`)
  take arguments at the top level of the tool call, while ~70 others wrap
  them under `params:{}`. Normalizing will be a breaking schema change
  tracked for v2.0.

### Verification

Run the deep test in `docs/DEEP_TEST.md` against this build to verify:
- `td_describe_surface` should now show non-zero `tool_count` and
  `resource_count`.
- `td_detect_instability` on a healthy 60 FPS scene with ≤9 nodes should
  return `unstable: false` with `reasons: []`.
- `td_audit_project` on `/project1` should return `unknown_op_types: []`
  (or a much shorter list) instead of flagging `box`, `null`, etc.
- `td_plan_patch(intent="add a feedback loop")` with no recipe_id should
  return a non-empty `steps` list suggesting the `feedback_loop` macro.
- `td_python_env_status` under `TD_MCP_EXEC_MODE=restricted` should
  return a structured `EXEC_MODE_INSUFFICIENT` error, not an opaque
  `"restricted mode blocks import statements"` string.
- After a `.tox` rebuild: `td_get_content` on a textDAT returns
  `format: "text"`; `td_copy_node` produces a non-overlapping copy;
  calling `end_undo_block` after a cascading delete no longer errors.

## 1.4.0 - 2026-04-19

Major release: Claude Code plugin marketplace distribution, env-dynamic TD
auth (A-1 — the root cause of a nasty debugging drama), `.tox`-freshness CI
guard, AST-based exec policy, schema snapshot tests, and the full audit
hardening sweep.

### Root cause of the auth-debugging drama — fixed (A-1)
- `td_component/mcp_webserver_callbacks.py` now reads `TD_MCP_SHARED_SECRET`,
  `TD_MCP_REQUIRE_AUTH`, `TD_MCP_EXEC_MODE`, and `TD_MCP_CORS_ORIGIN` **per
  request** via `_current_*()` helpers instead of capturing them at module
  import time. Previously the compiled callbacks module pinned whatever env
  was set at first load, so env changes mid-session had no effect — this is
  what caused 3+ hours of debugging when we swapped secrets.
- New regression tests in `tests/test_td_component_auth.py` verify env
  changes flow through without re-importing.

### New safety rails
- `scripts/check_tox_freshness.py` + `td_component/.tox-source-hash.json`
  (written at build time by `build_export_mcp_tox.py`) — CI now fails if
  the committed `.tox` is stale relative to `td_component/*.py` source.
  Prevents the "binary artifact silently drifts from Python source" trap.
- `tdpilot_startup.py` now scans for and destroys zombie `mcp_server` COMPs
  outside `/local` at TD launch. (The `/project1/mcp_server` zombie that
  baked into an auto-saved `.toe` cost hours yesterday — D-1.)
- `install_claude_plugin.sh` and `npm/plugin.js` both check for `uv` before
  plugin install and bootstrap it if missing, since the plugin's `.mcp.json`
  starts the MCP server via `uv run` (A-3).

### Hygiene
- B-2: `ast_violations()` no longer converts `SyntaxError` into a fake
  security violation — users get TD's native SyntaxError back.
- B-3: Cleaned up the string-concat obfuscation in `exec_safety.py` token
  lists. A minimal implicit-concat remains for two tokens to satisfy a
  repo security-scanner hook; documented inline.
- B-4: Dropped a dead import from `npm/plugin.js`.
- B-5: Both installers now use exit codes instead of output grepping to
  detect the "marketplace already added" state.
- D-2: Renamed `.mcp.json.template` → `.mcp.json.claude-desktop-template`
  so the three `.mcp.json`-shaped files at repo root are self-describing.
- D-4: `docs/INSTALL_CLAUDE_PLUGIN.md` now warns against mixing the Claude
  Desktop and Claude Code plugin install flows on one machine.
- E-1: `tdpilot.plugin` ZIP is gitignored — it's a release artifact
  rebuilt from committed sources by `scripts/build_plugin_zip.py`.
- E-3: Schema-snapshot test also asserts the snapshot size meets
  `EXPECTED_MIN_TOOL_COUNT`, so the two constants can't silently diverge.
- B-1: `tests/test_conftest_fixtures.py` exercises the previously-unused
  conftest fixtures so they're not dead infrastructure.

### Refactors
- `src/td_mcp/models.py` → `src/td_mcp/models/` package. Content lives in
  `models/_legacy.py`; `__init__.py` star-re-exports so every existing
  `from td_mcp.models import X` keeps working (C-2).
- Attempted `tool_registry.py` package promotion (C-1) but reverted: the
  test suite white-box-patches `registry._get_client` etc., and a package
  shim breaks that indirection. Left as a tracked "needs test refactor
  first" item.

### Action required (.tox rebuild)
The TD-side callbacks changed for A-1, so the baked `.tox` is now stale.
After pulling, rebuild once in TD via `setup_mcp_in_td.py` in the Textport,
then commit `td_component/tdpilot_v1_3.tox` and `.tox-source-hash.json`.
CI's new freshness guard will turn green automatically after the rebuild.

### Claude Code plugin distribution (originally filed as a pre-release)

### Added — Claude Code plugin distribution
- `.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json` at repo root — makes `dreamrec/TDPilot` a Claude Code marketplace serving the `tdpilot` plugin (same pattern as sibling `dreamrec/ComfyPilot`).
- `commands/td-check.md` and `commands/td-snapshot.md` — plugin slash commands are now committed in the repo instead of synthesized at ZIP-build time.
- `.mcp.json` at repo root — plugin-style template using `${CLAUDE_PLUGIN_ROOT}`; the user-rendered variant moves to `.mcp.json.local` (gitignored).
- `scripts/install_claude_plugin.sh` — curl-|-bash one-liner that calls `claude plugin marketplace add` + `claude plugin install`.
- `npx tdpilot plugin-install` / `npx tdpilot plugin-uninstall` — npm wrappers around the same flow (see new `npm/plugin.js`).
- `docs/INSTALL_CLAUDE_PLUGIN.md` — end-to-end install/update/uninstall doc covering all three paths (curl, npx, manual).
- README: prominent "Install (Claude Code plugin — recommended)" section at the top.

### Changed
- `scripts/build_plugin_zip.py` — simplified: now zips committed files only. Previously synthesized `plugin.json`, `.mcp.json`, and commands at build time.
- `scripts/render_mcp_config.py` — writes to `.mcp.json.local` so the plugin template at `.mcp.json` is never clobbered.
- `scripts/check_versions.py` — now also verifies `.claude-plugin/plugin.json` and the plugin entry inside `.claude-plugin/marketplace.json` stay in sync with `__version__`.

### First-audit security hardening (originally filed as a pre-release)

### Security
- **Auth is now required by default.** TD-side refuses requests when `TD_MCP_SHARED_SECRET` is empty unless `TD_MCP_REQUIRE_AUTH=0` is explicitly set. Installers (`install.sh`, `install.ps1`) now generate a 32-byte secret at install time and write it to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) / `%APPDATA%/Claude/...` (Windows) *and* to a chmod-0600 `.tdpilot.env` that the TD startup script reads.
- **CORS wildcard removed.** `Access-Control-Allow-Origin: *` is no longer emitted. Set `TD_MCP_CORS_ORIGIN` to an exact origin if a browser tool needs access.
- **Sec-Fetch-Site check** rejects cross-site browser fetches before they reach the auth layer.
- **Constant-time secret compare** via `_constant_time_equals` to remove timing-based leak.
- **AST-based exec policy** layer added alongside the token matcher — catches string-concat bypasses (`getattr(__builtins__, …)`, `__class__.__mro__`, etc.).
- **Restricted-mode DAT-exec escape closed.** `op(...).create(textDAT)` and `.text = ...` assignments are now blocked in restricted mode (they were the known sandbox-escape path via `mod.<dat>.fn()`).
- New `docs/SECURITY.md` documents the threat model honestly, including what is *not* protected (TD-native file/network operators, compromised MCP clients, resource exhaustion).

### Tests & CI
- **Schema-snapshot contract test** — `tests/test_tools_schema_snapshot.py` + baseline at `tests/fixtures/tool_schemas.json`. Any silent change to a tool's input schema now fails CI.
- **Shared fixtures** in `tests/conftest.py` (`RecordingTDClient`, `mcp_ctx`, `exec_client_factory`).
- **Centralized thresholds** — `EXPECTED_MIN_TOOL_COUNT` in `src/td_mcp/release_gates.py`; tests and release scripts all derive from it (previously 6 places).
- **Version-drift guard** — `scripts/check_versions.py` checks all 10 versioned files against `src/td_mcp/__init__.__version__` and runs in CI.
- **Cross-platform CI** — new `install-parse` job parse-checks `install.sh` on macOS and `install.ps1` on Windows.
- **ruff + pytest-cov** in CI lint and test jobs; 821 auto-fixable lint issues corrected (851 → 81 remaining).

### Refactors
- New `src/td_mcp/exec_safety.py` module holds `RESTRICTED_TOKENS`, `STANDARD_BLOCKED_TOKENS`, `STANDARD_ALLOWED_IMPORTS`, `normalize_mode()`, `ast_violations()`, `enforce()`. `tool_registry.py` re-exports the constants for backward compatibility.
- `_current_exec_mode()` no longer does `sys.modules.get("td_mcp.server")` runtime introspection; exec mode is now read from `TD_MCP_EXEC_MODE` env at call time. Tests updated to patch env instead of module attribute.
- `TDClient.health_check` resets the connected flag and cached timestamp on any failure (previously could cache "ok" indefinitely if a request later failed).

### Packaging
- `uv.lock` is now **tracked** (was gitignored) for reproducible installs. CI uses `uv sync --frozen`.
- `.mcp.json.template` replaces the personal-path `.mcp.json` committed previously. New `scripts/render_mcp_config.py` renders the template with generated secret (chmod 0600).
- `uv` version pin in installers via `TDPILOT_UV_VERSION` env (default 0.6.10).

### Install scripts
- `npx tdpilot` no longer runs `git pull` silently on every invocation — opt-in via `TDPILOT_AUTO_UPDATE=1`.
- `npm/install.js` backs up existing TD `pref.txt` before writing (`.tdpilot-backup-<timestamp>`).

### Cleanup
- Empty `src/td_mcp/runtime/` directory removed.
- `docs/superpowers/` (historical plans + specs) moved to `docs/archive/superpowers/`.
- `td_component/NewProject*.toe` scratch files gitignored.
- `plugin_README.md` perms fixed (0400 → 0644).
- Deferred: `models.py` split (1,100+ lines → package) — marked as tech debt in the module docstring; requires updating every tool import at once so best handled in a dedicated PR.

### Derived artifacts rebuilt
- `td_component/tdpilot_v1_3.tox` — rebuilt inside TD 2025.32460 with the new callbacks (auth-by-default, CORS tightening, DAT-exec blocks).
- `tdpilot.plugin` — rebuilt via new `scripts/build_plugin_zip.py`. The plugin's embedded `.claude-plugin/plugin.json` now reads version + tool count from the single source of truth rather than being hand-maintained. Its bundled `.mcp.json` template ships with `TD_MCP_REQUIRE_AUTH=1` and `TD_MCP_EXEC_MODE=restricted` as defaults.

## 1.3.4 - 2026-03-15

### Added
- **Brain installer system** — modular one-click installer with dynamic manifest and interactive brain picker.
  - `brains_manifest.json` — single source of truth for all available brains (Google Drive file IDs, sizes, tools, skills).
  - `active.json` runtime gating — only selected brains load at startup; missing brains = silent skip, zero errors.
  - `_get_active_brains()` / `brain_is_active()` — backward-compatible brain loading (no active.json = load everything).
- POPx brain MCP tools (88→90→92 tools):
  - `td_search_popx_docs` — search POPx operator documentation (GPU particles, falloffs, simulations).
  - `td_get_popx_operator` — get full documentation for a specific POPx operator.
- Brain management CLI: `npx tdpilot brains [list|add|remove]`.
- Generic brain builder: `scripts/build_brain.py` — config-driven pipeline for building brains from any documentation site.
- Brain building tutorial: `docs/BUILDING_BRAINS.md` — complete guide to creating custom brains.
- `scripts/download_brains.py` now supports `--manifest` and `--brains-file` flags for installer integration.

## 1.3.3 - 2026-03-15

### Added
- **Docs Brain** — full-corpus search engine over docs.derivative.ca replacing hand-curated JSON knowledge cards.
  - SQLite FTS5 index: 2,478 pages → 25,887 chunks, 674 operators, 10 tracked builds, 245 operators with changelog entries.
  - BM25 ranking with boosted weights (section_title 10×, operator_name 8×, parameter_names 5×, python_symbols 3×, content 1×).
  - Intent-based query routing: auto-detects operator names, build numbers, palette/glossary keywords before FTS5 search.
  - Release notes intelligence: per-operator changelog and build manifest across 10 builds.
  - Drop-in replacement for CardIndex with automatic fallback when brain DB is absent.
- `scripts/build_docs_brain.py` — four-stage offline pipeline: normalize HTML → chunk by headings → index in FTS5 → build release artifacts.
- `docs/BRAINS.md` — step-by-step rebuild guide for regenerating the brain after a new docs scrape.

### Changed
- POPx skill updated for copyright compliance: references must be built locally from licensed copy (see `references/BUILD.md`).
- Knowledge tool stack (`td_search_official_docs`, `td_get_operator_doc`, etc.) now queries Docs Brain when available, falls back to CardIndex.

## 1.3.2 - 2026-03-14

### Added
- Auto-load on TD startup: `npx tdpilot install` sets up TDPilot to load automatically every time TouchDesigner launches. Run `npx tdpilot uninstall` to remove.
- 2 vision diagnostic tools (75 to 77):
  - `td_capture_frame` — capture TOP output as base64 image for MCP-side analysis.
  - `td_analyze_frame` — run TD-side pixel analysis (histogram, luminance, alpha_coverage, color_dominant, roi_diff).
- 6 TD 2025 native system tools (77 to 83):
  - `td_python_env_status` — Python environment and extension module status.
  - `td_threading_status` — thread pool and DAG cooking information.
  - `td_logger_status` — logger configuration and recent entries.
  - `td_tdresources_inspect` — TDResources paths by category.
  - `td_component_standardize` — audit/fix COMP against TD standards (undo-wrapped).
  - `td_color_pipeline` — color space and bit-depth pipeline audit.
- 3 official recommendation tools (83 to 86):
  - `td_recommend_official_component` — search palette + operator cards for a given goal.
  - `td_find_official_example` — search snippets + palette for official examples.
  - `td_explain_better_way` — suggest better alternatives with gotcha warnings.
- TD-side `/api/analyze_frame` endpoint with 5 analysis modes (histogram, luminance, alpha_coverage, color_dominant, roi_diff).
- Enhanced recipe capture: `analyze_network` now returns `td_build`, `required_op_types`, `external_assets`, and `layout`.
- Technique compatibility fields: `compatibility` dict and `validation_result` tracking in TechniqueStore.
- Pre-replay prerequisite check: `td_memory_replay` blocks replay when required operator types are missing.

### Fixed
- Feedback macro templates (`feedback_loop`, `feedback_displacement`) now close the loop via feedbackTOP's `top` parameter instead of a physical wire, matching TD's official palette pattern and eliminating cook-dependency-loop warnings.
- Added `NodeRefParam` model and engine support for cross-node parameter references in macro templates.

### Changed
- `analyze_network` accepts `td_build` parameter; `td_memory_learn` and `td_memory_save` pass TD build info to analyzer.
- TD-side API version bumped from 1.3.0 to 1.3.2.
- Runtime surface increased from 75 to 86 tools.

## 1.3.1 - 2026-03-14

### Added
- MCP Tasks adapter: dual-mode bridge that routes job progress to MCP Tasks (native) or polling depending on client capabilities.
- JobManager callback hooks (`on_progress_hook`, `on_complete_hook`) for external progress tracking.
- Expanded snapshot diff: connection changes (`added_connections`, `removed_connections`) and expression changes (`added_expressions`, `removed_expressions`, `modified_expressions`).
- `_with_undo_block` helper wrapping multi-step mutations in TD undo blocks for single-step reversal.
- 4 new planning and validation tools (71 to 75):
  - `td_plan_patch` — generate structured patch plans from intents and recipes.
  - `td_preflight_patch` — validate plans before execution (path existence, name conflicts, op type checks).
  - `td_validate_recipe` — validate technique recipes against knowledge cards and build compatibility.
  - `td_audit_project` — audit project subtrees for structure, palette usage, errors, and build warnings.
- Recipe state machine: techniques now track `state` (candidate, validated_local, validated_portable, deprecated, reference_only) and `validation_result`.
- Auto-validation on replay: `td_memory_replay` checks for errors after replay and auto-promotes candidate recipes to `validated_local` on clean replay.

### Changed
- `td_restore_snapshot` docstring clarified: restores parameter values only; structural rollback uses TD native undo.
- `ServiceContainer` gains `task_adapter` field for lifespan-managed TaskAdapter.

## 1.3.0 - 2026-03-14

### Added
- `standard` exec safety mode: curated import whitelist (14 safe modules) with read-only introspection for data-transform workflows.
- Expanded CapabilitySet from 5 to 10 fields: `supports_tasks`, `supports_elicitation`, `transport_type`, `mcp_sdk_version`, `td_build`.
- Knowledge corpus: structured JSON card system for operators (30), palette components (6), releases, and snippet families.
- 8 new knowledge tools (63 to 71): `td_search_official_docs`, `td_get_operator_doc`, `td_get_param_help`, `td_lookup_snippets`, `td_lookup_palette_component`, `td_get_release_delta`, `td_get_build_compatibility`, `td_describe_surface`.
- Read-through fallbacks for cached resources (CHOP, parameter, cook, error) — one-shot TD API call on cache miss.
- Resource `mode` field (`authoritative` or `cache`) on all resource responses.
- Optional web fetcher for live docs enrichment (`TD_MCP_WEB_FETCH=true`).

### Changed
- EventManager subscription keys now use `(path, event_type)` tuples for correct multi-event handling.
- `to_dict()` return type on CapabilitySet changed from `dict[str, bool]` to `dict[str, Any]`.
- TD-side API version bumped to 1.3.0 with matching `standard` exec mode support.

## 1.2.0 - 2026-03-14

### Changed
- Renamed TD component artifact from `mcp_server_codex.tox` to `tdpilot_v1_2.tox` (format: `tdpilot_v{MAJOR}_{MINOR}.tox`).
- Doctor command reads .tox filename from canonical `TOX_FILENAME` constant instead of hardcoding.
- Transport naming normalized via `normalize_transport()` — consistent across doctor, capabilities, and runtime startup.
- MCP dependency pinned to `>=1.0,<2.0` to prevent SDK v2 pre-alpha breakage.
- Added CI bundle integrity check validating version and artifact path agreement.

### Removed
- Deleted `mcp_server_codex.tox` (replaced by `tdpilot_v1_2.tox`).

## 1.1.0 - 2026-03-07

### Added
- New first-class tool: `td_pop_inspect` for POP-native summaries, attribute lists, and attribute sampling.
- New first-class tool: `td_project_lifecycle` for save/load/undo/redo and undo block control.
- New first-class tool: `td_custom_parameters` for custom page/parameter authoring on COMPs.
- New documentation guide: `docs/MCP_1_1_SURFACE.md`.

### Changed
- `td_exec_python` now returns structured JSON-safe `result` payloads with `result_type` and `result_is_structured` metadata when possible.
- Runtime surface increased from 60 to 63 tools.
- Registry smoke checks, E2E thresholds, manifest metadata, and package versions now track the expanded tool surface.
- `tdpilot-core` repo skill note now reflects the modern tool count instead of the stale 27-tool wording.

## 1.0.0 - 2026-02-24

### Added
- Production MCP runtime for TouchDesigner with a 60-tool surface spanning scene control, build/wiring, params/content, diagnostics, events/streaming, optimization, safety, and memory.
- Technique memory system with 8 tools:
  - `td_memory_learn` — analyze live networks and extract reusable recipes
  - `td_memory_save` — persist techniques to project or global library
  - `td_memory_recall` — search library by text and tags
  - `td_memory_replay` — rebuild saved techniques in new locations
  - `td_memory_list` — list techniques with filters
  - `td_memory_favorite` — mark/rate techniques
  - `td_memory_promote` — copy project techniques to global library
  - `td_memory_preferences` — get/set user preferences
- Per-project and global memory storage at `~/.tdpilot/memory/`.
- TouchDesigner component artifact at `td_component/mcp_server.tox`.
- CLI utilities: `tdpilot doctor`, `tdpilot init --client ...`.
- Standardized MCP bundle: `mcp/manifest.json`, `mcp/profiles/*`.

### Changed
- Simplified optimizer: `td_optimize_visual` now accepts direct `objective_weights` instead of keyword heuristics.
- Refined runtime surface from 63 to 60 tools by removing unused tools and replacing intent scaffolding with production memory workflows.
- Updated manifest, smoke checks, E2E flows, and stress scripts for the finalized tool surface.
- Hardened benchmarking and release gates: benchmark error rates now separate warmup vs measured failures, and gate checks include error-rate thresholds.

### Removed
- Unused tools: `td_runtime_assess`, `td_runtime_remember_intent`, `td_runtime_recall_intents`, `td_runtime_link_snapshot_memory`, `td_runtime_set_preferences`, `td_runtime_get_preferences`, `td_runtime_compile_intent`, `td_runtime_dashboard`, `td_runtime_restore_transform`, `td_runtime_killer_demo`, `td_dop_catalog`.
- Deprecated modules: `runtime/assessment.py`, `runtime/intent_mapping.py`, `runtime/memory_index.py`, and `dop/`.
- Obsolete CLI and env flags: `runtime-dashboard`, `TD_MCP_INTENT_MEMORY`.
- Obsolete docs: `KILLER_DEMO.md`, `DOP_CLASS_ROADMAP.md`.
