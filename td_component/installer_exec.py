"""parexec DAT — routes pulse params on the tdpilot COMP to installer.module.

Watches the parent COMP's pulse params and dispatches to the right
installer function. Phase A wires only Detectstate; the install /
update / rollback pulses are wired but call stubs that raise
NotImplementedError until later phases land.

Note: TD's parexec onPulse callback fires from UI clicks (via the
event loop), not always from MCP-context Python pulses. The autostart
DAT calls installer.refresh_status_params() directly so panel state
stays accurate without depending on this dispatch path.
"""

# Map: param name (case-insensitive base name) -> installer.module function name
_PULSE_DISPATCH = {
    "Detectstate": "refresh_status_params",
    "Bootstrapall": "bootstrap_all",
    "Installpython": "install_python_wrapper",
    "Installclaude": "install_claude_plugin",
    "Settdautoload": "set_td_autoload",
    "Uninstallall": "uninstall_all",
    "Checkforupdates": "check_for_updates",
    "Updatenow": "update_now",
    "Rollback": "rollback",
}


def _set_status(message):
    """Best-effort write to Install_status. Swallows failures."""
    try:
        parent().par.Installstatus = message
    except Exception:
        pass


def _dispatch(par_name):
    """Look up and invoke the matching installer function."""
    func_name = _PULSE_DISPATCH.get(par_name)
    if func_name is None:
        return
    installer = parent().op("installer")
    if installer is None:
        _set_status("Error: installer DAT missing")
        return
    func = getattr(installer.module, func_name, None)
    if func is None:
        _set_status("Error: installer.module has no " + func_name)
        return
    try:
        result = func()
        # detect/refresh return state dicts; install/update return tuples; we
        # don't inspect them in Phase A.
        if par_name == "Detectstate" and isinstance(result, dict):
            print("[TDPilot installer] state probed:", result)
    except NotImplementedError as exc:
        _set_status("Not yet implemented: " + str(exc))
    except Exception as exc:
        _set_status("Error: " + str(exc))
        print("[TDPilot installer] " + par_name + " failed:", exc)


def onPulse(par):
    _dispatch(par.name)
    return


def onValueChange(par, prev):
    return


def onValuesChanged(changes):
    return


# Standard parexec callbacks we don't use:
def onExpressionChange(par, val, prev):
    return


def onExportChange(par, val, prev):
    return


def onEnableChange(par, val, prev):
    return


def onModeChange(par, val, prev):
    return
