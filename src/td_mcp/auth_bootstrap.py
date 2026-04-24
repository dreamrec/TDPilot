"""Shared auth bootstrap for TDPilot's Python MCP server and TD-side callbacks.

Problem solved
--------------
Before v1.4.5, the Claude Code plugin install path shipped ``.mcp.json`` with
``TD_MCP_REQUIRE_AUTH=1`` and no mechanism to provision ``TD_MCP_SHARED_SECRET``.
``install.sh`` / ``install.ps1`` generated secrets, but the plugin path didn't
invoke them. The v1.4.3 startup gate (``server.verify_auth_config``) then
deterministically failed every fresh plugin install — swapping one silent
failure (401 at every request) for a loud one (startup error), neither of
which is actually working.

This module provides a deterministic fix: a shared ``.tdpilot.env`` at a
well-known user-scoped path (``~/.tdpilot/.tdpilot.env``) that both the
Python MCP server and the TD-side ``tdpilot_startup.py`` can locate without
having to share ``${CLAUDE_PLUGIN_ROOT}`` awareness.

Sequence used at server startup (see ``server.main``):

  1. ``bootstrap_auth()`` is called before ``verify_auth_config()``.
  2. ``load_env_file()`` populates ``os.environ`` from the file, *without*
     overwriting process-supplied env. Explicit process env still wins.
  3. ``maybe_generate_secret()`` only acts if:
     - ``TD_MCP_REQUIRE_AUTH`` is truthy,
     - ``TD_MCP_AUTOGENERATE_SECRET`` is truthy (opt-in; prevents
       unexpected disk writes), and
     - no secret is resolvable after step 2.
     If all three hold, a fresh 256-bit secret is written to the file with
     restrictive permissions and injected into ``os.environ``.
  4. ``verify_auth_config()`` sees the populated env and passes.

If the user hasn't opted in to autogeneration, the gate trips as before —
``bootstrap_auth`` doesn't rescue silently. This is intentional: surfacing
the misconfiguration is better than generating a secret behind the user's
back.

Observability
-------------
Generated secrets are written to disk AND injected into the process env,
but NEVER printed to stdout — stdout is the MCP transport on stdio, and
secret leakage there would be fatal. Secret material must only surface
via the file (readable by the user) or via future structured logs.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

_TRUTHY = {"1", "true", "yes", "on"}


def default_env_file() -> Path:
    """Canonical cross-process env-file location.

    ~/.tdpilot/.tdpilot.env — user-scoped, survives plugin reinstalls,
    found by both the Python MCP server and the TD-side tdpilot_startup.py
    (the latter falls back to this path when ``<repo_root>/.tdpilot.env``
    is missing — see td_component/tdpilot_startup.py).
    """
    return Path.home() / ".tdpilot" / ".tdpilot.env"


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUTHY


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_env_file(path: Path) -> None:
    """Populate ``os.environ`` from KEY=VALUE lines in ``path``.

    Existing environment variables are never overwritten — process-supplied
    env wins, which matches the ``tdpilot_startup.py`` contract. Missing
    files are silently ignored (the file is optional). Lines starting with
    ``#`` and blank lines are skipped.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_quotes(value)


def _auth_required() -> bool:
    return _is_truthy(os.environ.get("TD_MCP_REQUIRE_AUTH"))


def _autogenerate_enabled() -> bool:
    return _is_truthy(os.environ.get("TD_MCP_AUTOGENERATE_SECRET"))


def _secret_present() -> bool:
    return bool((os.environ.get("TD_MCP_SHARED_SECRET") or "").strip())


def maybe_generate_secret(path: Path) -> str | None:
    """Generate + persist a secret IFF auth is required, secret is missing,
    and autogeneration is explicitly enabled. Otherwise no-op.

    Returns the generated secret on success, ``None`` otherwise.
    """
    if not _auth_required():
        return None
    if not _autogenerate_enabled():
        return None
    if _secret_present():
        return None

    secret = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    # Preserve any existing non-secret keys (idempotent re-run).
    existing_lines: list[str] = []
    if path.exists():
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if line.startswith("TD_MCP_SHARED_SECRET="):
                    continue
                existing_lines.append(raw)
        except OSError:
            pass

    payload_lines = existing_lines + [f"TD_MCP_SHARED_SECRET={secret}"]
    tmp.write_text("\n".join(payload_lines) + "\n", encoding="utf-8")
    # Restrict permissions on posix so other users can't read the secret.
    if os.name == "posix":
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
    tmp.replace(path)

    os.environ["TD_MCP_SHARED_SECRET"] = secret
    return secret


def bootstrap_auth(path: Path | None = None) -> None:
    """Called at server startup before ``verify_auth_config()``.

    Sequences: load-from-file → maybe-generate → (done). Silent on stdout.
    Callers that want verbose behaviour can read the env file themselves
    after the call or inspect ``os.environ['TD_MCP_SHARED_SECRET']``.
    """
    env_file = path or default_env_file()
    load_env_file(env_file)
    generated = maybe_generate_secret(env_file)
    if generated is not None:
        # Sanctioned log line — stderr only, never stdout (stdio MCP).
        # Secret itself is NOT included.
        print(
            f"[tdpilot] Generated TD_MCP_SHARED_SECRET and wrote it to {env_file}",
            file=sys.stderr,
        )


__all__ = [
    "default_env_file",
    "load_env_file",
    "maybe_generate_secret",
    "bootstrap_auth",
]
