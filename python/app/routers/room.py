from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, validate_room_member
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
    list_user_rooms_service,
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
def add_members_to_room(
    room_id: str,
    body: AddRoomMembersRequest,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    return add_members_to_room_service(room_id, current_user["user_uuid"], body)


@router.patch("/rooms/{room_id}/name")
def update_room_name(
    room_id: str,
    body: UpdateRoomNameRequest,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    return update_room_name_service(room_id, current_user["user_uuid"], body)


@router.get("/users/me/rooms")
def list_my_rooms(
    current_user: dict = Depends(get_current_user),
):
    return list_user_rooms_service(current_user["user_uuid"])