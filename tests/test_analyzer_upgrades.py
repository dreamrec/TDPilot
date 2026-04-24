"""Tests for enhanced recipe capture in analyzer."""

import asyncio
from unittest.mock import AsyncMock

from td_mcp.memory.analyzer import analyze_network


def test_recipe_contains_td_build():
    client = AsyncMock()
    client.request = AsyncMock(
        return_value={
            "path": "/project1/noise1",
            "name": "noise1",
            "type": "noiseTOP",
            "family": "TOP",
            "parameters": {"seed": {"value": 1}},
            "inputs": [],
            "nodeX": 100,
            "nodeY": 200,
        }
    )
    result = asyncio.run(analyze_network(client, "/project1/noise1", td_build="2025.32460"))
    assert result["td_build"] == "2025.32460"
    assert "required_op_types" in result
    assert "noiseTOP" in result["required_op_types"]


def test_recipe_contains_layout():
    client = AsyncMock()
    client.request = AsyncMock(
        return_value={
            "path": "/project1/noise1",
            "name": "noise1",
            "type": "noiseTOP",
            "family": "TOP",
            "parameters": {},
            "inputs": [],
            "nodeX": 100,
            "nodeY": 200,
            "color": [1.0, 0.5, 0.0],
            "comment": "test node",
        }
    )
    result = asyncio.run(analyze_network(client, "/project1/noise1"))
    assert result["recipe"] is not None
    layout = result["recipe"].get("layout", {})
    assert len(layout) > 0


def test_required_op_types_sorted():
    client = AsyncMock()
    client.request = AsyncMock(
        return_value={
            "path": "/project1/noise1",
            "name": "noise1",
            "type": "noiseTOP",
            "family": "TOP",
            "parameters": {},
            "inputs": [],
        }
    )
    result = asyncio.run(analyze_network(client, "/project1/noise1"))
    required = result["required_op_types"]
    assert required == sorted(required)


def test_external_assets_detected():
    client = AsyncMock()
    client.request = AsyncMock(
        return_value={
            "path": "/project1/movie1",
            "name": "movie1",
            "type": "moviefileinTOP",
            "family": "TOP",
            "parameters": {"file": {"value": "/path/to/video.mp4"}},
            "inputs": [],
        }
    )
    result = asyncio.run(analyze_network(client, "/project1/movie1"))
    assets = result["recipe"].get("external_assets", [])
    assert "/path/to/video.mp4" in assets


def test_td_build_default_empty():
    client = AsyncMock()
    client.request = AsyncMock(
        return_value={
            "path": "/project1/noise1",
            "name": "noise1",
            "type": "noiseTOP",
            "family": "TOP",
            "parameters": {},
            "inputs": [],
        }
    )
    result = asyncio.run(analyze_network(client, "/project1/noise1"))
    assert result["td_build"] == ""
