# TouchDesigner Component — TDPilot v2.4.0

This folder contains the TouchDesigner-side component and helper scripts.

Files:
- `tdpilot.tox`: drag into `/local` (persists across project opens) or import into your project.
- `mcp_webserver_callbacks.py`: HTTP callback handler code loaded into the component.
- `ws_callbacks.py`: websocket callback code for event streaming.
- `event_emitter.py`: TD event emitter helper.
- `build_tdpilot_tox.py`: builds the full installer/panel component and exports
  the canonical `tdpilot.tox`.
- `build_export_mcp_tox.py`: builds the inner MCP bridge used by the full
  component build.

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

After loading the component, verify the embedded version and bridge before
using it:

```bash
uv run python scripts/diagnose_live_sync.py --live --pretty
```

The health response must report `api_version: 2.4.0`. For release validation,
use a disposable project and run the transactional live smoke plus operator
availability sampler; both create and clean scratch networks.
