#!/usr/bin/env python3
"""CLI and runtime entrypoint for TDPilot MCP."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from td_mcp import TOX_FILENAME, __version__, normalize_transport
from td_mcp.td_client import TDClient, TouchDesignerConnectionError
from td_mcp.tool_registry import (
    TD_EXEC_MODE,
    TD_HOST,
    TD_HTTP_HOST,
    TD_HTTP_PORT,
    TD_PORT,
    TD_TRANSPORT,
    TD_WS_PORT,
    _apply_safety_to_set_params,
    _enforce_exec_mode,
    _restricted_exec_violation,
    mcp,
)
from td_mcp.tool_registry import (
    main as _run_server,
)


def _candidate_repo_roots() -> list[Path]:
    candidates: list[Path] = []

    env_root = (os.environ.get("TD_MCP_REPO_ROOT") or "").strip()
    if env_root:
        candidates.append(Path(env_root).expanduser())

    try:
        candidates.append(Path(__file__).resolve().parents[2])
    except Exception:
        pass

    candidates.append(Path.cwd())
    candidates.append(Path.home() / "TDPilot")

    seen: set[Path] = set()
    ordered: list[Path] = []
    for raw in candidates:
        root = raw.resolve()
        if root in seen:
            continue
        seen.add(root)
        ordered.append(root)
    return ordered


def _find_repo_root() -> Path | None:
    for root in _candidate_repo_roots():
        if (root / "pyproject.toml").is_file() and (root / "td_component").is_dir():
            return root
    return None


_TRUTHY_REQUIRE_AUTH = {"1", "true", "yes", "on"}


def _auth_required() -> bool:
    return os.environ.get("TD_MCP_REQUIRE_AUTH", "0").strip().lower() in _TRUTHY_REQUIRE_AUTH


def _auth_secret_present() -> bool:
    return bool(os.environ.get("TD_MCP_SHARED_SECRET", "").strip())


def verify_auth_config() -> None:
    """Fail loud if auth is required but no shared secret is resolvable.

    Prevents the misconfiguration where `.mcp.json` ships with
    `TD_MCP_REQUIRE_AUTH=1` but the plugin install path never runs the
    installer (install.sh / install.ps1) to generate a shared secret. Without
    this check, the server starts happily and every authenticated request
    returns 401 with no startup signal about why.
    """
    if not _auth_required():
        return
    if _auth_secret_present():
        return
    raise RuntimeError(
        "TDPilot: TD_MCP_REQUIRE_AUTH=1 but TD_MCP_SHARED_SECRET is not set.\n"
        "Run the installer (install.sh or install.ps1) to generate one, "
        "or set TD_MCP_REQUIRE_AUTH=0 to disable auth (not recommended)."
    )


def _tool_count_drift_check(repo_root: Path | None) -> tuple[str, str]:
    """Compare `@mcp.tool(` count in tool_registry.py against manifest's
    `surface.tool_count`. Returns (status, detail).

    Skip (not fail) when either file is missing — the check is a developer
    convenience, not a hard release gate (CI runs check_versions.py for that).
    """
    if repo_root is None:
        return "skip", "repo root not found"
    registry_path = repo_root / "src" / "td_mcp" / "tool_registry.py"
    manifest_path = repo_root / "mcp" / "manifest.json"
    if not registry_path.is_file() or not manifest_path.is_file():
        return "skip", "tool_registry.py or mcp/manifest.json missing"

    try:
        source = registry_path.read_text(encoding="utf-8")
        import json as _json
        import re as _re

        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        source_count = len(_re.findall(r"@mcp\.tool\(", source))
        manifest_count = int(manifest.get("surface", {}).get("tool_count", -1))
    except Exception as exc:  # pragma: no cover - defensive
        return "skip", f"could not read counts: {exc}"

    if manifest_count == source_count:
        return "pass", f"registry=manifest={manifest_count}"
    return "warn", (
        f"mismatch: registry={source_count} vs manifest={manifest_count}; "
        "update mcp/manifest.json surface.tool_count"
    )


def _check_tcp_port(host: str, port: int, timeout: float) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


async def _check_td_health(host: str, port: int, timeout: float) -> tuple[bool, str]:
    client = TDClient(host=host, port=port, timeout=timeout, max_retries=0)
    try:
        payload = await client.health_check()
        return True, f"health endpoint responded ({payload.get('status', 'ok')})"
    except TouchDesignerConnectionError as exc:
        return False, str(exc)
    except Exception as exc:  # pragma: no cover - defensive
        return False, str(exc)
    finally:
        await client.close()


def _collect_doctor_report(*, timeout: float, skip_td_check: bool, strict: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    repo_root = _find_repo_root()
    tox_path = (repo_root / "td_component" / TOX_FILENAME) if repo_root else None

    checks.append(
        {
            "name": "python_runtime",
            "status": "pass",
            "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
    )

    uv_path = shutil.which("uv")
    checks.append(
        {
            "name": "uv_available",
            "status": "pass" if uv_path else "warn",
            "detail": uv_path or "uv not in PATH (npx wrapper can still bootstrap it)",
        }
    )

    checks.append(
        {
            "name": "repo_root",
            "status": "pass" if repo_root else "warn",
            "detail": str(repo_root) if repo_root else "repo root not auto-detected",
        }
    )

    checks.append(
        {
            "name": "tox_component",
            "status": "pass" if tox_path and tox_path.is_file() else "fail",
            "detail": str(tox_path)
            if tox_path and tox_path.is_file()
            else f"td_component/{TOX_FILENAME} not found",
        }
    )

    transport = normalize_transport(TD_TRANSPORT or "stdio")
    valid_transport = transport in {"stdio", "streamable-http", "sse"}
    checks.append(
        {
            "name": "transport_config",
            "status": "pass" if valid_transport else "fail",
            "detail": f"{transport} (TD_MCP_TRANSPORT)",
        }
    )

    checks.append(
        {
            "name": "port_reachability",
            "status": "pass" if _check_tcp_port(TD_HOST, int(TD_PORT), timeout=min(timeout, 1.0)) else "warn",
            "detail": f"tcp://{TD_HOST}:{TD_PORT}",
        }
    )

    if skip_td_check:
        checks.append(
            {
                "name": "td_health",
                "status": "skip",
                "detail": "skipped (--skip-td-check)",
            }
        )
    else:
        ok, detail = asyncio.run(_check_td_health(TD_HOST, int(TD_PORT), timeout))
        checks.append(
            {
                "name": "td_health",
                "status": "pass" if ok else "warn",
                "detail": detail,
            }
        )

    checks.append(
        {
            "name": "runtime_defaults",
            "status": "pass",
            "detail": f"transport={transport}, http={TD_HTTP_HOST}:{TD_HTTP_PORT}, ws={TD_WS_PORT}, exec_mode={TD_EXEC_MODE}",
        }
    )

    # Auth config — fail-loud gate for the plugin-install misconfiguration where
    # TD_MCP_REQUIRE_AUTH=1 is set but no shared secret is resolvable.
    if _auth_required():
        if _auth_secret_present():
            auth_status = "pass"
            auth_detail = "TD_MCP_REQUIRE_AUTH=1 with TD_MCP_SHARED_SECRET set"
        else:
            auth_status = "fail"
            auth_detail = (
                "TD_MCP_REQUIRE_AUTH=1 but TD_MCP_SHARED_SECRET is not set; "
                "run install.sh/install.ps1 to generate one"
            )
    else:
        auth_status = "pass"
        auth_detail = "auth disabled (TD_MCP_REQUIRE_AUTH!=1)"
    checks.append({"name": "auth_config", "status": auth_status, "detail": auth_detail})

    # Tool-count drift — catch cases where a tool was added/removed without
    # bumping mcp/manifest.json's surface.tool_count. Warn (not fail) since the
    # server still runs correctly; the manifest is the external-facing number.
    drift_status, drift_detail = _tool_count_drift_check(repo_root)
    checks.append({"name": "tool_count_drift", "status": drift_status, "detail": drift_detail})

    fail_count = sum(1 for item in checks if item["status"] == "fail")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    ok = fail_count == 0 and (warn_count == 0 if strict else True)

    return {
        "schema_version": 1,
        "generated_at": now,
        "version": __version__,
        "summary": {
            "ok": ok,
            "fails": fail_count,
            "warnings": warn_count,
            "strict": strict,
        },
        "checks": checks,
    }


def _print_doctor_report(report: dict[str, Any]) -> None:
    print("TDPilot Doctor")
    print(f"version: {report.get('version')}")
    for item in report.get("checks", []):
        status = str(item.get("status", "unknown")).upper().ljust(5)
        print(f"[{status}] {item.get('name')}: {item.get('detail')}")
    summary = report.get("summary", {})
    print(f"Result: ok={summary.get('ok')} fails={summary.get('fails')} warnings={summary.get('warnings')}")


def _runtime_health_from_payloads(
    *,
    cooking: dict[str, Any],
    errors: dict[str, Any],
) -> dict[str, Any]:
    fps = float(cooking.get("fps", 0.0) or 0.0) if isinstance(cooking, dict) else 0.0
    issues = errors.get("issues", []) if isinstance(errors, dict) else []
    heavy_nodes = [
        node
        for node in (cooking.get("nodes", []) if isinstance(cooking, dict) else [])
        if isinstance(node, dict) and float(node.get("cookTime", 0.0) or 0.0) >= 0.01
    ]
    return {
        "fps": fps,
        "issues_count": len(issues),
        "unstable": fps < 30.0 or bool(issues) or len(heavy_nodes) >= 5,
        "heavy_nodes_count": len(heavy_nodes),
        "heavy_nodes": heavy_nodes[:10],
    }


def _default_client_output_path(client: str) -> Path:
    system = platform.system().lower()
    home = Path.home()

    if client == "claude-desktop":
        if system == "darwin":
            return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        if system == "windows":
            appdata = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return home / ".config" / "Claude" / "claude_desktop_config.json"

    if client == "cursor":
        return Path.cwd() / "cursor_mcp_config.json"

    return Path.cwd() / "mcp.config.json"


def _build_profile_config(
    client: str,
    server_name: str,
    *,
    auth_required: bool = False,
    shared_secret: str | None = None,
    exec_mode: str | None = None,
) -> dict[str, Any]:
    """Build an MCP client profile for TDPilot.

    Auth posture:
      - `auth_required=False` (default): minimal env, no auth. Matches the
        pre-v1.4.4 behaviour so existing `tdpilot init` callers get the
        same output.
      - `auth_required=True` + `shared_secret=<str>`: embeds
        `TD_MCP_REQUIRE_AUTH=1` and `TD_MCP_SHARED_SECRET=<str>`. Matches
        the shape that install.sh / install.ps1 produce after generating
        a secret per machine.
      - `auth_required=True` + `shared_secret=None`: embeds
        `TD_MCP_REQUIRE_AUTH=1` only. The resulting config will fail at
        server startup via verify_auth_config unless the caller has also
        arranged for a secret via env, .tdpilot.env, or auth_bootstrap
        autogeneration.

    v1.4.5: `exec_mode` lets callers bake `TD_MCP_EXEC_MODE=<value>` into
    the env. When `auth_required=True` and the caller doesn't override,
    defaults to "restricted" to match the shipped `.mcp.json` posture.
    """
    env: dict[str, str] = {
        "TD_MCP_HOST": "127.0.0.1",
        "TD_MCP_PORT": "9981",
        "TD_MCP_WS_PORT": "9982",
    }
    if auth_required:
        env["TD_MCP_REQUIRE_AUTH"] = "1"
        if shared_secret:
            env["TD_MCP_SHARED_SECRET"] = shared_secret
        # Default exec_mode when auth is on — matches shipped .mcp.json.
        if exec_mode is None:
            exec_mode = "restricted"
    if exec_mode:
        env["TD_MCP_EXEC_MODE"] = exec_mode
    profile: dict[str, Any] = {
        "mcpServers": {
            server_name: {
                "command": "npx",
                "args": ["-y", "tdpilot"],
                "env": env,
            }
        }
    }

    if client == "cursor":
        profile["$comment"] = "Generated profile for Cursor-style MCP config."
    elif client == "generic":
        profile["$comment"] = "Generic MCP profile."

    return profile


def _generate_shared_secret() -> str:
    """Return a fresh URL-safe 32-byte secret suitable for TD_MCP_SHARED_SECRET."""
    import secrets

    return secrets.token_urlsafe(32)


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def _merge_profile(existing: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    existing_servers = merged.get("mcpServers")
    if not isinstance(existing_servers, dict):
        existing_servers = {}
    merged["mcpServers"] = existing_servers

    profile_servers = profile.get("mcpServers", {})
    if isinstance(profile_servers, dict):
        for name, cfg in profile_servers.items():
            existing_servers[name] = cfg

    if "$comment" in profile and "$comment" not in merged:
        merged["$comment"] = profile["$comment"]
    return merged


def _run_init_command(args: argparse.Namespace) -> int:
    """Validate flag combinations, resolve the secret, build the profile.

    v1.4.5 flag rules (enforced here, not by argparse, because argparse
    can't express "X requires Y"):

      - `--generate-secret` without `--auth` → exit 2
      - `--shared-secret` without `--auth` → exit 2
      - `--generate-secret` AND `--shared-secret` together → exit 2
      - `--auth` alone (no secret flag) → generate a secret by default

    Secret notices go to STDERR when `--print-only` so the JSON profile on
    stdout stays pipeable through `jq`. File-write mode keeps notices on
    stdout for user visibility.
    """
    auth = bool(getattr(args, "auth", False))
    generate_flag = bool(getattr(args, "generate_secret", False))
    supplied_secret = getattr(args, "shared_secret", "") or ""
    print_only = bool(getattr(args, "print_only", False))

    # Validate flag combinations before touching anything
    if generate_flag and not auth:
        print(
            "[tdpilot] --generate-secret requires --auth. Aborting.",
            file=sys.stderr,
        )
        return 2
    if supplied_secret and not auth:
        print(
            "[tdpilot] --shared-secret requires --auth. Aborting.",
            file=sys.stderr,
        )
        return 2
    if generate_flag and supplied_secret:
        print(
            "[tdpilot] --generate-secret and --shared-secret are mutually exclusive. Aborting.",
            file=sys.stderr,
        )
        return 2

    # Resolve the secret
    shared_secret: str | None = None
    generated = False
    if auth:
        if supplied_secret:
            shared_secret = supplied_secret
        else:
            # v1.4.5: --auth alone (or --auth + --generate-secret) now
            # generates a secret by default. Pre-v1.4.5 you could get a
            # "require auth + no secret" config that tripped the startup
            # gate — deliberate fail-loud, but bad CLI UX.
            shared_secret = _generate_shared_secret()
            generated = True

    profile = _build_profile_config(
        args.client,
        args.server_name,
        auth_required=auth,
        shared_secret=shared_secret,
    )

    # Emit secret notice BEFORE writing the profile, but route it to
    # stderr when --print-only so stdout is pure JSON.
    if generated:
        notice = "[tdpilot] Generated a shared secret; keep the output safe — it grants full TD control."
        if print_only:
            print(notice, file=sys.stderr)
        else:
            print(notice)

    if args.print_only:
        print(json.dumps(profile, indent=2))
        return 0

    out_path = Path(args.output).expanduser() if args.output else _default_client_output_path(args.client)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not args.force:
        existing = _load_json_file(out_path)
        merged = _merge_profile(existing, profile)
    else:
        merged = profile

    out_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    print(f"[tdpilot] Wrote MCP config: {out_path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tdpilot",
        description="TDPilot MCP server and utilities.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", help="Run MCP server (default).")

    doctor = subparsers.add_parser("doctor", help="Run environment and connectivity diagnostics.")
    doctor.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    doctor.add_argument("--strict", action="store_true", help="Treat warnings as non-zero exit.")
    doctor.add_argument("--skip-td-check", action="store_true", help="Skip live TD /api/health check.")
    doctor.add_argument("--timeout", type=float, default=2.0, help="Health-check timeout in seconds.")

    init_cmd = subparsers.add_parser("init", help="Write MCP client config from bundled profile.")
    init_cmd.add_argument(
        "--client",
        choices=("claude-desktop", "cursor", "generic"),
        default="claude-desktop",
        help="Target client profile.",
    )
    init_cmd.add_argument("--server-name", default="touchdesigner", help="mcpServers key name.")
    init_cmd.add_argument("--output", default="", help="Explicit output config path.")
    init_cmd.add_argument("--print-only", action="store_true", help="Print config JSON only.")
    init_cmd.add_argument("--force", action="store_true", help="Overwrite instead of merge.")
    init_cmd.add_argument(
        "--auth",
        action="store_true",
        help="Embed TD_MCP_REQUIRE_AUTH=1 in the generated env.",
    )
    init_cmd.add_argument(
        "--generate-secret",
        action="store_true",
        help="Generate a fresh TD_MCP_SHARED_SECRET and embed it in the env (requires --auth).",
    )
    init_cmd.add_argument(
        "--shared-secret",
        default="",
        help="Use this existing secret instead of generating one (requires --auth).",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command or "run"

    # Run auth bootstrap BEFORE dispatching the command so `doctor` sees the
    # same environment `run` would — otherwise autogeneration works for the
    # server but doctor reports a misleading auth_config FAIL telling the
    # user to run install.sh, when autogen was supposed to handle it.
    # Skip for `init` because `init` is the config-generator, not a server
    # that consumes the secret; loading / minting at init time would be a
    # side-effect on the wrong path.
    if command != "init":
        from td_mcp import auth_bootstrap

        auth_bootstrap.bootstrap_auth()

    if command == "doctor":
        report = _collect_doctor_report(
            timeout=max(0.2, float(args.timeout)),
            skip_td_check=bool(args.skip_td_check),
            strict=bool(args.strict),
        )
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            _print_doctor_report(report)
        raise SystemExit(0 if report["summary"]["ok"] else 1)

    if command == "init":
        raise SystemExit(_run_init_command(args))

    # Startup gate: refuse to run the server if auth is required but no secret
    # is resolvable. Reached only when the caller declines autogeneration —
    # bootstrap_auth() doesn't silently rescue.
    try:
        verify_auth_config()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    _run_server()


__all__ = [
    "mcp",
    "main",
    "TD_EXEC_MODE",
    "_restricted_exec_violation",
    "_enforce_exec_mode",
    "_apply_safety_to_set_params",
    "_build_profile_config",
    "_collect_doctor_report",
    "verify_auth_config",
]


if __name__ == "__main__":
    main()
