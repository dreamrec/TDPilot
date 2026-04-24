"""Tests for exec-safety modes, focusing on the new ``standard`` tier."""

import re
import sys
import types
from unittest.mock import patch

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Helper: load only the exec-safety helpers from tool_registry without
# triggering the MCP decorator registrations that fail outside a server.
# ---------------------------------------------------------------------------


def _load_exec_helpers():
    """Return a namespace dict with the exec-safety helpers."""
    src_path = (
        __import__("pathlib").Path(__file__).resolve().parent.parent / "src" / "td_mcp" / "tool_registry.py"
    )
    source = src_path.read_text()
    # We only need lines up to the first @mcp decorator.
    # Cut at the first function that uses @mcp.
    cut = source.find("\n@mcp.")
    if cut != -1:
        source = source[:cut]
    # Build a minimal module with the needed dependencies pre-injected
    mod = types.ModuleType("_exec_helpers")
    mod.__dict__["re"] = re
    mod.__dict__["os"] = __import__("os")
    mod.__dict__["sys"] = sys
    mod.__dict__["__name__"] = "_exec_helpers"
    mod.__dict__["__file__"] = str(src_path)
    # Provide stubs for things the top of the file needs
    mod.__dict__["Optional"] = None
    mod.__dict__["Dict"] = None
    mod.__dict__["List"] = None
    mod.__dict__["Any"] = None
    mod.__dict__["Tuple"] = None
    # Use compile + eval to load the truncated source into the module
    code_obj = compile(source, str(src_path), "exec")
    # nosec B102 — intentional: loading our own source for test isolation
    builtins = __builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__
    builtins["eval"](code_obj, mod.__dict__)
    return mod


_helpers = _load_exec_helpers()

_normalize_exec_mode = _helpers._normalize_exec_mode
_restricted_exec_violation = _helpers._restricted_exec_violation
_enforce_exec_mode = _helpers._enforce_exec_mode


# ---------------------------------------------------------------------------
# _normalize_exec_mode
# ---------------------------------------------------------------------------


class TestNormalizeExecMode:
    def test_standard_recognized(self):
        assert _normalize_exec_mode("standard") == "standard"

    def test_standard_case_insensitive(self):
        assert _normalize_exec_mode("Standard") == "standard"
        assert _normalize_exec_mode("STANDARD") == "standard"

    def test_existing_modes_unchanged(self):
        assert _normalize_exec_mode("off") == "off"
        assert _normalize_exec_mode("restricted") == "restricted"
        assert _normalize_exec_mode("full") == "full"


# ---------------------------------------------------------------------------
# _standard_exec_violation
# ---------------------------------------------------------------------------


class TestStandardExecViolation:
    @pytest.fixture(autouse=True)
    def _import_fn(self):
        self.fn = _helpers._standard_exec_violation

    # -- allowed imports --
    @pytest.mark.parametrize(
        "mod",
        [
            "json",
            "math",
            "re",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "copy",
            "textwrap",
            "string",
            "random",
            "decimal",
            "fractions",
            "statistics",
        ],
    )
    def test_allows_whitelisted_import(self, mod):
        assert self.fn(f"import {mod}") is None

    @pytest.mark.parametrize(
        "mod",
        [
            "json",
            "math",
            "re",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "copy",
            "textwrap",
            "string",
            "random",
            "decimal",
            "fractions",
            "statistics",
        ],
    )
    def test_allows_whitelisted_from_import(self, mod):
        assert self.fn(f"from {mod} import something") is None

    # -- blocked imports --
    @pytest.mark.parametrize(
        "mod",
        [
            "os",
            "sys",
            "subprocess",
            "socket",
            "importlib",
            "pathlib",
            "shutil",
        ],
    )
    def test_blocks_dangerous_import(self, mod):
        result = self.fn(f"import {mod}")
        assert result is not None

    @pytest.mark.parametrize(
        "mod",
        [
            "os",
            "sys",
            "subprocess",
            "socket",
            "importlib",
            "pathlib",
            "shutil",
        ],
    )
    def test_blocks_dangerous_from_import(self, mod):
        result = self.fn(f"from {mod} import something")
        assert result is not None

    # -- blocked builtins / tokens --
    @pytest.mark.parametrize(
        "snippet",
        [
            "__import__('os')",
            "open('/etc/passwd')",
            "compile('x', '', 'exec')",
            "setattr(obj, 'x', 1)",
            "delattr(obj, 'x')",
            "cls.__subclasses__()",
            "cls.__bases__",
            "globals()",
            "locals()",
            "eval('1+1')",
        ],
    )
    def test_blocks_dangerous_builtins(self, snippet):
        result = self.fn(snippet)
        assert result is not None

    # -- allowed read-only introspection --
    @pytest.mark.parametrize(
        "snippet",
        [
            "dir(obj)",
            "type(obj)",
            "isinstance(obj, int)",
            "hasattr(obj, 'x')",
            "getattr(obj, 'x')",
        ],
    )
    def test_allows_readonly_introspection(self, snippet):
        assert self.fn(snippet) is None

    # -- multiline code --
    def test_multiline_safe(self):
        code = "import json\nimport math\nx = json.dumps({'a': 1})"
        assert self.fn(code) is None

    def test_multiline_with_violation(self):
        code = "import json\nimport os\nx = 1"
        assert self.fn(code) is not None


# ---------------------------------------------------------------------------
# _enforce_exec_mode — standard branch
# ---------------------------------------------------------------------------


class TestEnforceExecModeStandard:
    def test_standard_allows_safe_code(self):
        with patch.object(_helpers, "_current_exec_mode", return_value="standard"):
            _enforce_exec_mode("import json\nx = json.dumps({})")

    def test_standard_blocks_dangerous_code(self):
        with patch.object(_helpers, "_current_exec_mode", return_value="standard"):
            with pytest.raises(PermissionError):
                _enforce_exec_mode("import os")


# ---------------------------------------------------------------------------
# Restricted mode unchanged
# ---------------------------------------------------------------------------


class TestRestrictedUnchanged:
    def test_restricted_still_blocks_all_imports(self):
        result = _restricted_exec_violation("import json")
        assert result is not None

    def test_restricted_still_blocks_tokens(self):
        result = _restricted_exec_violation("open('/etc/passwd')")
        assert result is not None


# ---------------------------------------------------------------------------
# Fix #6 (v1.4.3) — timeout_ms field on ExecPythonInput and forwarding
# through td_exec_python to the TD-side exec endpoint.
# ---------------------------------------------------------------------------


class TestExecPythonInputSchema:
    """ExecPythonInput must expose a bounded optional timeout_ms field."""

    def test_timeout_ms_field_declared(self):
        from td_mcp.models._legacy import ExecPythonInput

        assert "timeout_ms" in ExecPythonInput.model_fields

    def test_timeout_ms_defaults_to_none(self):
        from td_mcp.models._legacy import ExecPythonInput

        assert ExecPythonInput(code="pass").timeout_ms is None

    def test_timeout_ms_accepts_bounded_int(self):
        from td_mcp.models._legacy import ExecPythonInput

        assert ExecPythonInput(code="pass", timeout_ms=100).timeout_ms == 100
        assert ExecPythonInput(code="pass", timeout_ms=5000).timeout_ms == 5000
        assert ExecPythonInput(code="pass", timeout_ms=60000).timeout_ms == 60000

    def test_timeout_ms_rejects_below_minimum(self):
        from td_mcp.models._legacy import ExecPythonInput

        with pytest.raises(ValidationError):
            ExecPythonInput(code="pass", timeout_ms=50)
        with pytest.raises(ValidationError):
            ExecPythonInput(code="pass", timeout_ms=99)

    def test_timeout_ms_rejects_above_maximum(self):
        from td_mcp.models._legacy import ExecPythonInput

        with pytest.raises(ValidationError):
            ExecPythonInput(code="pass", timeout_ms=60001)
        with pytest.raises(ValidationError):
            ExecPythonInput(code="pass", timeout_ms=120000)


class _ExecClient:
    """Fake TD client that records the last request for forwarding tests."""

    def __init__(self) -> None:
        self.last_endpoint: str | None = None
        self.last_body: dict | None = None

    async def request(self, endpoint: str, body: dict | None = None):
        self.last_endpoint = endpoint
        self.last_body = body or {}
        return {"status": "ok"}


def _make_exec_ctx(client):
    """Minimal Context-like object that passes _get_client via monkeypatch."""
    from types import SimpleNamespace

    lifespan_state = {"services": SimpleNamespace(td_client=client)}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


class TestExecPythonForwarding:
    """td_exec_python must forward timeout_ms to the TD-side exec endpoint."""

    @pytest.mark.asyncio
    async def test_forwards_timeout_ms_when_set(self, monkeypatch):
        import td_mcp.tool_registry as registry

        # Permit the exec so we reach the client.request() call.
        monkeypatch.setenv("TD_MCP_EXEC_MODE", "full")

        client = _ExecClient()
        monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

        # Post-Bug-A (v1.5.0 batch 2) signature: ctx first, then explicit args.
        await registry.td_exec_python(
            _make_exec_ctx(client),
            code="pass",
            timeout_ms=7500,
        )
        assert client.last_endpoint == "exec"
        assert client.last_body is not None
        assert client.last_body.get("timeout_ms") == 7500
        assert client.last_body.get("code") == "pass"

    @pytest.mark.asyncio
    async def test_omits_timeout_ms_when_none(self, monkeypatch):
        """When the caller doesn't set timeout_ms the key must not be sent,
        so the TD-side default takes effect."""
        import td_mcp.tool_registry as registry

        monkeypatch.setenv("TD_MCP_EXEC_MODE", "full")

        client = _ExecClient()
        monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

        # Post-Bug-A (v1.5.0 batch 2): omit timeout_ms entirely; default is None.
        await registry.td_exec_python(
            _make_exec_ctx(client),
            code="pass",
        )
        assert client.last_body is not None
        assert "timeout_ms" not in client.last_body
