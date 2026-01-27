"""WebSocket endpoint for real-time video processing updates."""

import json
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.db.models import User
from app.schemas.video import WSConnectedEvent, WSErrorEvent
from app.services.auth_service import auth_service
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["Video WebSocket"])


async def _authenticate_websocket(
    token: Optional[str],
    db: AsyncSession,
) -> Optional[User]:
    """Validate JWT from query param and return user or None if anonymous allowed."""
    if not token:
        return None

    try:
        payload = auth_service.decode_token(token)
        if not payload or payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        return await auth_service.get_user_by_id(db, int(user_id))
    except Exception as e:  # noqa: BLE001
        logger.warning("WebSocket auth failed: %s", e)
        return None


@router.websocket("/ws/{task_id}")
async def video_updates(
    websocket: WebSocket,
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[Optional[str], Query(description="JWT access token")] = None,
):
    """
    WebSocket endpoint for clients to receive video processing updates.

    - Accepts optional `token` query parameter for authenticated users.
    - Broadcasts `connected`, `segment_ready`, `progress`, `completed`, `error` events.
    """
    user = await _authenticate_websocket(token, db)
    if token and not user:
        # Token was provided but invalid/expired
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token"
        )
        return

    await websocket_manager.connect(task_id, websocket)

    try:
        # Send initial connected event to this socket only
        await websocket.send_json(WSConnectedEvent(task_id=task_id).model_dump())

        # Keep the connection alive; handle ping messages from client
        while True:
            message = await websocket.receive_text()
            # Handle ping messages to keep connection alive
            try:
                data = json.loads(message)
                if isinstance(data, dict) and data.get("type") == "ping":
                    logger.debug("WebSocket ping received for task_id=%s", task_id)
                    # Send pong response
                    await websocket.send_json({"type": "pong"})
            except Exception:  # noqa: BLE001
                # Ignore parse errors for ping messages
                pass

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for task_id=%s", task_id)

    except Exception as e:  # noqa: BLE001
        logger.error("WebSocket error for task_id=%s: %s", task_id, e, exc_info=True)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(e))

    finally:
        await websocket_manager.disconnect(task_id, websocket)
