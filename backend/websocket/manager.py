import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Keeps transient socket connections; quiz state itself stays in SQLite."""

    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.lock = asyncio.Lock()

    async def connect(self, quiz_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.connections[quiz_id].add(websocket)

    async def disconnect(self, quiz_id: str, websocket: WebSocket):
        async with self.lock:
            self.connections[quiz_id].discard(websocket)
            if not self.connections[quiz_id]:
                self.connections.pop(quiz_id, None)

    async def broadcast(self, quiz_id: str, event: dict):
        async with self.lock:
            sockets = list(self.connections.get(quiz_id, set()))
        disconnected = []
        for socket in sockets:
            try:
                await socket.send_json(event)
            except Exception:
                disconnected.append(socket)
        for socket in disconnected:
            await self.disconnect(quiz_id, socket)


manager = ConnectionManager()
