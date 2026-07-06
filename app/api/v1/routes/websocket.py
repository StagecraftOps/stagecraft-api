import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import AUTH_COOKIE_NAME
from app.core.security import verify_access_token

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            try:
                self.active_connections.remove(websocket)
            except ValueError:
                pass

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket) -> None:
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as exc:
            logger.debug("Dropping WebSocket after send failure: %s", exc)
            await self.disconnect(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        async with self._lock:
            connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as exc:
                logger.debug("Marking WebSocket dead after broadcast failure: %s", exc)
                dead.append(connection)

        for ws in dead:
            await self.disconnect(ws)

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.cookies.get(AUTH_COOKIE_NAME) or websocket.query_params.get("token")
    if token:
        payload = verify_access_token(token)
        if not payload:
            await websocket.close(code=4001, reason="Unauthorized")
            return

    await manager.connect(websocket)
    try:
        await manager.send_personal_message({"type": "connected", "message": "WebSocket connected"}, websocket)
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await manager.send_personal_message({"type": "pong"}, websocket)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
