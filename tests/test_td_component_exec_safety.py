"""Tests for TD-side standard exec mode in mcp_webserver_callbacks.py.

Since the callbacks file depends on TouchDesigner runtime globals (op, me, etc.)
we cannot import it directly.  Instead we parse the source file and verify the
expected constants, functions, and control-flow structures are present.
"""

import pathlib
import re
import textwrap

import pytest

# ---------------------------------------------------------------------------
# Locate the source file
# ---------------------------------------------------------------------------

_CB_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / 'td_component' / 'mcp_webserver_callbacks.py'
)
_SOURCE = _CB_PATH.read_text()


# ---------------------------------------------------------------------------
# Structural tests — constants exist and have correct values
# ---------------------------------------------------------------------------

class TestStandardModeConstants:
    """Verify STANDARD_ALLOWED_IMPORTS and STANDARD_BLOCKED_TOKENS are defined."""

    def test_standard_allowed_imports_defined(self):
        assert 'STANDARD_ALLOWED_IMPORTS' in _SOURCE

    def test_standard_allowed_imports_has_14_modules(self):
        expected = {
            'json', 'math', 're', 'datetime', 'collections',
            'itertools', 'functools', 'copy', 'textwrap',
            'string', 'random', 'decimal', 'fractions', 'statistics',
        }
        for mod in expected:
            assert "'{}'".format(mod) in _SOURCE or '"{}"'.format(mod) in _SOURCE, (
                'STANDARD_ALLOWED_IMPORTS missing module: {}'.format(mod)
            )

    def test_standard_blocked_tokens_defined(self):
        assert 'STANDARD_BLOCKED_TOKENS' in _SOURCE

    def test_standard_blocked_tokens_superset_of_restricted(self):
        """Standard tokens should include all restricted tokens plus extras."""
        extras = ['setattr', 'delattr', '__subclasses__', '__bases__',
                  'globals(', 'locals(']
        for token in extras:
            assert "'{}'".format(token) in _SOURCE or '"{}"'.format(token) in _SOURCE, (
                'STANDARD_BLOCKED_TOKENS missing token: {}'.format(token)
            )


# ---------------------------------------------------------------------------
# Structural tests — functions and mode handling
# ---------------------------------------------------------------------------

class TestStandardModeFunctions:
    """Verify _standard_exec_violation function exists."""

    def test_standard_exec_violation_defined(self):
        assert 'def _standard_exec_violation(code)' in _SOURCE

    def test_standard_exec_violation_checks_blocked_tokens(self):
        assert 'STANDARD_BLOCKED_TOKENS' in _SOURCE
        # The function should iterate over STANDARD_BLOCKED_TOKENS
        pattern = r'for\s+\w+\s+in\s+STANDARD_BLOCKED_TOKENS'
        assert re.search(pattern, _SOURCE), (
            '_standard_exec_violation should iterate STANDARD_BLOCKED_TOKENS'
        )

    def test_standard_exec_violation_checks_imports(self):
        # Should check imports against STANDARD_ALLOWED_IMPORTS
        pattern = r'STANDARD_ALLOWED_IMPORTS'
        after_func = _SOURCE[_SOURCE.index('def _standard_exec_violation'):]
        assert pattern in after_func


class TestDefaultExecModeValidation:
    """Verify the DEFAULT_EXEC_MODE validation includes 'standard'."""

    def test_standard_in_valid_modes(self):
        # The validation line should include 'standard'
        pattern = r"if\s+DEFAULT_EXEC_MODE\s+not\s+in\s+\(.*'standard'.*\)"
        assert re.search(pattern, _SOURCE), (
            "DEFAULT_EXEC_MODE validation must include 'standard'"
        )


class TestHandleExecPythonStandard:
    """Verify handle_exec_python routes standard mode correctly."""

    def test_handle_exec_python_accepts_standard(self):
        # The exec_mode validation inside handle_exec_python should include standard
        func_source = _SOURCE[_SOURCE.index('def handle_exec_python'):]
        # Accepts either inline tuple or dict-based validation (_MODE_RANK includes 'standard')
        pattern_tuple = r"if\s+exec_mode\s+not\s+in\s+\(.*'standard'.*\)"
        pattern_dict = r"_MODE_RANK\s*=\s*\{.*'standard'.*\}"
        assert re.search(pattern_tuple, func_source) or re.search(pattern_dict, func_source), (
            "handle_exec_python must accept 'standard' as a valid exec_mode"
        )

    def test_handle_exec_python_calls_standard_violation(self):
        func_source = _SOURCE[_SOURCE.index('def handle_exec_python'):]
        assert '_standard_exec_violation' in func_source, (
            'handle_exec_python must call _standard_exec_violation for standard mode'
        )


class TestBuildExecGlobalsStandard:
    """Verify _build_exec_globals pre-imports whitelisted modules for standard mode."""

    def test_build_exec_globals_handles_standard(self):
        func_source = _SOURCE[_SOURCE.index('def _build_exec_globals'):]
        # Should check for 'standard' mode
        assert "'standard'" in func_source or '"standard"' in func_source, (
            '_build_exec_globals must handle standard mode'
        )

    def test_build_exec_globals_imports_allowed_modules(self):
        func_source = _SOURCE[_SOURCE.index('def _build_exec_globals'):]
        # Should reference STANDARD_ALLOWED_IMPORTS
        assert 'STANDARD_ALLOWED_IMPORTS' in func_source, (
            '_build_exec_globals must use STANDARD_ALLOWED_IMPORTS'
        )


class TestNoFStrings:
    """Verify the callbacks file avoids f-strings for TD Python compatibility."""

    def test_standard_violation_uses_format(self):
        # Find the _standard_exec_violation function body
        start = _SOURCE.index('def _standard_exec_violation')
        # Find the next def
        next_def = _SOURCE.index('\ndef ', start + 1)
        func_body = _SOURCE[start:next_def]
        # Should not contain f-strings
        assert "f'" not in func_body and 'f"' not in func_body, (
            '_standard_exec_violation should use .format() not f-strings'
        )
