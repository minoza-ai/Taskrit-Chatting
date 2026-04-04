import os
import uuid
from io import BytesIO
from fastapi import HTTPException
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.database import rooms_collection, messages_collection, read_status_collection
from app.config import UPLOAD_DIR
from app.services.user_service import user_exists, find_user_by_uuid, resolve_user_uuid, get_user_identifiers_by_uuid
from app.utils.common import now_iso, make_dm_key
from app.utils.serializers import serialize_doc


MAX_ROOM_IMAGE_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
ROOM_IMAGE_TARGET_SIZE_BYTES = 900 * 1024
ROOM_IMAGE_MAX_EDGE_PIXELS = 1024
ROOM_IMAGE_START_QUALITY = 86
ROOM_IMAGE_MIN_QUALITY = 50


def _has_alpha_channel(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    if image.mode == "P" and "transparency" in image.info:
        return True
    return False


def _resolve_room_image_extension(content_type: str, original_ext: str) -> str:
    extension_by_content_type = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }

    normalized_original_ext = original_ext.lower()
    if normalized_original_ext == ".jpeg":
        normalized_original_ext = ".jpg"

    allowed_extensions = {".jpg", ".png", ".webp", ".gif"}
    if normalized_original_ext in allowed_extensions:
        return normalized_original_ext

    mapped_ext = extension_by_content_type.get(content_type, ".jpg")
    return mapped_ext if mapped_ext in allowed_extensions else ".jpg"


def _encode_room_image(image: Image.Image, target_format: str, keep_alpha: bool) -> bytes:
    working_image = image.convert("RGBA" if keep_alpha else "RGB")
    last_bytes = b""

    for quality in range(ROOM_IMAGE_START_QUALITY, ROOM_IMAGE_MIN_QUALITY - 1, -6):
        output_buffer = BytesIO()
        if target_format == "JPEG":
            working_image.convert("RGB").save(
                output_buffer,
                format="JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
            )
        else:
            working_image.save(
                output_buffer,
                format="WEBP",
                quality=quality,
                method=6,
            )

        candidate = output_buffer.getvalue()
        last_bytes = candidate
        if len(candidate) <= ROOM_IMAGE_TARGET_SIZE_BYTES:
            return candidate

    return last_bytes


def _optimize_room_image_content(content: bytes, content_type: str, original_ext: str) -> tuple[bytes, str]:
    try:
        with Image.open(BytesIO(content)) as opened_image:
            normalized_image = ImageOps.exif_transpose(opened_image)
            normalized_image.thumbnail(
                (ROOM_IMAGE_MAX_EDGE_PIXELS, ROOM_IMAGE_MAX_EDGE_PIXELS),
                Image.Resampling.LANCZOS,
            )

            has_alpha = _has_alpha_channel(normalized_image)
            target_format = "WEBP" if has_alpha else "JPEG"
            target_ext = ".webp" if has_alpha else ".jpg"
            optimized_content = _encode_room_image(normalized_image, target_format, has_alpha)

            if len(optimized_content) < len(content):
                return optimized_content, target_ext

            return content, _resolve_room_image_extension(content_type, original_ext)
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식입니다.") from exc


def room_exists(room_id: str) -> bool:
    return rooms_collection.find_one({"room_id": room_id}, {"_id": 1}) is not None


def get_room(room_id: str):
    return serialize_doc(rooms_collection.find_one({"room_id": room_id}))


def normalize_room_member_uuid(member_identifier: str | None) -> str | None:
    return resolve_user_uuid(member_identifier)


def get_room_member_uuids(room: dict | None) -> list[str]:
    if not room:
        return []

    normalized_member_uuids: list[str] = []
    for member_identifier in room.get("members", []):
        resolved_uuid = normalize_room_member_uuid(member_identifier)
        if resolved_uuid and resolved_uuid not in normalized_member_uuids:
            normalized_member_uuids.append(resolved_uuid)

    return normalized_member_uuids


def is_room_member(room: dict | None, user_uuid: str) -> bool:
    return user_uuid in get_room_member_uuids(room)


def create_dm_room_service(current_user_uuid: str, body):
    if not body.room_name.strip():
        raise HTTPException(status_code=400, detail="room_name은 비어 있을 수 없습니다.")

    if current_user_uuid == body.target_user_uuid:
        raise HTTPException(status_code=400, detail="자기 자신과는 1대1 채팅방을 만들 수 없습니다.")

    if not user_exists(current_user_uuid):
        raise HTTPException(status_code=404, detail="현재 사용자가 존재하지 않습니다.")

    target_user_uuid = resolve_user_uuid(body.target_user_uuid)
    if not target_user_uuid:
        raise HTTPException(status_code=404, detail=f"{body.target_user_uuid} 사용자가 존재하지 않습니다.")

    dm_key = make_dm_key(current_user_uuid, target_user_uuid)

    existing_room = rooms_collection.find_one(
        {"room_type": "dm", "dm_key": dm_key},
        {"_id": 0}
    )
    if existing_room:
        return existing_room

    room = {
        "room_id": str(uuid.uuid4()),
        "room_type": "dm",
        "room_name": body.room_name,
        "room_image_url": None,
        "dm_key": dm_key,
        "members": [current_user_uuid, target_user_uuid],
        "created_at": now_iso(),
        "created_by": current_user_uuid
    }

    rooms_collection.insert_one(room)
    return serialize_doc(room)


def create_team_room_service(current_user_uuid: str, body):
    if not body.room_name.strip():
        raise HTTPException(status_code=400, detail="room_name은 비어 있을 수 없습니다.")

    if not user_exists(current_user_uuid):
        raise HTTPException(status_code=404, detail="현재 사용자가 존재하지 않습니다.")

    normalized_members: list[str] = []
    for member_identifier in body.members:
        resolved_uuid = resolve_user_uuid(member_identifier)
        if resolved_uuid and resolved_uuid not in normalized_members:
            normalized_members.append(resolved_uuid)

    unique_members = list(dict.fromkeys(normalized_members))
    if current_user_uuid not in unique_members:
        unique_members.insert(0, current_user_uuid)

    if len(unique_members) < 2:
        raise HTTPException(status_code=400, detail="팀 채팅방은 최소 2명 이상이어야 합니다.")

    for member_uuid in unique_members:
        if not user_exists(member_uuid):
            raise HTTPException(status_code=404, detail=f"{member_uuid} 사용자가 존재하지 않습니다.")

    room = {
        "room_id": str(uuid.uuid4()),
        "room_type": "team",
        "room_name": body.room_name,
        "room_image_url": None,
        "members": unique_members,
        "created_at": now_iso(),
        "created_by": current_user_uuid
    }

    rooms_collection.insert_one(room)
    return serialize_doc(room)


def list_user_rooms_service(user_uuid: str):
    if not user_exists(user_uuid):
        raise HTTPException(status_code=404, detail="사용자가 존재하지 않습니다.")

    user_identifiers = get_user_identifiers_by_uuid(user_uuid)

    rooms = list(
        rooms_collection.find(
            {"members": {"$in": user_identifiers}},
            {"_id": 0}
        ).sort("created_at", -1)
    )

    enriched_rooms = []

    for room in rooms:
        room_id = room["room_id"]

        last_message_doc = messages_collection.find_one(
            {"room_id": room_id},
            sort=[("seq", -1)]
        )
        last_message_doc = serialize_doc(last_message_doc)

        room["last_message"] = None
        room["last_message_time"] = None
        room["unread_count"] = 0

        if last_message_doc:
            room["last_message"] = {
                "message_id": last_message_doc["message_id"],
                "text": last_message_doc["text"],
                "message_type": last_message_doc["message_type"],
                "sender_uuid": last_message_doc["sender_uuid"],
                "seq": last_message_doc["seq"],
            }
            room["last_message_time"] = last_message_doc["created_at"]

        read_status = read_status_collection.find_one(
            {"room_id": room_id, "user_uuid": user_uuid},
            {"_id": 0, "last_read_message_id": 1}
        )

        if read_status and read_status.get("last_read_message_id"):
            last_read_message = messages_collection.find_one(
                {
                    "room_id": room_id,
                    "message_id": read_status["last_read_message_id"]
                },
                {"_id": 0, "seq": 1}
            )

            if last_read_message:
                room["unread_count"] = messages_collection.count_documents(
                    {
                        "room_id": room_id,
                        "seq": {"$gt": last_read_message["seq"]},
                        "sender_uuid": {"$ne": user_uuid},
                    }
                )
            else:
                room["unread_count"] = messages_collection.count_documents(
                    {
                        "room_id": room_id,
                        "sender_uuid": {"$ne": user_uuid},
                    }
                )
        else:
            room["unread_count"] = messages_collection.count_documents(
                {
                    "room_id": room_id,
                    "sender_uuid": {"$ne": user_uuid},
                }
            )

        enriched_rooms.append(room)

    enriched_rooms.sort(
        key=lambda r: r.get("last_message_time") or r.get("created_at", ""),
        reverse=True
    )

    return enriched_rooms


def create_team_from_existing_room_service(room_id: str, current_user_uuid: str, body):
    base_room = get_room(room_id)
    if not base_room:
        raise HTTPException(status_code=404, detail="기존 채팅방이 없습니다.")

    if not user_exists(current_user_uuid):
        raise HTTPException(status_code=404, detail="현재 사용자가 존재하지 않습니다.")

    if not body.room_name.strip():
        raise HTTPException(status_code=400, detail="새 팀방 이름(room_name)은 비어 있을 수 없습니다.")

    if not is_room_member(base_room, current_user_uuid):
        raise HTTPException(status_code=403, detail="초대하는 사용자는 기존 채팅방 멤버여야 합니다.")

    new_members = get_room_member_uuids(base_room)

    for new_member_identifier in body.new_members:
        new_member_uuid = resolve_user_uuid(new_member_identifier)
        if not new_member_uuid:
            raise HTTPException(status_code=404, detail=f"{new_member_identifier} 사용자가 존재하지 않습니다.")
        if new_member_uuid not in new_members:
            new_members.append(new_member_uuid)

    if len(new_members) < 2:
        raise HTTPException(status_code=400, detail="팀 채팅방은 최소 2명 이상이어야 합니다.")

    new_room = {
        "room_id": str(uuid.uuid4()),
        "room_type": "team",
        "room_name": body.room_name,
        "room_image_url": None,
        "members": new_members,
        "created_at": now_iso(),
        "created_by": current_user_uuid,
        "created_from_room_id": room_id
    }

    rooms_collection.insert_one(new_room)
    return serialize_doc(new_room)


def add_members_to_room_service(room_id: str, current_user_uuid: str, body):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if not user_exists(current_user_uuid):
        raise HTTPException(status_code=404, detail="현재 사용자가 존재하지 않습니다.")

    if not is_room_member(room, current_user_uuid):
        raise HTTPException(status_code=403, detail="초대하는 사용자는 해당 채팅방의 멤버여야 합니다.")

    merged_members = get_room_member_uuids(room)
    added_count = 0
    added_member_uuids: list[str] = []

    for member_identifier in body.new_members:
        resolved_uuid = resolve_user_uuid(member_identifier)
        if not resolved_uuid:
            raise HTTPException(status_code=404, detail=f"{member_identifier} 사용자가 존재하지 않습니다.")
        if resolved_uuid not in merged_members:
            merged_members.append(resolved_uuid)
            added_count += 1
            added_member_uuids.append(resolved_uuid)

    if added_count == 0:
        room_with_meta = dict(room)
        room_with_meta["added_member_uuids"] = []
        return room_with_meta

    update_doc = {
        "members": merged_members,
    }

    # DM에 멤버를 추가하면 팀 채팅방으로 승격한다.
    if len(merged_members) > 2:
        update_doc["room_type"] = "team"

    rooms_collection.update_one({"room_id": room_id}, {"$set": update_doc})
    updated_room = get_room(room_id)
    updated_room["added_member_uuids"] = added_member_uuids
    return updated_room


def update_room_name_service(room_id: str, current_user_uuid: str, body):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if not user_exists(current_user_uuid):
        raise HTTPException(status_code=404, detail="현재 사용자가 존재하지 않습니다.")

    if not is_room_member(room, current_user_uuid):
        raise HTTPException(status_code=403, detail="채팅방 멤버만 이름을 변경할 수 있습니다.")

    if room.get("room_type") != "team":
        raise HTTPException(status_code=400, detail="단체 채팅방만 이름 변경이 가능합니다.")

    next_name = (body.room_name or "").strip()
    if not next_name:
        raise HTTPException(status_code=400, detail="room_name은 비어 있을 수 없습니다.")

    rooms_collection.update_one(
        {"room_id": room_id},
        {"$set": {"room_name": next_name}},
    )
    return get_room(room_id)


async def update_room_image_service(room_id: str, current_user_uuid: str, file: UploadFile):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if not user_exists(current_user_uuid):
        raise HTTPException(status_code=404, detail="현재 사용자가 존재하지 않습니다.")

    if not is_room_member(room, current_user_uuid):
        raise HTTPException(status_code=403, detail="채팅방 멤버만 사진을 변경할 수 있습니다.")

    if room.get("room_type") != "team":
        raise HTTPException(status_code=400, detail="단체 채팅방만 사진 변경이 가능합니다.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="파일 이름이 없습니다.")

    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일은 업로드할 수 없습니다.")

    if len(content) > MAX_ROOM_IMAGE_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="이미지 크기는 5MB를 초과할 수 없습니다.")

    original_ext = os.path.splitext(file.filename)[1].lower()
    optimized_content, extension = _optimize_room_image_content(content, content_type, original_ext)

    saved_filename = f"room_{room_id}_{uuid.uuid4().hex}{extension}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as fp:
        fp.write(optimized_content)

    _remove_room_image_file(room.get("room_image_url"))

    next_room_image_url = f"/files/{saved_filename}"
    rooms_collection.update_one(
        {"room_id": room_id},
        {"$set": {"room_image_url": next_room_image_url}},
    )

    return get_room(room_id)


def _remove_room_image_file(room_image_url: str | None):
    normalized_image_url = (room_image_url or "").strip()
    if not normalized_image_url.startswith("/files/"):
        return

    saved_filename = os.path.basename(normalized_image_url.removeprefix("/files/"))
    if not saved_filename:
        return

    file_path = os.path.join(UPLOAD_DIR, saved_filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass


def delete_room_image_service(room_id: str, current_user_uuid: str):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if not user_exists(current_user_uuid):
        raise HTTPException(status_code=404, detail="현재 사용자가 존재하지 않습니다.")

    if not is_room_member(room, current_user_uuid):
        raise HTTPException(status_code=403, detail="채팅방 멤버만 사진을 삭제할 수 있습니다.")

    if room.get("room_type") != "team":
        raise HTTPException(status_code=400, detail="단체 채팅방만 사진 삭제가 가능합니다.")

    _remove_room_image_file(room.get("room_image_url"))

    rooms_collection.update_one(
        {"room_id": room_id},
        {"$set": {"room_image_url": None}},
    )

    return get_room(room_id)


def get_dm_display_name_for_user(room: dict, current_user_uuid: str):
    """
    DM방에서 현재 사용자 관점의 표시될 이름을 반환합니다.
    DM인 경우 상대방의 이름으로 "{상대방}님과의 대화"를 반환합니다.
    Team방인 경우 원본 room_name을 반환합니다.
    """
    # Team 방이면 원본 room_name 반환
    if room.get("room_type") != "dm":
        return room.get("room_name") or "채팅방"

    # DM 방인 경우, 상대방의 UUID 찾기
    members = get_room_member_uuids(room)
    other_user_uuid = None

    for member_uuid in members:
        if member_uuid != current_user_uuid:
            other_user_uuid = member_uuid
            break

    if not other_user_uuid:
        return room.get("room_name") or "채팅방"

    # 상대방의 정보 조회
    other_user = find_user_by_uuid(other_user_uuid)
    if not other_user:
        return room.get("room_name") or "채팅방"

    # 상대방 이름으로 표시
    other_user_nickname = other_user.get("nickname", "사용자")
    return f"{other_user_nickname}님과의 대화"