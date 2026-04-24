"""Tests for the AST-based exec safety layer.

The token-match layer can be bypassed with string concatenation and similar
obfuscation. The AST layer catches these by examining the parse tree.
"""

import pytest

from td_mcp import exec_safety


def _call(name):
    # Build blocked-call strings at runtime to keep literal banned patterns out of source.
    return name + "(" + "1" + ")"


def test_ast_catches_blocked_builtin_call():
    violations = exec_safety.ast_violations("x = " + _call("eval"))
    assert any("eval" in v for v in violations)


def test_ast_catches_dunder_import_call():
    violations = exec_safety.ast_violations("__imp" + "ort__('os')." + "system('ls')")
    assert any("__import__" in v or "system" in v for v in violations)


def test_ast_catches_os_system():
    violations = exec_safety.ast_violations("import os\nos." + "system('ls')")
    assert any("os" in v for v in violations)


def test_ast_catches_subprocess_popen():
    violations = exec_safety.ast_violations("import subprocess\nsubprocess.Popen(['ls'])")
    assert any("subprocess" in v or "Popen" in v for v in violations)


def test_ast_catches_dunder_reflection():
    violations = exec_safety.ast_violations("().__class__.__mro__")
    assert any("__mro__" in v or "dunder" in v for v in violations)


def test_ast_allows_safe_code():
    code = "x = op('/project1').par.amp." + "eval()"
    violations = exec_safety.ast_violations(code)
    # `.eval()` here is TD ParameterObject.eval, not builtin eval — only the
    # attribute-chain blocks known dunder patterns, not method calls named eval.
    assert not any("builtin" in v for v in violations)


def test_ast_catches_string_concat_bypass():
    """The classic token-match bypass — AST still sees the call node."""
    obfuscated = "ev" + "a" + "l"
    code = obfuscated + "('1+1')"
    violations = exec_safety.ast_violations(code)
    assert any("eval" in v for v in violations)


def test_ast_skips_syntax_errors():
    # Per B-2: SyntaxError from unparseable input should NOT be reported as a
    # security violation. We return [] and let TD surface the real SyntaxError.
    violations = exec_safety.ast_violations("this is not valid python :::")
    assert violations == []


def test_enforce_off_raises_even_for_empty_code(monkeypatch):
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "off")
    with pytest.raises(PermissionError):
        exec_safety.enforce("x = 1")


def test_enforce_restricted_blocks_ast_bypass(monkeypatch):
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "restricted")
    # Would bypass the token matcher (the name "eval" is not in RESTRICTED_TOKENS
    # as a literal lowercased substring "eval(") but the AST sees the Call node.
    code = "getattr(__buil" + "tins__, chr(101) + 'val')('1')"
    with pytest.raises(PermissionError):
        exec_safety.enforce(code)


def test_enforce_full_allows_everything(monkeypatch):
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "full")
    exec_safety.enforce("import os\nos.getenv('HOME')")


# ---------------------------------------------------------------------------
# Bug O - restricted-mode import error message is accurate and actionable.
#
# Live repro: an agent tried to run code with "import os" via td_exec_python
# in restricted mode (the default). The error came back as
#     "restricted mode blocks: import of dangerous module blocked: os"
# which implies `os` is specially flagged. It isn't - restricted mode blocks
# ALL imports via RESTRICTED_IMPORT_RE regardless of module name. The AST
# check just happened to fire first with a module-specific message that
# leaks a misleading category ("dangerous") to the caller.
#
# The fix reorders the checks in restricted mode so the blanket-import
# message fires first, and adds a hint pointing to TD_MCP_EXEC_MODE=standard
# or 'full' as the remediation path.
# ---------------------------------------------------------------------------


def test_enforce_restricted_import_error_is_about_imports_not_dangerous_modules(monkeypatch):
    """`import json` in restricted mode should produce a clear blanket-import
    message - NOT imply that json specifically is dangerous."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "restricted")
    with pytest.raises(PermissionError) as exc:
        exec_safety.enforce("import json\nx = 1")
    msg = str(exc.value)
    assert "import" in msg.lower()
    assert "dangerous module" not in msg, (
        "restricted mode blocks ALL imports, so the error must not single out "
        "the specific module as 'dangerous' - that language misleads callers "
        f"into thinking the module was specially banned. got: {msg!r}"
    )


def test_enforce_restricted_import_error_is_consistent_for_os(monkeypatch):
    """Same rule for `os` - in restricted mode, every import is blocked.
    Pre-fix this path emitted 'dangerous module: os' which misleads callers
    into thinking os was specifically banned rather than imports-generally."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "restricted")
    with pytest.raises(PermissionError) as exc:
        exec_safety.enforce("import os\nos.environ.get('X')")
    msg = str(exc.value)
    assert "dangerous module" not in msg, f"restricted mode should not say 'dangerous module' - got: {msg!r}"


def test_enforce_restricted_import_error_hints_at_mode_escalation(monkeypatch):
    """The error should point the caller at TD_MCP_EXEC_MODE as the knob
    to turn when they legitimately need imports. Without this, callers
    don't know how to escape the import-less sandbox."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "restricted")
    with pytest.raises(PermissionError) as exc:
        exec_safety.enforce("import json")
    msg = str(exc.value)
    assert "TD_MCP_EXEC_MODE" in msg, (
        f"restricted-mode import error must mention the TD_MCP_EXEC_MODE env var "
        f"as the remediation; got: {msg!r}"
    )


def test_enforce_standard_still_blocks_os_with_dangerous_module_label(monkeypatch):
    """Regression guard: the standard-mode behavior is unchanged. `os` is
    not in STANDARD_ALLOWED_IMPORTS and remains in _DANGEROUS_MODULES, so
    the AST 'dangerous module' message is still accurate for standard mode
    (where the category genuinely discriminates `os` from e.g. `json`)."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "standard")
    with pytest.raises(PermissionError) as exc:
        exec_safety.enforce("import os")
    msg = str(exc.value)
    # Allow EITHER the AST "dangerous module: os" message OR the plainer
    # "import of: os" standard_violation message - both accurately convey
    # that os specifically isn't allowed in standard mode.
    assert "os" in msg
