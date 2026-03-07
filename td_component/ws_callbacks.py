"""WebSocket DAT callbacks for the TD -> MCP event bridge.

Attach this as callbacks DAT on `ws_client`.
`ws_client` should connect to ws://127.0.0.1:9982.
"""

import json
import time


def _emitter_mod():
    try:
        return mod("event_emitter")
    except Exception:
        return None


def onConnect(webSocketDAT):
    """Called when ws_client connects to the MCP event server."""
    emitter = _emitter_mod()
    if emitter and hasattr(emitter, "flush_pending"):
        try:
            emitter.flush_pending(limit=500)
        except Exception:
            pass
    return


def onDisconnect(webSocketDAT):
    """Called when ws_client disconnects from MCP event server."""
    # Keep Active on; the WebSocket DAT handles reconnect attempts.
    try:
        if hasattr(webSocketDAT, "par") and hasattr(webSocketDAT.par, "active"):
            webSocketDAT.par.active = 1
    except Exception:
        pass
    return


def onReceiveText(webSocketDAT, rowIndex, message, bytes, peer):
    """Handle control messages from MCP server (optional ping/pong)."""
    try:
        data = json.loads(message)
    except Exception:
        return

    if isinstance(data, dict) and data.get("type") == "ping":
        try:
            webSocketDAT.sendText(json.dumps({"type": "pong", "timestamp": time.time()}))
        except Exception:
            pass

    emitter = _emitter_mod()
    if emitter and hasattr(emitter, "flush_pending"):
        try:
            emitter.flush_pending(limit=200)
        except Exception:
            pass
    return


def onReceiveBinary(webSocketDAT, rowIndex, data, peer):
    """Binary payloads are not used."""
    return


def onError(webSocketDAT, error):
    """Log websocket callback errors to textport."""
    debug("[td-mcp ws]", error)
    return
