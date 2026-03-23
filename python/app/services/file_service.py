import os
import shutil
import uuid
import io
from PIL import Image
from fastapi import HTTPException, UploadFile

from app.config import UPLOAD_DIR
from app.database import messages_collection
from app.services.room_service import get_room
from app.services.message_service import get_next_seq
from app.utils.common import now_iso
from app.utils.serializers import serialize_doc


async def upload_file_to_room_service(room_id: str, sender_uuid: str, file: UploadFile, optimize: bool = True):
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if sender_uuid not in room["members"]:
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="파일 이름이 없습니다.")

    # Read content
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="파일 크기는 10MB를 초과할 수 없습니다.")

    
    file_id = str(uuid.uuid4())
    filename = file.filename
    content_type = file.content_type or "application/octet-stream"

    # Image Optimization
    if optimize and content_type.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(content))
            
            # Skip optimization for animated GIFs to preserve animation
            if getattr(img, "is_animated", False):
                pass
            else:
                # Resize if too large (e.g., max width/height 1920)
                max_dimension = 1920
                if img.width > max_dimension or img.height > max_dimension:
                    img.thumbnail((max_dimension, max_dimension))
                
                output_buffer = io.BytesIO()
                
                # Convert to RGB if saving as JPEG
                if img.format == 'JPEG' or (img.format != 'PNG' and img.mode in ("RGBA", "P")):
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    img.save(output_buffer, format="JPEG", quality=85, optimize=True)
                    # Update filename extension if format changed
                    if not filename.lower().endswith(('.jpg', '.jpeg')):
                        filename = os.path.splitext(filename)[0] + ".jpg"
                        content_type = "image/jpeg"
                elif img.format == 'PNG':
                    img.save(output_buffer, format="PNG", optimize=True)
                else:
                    # Default fallback for other formats, try to save as original format
                    img.save(output_buffer, format=img.format)

                content = output_buffer.getvalue()

        except Exception as e:
            print(f"Image optimization failed: {e}")
            # Fallback to original content
            pass

    saved_filename = f"{file_id}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "seq": get_next_seq(room_id),
        "sender_uuid": sender_uuid,
        "text": filename,
        "message_type": "file",
        "mime_type": content_type,
        "is_deleted": False,
        "file_name": filename,
        "saved_filename": saved_filename,
        "file_url": f"/files/{saved_filename}",
        "created_at": now_iso()
    }

    # New message is unread for all other members until they mark room as read.
    msg["unread_member_count"] = max(len(room["members"]) - 1, 0)
    messages_collection.insert_one(msg)

    return {
        "message": "파일 업로드 성공",
        "message_data": serialize_doc(msg)
    }


def download_file_service(saved_filename: str):
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    return file_path