"""Tool-registry submodules for TDPilot MCP.

Phase 2 (v1.5.0) module split: the monolithic
``src/td_mcp/tool_registry.py`` (7000+ lines) is being broken up into
domain-themed submodules under this package. Each submodule declares its
tools via ``@mcp.tool`` decorators that mutate the shared ``mcp`` instance
defined in ``tool_registry.py``.

The split is done incrementally — one domain at a time — so the schema
snapshot stays green at every step.

Current submodules:
- ``tools_memory``   — td_memory_* (10 tools)
- (future: tools_graph, tools_vision, tools_planning, etc.)

``tool_registry.py`` imports each submodule at the end of its own
initialization (after ``mcp`` and all helpers are defined) to trigger
decorator registration. The circular-looking dependency works because
Python's module cache exposes the partially-loaded ``tool_registry``
module to the importing submodule — by which point ``mcp`` and all
helper functions are already bound as module globals.
"""

from __future__ import annotations
