import os
import uuid
from typing import Optional
from fastapi import HTTPException

from app.database import messages_collection, read_status_collection
from app.services.room_service import get_room, room_exists
from app.config import UPLOAD_DIR
from app.utils.common import now_iso
from app.utils.serializers import serialize_doc


def find_message_by_id(message_id: str):
    msg = messages_collection.find_one({"message_id": message_id})

    if not msg:
        return None, None

    room_id = msg["room_id"]
    result = serialize_doc(msg)
    return result, room_id


def get_next_seq(room_id: str) -> int:
    last_msg = messages_collection.find_one(
        {"room_id": room_id},
        sort=[("seq", -1)]
    )

    next_seq = 1 if not last_msg else int(last_msg["seq"]) + 1
    return next_seq


def send_message_service(room_id: str, sender_uuid: str, text: str):
    room = get_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if sender_uuid not in room["members"]:
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    if text is None or not str(text).strip():
        raise HTTPException(status_code=400, detail="메시지 내용은 비어 있을 수 없습니다.")

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "seq": get_next_seq(room_id),
        "sender_uuid": sender_uuid,
        "text": text,
        "message_type": "text",
        "is_deleted": False,
        "file_name": None,
        "saved_filename": None,
        "file_url": None,
        "created_at": now_iso()
    }

    messages_collection.insert_one(msg)

    # New message is unread for all other members until they mark room as read.
    msg["unread_member_count"] = max(len(room["members"]) - 1, 0)

    return serialize_doc(msg)


def _get_last_read_seq_map(room_id: str) -> dict[str, int]:
    docs = list(
        read_status_collection.find(
            {"room_id": room_id},
            {"_id": 0, "user_uuid": 1, "last_read_message_id": 1},
        )
    )

    message_ids = [doc.get("last_read_message_id") for doc in docs if doc.get("last_read_message_id")]
    if not message_ids:
        return {}

    read_messages = list(
        messages_collection.find(
            {
                "room_id": room_id,
                "message_id": {"$in": message_ids},
            },
            {"_id": 0, "message_id": 1, "seq": 1},
        )
    )

    seq_by_message_id = {msg["message_id"]: int(msg["seq"]) for msg in read_messages}

    last_read_seq_by_user: dict[str, int] = {}
    for doc in docs:
        user_uuid = doc.get("user_uuid")
        last_read_message_id = doc.get("last_read_message_id")
        if not user_uuid or not last_read_message_id:
            continue
        last_read_seq_by_user[user_uuid] = seq_by_message_id.get(last_read_message_id, 0)

    return last_read_seq_by_user


def _attach_unread_member_count(room: dict, messages: list[dict]) -> list[dict]:
    if not messages:
        return messages

    members = room.get("members", [])
    last_read_seq_by_user = _get_last_read_seq_map(room["room_id"])

    for message in messages:
        unread_member_count = 0
        message_seq = int(message.get("seq", 0))
        sender_uuid = message.get("sender_uuid")

        for member_uuid in members:
            if member_uuid == sender_uuid:
                continue

            if last_read_seq_by_user.get(member_uuid, 0) < message_seq:
                unread_member_count += 1

        message["unread_member_count"] = unread_member_count

    return messages


def list_messages_service(
    room_id: str,
    limit: int = 30,
    before: Optional[str] = None,
    after: Optional[str] = None
):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit는 1 이상이어야 합니다.")

    if before and after:
        raise HTTPException(status_code=400, detail="before와 after는 동시에 사용할 수 없습니다.")

    if not before and not after:
        result = list(
            messages_collection.find(
                {"room_id": room_id},
                {"_id": 0}
            ).sort("seq", -1).limit(limit)
        )
        result.reverse()
        return _attach_unread_member_count(room, result)

    if before:
        target_msg = messages_collection.find_one(
            {"message_id": before, "room_id": room_id},
            {"_id": 0, "seq": 1}
        )

        if not target_msg:
            raise HTTPException(status_code=404, detail="before에 해당하는 메시지를 찾을 수 없습니다.")

        target_seq = target_msg["seq"]

        result = list(
            messages_collection.find(
                {"room_id": room_id, "seq": {"$lt": target_seq}},
                {"_id": 0}
            ).sort("seq", -1).limit(limit)
        )
        result.reverse()
        return _attach_unread_member_count(room, result)

    target_msg = messages_collection.find_one(
        {"message_id": after, "room_id": room_id},
        {"_id": 0, "seq": 1}
    )

    if not target_msg:
        raise HTTPException(status_code=404, detail="after에 해당하는 메시지를 찾을 수 없습니다.")

    target_seq = target_msg["seq"]

    result = list(
        messages_collection.find(
            {"room_id": room_id, "seq": {"$gt": target_seq}},
            {"_id": 0}
        ).sort("seq", 1).limit(limit)
    )

    return _attach_unread_member_count(room, result)


def delete_message_service(message_id: str, requester_uuid: str):
    msg, _ = find_message_by_id(message_id)

    if msg is None:
        raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")

    if msg["sender_uuid"] != requester_uuid:
        raise HTTPException(status_code=403, detail="본인이 보낸 메시지만 삭제할 수 있습니다.")

    if msg.get("message_type") == "file":
        saved_filename = msg.get("saved_filename")
        if saved_filename:
            file_path = os.path.join(UPLOAD_DIR, saved_filename)
            if os.path.exists(file_path):
                os.remove(file_path)

    messages_collection.update_one(
        {"message_id": message_id},
        {
            "$set": {
                "text": "삭제된 메시지입니다.",
                "is_deleted": True,
                "message_type": "deleted",
                "file_name": None,
                "saved_filename": None,
                "file_url": None
            }
        }
    )

    return {"message": "메시지가 삭제 처리되었습니다."}