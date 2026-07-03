"""HTTP subscription streams for stateless MCP revisions."""

from __future__ import annotations

import asyncio
import json

from fastapi import Request

from .shutdown import ensure_shutdown_event, wait_queue_message


def format_sse(data: str, *, event: str | None = None, event_id: str | None = None) -> str:
    lines: list[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    if event:
        lines.append(f"event: {event}")
    for chunk in data.splitlines() or [""]:
        lines.append(f"data: {chunk}")
    return "\n".join(lines) + "\n\n"


async def stream_stateless_subscription(
    request: Request,
    data: dict,
    *,
    heartbeat_interval: float = 10.0,
):
    shutdown = ensure_shutdown_event(request.app)
    params = data.get("params")
    params_dict = params if isinstance(params, dict) else {}
    requested = params_dict.get("notifications")
    notifications = requested if isinstance(requested, dict) else {}
    rpc_id = data.get("id")
    ack = {
        "jsonrpc": "2.0",
        "method": "notifications/subscriptions/acknowledged",
        "params": {"notifications": notifications},
    }
    if isinstance(rpc_id, (str, int)) and not isinstance(rpc_id, bool):
        ack["params"]["_meta"] = {"io.modelcontextprotocol/subscriptionId": rpc_id}
    yield format_sse(json.dumps(ack), event="message")
    try:
        while not shutdown.is_set() and not await request.is_disconnected():
            yield ": ping\n\n"
            await wait_queue_message(asyncio.Queue(), shutdown=shutdown, timeout=heartbeat_interval)
    except Exception:
        return


__all__ = ["format_sse", "stream_stateless_subscription"]
