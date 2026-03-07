# TouchDesigner Component

This folder contains the TouchDesigner-side component and helper scripts.

Files:
- `mcp_server.tox`: import this into your TouchDesigner project.
- `mcp_webserver_callbacks.py`: HTTP callback handler code loaded into the component.
- `ws_callbacks.py`: websocket callback code for event streaming.
- `event_emitter.py`: TD event emitter helper.
- `build_export_mcp_tox.py`: builds a reusable `mcp_server.tox` in a temporary container and optionally installs it into a target project COMP.

Quick rebuild in Textport:

```python
exec(open("/ABS/PATH/TDPilot/td_component/build_export_mcp_tox.py").read(), globals(), globals())
```

Optional live install target:

```python
import os
os.environ["TD_MCP_PARENT_PATH"] = "/project1"
```
