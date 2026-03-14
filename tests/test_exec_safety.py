"""Tests for exec-safety modes, focusing on the new ``standard`` tier."""

import importlib
import re
import sys
import types
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helper: load only the exec-safety helpers from tool_registry without
# triggering the MCP decorator registrations that fail outside a server.
# ---------------------------------------------------------------------------

def _load_exec_helpers():
    """Return a namespace dict with the exec-safety helpers."""
    import ast
    import textwrap
    src_path = (
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "src" / "td_mcp" / "tool_registry.py"
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
    @pytest.mark.parametrize("mod", [
        "json", "math", "re", "datetime", "collections",
        "itertools", "functools", "copy", "textwrap",
        "string", "random", "decimal", "fractions", "statistics",
    ])
    def test_allows_whitelisted_import(self, mod):
        assert self.fn(f"import {mod}") is None

    @pytest.mark.parametrize("mod", [
        "json", "math", "re", "datetime", "collections",
        "itertools", "functools", "copy", "textwrap",
        "string", "random", "decimal", "fractions", "statistics",
    ])
    def test_allows_whitelisted_from_import(self, mod):
        assert self.fn(f"from {mod} import something") is None

    # -- blocked imports --
    @pytest.mark.parametrize("mod", [
        "os", "sys", "subprocess", "socket", "importlib", "pathlib", "shutil",
    ])
    def test_blocks_dangerous_import(self, mod):
        result = self.fn(f"import {mod}")
        assert result is not None

    @pytest.mark.parametrize("mod", [
        "os", "sys", "subprocess", "socket", "importlib", "pathlib", "shutil",
    ])
    def test_blocks_dangerous_from_import(self, mod):
        result = self.fn(f"from {mod} import something")
        assert result is not None

    # -- blocked builtins / tokens --
    @pytest.mark.parametrize("snippet", [
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
    ])
    def test_blocks_dangerous_builtins(self, snippet):
        result = self.fn(snippet)
        assert result is not None

    # -- allowed read-only introspection --
    @pytest.mark.parametrize("snippet", [
        "dir(obj)",
        "type(obj)",
        "isinstance(obj, int)",
        "hasattr(obj, 'x')",
        "getattr(obj, 'x')",
    ])
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
