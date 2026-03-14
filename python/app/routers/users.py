from fastapi import APIRouter
from app.services.user_service import get_all_users
from app.services.room_service import list_user_rooms_service

router = APIRouter(tags=["users"])

@router.get("/users")
def get_users():
    return get_all_users()

@router.get("/users/{user_uuid}/rooms")
def list_user_rooms(user_uuid: str):
    return list_user_rooms_service(user_uuid)