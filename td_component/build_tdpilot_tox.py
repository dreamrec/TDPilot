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
# Resolve the td_component dir using TD_MCP_REPO_ROOT FIRST (always set
# explicitly by the textport caller), then __file__ (only set when this
# script is imported as a normal module).
#
# Priority order matters: when this script is exec'd from the textport,
# __file__ in the exec'd source resolves to TD's textport file path —
# something like ``/Applications/TouchDesigner.app/Contents/Resources/tfs``
# — NOT to our build_tdpilot_tox.py. Trusting __file__ first sends us to
# TD's app bundle, where build_export_mcp_tox.py doesn't exist.
def _resolve_this_dir():
    repo_root = os.environ.get("TD_MCP_REPO_ROOT")
    if repo_root:
        candidate = os.path.join(repo_root, "td_component")
        if os.path.isfile(os.path.join(candidate, "build_export_mcp_tox.py")):
            return candidate
    try:
        candidate = os.path.dirname(os.path.abspath(__file__))
        if os.path.isfile(os.path.join(candidate, "build_export_mcp_tox.py")):
            return candidate
    except NameError:
        pass
    raise RuntimeError(
        "Could not locate td_component/. Set TD_MCP_REPO_ROOT to the "
        "TDPilot repo root before exec'ing build_tdpilot_tox.py from Textport, "
        "and make sure td_component/build_export_mcp_tox.py exists there."
    )


_THIS_DIR = _resolve_this_dir()
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)


def _load_legacy_module():
    """Load build_export_mcp_tox.py as a synthetic module that inherits
    the caller's __builtins__.

    Why this dance instead of ``import build_export_mcp_tox``?
    ``import`` goes through Python's standard machinery, which creates a
    fresh module whose __builtins__ is the standard ``builtins`` module —
    NOT TD's enhanced builtins (where ``op``/``parent``/``me``/etc.
    actually live). When the imported module's helpers later call ``op()``,
    name lookup falls through to standard builtins, which doesn't have it,
    and we get ``NameError: name 'op' is not defined``.

    By using ``types.ModuleType`` + ``exec`` we control the namespace
    explicitly: we install the textport's enhanced ``__builtins__`` into
    the new module's __dict__, so name lookups inside legacy helpers
    correctly resolve TD's injected names.

    Also strips the trailing ``build_and_export()`` auto-run line so we
    only load the helper functions — our own ``build_and_export()`` is
    the entry point.
    """
    import re as _re
    import types as _types

    legacy_path = os.path.join(_THIS_DIR, "build_export_mcp_tox.py")
    if not os.path.isfile(legacy_path):
        raise RuntimeError("build_export_mcp_tox.py not found alongside build_tdpilot_tox.py at " + _THIS_DIR)
    with open(legacy_path) as f:
        legacy_src = f.read()
    # Strip the trailing module-level call so we don't auto-build legacy.
    legacy_src = _re.sub(r"\nbuild_and_export\(\)\s*$", "\n", legacy_src)

    legacy_module = _types.ModuleType("build_export_mcp_tox")
    legacy_module.__file__ = legacy_path
    # The critical line: inherit the caller's __builtins__ so that op,
    # parent, me, project, etc. resolve from inside the legacy helpers.
    caller_globals = globals()
    if "__builtins__" in caller_globals:
        legacy_module.__dict__["__builtins__"] = caller_globals["__builtins__"]
    exec(compile(legacy_src, legacy_path, "exec"), legacy_module.__dict__)
    return legacy_module


_legacy = _load_legacy_module()


# ---------------------------------------------------------------------------
# Configuration (mirrors build_export_mcp_tox.py for consistency)
# ---------------------------------------------------------------------------

_env_parent = os.environ.get("TD_MCP_PARENT_PATH")
INSTALL_PARENT_PATH = _env_parent.strip() if _env_parent is not None else "/local"
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
    ("Installhdr", "Header", "TDPilot Installer", None),
    ("Installstatus", "Str", "Status", "Not detected"),
    ("Detectstate", "Pulse", "Detect State", None),
    ("Actionshdr", "Header", "Actions", None),
    ("Bootstrapall", "Pulse", "Bootstrap All (clone + plugin + autoload)", None),
    ("Installpython", "Pulse", "Install Python Wrapper Only", None),
    ("Installclaude", "Pulse", "Register Claude Code Plugin Only", None),
    ("Settdautoload", "Pulse", "Set TD Autoload Only", None),
    ("Uninstallall", "Pulse", "Uninstall Everything", None),
    ("Configurationhdr", "Header", "Configuration", None),
    ("Repourl", "Str", "Repo URL", "https://github.com/dreamrec/TDPilot.git"),
    ("Pintotag", "Toggle", "Pin to latest tag (else stay on main)", True),
    ("Disableauth", "Toggle", "Disable MCP auth (single-user local mode)", True),
]

_UPDATE_PAGE = [
    ("Updatehdr", "Header", "Update", None),
    ("Installedversion", "Str", "Installed", "--"),
    ("Latestversion", "Str", "Latest", "--"),
    ("Updatestatus", "Str", "Status", "Click 'Detect State' to refresh"),
    ("Checkforupdates", "Pulse", "Check for Updates Now", None),
    ("Updatenow", "Pulse", "Update Now", None),
    ("Rollback", "Pulse", "Rollback to Previous Backup", None),
    ("Updateconfighdr", "Header", "Configuration", None),
    ("Autocheckonload", "Toggle", "Auto-check on project load", True),
    ("Backupdir", "Str", "Last Backup", "(none)"),
]

# Source files for the four installer DATs. Each tuple:
#   (DAT name, DAT op-type, source-path-relative-to-repo-root)
_INSTALLER_DATS = (
    ("installer", "textDAT", "td_component/installer.py"),
    ("renderer", "textDAT", "td_component/renderer.py"),
    ("autostart", "executeDAT", "td_component/autostart.py"),
    # parameterexecuteDAT in TD 2025+; some older builds used the old name.
    ("installer_exec", "parameterexecuteDAT", "td_component/installer_exec.py"),
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
    for name, kind, label, default in _INSTALL_PAGE:
        _append_custom_param(comp, "Install", name, kind, label, default)
    for name, kind, label, default in _UPDATE_PAGE:
        _append_custom_param(comp, "Update", name, kind, label, default)


# ---------------------------------------------------------------------------
# Status panel TOP
# ---------------------------------------------------------------------------


def _create_status_text_top(parent_comp, name="status_text"):
    """Create the textTOP that displays the rendered panel string.

    Styling (v1.6.9): Courier New 14pt, left-top aligned, 16px inset,
    cyan-green text on 90%-opaque black, native panel resolution
    (520×320 to match PANEL_W × PANEL_H — no horizontal stretch when
    used as the containerCOMP's panel-bg TOP). The renderer DAT writes
    multi-line text into ``status_text.par.text`` once per second.

    Style history:
      - v1.6.7: enabled ``display=True`` and ``viewer=True``.
      - v1.6.8: kept resolution at default 256×256 — caused horizontal
        stretching when the panel mapped this square TOP to its 520×320
        viewport (1.625:1 aspect ratio mismatch).
      - v1.6.9: native 520×320 resolution + cyan-green text
        (rgb 0.45/0.95/0.85) + 90% opaque black bg per user feedback.
        No more stretching, panel reads cleanly at any zoom level.
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
        # v1.6.9: cyan-greenish text color (was 55% white). Reads cleanly
        # against the dark panel bg and matches the user's design preference.
        "fontcolorr": 0.45,
        "fontcolorg": 0.95,
        "fontcolorb": 0.85,
        "fontcolora": 1.0,
        # v1.6.9: 90%-opaque black background. The remaining 10% transparency
        # lets a hint of TD's network background bleed through, giving the
        # panel a slight contextual "embedded in the project" feel rather
        # than a hard solid block.
        "bgcolorr": 0.0,
        "bgcolorg": 0.0,
        "bgcolorb": 0.0,
        "bgalpha": 0.9,
        # v1.6.9: native panel resolution to eliminate horizontal stretch.
        # Must match PANEL_W × PANEL_H. If you ever change PANEL_W/H above,
        # update these too — or refactor to read from the parent COMP.
        "resolutionw": PANEL_W,
        "resolutionh": PANEL_H,
        "wordwrap": False,
    }
    for par_name, par_value in style.items():
        _legacy._set_first_par(top, (par_name,), par_value)
    # v1.6.7: enable display + viewer flags so the panel actually shows
    # the rendered text. These are TOP-node attributes (not custom params),
    # so we set them directly rather than via _set_first_par.
    try:
        top.display = True
        top.viewer = True
    except Exception:
        pass
    return top


# ---------------------------------------------------------------------------
# Children: installer + installer_exec + autostart + renderer
# ---------------------------------------------------------------------------


def _create_text_dat_with_source(parent_comp, name, op_type, source_text):
    """Create a Text/Execute/Parameterexecute DAT and stamp source code into it.

    Tries op_type first, falls back to legacy-cased aliases TD has used over
    the years (parameterexecuteDAT vs parexecDAT, etc.).

    v1.6.7: for executeDAT, also enable the trigger toggles that fire the
    callback functions defined in ``source_text``. Without this, autostart's
    ``onStart``, ``onFrameStart``, ``onProjectPostSave`` etc. are defined
    but never called by TD — the COMP's auth-disable + panel-bootstrap +
    main-thread-action machinery silently never fires. This is the bug
    that left the v1.5.6-through-v1.6.6 panel stuck at "Ctn" placeholder
    on every fresh loadTox. We enable the toggles ``autostart.py`` actually
    uses; absent toggles (frameend, edit, etc.) stay at default False.
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

    if op_type == "executeDAT":
        # Trigger toggles autostart.py actually uses. Each toggle maps to
        # a callback function name in the DAT module — see autostart.py.
        executedat_triggers = (
            "start",  # onStart fires _disable_auth + _bootstrap + _refresh_installer + _tick
            "create",  # onCreate (currently no-op but reserved)
            "exit",  # onExit (no-op but reserved)
            "framestart",  # onFrameStart fires _tick + _refresh_installer + main-thread-actions
            "playstatechange",  # onPlayStateChange (no-op but reserved)
            "devicechange",  # onDeviceChange (no-op but reserved)
            "projectpresave",  # onProjectPreSave (no-op but reserved)
            "projectpostsave",  # onProjectPostSave (no-op but reserved)
        )
        for trig in executedat_triggers:
            _legacy._set_first_par(dat, (trig,), True)

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
        "valuechange",
        "valueschanged",
        "expressionchange",
        "exportchange",
        "enablechange",
        "modechange",
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

    # v1.6.8 (defense-in-depth): explicitly set viewer=True on the outer
    # containerCOMP so the panel surface renders inside the COMP node in
    # the network editor (vs showing TD's default "Ctn" placeholder). TD's
    # default is True empirically as of TD 2025.32460, but explicit > implicit
    # — this guards against a future TD release flipping the default. Paired
    # with `_create_status_text_top` setting `top.display = True` so the
    # textTOP actually surfaces in the panel.
    try:
        comp.viewer = True
    except Exception:
        pass

    # Wipe before populating so reruns land in a clean state.
    for child in list(comp.children):
        child.destroy()

    # Custom param pages
    _build_custom_params(comp)

    # Status panel TOP
    #
    # v1.6.8 PARTIAL fix (NOT actually sufficient — see v1.6.9 below):
    # tried positioning status_text at (0, 0) thinking nodeX/nodeY = panel
    # coordinates. The panel still rendered black at the network level.
    # Hypothesis was wrong.
    #
    # v1.6.9 ACTUAL fix:
    # ContainerCOMP panel composition does NOT auto-composite child TOPs by
    # nodeX/nodeY. The panel BACKGROUND comes from the COMP's "Look" page
    # `top` parameter (a TOP-typed reference). If `comp.par.top = None`,
    # the panel renders only `bgcolor` — no child TOP content. THE FIX is
    # to wire `comp.par.top = status_text` so the textTOP's pixels fill
    # the panel background. This was set correctly in the v1.5.x build
    # but lost in the v1.5.6 containerCOMP refactor.
    #
    # Verified live in TD 2025.32460: setting proj.par.top = status_text
    # immediately surfaces the textTOP content in the network-editor view
    # of the COMP icon. nodeX/nodeY position remains useful for network
    # organization (and panel hit-testing if the TOP is interactive), but
    # is NOT what makes the TOP visible in the panel.
    status_text = _create_status_text_top(comp, "status_text")
    try:
        status_text.nodeX, status_text.nodeY = 0, 0
    except Exception:
        pass

    # v1.6.9: wire the containerCOMP's Look-page panel-background TOP to
    # status_text. This is THE setting that makes the panel render the
    # textTOP's content as the panel background image.
    try:
        comp.par.top = status_text
    except Exception:
        pass

    # Installer source DATs
    created_dats = {}
    layout_x = {"installer": 200, "renderer": 400, "installer_exec": 400, "autostart": 600}
    layout_y = {"installer": 200, "renderer": 200, "installer_exec": 200, "autostart": 200}

    for name, op_type, rel_path in _INSTALLER_DATS:
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
    callbacks_code = _legacy._read_repo_file(repo_root, "td_component/mcp_webserver_callbacks.py")
    event_emitter_code = _legacy._read_repo_file(repo_root, "td_component/event_emitter.py")
    ws_callbacks_code = _legacy._read_repo_file(repo_root, "td_component/ws_callbacks.py")
    # v1.6.7: state_cache module text — bakes into the state_cache textDAT
    # inside mcp_server. Without this, the renderer's bootstrap silently
    # fails on every fresh loadTox (panel stays at TD's "Ctn" placeholder).
    state_cache_code = _legacy._read_repo_file(repo_root, "td_component/state_cache.py")
    _legacy._populate_component(
        mcp_comp,
        callbacks_code,
        event_emitter_code,
        ws_callbacks_code,
        info_text,
        state_cache_code=state_cache_code,
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
    repo_label = os.path.basename(os.path.abspath(repo_root.rstrip(os.sep))) or "TDPilot"
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
        print("[TDPilot] Drag " + export_path + " into a TD project to install.")
    return export_path


build_and_export()
