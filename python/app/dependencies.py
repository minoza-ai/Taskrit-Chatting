from fastapi import Depends, Header, HTTPException
from app.services.user_service import find_user_by_uuid
from app.services.room_service import get_room


def get_current_user_uuid(x_user_uuid: str | None = Header(default=None)):
    if not x_user_uuid:
        raise HTTPException(status_code=401, detail="X-User-UUID 헤더가 필요합니다.")
    return x_user_uuid


def get_current_user(user_uuid: str = Depends(get_current_user_uuid)):
    user = find_user_by_uuid(user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user

# def get_current_user(authorization: str | None = Header(default=None)):
#     if not authorization:
#         raise HTTPException(status_code=401, detail="Authorization 헤더가 필요합니다.")

#     # Bearer 토큰 파싱
#     # JWT 검증
#     # payload에서 user_uuid 추출
#     return {
#         "user_uuid": "...",
#         "nickname": "..."
#     }

def validate_room_member(room_id: str, user_uuid: str):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if user_uuid not in room["members"]:
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    return room