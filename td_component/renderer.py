"""Renderer for the TDPilot status panel.

Reads runtime telemetry from ./mcp_server/state_cache and formats a
fixed-width text block. Sibling autostart DAT calls render() once per
second and writes the result to ./status_text.par.text.

Phase A addition: also reads ./Installstatus, ./Updatestatus, and
./Latestversion from the parent COMP's custom params (set by the
sibling installer DAT) and renders an "Install" + "Update" row at
the bottom of the panel.
"""

MCP_COMP_PATH = "./mcp_server"
_DASH = "─" * 24


def _state():
    cache_dat = parent().op(MCP_COMP_PATH + "/state_cache")
    if cache_dat is None:
        return None
    try:
        return cache_dat.module.snapshot()
    except Exception:
        return None


def _fmt_latency(value):
    if not isinstance(value, (int, float)):
        return "-- ms"
    return f"{value:.0f} ms"


def _fmt_int(value):
    if isinstance(value, (int, float)):
        return str(int(value))
    return "--"


def _parse_popx_version(comp_name):
    parts = comp_name.split("_")
    digits = [p for p in parts if p.isdigit()]
    if len(digits) >= 2:
        return ".".join(digits)
    return None


def _detect_popx():
    canonical = ("/local/popx", "/local/popsextension", "/popx")
    for probe in canonical:
        if op(probe) is not None:
            return "installed"
    for parent_path in ("/", "/project1", "/local"):
        parent_op = op(parent_path)
        if parent_op is None:
            continue
        try:
            for child in parent_op.children:
                n = child.name.lower()
                if n.startswith("popx") or n.startswith("popsext"):
                    version = _parse_popx_version(child.name)
                    if version:
                        return "installed " + version
                    return "installed"
        except Exception:
            continue
    return "missing"


def _read_install_row():
    """Read parent COMP's Installstatus param. Returns 'Install   <value>'.

    Returns None if the param doesn't exist (e.g. in older COMPs).
    """
    try:
        value = parent().par.Installstatus.eval()
        if not value:
            return None
        return "{:<11} {}".format("Install", value)
    except Exception:
        return None


def _read_update_row():
    """Read parent COMP's Updatestatus + Latestversion params.

    Format depends on whether an update is available:
      - "Update     ▲ 1.5.7 available" (when Latest > Installed)
      - "Update     up to date 1.5.5"
      - "Update     <Updatestatus value>" (fallback)
    """
    try:
        installed = parent().par.Installedversion.eval() or "--"
        latest = parent().par.Latestversion.eval() or "--"
        status = parent().par.Updatestatus.eval() or ""

        # If both versions are valid and they differ, format as "update available"
        if installed != "--" and latest != "--":
            if installed != latest:
                return "{:<11} ▲ {} available (have {})".format("Update", latest, installed)
            return "{:<11} ✓ up to date {}".format("Update", installed)
        # Fall back to the raw status string
        if status:
            return "{:<11} {}".format("Update", status)
        return None
    except Exception:
        return None


def render():
    s = _state()
    if s is None:
        return "TDPilot\n" + _DASH + "\n(state_cache not loaded)\n"
    build = str(s.get("build") or app.build or "--")
    version = str(s.get("version") or "--")
    rows = [
        ("WS", str(s.get("ws") or "--")),
        ("Latency", _fmt_latency(s.get("latency_ms"))),
        ("Tools", _fmt_int(s.get("tools"))),
        ("Snapshots", _fmt_int(s.get("snapshots"))),
        ("Memory", _fmt_int(s.get("memory"))),
        ("Knowledge", _fmt_int(s.get("knowledge"))),
        ("POPx", str(s.get("popx") or "--")),
        ("Build", build),
        ("Last call", str(s.get("last_call") or "--")),
    ]
    body = "\n".join(f"{k:<11} {v}" for k, v in rows)
    out = f"TDPilot {version}\n{_DASH}\n{body}"

    # Append the install + update rows (Phase A: panel awareness of installer)
    install_row = _read_install_row()
    if install_row:
        out += "\n" + install_row
    update_row = _read_update_row()
    if update_row:
        out += "\n" + update_row
    return out


def tick():
    """Render once and write to ./status_text. Called by sibling autostart DAT.

    Re-detects POPx on every tick so plug/unplug at runtime updates the panel.
    Also re-reads installer state via the installer DAT's refresh helper, so
    the install/update rows update without the user manually clicking
    Detectstate.
    """
    cache_dat = parent().op(MCP_COMP_PATH + "/state_cache")
    if cache_dat is not None:
        try:
            cache_dat.module.update(popx=_detect_popx())
        except Exception:
            pass
    target = parent().op("status_text")
    if target is None:
        return False
    target.par.text = render()
    return True


def bootstrap():
    """Pre-populate static fields once on project load."""
    cache_dat = parent().op(MCP_COMP_PATH + "/state_cache")
    if cache_dat is None:
        return False
    callbacks = parent().op(MCP_COMP_PATH + "/callbacks")
    version = None
    if callbacks is not None:
        try:
            for line in callbacks.text.splitlines():
                if line.startswith("API_VERSION"):
                    version = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass
    build_str = str(app.build) if hasattr(app, "build") else None
    cache_dat.module.update(
        version=version,
        build=build_str,
        tools=102,
        popx=_detect_popx(),
        ws="OK",
    )
    return True
