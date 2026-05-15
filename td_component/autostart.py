"""TDPilot autostart — disable auth, refresh installer state, tick panel.

Self-sufficient: this runs from inside the dragged-in / loaded tdpilot
COMP, so it does NOT depend on the launcher .toe's tdpilot_startup.py
having executed. Drop the .tox into any project and you get a working
panel without textport gymnastics.

onStart()       fires once on project load. Permanently disables MCP
                shared-secret auth (single-user local dev — see comment
                in _disable_auth). Then refreshes installer state and
                renders the panel's first frame.
onFrameStart()  refreshes the panel once per second, polls the
                installer's job state every frame to surface live
                progress, and executes any pending main-thread actions
                the installer's bg thread requested (e.g. project.save).
"""

import os

PANEL_TICK_EVERY_N_FRAMES = 60  # 1Hz at 60fps for cheap renders
INSTALLER_REFRESH_EVERY_N_FRAMES = 60 * 60  # 1×/min — installer state changes rarely
INSTALLER_PROGRESS_EVERY_N_FRAMES = 6  # 10Hz — show live progress during a job


def _disable_auth():
    """See comment in plan §8 risk #1 — bypass auth for single-user local mode."""
    os.environ.pop("TD_MCP_SHARED_SECRET", None)
    os.environ["TD_MCP_REQUIRE_AUTH"] = "0"


def _tick():
    r = parent().op("renderer")
    if r is not None:
        try:
            r.module.tick()
        except Exception as exc:
            print("[TDPilot autostart] tick failed:", exc)


def _bootstrap():
    r = parent().op("renderer")
    if r is not None:
        try:
            r.module.bootstrap()
        except Exception as exc:
            print("[TDPilot autostart] bootstrap failed:", exc)


def _refresh_installer():
    """Probe install state and push to custom params. Cheap, cached."""
    installer = parent().op("installer")
    if installer is None:
        return
    try:
        installer.module.refresh_status_params()
    except Exception as exc:
        print("[TDPilot autostart] installer refresh failed:", exc)


def _poll_installer_progress():
    """Update Install_status from the bg job's progress message."""
    installer = parent().op("installer")
    if installer is None:
        return
    try:
        state = installer.module.get_job_state()
    except Exception:
        return
    if state.get("name") is None:
        return
    if not state.get("done"):
        try:
            parent().par.Installstatus = state.get("message") or state.get("stage") or "Working..."
        except Exception:
            pass
    else:
        if state.get("success"):
            try:
                parent().par.Installstatus = state.get("message") or "Done"
            except Exception:
                pass
        elif state.get("error"):
            try:
                parent().par.Installstatus = "Error: " + str(state["error"])[:120]
            except Exception:
                pass


def _execute_pending_main_thread_action():
    """Bridge bg thread → main thread for ops that aren't thread-safe in TD.

    Currently supports:
      "save_toe" — set externaltox on this COMP, then project.save() to the
                   installer's CURRENT autoload path. v1.6.6 added the
                   externaltox step (see _save_toe_with_externaltox docstring
                   for the architecture rationale — closes the "panel still
                   says 1.5.3 after restart" bug class permanently).
      "save_toe_pin_current" (v1.6.10) — same recipe as save_toe, but the
                   target is the CURRENTLY-OPEN .toe (project.folder +
                   project.name), not the canonical autoload. Generalizes
                   v1.6.6's protection to arbitrary user projects (closes
                   the "panel stuck on old version in user .toe" gap).

    IMPORTANT: we call installer.module.autoload_toe() (the FUNCTION) not
    installer.module.AUTOLOAD_TOE (the constant). The constant is captured
    at module-load time and won't follow TDPILOT_INSTALL_DIR overrides set
    later in the session. The function re-reads env vars on each call and
    is the only safe way to honor sandbox redirects during testing.
    """
    installer = parent().op("installer")
    if installer is None:
        return
    try:
        action = installer.module.consume_pending_main_thread_action()
    except Exception:
        return
    if action is None:
        return

    if action == "save_toe":
        try:
            target = installer.module.autoload_toe()  # FUNCTION, not constant
            externaltox_set = _save_toe_with_externaltox(installer, target)
            print(
                "[TDPilot autostart] saved autoload .toe to "
                + str(target)
                + (" (externaltox set)" if externaltox_set else " (externaltox skipped)")
            )
            installer.module.mark_pending_action_done(success=True)
        except Exception as exc:
            print("[TDPilot autostart] save_toe failed:", exc)
            try:
                installer.module.mark_pending_action_done(success=False, error=str(exc))
            except Exception:
                pass
    elif action == "save_toe_pin_current":
        # v1.6.10: pin THIS open project (not the canonical autoload).
        # Refuses to save if the project hasn't been saved yet (project.name
        # would be the unsaved-default like "untitled.toe") — reopening an
        # unsaved file isn't meaningful.
        try:
            current_path = os.path.join(project.folder, project.name)
            if not os.path.isfile(current_path):
                raise RuntimeError(
                    "Cannot pin unsaved project. File > Save the .toe first, then click 'Pin this project'."
                )
            externaltox_set = _save_toe_with_externaltox(installer, current_path)
            print(
                "[TDPilot autostart] pinned current project at "
                + str(current_path)
                + (" (externaltox set)" if externaltox_set else " (externaltox skipped — .tox missing?)")
            )
            installer.module.mark_pending_action_done(success=True)
        except Exception as exc:
            print("[TDPilot autostart] save_toe_pin_current failed:", exc)
            try:
                installer.module.mark_pending_action_done(success=False, error=str(exc))
            except Exception:
                pass
    else:
        print("[TDPilot autostart] unknown pending action:", action)
        try:
            installer.module.mark_pending_action_done(success=False, error="unknown action: " + str(action))
        except Exception:
            pass


def _save_toe_with_externaltox(installer, target):
    """Set externaltox on parent() COMP before saving, then project.save.

    Returns True if externaltox was set (and the future TD launches will
    auto-load fresh .tox content from disk), False if we couldn't set it
    (in which case the .toe still works, just embeds the current COMP
    content like before — the v1.6.5-and-earlier behavior).

    v1.6.6 architecture (closes the "panel still says 1.5.3 after restart"
    bug class permanently):

      Pre-v1.6.6: ``project.save`` baked the entire current /project1/tdpilot
      COMP (with whatever API_VERSION was current at save time) into the
      .toe file. Future TD launches restored that frozen content. To get a
      newer .tox into the running COMP required either (a) the v1.6.5
      Startup-script sweep (which fights TD's startup ordering — Startup
      scripts run BEFORE the .toe loads, so the sweep can't see /project1
      yet, and the .toe restore wipes whatever the sweep loaded into /local)
      or (b) a manual destroy + loadTox + project.save sequence (what the
      user had to do once via Textport to recover from the v1.6.4/5 mess).

      v1.6.6: before project.save, set the COMP's externaltox parameter to
      the on-disk .tox path. Then save WITHOUT saveExternalToxs=True so the
      COMP content is NOT embedded — only the path reference. Every future
      TD launch reads the latest .tox content fresh from disk.

      Net effect: a v1.6.6 user clicks "Update Now" once. From that point
      forward, ``npx tdpilot@latest`` + restart-TD = panel updates
      automatically. No manual sweeps, no Textport gymnastics, no ordering
      races. The Startup-script sweep (v1.6.5) becomes belt-and-suspenders
      defense for users whose .toe somehow gets out of sync.
    """
    comp = parent()
    if comp is None:
        # Shouldn't happen — autostart is always inside the tdpilot COMP —
        # but if it did, fall back to plain save so we don't lose data.
        project.save(target)
        return False

    # Compute the canonical .tox path the installer is managing.
    try:
        install_dir = installer.module.install_dir()
        tox_path = os.path.join(install_dir, "td_component", "tdpilot.tox")
    except Exception:
        tox_path = None

    externaltox_set = False
    if tox_path and os.path.isfile(tox_path) and hasattr(comp.par, "externaltox"):
        try:
            comp.par.externaltox = tox_path
            # v1.6.7 fix: the actual TD param is ``enableexternaltox``
            # (toggle that, when True, makes TD load the .tox at the
            # externaltox path on COMP creation / project load). v1.6.6
            # used the wrong name ``reloadtoxonstart`` which doesn't exist
            # on containerCOMP — silent no-op meant the .toe got saved
            # with externaltox path set but enableexternaltox=False, so
            # next TD launch restored an empty shell (the bug v1.6.7's
            # users would have hit had they ever managed to upgrade
            # cleanly to v1.6.6).
            if hasattr(comp.par, "enableexternaltox"):
                comp.par.enableexternaltox = True
            externaltox_set = True
        except Exception as exc:
            print("[TDPilot autostart] could not set externaltox:", exc)

    # Save WITHOUT saveExternalToxs so the COMP body stays referenced
    # by externaltox rather than embedded. If externaltox wasn't set,
    # this falls back to the pre-v1.6.6 behavior (full embed) — which
    # is correct for that case.
    try:
        project.save(target, saveExternalToxs=False)
    except TypeError:
        # Older TD builds may not accept saveExternalToxs kwarg.
        project.save(target)

    return externaltox_set


def onStart():
    _disable_auth()
    _bootstrap()
    _refresh_installer()
    _tick()
    return


def onCreate():
    # v1.6.15: onStart only fires on project load (Cmd+Q + reopen). When the
    # user drags the .tox into an existing project (the canonical install
    # flow!), onStart never fires for this COMP — so _bootstrap() never
    # populates the state_cache and the panel reads None for version/build/
    # tools/ws. Hooking _disable_auth + _bootstrap here makes the panel
    # populate correctly on drag-drop too. onCreate fires exactly once per
    # COMP instantiation regardless of trigger (loadTox, drag, scripted
    # create). Pre-existing v1.6.7+ regression — the panel-bug saga left
    # this writer wire-up gap when state_cache was first added.
    #
    # _refresh_installer() ALSO fires here so the right-panel "Status" row
    # stops showing the default "(checking)" string within ~1s of drag.
    # Without this, the only trigger is onFrameStart's 60s tick — for the
    # first minute after drag, the panel honestly shows the stale default,
    # which users misread as "the panel is broken." Probe is cheap (file
    # existence + which() lookups), safe to run synchronously on COMP init.
    _disable_auth()
    _bootstrap()
    _refresh_installer()


def onExit():
    return


def onFrameStart(frame):
    f = int(frame)
    _execute_pending_main_thread_action()
    if f % INSTALLER_PROGRESS_EVERY_N_FRAMES == 0:
        _poll_installer_progress()
    if f % PANEL_TICK_EVERY_N_FRAMES == 0:
        _tick()
    if f % INSTALLER_REFRESH_EVERY_N_FRAMES == 0:
        _refresh_installer()
    return


def onFrameEnd(frame):
    return


def onPlayStateChange(state):
    return


def onDeviceChange():
    return


def onProjectPreSave():
    return


def onProjectPostSave():
    return
