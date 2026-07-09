"""Strict local/live sync diagnostics for TDPilot.

Reports only short SHA-256 fingerprints for shared secrets; never secret
material.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from td_mcp import __version__ as LOCAL_VERSION
from td_mcp.auth_bootstrap import default_env_file

_SOURCE_HASH_PATHS = (
    "td_component/mcp_webserver_callbacks.py",
    "td_component/autostart.py",
    "td_component/tdpilot_startup.py",
    "td_component/build_export_mcp_tox.py",
    "src/td_mcp/td_client.py",
    "src/td_mcp/sync_diagnostics.py",
    "src/td_mcp/tool_registry.py",
    "src/td_mcp/registry/tools_meta.py",
    "src/td_mcp/registry/tools_vision.py",
    "src/td_mcp/registry/tools_planning.py",
    "src/td_mcp/registry/tools_info.py",
    "src/td_mcp/brain/live_smoke.py",
    "src/td_mcp/brain/transaction.py",
    "src/td_mcp/brain/validators.py",
    "src/td_mcp/self_updater.py",
    "scripts/brain_live_smoke.py",
    "scripts/replay_live_debug_incident.py",
)


def _secret_fingerprint(secret: str | None) -> str | None:
    secret = (secret or "").strip()
    if not secret:
        return None
    return f"sha256:{hashlib.sha256(secret.encode('utf-8')).hexdigest()[:12]}"


def _read_secret_from_env_file(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, FileNotFoundError):
        return None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != "TD_MCP_SHARED_SECRET":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        return value
    return None


def _read_secret_from_client_config(path: Path) -> str | None:
    """Extract a literal ``TD_MCP_SHARED_SECRET`` from an MCP client config.

    Walks ``mcpServers.*.env`` in the JSON. Returns ``None`` on any parse or
    I/O failure — the chain report only needs best-effort presence.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return None
    for server in servers.values():
        if not isinstance(server, dict):
            continue
        env = server.get("env")
        if isinstance(env, dict):
            value = str(env.get("TD_MCP_SHARED_SECRET") or "").strip()
            if value:
                return value
    return None


def _default_client_config_paths(local_root: Path) -> list[Path]:
    """Client config files that may (wrongly, post-unification) embed a secret."""
    home = Path.home()
    if sys.platform == "darwin":
        desktop = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif os.name == "nt":
        desktop = home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    else:
        desktop = home / ".config" / "Claude" / "claude_desktop_config.json"
    return [desktop, local_root / ".mcp.json", local_root / ".mcp.json.local"]


def _default_legacy_env_paths(local_root: Path, env_path: Path) -> list[Path]:
    """Pre-unification repo-local .tdpilot.env locations (no longer read by anyone)."""
    candidates = [
        local_root / ".tdpilot.env",
        Path.home() / "TDPilot" / ".tdpilot.env",
    ]
    resolved_env = env_path.expanduser()
    return [p for p in candidates if p.expanduser() != resolved_env]


def _secret_chain_report(
    *,
    env_path: Path,
    local_root: Path,
    client_config_paths: list[Path] | None = None,
    legacy_env_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Fingerprint EVERY file in the secret chain and name the winner.

    Canonical resolution order (unified across all readers in audit batch E):
    explicit ``TD_MCP_SHARED_SECRET`` process env var, then the canonical
    env file (``~/.tdpilot/.tdpilot.env`` / ``TDPILOT_ENV_FILE``). Client
    configs and legacy repo-local env files are scanned as drift suspects —
    a literal secret there becomes process env when that client launches the
    server, so a divergent one is a live 401 source. Output carries short
    SHA-256 fingerprints only, never secret material.
    """
    env_secret = (os.environ.get("TD_MCP_SHARED_SECRET") or "").strip() or None
    file_secret = _read_secret_from_env_file(env_path)

    sources: list[dict[str, Any]] = [
        {
            "id": "process_env",
            "kind": "env_var",
            "canonical": True,
            "present": env_secret is not None,
            "secret_present": env_secret is not None,
            "fingerprint": _secret_fingerprint(env_secret),
        },
        {
            "id": "canonical_env_file",
            "kind": "env_file",
            "path": str(env_path),
            "canonical": True,
            "present": env_path.is_file(),
            "secret_present": file_secret is not None,
            "fingerprint": _secret_fingerprint(file_secret),
        },
    ]
    config_paths = (
        client_config_paths if client_config_paths is not None else _default_client_config_paths(local_root)
    )
    for path in config_paths:
        secret = _read_secret_from_client_config(path)
        sources.append(
            {
                "id": f"client_config:{path.name}",
                "kind": "client_config",
                "path": str(path),
                "canonical": False,
                "present": path.is_file(),
                "secret_present": secret is not None,
                "fingerprint": _secret_fingerprint(secret),
            }
        )
    for path in (
        legacy_env_paths if legacy_env_paths is not None else _default_legacy_env_paths(local_root, env_path)
    ):
        secret = _read_secret_from_env_file(path)
        sources.append(
            {
                "id": f"legacy_env_file:{path}",
                "kind": "legacy_env_file",
                "path": str(path),
                "canonical": False,
                "present": path.is_file(),
                "secret_present": secret is not None,
                "fingerprint": _secret_fingerprint(secret),
            }
        )

    if env_secret is not None:
        winner = "process_env"
        winner_fp = _secret_fingerprint(env_secret)
    elif file_secret is not None:
        winner = "canonical_env_file"
        winner_fp = _secret_fingerprint(file_secret)
    else:
        winner = None
        winner_fp = None

    if winner_fp:
        divergent = [s["id"] for s in sources if s.get("fingerprint") and s["fingerprint"] != winner_fp]
    else:
        # No canonical secret anywhere, but a non-canonical source has one:
        # that literal will win inside whichever client ships it — divergence.
        divergent = [s["id"] for s in sources if s.get("fingerprint")]

    return {
        "canonical_order": ["process_env:TD_MCP_SHARED_SECRET", f"env_file:{env_path}"],
        "sources": sources,
        "winner": winner,
        "winner_fingerprint": winner_fp,
        "divergent_sources": divergent,
        "non_canonical_secret_sources": [
            s["id"] for s in sources if not s["canonical"] and s.get("secret_present")
        ],
        "ok": not divergent,
    }


def _installed_version() -> str | None:
    try:
        return importlib.metadata.version("tdpilot")
    except importlib.metadata.PackageNotFoundError:
        return None


def _plugin_cache_versions() -> dict[str, list[str]]:
    home = Path.home()
    roots = {
        "claude": home / ".claude" / "plugins" / "cache" / "dreamrec-TDPilot" / "tdpilot",
        "codex": home / ".codex" / "plugins" / "cache" / "tdpilot-local" / "tdpilot",
    }
    versions: dict[str, list[str]] = {}
    for name, root in roots.items():
        if root.is_dir():
            versions[name] = sorted(path.name for path in root.iterdir() if path.is_dir())
        else:
            versions[name] = []
    return versions


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_pyproject_version(root: Path) -> str | None:
    pyproject = root / "pyproject.toml"
    try:
        lines = pyproject.read_text(encoding="utf-8").splitlines()
    except (OSError, FileNotFoundError):
        return None
    for raw in lines:
        line = raw.strip()
        if line.startswith("version") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _source_hash_for_root(root: Path) -> dict[str, Any]:
    files: list[str] = []
    missing: list[str] = []
    digest = hashlib.sha256()
    for rel in _SOURCE_HASH_PATHS:
        path = root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            missing.append(rel)
            continue
        files.append(rel)
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    version = _read_pyproject_version(root)
    return {
        "path": str(root),
        "present": bool(files),
        "version": version,
        "hash": f"sha256:{digest.hexdigest()[:16]}" if files else None,
        "file_count": len(files),
        "files": files,
        "missing": missing,
    }


def _source_latest_mtime(root: Path) -> float | None:
    latest: float | None = None
    for rel in _SOURCE_HASH_PATHS:
        path = root / rel
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        latest = mtime if latest is None else max(latest, mtime)
    return latest


def _default_source_install_roots(local_version: str) -> dict[str, Path]:
    home = Path.home()
    roots: dict[str, Path] = {
        "user": home / ".tdpilot",
        "codex_vendor_import": home / ".codex" / "vendor_imports" / "TDPilot",
        "claude_plugin_current": (
            home / ".claude" / "plugins" / "cache" / "dreamrec-TDPilot" / "tdpilot" / local_version
        ),
        "codex_plugin_current": (
            home / ".codex" / "plugins" / "cache" / "tdpilot-local" / "tdpilot" / local_version
        ),
    }
    return roots


def _ps_available() -> bool:
    """The running-process probes shell out to ps(1) — absent on Windows."""
    return os.name != "nt"


def _process_start_epoch(pid: str) -> float | None:
    try:
        text = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "lstart="],
            text=True,
            errors="replace",
        ).strip()
    except Exception:
        return None
    if not text:
        return None
    try:
        return datetime.strptime(text, "%a %b %d %H:%M:%S %Y").timestamp()
    except ValueError:
        return None


def _process_env_secret_fingerprint(pid: str) -> str | None:
    try:
        text = subprocess.check_output(
            ["ps", "eww", "-p", str(pid)],
            text=True,
            errors="replace",
        )
    except Exception:
        return None
    match = re.search(r"TD_MCP_SHARED_SECRET=([^\s]+)", text)
    if not match:
        return None
    return _secret_fingerprint(match.group(1))


def _process_root_from_command(command: str) -> Path | None:
    directory_match = re.search(
        r"(?:^|\s)(?:uv|/[^\s]+/uv)\s+run\s+--directory\s+([^\s]+)\s+tdpilot(?:\s|$)",
        command,
    )
    if directory_match:
        return Path(directory_match.group(1).strip().strip("'\"")).expanduser()
    venv_match = re.search(r"(\S+?)/(?:\.venv|venv)/bin/tdpilot\b", command)
    if not venv_match:
        venv_match = re.search(
            r"(?:^|\s)\S+/(?:\.venv|venv)/bin/python\d*(?:\.\d+)?\s+(\S+?)/(?:\.venv|venv)/bin/tdpilot\b",
            command,
        )
    if venv_match:
        return Path(venv_match.group(1)).expanduser()
    return None


def _running_mcp_process_rows() -> list[dict[str, Any]]:
    try:
        text = subprocess.check_output(
            ["ps", "axww", "-o", "pid=,command="],
            text=True,
            errors="replace",
        )
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "tdpilot" not in line.lower():
            continue
        if "scripts/diagnose_live_sync.py" in line or "sync_diagnostics.py" in line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        pid, command = parts
        root = _process_root_from_command(command)
        if root is None:
            continue
        started_at = _process_start_epoch(pid)
        latest_mtime = _source_latest_mtime(root)
        row = _source_hash_for_root(root)
        row.update(
            {
                "pid": int(pid),
                "root": str(root),
                "command_kind": (
                    "codex_vendor"
                    if ".codex/vendor_imports/TDPilot" in str(root)
                    else "user_install"
                    if str(root).endswith(".tdpilot")
                    else "plugin_or_other"
                ),
                "process_secret_fingerprint": _process_env_secret_fingerprint(pid),
                "started_at_epoch": started_at,
                "source_latest_mtime_epoch": latest_mtime,
                "stale_source": bool(
                    started_at is not None and latest_mtime is not None and latest_mtime > started_at
                ),
            }
        )
        rows.append(row)
    return rows


def _running_process_report(
    *,
    local_hash: str | None,
    local_version: str,
    env_file_secret_fingerprint: str | None,
    process_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if process_rows is None and not _ps_available():
        # ps(1)-based probes can't run on Windows. Report that explicitly —
        # a silently-empty process list reads as "no drift" when it actually
        # means "not checked" (audit batch E, Windows-safety item).
        return {
            "status": "unsupported_platform",
            "processes": [],
            "process_count": 0,
            "mismatches": [],
            "ok": True,
        }
    rows = list(process_rows) if process_rows is not None else _running_mcp_process_rows()
    mismatches: list[dict[str, Any]] = []
    for row in rows:
        version = row.get("version")
        hash_value = row.get("hash")
        process_fp = row.get("process_secret_fingerprint")
        reasons: list[str] = []
        if version and version != local_version:
            reasons.append("version_mismatch")
        if local_hash and hash_value and hash_value != local_hash:
            reasons.append("source_hash_mismatch")
        if row.get("stale_source"):
            reasons.append("process_started_before_source_update")
        if process_fp and env_file_secret_fingerprint and process_fp != env_file_secret_fingerprint:
            reasons.append("auth_fingerprint_mismatch")
        if reasons:
            mismatches.append(
                {
                    "pid": row.get("pid"),
                    "root": row.get("root") or row.get("path"),
                    "reasons": reasons,
                }
            )
    return {
        "status": "checked",
        "processes": rows,
        "process_count": len(rows),
        "mismatches": mismatches,
        "ok": not mismatches,
    }


def _source_hash_report(
    *,
    local_root: Path,
    install_roots: dict[str, Path],
    local_version: str,
) -> dict[str, Any]:
    local = _source_hash_for_root(local_root)
    local_hash = local.get("hash")
    rows: dict[str, Any] = {}
    mismatches: list[str] = []
    unverified: list[str] = []
    for name, root in sorted(install_roots.items()):
        row = _source_hash_for_root(root)
        row_version = row.get("version")
        comparable = bool(local_hash and row.get("hash"))
        same_version = row_version in (None, local_version)
        row["compared_to_local"] = bool(comparable and same_version)
        row["matches_local"] = bool(row.get("hash") == local_hash) if row["compared_to_local"] else None
        rows[name] = row
        if row["compared_to_local"] and row["matches_local"] is False:
            mismatches.append(name)
        elif same_version and not row.get("present"):
            unverified.append(name)
    return {
        "local": local,
        "install_roots": rows,
        "mismatches": mismatches,
        "unverified": unverified,
        "ok": not mismatches,
    }


def _extract_version(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return None


async def _live_versions(client) -> dict[str, Any]:
    result: dict[str, Any] = {
        "reachable": False,
        "running_mcp": None,
        "td_component": None,
        "health": None,
        "info": None,
    }
    last_error = None
    for endpoint in ("health", "info"):
        try:
            payload = await client.request(endpoint)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue
        if not isinstance(payload, dict):
            continue
        result["reachable"] = True
        result[endpoint] = payload
        running = _extract_version(
            payload,
            "server_version",
            "mcp_server_version",
            "tdpilot_version",
        )
        component = _extract_version(
            payload,
            "mcp_component_version",
            "component_version",
            "api_version",
        )
        if running and not result["running_mcp"]:
            result["running_mcp"] = running
        if component and not result["td_component"]:
            result["td_component"] = component
    if last_error and not result["reachable"]:
        result["error"] = last_error
    return result


def _version_mismatch(versions: dict[str, Any]) -> bool:
    expected = versions.get("local")
    if not expected:
        return False
    for key in ("installed", "running_mcp", "td_component"):
        value = versions.get(key)
        if value and value != expected:
            return True
    for cache_versions in (versions.get("plugin_caches") or {}).values():
        if cache_versions and expected not in cache_versions:
            return True
    return False


async def diagnose_sync(
    *,
    client=None,
    host: str = "127.0.0.1",
    port: int = 9981,
    include_live: bool = True,
    local_version: str | None = None,
    installed_version: str | None = None,
    plugin_versions: dict[str, list[str]] | None = None,
    env_file: Path | None = None,
    local_root: Path | None = None,
    install_roots: dict[str, Path] | None = None,
    running_processes: list[dict[str, Any]] | None = None,
    client_config_paths: list[Path] | None = None,
    legacy_env_paths: list[Path] | None = None,
) -> dict[str, Any]:
    env_path = env_file or default_env_file()
    process_secret = (os.environ.get("TD_MCP_SHARED_SECRET") or "").strip() or None
    file_secret = _read_secret_from_env_file(env_path)
    process_fp = _secret_fingerprint(process_secret)
    file_fp = _secret_fingerprint(file_secret)

    versions: dict[str, Any] = {
        "local": local_version or LOCAL_VERSION,
        "installed": installed_version if installed_version is not None else _installed_version(),
        "plugin_caches": plugin_versions if plugin_versions is not None else _plugin_cache_versions(),
        "running_mcp": None,
        "td_component": None,
    }
    live: dict[str, Any] = {"skipped": not include_live, "endpoint": f"http://{host}:{port}"}
    if include_live and client is not None:
        live = await _live_versions(client)
        live["endpoint"] = f"http://{host}:{port}"
        versions["running_mcp"] = live.get("running_mcp")
        versions["td_component"] = live.get("td_component")
    elif include_live:
        live["error"] = "no TD client provided"

    auth_mismatch = bool(process_fp and file_fp and process_fp != file_fp)
    version_mismatch = _version_mismatch(versions)
    resolved_local_root = local_root or _repo_root()
    secret_chain = _secret_chain_report(
        env_path=env_path,
        local_root=resolved_local_root,
        client_config_paths=client_config_paths,
        legacy_env_paths=legacy_env_paths,
    )
    secret_chain_divergence = not secret_chain["ok"]
    source_hashes = _source_hash_report(
        local_root=resolved_local_root,
        install_roots=(
            install_roots
            if install_roots is not None
            else _default_source_install_roots(str(versions["local"]))
        ),
        local_version=str(versions["local"]),
    )
    source_hash_mismatch = not source_hashes["ok"]
    running_process_report = _running_process_report(
        local_hash=source_hashes["local"].get("hash"),
        local_version=str(versions["local"]),
        env_file_secret_fingerprint=file_fp,
        process_rows=running_processes,
    )
    running_process_mismatch = not running_process_report["ok"]
    recommendations: list[str] = []
    if version_mismatch:
        recommendations.append(
            "Restart or reinstall the MCP server and TouchDesigner component so running versions match local."
        )
    if source_hash_mismatch:
        recommendations.append(
            "Same-version source files differ from the local checkout; reinstall/sync TDPilot source roots and rebuild/reload the TD component."
        )
    if running_process_mismatch:
        recommendations.append(
            "Restart running TDPilot MCP processes that predate source/auth updates so the tool surface reloads current code and credentials."
        )
    if auth_mismatch:
        recommendations.append(
            f"Align TD_MCP_SHARED_SECRET between process env and {env_path}; restart MCP and TouchDesigner."
        )
    if secret_chain_divergence:
        for source in secret_chain["sources"]:
            if source["id"] not in secret_chain["divergent_sources"]:
                continue
            if source["kind"] == "client_config":
                recommendations.append(
                    f"Client config {source.get('path')} embeds a TD_MCP_SHARED_SECRET that diverges "
                    "from the canonical winner. Remove the literal secret and set "
                    "TD_MCP_AUTOGENERATE_SECRET=1 instead (re-run install.sh / install.ps1), "
                    f"or copy the winning secret into {env_path}."
                )
            elif source["kind"] == "legacy_env_file":
                recommendations.append(
                    f"Legacy secret file {source.get('path')} diverges from the canonical winner and "
                    "is no longer read by any TDPilot component. Delete it (or sync it with "
                    f"{env_path}) to stop 401 confusion."
                )
            elif source["id"] == "canonical_env_file":
                recommendations.append(
                    f"Canonical env file {env_path} diverges from the process env secret; the process "
                    "env wins. Restart clients after aligning them."
                )
    if include_live and live.get("error"):
        recommendations.append(
            "Run with TouchDesigner WebServer active on the configured endpoint and matching shared secret."
        )

    return {
        "schema_version": 1,
        "ok": not version_mismatch
        and not auth_mismatch
        and not secret_chain_divergence
        and not source_hash_mismatch
        and not running_process_mismatch
        and not live.get("error"),
        "versions": versions,
        "source_hashes": source_hashes,
        "running_processes": running_process_report,
        "auth": {
            "env_file": str(env_path),
            "process_secret_present": process_fp is not None,
            "env_file_secret_present": file_fp is not None,
            "process_secret_fingerprint": process_fp,
            "env_file_secret_fingerprint": file_fp,
            "fingerprints_match": (
                process_fp == file_fp if process_fp is not None and file_fp is not None else None
            ),
            "secret_chain": secret_chain,
        },
        "live": live,
        "drift": {
            "version_mismatch": version_mismatch,
            "auth_mismatch": auth_mismatch,
            "secret_chain_divergence": secret_chain_divergence,
            "source_hash_mismatch": source_hash_mismatch,
            "running_process_mismatch": running_process_mismatch,
        },
        "recommendations": recommendations,
    }
