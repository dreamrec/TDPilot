"""Tests for auth_bootstrap — the env-file + autogenerate-secret flow.

Design:
  - `~/.tdpilot/.tdpilot.env` is the canonical cross-process env file.
    Both the Python MCP server and the TD-side `tdpilot_startup.py` can
    find it at a stable user-scoped path, without needing to share
    `${CLAUDE_PLUGIN_ROOT}` awareness.
  - `load_env_file(path)` populates `os.environ` from a KEY=VALUE file
    WITHOUT overwriting existing env. Process-supplied env always wins.
  - `maybe_generate_secret(path)` writes a fresh secret to the file IFF
    auth is required, no secret is resolvable, and
    `TD_MCP_AUTOGENERATE_SECRET=1` is set. This makes autogeneration
    opt-in (prevents unexpected disk writes).
  - `bootstrap_auth(path)` is the top-level orchestrator called before
    `verify_auth_config()`. It sequences load → maybe-generate → re-load.
"""

from __future__ import annotations

import os
import stat

import pytest

from td_mcp import auth_bootstrap


def _env_path(tmp_path) -> "os.PathLike":
    return tmp_path / ".tdpilot.env"


# ---------------------------------------------------------------------------
# load_env_file
# ---------------------------------------------------------------------------


class TestLoadEnvFile:
    def test_missing_file_is_silent_no_op(self, tmp_path, monkeypatch):
        """If the file doesn't exist, load is a no-op (no exception)."""
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
        auth_bootstrap.load_env_file(_env_path(tmp_path))
        assert "TD_MCP_SHARED_SECRET" not in os.environ

    def test_populates_missing_env_vars(self, tmp_path, monkeypatch):
        env_file = _env_path(tmp_path)
        env_file.write_text("TD_MCP_SHARED_SECRET=file-secret-value\n", encoding="utf-8")
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        auth_bootstrap.load_env_file(env_file)

        assert os.environ["TD_MCP_SHARED_SECRET"] == "file-secret-value"

    def test_does_not_overwrite_existing_env_vars(self, tmp_path, monkeypatch):
        """Process-supplied env wins over file contents."""
        env_file = _env_path(tmp_path)
        env_file.write_text("TD_MCP_SHARED_SECRET=file-secret\n", encoding="utf-8")
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "process-secret")

        auth_bootstrap.load_env_file(env_file)

        assert os.environ["TD_MCP_SHARED_SECRET"] == "process-secret"

    def test_skips_comments_and_blank_lines(self, tmp_path, monkeypatch):
        env_file = _env_path(tmp_path)
        env_file.write_text(
            "# comment line\n"
            "\n"
            "TD_MCP_SHARED_SECRET=ok\n"
            "  # indented comment\n"
            "TD_MCP_REQUIRE_AUTH=1\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
        monkeypatch.delenv("TD_MCP_REQUIRE_AUTH", raising=False)

        auth_bootstrap.load_env_file(env_file)

        assert os.environ["TD_MCP_SHARED_SECRET"] == "ok"
        assert os.environ["TD_MCP_REQUIRE_AUTH"] == "1"

    def test_strips_surrounding_quotes(self, tmp_path, monkeypatch):
        env_file = _env_path(tmp_path)
        env_file.write_text(
            'TD_MCP_SHARED_SECRET="quoted-value"\n'
            "OTHER_KEY='single-quoted'\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
        monkeypatch.delenv("OTHER_KEY", raising=False)

        auth_bootstrap.load_env_file(env_file)

        assert os.environ["TD_MCP_SHARED_SECRET"] == "quoted-value"
        assert os.environ["OTHER_KEY"] == "single-quoted"


# ---------------------------------------------------------------------------
# maybe_generate_secret
# ---------------------------------------------------------------------------


class TestMaybeGenerateSecret:
    def test_no_op_when_auth_not_required(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TD_MCP_REQUIRE_AUTH", raising=False)
        monkeypatch.setenv("TD_MCP_AUTOGENERATE_SECRET", "1")

        result = auth_bootstrap.maybe_generate_secret(_env_path(tmp_path))

        assert result is None
        assert not _env_path(tmp_path).exists()

    def test_no_op_when_autogenerate_not_enabled(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        monkeypatch.delenv("TD_MCP_AUTOGENERATE_SECRET", raising=False)
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        result = auth_bootstrap.maybe_generate_secret(_env_path(tmp_path))

        assert result is None
        assert not _env_path(tmp_path).exists()

    def test_no_op_when_secret_already_present_in_env(self, tmp_path, monkeypatch):
        """If the process already has a secret, don't overwrite anything."""
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        monkeypatch.setenv("TD_MCP_AUTOGENERATE_SECRET", "1")
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "existing-secret")

        result = auth_bootstrap.maybe_generate_secret(_env_path(tmp_path))

        assert result is None
        assert not _env_path(tmp_path).exists()

    def test_generates_and_persists_when_required_and_allowed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        monkeypatch.setenv("TD_MCP_AUTOGENERATE_SECRET", "1")
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        result = auth_bootstrap.maybe_generate_secret(_env_path(tmp_path))

        assert result is not None
        assert len(result) >= 32
        # Written to disk
        assert _env_path(tmp_path).exists()
        contents = _env_path(tmp_path).read_text(encoding="utf-8")
        assert f"TD_MCP_SHARED_SECRET={result}" in contents
        # Injected into os.environ for same-process use
        assert os.environ["TD_MCP_SHARED_SECRET"] == result

    def test_generated_file_has_restrictive_permissions_on_posix(self, tmp_path, monkeypatch):
        """Secret file should be 0600 on posix so other users can't read it."""
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        monkeypatch.setenv("TD_MCP_AUTOGENERATE_SECRET", "1")
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        auth_bootstrap.maybe_generate_secret(_env_path(tmp_path))

        if os.name == "posix":
            mode = _env_path(tmp_path).stat().st_mode
            # Only owner read/write; no group/other access
            assert mode & stat.S_IRWXG == 0, f"group bits set: {oct(mode)}"
            assert mode & stat.S_IRWXO == 0, f"other bits set: {oct(mode)}"

    def test_generate_is_idempotent_if_file_secret_present(self, tmp_path, monkeypatch):
        """If a secret is already on disk but not in env, load it into env
        instead of generating a new one."""
        env_file = _env_path(tmp_path)
        env_file.write_text("TD_MCP_SHARED_SECRET=persisted-secret\n", encoding="utf-8")
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        monkeypatch.setenv("TD_MCP_AUTOGENERATE_SECRET", "1")
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        # bootstrap_auth sequences load → maybe-generate, so we test through it.
        auth_bootstrap.bootstrap_auth(env_file)

        assert os.environ["TD_MCP_SHARED_SECRET"] == "persisted-secret"
        # File unchanged — no new line appended
        assert env_file.read_text(encoding="utf-8").count("TD_MCP_SHARED_SECRET=") == 1


# ---------------------------------------------------------------------------
# bootstrap_auth — the orchestrator used by server.main()
# ---------------------------------------------------------------------------


class TestBootstrapAuth:
    def test_full_fresh_install_flow(self, tmp_path, monkeypatch):
        """Fresh plugin install: no .tdpilot.env, auth required, autogen enabled.
        bootstrap_auth() must end with TD_MCP_SHARED_SECRET set in env + on disk."""
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        monkeypatch.setenv("TD_MCP_AUTOGENERATE_SECRET", "1")
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        auth_bootstrap.bootstrap_auth(_env_path(tmp_path))

        assert os.environ.get("TD_MCP_SHARED_SECRET")
        assert _env_path(tmp_path).exists()

    def test_subsequent_start_reuses_persisted_secret(self, tmp_path, monkeypatch):
        """Second server start: .tdpilot.env already has the secret; env is empty.
        bootstrap_auth() loads the file, secret is now in env, done."""
        env_file = _env_path(tmp_path)
        env_file.write_text("TD_MCP_SHARED_SECRET=seeded\n", encoding="utf-8")
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        # Note: TDPILOT_AUTOGENERATE_SECRET can be anything — we already have one
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        auth_bootstrap.bootstrap_auth(env_file)

        assert os.environ["TD_MCP_SHARED_SECRET"] == "seeded"
        # File unchanged
        assert env_file.read_text(encoding="utf-8").strip() == "TD_MCP_SHARED_SECRET=seeded"

    def test_auth_not_required_is_pure_no_op(self, tmp_path, monkeypatch):
        """No auth = no env file touched, no secret generated."""
        monkeypatch.delenv("TD_MCP_REQUIRE_AUTH", raising=False)
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        auth_bootstrap.bootstrap_auth(_env_path(tmp_path))

        assert not _env_path(tmp_path).exists()
        assert "TD_MCP_SHARED_SECRET" not in os.environ

    def test_auth_required_without_autogenerate_leaves_gate_to_trip(self, tmp_path, monkeypatch):
        """The fail-loud gate (verify_auth_config) should still trip if the
        user declines autogenerate. bootstrap_auth's job is to try, not to
        rescue."""
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        monkeypatch.delenv("TD_MCP_AUTOGENERATE_SECRET", raising=False)
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        auth_bootstrap.bootstrap_auth(_env_path(tmp_path))

        # No secret materialized
        assert "TD_MCP_SHARED_SECRET" not in os.environ
        # verify_auth_config called afterwards should raise
        from td_mcp.server import verify_auth_config

        with pytest.raises(RuntimeError):
            verify_auth_config()


# ---------------------------------------------------------------------------
# Observability — generated secret must NOT leak into stdout
# ---------------------------------------------------------------------------


class TestNoSecretLeakToStdout:
    def test_bootstrap_does_not_print_secret(self, tmp_path, monkeypatch, capsys):
        """Server startup via bootstrap_auth must NOT echo the secret to stdout.
        Logs/file are fine; stdout is where MCP transport negotiation lives."""
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        monkeypatch.setenv("TD_MCP_AUTOGENERATE_SECRET", "1")
        monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

        auth_bootstrap.bootstrap_auth(_env_path(tmp_path))
        secret = os.environ["TD_MCP_SHARED_SECRET"]

        captured = capsys.readouterr()
        assert secret not in captured.out, "secret leaked to stdout"


# ---------------------------------------------------------------------------
# Canonical path
# ---------------------------------------------------------------------------


def test_default_env_path_is_user_scoped_not_cwd():
    """Canonical location is ~/.tdpilot/.tdpilot.env — user-scoped, survives
    plugin reinstall, shared with TD-side tdpilot_startup.py."""
    from pathlib import Path

    expected = Path.home() / ".tdpilot" / ".tdpilot.env"
    assert auth_bootstrap.default_env_file() == expected
