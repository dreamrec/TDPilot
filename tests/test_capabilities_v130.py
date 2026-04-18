"""Tests for expanded CapabilitySet (v1.3.0 — 10 fields)."""

from __future__ import annotations

from td_mcp.capabilities import CapabilitySet, detect_capabilities


class TestCapabilitySetFields:
    """CapabilitySet has the 5 new fields with correct defaults."""

    def test_has_supports_tasks(self):
        cs = CapabilitySet()
        assert cs.supports_tasks is False

    def test_has_supports_elicitation(self):
        cs = CapabilitySet()
        assert cs.supports_elicitation is False

    def test_has_transport_type(self):
        cs = CapabilitySet()
        assert cs.transport_type == "stdio"

    def test_has_mcp_sdk_version(self):
        cs = CapabilitySet()
        assert cs.mcp_sdk_version == ""

    def test_has_td_build(self):
        cs = CapabilitySet()
        assert cs.td_build == ""

    def test_all_10_fields_present(self):
        cs = CapabilitySet()
        d = cs.to_dict()
        expected_keys = {
            "supports_resources",
            "supports_subscriptions",
            "supports_sampling",
            "supports_sampling_tool_calls",
            "supports_streamable_http",
            "supports_tasks",
            "supports_elicitation",
            "transport_type",
            "mcp_sdk_version",
            "td_build",
        }
        assert set(d.keys()) == expected_keys

    def test_constructor_with_new_fields(self):
        cs = CapabilitySet(
            supports_tasks=True,
            supports_elicitation=True,
            transport_type="streamable-http",
            mcp_sdk_version="1.8.0",
            td_build="2024.12345",
        )
        assert cs.supports_tasks is True
        assert cs.supports_elicitation is True
        assert cs.transport_type == "streamable-http"
        assert cs.mcp_sdk_version == "1.8.0"
        assert cs.td_build == "2024.12345"


class TestToDictReturnType:
    """to_dict() returns dict[str, Any] including non-bool values."""

    def test_returns_dict_str_any(self):
        cs = CapabilitySet(transport_type="sse", mcp_sdk_version="1.5.0")
        d = cs.to_dict()
        assert isinstance(d, dict)
        # Contains string values, not just bools
        assert isinstance(d["transport_type"], str)
        assert isinstance(d["mcp_sdk_version"], str)


class TestDetectCapabilities:
    """detect_capabilities() populates transport_type and mcp_sdk_version."""

    def test_transport_type_stdio(self, monkeypatch):
        monkeypatch.setenv("TD_MCP_TRANSPORT", "stdio")
        cs = detect_capabilities()
        assert cs.transport_type == "stdio"

    def test_transport_type_streamable_http(self, monkeypatch):
        monkeypatch.setenv("TD_MCP_TRANSPORT", "streamable_http")
        cs = detect_capabilities()
        assert cs.transport_type == "streamable-http"

    def test_mcp_sdk_version_populated(self):
        cs = detect_capabilities()
        # Should be a non-empty string if mcp package is installed,
        # or empty string if not — either way it should not raise.
        assert isinstance(cs.mcp_sdk_version, str)

    def test_td_build_passed_through(self, monkeypatch):
        monkeypatch.setenv("TD_MCP_TRANSPORT", "stdio")
        cs = detect_capabilities(td_build="2024.99999")
        assert cs.td_build == "2024.99999"

    def test_td_build_default_empty(self):
        cs = detect_capabilities()
        assert cs.td_build == ""
