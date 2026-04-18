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


def test_ast_survives_syntax_errors():
    violations = exec_safety.ast_violations("this is not valid python :::")
    assert violations
    assert "syntax error" in violations[0]


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
