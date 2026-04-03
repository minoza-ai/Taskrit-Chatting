from pydantic import BaseModel
from typing import List


class CreateDMRoomRequest(BaseModel):
    room_name: str
    target_user_uuid: str


class CreateTeamRoomRequest(BaseModel):
    room_name: str
    members: List[str]


class CreateTeamFromRoomRequest(BaseModel):
    room_name: str
    new_members: List[str]


class AddRoomMembersRequest(BaseModel):
    new_members: List[str]