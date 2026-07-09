"""Meta tools — agent observability + server self-management.

Server-local tools that don't talk to TouchDesigner over MCP:

* ``td_get_activity_log`` — recent tool-call history (server-side ring
  buffer). Useful for Claude to inspect what it's done in this session
  across MCP request boundaries.
* ``td_self_update`` — check for and install a newer TDPilot release
  from GitHub. Closes the long-running staleness problem documented in
  ``CLAUDE.md`` (seven artifact layers go stale silently).
* ``td_sync_status`` — one-call drift report for server version,
  TouchDesigner component version, package releases, plugin caches, and
  source-checkout ``.tox`` freshness when that check is applicable.
* ``td_sync_diagnose`` — stricter local/live version + auth fingerprint
  diagnostic that never exposes secret material.

Neither tool requires a live TD connection or an exec-mode privilege —
they introspect or mutate server-local state only. That's why they live
in a dedicated module instead of ``tools_info.py`` or ``tools_system.py``.

Part of the v2.0.3 surface (tool count 110 -> 112; 114 total since td_brain_ground/td_brain_propose).
"""

from __future__ import annotations

import importlib.util
import json
import urllib.request
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import mcp  # noqa: E402


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _expected_github_description(*, version: str, tool_count: int) -> str:
    return (
        f"TDPilot v{version} — TouchDesigner AI assistant ({tool_count} MCP tools, "
        "correctness-first brain: plan -> execute -> validate -> rollback, "
        "656 operator cards, read-only cockpit UI)"
    )


def _fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "tdpilot-sync-status"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = resp.read()
    data = json.loads(payload)
    return data if isinstance(data, dict) else {}


def _tox_freshness_status() -> dict[str, Any]:
    root = _repo_root()
    script = root / "scripts" / "check_tox_freshness.py"
    tox = root / "td_component" / "tdpilot.tox"
    if not script.exists() or not tox.exists():
        return {
            "fresh": None,
            "status": "not_applicable",
            "message": "tox freshness is only available from a source checkout with td_component/tdpilot.tox.",
            "messages": [],
        }
    try:
        spec = importlib.util.spec_from_file_location("tdpilot_check_tox_freshness", script)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load {script}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ok, messages = module.check_freshness(root)
        return {"fresh": bool(ok), "status": "fresh" if ok else "stale", "messages": list(messages)}
    except Exception as exc:
        return {"fresh": False, "status": "error", "error": str(exc), "messages": []}


def _plugin_cache_versions() -> list[dict[str, Any]]:
    from td_mcp import __version__ as server_version

    home = Path.home()
    roots = [
        ("claude", home / ".claude" / "plugins" / "cache" / "dreamrec-TDPilot" / "tdpilot"),
        ("codex", home / ".codex" / "plugins" / "cache" / "tdpilot-local" / "tdpilot"),
    ]
    rows: list[dict[str, Any]] = []
    for name, root in roots:
        versions: list[str] = []
        if root.is_dir():
            versions = sorted(path.name for path in root.iterdir() if path.is_dir())
        rows.append(
            {
                "name": name,
                "path": str(root),
                "versions": versions,
                "contains_server_version": server_version in versions,
            }
        )
    return rows


def _remote_release_status() -> dict[str, Any]:
    from td_mcp import __version__ as server_version
    from td_mcp import self_updater

    status: dict[str, Any] = {"installed": server_version}
    github = self_updater.run(check_only=True)
    if "error" in github:
        status["github_error"] = github["error"]
    else:
        status["github_latest"] = github.get("latest")
        status["github_release_url"] = github.get("release_url")
        status["newer_available"] = github.get("newer_available", False)

    try:
        npm = _fetch_json("https://registry.npmjs.org/tdpilot/latest")
        status["npm_latest"] = npm.get("version")
    except Exception as exc:
        status["npm_error"] = str(exc)

    return status


def _github_repo_description_status() -> dict[str, Any]:
    from td_mcp import __version__ as server_version
    from td_mcp.release_gates import EXPECTED_MIN_TOOL_COUNT

    expected = _expected_github_description(version=server_version, tool_count=EXPECTED_MIN_TOOL_COUNT)
    try:
        repo = _fetch_json("https://api.github.com/repos/dreamrec/TDPilot")
    except Exception as exc:
        return {"expected": expected, "error": str(exc), "matches": None}

    description = str(repo.get("description") or "")
    return {
        "description": description,
        "expected": expected,
        "matches": description == expected,
        "html_url": repo.get("html_url"),
    }


async def _live_component_status(ctx: Context) -> dict[str, Any]:
    from td_mcp import __version__ as server_version

    status: dict[str, Any] = {
        "reachable": False,
        "component_version": None,
        "matches_server": None,
    }
    try:
        client = _tr._get_client(ctx)
    except Exception as exc:
        status["error"] = str(exc)
        return status

    last_error = ""
    for endpoint in ("health", "info"):
        try:
            payload = await client.request(endpoint)
        except Exception as exc:
            last_error = str(exc)
            continue
        if not isinstance(payload, dict):
            continue
        status["reachable"] = True
        status["source_endpoint"] = endpoint
        status["raw_status"] = payload.get("status")
        component_version = (
            payload.get("mcp_component_version")
            or payload.get("api_version")
            or payload.get("component_version")
        )
        if component_version:
            status["component_version"] = str(component_version)
            status["matches_server"] = str(component_version) == server_version
            return status

    if last_error:
        status["error"] = last_error
    return status


@mcp.tool(
    name="td_get_activity_log",
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    ),
)
async def td_get_activity_log(
    ctx: Context,
    limit: Annotated[
        int,
        Field(
            default=20,
            ge=1,
            le=200,
            description="How many recent entries to return (1–200, newest first).",
        ),
    ] = 20,
    tool_filter: Annotated[
        str | None,
        Field(
            default=None,
            description="If set, only return entries for this exact tool name.",
        ),
    ] = None,
) -> str:
    """Recent tool-call activity from this MCP server's ring buffer.

    Returns a JSON array of entries newest-first, each with ``ts``, ``tool``,
    ``args_summary``, ``result_summary``, ``duration_ms``, ``ok``. The buffer
    holds the most recent 200 calls; older entries are evicted.

    Pairs with the in-TD ``activity_log`` Table DAT mirror so the same data
    is also wireable into a live visual patch.
    """
    finish = _tr._start_tool(ctx, "td_get_activity_log")
    try:
        from td_mcp import activity_log

        entries = activity_log.snapshot(limit=limit, tool_filter=tool_filter)
        payload = {
            "schema_version": 1,
            "count": len(entries),
            "max_buffer": activity_log.MAX_ENTRIES,
            "entries": entries,
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_activity_log")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(
    name="td_self_update",
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
    ),
)
async def td_self_update(
    ctx: Context,
    check_only: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If True (default), only check whether a newer release exists. "
                "If False, download + install the latest .plugin/.tox to all "
                "three install paths (~/.tdpilot, plugin cache, repo)."
            ),
        ),
    ] = True,
) -> str:
    """Check for and optionally install a newer TDPilot release from GitHub.

    Default behavior (``check_only=True``) hits the GitHub releases API and
    returns ``{installed, latest, newer_available, release_url, asset_urls}``.
    Set ``check_only=False`` to actually download and install — this writes
    to ``~/.tdpilot/td_component/tdpilot.tox``, the Claude Code plugin cache,
    and the repo working-tree (when running from a clone). On success returns
    md5 fingerprints for each install path so the caller can verify sync.

    Releases v1.6.9 through v2.0.3 shipped without the ``tdpilot.tox`` asset;
    against those, ``check_only=False`` returns
    ``error_code="release_asset_missing"`` with remediation hints instead of
    installing. Releases after v2.0.3 attach the asset automatically
    (.github/workflows/release-assets.yml).

    Network-only — does not touch TouchDesigner. Safe to run when TD is closed.
    """
    finish = _tr._start_tool(ctx, "td_self_update")
    try:
        from td_mcp import self_updater

        result = self_updater.run(check_only=check_only)
        return _tr._as_json_output(result)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_self_update")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(
    name="td_sync_status",
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    ),
)
async def td_sync_status(
    ctx: Context,
    check_remote: Annotated[
        bool,
        Field(
            default=True,
            description="If true, also check GitHub release, npm latest, and GitHub repository description.",
        ),
    ] = True,
) -> str:
    """Report whether the local server, TD component, packages, and public surfaces are in sync."""
    finish = _tr._start_tool(ctx, "td_sync_status")
    try:
        from td_mcp import __version__ as server_version
        from td_mcp.release_gates import EXPECTED_MIN_TOOL_COUNT

        touchdesigner = await _live_component_status(ctx)
        tox = _tox_freshness_status()
        plugin_caches = _plugin_cache_versions()
        remote = _remote_release_status() if check_remote else {"skipped": True}
        github_repo = _github_repo_description_status() if check_remote else {"skipped": True}

        recommendations: list[str] = []
        if touchdesigner.get("matches_server") is False:
            recommendations.append("Reload/export the bundled td_component/tdpilot.tox in TouchDesigner.")
        if tox.get("fresh") is False:
            recommendations.append("Rebuild td_component/tdpilot.tox before publishing this source change.")
        if any(row.get("versions") and not row.get("contains_server_version") for row in plugin_caches):
            recommendations.append(
                "Refresh local Claude/Codex plugin caches so they include the server version."
            )
        if remote.get("github_latest") and remote.get("github_latest") != server_version:
            recommendations.append("Install or release-sync to the latest GitHub version.")
        if remote.get("npm_latest") and remote.get("npm_latest") != server_version:
            recommendations.append("Publish or install the matching npm package version.")
        if github_repo.get("matches") is False:
            recommendations.append(
                "Update the GitHub repository description to match the current public version/tool count."
            )

        overall = "ok" if not recommendations else "warning"
        payload = {
            "schema_version": 1,
            "success": True,
            "overall": overall,
            "server": {
                "version": server_version,
                "expected_min_tool_count": EXPECTED_MIN_TOOL_COUNT,
            },
            "touchdesigner": touchdesigner,
            "tox": tox,
            "plugin_caches": plugin_caches,
            "remote": remote,
            "github_repo": github_repo,
            "recommendations": recommendations,
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_sync_status")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(
    name="td_sync_diagnose",
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    ),
)
async def td_sync_diagnose(
    ctx: Context,
    include_live: Annotated[
        bool,
        Field(default=True, description="If true, probe the live TouchDesigner WebServer."),
    ] = True,
    check_remote: Annotated[
        bool,
        Field(default=False, description="Reserved for compatibility; remote checks are not required."),
    ] = False,
) -> str:
    """Strict version/auth sync diagnostic without exposing secret material."""
    finish = _tr._start_tool(ctx, "td_sync_diagnose")
    try:
        from td_mcp.sync_diagnostics import diagnose_sync

        client = _tr._get_client(ctx) if include_live else None
        diagnostic = await diagnose_sync(client=client, include_live=include_live)
        payload = {
            "schema_version": 1,
            "success": True,
            "check_remote": bool(check_remote),
            "diagnostic": diagnostic,
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_sync_diagnose")
        return format_tool_error(exc)
    finally:
        finish()
