from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # room_id -> {user_uuid: websocket}
        self.active_connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, room_id: str, user_uuid: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[room_id][user_uuid] = websocket

    def disconnect(self, room_id: str, user_uuid: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].pop(user_uuid, None)
            if not self.active_connections[room_id]:
                self.active_connections.pop(room_id, None)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, room_id: str, message: dict):
        if room_id not in self.active_connections:
            return

        disconnected_users = []

        for user_uuid, connection in self.active_connections[room_id].items():
            try:
                await connection.send_json(message)
            except Exception:
                disconnected_users.append(user_uuid)

        for user_uuid in disconnected_users:
            self.disconnect(room_id, user_uuid)


manager = ConnectionManager()