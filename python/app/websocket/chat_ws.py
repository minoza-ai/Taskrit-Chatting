from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from app.dependencies import validate_ws_room_member
from app.services.message_service import send_message_service
from app.websocket.manager import manager

router = APIRouter(tags=["websocket"])


class WSChatMessage(BaseModel):
    type: str
    text: str | None = None


@router.websocket("/ws/rooms/{room_id}")
async def websocket_chat(websocket: WebSocket, room_id: str):
    try:
        auth = await validate_ws_room_member(websocket, room_id)
    except Exception:
        return

    current_user = auth["current_user"]
    user_uuid = current_user["user_uuid"]
    nickname = current_user["nickname"]

    await manager.connect(room_id, user_uuid, websocket)

    await manager.broadcast(
        room_id,
        {
            "type": "system",
            "event": "user_joined",
            "room_id": room_id,
            "user_uuid": user_uuid,
            "nickname": nickname,
        },
    )

    try:
        while True:
            data = await websocket.receive_json()

            try:
                payload = WSChatMessage(**data)
            except ValidationError as e:
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": "잘못된 WebSocket 메시지 형식입니다.",
                        "detail": e.errors(),
                    },
                    websocket,
                )
                continue

            if payload.type == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)
                continue

            if payload.type == "message":
                if not payload.text or not payload.text.strip():
                    await manager.send_personal_message(
                        {
                            "type": "error",
                            "message": "메시지 내용은 비어 있을 수 없습니다.",
                        },
                        websocket,
                    )
                    continue

                saved_message = send_message_service(
                    room_id=room_id,
                    sender_uuid=user_uuid,
                    text=payload.text,
                )

                await manager.broadcast(
                    room_id,
                    {
                        "type": "message",
                        "data": saved_message,
                        "sender": {
                            "user_uuid": user_uuid,
                            "nickname": nickname,
                        },
                    },
                )
                continue

            await manager.send_personal_message(
                {
                    "type": "error",
                    "message": f"지원하지 않는 type입니다: {payload.type}",
                },
                websocket,
            )

    except WebSocketDisconnect:
        manager.disconnect(room_id, user_uuid)
        await manager.broadcast(
            room_id,
            {
                "type": "system",
                "event": "user_left",
                "room_id": room_id,
                "user_uuid": user_uuid,
                "nickname": nickname,
            },
        )
    except Exception:
        manager.disconnect(room_id, user_uuid)
        try:
            await manager.broadcast(
                room_id,
                {
                    "type": "system",
                    "event": "user_left",
                    "room_id": room_id,
                    "user_uuid": user_uuid,
                    "nickname": nickname,
                },
            )
        except Exception:
            pass