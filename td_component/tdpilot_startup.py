"""
TDPilot auto-load startup script for TouchDesigner.

Place in ~/Documents/Derivative/Startup/ to auto-load TDPilot on every TD launch.
Installed automatically by: npx tdpilot install

Reads ~/.tdpilot_path to find the TDPilot repo root, then either:
  1. Loads the pre-built tdpilot.tox into /local (fast path)
  2. Rebuilds from source if the TOX is missing or stale (fallback)

Never crashes TD startup — all errors are caught and printed to Textport.
"""

import glob
import os

_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".tdpilot_path")
_ENV_FILE_NAME = ".tdpilot.env"
_TOX_RELATIVE = os.path.join("td_component", "tdpilot.tox")
_BUILD_SCRIPT_RELATIVE = os.path.join("td_component", "build_export_mcp_tox.py")
_COMP_NAME = "mcp_server"

# Repo root validation markers (same as build_export_mcp_tox.py _is_repo_root)
_MARKER_FILES = [
    "pyproject.toml",
    os.path.join("td_component", "mcp_webserver_callbacks.py"),
]

# Source files whose mtime is checked against the TOX for staleness.
# Only files that are embedded in the TOX — excludes this startup script
# and the build script itself.
_SOURCE_GLOB = os.path.join("td_component", "*.py")
_STALENESS_EXCLUDE = {"tdpilot_startup.py", "build_export_mcp_tox.py"}


def _read_config():
    """Read repo root path from ~/.tdpilot_path. Returns None if missing."""
    if not os.path.isfile(_CONFIG_FILE):
        return None
    with open(_CONFIG_FILE, encoding="utf-8") as f:
        path = f.read().strip()
    return path if path else None


def _load_env_file(repo_root):
    """Load KEY=VALUE pairs from <repo_root>/.tdpilot.env into os.environ.

    Written by the installer; carries the shared secret and auth policy into
    the TD process without hardcoding it in the .toe file.
    """
    env_path = os.path.join(repo_root, _ENV_FILE_NAME)
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError as exc:
        print(f"[TDPilot] Could not read {env_path}: {exc}")


def _validate_repo(repo_root):
    """Check that repo_root contains expected marker files."""
    for marker in _MARKER_FILES:
        if not os.path.isfile(os.path.join(repo_root, marker)):
            return False
    return True


def _is_tox_stale(repo_root, tox_path):
    """Return True if any td_component/*.py source file is newer than the TOX."""
    try:
        tox_mtime = os.path.getmtime(tox_path)
    except OSError:
        return True
    for src in glob.glob(os.path.join(repo_root, _SOURCE_GLOB)):
        if os.path.basename(src) in _STALENESS_EXCLUDE:
            continue
        try:
            if os.path.getmtime(src) > tox_mtime:
                return True
        except OSError:
            continue
    return False


def _destroy_zombie_mcp_servers(exclude_path):
    """Destroy any mcp_server COMPs OUTSIDE exclude_path.

    If a user re-saves the default .toe with /local/mcp_server loaded, TD
    bakes a COPY at /project1/mcp_server. Next TD launch opens BOTH — the
    /project1 copy binds to port 9981 first with its stale callbacks and
    shadows the fresh /local one. We hit this during v1.3.4 debugging and
    it's easy to re-trigger. This routine scans the whole project at
    startup and destroys any non-/local mcp_server we find. See audit D-1.
    """
    try:
        root = op("/")
        if root is None or not hasattr(root, "findChildren"):
            return
        # Look only at known hostnames to avoid walking the whole project graph.
        for parent_path in ("/project1", "/"):
            parent = op(parent_path)
            if parent is None:
                continue
            cand = parent.op(_COMP_NAME) if hasattr(parent, "op") else None
            if cand is None:
                continue
            if cand.path == exclude_path:
                continue
            print(f"[TDPilot] destroying zombie {cand.path} (not at {exclude_path})")
            try:
                cand.destroy()
            except Exception as e:
                print(f"[TDPilot] failed to destroy zombie {cand.path}: {e}")
    except Exception as e:
        print(f"[TDPilot] zombie scan error: {e}")


def _load_tox_fast(tox_path):
    """Load pre-built TOX into /local. Returns True on success."""
    local = op("/local")
    if local is None or not getattr(local, "isCOMP", False):
        print("[TDPilot] ERROR: /local container not found")
        return False

    # Destroy existing mcp_server if present
    existing = local.op(_COMP_NAME)
    if existing is not None:
        existing.destroy()

    # Also destroy any stray mcp_server elsewhere (e.g. /project1/mcp_server
    # baked into an auto-saved .toe) — see audit D-1.
    _destroy_zombie_mcp_servers(exclude_path="/local/" + _COMP_NAME)

    try:
        # loadTox on a COMP in TD 2025+ loads as a child and returns the new COMP
        loaded = local.loadTox(tox_path)
        if loaded is not None:
            print(f"[TDPilot] v1.3 loaded from {tox_path}")
            return True
    except Exception as e:
        print(f"[TDPilot] loadTox failed ({e}), falling back to rebuild")

    return False


def _rebuild_from_source(repo_root):
    """Run build_export_mcp_tox.py to rebuild and install into /local."""
    build_script = os.path.join(repo_root, _BUILD_SCRIPT_RELATIVE)
    if not os.path.isfile(build_script):
        print(f"[TDPilot] ERROR: Build script not found: {build_script}")
        return False

    # Set env so the build script skips heuristic repo detection
    os.environ["TD_MCP_REPO_ROOT"] = repo_root
    # Ensure it installs into /local (default, but be explicit)
    os.environ.pop("TD_MCP_PARENT_PATH", None)

    print("[TDPilot] Rebuilding from source...")
    with open(build_script, encoding="utf-8") as f:
        source = f.read()

    # Same exec pattern as setup_mcp_in_td.py — runs the build script
    # in the current TD Python environment. Input is from the validated
    # repo root (checked by _validate_repo), not arbitrary user input.
    prev_file = globals().get("__file__", None)
    globals()["__file__"] = build_script
    try:
        exec(compile(source, build_script, "exec"), globals(), globals())  # noqa: S102
    finally:
        if prev_file is None:
            globals().pop("__file__", None)
        else:
            globals()["__file__"] = prev_file
    return True


def _startup():
    """Main entry point — called at module load time."""
    repo_root = _read_config()
    if repo_root is None:
        # No config file — TDPilot not installed via CLI, skip silently
        return

    if not os.path.isdir(repo_root):
        print(f"[TDPilot] WARNING: Repo not found at {repo_root}")
        print("[TDPilot] Re-run: npx tdpilot install")
        return

    if not _validate_repo(repo_root):
        print(f"[TDPilot] WARNING: Invalid repo at {repo_root}")
        print("[TDPilot] Re-run: npx tdpilot install")
        return

    # Load installer-written secret/policy env before the .tox runs its callbacks.
    _load_env_file(repo_root)

    tox_path = os.path.join(repo_root, _TOX_RELATIVE)
    tox_exists = os.path.isfile(tox_path)
    stale = _is_tox_stale(repo_root, tox_path) if tox_exists else True

    if tox_exists and not stale:
        # Fast path: load pre-built TOX
        if _load_tox_fast(tox_path):
            return
        # If loadTox failed, fall through to rebuild

    # Rebuild fallback
    _rebuild_from_source(repo_root)


try:
    _startup()
except Exception as e:
    print(f"[TDPilot] Startup error: {e}")
    print("[TDPilot] TDPilot did not load. Try: npx tdpilot install")
