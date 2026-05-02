"""TDPilot installer — drives the COMP's "Install" + "Update" pages.

Runs in TD's normal (unrestricted) Python — NOT through the MCP
exec-restricted path. That means subprocess, file I/O, json, urllib,
threading, etc. all work directly.

Public surface:
    detect_state() -> dict
    install_python_wrapper() -> (started, message)
    install_claude_plugin() -> (started, message)
    set_td_autoload() -> (started, message)
    bootstrap_all() -> (started, message)
    uninstall_all() -> (started, message)
    check_for_updates() -> dict
    update_now() -> (started, message)
    rollback() -> (started, message)
    refresh_status_params() -> dict          # autostart calls this
    get_job_state() -> dict                  # autostart polls this each frame
    consume_pending_main_thread_action() -> Optional[str]

Threading model:
    Long-running ops run in a daemon Thread. The thread is FORBIDDEN from
    touching TD ops directly — it only touches files, subprocess, and
    the lock-protected _job_state dict. When the thread needs a
    main-thread action like project.save(), it sets
    _job_state["pending_action"] and waits; autostart.onFrameStart
    notices the flag, performs the action, and clears it.

Late-binding env reads:
    INSTALL_DIR, CONFIG_FILE etc. are functions, not constants, so
    setting TDPILOT_INSTALL_DIR mid-session redirects subsequent
    operations without needing to reload the module.
"""

import json
import os
import shutil
import subprocess
import threading
import time

# ---------------------------------------------------------------------------
# Path helpers (late-binding so env-var overrides take effect mid-session)
# ---------------------------------------------------------------------------

HOME = os.path.expanduser("~")

REPO_URL = "https://github.com/dreamrec/TDPilot.git"
ZIP_URL = "https://github.com/dreamrec/TDPilot/archive/refs/heads/main.zip"


def install_dir():
    return os.environ.get("TDPILOT_INSTALL_DIR") or os.path.join(HOME, ".tdpilot")


def config_file():
    return os.environ.get("TDPILOT_CONFIG_FILE") or os.path.join(HOME, ".tdpilot_path")


def env_file():
    return os.path.join(install_dir(), ".tdpilot.env")


def autoload_toe():
    return os.path.join(install_dir(), "tdpilot_default.toe")


def pyproject():
    return os.path.join(install_dir(), "pyproject.toml")


def backups_dir():
    return os.path.join(install_dir(), "backups")


def prefs_path():
    if os.name == "nt":
        return os.path.join(
            HOME, "AppData", "Roaming", "Derivative", "TouchDesigner099", "pref.txt"
        )
    return os.path.join(
        HOME, "Library", "Application Support", "Derivative",
        "TouchDesigner099", "pref.txt"
    )


CLAUDE_PLUGINS_DIR = os.path.join(HOME, ".claude", "plugins")
CLAUDE_INSTALLED_PLUGINS = os.path.join(CLAUDE_PLUGINS_DIR, "installed_plugins.json")

_EXTRA_PATH_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    os.path.join(HOME, ".bun", "bin"),
    os.path.join(HOME, ".local", "bin"),
)


# Backwards-compat module-level constants (some callers still use these).
# Kept as references to the function results AT IMPORT TIME — for the
# sandboxed test path we always call the function directly.
INSTALL_DIR = install_dir()
CONFIG_FILE = config_file()
ENV_FILE = env_file()
AUTOLOAD_TOE = autoload_toe()
PYPROJECT = pyproject()
BACKUPS_DIR = backups_dir()
PREFS_PATH = prefs_path()


# ---------------------------------------------------------------------------
# Job state — lock-protected shared dict between bg thread and TD main thread
# ---------------------------------------------------------------------------

_job_state = {
    "name": None,
    "stage": None,
    "message": "",
    "started_at": None,
    "done": False,
    "success": None,
    "error": None,
    "pending_action": None,
    "pending_done": False,
}
_job_lock = threading.Lock()


def get_job_state():
    with _job_lock:
        return dict(_job_state)


def consume_pending_main_thread_action():
    with _job_lock:
        action = _job_state["pending_action"]
        if action is None:
            return None
        _job_state["pending_action"] = None
        return action


def mark_pending_action_done(success=True, error=None):
    with _job_lock:
        _job_state["pending_done"] = True
        if not success and error:
            _job_state["error"] = error


def _wait_for_main_thread_action(action_name, timeout=10):
    with _job_lock:
        _job_state["pending_action"] = action_name
        _job_state["pending_done"] = False
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _job_lock:
            if _job_state["pending_done"]:
                err = _job_state.get("error")
                _job_state["pending_done"] = False
                if err:
                    raise RuntimeError(err)
                return True
        time.sleep(0.05)
    raise TimeoutError("main-thread action " + action_name + " timed out")


def _start_job(name, target_func):
    with _job_lock:
        if _job_state["name"] is not None and not _job_state["done"]:
            return False, "Job already running: " + _job_state["name"]
        _job_state["name"] = name
        _job_state["stage"] = "starting"
        _job_state["message"] = "Starting " + name + "..."
        _job_state["started_at"] = time.time()
        _job_state["done"] = False
        _job_state["success"] = None
        _job_state["error"] = None
        _job_state["pending_action"] = None
        _job_state["pending_done"] = False

    def progress_cb(stage, message):
        with _job_lock:
            _job_state["stage"] = stage
            _job_state["message"] = message
        print("[TDPilot installer]", stage + ":", message)

    def runner():
        try:
            target_func(progress_cb)
            with _job_lock:
                _job_state["done"] = True
                _job_state["success"] = True
                _job_state["message"] = name + " complete"
        except Exception as e:
            with _job_lock:
                _job_state["done"] = True
                _job_state["success"] = False
                _job_state["error"] = str(e)
                _job_state["message"] = "Error: " + str(e)[:120]
            print("[TDPilot installer] " + name + " failed:", e)

    t = threading.Thread(target=runner, name="tdpilot_" + name, daemon=True)
    t.start()
    return True, "Started"


# ---------------------------------------------------------------------------
# PATH augmentation + tool probing
# ---------------------------------------------------------------------------


def _augmented_path():
    cur = os.environ.get("PATH", "").split(os.pathsep)
    extras = [d for d in _EXTRA_PATH_DIRS if os.path.isdir(d) and d not in cur]
    return os.pathsep.join(extras + cur) if extras else os.environ.get("PATH", "")


def _which(cmd):
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


def _run(cmd, **kwargs):
    env = kwargs.pop("env", None) or os.environ.copy()
    env["PATH"] = _augmented_path()
    return subprocess.run(
        cmd, env=env, capture_output=True, text=True,
        timeout=kwargs.pop("timeout", 300), **kwargs
    )


# ---------------------------------------------------------------------------
# State detection
# ---------------------------------------------------------------------------


def _read_repo_version():
    py = pyproject()
    if not os.path.isfile(py):
        return None
    try:
        with open(py, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("version") and "=" in stripped:
                    return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def _read_td_prefs():
    pp = prefs_path()
    if not os.path.isfile(pp):
        return {}
    prefs = {}
    try:
        with open(pp, encoding="utf-8") as f:
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
    ef = env_file()
    if not os.path.isfile(ef):
        return False
    try:
        with open(ef, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("TD_MCP_SHARED_SECRET="):
                    value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                    return bool(value)
    except OSError:
        pass
    return False


def _read_config_file():
    cf = config_file()
    if not os.path.isfile(cf):
        return None
    try:
        with open(cf, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def detect_state():
    prefs = _read_td_prefs()
    autoload_target = prefs.get("general.startupfilename", "")
    return {
        "uv": _which("uv"),
        "git": _which("git"),
        "claude_cli": _which("claude"),
        "repo_at_home": os.path.isfile(pyproject()),
        "repo_version": _read_repo_version(),
        "td_prefs_set": (
            prefs.get("general.startupfilemode") == "2"
            and autoload_target == autoload_toe()
        ),
        "autoload_toe_exists": os.path.isfile(autoload_toe()),
        "autoload_target": autoload_target or None,
        "claude_plugin_installed": _is_claude_plugin_installed(),
        "secret_present": _has_secret_in_env_file(),
        "env_file_exists": os.path.isfile(env_file()),
        "config_file_exists": os.path.isfile(config_file()),
        "config_target": _read_config_file(),
    }


def status_from_state(state):
    has_repo = state["repo_at_home"]
    has_autoload = state["td_prefs_set"] and state["autoload_toe_exists"]
    has_plugin = state["claude_plugin_installed"]
    if not has_repo and not has_autoload and not has_plugin:
        return "Not installed"
    if has_repo and has_autoload and has_plugin:
        return "Ready"
    if has_repo and has_autoload and not has_plugin:
        return "Ready (no Claude plugin)"
    missing = []
    if not has_repo:
        missing.append("Python wrapper")
    if not has_autoload:
        missing.append("TD autoload")
    if not has_plugin:
        missing.append("Claude plugin")
    return "Partial: missing " + ", ".join(missing)


def update_status_from_state(state):
    if not state["repo_at_home"]:
        return "Install TDPilot first"
    installed = state.get("repo_version") or "unknown"
    return "Installed " + installed + " — click 'Check for Updates' to compare"


def refresh_status_params():
    tp = parent()
    if tp is None:
        return None
    state = detect_state()
    try:
        with _job_lock:
            job_running = (
                _job_state["name"] is not None
                and not _job_state["done"]
            )
            job_message = _job_state["message"] if job_running else None
        if job_message:
            tp.par.Installstatus = job_message
        else:
            tp.par.Installstatus = status_from_state(state)
        tp.par.Updatestatus = update_status_from_state(state)
        tp.par.Installedversion = state.get("repo_version") or "--"
    except Exception as exc:
        print("[TDPilot installer] could not write status params:", exc)
    return state


# ---------------------------------------------------------------------------
# Subprocess primitives
# ---------------------------------------------------------------------------


def _install_uv():
    if os.name == "nt":
        cmd = ["powershell", "-ExecutionPolicy", "ByPass", "-c",
               "irm https://astral.sh/uv/install.ps1 | iex"]
    else:
        cmd = ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"]
    result = _run(cmd, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(
            "uv install failed: " + (result.stderr or result.stdout)[:300]
        )


def _git_clone(target_dir):
    git = _which("git")
    if git is None:
        return False
    result = _run([git, "clone", REPO_URL, target_dir], timeout=180)
    if result.returncode != 0:
        raise RuntimeError(
            "git clone failed: " + (result.stderr or result.stdout)[:300]
        )
    return True


def _git_pin_to_latest_tag(target_dir):
    git = _which("git")
    if git is None:
        return None
    try:
        tag = _run(
            [git, "describe", "--tags", "--abbrev=0"],
            cwd=target_dir, timeout=10,
        ).stdout.strip()
        if tag:
            _run([git, "checkout", tag], cwd=target_dir, timeout=10)
            return tag
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _zip_download(target_dir):
    import urllib.request
    import zipfile
    import tempfile
    fd, zip_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        urllib.request.urlretrieve(ZIP_URL, zip_path)
        extract_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(extract_dir)
            extracted = os.path.join(extract_dir, "TDPilot-main")
            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            shutil.move(extracted, target_dir)
        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)
    finally:
        try:
            os.unlink(zip_path)
        except OSError:
            pass


def _uv_sync(repo_dir):
    uv = _which("uv")
    if uv is None:
        raise RuntimeError("uv not found after install attempt")
    result = _run(
        [uv, "sync", "--directory", repo_dir],
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "uv sync failed: " + (result.stderr or result.stdout)[:500]
        )


def _write_env_file_if_missing():
    ef = env_file()
    if os.path.isfile(ef):
        return False
    os.makedirs(os.path.dirname(ef), exist_ok=True)
    with open(ef, "w", encoding="utf-8") as f:
        f.write("# TDPilot env file written by .tox installer\n")
        f.write("TD_MCP_REQUIRE_AUTH=0\n")
        f.write("TD_MCP_EXEC_MODE=restricted\n")
    os.chmod(ef, 0o600)
    return True


def _write_config_file():
    cf = config_file()
    parent_dir = os.path.dirname(cf)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(cf, "w", encoding="utf-8") as f:
        f.write(install_dir() + "\n")


def _update_td_prefs():
    pp = prefs_path()
    prefs_dir = os.path.dirname(pp)
    os.makedirs(prefs_dir, exist_ok=True)
    prefs = _read_td_prefs()
    if os.path.isfile(pp):
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup = pp + ".tdpilot-backup-" + ts
        if not os.path.isfile(backup):
            shutil.copy2(pp, backup)
    prefs["general.startupfilemode"] = "2"
    prefs["general.startupfilename"] = autoload_toe()
    lines = [k + "\t" + v for k, v in prefs.items()]
    with open(pp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _revert_td_prefs():
    pp = prefs_path()
    if not os.path.isfile(pp):
        return
    prefs = _read_td_prefs()
    target = autoload_toe()
    if (prefs.get("general.startupfilemode") == "2"
            and prefs.get("general.startupfilename") == target):
        prefs.pop("general.startupfilemode", None)
        prefs.pop("general.startupfilename", None)
        lines = [k + "\t" + v for k, v in prefs.items()]
        with open(pp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Action: install_python_wrapper
# ---------------------------------------------------------------------------


def install_python_wrapper(progress_cb=None):
    return _start_job("install_python_wrapper", _do_install_python_wrapper)


def _do_install_python_wrapper(progress_cb):
    progress_cb("checking_uv", "Checking uv...")
    if _which("uv") is None:
        progress_cb("install_uv", "Installing uv (curl ... | sh)...")
        _install_uv()
        if _which("uv") is None:
            raise RuntimeError("uv install completed but binary still not on PATH")
    else:
        progress_cb("checking_uv", "uv found at " + _which("uv"))

    target = install_dir()
    progress_cb("checking_repo", "Checking " + target + "...")
    if os.path.isfile(pyproject()):
        progress_cb("checking_repo", "Already cloned at " + target)
    else:
        progress_cb("clone", "Cloning TDPilot repo...")
        cloned = _git_clone(target)
        if not cloned:
            progress_cb("clone", "git missing, downloading zip instead...")
            _zip_download(target)
        tag = _git_pin_to_latest_tag(target)
        if tag:
            progress_cb("clone", "Pinned to release tag " + tag)

    progress_cb("uv_sync", "Syncing Python deps (this can take 30s on first run)...")
    _uv_sync(target)

    progress_cb("env_file", "Writing .tdpilot.env...")
    wrote = _write_env_file_if_missing()
    if not wrote:
        progress_cb("env_file", ".tdpilot.env already exists, leaving it untouched")

    progress_cb("done", "Python wrapper ready at " + target)


# ---------------------------------------------------------------------------
# Action: set_td_autoload
# ---------------------------------------------------------------------------


def set_td_autoload(progress_cb=None):
    return _start_job("set_td_autoload", _do_set_td_autoload)


def _do_set_td_autoload(progress_cb):
    if not os.path.isfile(pyproject()):
        raise RuntimeError("Python wrapper not installed yet — run that first")

    progress_cb("config", "Writing " + config_file() + "...")
    _write_config_file()

    progress_cb("prefs", "Updating TD preferences...")
    _update_td_prefs()

    progress_cb("save_toe", "Saving current project as autoload .toe... (main-thread)")
    _wait_for_main_thread_action("save_toe", timeout=30)

    progress_cb("done", "TD autoload configured. Restart TD to pick up changes.")


# ---------------------------------------------------------------------------
# Action: uninstall_all
# ---------------------------------------------------------------------------


def uninstall_all(progress_cb=None):
    return _start_job("uninstall_all", _do_uninstall_all)


def _do_uninstall_all(progress_cb):
    target = install_dir()
    cf = config_file()
    at = autoload_toe()

    progress_cb("prefs", "Reverting TD preferences...")
    _revert_td_prefs()

    progress_cb("config", "Removing " + cf + "...")
    if os.path.isfile(cf):
        os.unlink(cf)

    progress_cb("autoload", "Removing autoload .toe...")
    if os.path.isfile(at):
        os.unlink(at)

    if os.environ.get("TDPILOT_KEEP_INSTALL_DIR") == "1":
        progress_cb("install_dir",
                    "Skipping " + target + " removal "
                    "(TDPILOT_KEEP_INSTALL_DIR=1)")
    else:
        progress_cb("install_dir", "Removing " + target + "...")
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=False)

    progress_cb("done",
                "Uninstalled. TDPilot will not auto-load on next TD launch.")


# ---------------------------------------------------------------------------
# Phase C / D stubs
# ---------------------------------------------------------------------------


def install_claude_plugin(progress_cb=None):
    raise NotImplementedError("Phase C")


def bootstrap_all(progress_cb=None):
    raise NotImplementedError("Phase C")


def check_for_updates():
    raise NotImplementedError("Phase D")


def update_now(progress_cb=None):
    raise NotImplementedError("Phase D")


def rollback(progress_cb=None):
    raise NotImplementedError("Phase D")
