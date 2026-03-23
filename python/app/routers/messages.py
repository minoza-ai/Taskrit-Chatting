from typing import Optional
from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, validate_room_member
from app.schemas.message import SendMessageRequest, EditMessageRequest
from app.services.message_service import (
    send_message_service,
    list_messages_service,
    delete_message_service,
    edit_message_service,
)
from app.websocket.manager import manager
from app.services.room_service import get_room, get_dm_display_name_for_user

router = APIRouter(tags=["messages"])


@router.post("/rooms/{room_id}/messages")
async def send_message(
    room_id: str,
    body: SendMessageRequest,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    saved_message = send_message_service(room_id, current_user["user_uuid"], body.text)
    room = get_room(room_id)

    # REST 전송도 WebSocket 구독자에게 동일 이벤트를 push 해야 실시간 동기화된다.
    await manager.broadcast(
        room_id,
        {
            "type": "message",
            "data": saved_message,
            "sender": {
                "user_uuid": current_user["user_uuid"],
                "nickname": current_user.get("nickname"),
            },
        },
    )

    if room:
        for member_uuid in room["members"]:
            if member_uuid == current_user["user_uuid"]:
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
                        "sender_uuid": current_user["user_uuid"],
                        "sender_profile_image": current_user.get("profile_image_url"),
                        "created_at": saved_message["created_at"],
                    },
                },
            )

    return saved_message


@router.get("/rooms/{room_id}/messages")
def list_messages(
    room_id: str,
    limit: int = 30,
    before: Optional[str] = None,
    after: Optional[str] = None,
    auth: dict = Depends(validate_room_member),
):
    return list_messages_service(room_id, limit, before, after)


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
):
    deleted_message = delete_message_service(message_id, current_user["user_uuid"])

    await manager.broadcast(
        deleted_message["room_id"],
        {
            "type": "message_deleted",
            "data": deleted_message,
            "user_uuid": current_user["user_uuid"],
        },
    )

    return {
        "message": "메시지가 삭제 처리되었습니다.",
        "data": deleted_message,
    }


@router.put("/messages/{message_id}")
async def edit_message(
    message_id: str,
    body: EditMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    edited_message = edit_message_service(message_id, body.text, current_user["user_uuid"])

    await manager.broadcast(
        edited_message["room_id"],
        {
            "type": "message_updated",
            "data": edited_message,
            "user_uuid": current_user["user_uuid"],
        },
    )

    return {
        "message": "메시지가 수정되었습니다.",
        "data": edited_message,
    }