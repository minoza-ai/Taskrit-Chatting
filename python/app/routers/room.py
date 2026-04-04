from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies import get_current_user, validate_room_member
from app.websocket.manager import manager
from app.schemas.room import (
    AddRoomMembersRequest,
    CreateDMRoomRequest,
    CreateTeamRoomRequest,
    CreateTeamFromRoomRequest,
    UpdateRoomNameRequest,
)
from app.services.room_service import (
    add_members_to_room_service,
    create_dm_room_service,
    create_team_room_service,
    create_team_from_existing_room_service,
    delete_room_image_service,
    list_user_rooms_service,
    update_room_image_service,
    update_room_name_service,
)

router = APIRouter(tags=["rooms"])


@router.post("/dm/rooms")
def create_dm_room(
    body: CreateDMRoomRequest,
    current_user: dict = Depends(get_current_user),
):
    return create_dm_room_service(current_user["user_uuid"], body)


@router.post("/team/rooms")
def create_team_room(
    body: CreateTeamRoomRequest,
    current_user: dict = Depends(get_current_user),
):
    return create_team_room_service(current_user["user_uuid"], body)


@router.post("/rooms/{room_id}/team")
def create_team_from_existing_room(
    room_id: str,
    body: CreateTeamFromRoomRequest,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    return create_team_from_existing_room_service(room_id, current_user["user_uuid"], body)


@router.post("/rooms/{room_id}/members")
async def add_members_to_room(
    room_id: str,
    body: AddRoomMembersRequest,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    result = add_members_to_room_service(room_id, current_user["user_uuid"], body)

    # 방 멤버가 바뀌면 기존 메시지 unread_member_count 계산도 달라지므로
    # 실시간 구독자들이 메시지/방 목록을 재동기화할 수 있도록 이벤트를 전파한다.
    await manager.broadcast(
        room_id,
        {
            "type": "room_members_updated",
            "room_id": room_id,
            "members": result.get("members", []),
        },
    )

    for member_uuid in result.get("members", []):
        if member_uuid == current_user["user_uuid"]:
            continue
        await manager.send_user_notification(
            member_uuid,
            {
                "type": "notification",
                "event": "room_members_updated",
                "room_id": room_id,
                "room_name": result.get("room_name") or "채팅방",
            },
        )

    return result


@router.patch("/rooms/{room_id}/name")
def update_room_name(
    room_id: str,
    body: UpdateRoomNameRequest,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    return update_room_name_service(room_id, current_user["user_uuid"], body)


@router.patch("/rooms/{room_id}/image")
async def update_room_image(
    room_id: str,
    image: UploadFile = File(...),
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    updated_room = await update_room_image_service(room_id, current_user["user_uuid"], image)

    await manager.broadcast(
        room_id,
        {
            "type": "room_members_updated",
            "room_id": room_id,
            "members": updated_room.get("members", []),
        },
    )

    for member_uuid in updated_room.get("members", []):
        if member_uuid == current_user["user_uuid"]:
            continue
        await manager.send_user_notification(
            member_uuid,
            {
                "type": "notification",
                "event": "room_members_updated",
                "room_id": room_id,
                "room_name": updated_room.get("room_name") or "채팅방",
            },
        )

    return updated_room


@router.delete("/rooms/{room_id}/image")
async def delete_room_image(
    room_id: str,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    updated_room = delete_room_image_service(room_id, current_user["user_uuid"])

    await manager.broadcast(
        room_id,
        {
            "type": "room_members_updated",
            "room_id": room_id,
            "members": updated_room.get("members", []),
        },
    )

    for member_uuid in updated_room.get("members", []):
        if member_uuid == current_user["user_uuid"]:
            continue
        await manager.send_user_notification(
            member_uuid,
            {
                "type": "notification",
                "event": "room_members_updated",
                "room_id": room_id,
                "room_name": updated_room.get("room_name") or "채팅방",
            },
        )

    return updated_room


@router.get("/users/me/rooms")
def list_my_rooms(
    current_user: dict = Depends(get_current_user),
):
    return list_user_rooms_service(current_user["user_uuid"])