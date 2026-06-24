import pytest

from td_mcp.macros.engine import MacroEngine


class FakeTDClient:
    def __init__(self):
        self.calls = []

    async def request(self, endpoint, body=None):
        body = body or {}
        self.calls.append((endpoint, body))

        if endpoint == "node/create":
            parent = body.get("parent_path", "/project1").rstrip("/")
            name = body.get("name", "node1")
            return {
                "success": True,
                "node": {
                    "name": name,
                    "path": f"{parent}/{name}",
                    "type": body.get("node_type", "nullTOP"),
                },
            }

        return {"success": True}


@pytest.mark.asyncio
async def test_create_macro_feedback_loop():
    client = FakeTDClient()
    engine = MacroEngine(td_client=client)

    result = await engine.create_macro(
        parent_path="/project1",
        macro_type="feedback_loop",
        name_prefix="demo",
        node_x=100,
        node_y=200,
        overrides={"feedback_opacity": 0.9},
    )

    assert result["success"] is True
    assert result["macro_type"] == "feedback_loop"
    assert len(result["created_nodes"]) >= 4
    assert result["entry_node"].startswith("/project1/demo_")
    assert result["exit_node"].startswith("/project1/demo_")

    created = [call for call in client.calls if call[0] == "node/create"]
    assert created


def test_list_macros_has_defaults():
    engine = MacroEngine(td_client=FakeTDClient())
    summary = engine.list_macros()
    names = {entry["name"] for entry in summary["macros"]}
    assert "feedback_loop" in names
    assert "post_processing" in names


def test_feedback_displacement_macro_uses_feedback_top_reference_not_invalid_input_wiring():
    engine = MacroEngine(td_client=FakeTDClient())
    template = engine._templates["feedback_displacement"]

    connections = {(item.source, item.target, item.source_index, item.target_index) for item in template.connections}
    refs = {(item.node, item.param, item.target_node) for item in template.node_references}

    assert ("feedback", "decay", 0, 0) in connections
    assert ("source", "feedback", 0, 0) not in connections
    assert ("feedback", "top", "out") in refs
    assert template.exit_node == "out"


@pytest.mark.asyncio
async def test_macro_engine_routes_param_writes_through_shared_preflight():
    client = FakeTDClient()
    preflight_calls = []

    class Result:
        adjusted_params = {"opacity": 0.5}
        safety_warnings = ["clamped opacity"]
        param_semantics_warnings = []
        blocked = False

    def preflight(**kwargs):
        preflight_calls.append(kwargs)
        return Result()

    engine = MacroEngine(td_client=client, param_preflight=preflight)

    result = await engine.create_macro(
        parent_path="/project1",
        macro_type="feedback_loop",
        name_prefix="demo",
        param_semantics_policy="block",
    )

    decay_call = next(
        body
        for endpoint, body in client.calls
        if endpoint == "node/params/set" and body["path"].endswith("/demo_decay")
    )
    assert decay_call["params"] == {"opacity": 0.5}
    assert preflight_calls
    assert preflight_calls[0]["path"] == "/project1/demo_decay"
    assert preflight_calls[0]["op_type"] == "levelTOP"
    assert preflight_calls[0]["param_semantics_policy"] == "block"
    assert "clamped opacity" in result["warnings"]


@pytest.mark.asyncio
async def test_macro_engine_block_policy_preflights_before_creating_nodes():
    client = FakeTDClient()
    preflight_calls = []

    class Result:
        adjusted_params = {"opacity": "definitely"}
        safety_warnings = []
        param_semantics_warnings = ["invalid_bool_param"]
        blocked = True

    def preflight(**kwargs):
        preflight_calls.append(kwargs)
        return Result()

    engine = MacroEngine(td_client=client, param_preflight=preflight)

    result = await engine.create_macro(
        parent_path="/project1",
        macro_type="feedback_loop",
        name_prefix="demo",
        param_semantics_policy="block",
    )

    assert result["success"] is False
    assert result["blocked"] is True
    assert result["param_semantics_status"] == "blocked"
    assert preflight_calls
    assert preflight_calls[0]["path"] == "/project1/demo_decay"
    assert preflight_calls[0]["op_type"] == "levelTOP"
    assert not client.calls
