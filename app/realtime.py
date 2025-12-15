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
            conns = list(self.active)
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


async def broadcast_stacks_update(stacks: List[Dict[str, Any]]) -> None:
    """Broadcast a full list of stacks to all connected clients (for sync/refresh-all)."""
    await manager.broadcast_json({"type": "stacks_sync", "payload": stacks})
