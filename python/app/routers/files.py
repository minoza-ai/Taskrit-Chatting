from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import FileResponse

from app.dependencies import validate_room_member
from app.services.file_service import (
    upload_file_to_room_service,
    download_file_service,
)

router = APIRouter(tags=["files"])


from app.websocket.manager import manager


@router.post("/rooms/{room_id}/files")
async def upload_file_to_room(
    room_id: str,
    file: UploadFile = File(...),
    auth: dict = Depends(validate_room_member),
):
    current_user = auth["current_user"]
    result = upload_file_to_room_service(room_id, current_user["user_uuid"], file)

    # WebSocket 브로드캐스트 추가
    await manager.broadcast(
        room_id,
        {
            "type": "message",
            "data": result["message_data"],
            "sender": {
                "user_uuid": current_user["user_uuid"],
                "nickname": current_user["nickname"],
            },
        },
    )

    return result


@router.get("/files/{saved_filename}")
def download_file(saved_filename: str):
    file_path = download_file_service(saved_filename)
    original_name = saved_filename.split("_", 1)[1] if "_" in saved_filename else saved_filename
    return FileResponse(path=file_path, filename=original_name)