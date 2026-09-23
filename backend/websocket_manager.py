import logging
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger("EcoQuery.ws")

class WebSocketManager:
    def __init__(self):
        self.connections: dict[str, Set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, user_email: str):
        await ws.accept()
        self.connections.setdefault(user_email, set()).add(ws)
        logger.info(f"WS connected: {user_email}")

    def disconnect(self, ws: WebSocket, user_email: str):
        self.connections.get(user_email, set()).discard(ws)
        if not self.connections.get(user_email):
            self.connections.pop(user_email, None)
        logger.info(f"WS disconnected: {user_email}")

    async def broadcast_to_user(self, user_email: str, event: str, data: dict):
        for ws in self.connections.get(user_email, set()):
            try:
                await ws.send_json({"event": event, "data": data})
            except Exception:
                self.connections.get(user_email, set()).discard(ws)

    async def broadcast_to_all(self, event: str, data: dict):
        for user, sockets in list(self.connections.items()):
            for ws in list(sockets):
                try:
                    await ws.send_json({"event": event, "data": data})
                except Exception:
                    sockets.discard(ws)

ws_manager = WebSocketManager()
