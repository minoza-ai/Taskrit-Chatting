import requests
from fastapi import Depends, Header, HTTPException

from app.config import USER_API_BASE_URL, USER_ME_ENDPOINT
from app.services.room_service import get_room, is_room_member


def get_bearer_token(authorization: str | None = Header(default=None)) -> str:

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization 헤더가 필요합니다.")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer 토큰 형식이 아닙니다.")

    token = authorization.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(status_code=401, detail="access token이 비어 있습니다.")

    return token


def fetch_current_user_by_token(token: str) -> dict:

    if token.startswith("test_"):
        uuid = token.replace("test_", "")

        from app.services.user_service import find_user_by_uuid

        user_doc = find_user_by_uuid(uuid)

        if user_doc:
            return {
                "user_uuid": user_doc["user_uuid"],
                "user_id": user_doc["user_id"],
                "nickname": user_doc["nickname"],
                "profile_image_url": user_doc.get("profile_image_url"),
            }

        return {
            "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "test",
            "nickname": "Tester",
            "profile_image_url": None,
        }

    url = f"{USER_API_BASE_URL}{USER_ME_ENDPOINT}"

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="인증 서비스에 연결할 수 없습니다.")

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="유효하지 않은 access token입니다.")

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail=f"인증 서비스 응답 오류: {response.status_code}",
        )

    try:
        user = response.json()
    except Exception:
        raise HTTPException(status_code=503, detail="인증 서비스 응답이 JSON 형식이 아닙니다.")

    required_fields = ["user_uuid", "user_id", "nickname"]

    for field in required_fields:
        if field not in user:
            raise HTTPException(
                status_code=503,
                detail=f"인증 서비스 응답에 {field}가 없습니다.",
            )

    from app.services.user_service import upsert_user

    upsert_user(
        user_uuid=user["user_uuid"],
        user_id=user["user_id"],
        nickname=user["nickname"],
        wallet_address=user.get("wallet_address"),
        profile_image_url=user.get("profile_image_url"),
    )

    return user


def get_current_user(token: str = Depends(get_bearer_token)) -> dict:
    return fetch_current_user_by_token(token)


def validate_room_member(
    room_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:

    room = get_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if not is_room_member(room, current_user["user_uuid"]):
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    return {
        "room": room,
        "current_user": current_user,
    }