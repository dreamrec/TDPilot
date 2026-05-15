"""
TDPilot — Build and export a reusable `tdpilot.tox`
=============================================================

Run inside TouchDesigner Textport:

    exec(open("/ABS/PATH/td_component/build_export_mcp_tox.py").read(), globals(), globals())

By default the component is installed into /local so it persists across
project opens within the same TD session.  Override with:

    import os
    os.environ["TD_MCP_REPO_ROOT"] = "/ABS/PATH/TDPilot"
    os.environ["TD_MCP_PARENT_PATH"] = "/project1"   # per-project install
    os.environ["TD_MCP_PARENT_PATH"] = ""             # export only, no install
"""

import os
import glob
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlparse


# Files whose content is baked into the .tox and therefore determines its
# "fresh enough" status. Kept in sync with scripts/check_tox_freshness.py.
#
# v1.5.6 added the four installer-pane source files (installer, installer_exec,
# autostart, renderer). They live as Text DATs inside the tdpilot COMP — the
# parent COMP that the v1.5.6 .tox now exports. CI hash-tracks them so a
# committed .tox stays in sync with the source on disk.
_TOX_SOURCE_FILES = (
    "td_component/mcp_webserver_callbacks.py",
    "td_component/event_emitter.py",
    "td_component/ws_callbacks.py",
    "td_component/tdpilot_startup.py",
    "td_component/installer.py",
    "td_component/installer_exec.py",
    "td_component/autostart.py",
    "td_component/renderer.py",
    # v1.6.7: state_cache module — was missing from main from v1.5.6 through
    # v1.6.6, causing renderer.bootstrap to silently fail on every fresh
    # loadTox (panel showed TD's "Ctn" placeholder forever, status_text
    # stuck at default "derivative" text). Restored from a v1.6.0 worktree
    # + wired into _populate_component so a textDAT named "state_cache"
    # gets created inside mcp_server with this content baked in.
    "td_component/state_cache.py",
)


def _compute_tox_source_hash(repo_root):
    """Return sha256 of the concatenated .py source that gets baked into the .tox.

    This is the single source of truth for .tox freshness. Matches the
    freshness check in scripts/check_tox_freshness.py.
    """
    h = hashlib.sha256()
    for rel in _TOX_SOURCE_FILES:
        path = os.path.join(repo_root, rel)
        if not os.path.isfile(path):
            continue
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        with open(path, "rb") as f:
            h.update(f.read())
        h.update(b"\x00")
    return h.hexdigest()


def _write_tox_source_hash(repo_root):
    """Record the .tox-source hash so CI can detect drift after edits."""
    manifest = {
        "tox_source_hash": _compute_tox_source_hash(repo_root),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_files": list(_TOX_SOURCE_FILES),
    }
    out_path = os.path.join(repo_root, "td_component", ".tox-source-hash.json")
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print("[TDPilot] Wrote {}".format(out_path))


# Configuration
# Default install target is /local (persists across project opens).
# Set TD_MCP_PARENT_PATH to override (e.g. "/project1") or to "" for export-only.
_env_parent = os.environ.get("TD_MCP_PARENT_PATH")
INSTALL_PARENT_PATH = _env_parent.strip() if _env_parent is not None else "/local"
COMP_NAME = "mcp_server"
TEMP_CONTAINER_NAME = "__tdpilot_export__"
WEB_PORT = 9981
WS_URL = "ws://127.0.0.1:9982"
OVERWRITE_COMPONENT = True

# If empty, auto-resolve to: <repo_root>/td_component/tdpilot.tox
EXPORT_TOX_PATH = ""


def _set_first_par(node, names, value):
    for name in names:
        try:
            par = getattr(node.par, name)
        except Exception:
            continue
        try:
            par.val = value
            return True
        except Exception:
            try:
                setattr(node.par, name, value)
                return True
            except Exception:
                continue
    return False


def _create_with_fallback(parent_comp, op_types, name):
    for op_type in op_types:
        try:
            return parent_comp.create(op_type, name)
        except Exception:
            continue
    raise RuntimeError("Could not create {} using any of {}".format(name, op_types))


def _read_repo_file(repo_root, relative_path):
    path = os.path.join(repo_root, relative_path)
    if not os.path.isfile(path):
        raise FileNotFoundError("Required file not found: {}".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _guess_repo_root():
    def _append_variants(bucket, path):
        if not path:
            return
        path = os.path.abspath(os.path.expanduser(str(path)))
        if os.path.isfile(path):
            path = os.path.dirname(path)
        bucket.append(path)
        bucket.append(os.path.dirname(path))
        bucket.append(os.path.dirname(os.path.dirname(path)))

    def _is_repo_root(path):
        marker = os.path.join(path, "td_component", "mcp_webserver_callbacks.py")
        pyproject = os.path.join(path, "pyproject.toml")
        return os.path.isfile(marker) and os.path.isfile(pyproject)

    candidates = []

    env_root = (os.environ.get("TD_MCP_REPO_ROOT") or "").strip()
    _append_variants(candidates, env_root)

    try:
        _append_variants(candidates, __file__)
    except Exception:
        pass

    try:
        _append_variants(candidates, os.getcwd())
    except Exception:
        pass

    try:
        _append_variants(candidates, project.folder)
    except Exception:
        pass

    # If this is run from a Text DAT, try its external file parameter.
    try:
        me_file_par = getattr(getattr(me, "par", None), "file", None)
        if me_file_par is not None:
            _append_variants(candidates, me_file_par.eval())
    except Exception:
        pass

    home = os.path.expanduser("~")
    common = [
        os.path.join(home, "Desktop", "TDPilot"),
        os.path.join(home, "Documents", "TDPilot"),
    ]
    for item in common:
        _append_variants(candidates, item)

    # Lightweight discovery in common places (single level only).
    search_bases = [
        home,
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Projects"),
        os.path.join(home, "Dev"),
        os.path.join(home, "dev"),
        os.path.join(home, "Code"),
        os.path.join(home, "code"),
        os.path.join(home, "repos"),
        os.path.join(home, "src"),
    ]
    for base in search_bases:
        if not os.path.isdir(base):
            continue
        for pattern in ("*TDPilot*", "*tdpilot*"):
            for match in glob.glob(os.path.join(base, pattern)):
                _append_variants(candidates, match)

    seen = set()
    for root in candidates:
        if not root:
            continue
        root = os.path.abspath(os.path.expanduser(root))
        if root in seen:
            continue
        seen.add(root)
        if _is_repo_root(root):
            return root
    return None


def _resolve_export_path(repo_root):
    if EXPORT_TOX_PATH:
        out_path = os.path.abspath(os.path.expanduser(EXPORT_TOX_PATH))
    else:
        out_path = os.path.join(repo_root, "td_component", "tdpilot.tox")
    out_dir = os.path.dirname(out_path)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    return out_path


def _resolve_install_parent_comp():
    if not INSTALL_PARENT_PATH:
        return None
    node = op(INSTALL_PARENT_PATH)
    if node is not None and getattr(node, "isCOMP", False):
        return node
    # /local is a built-in TD container — if it somehow isn't found, warn clearly.
    if INSTALL_PARENT_PATH == "/local":
        raise RuntimeError(
            "Could not find /local container. This is a built-in TD container "
            "that should always exist. Please check your TouchDesigner version."
        )
    raise RuntimeError(
        "Install target not found: {}. Set TD_MCP_PARENT_PATH to a valid COMP path.".format(
            INSTALL_PARENT_PATH
        )
    )


def _resolve_export_host():
    root = op("/")
    if root is not None and getattr(root, "isCOMP", False):
        return root
    raise RuntimeError("Could not resolve a TouchDesigner root COMP for temporary export.")


def _build_info_text(repo_root, export_path):
    timestamp = datetime.now(timezone.utc).isoformat()
    repo_label = os.path.basename(os.path.abspath(repo_root.rstrip(os.sep))) or "TDPilot"
    tox_name = os.path.basename(export_path)
    # Read the package version dynamically — was hardcoded to "v1.3" pre-v1.6.15,
    # so the info DAT shipped wrong-version strings for 12+ releases. The helper
    # falls back to '?' if __init__.py is unreadable; build still proceeds.
    version = _read_pkg_version(repo_root) or "?"
    return (
        "TDPilot v{version} MCP server component\\n"
        "Generated by build_export_mcp_tox.py\\n"
        "\\n"
        "Generated at (UTC): {timestamp}\\n"
        "Source repo: {repo_label}\\n"
        "Export file: {tox_name}\\n"
        "WebServer port: {port}\\n"
        "WebSocket URL: {ws_url}\\n"
    ).format(
        version=version,
        timestamp=timestamp,
        repo_label=repo_label,
        tox_name=tox_name,
        port=WEB_PORT,
        ws_url=WS_URL,
    )


def _read_pkg_version(repo_root):
    """Read ``__version__`` from ``src/td_mcp/__init__.py``.

    Returns the version string (e.g. ``"1.6.14"``) or ``None`` if the file
    can't be read or the variable can't be parsed. Used to name the
    versioned .tox sidecar (see ``_copy_versioned_export``).

    We read ``__init__.py`` rather than ``pyproject.toml`` because the build
    script runs inside TouchDesigner's Python interpreter, which historically
    lags upstream Python versions; ``__init__.py`` is plain text and parses
    with a string split, while ``pyproject.toml`` requires ``tomllib``
    (3.11+) or a third-party dep.
    """
    init_path = os.path.join(repo_root, "src", "td_mcp", "__init__.py")
    try:
        with open(init_path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.lstrip().startswith("__version__"):
                    # e.g. __version__ = "1.6.14"
                    _, _, rhs = line.partition("=")
                    return rhs.strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def _save_versioned_export(repo_root, export_comp, canonical_path):
    """Save a versioned `.tox` sidecar with a version-named COMP baked in.

    For ``td_component/tdpilot.tox`` at version ``1.6.15`` this produces
    ``td_component/tdpilot1.6.15.tox`` whose embedded COMP is named
    ``tdpilot1_6_15`` (underscores — TD operator names disallow dots).
    Result: when a user drags this `.tox` into TD's network view, the
    resulting COMP shows the version in its node label immediately —
    no need to open the info DAT to identify which build is loaded.

    The canonical ``tdpilot.tox`` saved by the caller retains the
    ``mcp_server`` COMP name so existing code paths
    (``op('/local/mcp_server')``, the setup script's install target,
    user memory references) keep working unchanged. We achieve this by
    saving the canonical FIRST, then temporarily renaming the in-network
    ``export_comp`` to ``tdpilot<VERSION>``, saving the versioned sidecar,
    then renaming back to ``mcp_server`` before the caller's downstream
    install step runs.

    Filename keeps dots (``tdpilot1.6.15.tox``) for semver clarity and to
    match Finder-friendly version strings; COMP name uses underscores
    (``tdpilot1_6_15``) because TD operator names allow only alphanumerics
    and underscores.

    Gitignored via ``td_component/tdpilot[0-9]*.tox`` — local-only utility.
    Historical recovery still available from any release tag via
    ``git show vX.Y.Z:td_component/tdpilot.tox``.

    Failures (no version readable, COMP rename rejected, save failure) are
    logged as WARN and do NOT raise. The canonical .tox write at the
    caller is the sacred contract; this sidecar is a convenience.
    """
    version = _read_pkg_version(repo_root)
    if not version:
        print(
            "[tdpilot] WARN: could not read __version__ from src/td_mcp/__init__.py; "
            "skipping versioned .tox sidecar."
        )
        return
    base_dir = os.path.dirname(canonical_path)
    versioned_path = os.path.join(base_dir, "tdpilot{0}.tox".format(version))
    versioned_comp_name = "tdpilot{0}".format(version.replace(".", "_"))

    original_name = export_comp.name
    rename_succeeded = False
    try:
        try:
            export_comp.name = versioned_comp_name
            rename_succeeded = True
        except Exception as rename_exc:
            print(
                "[tdpilot] WARN: could not rename COMP to {0!r} (TD rejected): {1!r}. "
                "Falling back to file-copy with mcp_server COMP name baked in.".format(
                    versioned_comp_name, rename_exc
                )
            )
            import shutil
            shutil.copy2(canonical_path, versioned_path)
            print("[tdpilot] Versioned .tox sidecar (fallback copy): " + versioned_path)
            return

        export_comp.save(versioned_path)
        print(
            "[tdpilot] Versioned .tox sidecar: {0} (COMP baked as {1!r})".format(
                versioned_path, versioned_comp_name
            )
        )
    except Exception as exc:
        print("[tdpilot] WARN: failed to write versioned .tox sidecar: " + repr(exc))
    finally:
        if rename_succeeded:
            try:
                export_comp.name = original_name
            except Exception as restore_exc:
                # If we can't restore the canonical name, downstream
                # /local/ install will fail loudly — surface this clearly.
                print(
                    "[tdpilot] ERROR: could not restore COMP name to {0!r}: {1!r}. "
                    "Downstream install target may be broken — re-run the build.".format(
                        original_name, restore_exc
                    )
                )


def _reset_or_create_comp(parent, name):
    existing = parent.op(name)
    if existing is not None and OVERWRITE_COMPONENT:
        existing.destroy()
        existing = None

    if existing is None:
        return parent.create("baseCOMP", name)

    for child in list(existing.children):
        child.destroy()
    return existing


def _populate_component(comp, callbacks_code, event_emitter_code, ws_callbacks_code, info_text, state_cache_code=""):
    """Populate the mcp_server baseCOMP with its child DATs.

    v1.6.7: ``state_cache_code`` is the new positional-with-default arg.
    Callers built before v1.6.7 didn't pass it; without state_cache, the
    panel renderer fails silently (returns False from bootstrap; tick
    falls through to the "(state_cache not loaded)" placeholder string).
    Default empty string keeps API back-compat — but the panel won't
    render correctly until callers populate it from
    ``td_component/state_cache.py``.
    """
    comp.comment = "TDPilot v1.3 MCP server component"
    try:
        comp.nodeX = 400
        comp.nodeY = -200
    except Exception:
        pass

    for child in list(comp.children):
        child.destroy()

    webserver = _create_with_fallback(comp, ("webserverDAT",), "webserver")
    callbacks = _create_with_fallback(comp, ("textDAT",), "callbacks")
    ws_client = _create_with_fallback(comp, ("webSocketDAT", "websocketDAT"), "ws_client")
    ws_callbacks = _create_with_fallback(comp, ("textDAT",), "ws_callbacks")
    event_emitter = _create_with_fallback(comp, ("textDAT",), "event_emitter")
    info = _create_with_fallback(comp, ("textDAT",), "info")
    # v1.6.7: state_cache textDAT — the renderer's data source. See
    # docstring above for context. Created here so every fresh loadTox
    # produces a panel-renderable COMP.
    state_cache = _create_with_fallback(comp, ("textDAT",), "state_cache")

    _set_first_par(webserver, ("port",), WEB_PORT)
    _set_first_par(webserver, ("active", "enable"), 1)
    _set_first_par(webserver, ("callbacks", "callbackdat", "callback"), "callbacks")

    callbacks.text = callbacks_code
    ws_callbacks.text = ws_callbacks_code
    event_emitter.text = event_emitter_code
    info.text = info_text
    state_cache.text = state_cache_code

    _configure_websocket_dat(ws_client)

    try:
        webserver.nodeX, webserver.nodeY = 0, 0
        callbacks.nodeX, callbacks.nodeY = 260, 0
        ws_client.nodeX, ws_client.nodeY = 0, -180
        ws_callbacks.nodeX, ws_callbacks.nodeY = 260, -180
        event_emitter.nodeX, event_emitter.nodeY = 520, -180
        info.nodeX, info.nodeY = 520, 0
        state_cache.nodeX, state_cache.nodeY = 780, -90
    except Exception:
        pass


def _configure_websocket_dat(ws_dat):
    parsed = urlparse(WS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9982
    path = parsed.path or "/"

    _set_first_par(ws_dat, ("active", "open", "enable"), 1)

    # Prefer URL if available; otherwise set host/port style fields.
    if not _set_first_par(ws_dat, ("url", "address", "uri"), WS_URL):
        _set_first_par(ws_dat, ("host", "address", "netaddress"), host)
        _set_first_par(ws_dat, ("port", "networkport"), port)
        _set_first_par(ws_dat, ("path",), path)

    _set_first_par(ws_dat, ("callbacks", "callbackdat", "callback"), "ws_callbacks")


def build_and_export():
    repo_root = _guess_repo_root()
    if not repo_root:
        raise RuntimeError(
            "Could not auto-detect repo root. Set TD_MCP_REPO_ROOT first, e.g. "
            "os.environ['TD_MCP_REPO_ROOT']='/ABS/PATH/TDPilot'"
        )

    callbacks_code = _read_repo_file(repo_root, "td_component/mcp_webserver_callbacks.py")
    event_emitter_code = _read_repo_file(repo_root, "td_component/event_emitter.py")
    ws_callbacks_code = _read_repo_file(repo_root, "td_component/ws_callbacks.py")
    export_path = _resolve_export_path(repo_root)
    info_text = _build_info_text(repo_root, export_path)

    export_host = _resolve_export_host()
    temp_parent = export_host.op(TEMP_CONTAINER_NAME)
    if temp_parent is not None and OVERWRITE_COMPONENT:
        temp_parent.destroy()
        temp_parent = None
    if temp_parent is None:
        temp_parent = export_host.create("baseCOMP", TEMP_CONTAINER_NAME)
    try:
        temp_parent.nodeX = 800
        temp_parent.nodeY = -200
    except Exception:
        pass

    try:
        export_comp = _reset_or_create_comp(temp_parent, COMP_NAME)
        _populate_component(
            export_comp,
            callbacks_code,
            event_emitter_code,
            ws_callbacks_code,
            info_text,
        )
        export_comp.save(export_path)
        _save_versioned_export(repo_root, export_comp, export_path)
        _write_tox_source_hash(repo_root)
    finally:
        try:
            temp_parent.destroy()
        except Exception:
            pass

    install_parent = _resolve_install_parent_comp()
    if install_parent is not None:
        installed_comp = _reset_or_create_comp(install_parent, COMP_NAME)
        _populate_component(
            installed_comp,
            callbacks_code,
            event_emitter_code,
            ws_callbacks_code,
            info_text,
        )
        print("[TDPilot] Installed {}".format(installed_comp.path))

    print("[TDPilot] Built reusable component")
    print("[TDPilot] WebServer port: {}".format(WEB_PORT))
    print("[TDPilot] WebSocket URL: {}".format(WS_URL))
    print("[TDPilot] Exported TOX: {}".format(export_path))
    if install_parent is None:
        print("[TDPilot] No live install requested (TD_MCP_PARENT_PATH='').")
        print("[TDPilot] Import the TOX manually, or re-run without setting TD_MCP_PARENT_PATH")
        print("[TDPilot] to auto-install into /local (persists across project opens).")
    return export_path


build_and_export()
