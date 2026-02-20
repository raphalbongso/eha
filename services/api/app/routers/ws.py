"""WebSocket endpoint for real-time alert delivery."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import get_settings
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


def _authenticate_ws(token: str) -> uuid.UUID:
    """Validate a JWT token from the WebSocket query string. Returns user_id."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_private_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )
    user_id = payload.get("sub")
    token_type = payload.get("type")
    if user_id is None or token_type != "access":
        raise ValueError("invalid token payload")
    return uuid.UUID(user_id)


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alerts.

    Auth: connect with ?token=<JWT access token>.
    Supports ping/pong: client sends {"type":"ping"}, server replies {"type":"pong"}.
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        user_id = _authenticate_ws(token)
    except (JWTError, ValueError) as e:
        logger.warning("WS auth failed: %s", e)
        await websocket.close(code=4003, reason="Authentication failed")
        return

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("WS error for user=%s", user_id, exc_info=True)
    finally:
        ws_manager.disconnect(user_id, websocket)
