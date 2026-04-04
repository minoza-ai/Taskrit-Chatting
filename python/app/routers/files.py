from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import FileResponse

from app.dependencies import validate_room_member
from app.services.file_service import (
    upload_file_to_room_service,
    download_file_service,
)
from app.services.room_service import get_room, get_dm_display_name_for_user

router = APIRouter(tags=["files"])


from app.websocket.manager import manager


@router.post("/rooms/{room_id}/files")
async def upload_file_to_room(
    room_id: str,
    file: UploadFile = File(...),
    optimize: bool = True,
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    result = await upload_file_to_room_service(room_id, current_user["user_uuid"], file, optimize)
    
    saved_message = result["message_data"]

    # WebSocket 브로드캐스트 추가
    await manager.broadcast(
        room_id,
        {
            "type": "message",
            "data": saved_message,
            "sender": {
                "user_uuid": current_user["user_uuid"],
                "nickname": current_user["nickname"],
            },
        },
    )
    
    # 2. Add push notification logic
    room = get_room(room_id)
    user_uuid = current_user["user_uuid"]
    
    if room:
      sender_profile_image = current_user.get("profile_image_url")
      if not sender_profile_image:
          from app.services.user_service import find_user_by_uuid
          sender = find_user_by_uuid(user_uuid)
          if sender:
              sender_profile_image = sender.get("profile_image_url")

      for member_uuid in room["members"]:
          if member_uuid == user_uuid:
              continue

          await manager.send_user_notification(
              member_uuid,
              {
                  "type": "notification",
                  "event": "new_message",
                  "room_id": room_id,
                  "room_name": get_dm_display_name_for_user(room, member_uuid),
                  "room_type": room.get("room_type"),
                  "room_image_url": room.get("room_image_url"),
                  "message": {
                      "message_id": saved_message["message_id"],
                      "text": "파일을 보냈습니다.",
                      "sender_uuid": user_uuid,
                      "sender_profile_image": sender_profile_image,
                      "created_at": saved_message["created_at"],
                      "message_type": "file",
                  },
              },
          )

    return result


@router.get("/files/{saved_filename}")
def download_file(saved_filename: str):
    file_path = download_file_service(saved_filename)
    original_name = saved_filename.split("_", 1)[1] if "_" in saved_filename else saved_filename
    return FileResponse(path=file_path, filename=original_name)