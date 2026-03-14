"""
TDPilot setup entrypoint for TouchDesigner.

Run inside TouchDesigner Textport:

    exec(open("/ABS/PATH/TDPilot/setup_mcp_in_td.py").read(), globals(), globals())

What this does:
  1) Finds the repo root.
  2) Runs td_component/build_export_mcp_tox.py.
  3) Builds a reusable mcp_server component in a temporary container.
  4) Exports td_component/tdpilot_v1_2.tox.
  5) Optionally installs /<target>/mcp_server if TD_MCP_PARENT_PATH is set.

If auto-detect fails, set:

    import os
    os.environ["TD_MCP_REPO_ROOT"] = "/ABS/PATH/TDPilot"

If the target project root is not auto-detected, optionally also set:

    os.environ["TD_MCP_PARENT_PATH"] = "/project1"
"""

import os
import glob


def _iter_repo_candidates():
    candidates = []
    env_root = (os.environ.get("TD_MCP_REPO_ROOT") or "").strip()
    if env_root:
        candidates.append(env_root)

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.extend((script_dir, os.path.dirname(script_dir)))
    except Exception:
        pass

    # If run from a Text DAT, prefer its external file location when available.
    try:
        me_file_par = getattr(getattr(me, "par", None), "file", None)
        if me_file_par is not None:
            file_path = os.path.abspath(os.path.expanduser(str(me_file_par.eval())))
            if os.path.isfile(file_path):
                file_dir = os.path.dirname(file_path)
                candidates.extend((file_dir, os.path.dirname(file_dir)))
    except Exception:
        pass

    try:
        cwd = os.path.abspath(os.getcwd())
        candidates.extend((cwd, os.path.dirname(cwd)))
    except Exception:
        pass

    try:
        proj = os.path.abspath(project.folder)
        candidates.extend((proj, os.path.dirname(proj)))
    except Exception:
        pass

    home = os.path.expanduser("~")
    candidates.extend(
        (
            os.path.join(home, "Desktop", "TDPilot"),
            os.path.join(home, "Documents", "TDPilot"),
        )
    )
    for base in (
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
    ):
        if not os.path.isdir(base):
            continue
        for pattern in ("*TDPilot*", "*tdpilot*"):
            candidates.extend(glob.glob(os.path.join(base, pattern)))

    seen = set()
    for path in candidates:
        if not path:
            continue
        norm = os.path.abspath(os.path.expanduser(path))
        if norm in seen:
            continue
        seen.add(norm)
        yield norm


def _find_build_script():
    for root in _iter_repo_candidates():
        build_script = os.path.join(root, "td_component", "build_export_mcp_tox.py")
        callbacks = os.path.join(root, "td_component", "mcp_webserver_callbacks.py")
        if os.path.isfile(build_script) and os.path.isfile(callbacks):
            return root, build_script
    return None, None


def run_setup():
    repo_root, build_script = _find_build_script()
    if not build_script:
        print("[TDPilot] ERROR: Could not find td_component/build_export_mcp_tox.py")
        print("[TDPilot] Set TD_MCP_REPO_ROOT then run again:")
        print('  import os')
        print('  os.environ["TD_MCP_REPO_ROOT"] = "/ABS/PATH/TDPilot"')
        print('  os.environ["TD_MCP_PARENT_PATH"] = "/project1"  # optional')
        print(
            '  exec(open("/ABS/PATH/TDPilot/setup_mcp_in_td.py").read(), globals(), globals())'
        )
        return False

    os.environ["TD_MCP_REPO_ROOT"] = repo_root
    print("[TDPilot] Repo root:", repo_root)
    print("[TDPilot] Running:", build_script)
    if os.environ.get("TD_MCP_PARENT_PATH"):
        print("[TDPilot] Install target:", os.environ["TD_MCP_PARENT_PATH"])
    else:
        print("[TDPilot] Install target: none (export only)")

    with open(build_script, "r", encoding="utf-8") as handle:
        source = handle.read()

    prev_file = globals().get("__file__", None)
    globals()["__file__"] = build_script
    try:
        exec(compile(source, build_script, "exec"), globals(), globals())
    finally:
        if prev_file is None:
            globals().pop("__file__", None)
        else:
            globals()["__file__"] = prev_file
    return True


run_setup()
