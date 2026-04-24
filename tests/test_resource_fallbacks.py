"""Tests for resource handler mode fields, read-through fallbacks,
and EventManager tuple-key subscriptions.

The AST-based registration tests below (kept as invariants) are complemented
by behavioral tests further down that actually call each of the seven
resource handlers and assert the returned payload contract.

Why behavioral + AST (not just behavioral): AST tests pin the *registration*
invariant (all seven URIs are still decorated with @mcp.resource), which a
behavioral test can't observe once the handler exists. The behavioral tests
pin the *payload contract* — the actual dict shape callers depend on.
"""

import ast

import pytest

from td_mcp.events.event_manager import EventManager
from td_mcp.tool_registry import (
    td_resource_chop_channel,
    td_resource_cook,
    td_resource_error,
    td_resource_job,
    td_resource_parameter,
    td_resource_timeline,
    td_resource_top_frame,
)

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


def _merged_source() -> str:
    """Return merged text of tool_registry.py + registry/*.py submodules.

    v1.5.0 Phase 2 module split: resources moved to
    ``src/td_mcp/registry/resources.py``. Tests that do AST-level
    decorator discovery or ``ast.get_source_segment`` lookups need the
    merged source text so node line-numbers from the AST index into
    the same string.
    """
    import pathlib

    src_root = pathlib.Path(__file__).resolve().parent.parent / "src" / "td_mcp"
    main_src = (src_root / "tool_registry.py").read_text()
    pkg_dir = src_root / "registry"
    extra_srcs: list[str] = []
    if pkg_dir.is_dir():
        for sub in sorted(pkg_dir.glob("*.py")):
            if sub.name == "__init__.py":
                continue
            extra_srcs.append(sub.read_text())
    return main_src + "\n" + "\n".join(extra_srcs)


def _get_tool_registry_ast():
    """Parse merged tool_registry.py + registry/*.py as a single AST.

    The AST's node line-numbers index into the string returned by
    ``_merged_source()``, so helpers using ``ast.get_source_segment``
    must pass the same string.
    """
    return ast.parse(_merged_source(), filename="<merged tool_registry + registry/*.py>")


def _find_decorated_functions(tree: ast.Module, decorator_substring: str) -> dict:
    """Return {name_kwarg_or_func_name: func_name} for functions decorated with a call
    containing decorator_substring."""
    results = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                func = dec.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == decorator_substring
                    or isinstance(func, ast.Name)
                    and func.id == decorator_substring
                ):
                    pass
                else:
                    continue
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
    source = _merged_source()
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
    source = _merged_source()
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
# Behavioral resource-handler tests (v1.4.4 reliability release)
# The handlers are intentionally static-mode: mcp>=1.3 removed context
# injection for parameter-less resources, so the handlers pin a known
# fallback contract (URI shape, mode=static, a note pointing at the tool).
# These tests call each handler and assert that contract, replacing the
# AST-only "has 'mode' substring" check from earlier releases.
# ---------------------------------------------------------------------------


def _assert_static_contract(payload: dict, expected_uri: str, tool_hint: str) -> None:
    """Every resource handler returns a dict with this invariant."""
    assert isinstance(payload, dict), f"handler returned {type(payload)!r}, expected dict"
    assert payload.get("resource_schema_version") == 1
    assert payload.get("resource_uri") == expected_uri
    assert payload.get("mode") == "static"
    note = payload.get("note", "")
    assert tool_hint in note, f"note does not mention the suggested tool {tool_hint!r}; got: {note!r}"


@pytest.mark.asyncio
async def test_resource_timeline_state_payload():
    payload = await td_resource_timeline()
    _assert_static_contract(payload, expected_uri="td://timeline/state", tool_hint="td_get_timescale_state")


@pytest.mark.asyncio
async def test_resource_chop_channel_payload_roundtrips_params():
    payload = await td_resource_chop_channel(encoded_path="_project1_audio1", channel="chan1")
    assert "td://chop/path/" in payload["resource_uri"]
    assert "/channel/chan1" in payload["resource_uri"]
    _assert_static_contract(payload, expected_uri=payload["resource_uri"], tool_hint="td_chop_data")
    assert payload.get("channel") == "chan1"
    # Decoded path is what the handler exposes back to callers.
    assert payload.get("path")
    assert payload.get("available") is False


@pytest.mark.asyncio
async def test_resource_parameter_payload_roundtrips_params():
    payload = await td_resource_parameter(encoded_path="_project1_noise1", name="amp")
    assert "td://par/path/" in payload["resource_uri"]
    assert "/name/amp" in payload["resource_uri"]
    _assert_static_contract(payload, expected_uri=payload["resource_uri"], tool_hint="td_get_params")
    assert payload.get("name") == "amp"
    assert payload.get("path")
    assert payload.get("available") is False


@pytest.mark.asyncio
async def test_resource_cook_state_payload():
    payload = await td_resource_cook(encoded_path="_project1_null1")
    assert "td://cook/path/" in payload["resource_uri"]
    _assert_static_contract(payload, expected_uri=payload["resource_uri"], tool_hint="td_cooking_info")
    assert payload.get("path")
    assert payload.get("available") is False


@pytest.mark.asyncio
async def test_resource_error_state_payload():
    payload = await td_resource_error(encoded_path="_project1_render1")
    assert "td://error/path/" in payload["resource_uri"]
    _assert_static_contract(payload, expected_uri=payload["resource_uri"], tool_hint="td_get_errors")
    assert payload.get("path")
    assert payload.get("available") is False


@pytest.mark.asyncio
async def test_resource_top_frame_payload():
    payload = await td_resource_top_frame(encoded_path="_project1_render1")
    assert "td://top/path/" in payload["resource_uri"]
    assert payload["resource_uri"].endswith("/frame")
    _assert_static_contract(payload, expected_uri=payload["resource_uri"], tool_hint="td_screenshot")
    assert payload.get("path")
    assert payload.get("available") is False


@pytest.mark.asyncio
async def test_resource_job_state_payload():
    payload = await td_resource_job(job_id="abc123")
    assert payload["resource_uri"] == "td://job/abc123"
    _assert_static_contract(payload, expected_uri="td://job/abc123", tool_hint="job tracking")
    assert payload.get("job_id") == "abc123"
    assert payload.get("available") is False


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
