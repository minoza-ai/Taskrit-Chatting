from pydantic import BaseModel
from typing import List


class CreateDMRoomRequest(BaseModel):
    room_name: str
    user1_uuid: str
    user2_uuid: str


class CreateTeamRoomRequest(BaseModel):
    room_name: str
    creator_uuid: str
    members: List[str]


class CreateTeamFromRoomRequest(BaseModel):
    creator_uuid: str
    room_name: str
    new_members: List[str]