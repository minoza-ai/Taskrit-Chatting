from collections import defaultdict
from fastapi import WebSocket
import uuid


class ConnectionManager:
    def __init__(self):
        # room_id -> connection_id -> {"user_uuid": str, "websocket": WebSocket}
        self.active_connections: dict[str, dict[str, dict]] = defaultdict(dict)

    async def connect(self, room_id: str, user_uuid: str, websocket: WebSocket) -> tuple[str, bool]:
        was_user_connected = self.is_user_connected(room_id, user_uuid)

        connection_id = str(uuid.uuid4())
        self.active_connections[room_id][connection_id] = {
            "user_uuid": user_uuid,
            "websocket": websocket,
        }

        is_first_connection = not was_user_connected
        return connection_id, is_first_connection

    def disconnect(self, room_id: str, connection_id: str) -> tuple[str | None, bool]:
        if room_id not in self.active_connections:
            return None, False

        connection_info = self.active_connections[room_id].pop(connection_id, None)
        if connection_info is None:
            if not self.active_connections[room_id]:
                self.active_connections.pop(room_id, None)
            return None, False

        user_uuid = connection_info["user_uuid"]
        is_last_connection = not self.is_user_connected(room_id, user_uuid)

        if not self.active_connections[room_id]:
            self.active_connections.pop(room_id, None)

        return user_uuid, is_last_connection

    def is_user_connected(self, room_id: str, user_uuid: str) -> bool:
        if room_id not in self.active_connections:
            return False

        for connection_info in self.active_connections[room_id].values():
            if connection_info["user_uuid"] == user_uuid:
                return True

        return False

    def get_user_connection_count(self, room_id: str, user_uuid: str) -> int:
        if room_id not in self.active_connections:
            return 0

        count = 0
        for connection_info in self.active_connections[room_id].values():
            if connection_info["user_uuid"] == user_uuid:
                count += 1

        return count

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(
        self,
        room_id: str,
        message: dict,
        exclude_connection_id: str | None = None,
    ):
        if room_id not in self.active_connections:
            return

        disconnected_connection_ids = []

        for connection_id, connection_info in self.active_connections[room_id].items():
            if exclude_connection_id and connection_id == exclude_connection_id:
                continue

            websocket = connection_info["websocket"]

            try:
                await websocket.send_json(message)
            except Exception:
                disconnected_connection_ids.append(connection_id)

        for connection_id in disconnected_connection_ids:
            self.disconnect(room_id, connection_id)

    async def broadcast_to_user(
        self,
        room_id: str,
        target_user_uuid: str,
        message: dict,
    ):
        if room_id not in self.active_connections:
            return

        disconnected_connection_ids = []

        for connection_id, connection_info in self.active_connections[room_id].items():
            if connection_info["user_uuid"] != target_user_uuid:
                continue

            websocket = connection_info["websocket"]

            try:
                await websocket.send_json(message)
            except Exception:
                disconnected_connection_ids.append(connection_id)

        for connection_id in disconnected_connection_ids:
            self.disconnect(room_id, connection_id)


manager = ConnectionManager()