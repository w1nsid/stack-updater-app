from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

__all__ = [
    "manager",
    "ConnectionManager",
    "broadcast_stack_update",
    "broadcast_stacks_update",
]

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()
        # Simple lock to avoid concurrent set mutation
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active.add(websocket)
        log.debug("WebSocket connected; active=%d", len(self.active))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self.active:
                self.active.remove(websocket)
        log.debug("WebSocket disconnected; active=%d", len(self.active))

    async def broadcast_json(self, message: Dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        async with self._lock:
            conns: Iterable[WebSocket] = list(self.active)
        for ws in conns:
            try:
                await ws.send_text(payload)
            except WebSocketDisconnect:
                dead.append(ws)
            except Exception:  # pragma: no cover - best effort
                log.exception("WebSocket send failed; dropping client")
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self.active.discard(ws)


manager = ConnectionManager()


def stack_payload(row: Any) -> Dict[str, Any]:
    """Convert a stack row or dict to a WebSocket payload."""
    # Handle both ORM models and dicts (from StackDTO.to_dict())
    if isinstance(row, dict):
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "webhook_url": row.get("webhook_url"),
            "image_status": row.get("image_status"),
            "image_message": row.get("image_message"),
            "image_last_checked": row.get("image_last_checked"),
            "auto_update_enabled": row.get("auto_update_enabled"),
            "last_updated_at": row.get("last_updated_at"),
            "portainer_created_at": row.get("portainer_created_at"),
            "portainer_updated_at": row.get("portainer_updated_at"),
        }
    # Row is ORM model with attributes
    return {
        "id": row.id,
        "name": getattr(row, "name", None),
        "webhook_url": getattr(row, "webhook_url", None),
        "image_status": getattr(row, "image_status", None),
        "image_message": getattr(row, "image_message", None),
        "image_last_checked": getattr(row, "image_last_checked", None),
        "auto_update_enabled": getattr(row, "auto_update_enabled", None),
        "last_updated_at": getattr(row, "last_updated_at", None),
        "portainer_created_at": getattr(row, "portainer_created_at", None),
        "portainer_updated_at": getattr(row, "portainer_updated_at", None),
    }


async def broadcast_stack_update(row: Any) -> None:
    """Broadcast a single stack update to all connected clients."""
    await manager.broadcast_json({"type": "stack_update", "payload": stack_payload(row)})


async def broadcast_stacks_update(stacks: List[Dict[str, Any]]) -> None:
    """Broadcast a full list of stacks to all connected clients (for sync/refresh-all)."""
    await manager.broadcast_json({"type": "stacks_sync", "payload": stacks})
