from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Iterable

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

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
    # Row has attributes from models.Stack
    return {
        "id": row.id,
        "name": getattr(row, "name", None),
        "image_status": getattr(row, "image_status", None),
        "image_message": getattr(row, "image_message", None),
        "image_last_checked": getattr(row, "image_last_checked", None),
        "last_updated_at": getattr(row, "last_updated_at", None),
        "is_outdated": getattr(row, "is_outdated", None),
    }


async def broadcast_stack_update(row: Any) -> None:
    await manager.broadcast_json({"type": "stack", "payload": stack_payload(row)})


async def broadcast_staleness(rows: Iterable[Any]) -> None:
    await manager.broadcast_json(
        {
            "type": "staleness",
            "payload": [{
                "id": r.id,
                "is_outdated": getattr(r, "is_outdated", None)
            } for r in rows],
        }
    )


async def broadcast_staleness_payload(payload: list[dict]) -> None:
    """Broadcast a precomputed staleness payload of primitives.

    Use this when ORM instances may be detached (e.g., after commit/close).
    """
    await manager.broadcast_json({"type": "staleness", "payload": payload})
