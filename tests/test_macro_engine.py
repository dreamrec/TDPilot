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
