from typing import Optional
from fastapi import APIRouter
from app.schemas.message import SendMessageRequest, DeleteMessageRequest
from app.services.message_service import (
    send_message_service,
    list_messages_service,
    delete_message_service,
)

router = APIRouter(tags=["messages"])

@router.post("/rooms/{room_id}/messages")
def send_message(room_id: str, body: SendMessageRequest):
    return send_message_service(room_id, body.sender_uuid, body.text)

@router.get("/rooms/{room_id}/messages")
def list_messages(
    room_id: str,
    limit: int = 30,
    before: Optional[str] = None,
    after: Optional[str] = None
):
    return list_messages_service(room_id, limit, before, after)

@router.delete("/messages/{message_id}")
def delete_message(message_id: str, body: DeleteMessageRequest):
    return delete_message_service(message_id, body.requester_uuid)