"""Tool-registry submodules for TDPilot MCP.

The monolithic ``src/td_mcp/tool_registry.py`` has been split into
domain-themed submodules under this package. Each submodule declares its
tools via ``@mcp.tool`` decorators that mutate the shared ``mcp`` instance
defined in ``tool_registry.py``.

Current submodules cover the public tool surface by domain: graph, data,
runtime, safety, state, memory, knowledge, brain/transaction, patch,
streaming, vision, system, notes, optimizer, metadata, macros, hints,
recommendations, events, batch, resources, and prompts. Keep this package
doc high-level; ``tool_registry.py`` is the source of truth for the exact
side-effect import and re-export list.

``tool_registry.py`` imports each submodule at the end of its own
initialization (after ``mcp`` and all helpers are defined) to trigger
decorator registration. The circular-looking dependency works because
Python's module cache exposes the partially-loaded ``tool_registry``
module to the importing submodule — by which point ``mcp`` and all
helper functions are already bound as module globals.
"""

from __future__ import annotations
