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
      "save_toe" — project.save() to the installer's CURRENT autoload path

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
            project.save(target)
            print("[TDPilot autostart] saved autoload .toe to", target)
            installer.module.mark_pending_action_done(success=True)
        except Exception as exc:
            print("[TDPilot autostart] save_toe failed:", exc)
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


def onStart():
    _disable_auth()
    _bootstrap()
    _refresh_installer()
    _tick()
    return


def onCreate():
    return


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
