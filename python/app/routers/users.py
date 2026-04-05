from fastapi import APIRouter, Query
from app.services.user_service import get_all_users, search_users
from app.services.room_service import list_user_rooms_service

router = APIRouter(tags=["users"])


@router.get("/users")
def get_users(
    query: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=10),
):
    if query and query.strip():
        return search_users(query=query, limit=limit)
    return get_all_users()


@router.get("/users/{user_uuid}/rooms")
def list_user_rooms(user_uuid: str):
    return list_user_rooms_service(user_uuid)