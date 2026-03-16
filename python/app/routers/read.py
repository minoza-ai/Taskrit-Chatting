from fastapi import APIRouter, Depends

from app.dependencies import validate_room_member
from app.schemas.read import ReadMessageRequest
from app.services.read_service import (
    mark_room_as_read_service,
    get_read_status_service,
)

router = APIRouter(tags=["reads"])


@router.post("/rooms/{room_id}/read")
def mark_room_as_read(
    room_id: str,
    body: ReadMessageRequest,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    return mark_room_as_read_service(
        room_id,
        current_user["user_uuid"],
        body.last_read_message_id,
    )


@router.get("/rooms/{room_id}/read-status")
def get_read_status(
    room_id: str,
    auth: dict = Depends(validate_room_member),
):
    return get_read_status_service(room_id)