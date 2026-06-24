"""TDPilot self-updater — close the staleness saga.

Background — the problem this exists to solve
---------------------------------------------

The user-memory note ``feedback_check_plugin_cache_freshness.md`` documents
**seven** locations where TDPilot's bits can fall out of sync:

1. The repo working-tree ``td_component/tdpilot.tox``.
2. The Claude Code plugin cache: ``~/.claude/plugins/cache/...``.
3. The user data dir ``~/.tdpilot/td_component/tdpilot.tox``.
4. The live TD COMP installed at ``/local/mcp_server`` — built from
   sources at setup time, not from a .tox reference.
5. The ``.claude-plugin/marketplace.json`` ``plugins[0].version`` field,
   which controls whether Claude Code's UI offers an "Update" button.
6. The npm install (``npx tdpilot``), pinned to ``git describe`` at
   release-tag push time.
7. The TD startup ``.toe`` (``~/.tdpilot/tdpilot_default.toe``)
   embedded-script snapshot.

When any of these lag, users see "the fix from last session isn't working"
even when the fix is in the repo. The historical pattern was: ship a
release, push to GitHub, wait for the user to re-install, find out months
later that they're still running an old plugin cache.

What this module does
---------------------

Asks GitHub "is there a newer release?", and (optionally) downloads the
release asset to all configured install paths in one shot. No system
package manager, no shell scripts to remember — one tool call from inside
Claude Code or one ``import`` from the TD Textport.

Architecture
------------

Pure stdlib (``urllib.request``, ``json``, ``hashlib``) — the same script
runs inside TouchDesigner's Python interpreter, which lags upstream Python
and ships no third-party HTTP libraries. Network access is injected as a
callable (``fetch_releases``, ``download_asset``) so tests cover every
branch without touching the network. The default callables make real
HTTPS calls.

Out of scope
------------

* Updating ``.claude-plugin/marketplace.json`` — that's the GitHub-side
  release packager's job; the user-side updater only refreshes binary
  artifacts.
* Refreshing the in-TD ``/local/mcp_server`` COMP — that still requires
  re-running ``setup_mcp_in_td.py`` from TD Textport. We surface that as
  a follow-up step in the result payload.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

GITHUB_RELEASES_URL = "https://api.github.com/repos/dreamrec/TDPilot/releases/latest"
DEFAULT_ASSET_NAME = "tdpilot.tox"
HTTP_TIMEOUT = 30


# ──────────────────────────────────────────────────────────
# Semver comparison
# ──────────────────────────────────────────────────────────


_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def _parse_version(value: str) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = _VERSION_RE.match(value.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def is_newer(*, latest: str, installed: str) -> bool:
    """Return True when ``latest`` is a strictly higher semver than ``installed``.

    Tolerates ``v`` prefixes (``v1.6.16`` parses the same as ``1.6.16``).
    Returns False on any parse failure — the safe default is "no update."
    """
    left = _parse_version(latest)
    right = _parse_version(installed)
    if left is None or right is None:
        return False
    return left > right


# ──────────────────────────────────────────────────────────
# Default network callables
# ──────────────────────────────────────────────────────────


def _default_fetch_releases() -> dict[str, Any]:
    """Hit the GitHub releases API. Raises on network/HTTP errors."""
    req = urllib.request.Request(
        GITHUB_RELEASES_URL,
        headers={"User-Agent": "tdpilot-self-updater"},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        body = resp.read()
    return json.loads(body)


def _default_download_asset(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tdpilot-self-updater"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read()


# ──────────────────────────────────────────────────────────
# Install path resolution
# ──────────────────────────────────────────────────────────


def _resolve_default_install_paths(asset_name: str = DEFAULT_ASSET_NAME) -> list[Path]:
    """Return the standard set of install paths for this machine.

    Three locations per the CLAUDE.md sync table:

    1. Repo working tree ``td_component/<asset>``.
    2. Claude Code plugin cache (best-effort glob).
    3. User data dir ``~/.tdpilot/td_component/<asset>``.

    Each path is returned even if its parent directory doesn't exist —
    :func:`_install_to_paths` creates parents on demand.
    """
    home = Path.home()
    paths: list[Path] = []

    # 1. Repo working tree, only if the script is running from inside a
    #    clone. The src/td_mcp file is three levels deep from repo root.
    try:
        repo_root = Path(__file__).resolve().parents[2]
        if (repo_root / "pyproject.toml").is_file() and (repo_root / "td_component").is_dir():
            paths.append(repo_root / "td_component" / asset_name)
    except Exception:
        pass

    # 2. Claude Code plugin cache. Pattern:
    #    ~/.claude/plugins/cache/dreamrec-TDPilot/tdpilot/<version>/td_component/<asset>
    #    The version subdir is the canonical version; we let the caller's
    #    plugin manager pick a specific subdir on next launch — we just
    #    drop the file into ALL versioned subdirs that already exist, so
    #    whichever one Claude Code resolves to is up-to-date.
    cache_root = home / ".claude" / "plugins" / "cache" / "dreamrec-TDPilot" / "tdpilot"
    if cache_root.is_dir():
        for version_dir in cache_root.iterdir():
            if not version_dir.is_dir():
                continue
            paths.append(version_dir / "td_component" / asset_name)

    # 3. User data dir.
    paths.append(home / ".tdpilot" / "td_component" / asset_name)

    return paths


# ──────────────────────────────────────────────────────────
# Install
# ──────────────────────────────────────────────────────────


def _install_to_paths(
    payload: bytes,
    paths: list[Path],
) -> tuple[list[str], dict[str, str]]:
    """Write ``payload`` to every path; return (installed_paths, md5_map).

    Parent directories are created as needed. Failures on individual
    paths are skipped — the caller decides whether partial success
    counts as success. md5 is reported for every WRITTEN path so the
    caller can verify three-way sync.
    """
    installed: list[str] = []
    md5_map: dict[str, str] = {}
    md5 = hashlib.md5(payload).hexdigest()
    for path in paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            installed.append(str(path))
            md5_map[str(path)] = md5
        except Exception:
            continue
    return installed, md5_map


def _http_fetch_error_result(exc: Exception, *, installed_version: str) -> dict[str, Any]:
    if isinstance(exc, urllib.error.HTTPError):
        remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
        reset = exc.headers.get("X-RateLimit-Reset") if exc.headers else None
        message = str(exc.reason or exc.msg or exc)
        rate_limited = exc.code == 403 and (remaining == "0" or "rate limit" in message.lower())
        if rate_limited:
            return {
                "ok": False,
                "error": f"failed to fetch releases: GitHub API rate limited ({message})",
                "error_code": "github_rate_limited",
                "installed": installed_version,
                "diagnostic": {
                    "kind": "github_http_error",
                    "http_status": exc.code,
                    "rate_limit_remaining": remaining,
                    "rate_limit_reset": reset,
                    "remediation": [
                        "Retry after the GitHub rate-limit reset time.",
                        "Set GH_TOKEN or GITHUB_TOKEN for authenticated GitHub API requests.",
                        "If local source is already current, continue with local install and rerun live sync diagnostics.",
                    ],
                },
            }
        return {
            "ok": False,
            "error": f"failed to fetch releases: HTTP {exc.code} ({message})",
            "error_code": "github_http_error",
            "installed": installed_version,
            "diagnostic": {
                "kind": "github_http_error",
                "http_status": exc.code,
                "rate_limit_remaining": remaining,
                "rate_limit_reset": reset,
                "remediation": [
                    "Check GitHub connectivity and credentials.",
                    "If the local source install is current, rerun sync diagnostics before touching live TD.",
                ],
            },
        }
    return {
        "ok": False,
        "error": f"failed to fetch releases: {exc}",
        "error_code": "release_fetch_failed",
        "installed": installed_version,
        "diagnostic": {
            "kind": "network_error",
            "message": str(exc),
            "remediation": [
                "Check network connectivity and retry.",
                "If local source is already current, continue with local install and rerun live sync diagnostics.",
            ],
        },
    }


def _asset_name_matches(candidate: str, requested: str) -> bool:
    return candidate.strip().lower() == requested.strip().lower()


def _missing_asset_result(
    result: dict[str, Any],
    *,
    latest_tag: str,
    asset_name: str,
    assets: list[Any],
) -> dict[str, Any]:
    available = [str(asset.get("name")) for asset in assets if isinstance(asset, dict) and asset.get("name")]
    tox_assets = [name for name in available if name.lower().endswith(".tox")]
    return {
        **result,
        "ok": False,
        "error": f"release {latest_tag!r} does not contain asset {asset_name!r}",
        "error_code": "release_asset_missing",
        "diagnostic": {
            "kind": "release_packaging",
            "requested_asset": asset_name,
            "available_assets": available,
            "tox_assets": tox_assets,
            "release_packaging_incomplete": not tox_assets,
            "remediation": [
                f"Publish a canonical .tox release asset named {asset_name!r}.",
                "If local source install is current, the release package is incomplete rather than the local install being stale.",
                "Rerun setup_mcp_in_td.py after a valid .tox is installed.",
            ],
        },
    }


# ──────────────────────────────────────────────────────────
# Public entrypoint
# ──────────────────────────────────────────────────────────


def run(
    *,
    check_only: bool = True,
    installed_version: str | None = None,
    fetch_releases: Callable[[], dict[str, Any]] | None = None,
    download_asset: Callable[[str], bytes] | None = None,
    install_paths: list[Path] | None = None,
    asset_name: str = DEFAULT_ASSET_NAME,
) -> dict[str, Any]:
    """Check (and optionally install) the latest TDPilot release.

    Parameters
    ----------
    check_only:
        When True (default), report only — never download or write.
    installed_version:
        Override for the installed version. Defaults to ``td_mcp.__version__``.
    fetch_releases, download_asset:
        Network callables, injected for tests. Production defaults call
        GitHub via stdlib urllib.
    install_paths:
        Where to write the asset when ``check_only=False``. Defaults to
        the three-location sync table.
    asset_name:
        Which release asset to pull. Defaults to ``tdpilot.tox``.
    """
    if installed_version is None:
        from td_mcp import __version__ as installed_version

    fetch = fetch_releases or _default_fetch_releases
    download = download_asset or _default_download_asset

    try:
        release = fetch()
    except Exception as exc:
        return _http_fetch_error_result(exc, installed_version=installed_version)

    if not isinstance(release, dict) or "tag_name" not in release:
        return {
            "ok": False,
            "error": "malformed release payload (missing tag_name)",
            "error_code": "malformed_release_payload",
            "installed": installed_version,
        }

    latest_tag = release.get("tag_name", "")
    latest_version = latest_tag.lstrip("v")
    release_url = release.get("html_url", "")
    newer = is_newer(latest=latest_tag, installed=installed_version)

    result: dict[str, Any] = {
        "ok": True,
        "installed": installed_version,
        "latest": latest_version,
        "newer_available": newer,
        "release_url": release_url,
        "follow_up": (
            "After this update, re-run setup_mcp_in_td.py inside TouchDesigner "
            "Textport to refresh the live /local/mcp_server COMP from the new .tox."
        ),
    }

    if check_only or not newer:
        return result

    # Find the requested asset.
    asset_url: str | None = None
    assets = list(release.get("assets") or [])
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if _asset_name_matches(str(asset.get("name") or ""), asset_name):
            asset_url = asset.get("browser_download_url")
            break

    if not asset_url:
        return _missing_asset_result(result, latest_tag=latest_tag, asset_name=asset_name, assets=assets)

    try:
        payload = download(asset_url)
    except Exception as exc:
        return {
            **result,
            "ok": False,
            "error": f"failed to download asset: {exc}",
            "error_code": "asset_download_failed",
        }

    if not isinstance(payload, (bytes, bytearray)) or len(payload) == 0:
        return {**result, "ok": False, "error": "downloaded asset is empty", "error_code": "asset_empty"}

    paths = install_paths if install_paths is not None else _resolve_default_install_paths(asset_name)
    if not paths:
        return {**result, "ok": False, "error": "no install paths resolved", "error_code": "no_install_paths"}

    installed_to, md5_map = _install_to_paths(bytes(payload), [Path(p) for p in paths])
    if not installed_to:
        return {
            **result,
            "ok": False,
            "error": "no install paths were writable",
            "error_code": "install_paths_unwritable",
        }

    result["installed_to"] = installed_to
    result["md5"] = md5_map
    result["bytes_written"] = len(payload)
    return result


# ──────────────────────────────────────────────────────────
# CLI entry — `python -m td_mcp.self_updater`
# ──────────────────────────────────────────────────────────


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="TDPilot self-updater.")
    parser.add_argument(
        "--install",
        action="store_true",
        help="Download and install the latest release. Default is check-only.",
    )
    args = parser.parse_args()
    result = run(check_only=not args.install)
    print(json.dumps(result, indent=2))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(_main())
