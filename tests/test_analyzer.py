"""Tests for network analyzer — technique extraction from mock TD networks."""

import pytest

from td_mcp.memory.analyzer import analyze_network


class MockClient:
    """Fake TDClient that returns pre-configured node data."""

    def __init__(self, nodes):
        self._nodes = nodes  # dict of path -> detail dict

    async def request(self, endpoint, params=None):
        params = params or {}
        if endpoint == "node/detail":
            path = params.get("path", "")
            return self._nodes.get(path, {"error": "not found"})
        elif endpoint == "nodes":
            parent = params.get("path", "")
            children = [
                {"path": p}
                for p in self._nodes
                if p.startswith(parent + "/") and "/" not in p[len(parent) + 1 :]
            ]
            offset = params.get("offset", 0)
            limit = params.get("limit", 200)
            return {"nodes": children[offset : offset + limit]}
        return {}


def _make_node(path, name, op_type, family, params=None, inputs=None, is_comp=False):
    return {
        "path": path,
        "name": name,
        "type": op_type,
        "family": family,
        "parameters": params or {},
        "inputs": inputs or [],
        "isCOMP": is_comp,
    }


@pytest.fixture
def small_network():
    """5-node feedback network."""
    nodes = {
        "/project1/feedback": _make_node(
            "/project1/feedback", "feedback", "containerCOMP", "COMP", is_comp=True
        ),
        "/project1/feedback/noise1": _make_node(
            "/project1/feedback/noise1",
            "noise1",
            "noiseTOP",
            "TOP",
            params={"seed": {"value": 42}, "rate": {"value": 0.5}},
        ),
        "/project1/feedback/feedback1": _make_node(
            "/project1/feedback/feedback1",
            "feedback1",
            "feedbackTOP",
            "TOP",
            inputs=[{"from": "/project1/feedback/noise1", "from_index": 0, "to_index": 0}],
        ),
        "/project1/feedback/comp1": _make_node(
            "/project1/feedback/comp1",
            "comp1",
            "compositeTOP",
            "TOP",
            inputs=[{"from": "/project1/feedback/feedback1", "from_index": 0, "to_index": 0}],
        ),
        "/project1/feedback/out1": _make_node(
            "/project1/feedback/out1",
            "out1",
            "outTOP",
            "TOP",
            inputs=[{"from": "/project1/feedback/comp1", "from_index": 0, "to_index": 0}],
        ),
    }
    return MockClient(nodes)


@pytest.mark.asyncio
async def test_small_network_full_recipe(small_network):
    result = await analyze_network(small_network, "/project1/feedback", name="test feedback")
    assert result["complexity"] == "small"
    assert result["node_count"] == 5
    assert result["connection_count"] == 3
    assert result["recipe"] is not None
    assert len(result["recipe"]["nodes"]) > 0
    assert result["name"] == "test feedback"


@pytest.mark.asyncio
async def test_small_network_relative_paths(small_network):
    result = await analyze_network(small_network, "/project1/feedback")
    recipe = result["recipe"]
    # All paths in recipe should be relative
    for path in recipe["nodes"]:
        assert not path.startswith("/project1/feedback")


@pytest.mark.asyncio
async def test_large_network_no_recipe():
    """Networks >20 nodes should get summary only, no full recipe."""
    nodes = {
        "/root": _make_node("/root", "root", "containerCOMP", "COMP", is_comp=True),
    }
    for i in range(25):
        nodes[f"/root/node{i}"] = _make_node(
            f"/root/node{i}",
            f"node{i}",
            "noiseTOP",
            "TOP",
            params={"seed": {"value": i}, "rate": {"value": 0.1 * i}},
        )
    client = MockClient(nodes)
    result = await analyze_network(client, "/root")
    assert result["complexity"] == "large"
    assert result["recipe"] is None
    assert result["key_params"] is not None
    assert len(result["key_params"]) > 0


@pytest.mark.asyncio
async def test_medium_network_has_recipe():
    """Networks 10-20 nodes should get full recipe."""
    nodes = {
        "/root": _make_node("/root", "root", "containerCOMP", "COMP", is_comp=True),
    }
    for i in range(14):
        nodes[f"/root/n{i}"] = _make_node(f"/root/n{i}", f"n{i}", "noiseTOP", "TOP")
    client = MockClient(nodes)
    result = await analyze_network(client, "/root")
    assert result["complexity"] == "medium"
    assert result["recipe"] is not None


@pytest.mark.asyncio
async def test_families_and_op_types(small_network):
    result = await analyze_network(small_network, "/project1/feedback")
    assert "TOP" in result["families"]
    assert result["families"]["TOP"] >= 3


@pytest.mark.asyncio
async def test_expressions_extracted():
    """Expressions in params should be captured in the recipe."""
    nodes = {
        "/root": _make_node("/root", "root", "containerCOMP", "COMP", is_comp=True),
        "/root/noise": _make_node(
            "/root/noise",
            "noise",
            "noiseTOP",
            "TOP",
            params={
                "seed": {"value": 42, "expression": "absTime.frame % 100"},
                "rate": {"value": 0.5},
            },
        ),
    }
    client = MockClient(nodes)
    result = await analyze_network(client, "/root")
    recipe = result["recipe"]
    noise_node = recipe["nodes"].get("/noise")
    assert noise_node is not None
    assert "expressions" in noise_node
    assert noise_node["expressions"]["seed"] == "absTime.frame % 100"
