from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.services.file_service import (
    upload_file_to_room_service,
    download_file_service,
)

router = APIRouter(tags=["files"])


@router.post("/rooms/{room_id}/files")
def upload_file_to_room(
    room_id: str,
    sender_uuid: str = Form(...),
    file: UploadFile = File(...)
):
    return upload_file_to_room_service(room_id, sender_uuid, file)


@router.get("/files/{saved_filename}")
def download_file(saved_filename: str):
    file_path = download_file_service(saved_filename)
    original_name = saved_filename.split("_", 1)[1] if "_" in saved_filename else saved_filename
    return FileResponse(path=file_path, filename=original_name)