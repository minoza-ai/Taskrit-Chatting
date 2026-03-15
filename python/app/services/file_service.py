import os
import shutil
import uuid
from fastapi import HTTPException, UploadFile

from app.config import UPLOAD_DIR
from app.database import messages_collection
from app.services.room_service import get_room
from app.services.user_service import user_exists
from app.services.message_service import get_next_seq
from app.utils.common import now_iso


def upload_file_to_room_service(room_id: str, sender_uuid: str, file: UploadFile):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if not user_exists(sender_uuid):
        raise HTTPException(status_code=404, detail="보내는 사용자가 존재하지 않습니다.")

    if sender_uuid not in room["members"]:
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="파일 이름이 없습니다.")

    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "seq": get_next_seq(room_id),
        "sender_uuid": sender_uuid,
        "text": file.filename,
        "message_type": "file",
        "is_deleted": False,
        "file_name": file.filename,
        "saved_filename": saved_filename,
        "file_url": f"/files/{saved_filename}",
        "created_at": now_iso()
    }

    messages_collection.insert_one(msg)

    return {
        "message": "파일 업로드 성공",
        "message_data": msg
    }


def download_file_service(saved_filename: str):
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    return file_path