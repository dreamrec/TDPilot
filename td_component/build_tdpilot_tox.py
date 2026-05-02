"""
TDPilot v1.5.6 — Build the full tdpilot container COMP and export tdpilot.tox
=============================================================================

Run inside TouchDesigner Textport:

    runfile = "/ABS/PATH/td_component/build_tdpilot_tox.py"
    with open(runfile) as f: source = f.read()
    exec(compile(source, runfile, "exec"), globals(), globals())

This is the v1.5.6 successor to ``build_export_mcp_tox.py``. The earlier
script built only the inner ``mcp_server`` COMP and exported it as
tdpilot.tox; v1.5.6 wraps that in a containerCOMP that also hosts the
installer panel, status display, and lifecycle wiring. Drag the resulting
.tox into any TD project and the user gets a working install/update UI
without ever touching Textport.

What this script produces inside the dragged-in COMP:

    /tdpilot                        containerCOMP, panel 520x320
        Custom param pages:
          Install   (status, action pulses, configuration toggles)
          Update    (installed/latest, check/update/rollback, auto-check)
        Children:
          installer        textDAT             - Phase A-D installer module
          installer_exec   parameterexecuteDAT - routes pulses on parent COMP
          autostart        executeDAT          - onStart/onFrameStart bridge
          renderer         textDAT             - formats the status panel
          status_text      textTOP             - visible panel (Courier New 14)
          mcp_server       baseCOMP            - built by build_export_mcp_tox

Override behaviour with env vars:

    TD_MCP_REPO_ROOT    /ABS/PATH/TDPilot       (auto-detected if unset)
    TD_MCP_PARENT_PATH  /local                  (where to install the live
                                                 COMP - '' to skip install)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Reuse helpers from the existing builder so we don't duplicate logic.
# Derive the td_component dir from one of three sources, in order:
#   1. __file__       — set when imported as a module
#   2. TD_MCP_REPO_ROOT environment variable — set by the textport caller
#   3. caller's globals (for the exec(open(...).read(), globals()) idiom)
# Without this, exec'ing the script via the canonical TD textport pattern
# would leave __file__ undefined and the sibling-module import would fail.
def _resolve_this_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        pass
    repo_root = os.environ.get("TD_MCP_REPO_ROOT")
    if repo_root and os.path.isdir(os.path.join(repo_root, "td_component")):
        return os.path.join(repo_root, "td_component")
    raise RuntimeError(
        "Could not locate td_component/. Set TD_MCP_REPO_ROOT before "
        "exec'ing build_tdpilot_tox.py from Textport."
    )


_THIS_DIR = _resolve_this_dir()
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
import build_export_mcp_tox as _legacy  # noqa: E402


def _propagate_td_globals():
    """Forward TD's textport-only globals (op, parent, project, etc.) into
    the imported _legacy module's namespace.

    TD injects these names into the textport interactive namespace and into
    DAT module namespaces, but NOT into arbitrary Python module imports.
    Without this forwarding, calling _legacy._resolve_export_host() would
    raise ``NameError: name 'op' is not defined`` because _legacy's own
    __dict__ doesn't have ``op``.

    Idempotent — only sets names that aren't already present on _legacy
    and that ARE present in our globals.
    """
    caller_globals = globals()
    for name in (
        "op", "ops",
        "parent", "iop", "ipar",
        "me", "project", "app", "root",
        "tdu", "absTime", "ui",
    ):
        if name in caller_globals and not hasattr(_legacy, name):
            setattr(_legacy, name, caller_globals[name])


_propagate_td_globals()


# ---------------------------------------------------------------------------
# Configuration (mirrors build_export_mcp_tox.py for consistency)
# ---------------------------------------------------------------------------

_env_parent = os.environ.get("TD_MCP_PARENT_PATH")
INSTALL_PARENT_PATH = (
    _env_parent.strip() if _env_parent is not None else "/local"
)
TDPILOT_COMP_NAME = "tdpilot"
TEMP_CONTAINER_NAME = "__tdpilot_tox_export__"
EXPORT_TOX_PATH = ""  # empty = repo_root/td_component/tdpilot.tox
OVERWRITE_COMPONENT = True

# Panel default size matches the live design (520x320 was the tuned size,
# 400x300 is the TD default). Pick the user-tuned size as our shipped default.
PANEL_W = 520
PANEL_H = 320


# ---------------------------------------------------------------------------
# Custom param schema
# ---------------------------------------------------------------------------

# Each tuple: (name, kind, label, default-or-None)
# kind in {"Header", "Str", "Pulse", "Toggle"}.
# Order matters - TD respects insertion order on the page.
_INSTALL_PAGE = [
    ("Installhdr",       "Header", "TDPilot Installer",            None),
    ("Installstatus",    "Str",    "Status",                       "Not detected"),
    ("Detectstate",      "Pulse",  "Detect State",                 None),
    ("Actionshdr",       "Header", "Actions",                      None),
    ("Bootstrapall",     "Pulse",
     "Bootstrap All (clone + plugin + autoload)", None),
    ("Installpython",    "Pulse",  "Install Python Wrapper Only",  None),
    ("Installclaude",    "Pulse",  "Register Claude Code Plugin Only", None),
    ("Settdautoload",    "Pulse",  "Set TD Autoload Only",         None),
    ("Uninstallall",     "Pulse",  "Uninstall Everything",         None),
    ("Configurationhdr", "Header", "Configuration",                None),
    ("Repourl",          "Str",    "Repo URL",
     "https://github.com/dreamrec/TDPilot.git"),
    ("Pintotag",         "Toggle", "Pin to latest tag (else stay on main)", True),
    ("Disableauth",      "Toggle",
     "Disable MCP auth (single-user local mode)", True),
]

_UPDATE_PAGE = [
    ("Updatehdr",        "Header", "Update",                       None),
    ("Installedversion", "Str",    "Installed",                    "--"),
    ("Latestversion",    "Str",    "Latest",                       "--"),
    ("Updatestatus",     "Str",    "Status",
     "Click 'Detect State' to refresh"),
    ("Checkforupdates",  "Pulse",  "Check for Updates Now",        None),
    ("Updatenow",        "Pulse",  "Update Now",                   None),
    ("Rollback",         "Pulse",  "Rollback to Previous Backup",  None),
    ("Updateconfighdr",  "Header", "Configuration",                None),
    ("Autocheckonload",  "Toggle", "Auto-check on project load",   True),
    ("Backupdir",        "Str",    "Last Backup",                  "(none)"),
]

# Source files for the four installer DATs. Each tuple:
#   (DAT name, DAT op-type, source-path-relative-to-repo-root)
_INSTALLER_DATS = (
    ("installer",      "textDAT",              "td_component/installer.py"),
    ("renderer",       "textDAT",              "td_component/renderer.py"),
    ("autostart",      "executeDAT",           "td_component/autostart.py"),
    # parameterexecuteDAT in TD 2025+; some older builds used the old name.
    ("installer_exec", "parameterexecuteDAT",  "td_component/installer_exec.py"),
)


# ---------------------------------------------------------------------------
# Custom-param helpers
# ---------------------------------------------------------------------------


def _append_custom_param(comp, page_name, name, kind, label, default):
    """Append one custom parameter to the named page on `comp`.

    TD's appendXxx() returns a tuple of par instances (vector params return
    multiple). We always touch [0] for default-setting.
    """
    page = comp.appendCustomPage(page_name)
    if kind == "Header":
        # Header is a label-only "Str"-style with no editable value. TD has
        # appendHeader() in modern builds; older builds expose
        # appendXY/appendStr only. Try the modern API first.
        try:
            page.appendHeader(name, label=label)
            return
        except Exception:
            par = page.appendStr(name, label=label)[0]
            par.readOnly = True
            return
    if kind == "Str":
        par = page.appendStr(name, label=label)[0]
        if default is not None:
            par.default = default
            par.val = default
        return
    if kind == "Pulse":
        page.appendPulse(name, label=label)
        return
    if kind == "Toggle":
        par = page.appendToggle(name, label=label)[0]
        if default is not None:
            par.default = bool(default)
            par.val = bool(default)
        return
    raise ValueError("Unknown custom param kind: " + kind)


def _build_custom_params(comp):
    """Add Install + Update custom param pages on the parent COMP.

    Idempotent in spirit, but expects a freshly-constructed (or wiped) COMP.
    """
    for (name, kind, label, default) in _INSTALL_PAGE:
        _append_custom_param(comp, "Install", name, kind, label, default)
    for (name, kind, label, default) in _UPDATE_PAGE:
        _append_custom_param(comp, "Update", name, kind, label, default)


# ---------------------------------------------------------------------------
# Status panel TOP
# ---------------------------------------------------------------------------


def _create_status_text_top(parent_comp, name="status_text"):
    """Create the textTOP that displays the rendered panel string.

    Styling matches the live design: Courier New 14pt, left-top aligned,
    16px inset, 4px line-spacing, 55% white. The renderer DAT writes
    multi-line text into ``status_text.par.text`` once per second.
    """
    top = _legacy._create_with_fallback(parent_comp, ("textTOP",), name)
    style = {
        "font": "Courier New",
        "fontsizex": 14,
        "fontsizey": 14,
        "fontsizexunit": "points",
        "fontsizeyunit": "points",
        "alignx": "left",
        "aligny": "top",
        "positionx": 16,
        "positiony": -16,
        "linespacing": 4,
        "fontcolorr": 0.55,
        "fontcolorg": 0.55,
        "fontcolorb": 0.55,
        "fontcolora": 1.0,
        "wordwrap": False,
    }
    for par_name, par_value in style.items():
        _legacy._set_first_par(top, (par_name,), par_value)
    return top


# ---------------------------------------------------------------------------
# Children: installer + installer_exec + autostart + renderer
# ---------------------------------------------------------------------------


def _create_text_dat_with_source(parent_comp, name, op_type, source_text):
    """Create a Text/Execute/Parameterexecute DAT and stamp source code into it.

    Tries op_type first, falls back to legacy-cased aliases TD has used over
    the years (parameterexecuteDAT vs parexecDAT, etc.).
    """
    fallbacks = (op_type,)
    if op_type == "parameterexecuteDAT":
        fallbacks = ("parameterexecuteDAT", "parexecDAT")
    elif op_type == "executeDAT":
        fallbacks = ("executeDAT",)
    elif op_type == "textDAT":
        fallbacks = ("textDAT",)

    dat = _legacy._create_with_fallback(parent_comp, fallbacks, name)
    dat.text = source_text
    return dat


def _wire_installer_exec(parexec_dat, parent_comp):
    """Point the parexec at the parent tdpilot COMP and turn off everything
    we don't need.

    Must match the live config:
      executeloc = here
      fromop     = parent()  (expression mode)
      pars       = *
      onpulse    = True (only event we listen to)
      custom     = True, builtin = False
      valuechange / valueschanged / etc = False
    """
    _legacy._set_first_par(parexec_dat, ("executeloc",), "here")

    # ``fromop`` is an OP-typed param; setting it as an expression `parent()`
    # is the only correct way - string assignment fails (TD silently nulls
    # the ref). The expression resolves to whichever COMP holds this DAT,
    # so the saved .tox carries an instance-relative reference.
    try:
        par = parexec_dat.par.fromop
        par.expr = "parent()"
        # Read ParMode enum off a known-good par to avoid a hardcoded import.
        par.mode = parexec_dat.par.executeloc.mode.__class__.EXPRESSION
    except Exception:
        # Fall back to assigning the live parent COMP directly. Won't survive
        # paste-into-different-parent, but better than a null ref.
        try:
            parexec_dat.par.fromop = parent_comp
        except Exception:
            pass

    _legacy._set_first_par(parexec_dat, ("pars",), "*")
    _legacy._set_first_par(parexec_dat, ("onpulse",), 1)
    _legacy._set_first_par(parexec_dat, ("custom",), 1)
    _legacy._set_first_par(parexec_dat, ("builtin",), 0)
    for off_par in (
        "valuechange", "valueschanged",
        "expressionchange", "exportchange",
        "enablechange", "modechange",
    ):
        _legacy._set_first_par(parexec_dat, (off_par,), 0)
    _legacy._set_first_par(parexec_dat, ("active",), 1)


def _populate_tdpilot_comp(comp, repo_root, info_text):
    """Build the full v1.5.6 tdpilot COMP children inside `comp`.

    Wipes existing children first so the build is reproducible (matches
    the OVERWRITE_COMPONENT semantics in build_export_mcp_tox).
    """
    comp.comment = "TDPilot v1.5.6 installer + MCP server panel"

    # Panel sizing
    _legacy._set_first_par(comp, ("w",), PANEL_W)
    _legacy._set_first_par(comp, ("h",), PANEL_H)

    # Wipe before populating so reruns land in a clean state.
    for child in list(comp.children):
        child.destroy()

    # Custom param pages
    _build_custom_params(comp)

    # Status panel TOP
    status_text = _create_status_text_top(comp, "status_text")
    try:
        status_text.nodeX, status_text.nodeY = 600, 0
    except Exception:
        pass

    # Installer source DATs
    created_dats = {}
    layout_x = {"installer": 200, "renderer": 400, "installer_exec": 400,
                "autostart": 600}
    layout_y = {"installer": 200, "renderer": 200, "installer_exec": 200,
                "autostart": 200}

    for (name, op_type, rel_path) in _INSTALLER_DATS:
        source = _legacy._read_repo_file(repo_root, rel_path)
        dat = _create_text_dat_with_source(comp, name, op_type, source)
        created_dats[name] = dat
        try:
            dat.nodeX = layout_x.get(name, 0)
            dat.nodeY = layout_y.get(name, 0)
        except Exception:
            pass

    # parexec wiring (must happen AFTER custom params exist so pars=*
    # actually finds them).
    _wire_installer_exec(created_dats["installer_exec"], comp)

    # Nested mcp_server child (built by the legacy populator)
    mcp_comp = _legacy._reset_or_create_comp(comp, "mcp_server")
    callbacks_code = _legacy._read_repo_file(
        repo_root, "td_component/mcp_webserver_callbacks.py"
    )
    event_emitter_code = _legacy._read_repo_file(
        repo_root, "td_component/event_emitter.py"
    )
    ws_callbacks_code = _legacy._read_repo_file(
        repo_root, "td_component/ws_callbacks.py"
    )
    _legacy._populate_component(
        mcp_comp,
        callbacks_code,
        event_emitter_code,
        ws_callbacks_code,
        info_text,
    )
    try:
        mcp_comp.nodeX, mcp_comp.nodeY = 375, 0
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _resolve_export_path(repo_root):
    if EXPORT_TOX_PATH:
        out = os.path.abspath(os.path.expanduser(EXPORT_TOX_PATH))
    else:
        out = os.path.join(repo_root, "td_component", "tdpilot.tox")
    out_dir = os.path.dirname(out)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    return out


def _build_info_text_v156(repo_root, export_path):
    timestamp = datetime.now(timezone.utc).isoformat()
    repo_label = (
        os.path.basename(os.path.abspath(repo_root.rstrip(os.sep)))
        or "TDPilot"
    )
    tox_name = os.path.basename(export_path)
    return (
        "TDPilot v1.5.6 installer + MCP server\n"
        "Generated by build_tdpilot_tox.py\n"
        "\n"
        "Generated at (UTC): " + timestamp + "\n"
        "Source repo: " + repo_label + "\n"
        "Export file: " + tox_name + "\n"
    )


def build_and_export():
    repo_root = _legacy._guess_repo_root()
    if not repo_root:
        raise RuntimeError(
            "Could not auto-detect repo root. Set TD_MCP_REPO_ROOT first, e.g. "
            "os.environ['TD_MCP_REPO_ROOT']='/ABS/PATH/TDPilot'"
        )

    export_path = _resolve_export_path(repo_root)
    info_text = _build_info_text_v156(repo_root, export_path)

    # Build into a throwaway scratch container, then save.
    export_host = _legacy._resolve_export_host()
    temp_parent = export_host.op(TEMP_CONTAINER_NAME)
    if temp_parent is not None and OVERWRITE_COMPONENT:
        temp_parent.destroy()
        temp_parent = None
    if temp_parent is None:
        temp_parent = export_host.create("baseCOMP", TEMP_CONTAINER_NAME)
    try:
        temp_parent.nodeX = 1000
        temp_parent.nodeY = -200
    except Exception:
        pass

    try:
        # The shipped COMP is a containerCOMP (panel-capable), not a baseCOMP.
        existing = temp_parent.op(TDPILOT_COMP_NAME)
        if existing is not None:
            existing.destroy()
        export_comp = temp_parent.create("containerCOMP", TDPILOT_COMP_NAME)
        _populate_tdpilot_comp(export_comp, repo_root, info_text)
        export_comp.save(export_path)
        # Refresh the .tox-source-hash.json so CI's freshness gate stays green.
        _legacy._write_tox_source_hash(repo_root)
    finally:
        try:
            temp_parent.destroy()
        except Exception:
            pass

    # Optionally also install a live copy at TD_MCP_PARENT_PATH.
    install_parent = _legacy._resolve_install_parent_comp()
    if install_parent is not None:
        live = install_parent.op(TDPILOT_COMP_NAME)
        if live is not None and OVERWRITE_COMPONENT:
            live.destroy()
            live = None
        if live is None:
            live = install_parent.create("containerCOMP", TDPILOT_COMP_NAME)
        _populate_tdpilot_comp(live, repo_root, info_text)
        print("[TDPilot] Installed " + live.path)

    print("[TDPilot] Built v1.5.6 tdpilot COMP")
    print("[TDPilot] Exported TOX: " + export_path)
    if install_parent is None:
        print("[TDPilot] No live install requested (TD_MCP_PARENT_PATH='').")
        print(
            "[TDPilot] Drag " + export_path
            + " into a TD project to install."
        )
    return export_path


build_and_export()
