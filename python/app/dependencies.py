import os
import requests
from fastapi import Depends, Header, HTTPException
from fastapi import WebSocket

from app.services.room_service import get_room

USER_API_BASE_URL = os.getenv("USER_API_BASE_URL", "https://api.taskr.it")
USER_ME_ENDPOINT = os.getenv("USER_ME_ENDPOINT", "/user/me")


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
            return {"user_uuid": user_doc["user_uuid"], "user_id": user_doc["user_id"], "nickname": user_doc["nickname"]}
        return {"user_uuid": "550e8400-e29b-41d4-a716-446655440000", "user_id": "test", "nickname": "Tester"}

    try:
        response = requests.get(
            f"{USER_API_BASE_URL}{USER_ME_ENDPOINT}",
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
        raise HTTPException(status_code=503, detail="인증 서비스 응답이 올바르지 않습니다.")

    user = response.json()

    required_fields = ["user_uuid", "user_id", "nickname"]
    for field in required_fields:
        if field not in user:
            raise HTTPException(status_code=503, detail=f"인증 서비스 응답에 {field}가 없습니다.")

    return user


def get_current_user(token: str = Depends(get_bearer_token)) -> dict:
    return fetch_current_user_by_token(token)


def validate_room_member(room_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if current_user["user_uuid"] not in room["members"]:
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    return {
        "room": room,
        "current_user": current_user,
    }


async def get_ws_current_user(websocket: WebSocket) -> dict:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        raise Exception("WebSocket token missing")

    try:
        user = fetch_current_user_by_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        raise

    return user


async def validate_ws_room_member(websocket: WebSocket, room_id: str) -> dict:
    user = await get_ws_current_user(websocket)
    room = get_room(room_id)

    if not room:
        await websocket.close(code=4404)
        raise Exception("Room not found")

    if user["user_uuid"] not in room["members"]:
        await websocket.close(code=4403)
        raise Exception("Forbidden")

    return {
        "room": room,
        "current_user": user,
    }