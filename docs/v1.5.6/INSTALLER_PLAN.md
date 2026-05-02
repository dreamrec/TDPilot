# Plan: One-Button Install + Update via .tox

**Status:** draft, awaiting sign-off
**Target release:** v1.5.6
**Last updated:** 2026-05-02

---

## 1. What we're trying to achieve

**Single-file UX for first-time users.** Download `tdpilot.tox`, drag into
TD, click one button on the COMP's custom params, all install paths
complete:

- Python wrapper (`~/.tdpilot/`) cloned/extracted
- `uv` toolchain installed if missing
- Claude Code plugin registered (marketplace + plugin install)
- TD prefs written so the .tox auto-loads on next launch
- Shared secret generated, env file written
- Project saved as the auto-load .toe
- Status panel shows real-time install progress

**Single-click updates for existing users.** Once installed, the panel
auto-detects when a new version is available. One click pulls the new
.tox, refreshes the Python wrapper, updates the Claude Code plugin, and
re-saves the autoload .toe. Rollback to the previous version is one
click away if something breaks.

**Non-goals (this iteration):**
- Claude Desktop install path (different mechanism — separate phase if
  wanted)
- Windows-first testing (target macOS first, design Windows-compatible,
  validate later)
- Multi-version side-by-side installs (latest wins, prior version is
  backup-only)

---

## 2. What already exists

Mapped during investigation in `npm/run.js`, `npm/install.js`,
`npm/plugin.js`, `setup_mcp_in_td.py`, `src/td_mcp/auth_bootstrap.py`,
`tdpilot.mcpb/manifest.json`, and the existing tdpilot containerCOMP:

| Capability | Lives in | Reuse strategy |
|---|---|---|
| Clone repo + checkout latest tag | `npm/run.js:ensureRepo` | Port to Python (uses `git`/`curl` shellouts, both have Python equivalents) |
| Install `uv` | `npm/run.js:installUv` | Same — port to subprocess.run |
| Write `~/.tdpilot_path` + TD pref.txt | `npm/install.js` | Port directly — pure file I/O |
| Add Claude Code marketplace + install plugin | `npm/plugin.js` | Shell out to `claude` CLI |
| Generate shared secret, write `.tdpilot.env` | `auth_bootstrap.maybe_generate_secret` | Reuse — already pure Python |
| Build .tox from source if missing | `td_component/build_export_mcp_tox.py` | Already runs in TD |
| Save current state as auto-load .toe | `project.save(path)` | TD API call we already use |

**None of this is new logic** — it's a port of `npm/run.js` +
`npm/install.js` + `npm/plugin.js` from Node into TD's Python, plus a
custom params UI to drive it.

---

## 3. Architecture

### 3.1 Inside the `tdpilot` containerCOMP

Add three new pieces alongside the existing `mcp_server` / `status_text` /
`renderer` / `autostart`:

```
/project1/tdpilot
├── (existing)
│   ├── mcp_server/        (the MCP runtime; unchanged)
│   ├── status_text        (panel TOP; unchanged)
│   ├── renderer           (panel renderer; unchanged)
│   └── autostart          (executeDAT; unchanged)
├── installer              (textDAT — pure-Python install logic)
├── installer_exec         (parexec DAT — wires custom param pulses to installer.module calls)
└── (custom params on tdpilot itself, see §3.2)
```

### 3.2 Custom params — two pages

#### Page "Install"

| Param | Style | Purpose |
|---|---|---|
| `Install_status` | Str (read-only) | "Not installed" / "Installing…" / "Ready" / "Error: …" |
| `Bootstrap_all` | Pulse | One-click install everything |
| `Install_python_wrapper` | Pulse | Just clone + uv setup |
| `Install_claude_plugin` | Pulse | Just register with Claude Code |
| `Set_td_autoload` | Pulse | Just write TD prefs + save .toe |
| `Uninstall_all` | Pulse | Reverse everything |
| `Detect_state` | Pulse | Re-run state probe, refresh status |
| `Repo_url` | Str | Default `https://github.com/dreamrec/TDPilot.git` (override for forks) |
| `Pin_to_tag` | Toggle | If on, checkout latest tag; if off, stay on main |

#### Page "Update"

| Param | Style | Purpose |
|---|---|---|
| `Installed_version` | Str (read-only) | e.g. "1.5.6" — populated from `~/.tdpilot/pyproject.toml` |
| `Latest_version` | Str (read-only) | e.g. "1.5.7" — fetched from GitHub Releases API |
| `Update_status` | Str (read-only) | "Up to date" / "Update available: 1.5.7" / "Updating…" / "Update failed (rolled back): …" |
| `Check_for_updates` | Pulse | Hit GitHub API, refresh `Latest_version` and `Update_status` |
| `Update_now` | Pulse | Pulls latest .tox + wrapper + plugin, re-saves autoload .toe |
| `Rollback` | Pulse | Restores the previous version from backup (only enabled if a backup exists) |
| `Auto_check_on_load` | Toggle | If on, `Check_for_updates` fires from `autostart.onStart` (default: on) |
| `Backup_dir` | Str (read-only) | `~/.tdpilot/backups/<timestamp>/` — shows where the last backup lives |

### 3.3 `installer.module` API

Pure Python, runs in TD's normal (unrestricted) Python thread:

```python
detect_state() -> dict
    # {
    #     "uv": "/path/to/uv" or None,
    #     "git": "/path/to/git" or None,
    #     "claude_cli": "/path/to/claude" or None,
    #     "repo_at_home": True/False,                   # ~/.tdpilot/pyproject.toml exists
    #     "repo_version": "1.5.3" or None,
    #     "td_prefs_set": True/False,                   # pref.txt points at autoload .toe
    #     "autoload_toe_exists": True/False,
    #     "claude_plugin_installed": True/False,        # via reading installed_plugins.json
    #     "secret_present": True/False,
    # }

bootstrap_all(progress_cb)        # orchestrates, calls progress_cb(stage, message)
install_python_wrapper(progress_cb)
install_claude_plugin(progress_cb)
set_td_autoload(progress_cb)
uninstall_all(progress_cb)

# Update API (see §5 for orchestration detail)
check_for_updates() -> dict
    # {
    #     "installed": "1.5.6",
    #     "latest": "1.5.7",
    #     "update_available": True,
    #     "release_url": "https://github.com/dreamrec/TDPilot/releases/tag/v1.5.7",
    #     "release_notes": "…first 500 chars of release body…",
    # }

update_now(progress_cb)           # downloads + installs latest, see §5
rollback(progress_cb)             # restores previous version from backup
```

Each function returns `(success: bool, message: str)`.

The `progress_cb` updates the `Install_status` (or `Update_status`)
custom param so the user sees live progress on the panel.

### 3.4 New panel row

Add an "Install" line to the status panel renderer — shows the live
`Install_status` value. So the same panel that shows
`WS / Latency / Tools / POPx` now also shows `Install Ready` (or
`Install (stage 2/5: cloning repo)`).

### 3.5 Distribution

Two artifacts shipped per release:
- `tdpilot.tox` — current 36KB self-contained COMP **plus** the new
  installer logic
- `tdpilot.mcpb` — unchanged Claude Desktop bundle (separate channel)

User downloads tdpilot.tox alone for the one-button-install path.

**The COMP must save with `enableexternaltox=True`.** This makes the
.toe store only the path to the `tdpilot.tox` file, not the baked-in
content. Future updates become "replace `~/.tdpilot/td_component/tdpilot.tox`,
restart TD" — TD's documented externaltox mechanism handles the reload
on next project load. See §5.3.1.

This is a one-line change at install time but has architectural impact
on Phases A–D: the installer must verify `reloadcustom=True` and
`reloadbuiltin=True` so custom params survive .tox swaps. Phase A test
specifically validates this.

---

## 4. Orchestration sequence (the critical 30 seconds)

What `Bootstrap_all` runs through, and what could go wrong at each step:

| # | Stage | Action | Failure mode | Recovery |
|---|---|---|---|---|
| 1 | Detect | Probe what exists | — | always succeeds |
| 2 | Install uv | `curl … \| sh` if missing | curl/network/perms fail | Show actionable error, halt |
| 3 | Clone repo | `git clone` to `~/.tdpilot/` | git missing → fall back to zip download | If both fail: halt with error |
| 4 | Sync deps | `uv sync --directory ~/.tdpilot` | network/disk | retry once, then halt |
| 5 | Generate secret | Write `~/.tdpilot/.tdpilot.env` | disk full / perms | halt |
| 6 | Register Claude plugin | `claude plugin marketplace add` + `plugin install` | `claude` CLI not on PATH | fall back to printing manual command |
| 7 | Write TD prefs | Write `pref.txt` with autoload pointer | TD prefs locked | halt with error |
| 8 | Save .toe | `project.save(autoload_path)` | save fails | halt |
| 9 | Done | Update status, prompt "Restart Claude Code" | — | — |

Each stage is **idempotent** — running `Bootstrap_all` twice should be a
no-op on the second run, not a re-clone or duplicate plugin entry.

---

## 5. Update strategy (the second critical 30 seconds)

### 5.1 Detecting updates

`check_for_updates()` queries `https://api.github.com/repos/dreamrec/TDPilot/releases/latest`
once. From the response we extract:
- `tag_name` (e.g. `v1.5.7`) → strips the `v` prefix to get `Latest_version`
- `assets[]` → finds the `tdpilot.tox` attachment URL
- `body` → first 500 chars become `release_notes` for the panel

`Installed_version` comes from parsing `~/.tdpilot/pyproject.toml`'s
`version = "X.Y.Z"` line. No git invocation needed — file read only.

If `Latest_version > Installed_version` (semver compare), set
`Update_status = "Update available: <latest>"` and enable the
`Update_now` button. Otherwise `"Up to date"`.

If `Auto_check_on_load = True` (default), `autostart.onStart()` calls
`check_for_updates()` once per project load — same Frame 0, before the
panel paints. Network call has 5s timeout; if it fails (offline,
GitHub rate-limit), `Update_status` stays at last known value and a
`(check failed)` suffix is appended. Never blocks the panel render.

**Cache TTL: 24 hours.** Result cached at `~/.tdpilot/last_check.json`
with timestamp. If cache is fresher than 24h, skip the API call and reuse
the cached value (panel still renders accurate status). Releases ship at
most weekly; a 24h TTL means at most ~30 API calls/month per machine,
well below the unauthenticated GitHub limit of 60/hr per IP. A
forced-refresh path (manual pulse of `Check_for_updates`) bypasses the
cache.

### 5.2 What "Update Now" actually does

`Update_now` is structured to be **safe by construction** — every step
either succeeds idempotently or rolls back cleanly. The orchestration:

| # | Stage | Action | Failure mode | Recovery |
|---|---|---|---|---|
| 1 | Snapshot | Copy `~/.tdpilot/` → `~/.tdpilot/backups/<timestamp>/` (lightweight: hardlinks where filesystem supports them) | disk full | halt before any change |
| 2 | Backup .toe | Copy current `tdpilot_default.toe` → `<backup>/tdpilot_default.toe` | — | halt |
| 3 | Pull latest | `git -C ~/.tdpilot fetch --tags && git checkout vX.Y.Z` (or zip fallback) | network/conflict | restore from backup, halt |
| 4 | Sync deps | `uv sync --directory ~/.tdpilot` | network/disk | restore from backup, halt |
| 5 | Update plugin | `claude plugin update tdpilot@dreamrec-TDPilot` (only if Claude CLI present) | CLI missing | print manual cmd, continue (non-fatal) |
| 6 | Stage new .tox | Download new `tdpilot.tox` from release asset → `~/.tdpilot/td_component/tdpilot.tox` (overwrites existing file) | download fail | restore from backup, halt |
| 7 | Mark for reload | Set `enableexternaltox=True` on the live COMP and call `enableexternaltoxpulse` so TD's externaltox machinery picks up the new file content on next project load. Optionally also reload it now via the COMP's reload mechanism, which is the **supported** TD path | — | — |
| 8 | Re-save .toe | `project.save(autoload_toe_path)` — preserves the externaltox link (not the baked content) | save fail | restore .toe from backup, halt |
| 9 | Done | Update panel: "Updated to <new>. Restart TD to load new tools, then restart Claude Code." | — | — |

Total wall-clock target: **under 20 seconds** for the file/network work,
plus a 5-second TD restart on the user's side.

### 5.3 Why we restart TD instead of swapping in-place

An earlier draft of this plan described "in-place .tox swap" via
`parent.loadTox()` mid-execution. That pattern works in TD 2025.32460
(we used it once during this session's debugging) but it's:

1. **Undocumented by Derivative** — relies on the executing Python frame
   surviving its containing COMP's destruction. Future TD versions could
   change this without warning.
2. **Hostile to mid-flight MCP requests.** If Claude Code is in the
   middle of a tool call when the user clicks Update, destroying
   `mcp_server` mid-request kills the in-flight HTTP connection.
3. **Saves only ~5 seconds of wall-clock time** vs. a clean restart.

**Decision: always require a TD restart after updates.** The trade-off is
worth it for the safety + supportability win. Implementation is also
much simpler: stage the new .tox, save .toe, show "Restart TD" message,
done.

The `externaltox` mechanism (TD's documented external-content pattern)
gives us this almost for free. If we keep `enableexternaltox=True` on
the saved COMP, the .toe stores only the external path; TD reads the
current `tdpilot.tox` file every time it opens the .toe. Then "update"
is just "replace the .tox file on disk" — TD picks it up on next launch.
See §3.5.

### 5.3.1 Architecture implication: keep `enableexternaltox=True`

**This is a change from the current saved .toe**, where
`enableexternaltox` is False (the COMP content is baked in). We need to
flip it to True before §5.2 step 8. One-line change to the COMP at
install time. Means future updates can be as light as "drop a new .tox
into `~/.tdpilot/td_component/`" — no .toe regeneration needed at all.

The trade-off: external-tox COMPs lose their custom params on reload
unless `reloadcustom=True`. We need to verify the panel state and
installer state survive the reload. (Phase A test will catch this.)

### 5.4 Rollback

`Rollback` reverses the same steps in reverse order:

1. Find most recent `~/.tdpilot/backups/<timestamp>/`
2. Restore `~/.tdpilot/` from backup (or use git to checkout the prior
   tag if backup is a hardlinked tree)
3. Restore `tdpilot_default.toe` from backup
4. Optionally `claude plugin install tdpilot@dreamrec-TDPilot@<old-version>`
   if the CLI supports version-pinned installs
5. Reload .tox into the COMP
6. Update panel: "Rolled back to <old version>"

Rollback is **always offered after a failed update**, and is also
available as a manual-revert option (e.g. "the new version broke a tool I
was using").

Backups beyond N=3 are pruned automatically to avoid disk bloat.

### 5.5 Update notification UX

The panel gets a new bottom row that shows on the same `status_text` TOP:

```
TDPilot 1.5.6                   ← header
────────────────────────
WS          OK
Latency     7 ms
Tools       102
Snapshots   --
Memory      --
Knowledge   --
POPx        installed 1.2.1
Build       2025.32460
Last call   /api/screenshot
Update      ▲ 1.5.7 available    ← NEW row, only shown when update_available
```

The `▲` (or similar glyph) makes the update visible at a glance. Clicking
into the COMP's custom params and pressing `Update_now` is the user's
next action.

When up to date, the row reads `Update      ✓ up to date` (or is hidden,
TBD).

---

## 6. Subprocess strategy (the gotcha)

TD's Python runs as a child of the TD app, with limited PATH. Things that
work in a terminal (`git`, `claude`, `uv`) might not be on TD's PATH. The
installer needs to:

1. **Augment PATH** before subprocess calls. Add `~/.local/bin`,
   `/opt/homebrew/bin`, `/usr/local/bin`, `~/.bun/bin` (Claude Code's
   location on some installs).
2. **Probe with `which`/`where`** before running, fail with a useful
   message if missing.
3. **Use absolute paths where possible** once probing finds them.
4. **Run subprocesses non-blocking** — TD's main thread is the render
   thread; long subprocess waits will freeze the UI. Use
   `subprocess.Popen` + a poll loop in `onFrameStart`, OR a TD
   `threadingDAT`. **Decision: threading**, because the install can take
   30+ seconds (clone + uv sync) and a 30s frozen UI is worse than the
   threading complexity.

---

## 7. Phasing

Four deliverables, each independently shippable:

### Phase A — Detect-only (smallest scope, validates everything)

Just the `Detect_state` button + the new "Install" panel row + read-only
version display on the "Update" page (no network call yet). Confirms:
- Custom params + parexec wiring works
- `installer.module` can read all the right files
- Panel can show installer/update state

**Estimated effort:** 2 hours. Lets us catch UI/wiring issues before
writing real install logic.

### Phase B — Local-only install (no Claude Code yet)

`Install_python_wrapper` + `Set_td_autoload` + `Uninstall_all`. Skips
Claude Code entirely. Result: TDPilot runs as a self-contained TD MCP
server that you can talk to via the MCP wrapper, BUT the user still has
to wire Claude Code manually (or via existing
`npx tdpilot plugin-install`).

**Estimated effort:** 4 hours. Validates the subprocess+threading
architecture on the easier (file-only) path before tackling the cross-app
`claude` CLI step.

### Phase C — Full one-button bootstrap

`Install_claude_plugin` + `Bootstrap_all` orchestrator. The "drag and
click" flow.

**Estimated effort:** 3 hours. Mostly subprocess shellout + error
handling + the Claude CLI fallback message.

### Phase D — One-click updates with rollback

`check_for_updates` + `update_now` + `rollback` + the auto-check at
project load + the "Update available" panel row. Reuses Phase B/C
plumbing for the actual install steps; new code is the GitHub API call,
the .tox self-replacement trick (§5.3), and the backup/restore logic.

**Estimated effort:** 4 hours. The trickiest part is the in-place .tox
swap and validating that rollback works end-to-end. Backup-restore tests
must run on real installs, not mocks.

**Total: ~13 hours of work, split into 4 independently testable phases.**

Phase D is the new addition — without it, users have to keep running
`npx tdpilot` from a terminal to update, which negates the "no terminal
ever" promise of the .tox install path.

---

## 8. Risks requiring explicit sign-off

1. **Auth model after install — and the secret-generation conflict.**
   Right now the COMP forces `TD_MCP_REQUIRE_AUTH=0` on every load. If
   the installer runs `auth_bootstrap.maybe_generate_secret()`, the
   secret is wasted bytes — autostart's bypass overrides it next frame.
   Worse, if we ever flip the bypass off without coordinating, the live
   wrapper has a different secret than the regenerated `.tdpilot.env`
   and every request fails 401 (the exact bug we spent two hours
   debugging earlier in this session).

   **Decision: installer skips secret-generation entirely.** The
   `Install_python_wrapper` action will set up `~/.tdpilot/` and run
   `uv sync`, but will not call `maybe_generate_secret`. The `.tdpilot.env`
   file is created with `TD_MCP_REQUIRE_AUTH=0` and `TD_MCP_EXEC_MODE=restricted`
   only. Panel shows: "Auth: disabled (single-user local mode)."

   To re-enable canonical auth (multi-user shared-machine setups), a
   power-user toggle on the Install params page sets `Disable_auth=False`,
   removes the bypass call from autostart, and runs secret-gen. This is
   a v1.5.7 follow-up — for v1.5.6 the toggle exists but is read-only-on
   so the simple path is the only path.

2. **`claude` CLI dependency.** Phase C requires Claude Code's CLI on
   PATH. On macOS that's typically `/Users/<u>/.bun/bin/claude` — not on
   TD's spawn PATH by default. If we can't find it, we degrade to
   printing the manual install command. **Acceptable?**

3. **Network at install time.** Cloning the repo + downloading uv
   requires internet. Offline install isn't supported — we'd need to
   bundle the full Python wrapper in the .tox or alongside it
   (significantly larger). **Recommend: online-only for v1, document the
   offline workaround.**

4. **Where does `tdpilot.tox` live for distribution?** Currently it's a
   build artifact in the repo. Options:
   - GitHub Release attachment (clean, but adds release-step manual
     work)
   - Direct GitHub raw-content URL (works, but versioning is per-commit
     not per-release)
   - npm-published asset (consistent with existing channel)
   **Recommend: GitHub Release attachment. Updates via "check for
   updates" button later.**

5. **Threading risk.** TD's threading model has known footguns (UI thread
   vs cook thread vs Python thread). If subprocess threading proves flaky
   in practice, fall back to a non-threaded "click-and-wait" UI with a
   spinning indicator. **Plan for the threaded version, accept the
   fallback if testing shows UI freezes.**

6. **Reversibility.** Uninstall must be perfect. If a user clicks
   Bootstrap once and decides they don't want it, we need to put their TD
   prefs back, remove the autoload .toe, deregister the plugin, and
   remove `~/.tdpilot/`. The current `npm/install.js:uninstall` is the
   model — reproduce its exactness.

7. **GitHub API rate limits.** Unauthenticated calls to
   `api.github.com/repos/dreamrec/TDPilot/releases/latest` are limited to
   60/hr per IP. With `Auto_check_on_load=True`, every TD launch costs
   one request. Acceptable for individuals; edge case is a
   shared/CI machine running TD repeatedly. **Recommend: cache the
   `latest_version` result in `~/.tdpilot/last_check.json` for 1 hour;
   skip API call if cache is fresh. Show stale data with timestamp if
   network fails.**

8. **In-place .tox swap during update.** §5.3 describes the
   `parent.loadTox()` trick to replace the running COMP. This is
   structurally sound but unusual — TD doesn't officially document this
   pattern. Risk: future TD release changes the semantics and a
   self-update bricks the COMP mid-flight. Mitigation: the backup made
   in step 1 of `update_now` lets a user manually swap the .tox file in
   `~/.tdpilot/td_component/` and restart TD as a recovery path. **Plan:
   in-place swap as primary; "restart TD" as the documented fallback.**

---

## 9. Success criteria

- **Phase A:** panel shows correct install state for all four scenarios —
  fresh machine, partial install, full install, Claude-only install.
- **Phase B:** clicking "Install Python Wrapper" on a fresh machine
  results in a working `~/.tdpilot/` with `uv sync` complete, and "Set TD
  Autoload" makes the .tox auto-load on next TD restart.
- **Phase C:** on a fresh Mac with TD + Claude Code already installed but
  no TDPilot, dragging in tdpilot.tox and clicking "Bootstrap All" — wait
  30s — restart Claude Code — talk to TDPilot. Zero terminal commands.
  Zero textport edits.
- **Phase D:** on a machine with TDPilot 1.5.6 installed, releasing
  1.5.7 → next TD launch shows "Update available: 1.5.7" in the panel
  within 5s of project load. User clicks `Update_now`, sees live
  progress, ends up on 1.5.7 within 30s. If we deliberately corrupt the
  download mid-flight, `Rollback` returns them to 1.5.6 with no
  user-visible damage. Zero terminal commands required for either path.

---

## 10. Decisions needed before starting

- **Sign-off on risks 1–6** (especially 1: auth bypass forever, and 4:
  distribution channel).
- **Phase to start with.** Recommend A, but if you want to skip straight
  to B that's fine — A is mostly there because it's de-risk-y.
- **Where to write the installer code.**
  - Option (a): inside the .tox as a Text DAT (current pattern,
    self-contained).
  - Option (b): port the npm scripts into `td_component/installer.py` and
    have the .tox embed it during build (matches how
    `tdpilot_startup.py` is treated).

  **Recommend (b)** — keeps installer logic in version control as Python
  rather than serialized into the .tox binary.

---

## 11. Open questions for follow-up

- Should the installer also offer to install brain DBs (`npx tdpilot
  brains`)? They're optional but improve TDPilot quality. Could fit in
  Phase D as another Update-page option, or defer to v1.5.7.
- Multi-user install scope — `--user` (default) vs `--global` vs
  `--project`? Current install.js uses user scope; we'd inherit that.
- Update channel — stable releases only, or opt-in to pre-release tags?
  GitHub Releases API has a `prerelease=true` flag we can filter on. For
  v1.5.6 default to stable; expose a "Use pre-release builds" toggle on
  the Update params page for power users.
- Notification persistence — should the "Update available" badge stay
  visible until acted on, or auto-clear after first display? Recommend
  sticky until `Update_now` or explicit dismiss button.
