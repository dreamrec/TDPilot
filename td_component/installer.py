"""TDPilot installer — drives the COMP's "Install" + "Update" pages.

Runs in TD's normal (unrestricted) Python — NOT through the MCP
exec-restricted path. That means subprocess, file I/O, json, urllib,
etc. all work directly. Imports go at module top; helpers live in
private functions; the public surface is just:

    detect_state() -> dict
    install_python_wrapper(progress_cb)
    install_claude_plugin(progress_cb)
    set_td_autoload(progress_cb)
    bootstrap_all(progress_cb)
    uninstall_all(progress_cb)
    check_for_updates() -> dict
    update_now(progress_cb)
    rollback(progress_cb)

Phase A scope: detect_state() + status_from_state() only. The install /
update / rollback functions are stubbed to NotImplementedError so the
parexec wiring can be tested without doing anything destructive.
"""

import json
import os
import shutil
import subprocess

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------

HOME = os.path.expanduser("~")
INSTALL_DIR = os.path.join(HOME, ".tdpilot")
CONFIG_FILE = os.path.join(HOME, ".tdpilot_path")
ENV_FILE = os.path.join(INSTALL_DIR, ".tdpilot.env")
AUTOLOAD_TOE = os.path.join(INSTALL_DIR, "tdpilot_default.toe")
PYPROJECT = os.path.join(INSTALL_DIR, "pyproject.toml")

# macOS / Windows TD prefs path. Linux deferred to v1.5.7.
if os.name == "nt":  # Windows
    PREFS_PATH = os.path.join(
        HOME, "AppData", "Roaming", "Derivative", "TouchDesigner099", "pref.txt"
    )
else:  # darwin (macOS)
    PREFS_PATH = os.path.join(
        HOME, "Library", "Application Support", "Derivative",
        "TouchDesigner099", "pref.txt"
    )

# Claude Code plugin registry — same paths the CLI reads.
CLAUDE_PLUGINS_DIR = os.path.join(HOME, ".claude", "plugins")
CLAUDE_INSTALLED_PLUGINS = os.path.join(CLAUDE_PLUGINS_DIR, "installed_plugins.json")

# Augment PATH so subprocess can find tools that live outside TD's spawn PATH.
# Order matters: Homebrew Apple Silicon first, then Intel, then user-local
# bun (Claude Code's typical location), then ~/.local/bin (uv default).
_EXTRA_PATH_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    os.path.join(HOME, ".bun", "bin"),
    os.path.join(HOME, ".local", "bin"),
)


def _augmented_path():
    """Return PATH with extra dirs prepended, deduped."""
    cur = os.environ.get("PATH", "").split(os.pathsep)
    extras = [d for d in _EXTRA_PATH_DIRS if os.path.isdir(d) and d not in cur]
    return os.pathsep.join(extras + cur) if extras else os.environ.get("PATH", "")


# ---------------------------------------------------------------------------
# State detection (Phase A surface)
# ---------------------------------------------------------------------------


def _which(cmd):
    """Find executable in augmented PATH. Returns absolute path or None."""
    finder = "where" if os.name == "nt" else "which"
    try:
        result = subprocess.run(
            [finder, cmd],
            env={**os.environ, "PATH": _augmented_path()},
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[0] or None
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _read_repo_version():
    """Parse version from ~/.tdpilot/pyproject.toml. Returns str or None."""
    if not os.path.isfile(PYPROJECT):
        return None
    try:
        with open(PYPROJECT, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("version") and "=" in stripped:
                    # version = "1.5.5"  →  1.5.5
                    return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def _read_td_prefs():
    """Read TD pref.txt as a dict. Returns {} if missing."""
    if not os.path.isfile(PREFS_PATH):
        return {}
    prefs = {}
    try:
        with open(PREFS_PATH, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or "\t" not in stripped:
                    continue
                k, _, v = stripped.partition("\t")
                prefs[k] = v
    except OSError:
        pass
    return prefs


def _is_claude_plugin_installed():
    """Check Claude Code's installed_plugins.json for the tdpilot entry."""
    if not os.path.isfile(CLAUDE_INSTALLED_PLUGINS):
        return False
    try:
        with open(CLAUDE_INSTALLED_PLUGINS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False
    plugins = data.get("plugins", {}) if isinstance(data, dict) else {}
    return "tdpilot@dreamrec-TDPilot" in plugins


def _has_secret_in_env_file():
    """True if .tdpilot.env contains a non-empty TD_MCP_SHARED_SECRET line."""
    if not os.path.isfile(ENV_FILE):
        return False
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("TD_MCP_SHARED_SECRET="):
                    value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                    return bool(value)
    except OSError:
        pass
    return False


def detect_state():
    """Probe the system, return a structured state dict.

    Pure read — never modifies anything. Safe to call repeatedly.
    """
    prefs = _read_td_prefs()
    autoload_target = prefs.get("general.startupfilename", "")

    return {
        # Tool availability
        "uv": _which("uv"),
        "git": _which("git"),
        "claude_cli": _which("claude"),
        # Python wrapper
        "repo_at_home": os.path.isfile(PYPROJECT),
        "repo_version": _read_repo_version(),
        # TD autoload
        "td_prefs_set": (
            prefs.get("general.startupfilemode") == "2"
            and autoload_target == AUTOLOAD_TOE
        ),
        "autoload_toe_exists": os.path.isfile(AUTOLOAD_TOE),
        "autoload_target": autoload_target or None,
        # Claude integration
        "claude_plugin_installed": _is_claude_plugin_installed(),
        # Auth
        "secret_present": _has_secret_in_env_file(),
        "env_file_exists": os.path.isfile(ENV_FILE),
        # Config
        "config_file_exists": os.path.isfile(CONFIG_FILE),
        "config_target": _read_config_file(),
    }


def _read_config_file():
    """Read ~/.tdpilot_path content. Returns str or None."""
    if not os.path.isfile(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Status string formatting (drives Install_status / Update_status params)
# ---------------------------------------------------------------------------


def status_from_state(state):
    """One-line summary string for the Install_status param.

    Returns one of:
      "Not installed"          — nothing on disk
      "Partial: <details>"     — some pieces but not coherent
      "Ready"                  — full install detected
      "Ready (no Claude)"      — Python wrapper + autoload but no Claude plugin
    """
    has_repo = state["repo_at_home"]
    has_autoload = state["td_prefs_set"] and state["autoload_toe_exists"]
    has_plugin = state["claude_plugin_installed"]

    if not has_repo and not has_autoload and not has_plugin:
        return "Not installed"

    if has_repo and has_autoload and has_plugin:
        return "Ready"
    if has_repo and has_autoload and not has_plugin:
        return "Ready (no Claude plugin)"

    # Partial — call out what's missing
    missing = []
    if not has_repo:
        missing.append("Python wrapper")
    if not has_autoload:
        missing.append("TD autoload")
    if not has_plugin:
        missing.append("Claude plugin")
    return "Partial: missing " + ", ".join(missing)


def update_status_from_state(state):
    """One-line summary string for the Update_status param."""
    if not state["repo_at_home"]:
        return "Install TDPilot first"
    installed = state.get("repo_version") or "unknown"
    return "Installed " + installed + " — click 'Check for Updates' to compare"


# ---------------------------------------------------------------------------
# Push state into custom params (called by parexec on pulse, and by autostart)
# ---------------------------------------------------------------------------


def refresh_status_params():
    """Run detect_state() and write results into tdpilot's custom params.

    Called from parexec_DAT.onPulse and from autostart.onStart. Idempotent.
    """
    tp = parent()
    if tp is None:
        return None
    state = detect_state()
    try:
        tp.par.Installstatus = status_from_state(state)
        tp.par.Updatestatus = update_status_from_state(state)
        tp.par.Installedversion = state.get("repo_version") or "--"
    except Exception as exc:
        print("[TDPilot installer] could not write status params:", exc)
    return state


# ---------------------------------------------------------------------------
# Installation actions — stubs for Phase A
# ---------------------------------------------------------------------------


def install_python_wrapper(progress_cb=None):
    raise NotImplementedError("Phase B")


def install_claude_plugin(progress_cb=None):
    raise NotImplementedError("Phase C")


def set_td_autoload(progress_cb=None):
    raise NotImplementedError("Phase B")


def bootstrap_all(progress_cb=None):
    raise NotImplementedError("Phase C")


def uninstall_all(progress_cb=None):
    raise NotImplementedError("Phase B")


# ---------------------------------------------------------------------------
# Update actions — stubs for Phase A
# ---------------------------------------------------------------------------


def check_for_updates():
    raise NotImplementedError("Phase D")


def update_now(progress_cb=None):
    raise NotImplementedError("Phase D")


def rollback(progress_cb=None):
    raise NotImplementedError("Phase D")
