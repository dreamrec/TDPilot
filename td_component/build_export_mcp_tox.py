"""
TDPilot — Build and export a reusable `tdpilot_v1_2.tox`
=============================================================

Run inside TouchDesigner Textport:

    exec(open("/ABS/PATH/td_component/build_export_mcp_tox.py").read(), globals(), globals())

Optional before running:

    import os
    os.environ["TD_MCP_REPO_ROOT"] = "/ABS/PATH/TDPilot"
    os.environ["TD_MCP_PARENT_PATH"] = "/project1"  # optional install target
"""

import os
import glob
from datetime import datetime, timezone
from urllib.parse import urlparse


# Configuration
# If set, also install/update /<target>/mcp_server after exporting the .tox.
INSTALL_PARENT_PATH = os.environ.get("TD_MCP_PARENT_PATH", "").strip()
COMP_NAME = "mcp_server"
TEMP_CONTAINER_NAME = "__tdpilot_export__"
WEB_PORT = 9981
WS_URL = "ws://127.0.0.1:9982"
OVERWRITE_COMPONENT = True

# If empty, auto-resolve to: <repo_root>/td_component/tdpilot_v1_2.tox
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
        out_path = os.path.join(repo_root, "td_component", "tdpilot_v1_2.tox")
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
    return (
        "TDPilot v1.2 MCP server component\\n"
        "Generated by build_export_mcp_tox.py\\n"
        "\\n"
        "Generated at (UTC): {timestamp}\\n"
        "Source repo: {repo_label}\\n"
        "Export file: {tox_name}\\n"
        "WebServer port: {port}\\n"
        "WebSocket URL: {ws_url}\\n"
    ).format(
        timestamp=timestamp,
        repo_label=repo_label,
        tox_name=tox_name,
        port=WEB_PORT,
        ws_url=WS_URL,
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


def _populate_component(comp, callbacks_code, event_emitter_code, ws_callbacks_code, info_text):
    comp.comment = "TDPilot v1.2 MCP server component"
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

    _set_first_par(webserver, ("port",), WEB_PORT)
    _set_first_par(webserver, ("active", "enable"), 1)
    _set_first_par(webserver, ("callbacks", "callbackdat", "callback"), "callbacks")

    callbacks.text = callbacks_code
    ws_callbacks.text = ws_callbacks_code
    event_emitter.text = event_emitter_code
    info.text = info_text

    _configure_websocket_dat(ws_client)

    try:
        webserver.nodeX, webserver.nodeY = 0, 0
        callbacks.nodeX, callbacks.nodeY = 260, 0
        ws_client.nodeX, ws_client.nodeY = 0, -180
        ws_callbacks.nodeX, ws_callbacks.nodeY = 260, -180
        event_emitter.nodeX, event_emitter.nodeY = 520, -180
        info.nodeX, info.nodeY = 520, 0
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
        print("[TDPilot] No live project install requested. Import the TOX where needed.")
    return export_path


build_and_export()
