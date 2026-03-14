from fastapi import APIRouter
from app.schemas.room import (
    CreateDMRoomRequest,
    CreateTeamRoomRequest,
    CreateTeamFromRoomRequest,
)
from app.services.room_service import (
    create_dm_room_service,
    create_team_room_service,
    create_team_from_existing_room_service,
)

router = APIRouter(tags=["rooms"])

@router.post("/dm/rooms")
def create_dm_room(body: CreateDMRoomRequest):
    return create_dm_room_service(body.room_name, body.user1_uuid, body.user2_uuid)

@router.post("/team/rooms")
def create_team_room(body: CreateTeamRoomRequest):
    return create_team_room_service(body.room_name, body.creator_uuid, body.members)

@router.post("/rooms/{room_id}/team")
def create_team_from_existing_room(room_id: str, body: CreateTeamFromRoomRequest):
    return create_team_from_existing_room_service(
        room_id,
        body.creator_uuid,
        body.room_name,
        body.new_members
    )