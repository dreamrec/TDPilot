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
_HOME_ENV_FILE = os.path.join(os.path.expanduser("~"), ".tdpilot", ".tdpilot.env")
_TOX_RELATIVE = os.path.join("td_component", "tdpilot.tox")
_BUILD_SCRIPT_RELATIVE = os.path.join("td_component", "build_export_mcp_tox.py")
# v1.6.5: handle both COMP names a tdpilot install might have.
# Pre-v1.5.6 the build script saved a baseCOMP named "mcp_server"; v1.5.6+
# saves a containerCOMP named "tdpilot" (the panel UI lives at this level).
# Listed newest-first so log messages reference the canonical current name
# when both are present.
_COMP_NAMES: tuple[str, ...] = ("tdpilot", "mcp_server")
_COMP_NAME = _COMP_NAMES[0]  # backward-compat alias for any external callers

# v1.6.5: where to look for existing tdpilot installs. /local is the
# canonical Startup-script-managed location; /project1 catches the very
# common case where a user dragged the .tox into the visible network and
# then project.save'd a .toe with the COMP baked in (which is what
# happened to the user reporting "panel says 1.5.3 after restart" —
# /project1/tdpilot was binding port 9981 first on every launch and the
# fresh /local/tdpilot couldn't displace it).
_SCAN_PARENTS: tuple[str, ...] = ("/local", "/project1")

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
    """Load KEY=VALUE pairs from .tdpilot.env into os.environ.

    Loads from two locations in priority order (first one wins per key):
      1. <repo_root>/.tdpilot.env         — installer-written, repo-local
      2. ~/.tdpilot/.tdpilot.env          — canonical Python-server path
                                            (auth_bootstrap.maybe_generate_secret
                                            writes here when TD_MCP_AUTOGENERATE_SECRET=1)

    Carries the shared secret and auth policy into the TD process without
    hardcoding them in the .toe file. The two-file scan keeps TD-side and
    Python-side auth in sync so the dragged-in / auto-rebuilt .tox sees
    the same secret the Python MCP server generated.

    Existing os.environ keys are NEVER overwritten — process-supplied env
    wins, matching auth_bootstrap.load_env_file's contract.
    """
    for env_path in (os.path.join(repo_root, _ENV_FILE_NAME), _HOME_ENV_FILE):
        if not os.path.isfile(env_path):
            continue
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


def _find_existing_tdpilot_comps():
    """Return ``[(parent_path, comp_path), ...]`` for every tdpilot/mcp_server
    COMP we find under the canonical scan parents (``/local``, ``/project1``).

    v1.6.5: this is the sweep that fixes the "panel says 1.5.3 after restart"
    class of bug. The pre-v1.6.5 ``_destroy_zombie_mcp_servers`` only looked
    for the legacy name "mcp_server"; the current build script saves the
    COMP as "tdpilot", so the scan never matched the user's actual stale
    install and the fresh load got shadowed forever.
    """
    found: list[tuple[str, str]] = []
    for parent_path in _SCAN_PARENTS:
        parent = op(parent_path)
        if parent is None or not hasattr(parent, "op"):
            continue
        for name in _COMP_NAMES:
            cand = parent.op(name)
            if cand is not None and getattr(cand, "isCOMP", False):
                found.append((parent_path, cand.path))
    return found


def _destroy_zombie_mcp_servers(exclude_path):
    """Backward-compat shim — pre-v1.6.5 callers used this name.

    Now delegates to the comprehensive sweep used by ``_load_tox_fast``.
    Kept as a no-arg-changing wrapper so any third-party scripts that
    `import tdpilot_startup` and call this directly keep working.
    """
    for _parent_path, comp_path in _find_existing_tdpilot_comps():
        if comp_path == exclude_path:
            continue
        try:
            print(f"[TDPilot] destroying zombie {comp_path} (not at {exclude_path})")
            op(comp_path).destroy()
        except Exception as e:
            print(f"[TDPilot] failed to destroy zombie {comp_path}: {e}")


def _load_tox_fast(tox_path):
    """Load pre-built TOX. Returns True on success.

    v1.6.5 changes:
      - Sweeps BOTH `/local` AND `/project1` for tdpilot/mcp_server COMPs.
        Pre-v1.6.5 we only managed `/local/mcp_server`, leaving any
        `/project1/tdpilot` (the result of dragging the .tox into the
        visible network at some past point) baked into the user's .toe
        and silently shadowing every fresh load via port-9981 collision.
      - Loads the new COMP into the SAME parent the previous one was at.
        If the user had `/project1/tdpilot`, the fresh load goes to
        `/project1/tdpilot` so their UI position is preserved. Falls
        back to `/local` when nothing was found.
    """
    existing = _find_existing_tdpilot_comps()

    # Pick where to load: preserve the user's existing parent if any,
    # otherwise default to /local. We pick the FIRST hit because
    # _find_existing_tdpilot_comps returns scan-parent order with /local
    # listed first — meaning if a /local install exists we keep it there,
    # and only fall back to /project1 if /local was empty.
    target_parent_path = existing[0][0] if existing else "/local"

    target_parent = op(target_parent_path)
    if target_parent is None or not getattr(target_parent, "isCOMP", False):
        print(f"[TDPilot] ERROR: target parent {target_parent_path} not found")
        return False

    # Destroy ALL existing tdpilot/mcp_server COMPs to avoid name
    # collisions on loadTox AND port-9981 binding races on the WS DAT.
    for _parent_path, comp_path in existing:
        try:
            print(f"[TDPilot] destroying stale {comp_path}")
            op(comp_path).destroy()
        except Exception as e:
            print(f"[TDPilot] failed to destroy {comp_path}: {e}")

    try:
        # loadTox on a COMP in TD 2025+ loads as a child and returns the new COMP
        loaded = target_parent.loadTox(tox_path)
        if loaded is not None:
            print(f"[TDPilot] v{_read_api_version(tox_path)} loaded into {loaded.path}")
            return True
    except Exception as e:
        print(f"[TDPilot] loadTox failed ({e}), falling back to rebuild")

    return False


def _read_api_version(tox_path):
    """Read API_VERSION from mcp_webserver_callbacks.py adjacent to the .tox.

    Reading the version from source (rather than hardcoding it here) means
    the startup banner stays correct forever — no per-release maintenance,
    no drift between this file and ``mcp_webserver_callbacks.py``. Falls
    back to ``"?"`` if the file is missing (e.g. the user dragged the .tox
    into a directory without the rest of the repo). A fallback string is
    preferable to crashing TD startup over a banner.
    """
    callbacks_path = os.path.join(os.path.dirname(tox_path), "mcp_webserver_callbacks.py")
    try:
        with open(callbacks_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("API_VERSION"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return "?"


def _auto_pin_latest_tag(repo_root):
    """Optional: git fetch + checkout latest released tag at TD launch.

    Opt-in via ``TDPILOT_AUTO_PIN_TAG=1`` in ``~/.tdpilot/.tdpilot.env``
    (toggle with ``npx tdpilot autopin --enable`` / ``--disable``).

    When enabled, this:
      1. ``git fetch --tags`` (5s timeout) — refreshes remote tag list.
      2. Resolves the latest tag reachable from ``origin/main``.
      3. If HEAD is already at that tag, no-op silently.
      4. Otherwise ``git checkout <tag>`` so the .tox loaded immediately
         after is the freshly-released one.

    NEVER blocks TD startup. Every git call has a timeout; every error
    path catches and prints to Textport without re-raising. Offline
    starts incur a 5-second fetch timeout, then proceed with the current
    pinned tag — the system degrades gracefully.

    Why this lives in the startup script (not in the running .tox):
    we need the new .tox on disk BEFORE the loadTox call, so the pin
    must happen earlier in the boot sequence than the tdpilot COMP can
    react. The .tox itself can never reload itself live — TD has no
    "reload .tox in place" primitive — so the pin-then-load flow is
    the only safe shape.
    """
    if os.environ.get("TDPILOT_AUTO_PIN_TAG", "0") != "1":
        return
    if not os.path.isdir(os.path.join(repo_root, ".git")):
        print("[TDPilot] AUTOPIN skipped — not a git checkout at " + repo_root)
        return

    import subprocess  # local import: keeps cold-start cheap when autopin disabled

    try:
        subprocess.run(
            ["git", "fetch", "--tags", "--quiet"],
            cwd=repo_root,
            timeout=5,
            capture_output=True,
            check=True,
        )
        # Latest tag reachable from origin/main (the release branch).
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "origin/main"],
            cwd=repo_root,
            timeout=2,
            capture_output=True,
            check=True,
            text=True,
        )
        latest_tag = result.stdout.strip()
        if not latest_tag:
            return

        # What tag (if any) is HEAD currently exactly at?
        current_proc = subprocess.run(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            cwd=repo_root,
            timeout=2,
            capture_output=True,
            text=True,
        )
        current_tag = current_proc.stdout.strip() if current_proc.returncode == 0 else ""

        if current_tag == latest_tag:
            return  # already on latest, nothing to do

        subprocess.run(
            ["git", "checkout", "--quiet", latest_tag],
            cwd=repo_root,
            timeout=10,
            capture_output=True,
            check=True,
        )
        print(
            "[TDPilot] AUTOPIN updated "
            + repo_root
            + " from "
            + (current_tag or "HEAD")
            + " to "
            + latest_tag
        )
    except subprocess.TimeoutExpired:
        print("[TDPilot] AUTOPIN skipped — git timeout (offline?)")
    except subprocess.CalledProcessError as exc:
        # Stay silent on stderr details to avoid noisy startup logs;
        # the user can run `git status` in ~/.tdpilot themselves to debug.
        print("[TDPilot] AUTOPIN failed (continuing with current state): exit " + str(exc.returncode))
    except Exception as exc:  # noqa: BLE001 — startup must not crash TD
        print("[TDPilot] AUTOPIN unexpected error (continuing): " + str(exc))


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
    # MUST be called before _auto_pin_latest_tag — the env file is where the
    # TDPILOT_AUTO_PIN_TAG opt-in flag lives.
    _load_env_file(repo_root)

    # v1.6.4: optional pre-load git pin to latest released tag (opt-in via env).
    # Runs BEFORE we resolve tox_path so a fresh checkout's .tox is what gets
    # loaded into /local. Non-blocking — failures fall through to the existing
    # (potentially stale) checkout.
    _auto_pin_latest_tag(repo_root)

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


# v1.6.4: tests need to import this module without auto-firing _startup()
# (which would call op() / parent() and fail outside TD). Set
# TDPILOT_STARTUP_SKIP=1 in the test setup; production TD launches leave
# it unset, so behavior is unchanged.
if os.environ.get("TDPILOT_STARTUP_SKIP") != "1":
    try:
        _startup()
    except Exception as e:
        print(f"[TDPilot] Startup error: {e}")
        print("[TDPilot] TDPilot did not load. Try: npx tdpilot install")
