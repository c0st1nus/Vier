"""WebSocket manager to track and broadcast pipeline events per task_id.

This is an in-memory manager intended for a single FastAPI instance.
It can later be swapped for a Redis/pubsub-backed implementation without
changing the public interface.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manage WebSocket connections keyed by task_id."""

    def __init__(self) -> None:
        # task_id (str) -> list[WebSocket]
        self._connections: DefaultDict[str, List[WebSocket]] = defaultdict(list)
        # async lock to avoid race conditions when connecting/disconnecting
        self._lock = asyncio.Lock()

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """Accept connection and register it under a task_id."""
        await websocket.accept()
        async with self._lock:
            self._connections[task_id].append(websocket)
        logger.info(
            "WebSocket connected for task_id=%s (total=%d)",
            task_id,
            self._count(task_id),
        )

    async def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the registry."""
        async with self._lock:
            conns = self._connections.get(task_id, [])
            if websocket in conns:
                conns.remove(websocket)
            if not conns and task_id in self._connections:
                del self._connections[task_id]
        logger.info(
            "WebSocket disconnected for task_id=%s (remaining=%d)",
            task_id,
            self._count(task_id),
        )

    async def send_to_task(self, task_id: str, message: Dict[str, Any]) -> None:
        """Send a JSON message to all connections for a task_id."""
        async with self._lock:
            conns = list(self._connections.get(task_id, []))

        if not conns:
            logger.debug("No active connections for task_id=%s; skipping send", task_id)
            return

        await asyncio.gather(*(self._safe_send_json(ws, message) for ws in conns))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a JSON message to all connected sockets."""
        async with self._lock:
            conns = [ws for conn_list in self._connections.values() for ws in conn_list]

        await asyncio.gather(*(self._safe_send_json(ws, message) for ws in conns))

    async def _safe_send_json(
        self, websocket: WebSocket, message: Dict[str, Any]
    ) -> None:
        """Send JSON if the socket is still connected."""
        if websocket.client_state != WebSocketState.CONNECTED:
            return
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            # Client disconnected between checks
            return
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to send WebSocket message: %s", e)

    def _count(self, task_id: Optional[str] = None) -> int:
        """Return number of connections (global or per task)."""
        if task_id is None:
            return sum(len(v) for v in self._connections.values())
        return len(self._connections.get(task_id, []))


# Singleton instance for easy import
websocket_manager = WebSocketManager()
