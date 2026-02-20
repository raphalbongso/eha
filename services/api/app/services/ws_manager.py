"""WebSocket connection manager with Redis pub/sub for multi-worker support."""

import asyncio
import json
import logging
import uuid

import redis
import redis.asyncio as aioredis
from fastapi import WebSocket

from app.config import get_settings

logger = logging.getLogger(__name__)

REDIS_CHANNEL = "eha:ws:alerts"


class ConnectionManager:
    """Manages per-user WebSocket connections and a Redis pub/sub listener."""

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, list[WebSocket]] = {}
        self._pubsub: aioredis.client.PubSub | None = None
        self._listener_task: asyncio.Task | None = None

    # -- lifecycle --

    async def start(self) -> None:
        """Start the Redis pub/sub listener."""
        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        self._pubsub = r.pubsub()
        await self._pubsub.subscribe(REDIS_CHANNEL)
        self._listener_task = asyncio.create_task(self._listen())
        logger.info("WebSocket manager started (Redis channel=%s)", REDIS_CHANNEL)

    async def stop(self) -> None:
        """Stop the listener and close all connections."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.unsubscribe(REDIS_CHANNEL)
            await self._pubsub.close()
        # Close all WebSocket connections
        for ws_list in self._connections.values():
            for ws in ws_list:
                try:
                    await ws.close()
                except Exception:
                    pass
        self._connections.clear()
        logger.info("WebSocket manager stopped")

    # -- connection tracking --

    async def connect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(user_id, []).append(ws)
        logger.debug("WS connected: user=%s (total=%d)", user_id, len(self._connections[user_id]))

    def disconnect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        ws_list = self._connections.get(user_id, [])
        if ws in ws_list:
            ws_list.remove(ws)
        if not ws_list:
            self._connections.pop(user_id, None)
        logger.debug("WS disconnected: user=%s", user_id)

    # -- send to user on this worker --

    async def _send_to_user(self, user_id: uuid.UUID, payload: dict) -> None:
        ws_list = self._connections.get(user_id, [])
        dead: list[WebSocket] = []
        for ws in ws_list:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    # -- Redis listener --

    async def _listen(self) -> None:
        """Listen for messages on the Redis channel and forward to local WS clients."""
        assert self._pubsub is not None
        try:
            async for message in self._pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    target_user = uuid.UUID(data["user_id"])
                    await self._send_to_user(target_user, data["payload"])
                except Exception:
                    logger.exception("Error processing pub/sub message")
        except asyncio.CancelledError:
            return

    # -- publish (async, for use from async code) --

    async def publish_alert(self, user_id: uuid.UUID, payload: dict) -> None:
        """Publish an alert to all workers via Redis."""
        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            msg = json.dumps({"user_id": str(user_id), "payload": payload})
            await r.publish(REDIS_CHANNEL, msg)
        finally:
            await r.aclose()


# Singleton instance
ws_manager = ConnectionManager()


def publish_alert_sync(user_id: str, payload: dict) -> None:
    """Publish an alert from synchronous code (e.g. Celery tasks).

    Uses a synchronous Redis client to avoid event-loop issues in Celery.
    """
    settings = get_settings()
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        msg = json.dumps({"user_id": user_id, "payload": payload})
        r.publish(REDIS_CHANNEL, msg)
    finally:
        r.close()
