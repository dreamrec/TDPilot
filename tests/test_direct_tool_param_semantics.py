from __future__ import annotations

import asyncio
import json
from typing import Any

import td_mcp.server as server  # noqa: F401
from td_mcp import tool_registry as _tr
from td_mcp.macros import MacroEngine
from td_mcp.memory import SnapshotManager
from td_mcp.models import MacroType
from td_mcp.models.brain import ValidationIssue
from td_mcp.registry import tools_graph, tools_macros, tools_snapshots


def test_td_set_params_attaches_warn_only_param_semantics(monkeypatch, mcp_ctx, td_client):
    def handler(endpoint: str, body: dict[str, Any]):
        if endpoint == "node/detail":
            return {"path": body["path"], "type": "feedback", "family": "TOP"}
        if endpoint == "node/params/set":
            return {"success": True, "results": {}}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    td_client.handler = handler
    monkeypatch.setattr(tools_graph._tr, "_get_client", lambda _ctx: td_client)
    monkeypatch.setattr(tools_graph._tr, "_get_safety_manager", lambda _ctx: None)

    raw = asyncio.run(
        tools_graph.td_set_params(
            mcp_ctx,
            "/project1/fb1",
            {"reset": "yes please", "mystery": 1},
        )
    )

    payload = json.loads(raw)
    warnings = payload["param_semantics_warnings"]
    codes = {item["code"] for item in warnings}
    assert "invalid_bool_param" in codes
    assert "missing_param_semantics" in codes
    assert all(item["severity"] == "warning" for item in warnings)
    assert all(item["source"] == "tdpilot-direct-tool" for item in warnings)
    assert payload["param_semantics_status"] == "warnings"


def test_td_set_params_semantics_unwraps_direct_value_payloads(monkeypatch, mcp_ctx, td_client):
    def handler(endpoint: str, body: dict[str, Any]):
        if endpoint == "node/detail":
            return {"path": body["path"], "type": "level", "family": "TOP"}
        if endpoint == "node/params/set":
            return {"success": True, "results": {}}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    td_client.handler = handler
    monkeypatch.setattr(tools_graph._tr, "_get_client", lambda _ctx: td_client)
    monkeypatch.setattr(tools_graph._tr, "_get_safety_manager", lambda _ctx: None)

    raw = asyncio.run(
        tools_graph.td_set_params(
            mcp_ctx,
            "/project1/level1",
            {
                "opacity": {"val": 2.0},
                "invert": {"reset": True},
            },
        )
    )

    payload = json.loads(raw)
    warnings = payload["param_semantics_warnings"]
    assert [item["code"] for item in warnings] == ["param_out_of_range"]
    assert "outside [0.0, 1.0]" in warnings[0]["message"]


def test_td_set_params_can_block_on_param_semantics_policy(monkeypatch, mcp_ctx, td_client):
    endpoints: list[str] = []

    def handler(endpoint: str, body: dict[str, Any]):
        endpoints.append(endpoint)
        if endpoint == "node/detail":
            return {"path": body["path"], "type": "feedback", "family": "TOP"}
        if endpoint == "node/params/set":
            raise AssertionError("block policy should not mutate params")
        raise AssertionError(f"unexpected endpoint {endpoint}")

    td_client.handler = handler
    monkeypatch.setattr(tools_graph._tr, "_get_client", lambda _ctx: td_client)
    monkeypatch.setattr(tools_graph._tr, "_get_safety_manager", lambda _ctx: None)

    raw = asyncio.run(
        tools_graph.td_set_params(
            mcp_ctx,
            "/project1/fb1",
            {"reset": "yes please"},
            param_semantics_policy="block",
        )
    )

    payload = json.loads(raw)
    assert payload["success"] is False
    assert payload["blocked"] is True
    assert payload["param_semantics_status"] == "blocked"
    assert {item["code"] for item in payload["param_semantics_warnings"]} == {"invalid_bool_param"}
    assert endpoints == ["node/detail"]


def test_td_set_params_keeps_direct_write_working_when_detail_unavailable(monkeypatch, mcp_ctx, td_client):
    def handler(endpoint: str, body: dict[str, Any]):
        if endpoint == "node/detail":
            raise RuntimeError("detail unavailable")
        if endpoint == "node/params/set":
            return {"success": True, "results": {"reset": {"success": True}}}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    td_client.handler = handler
    monkeypatch.setattr(tools_graph._tr, "_get_client", lambda _ctx: td_client)
    monkeypatch.setattr(tools_graph._tr, "_get_safety_manager", lambda _ctx: None)

    raw = asyncio.run(tools_graph.td_set_params(mcp_ctx, "/project1/fb1", {"reset": "yes please"}))

    payload = json.loads(raw)
    assert payload["success"] is True
    assert "param_semantics_warnings" not in payload


def test_shared_direct_param_preflight_blocks_before_mutation():
    result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/fb1",
        params={"reset": "yes please"},
        op_type="feedbackTOP",
        param_semantics_policy="block",
    )

    assert result.blocked is True
    assert result.adjusted_params == {"reset": "yes please"}
    assert {issue.code for issue in result.param_semantics_warnings} == {"invalid_bool_param"}


def test_shared_direct_param_preflight_blocks_unsupported_wave_period_unit():
    result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/wave1",
        params={"periodunit": "beats"},
        op_type="waveCHOP",
        param_semantics_policy="block",
    )

    assert result.blocked is True
    assert result.adjusted_params == {"periodunit": "beats"}
    assert any(
        issue.code == "invalid_enum_param" and "periodunit" in issue.message
        for issue in result.param_semantics_warnings
    )


def test_shared_direct_param_preflight_blocks_unsafe_audio_device_out_params():
    result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/speaker_audio",
        params={
            "active": "yes",
            "driver": "bluetooth",
            "adjustspeed": "sometimes",
            "clampoutput": "loud please",
        },
        op_type="audiodeviceoutCHOP",
        param_semantics_policy="block",
    )

    assert result.blocked is True
    assert result.adjusted_params == {
        "active": "yes",
        "driver": "bluetooth",
        "adjustspeed": "sometimes",
        "clampoutput": "loud please",
    }
    assert {issue.code for issue in result.param_semantics_warnings} == {
        "invalid_bool_param",
        "invalid_enum_param",
    }
    assert all(issue.path == "/project1/speaker_audio" for issue in result.param_semantics_warnings)


def test_shared_direct_param_preflight_blocks_unsafe_audio_file_out_params():
    result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/recorder_audio",
        params={
            "filetype": "telepathy",
            "uniquesuff": "maybe",
            "file": "",
            "bitrate": "fast",
            "record": "now",
            "pause": 2,
        },
        op_type="audiofileoutCHOP",
        param_semantics_policy="block",
    )

    assert result.blocked is True
    assert {
        "invalid_enum_param",
        "invalid_bool_param",
        "empty_path_param",
        "invalid_int_param",
    }.issubset({issue.code for issue in result.param_semantics_warnings})


def test_shared_direct_param_preflight_blocks_valid_high_risk_audio_output_writes():
    result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/recorder_audio",
        params={"record": True},
        op_type="audiofileoutCHOP",
        param_semantics_policy="block",
    )

    assert result.blocked is True
    assert [issue.code for issue in result.param_semantics_warnings] == ["param_semantics_risk"]
    assert "audio-file-recording" in result.param_semantics_warnings[0].message

    speaker_result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/speaker_audio",
        params={"active": True},
        op_type="audiodeviceoutCHOP",
        param_semantics_policy="block",
    )

    assert speaker_result.blocked is True
    assert [issue.code for issue in speaker_result.param_semantics_warnings] == ["param_semantics_risk"]
    assert "live-audio-output" in speaker_result.param_semantics_warnings[0].message


def test_shared_direct_param_preflight_blocks_valid_web_client_request_pulse():
    result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/web_client",
        params={"request": True},
        op_type="webclientDAT",
        param_semantics_policy="block",
    )

    assert result.blocked is True
    assert [issue.code for issue in result.param_semantics_warnings] == ["param_semantics_risk"]
    assert "http-request" in result.param_semantics_warnings[0].message


def test_shared_direct_param_preflight_blocks_valid_web_client_live_network_enables():
    result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/web_client",
        params={"active": True, "stream": True},
        op_type="webclientDAT",
        param_semantics_policy="block",
    )

    messages = "\n".join(issue.message for issue in result.param_semantics_warnings)
    assert result.blocked is True
    assert {issue.code for issue in result.param_semantics_warnings} == {"param_semantics_risk"}
    assert "http-client-active" in messages
    assert "http-streaming-response" in messages


def test_shared_direct_param_preflight_blocks_valid_web_server_start_and_restart():
    start_result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/web_server",
        params={"active": True},
        op_type="webserverDAT",
        param_semantics_policy="block",
    )

    assert start_result.blocked is True
    assert [issue.code for issue in start_result.param_semantics_warnings] == ["param_semantics_risk"]
    assert "web-server-listener" in start_result.param_semantics_warnings[0].message

    restart_result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/web_server",
        params={"restart": True},
        op_type="webserverDAT",
        param_semantics_policy="block",
    )

    assert restart_result.blocked is True
    assert [issue.code for issue in restart_result.param_semantics_warnings] == ["param_semantics_risk"]
    assert "web-server-restart" in restart_result.param_semantics_warnings[0].message


def test_shared_direct_param_preflight_blocks_valid_live_source_activations():
    cases = [
        ("audiodeviceinCHOP", {"active": True}, "live-audio-input"),
        ("videodeviceinTOP", {"active": True}, "live-video-input"),
        ("videodeviceinTOP", {"capture": True}, "live-video-capture"),
        ("kinectazureTOP", {"active": True}, "kinect-azure-sensor-input"),
        ("midiinCHOP", {"source": "device"}, "midi-device-input"),
        ("serialDAT", {"active": True}, "serial-device-listener"),
        ("oscinDAT", {"active": True}, "osc-network-listener"),
        ("websocketDAT", {"active": True}, "websocket-network-client"),
        ("mqttclientDAT", {"active": True}, "mqtt-broker-client"),
        ("udpinDAT", {"active": True}, "udp-network-listener"),
    ]

    for op_type, params, expected_fragment in cases:
        result = _tr._preflight_direct_param_write(
            safety_manager=None,
            path=f"/project1/{op_type.lower()}",
            params=params,
            op_type=op_type,
            param_semantics_policy="block",
        )

        assert result.blocked is True
        assert [issue.code for issue in result.param_semantics_warnings] == ["param_semantics_risk"]
        assert expected_fragment in result.param_semantics_warnings[0].message


def test_shared_direct_param_preflight_blocks_valid_callback_dat_execution_params():
    cases = [
        (
            "datexecuteDAT",
            {
                "active": True,
                "executeloc": "current",
                "tablechange": True,
                "execute": "end",
            },
            [
                "callback-execution-enabled",
                "callback-execute-location",
                "callback-trigger-enabled",
                "callback-execution-timing",
            ],
        ),
        (
            "executeDAT",
            {"active": True, "framestart": True, "writepulse": True},
            ["callback-execution-enabled", "callback-trigger-enabled", "script-file-write"],
        ),
        (
            "mqttclientDAT",
            {"callbacks": "/project1/mqtt_callbacks", "executeloc": "callbacks"},
            ["callback-dat-binding", "callback-execute-location"],
        ),
    ]

    for op_type, params, expected_fragments in cases:
        result = _tr._preflight_direct_param_write(
            safety_manager=None,
            path=f"/project1/{op_type.lower()}",
            params=params,
            op_type=op_type,
            param_semantics_policy="block",
        )

        messages = "\n".join(issue.message for issue in result.param_semantics_warnings)
        assert result.blocked is True
        assert {issue.code for issue in result.param_semantics_warnings} == {"param_semantics_risk"}
        for fragment in expected_fragments:
            assert fragment in messages


def test_shared_direct_param_preflight_blocks_valid_mqtt_credentials_and_tls_writes():
    result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/mqtt",
        params={"username": "user", "password": "secret", "verifycert": False},
        op_type="mqttclientDAT",
        param_semantics_policy="block",
    )

    messages = "\n".join(issue.message for issue in result.param_semantics_warnings)
    assert result.blocked is True
    assert {issue.code for issue in result.param_semantics_warnings} == {"param_semantics_risk"}
    assert "mqtt-credential-username" in messages
    assert "mqtt-credential-secret" in messages
    assert "mqtt-tls-verification-disabled" in messages


def test_shared_direct_param_preflight_blocks_valid_web_credentials_and_tls_writes():
    client_result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/web_client",
        params={
            "username": "user",
            "pw": "secret",
            "appsecret": "app-secret",
            "oauthtoken": "oauth-token",
            "oauthsecret": "oauth-secret",
            "token": "bearer-token",
            "verifycert": False,
        },
        op_type="webclientDAT",
        param_semantics_policy="block",
    )

    client_messages = "\n".join(issue.message for issue in client_result.param_semantics_warnings)
    assert client_result.blocked is True
    assert {issue.code for issue in client_result.param_semantics_warnings} == {"param_semantics_risk"}
    assert "http-credential-username" in client_messages
    assert "http-credential-secret" in client_messages
    assert "http-tls-verification-disabled" in client_messages

    server_result = _tr._preflight_direct_param_write(
        safety_manager=None,
        path="/project1/web_server",
        params={
            "privatekey": "/project1/private_key",
            "certificate": "/project1/certificate",
            "password": "cert-secret",
        },
        op_type="webserverDAT",
        param_semantics_policy="block",
    )

    server_messages = "\n".join(issue.message for issue in server_result.param_semantics_warnings)
    assert server_result.blocked is True
    assert {issue.code for issue in server_result.param_semantics_warnings} == {"param_semantics_risk"}
    assert "web-server-tls-private-key" in server_messages
    assert "web-server-tls-certificate" in server_messages
    assert "web-server-tls-credential-secret" in server_messages


def test_td_set_params_uses_shared_direct_param_preflight(monkeypatch, mcp_ctx, td_client):
    def handler(endpoint: str, body: dict[str, Any]):
        if endpoint == "node/detail":
            return {"path": body["path"], "type": "feedback", "family": "TOP"}
        if endpoint == "node/params/set":
            return {"success": True, "results": {}}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    calls: list[dict[str, Any]] = []

    def fake_preflight(**kwargs):
        calls.append(kwargs)
        return _tr.DirectParamPreflightResult(
            adjusted_params={"reset": False},
            safety_warnings=["clamped-test"],
            param_semantics_warnings=[],
            blocked=False,
        )

    td_client.handler = handler
    monkeypatch.setattr(tools_graph._tr, "_get_client", lambda _ctx: td_client)
    monkeypatch.setattr(tools_graph._tr, "_get_safety_manager", lambda _ctx: None)
    monkeypatch.setattr(tools_graph._tr, "_preflight_direct_param_write", fake_preflight)

    raw = asyncio.run(
        tools_graph.td_set_params(
            mcp_ctx,
            "/project1/fb1",
            {"reset": "yes please"},
            param_semantics_policy="block",
        )
    )

    payload = json.loads(raw)
    assert payload["success"] is True
    assert payload["safety_warnings"] == ["clamped-test"]
    assert calls
    assert calls[0]["path"] == "/project1/fb1"
    assert calls[0]["op_type"] == "feedbackTOP"
    assert calls[0]["param_semantics_policy"] == "block"
    assert any(
        endpoint == "node/params/set" and body["params"] == {"reset": False}
        for endpoint, body in td_client.calls
    )


def test_td_restore_snapshot_can_block_on_param_semantics_policy(
    monkeypatch,
    mcp_ctx,
    service_container,
    td_client,
):
    snapshot_manager = SnapshotManager()
    saved = snapshot_manager.add_snapshot(
        {
            "root_path": "/project1",
            "nodes": {
                "/project1/fb1": {
                    "type": "feedback",
                    "family": "TOP",
                    "params": {"reset": {"value": "yes please"}},
                }
            },
            "connections": [],
        },
        name="unsafe-feedback-reset",
    )
    service_container.snapshot_manager = snapshot_manager

    def handler(endpoint: str, body: dict[str, Any]):
        if endpoint == "node/params/set":
            raise AssertionError("block policy should not restore unsafe params")
        raise AssertionError(f"unexpected endpoint {endpoint}")

    td_client.handler = handler
    monkeypatch.setattr(tools_snapshots._tr, "_get_client", lambda _ctx: td_client)
    monkeypatch.setattr(tools_snapshots._tr, "_get_safety_manager", lambda _ctx: None)

    raw = asyncio.run(
        tools_snapshots.td_restore_snapshot(
            mcp_ctx,
            saved["snapshot_id"],
            param_semantics_policy="block",
        )
    )

    payload = json.loads(raw)
    assert payload["success"] is False
    assert payload["blocked"] is True
    assert payload["param_semantics_status"] == "blocked"
    assert {item["code"] for item in payload["param_semantics_warnings"]} == {"invalid_bool_param"}
    assert not any(endpoint == "node/params/set" for endpoint, _body in td_client.calls)


def test_optimizer_apply_plan_can_block_through_shared_direct_param_preflight(
    monkeypatch,
    td_client,
):
    calls: list[dict[str, Any]] = []

    def fake_preflight(**kwargs):
        calls.append(kwargs)
        return _tr.DirectParamPreflightResult(
            adjusted_params=kwargs["params"],
            safety_warnings=[],
            param_semantics_warnings=[
                ValidationIssue(
                    severity="warning",
                    code="invalid_bool_param",
                    message="reset must be a boolean",
                    path=kwargs["path"],
                    source="tdpilot-direct-tool",
                )
            ],
            blocked=True,
        )

    td_client.responses = {"node/params/set": {"success": True}}
    monkeypatch.setattr(_tr, "_preflight_direct_param_write", fake_preflight)

    result = asyncio.run(
        _tr._apply_optimizer_plan(
            td_client,
            None,
            [
                {
                    "path": "/project1/fb1",
                    "param": "reset",
                    "current": 0.0,
                    "proposed": 1.0,
                    "direction": 1,
                    "step": 1.0,
                }
            ],
            op_types_by_path={"/project1/fb1": "feedbackTOP"},
            param_semantics_policy="block",
        )
    )

    assert result["blocked"] is True
    assert result["applied"] == []
    assert result["failed"] == [
        {
            "path": "/project1/fb1",
            "param": "reset",
            "error": "param semantics blocked optimizer params for /project1/fb1",
        }
    ]
    assert {item["code"] for item in result["param_semantics_warnings"]} == {"invalid_bool_param"}
    assert calls
    assert calls[0]["op_type"] == "feedbackTOP"
    assert calls[0]["param_semantics_policy"] == "block"
    assert not any(endpoint == "node/params/set" for endpoint, _body in td_client.calls)


def test_td_create_macro_surfaces_blocked_preflight_without_mutating(
    mcp_ctx,
    service_container,
    td_client,
):
    class Result:
        adjusted_params = {"opacity": "unsafe"}
        safety_warnings = []
        param_semantics_warnings = [
            ValidationIssue(
                severity="warning",
                code="invalid_bool_param",
                message="opacity is invalid",
                path="/project1/demo_decay",
                source="tdpilot-direct-tool",
            )
        ]
        blocked = True

    service_container.macro_engine = MacroEngine(
        td_client=td_client,
        param_preflight=lambda **_kwargs: Result(),
    )

    raw = asyncio.run(
        tools_macros.td_create_macro(
            mcp_ctx,
            MacroType.FEEDBACK_LOOP,
            name="demo",
            param_semantics_policy="block",
        )
    )

    payload = json.loads(raw)
    assert payload["success"] is False
    assert payload["blocked"] is True
    assert payload["param_semantics_status"] == "blocked"
    assert {item[0] for item in td_client.calls} == set()
