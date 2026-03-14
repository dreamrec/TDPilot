"""TDPilot knowledge corpus — structured JSON cards for TD operators, palette, releases."""

from td_mcp.knowledge.card_index import CardIndex  # noqa: F401

try:
    from td_mcp.knowledge.docsbrain import DocsBrain  # noqa: F401
except ImportError:
    DocsBrain = None  # type: ignore[assignment,misc]
