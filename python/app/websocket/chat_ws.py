from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from app.dependencies import fetch_current_user_by_token
from app.services.room_service import get_room, get_dm_display_name_for_user
from app.services.message_service import send_message_service, list_messages_service
from app.websocket.manager import manager

router = APIRouter(tags=["websocket"])


class WSChatMessage(BaseModel):
    type: str
    text: str | None = None


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    user_uuid = None
    connection_id = None

    await websocket.accept()

    try:
        token = websocket.query_params.get("token")

        if not token:
            await websocket.send_json({
                "type": "error",
                "message": "token query parameter가 필요합니다.",
            })
            await websocket.close(code=4401)
            return

        current_user = fetch_current_user_by_token(token)
        user_uuid = current_user["user_uuid"]
        connection_id = manager.connect_user_notifications(user_uuid, websocket)

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        if user_uuid and connection_id:
            manager.disconnect_user_notifications(user_uuid, connection_id)

    except Exception:
        if user_uuid and connection_id:
            manager.disconnect_user_notifications(user_uuid, connection_id)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


@router.websocket("/ws/rooms/{room_id}")
async def websocket_chat(websocket: WebSocket, room_id: str):
    user_uuid = None
    nickname = None
    connection_id = None

    await websocket.accept()

    try:
        token = websocket.query_params.get("token")
        last_message_id = websocket.query_params.get("last_message_id")

        if not token:
            await websocket.send_json({
                "type": "error",
                "message": "token query parameter가 필요합니다."
            })
            await websocket.close(code=4401)
            return

        current_user = fetch_current_user_by_token(token)

        user_uuid = current_user["user_uuid"]
        nickname = current_user["nickname"]

        room = get_room(room_id)

        if not room:
            await websocket.send_json({
                "type": "error",
                "message": "채팅방이 없습니다."
            })
            await websocket.close(code=4404)
            return

        if user_uuid not in room["members"]:
            await websocket.send_json({
                "type": "error",
                "message": "이 사용자는 해당 채팅방 멤버가 아닙니다."
            })
            await websocket.close(code=4403)
            return

        connection_id, is_first_connection = await manager.connect(room_id, user_uuid, websocket)

        if last_message_id:
            try:
                missed_messages = list_messages_service(
                    room_id=room_id,
                    limit=100,
                    after=last_message_id,
                )

                for missed_message in missed_messages:
                    await websocket.send_json({
                        "type": "message",
                        "data": missed_message,
                        "sender": {
                            "user_uuid": missed_message["sender_uuid"],
                            "nickname": None,
                        },
                        "resumed": True,
                    })
            except Exception:
                await websocket.send_json({
                    "type": "resume_failed",
                    "message": "이전 메시지 복구에 실패했습니다."
                })

        if is_first_connection:
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

        while True:
            data = await websocket.receive_json()

            try:
                payload = WSChatMessage(**data)
            except ValidationError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": "잘못된 메시지 형식입니다.",
                    "detail": e.errors(),
                })
                continue

            if payload.type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if payload.type == "typing":
                await manager.broadcast(
                    room_id,
                    {
                        "type": "typing",
                        "room_id": room_id,
                        "user_uuid": user_uuid,
                        "nickname": nickname,
                    },
                    exclude_connection_id=connection_id,
                )
                continue

            if payload.type == "stop_typing":
                await manager.broadcast(
                    room_id,
                    {
                        "type": "stop_typing",
                        "room_id": room_id,
                        "user_uuid": user_uuid,
                        "nickname": nickname,
                    },
                    exclude_connection_id=connection_id,
                )
                continue

            if payload.type == "message":
                if not payload.text or not payload.text.strip():
                    await websocket.send_json({
                        "type": "error",
                        "message": "메시지 내용은 비어 있을 수 없습니다."
                    })
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

                for member_uuid in room["members"]:
                    if member_uuid == user_uuid:
                        continue

                    await manager.send_user_notification(
                        member_uuid,
                        {
                            "type": "notification",
                            "event": "new_message",
                            "room_id": room_id,
                            "room_name": get_dm_display_name_for_user(room, member_uuid),
                            "message": {
                                "message_id": saved_message["message_id"],
                                "text": saved_message["text"],
                                "sender_uuid": user_uuid,
                                "sender_profile_image": current_user.get("profile_image_url"),
                                "created_at": saved_message["created_at"],
                            },
                        },
                    )
                continue

            await websocket.send_json({
                "type": "error",
                "message": f"지원하지 않는 type입니다: {payload.type}"
            })

    except WebSocketDisconnect:
        if connection_id:
            disconnected_user_uuid, is_last_connection = manager.disconnect(room_id, connection_id)

            if disconnected_user_uuid and is_last_connection:
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

    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": "websocket 내부 예외 발생",
                "detail": str(e),
            })
        except Exception:
            pass

        try:
            await websocket.close(code=1011)
        except Exception:
            pass