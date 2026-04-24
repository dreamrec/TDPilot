"""Event-subscription tools.

Part of the v1.5.0 Phase 2 module split.

Tools in this module (3):
    td_subscribe    — subscribe to chop/par/cook/error/timeline events
    td_unsubscribe  — remove all subscriptions for a node
    td_get_events   — read recent event history
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.models import SubscribeInput
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_subscribe")
async def td_subscribe(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="TD node path to monitor, e.g. '/project1/audio1'."),
    ],
    event_types: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Event types: chop_change, par_change, cook_complete, "
                "node_error, timeline. Defaults to ['chop_change', 'par_change']."
            ),
        ),
    ] = None,
    channels: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Specific CHOP channels to monitor. None means all channels.",
        ),
    ] = None,
    params: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Specific parameters to monitor. None means all tracked params.",
        ),
    ] = None,
    threshold: Annotated[
        float | None,
        Field(
            default=None,
            description="Only emit events when delta exceeds this threshold.",
        ),
    ] = None,
    rate_limit: Annotated[
        float,
        Field(
            default=0.016,
            ge=0.001,
            le=10.0,
            description="Minimum seconds between repeated events from same source.",
        ),
    ] = 0.016,
) -> str:
    """Subscribe to runtime TD events for a node."""
    # Re-instantiate so the SubscribeInput @field_validator on event_types
    # (allowed set: chop_change|par_change|cook_complete|node_error|timeline)
    # still runs.
    validated = SubscribeInput(
        path=path,
        event_types=event_types or ["chop_change", "par_change"],
        channels=channels,
        params=params,
        threshold=threshold,
        rate_limit=rate_limit,
    )
    finish = _tr._start_tool(ctx, "td_subscribe")
    try:
        body = validated.model_dump(exclude_none=True)
        provisioning = await _tr._get_client(ctx).request("monitor/subscribe", body)

        event_manager = _tr._get_event_manager(ctx)
        for et in validated.event_types:
            event_manager.register_subscription(validated.path, et, body)

        payload = {
            "success": True,
            "path": validated.path,
            "subscription": body,
            "resource_uris": _tr._build_subscription_resource_uris(validated),
            "provisioning": provisioning,
            "active_subscriptions": len(event_manager.list_subscriptions()),
        }
        _tr._audit_log(
            ctx,
            "td_subscribe",
            {
                "path": validated.path,
                "event_types": validated.event_types,
            },
        )
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_subscribe")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_unsubscribe")
async def td_unsubscribe(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="TD node path to stop monitoring."),
    ],
) -> str:
    """Remove a node subscription."""
    finish = _tr._start_tool(ctx, "td_unsubscribe")
    try:
        provisioning = await _tr._get_client(ctx).request(
            "monitor/unsubscribe",
            {"path": path},
        )

        event_manager = _tr._get_event_manager(ctx)
        removed = event_manager.unregister_all_for_path(path)

        payload = {
            "success": removed > 0,
            "path": path,
            "provisioning": provisioning,
            "active_subscriptions": len(event_manager.list_subscriptions()),
        }
        _tr._audit_log(ctx, "td_unsubscribe", {"path": path})
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_unsubscribe")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_events")
async def td_get_events(
    ctx: Context,
    event_type: Annotated[
        str | None,
        Field(default=None, description="Optional event type filter."),
    ] = None,
    limit: Annotated[
        int,
        Field(
            default=50,
            ge=1,
            le=1000,
            description="Maximum number of events to return.",
        ),
    ] = 50,
) -> str:
    """Read recent event history."""
    finish = _tr._start_tool(ctx, "td_get_events")
    try:
        manager = _tr._get_event_manager(ctx)
        events = manager.get_recent_events(event_type=event_type, limit=limit)
        payload = {
            "schema_version": 1,
            "event_type": event_type,
            "count": len(events),
            "events": events,
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_events")
        return format_tool_error(exc)
    finally:
        finish()
