"""Tests for v1.6.4 autopin: TD-startup auto-checkout-latest-tag flow.

Covers two surfaces:

1. ``td_component/tdpilot_startup.py:_auto_pin_latest_tag(repo_root)``
   — the function that runs at TD launch when ``TDPILOT_AUTO_PIN_TAG=1``
   is set in ``~/.tdpilot/.tdpilot.env``. It must:
     - Be a silent no-op when the env var is unset/0/false.
     - Skip cleanly when ``repo_root`` isn't a git checkout.
     - Issue ``git fetch --tags`` then ``git describe --tags --abbrev=0
       origin/main`` to find the latest tag.
     - Skip checkout when HEAD is already at that tag (idempotent).
     - Catch every subprocess failure (timeout, non-zero exit, anything)
       so a broken git or no network never blocks TD startup.

2. ``src/td_mcp/server.py:_run_autopin_command(args)`` — the CLI
   subcommand that toggles the env-file flag. It must:
     - ``--enable`` write ``TDPILOT_AUTO_PIN_TAG=1`` to the file.
     - ``--disable`` REMOVE the key (cleaner than ``=0``) while
       preserving every other line in the file.
     - No flag → print status without modifying state.
     - Mutually exclusive flags → exit 2 (argparse-level guard).
     - Atomic write (tmp + replace) so a crash mid-write can't corrupt
       the shared env file (also holds the auth secret).

Why import ``tdpilot_startup`` via ``importlib.util``: the file lives in
``td_component/`` (a TD-runtime payload directory, not a Python package)
and carries no ``__init__.py``. Using importlib lets us load it like a
module without polluting ``sys.path``. The ``TDPILOT_STARTUP_SKIP=1``
env-var guard added in v1.6.4 prevents the bottom-of-file ``_startup()``
call from firing during import (which would call ``op()`` etc. and
crash outside TD).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from td_mcp import server

REPO_ROOT = Path(__file__).resolve().parent.parent
STARTUP_PATH = REPO_ROOT / "td_component" / "tdpilot_startup.py"


@pytest.fixture(scope="module")
def startup_module():
    """Load tdpilot_startup.py without firing _startup() at import time."""
    os.environ["TDPILOT_STARTUP_SKIP"] = "1"
    try:
        spec = importlib.util.spec_from_file_location("tdpilot_startup_under_test", STARTUP_PATH)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        os.environ.pop("TDPILOT_STARTUP_SKIP", None)
        # Clean up sys.modules in case importlib added anything (it doesn't,
        # but be defensive against future Python changes).
        sys.modules.pop("tdpilot_startup_under_test", None)


# ---------------------------------------------------------------------------
# _auto_pin_latest_tag — startup-side
# ---------------------------------------------------------------------------


class TestAutoPinDisabled:
    def test_env_unset_is_no_op(self, startup_module, tmp_path, monkeypatch):
        """No TDPILOT_AUTO_PIN_TAG env → never call subprocess."""
        monkeypatch.delenv("TDPILOT_AUTO_PIN_TAG", raising=False)
        with patch.object(subprocess, "run") as run_mock:
            startup_module._auto_pin_latest_tag(str(tmp_path))
        assert run_mock.call_count == 0

    def test_env_zero_is_no_op(self, startup_module, tmp_path, monkeypatch):
        """TDPILOT_AUTO_PIN_TAG=0 → no subprocess calls."""
        monkeypatch.setenv("TDPILOT_AUTO_PIN_TAG", "0")
        with patch.object(subprocess, "run") as run_mock:
            startup_module._auto_pin_latest_tag(str(tmp_path))
        assert run_mock.call_count == 0


class TestAutoPinSkipsNonGit:
    def test_non_git_repo_skip_silently(self, startup_module, tmp_path, monkeypatch, capsys):
        """No .git/ dir → print 'not a git checkout' and return without subprocess."""
        monkeypatch.setenv("TDPILOT_AUTO_PIN_TAG", "1")
        with patch.object(subprocess, "run") as run_mock:
            startup_module._auto_pin_latest_tag(str(tmp_path))
        assert run_mock.call_count == 0
        assert "not a git checkout" in capsys.readouterr().out


class TestAutoPinHappyPath:
    def _setup_fake_git(self, tmp_path):
        (tmp_path / ".git").mkdir()
        return tmp_path

    def test_fetches_describes_and_checks_out(self, startup_module, tmp_path, monkeypatch, capsys):
        """End-to-end: fetch → describe (latest=v1.6.4) → describe HEAD (v1.6.2) → checkout v1.6.4."""
        repo = self._setup_fake_git(tmp_path)
        monkeypatch.setenv("TDPILOT_AUTO_PIN_TAG", "1")

        def fake_run(cmd, **kwargs):
            # cmd[1] is 'fetch' / 'describe' / 'checkout'
            verb = cmd[1] if len(cmd) > 1 else ""
            if verb == "fetch":
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if verb == "describe" and "origin/main" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "v1.6.4\n", "")
            if verb == "describe" and "HEAD" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "v1.6.2\n", "")
            if verb == "checkout":
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            raise AssertionError(f"unexpected command: {cmd}")

        with patch.object(subprocess, "run", side_effect=fake_run) as run_mock:
            startup_module._auto_pin_latest_tag(str(repo))

        # Should have fired fetch, two describes, and one checkout.
        verbs = [call.args[0][1] for call in run_mock.call_args_list]
        assert verbs == ["fetch", "describe", "describe", "checkout"]
        out = capsys.readouterr().out
        assert "AUTOPIN updated" in out
        assert "v1.6.2" in out and "v1.6.4" in out

    def test_already_on_latest_skips_checkout(self, startup_module, tmp_path, monkeypatch, capsys):
        """If HEAD's tag == latest tag, don't run checkout (idempotent)."""
        repo = self._setup_fake_git(tmp_path)
        monkeypatch.setenv("TDPILOT_AUTO_PIN_TAG", "1")

        def fake_run(cmd, **kwargs):
            verb = cmd[1] if len(cmd) > 1 else ""
            if verb == "fetch":
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if verb == "describe":
                return subprocess.CompletedProcess(cmd, 0, "v1.6.4\n", "")
            raise AssertionError(f"checkout should not run when already on latest: {cmd}")

        with patch.object(subprocess, "run", side_effect=fake_run) as run_mock:
            startup_module._auto_pin_latest_tag(str(repo))

        verbs = [call.args[0][1] for call in run_mock.call_args_list]
        assert verbs == ["fetch", "describe", "describe"]
        # No "AUTOPIN updated" line because we no-op'd
        assert "AUTOPIN updated" not in capsys.readouterr().out


class TestAutoPinErrorHandling:
    def test_fetch_timeout_caught(self, startup_module, tmp_path, monkeypatch, capsys):
        (tmp_path / ".git").mkdir()
        monkeypatch.setenv("TDPILOT_AUTO_PIN_TAG", "1")

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 5)

        with patch.object(subprocess, "run", side_effect=fake_run):
            # MUST NOT raise — startup script must never crash TD launch.
            startup_module._auto_pin_latest_tag(str(tmp_path))

        assert "AUTOPIN skipped" in capsys.readouterr().out

    def test_called_process_error_caught(self, startup_module, tmp_path, monkeypatch, capsys):
        (tmp_path / ".git").mkdir()
        monkeypatch.setenv("TDPILOT_AUTO_PIN_TAG", "1")

        def fake_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(128, cmd, b"", b"fatal: not a git repo")

        with patch.object(subprocess, "run", side_effect=fake_run):
            startup_module._auto_pin_latest_tag(str(tmp_path))

        assert "AUTOPIN failed" in capsys.readouterr().out

    def test_unexpected_exception_caught(self, startup_module, tmp_path, monkeypatch, capsys):
        """Even an OSError / random exception from subprocess must be swallowed."""
        (tmp_path / ".git").mkdir()
        monkeypatch.setenv("TDPILOT_AUTO_PIN_TAG", "1")

        def fake_run(cmd, **kwargs):
            raise OSError("disk gone")

        with patch.object(subprocess, "run", side_effect=fake_run):
            startup_module._auto_pin_latest_tag(str(tmp_path))

        assert "AUTOPIN unexpected error" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# CLI: tdpilot autopin --enable / --disable / (status)
# ---------------------------------------------------------------------------


class TestAutopinCliRead:
    def test_main_dispatches_to_autopin(self, tmp_path, monkeypatch):
        """server.main(['autopin']) routes to _run_autopin_command and exits with its rc."""
        env_file = tmp_path / ".tdpilot.env"
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        with pytest.raises(SystemExit) as exc:
            server.main(["autopin"])
        assert exc.value.code == 0

    def test_run_status_no_file(self, tmp_path, monkeypatch, capsys):
        env_file = tmp_path / ".tdpilot.env"
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        import argparse as _ap

        ns = _ap.Namespace(enable=False, disable=False)
        assert server._run_autopin_command(ns) == 0
        out = capsys.readouterr().out
        assert "Auto-pin: DISABLED" in out
        assert "To enable" in out

    def test_run_status_enabled(self, tmp_path, monkeypatch, capsys):
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text("TDPILOT_AUTO_PIN_TAG=1\n", encoding="utf-8")
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        import argparse as _ap

        ns = _ap.Namespace(enable=False, disable=False)
        assert server._run_autopin_command(ns) == 0
        out = capsys.readouterr().out
        assert "Auto-pin: ENABLED" in out
        assert "Next TD launch" in out


class TestAutopinCliEnable:
    def test_enable_writes_key(self, tmp_path, monkeypatch, capsys):
        env_file = tmp_path / ".tdpilot.env"
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        import argparse as _ap

        ns = _ap.Namespace(enable=True, disable=False)
        assert server._run_autopin_command(ns) == 0

        text = env_file.read_text(encoding="utf-8")
        assert "TDPILOT_AUTO_PIN_TAG=1" in text
        assert "ENABLED" in capsys.readouterr().out

    def test_enable_preserves_existing_keys(self, tmp_path, monkeypatch):
        """Enabling autopin must not delete TD_MCP_SHARED_SECRET, comments, etc."""
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text(
            "# config file — written by auth_bootstrap\n"
            "TD_MCP_REQUIRE_AUTH=0\n"
            "TD_MCP_EXEC_MODE=restricted\n"
            "TD_MCP_SHARED_SECRET=abc123def456\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        import argparse as _ap

        ns = _ap.Namespace(enable=True, disable=False)
        assert server._run_autopin_command(ns) == 0

        text = env_file.read_text(encoding="utf-8")
        assert "# config file — written by auth_bootstrap" in text
        assert "TD_MCP_REQUIRE_AUTH=0" in text
        assert "TD_MCP_EXEC_MODE=restricted" in text
        assert "TD_MCP_SHARED_SECRET=abc123def456" in text
        assert "TDPILOT_AUTO_PIN_TAG=1" in text

    def test_enable_idempotent(self, tmp_path, monkeypatch):
        """Enabling twice must not duplicate the line."""
        env_file = tmp_path / ".tdpilot.env"
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        import argparse as _ap

        ns = _ap.Namespace(enable=True, disable=False)
        server._run_autopin_command(ns)
        server._run_autopin_command(ns)

        text = env_file.read_text(encoding="utf-8")
        assert text.count("TDPILOT_AUTO_PIN_TAG=1") == 1

    def test_enable_replaces_old_value(self, tmp_path, monkeypatch):
        """If file already has TDPILOT_AUTO_PIN_TAG=0, --enable replaces with =1."""
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text("TDPILOT_AUTO_PIN_TAG=0\nOTHER_KEY=value\n", encoding="utf-8")
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        import argparse as _ap

        ns = _ap.Namespace(enable=True, disable=False)
        server._run_autopin_command(ns)

        text = env_file.read_text(encoding="utf-8")
        assert "TDPILOT_AUTO_PIN_TAG=1" in text
        assert "TDPILOT_AUTO_PIN_TAG=0" not in text
        assert "OTHER_KEY=value" in text


class TestAutopinCliDisable:
    def test_disable_removes_key(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text(
            "TD_MCP_SHARED_SECRET=abc123\nTDPILOT_AUTO_PIN_TAG=1\nOTHER=x\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        import argparse as _ap

        ns = _ap.Namespace(enable=False, disable=True)
        server._run_autopin_command(ns)

        text = env_file.read_text(encoding="utf-8")
        assert "TDPILOT_AUTO_PIN_TAG" not in text
        assert "TD_MCP_SHARED_SECRET=abc123" in text
        assert "OTHER=x" in text

    def test_disable_when_key_absent_is_ok(self, tmp_path, monkeypatch):
        """Disabling when not enabled is a no-op (no error, env file may or may not exist)."""
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text("OTHER=x\n", encoding="utf-8")
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        import argparse as _ap

        ns = _ap.Namespace(enable=False, disable=True)
        assert server._run_autopin_command(ns) == 0
        assert "OTHER=x" in env_file.read_text(encoding="utf-8")


class TestAutopinCliBoth:
    def test_both_flags_returns_2(self, tmp_path, monkeypatch, capsys):
        """Defense-in-depth: even if argparse's mutex group is bypassed, runtime check rejects."""
        env_file = tmp_path / ".tdpilot.env"
        monkeypatch.setattr(server, "_autopin_env_file_path", lambda: env_file)
        import argparse as _ap

        ns = _ap.Namespace(enable=True, disable=True)
        assert server._run_autopin_command(ns) == 2
        assert "mutually exclusive" in capsys.readouterr().err


class TestAutopinReadStateValueParsing:
    def test_value_one_is_enabled(self, tmp_path):
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text("TDPILOT_AUTO_PIN_TAG=1\n", encoding="utf-8")
        enabled, raw = server._read_autopin_state(env_file)
        assert enabled is True
        assert raw == "1"

    def test_value_true_is_enabled(self, tmp_path):
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text("TDPILOT_AUTO_PIN_TAG=true\n", encoding="utf-8")
        enabled, raw = server._read_autopin_state(env_file)
        assert enabled is True
        assert raw == "true"

    def test_value_zero_is_disabled(self, tmp_path):
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text("TDPILOT_AUTO_PIN_TAG=0\n", encoding="utf-8")
        enabled, raw = server._read_autopin_state(env_file)
        assert enabled is False
        assert raw == "0"

    def test_value_quoted_is_stripped(self, tmp_path):
        """Some env files quote values — we strip and still match."""
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text('TDPILOT_AUTO_PIN_TAG="yes"\n', encoding="utf-8")
        enabled, raw = server._read_autopin_state(env_file)
        assert enabled is True
        assert raw == "yes"

    def test_missing_file(self, tmp_path):
        enabled, raw = server._read_autopin_state(tmp_path / "nope.env")
        assert enabled is False
        assert raw is None

    def test_key_absent(self, tmp_path):
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text("OTHER=x\n", encoding="utf-8")
        enabled, raw = server._read_autopin_state(env_file)
        assert enabled is False
        assert raw is None

    def test_comments_and_blank_lines_skipped(self, tmp_path):
        env_file = tmp_path / ".tdpilot.env"
        env_file.write_text(
            "# header\n\n# autopin section\nTDPILOT_AUTO_PIN_TAG=1\n",
            encoding="utf-8",
        )
        enabled, _ = server._read_autopin_state(env_file)
        assert enabled is True


# ---------------------------------------------------------------------------
# Argparse integration
# ---------------------------------------------------------------------------


class TestArgparseSubcommand:
    def test_autopin_subcommand_registered(self):
        """The 'autopin' subcommand must be parseable from CLI args."""
        parser = server._build_parser()
        args = parser.parse_args(["autopin"])
        assert args.command == "autopin"
        assert args.enable is False
        assert args.disable is False

    def test_autopin_enable_flag(self):
        parser = server._build_parser()
        args = parser.parse_args(["autopin", "--enable"])
        assert args.enable is True
        assert args.disable is False

    def test_autopin_disable_flag(self):
        parser = server._build_parser()
        args = parser.parse_args(["autopin", "--disable"])
        assert args.enable is False
        assert args.disable is True

    def test_autopin_argparse_rejects_both_flags(self):
        """argparse's mutex group should reject --enable --disable together with SystemExit(2)."""
        parser = server._build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["autopin", "--enable", "--disable"])
        assert exc.value.code == 2
