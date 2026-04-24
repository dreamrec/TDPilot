# TouchDesigner Component

This folder contains the TouchDesigner-side component and helper scripts.

Files:
- `tdpilot.tox`: drag into `/local` (persists across project opens) or import into your project.
- `mcp_webserver_callbacks.py`: HTTP callback handler code loaded into the component.
- `ws_callbacks.py`: websocket callback code for event streaming.
- `event_emitter.py`: TD event emitter helper.
- `build_export_mcp_tox.py`: builds a reusable `tdpilot.tox` and installs it into `/local` by default.

Quick setup in Textport (auto-installs into `/local`):

```python
exec(open("/ABS/PATH/TDPilot/setup_mcp_in_td.py").read(), globals(), globals())
```

To install into a specific project instead:

```python
import os
os.environ["TD_MCP_PARENT_PATH"] = "/project1"
```

To export the .tox only (no live install):

```python
import os
os.environ["TD_MCP_PARENT_PATH"] = ""
```
