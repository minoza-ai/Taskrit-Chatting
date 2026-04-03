from fastapi import HTTPException

from app.database import messages_collection, read_status_collection
from app.services.room_service import get_room, room_exists
from app.utils.common import now_iso


def mark_room_as_read_service(room_id: str, user_uuid: str, last_read_message_id: str):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if user_uuid not in room["members"]:
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    target_msg = messages_collection.find_one(
        {"message_id": last_read_message_id, "room_id": room_id},
        {"_id": 0, "seq": 1}
    )
    if not target_msg:
        raise HTTPException(status_code=404, detail="last_read_message_id에 해당하는 메시지가 없습니다.")

    previous_doc = read_status_collection.find_one(
        {"room_id": room_id, "user_uuid": user_uuid},
        {"_id": 0, "last_read_message_id": 1},
    )
    previous_last_read_message_id = previous_doc.get("last_read_message_id") if previous_doc else None

    previous_last_read_seq = 0
    if previous_last_read_message_id:
        previous_msg = messages_collection.find_one(
            {"message_id": previous_last_read_message_id, "room_id": room_id},
            {"_id": 0, "seq": 1},
        )
        if previous_msg:
            previous_last_read_seq = int(previous_msg["seq"])

    current_last_read_seq = int(target_msg["seq"])
    is_changed = current_last_read_seq > previous_last_read_seq

    if is_changed:
        read_status_collection.update_one(
            {"room_id": room_id, "user_uuid": user_uuid},
            {
                "$set": {
                    "last_read_message_id": last_read_message_id,
                    "updated_at": now_iso()
                }
            },
            upsert=True
        )

    return {
        "message": "읽음 상태가 업데이트되었습니다.",
        "room_id": room_id,
        "user_uuid": user_uuid,
        "last_read_message_id": last_read_message_id,
        "last_read_seq": current_last_read_seq,
        "previous_last_read_seq": previous_last_read_seq,
        "is_changed": is_changed,
    }


def get_read_status_service(room_id: str):
    if not room_exists(room_id):
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    docs = list(
        read_status_collection.find(
            {"room_id": room_id},
            {"_id": 0, "user_uuid": 1, "last_read_message_id": 1}
        )
    )

    result = {}
    for doc in docs:
        result[doc["user_uuid"]] = doc["last_read_message_id"]

    return result