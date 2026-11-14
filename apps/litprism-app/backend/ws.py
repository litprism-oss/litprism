from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    def register(self, project_id: str, websocket: WebSocket) -> None:
        """Track an already-accepted socket. The auth handshake runs between accept and this."""
        self._connections.setdefault(project_id, []).append(websocket)

    async def connect(self, project_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.register(project_id, websocket)

    def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(project_id, [])
        if websocket in conns:
            conns.remove(websocket)

    def has_connections(self, project_id: str) -> bool:
        return bool(self._connections.get(project_id))

    async def broadcast(self, project_id: str, message: Any) -> None:
        # Iterate a copy: a failed send drops its socket, and sockets can come and go meanwhile.
        for connection in list(self._connections.get(project_id, [])):
            try:
                await connection.send_json(message)
            except Exception:  # noqa: BLE001 - one dead socket must not stop the others
                self.disconnect(project_id, connection)


ws_manager = ConnectionManager()
