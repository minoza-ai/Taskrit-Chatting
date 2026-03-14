from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse
from app.services.file_service import (
    upload_file_to_room_service,
    get_file_path_service,
    get_original_filename,
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
    file_path = get_file_path_service(saved_filename)
    return FileResponse(
        path=file_path,
        filename=get_original_filename(saved_filename)
    )