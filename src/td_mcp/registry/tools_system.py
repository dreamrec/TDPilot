"""TD 2025 native-system tools — diagnostics for TD's internals.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Tools in this module:
    td_python_env_status       — Python interpreter / venv state
    td_threading_status        — thread + job manager diagnostics
    td_logger_status           — TD logger state
    td_tdresources_inspect     — /sys/TDResources inspection
    td_component_standardize   — enforce ``Version/Help/Creator`` params
                                  + optional auto-fix under undo block
    td_color_pipeline          — color space / gamma / HDR settings

All six delegate to TouchDesigner via ``exec`` with server-side Python
snippets, so the exec-safety helpers from tool_registry (``_check_exec_not_off``,
``_check_exec_mode_at_least``) are threaded in via ``_tr.`` module-attribute
lookup.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_python_env_status")
async def td_python_env_status(ctx: Context) -> dict[str, Any]:
    """Inspect the Python environment inside TouchDesigner: version, installed packages, env manager status.

    Requires 'full' exec mode — uses sys and pkg_resources which are not in the standard allowlist.
    """
    finish = _tr._start_tool(ctx, "td_python_env_status")
    try:
        off_err = _tr._check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _tr._check_exec_mode_at_least("full", "td_python_env_status")
        if mode_err:
            return mode_err
        client = _tr._get_client(ctx)
        code = (
            "import sys, json\n"
            "result = {\n"
            "    'python_version': sys.version,\n"
            "    'executable': sys.executable,\n"
            "    'paths': sys.path[:10],\n"
            "}\n"
            "try:\n"
            "    import pkg_resources\n"
            "    result['installed_packages'] = [str(d) for d in pkg_resources.working_set][:50]\n"
            "except Exception:\n"
            "    result['installed_packages'] = []\n"
            "__result__ = json.dumps(result)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "full"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        _tr._audit_log(ctx, "td_python_env_status", {})
        return data
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_python_env_status")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_threading_status")
async def td_threading_status(ctx: Context) -> dict[str, Any]:
    """Inspect the threading status inside TouchDesigner: active threads, cook rate.

    Requires 'full' exec mode — uses threading module which is not in the standard allowlist.
    """
    finish = _tr._start_tool(ctx, "td_threading_status")
    try:
        off_err = _tr._check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _tr._check_exec_mode_at_least("full", "td_threading_status")
        if mode_err:
            return mode_err
        client = _tr._get_client(ctx)
        code = (
            "import threading, json\n"
            "result = {\n"
            "    'active_thread_count': threading.active_count(),\n"
            "    'current_thread': threading.current_thread().name,\n"
            "    'thread_names': [t.name for t in threading.enumerate()],\n"
            "}\n"
            "try:\n"
            "    result['cook_rate'] = project.cookRate\n"
            "except Exception:\n"
            "    pass\n"
            "__result__ = json.dumps(result)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "full"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        _tr._audit_log(ctx, "td_threading_status", {})
        return data
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_threading_status")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_logger_status")
async def td_logger_status(ctx: Context) -> dict[str, Any]:
    """Inspect the Python logging configuration inside TouchDesigner: log level, handlers, registered loggers.

    Note: This inspects Python's logging module, not TD's native logging. Requires 'full' exec mode.
    """
    finish = _tr._start_tool(ctx, "td_logger_status")
    try:
        off_err = _tr._check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _tr._check_exec_mode_at_least("full", "td_logger_status")
        if mode_err:
            return mode_err
        client = _tr._get_client(ctx)
        code = (
            "import logging, json\n"
            "root_logger = logging.getLogger()\n"
            "result = {\n"
            "    'root_level': logging.getLevelName(root_logger.level),\n"
            "    'handler_count': len(root_logger.handlers),\n"
            "    'handlers': [type(h).__name__ for h in root_logger.handlers],\n"
            "    'loggers': list(logging.Logger.manager.loggerDict.keys())[:20],\n"
            "}\n"
            "__result__ = json.dumps(result)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "full"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        _tr._audit_log(ctx, "td_logger_status", {})
        return data
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_logger_status")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_tdresources_inspect")
async def td_tdresources_inspect(
    ctx: Context,
    category: Annotated[
        str | None,
        Field(
            default=None,
            description="Category: fonts, icons, defaults, or None for all",
        ),
    ] = None,
) -> dict[str, Any]:
    """Inspect TDResources available in the TouchDesigner installation: fonts, icons, defaults."""
    finish = _tr._start_tool(ctx, "td_tdresources_inspect")
    try:
        off_err = _tr._check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _tr._check_exec_mode_at_least("standard", "td_tdresources_inspect")
        if mode_err:
            return mode_err
        client = _tr._get_client(ctx)
        category_filter = category or ""
        safe_filter = json.dumps(category_filter)
        code = (
            "import json\n"
            "result = {'categories': {}, 'total_children': 0}\n"
            "try:\n"
            "    res = op('/sys/TDResources')\n"
            "    if res:\n"
            "        children = res.children\n"
            "        result['total_children'] = len(children)\n"
            "        filt = json.loads(" + repr(safe_filter) + ")\n"
            "        for child in children:\n"
            "            cat = child.type\n"
            "            if filt and filt.lower() not in child.name.lower() and filt.lower() not in cat.lower():\n"
            "                continue\n"
            "            if cat not in result['categories']:\n"
            "                result['categories'][cat] = []\n"
            "            result['categories'][cat].append(child.name)\n"
            "    else:\n"
            "        result['note'] = 'TDResources not found at /sys/TDResources'\n"
            "except Exception as e:\n"
            "    result['error'] = str(e)\n"
            "__result__ = json.dumps(result)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "standard"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        if isinstance(data, dict):
            data["mode"] = "live"
        _tr._audit_log(ctx, "td_tdresources_inspect", {"category": category})
        return data
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_tdresources_inspect")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_component_standardize")
async def td_component_standardize(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to COMP to audit", min_length=1),
    ],
    fix: Annotated[
        bool,
        Field(
            default=False,
            description="If True, auto-fix issues (wrapped in undo block)",
        ),
    ] = False,
) -> dict[str, Any]:
    """Audit or fix COMP standardization: required custom parameters (Version, Help, Creator), extension, naming."""
    finish = _tr._start_tool(ctx, "td_component_standardize")
    try:
        off_err = _tr._check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _tr._check_exec_mode_at_least("standard", "td_component_standardize")
        if mode_err:
            return mode_err
        client = _tr._get_client(ctx)

        safe_path = json.dumps(path)
        audit_code = (
            "import json\n"
            "_path = json.loads(" + repr(safe_path) + ")\n"
            "result = {'path': _path, 'issues': [], 'fixed': []}\n"
            "try:\n"
            "    comp = op(_path)\n"
            "    if comp is None:\n"
            "        result['error'] = 'Node not found'\n"
            "    else:\n"
            "        for par_name in ('Version', 'Help', 'Creator'):\n"
            "            if not hasattr(comp.par, par_name):\n"
            "                result['issues'].append('Missing custom parameter: ' + par_name)\n"
            "        if not comp.name[0].isupper() and not comp.name[0].isdigit():\n"
            "            result['issues'].append('Name does not start with uppercase: ' + comp.name)\n"
            "        result['has_extension'] = bool(comp.extensions)\n"
            "        result['op_type'] = comp.type\n"
        )

        if fix:
            fix_code = (
                "        page = None\n"
                "        for p in comp.customPages:\n"
                "            if p.name == 'Meta':\n"
                "                page = p\n"
                "                break\n"
                "        if page is None:\n"
                "            page = comp.appendCustomPage('Meta')\n"
                "        for par_name in ('Version', 'Help', 'Creator'):\n"
                "            if not hasattr(comp.par, par_name):\n"
                "                page.appendStr(par_name, label=par_name)\n"
                "                result['fixed'].append('Added parameter: ' + par_name)\n"
            )
            audit_code = audit_code + fix_code

        audit_code = (
            audit_code
            + "        result['issue_count'] = len(result['issues'])\n"
            + "except Exception as e:\n"
            + "    result['error'] = str(e)\n"
            + "__result__ = json.dumps(result)"
        )

        async def _do_audit():
            resp = await client.request("exec", {"code": audit_code, "exec_mode": "standard"})
            raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
            try:
                return json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                return {"raw": raw}

        if fix:
            data = await _tr._with_undo_block(client, f"td_component_standardize:{path}", _do_audit)
        else:
            data = await _do_audit()

        _tr._audit_log(ctx, "td_component_standardize", {"path": path, "fix": fix})
        return data
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_component_standardize")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_color_pipeline")
async def td_color_pipeline(ctx: Context) -> dict[str, Any]:
    """Inspect the color management pipeline in TouchDesigner: color space, gamma, display settings."""
    finish = _tr._start_tool(ctx, "td_color_pipeline")
    try:
        off_err = _tr._check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _tr._check_exec_mode_at_least("standard", "td_color_pipeline")
        if mode_err:
            return mode_err
        client = _tr._get_client(ctx)
        code = (
            "import json\n"
            "result = {}\n"
            "result['defaultParameterColorSpace'] = getattr(project, 'defaultParameterColorSpace', None)\n"
            "result['workingColorSpace'] = getattr(project, 'workingColorSpace', None)\n"
            "result['editorWindowPixelFormat'] = getattr(project, 'editorWindowPixelFormat', None)\n"
            "result['sdrReferenceWhiteNits'] = getattr(project, 'sdrReferenceWhiteNits', None)\n"
            "result['hdrReferenceWhiteNits'] = getattr(project, 'hdrReferenceWhiteNits', None)\n"
            "# Legacy fallbacks\n"
            "result['monitorGamma'] = getattr(project, 'monitorGamma', None)\n"
            "__result__ = json.dumps(result, default=str)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "standard"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        _tr._audit_log(ctx, "td_color_pipeline", {})
        return data
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_color_pipeline")
        return {"error": str(exc)}
    finally:
        finish()
