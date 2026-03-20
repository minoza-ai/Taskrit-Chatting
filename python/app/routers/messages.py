from typing import Optional
from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, validate_room_member
from app.schemas.message import SendMessageRequest
from app.services.message_service import (
    send_message_service,
    list_messages_service,
    delete_message_service,
)
from app.websocket.manager import manager

router = APIRouter(tags=["messages"])


@router.post("/rooms/{room_id}/messages")
async def send_message(
    room_id: str,
    body: SendMessageRequest,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    saved_message = send_message_service(room_id, current_user["user_uuid"], body.text)

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
def delete_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
):
    return delete_message_service(message_id, current_user["user_uuid"])