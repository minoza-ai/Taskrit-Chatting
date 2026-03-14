import uuid
from fastapi import HTTPException

from app.database import rooms_collection
from app.services.user_service import user_exists
from app.utils.common import now_iso, make_dm_key
from app.utils.serializers import serialize_doc

def room_exists(room_id: str) -> bool:
    return rooms_collection.find_one({"room_id": room_id}, {"_id": 1}) is not None

def get_room(room_id: str):
    return serialize_doc(rooms_collection.find_one({"room_id": room_id}))

def create_dm_room_service(room_name: str, user1_uuid: str, user2_uuid: str):
    if not room_name.strip():
        raise HTTPException(status_code=400, detail="room_name은 비어 있을 수 없습니다.")

    if user1_uuid == user2_uuid:
        raise HTTPException(status_code=400, detail="자기 자신과는 1대1 채팅방을 만들 수 없습니다.")

    if not user_exists(user1_uuid):
        raise HTTPException(status_code=404, detail=f"{user1_uuid} 사용자가 존재하지 않습니다.")

    if not user_exists(user2_uuid):
        raise HTTPException(status_code=404, detail=f"{user2_uuid} 사용자가 존재하지 않습니다.")

    dm_key = make_dm_key(user1_uuid, user2_uuid)

    existing_room = rooms_collection.find_one(
        {"room_type": "dm", "dm_key": dm_key},
        {"_id": 0}
    )
    if existing_room:
        return existing_room

    room = {
        "room_id": str(uuid.uuid4()),
        "room_type": "dm",
        "room_name": room_name,
        "dm_key": dm_key,
        "members": [user1_uuid, user2_uuid],
        "created_at": now_iso(),
        "created_by": user1_uuid
    }

    rooms_collection.insert_one(room)
    return room

def create_team_room_service(room_name: str, creator_uuid: str, members: list[str]):
    if not room_name.strip():
        raise HTTPException(status_code=400, detail="room_name은 비어 있을 수 없습니다.")

    if not user_exists(creator_uuid):
        raise HTTPException(status_code=404, detail=f"{creator_uuid} 사용자가 존재하지 않습니다.")

    if len(members) < 2:
        raise HTTPException(status_code=400, detail="팀 채팅방은 최소 2명 이상이어야 합니다.")

    unique_members = list(dict.fromkeys(members))
    if creator_uuid not in unique_members:
        unique_members.insert(0, creator_uuid)

    for member_uuid in unique_members:
        if not user_exists(member_uuid):
            raise HTTPException(status_code=404, detail=f"{member_uuid} 사용자가 존재하지 않습니다.")

    room = {
        "room_id": str(uuid.uuid4()),
        "room_type": "team",
        "room_name": room_name,
        "members": unique_members,
        "created_at": now_iso(),
        "created_by": creator_uuid
    }

    rooms_collection.insert_one(room)
    return room

def list_user_rooms_service(user_uuid: str):
    if not user_exists(user_uuid):
        raise HTTPException(status_code=404, detail="사용자가 존재하지 않습니다.")

    return list(
        rooms_collection.find(
            {"members": user_uuid},
            {"_id": 0}
        ).sort("created_at", -1)
    )

def create_team_from_existing_room_service(
    room_id: str,
    creator_uuid: str,
    room_name: str,
    new_members: list[str]
):
    base_room = get_room(room_id)
    if not base_room:
        raise HTTPException(status_code=404, detail="기존 채팅방이 없습니다.")

    if not user_exists(creator_uuid):
        raise HTTPException(status_code=404, detail="creator_uuid 사용자가 존재하지 않습니다.")

    if not room_name.strip():
        raise HTTPException(status_code=400, detail="새 팀방 이름(room_name)은 비어 있을 수 없습니다.")

    if creator_uuid not in base_room["members"]:
        raise HTTPException(status_code=403, detail="초대하는 사용자는 기존 채팅방 멤버여야 합니다.")

    merged_members = list(base_room["members"])

    for member_uuid in new_members:
        if not user_exists(member_uuid):
            raise HTTPException(status_code=404, detail=f"{member_uuid} 사용자가 존재하지 않습니다.")
        if member_uuid not in merged_members:
            merged_members.append(member_uuid)

    if len(merged_members) < 2:
        raise HTTPException(status_code=400, detail="팀 채팅방은 최소 2명 이상이어야 합니다.")

    new_room = {
        "room_id": str(uuid.uuid4()),
        "room_type": "team",
        "room_name": room_name,
        "members": merged_members,
        "created_at": now_iso(),
        "created_by": creator_uuid,
        "created_from_room_id": room_id
    }

    rooms_collection.insert_one(new_room)
    return new_room