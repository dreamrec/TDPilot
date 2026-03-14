"""Tests for resource handler mode fields, read-through fallbacks,
and EventManager tuple-key subscriptions."""

import ast
import pytest

from td_mcp.events.event_manager import EventManager


# ---------------------------------------------------------------------------
# Helper: FakeMCPServer
# ---------------------------------------------------------------------------


class FakeMCPServer:
    """Minimal stand-in for the MCP server object used by EventManager."""

    def __init__(self):
        self.updated: list = []

    async def notify_resource_updated(self, uri: str):
        self.updated.append(uri)


# ---------------------------------------------------------------------------
# Structural / registration tests (source-level AST inspection)
# ---------------------------------------------------------------------------


def _get_tool_registry_ast():
    """Parse tool_registry.py as AST to inspect structure without importing."""
    import pathlib

    path = pathlib.Path(__file__).resolve().parent.parent / "src" / "td_mcp" / "tool_registry.py"
    return ast.parse(path.read_text(), filename=str(path))


def _find_decorated_functions(tree: ast.Module, decorator_substring: str) -> dict:
    """Return {name_kwarg_or_func_name: func_name} for functions decorated with a call
    containing decorator_substring."""
    results = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                # Check decorator function attribute or name
                dec_src = ast.dump(dec)
                if decorator_substring in dec_src:
                    # Extract name= keyword if present
                    for kw in dec.keywords:
                        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                            results[kw.value.value] = node.name
                            break
                    else:
                        results[node.name] = node.name
    return results


def test_all_resource_names_registered():
    """All 7 resource templates should be decorated with @mcp.resource."""
    tree = _get_tool_registry_ast()
    resources = _find_decorated_functions(tree, "resource")

    expected = {
        "td_timeline_state",
        "td_chop_channel",
        "td_parameter",
        "td_cook_state",
        "td_error_state",
        "td_top_frame",
        "td_job_state",
    }
    for name in expected:
        assert name in resources, f"Resource '{name}' not found in @mcp.resource decorators"


def test_resource_handler_signatures():
    """Resource handler functions should have the expected parameter names."""
    tree = _get_tool_registry_ast()
    resources = _find_decorated_functions(tree, "resource")

    # Map resource name -> expected params (excluding ctx)
    expected_params = {
        "td_timeline_state": [],
        "td_chop_channel": ["encoded_path", "channel"],
        "td_parameter": ["encoded_path", "name"],
        "td_cook_state": ["encoded_path"],
        "td_error_state": ["encoded_path"],
        "td_top_frame": ["encoded_path"],
        "td_job_state": ["job_id"],
    }

    for res_name, func_name in resources.items():
        if res_name not in expected_params:
            continue
        # Find the function node
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                param_names = [a.arg for a in node.args.args if a.arg != "ctx"]
                assert param_names == expected_params[res_name], (
                    f"Resource '{res_name}' handler '{func_name}' has params {param_names}, "
                    f"expected {expected_params[res_name]}"
                )
                break


def test_resource_handlers_include_mode_field():
    """Every resource handler return dict should include a 'mode' key."""
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parent.parent / "src" / "td_mcp" / "tool_registry.py"
    ).read_text()

    tree = _get_tool_registry_ast()
    resources = _find_decorated_functions(tree, "resource")

    for res_name, func_name in resources.items():
        # Find function source range and check "mode" appears in it
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                func_source = ast.get_source_segment(source, node)
                assert func_source is not None, f"Could not extract source for {func_name}"
                assert '"mode"' in func_source or "'mode'" in func_source, (
                    f"Resource handler '{func_name}' (name='{res_name}') missing 'mode' field in response"
                )
                break


def test_cache_resources_have_fallback_try_except():
    """Cache-mode resources with fallbacks (chop, par, cook, error) should have try/except blocks."""
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parent.parent / "src" / "td_mcp" / "tool_registry.py"
    ).read_text()

    tree = _get_tool_registry_ast()
    resources = _find_decorated_functions(tree, "resource")

    fallback_resources = {"td_chop_channel", "td_parameter", "td_cook_state", "td_error_state"}

    for res_name in fallback_resources:
        func_name = resources[res_name]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                func_source = ast.get_source_segment(source, node)
                assert "try:" in func_source, (
                    f"Resource handler '{func_name}' missing try block for read-through fallback"
                )
                assert "except" in func_source, (
                    f"Resource handler '{func_name}' missing except block for read-through fallback"
                )
                break


# ---------------------------------------------------------------------------
# EventManager subscription key tests (tuple keys)
# ---------------------------------------------------------------------------


def test_subscription_tuple_key_register_and_get():
    """register_subscription should use (path, event_type) tuple keys."""
    mgr = EventManager(mcp_server=FakeMCPServer(), port=19982)
    mgr.register_subscription("/project1/audio1", "chop_change", {"interval": 0.1})
    mgr.register_subscription("/project1/audio1", "par_change", {"interval": 0.5})

    # Both subscriptions should coexist
    assert mgr.get_subscription("/project1/audio1", "chop_change") == {"interval": 0.1}
    assert mgr.get_subscription("/project1/audio1", "par_change") == {"interval": 0.5}


def test_subscription_tuple_key_unregister():
    """unregister_subscription with tuple keys removes only the matching pair."""
    mgr = EventManager(mcp_server=FakeMCPServer(), port=19982)
    mgr.register_subscription("/project1/audio1", "chop_change", {"interval": 0.1})
    mgr.register_subscription("/project1/audio1", "par_change", {"interval": 0.5})

    assert mgr.unregister_subscription("/project1/audio1", "chop_change") is True
    assert mgr.get_subscription("/project1/audio1", "chop_change") is None
    # The other subscription should still exist
    assert mgr.get_subscription("/project1/audio1", "par_change") == {"interval": 0.5}


def test_subscription_list_returns_tuple_keys():
    """list_subscriptions should return dict with tuple keys."""
    mgr = EventManager(mcp_server=FakeMCPServer(), port=19982)
    mgr.register_subscription("/a", "chop_change", {"x": 1})
    mgr.register_subscription("/b", "par_change", {"x": 2})

    subs = mgr.list_subscriptions()
    assert ("/a", "chop_change") in subs
    assert ("/b", "par_change") in subs
    assert len(subs) == 2


def test_unregister_all_for_path():
    """unregister_all_for_path removes all event types for a given path."""
    mgr = EventManager(mcp_server=FakeMCPServer(), port=19982)
    mgr.register_subscription("/project1/audio1", "chop_change", {"interval": 0.1})
    mgr.register_subscription("/project1/audio1", "par_change", {"interval": 0.5})
    mgr.register_subscription("/other/path", "chop_change", {"interval": 1.0})

    removed = mgr.unregister_all_for_path("/project1/audio1")
    assert removed == 2
    assert len(mgr.list_subscriptions()) == 1
    assert mgr.get_subscription("/other/path", "chop_change") == {"interval": 1.0}
