from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List
from datetime import datetime
import uuid

app = FastAPI()


# -----------------------------
# 메모리 저장소
# -----------------------------
rooms: Dict[str, Dict] = {}
messages: Dict[str, List[Dict]] = {}

# 사용자 목록 예시
users = ["A", "B", "C", "D", "E"]

# -----------------------------
# 요청 형식
# -----------------------------
class CreateDMRoomRequest(BaseModel):
    user1_id: str
    user2_id: str

class SendMessageRequest(BaseModel):
    sender_id: str
    text: str

# -----------------------------
# 도우미 함수
# -----------------------------
def make_dm_key(a: str, b: str) -> str:
    return "|".join(sorted([a, b]))

# -----------------------------
# 메인 페이지
# -----------------------------
@app.get("/")
def read_index():
    return FileResponse("index.html")

# -----------------------------
# 사용자 목록
# -----------------------------
@app.get("/users")
def get_users():
    return users

# -----------------------------
# 1대1 채팅방 만들기
# -----------------------------
@app.post("/dm/rooms")
def create_dm_room(body: CreateDMRoomRequest):
    dm_key = make_dm_key(body.user1_id, body.user2_id)

    for room in rooms.values():
        if room["type"] == "dm" and room["dm_key"] == dm_key:
            return room

    room_id = str(uuid.uuid4())

    room = {
        "room_id": room_id,
        "type": "dm",
        "dm_key": dm_key,
        "members": [body.user1_id, body.user2_id],
        "created_at": datetime.now().isoformat()
    }

    rooms[room_id] = room
    messages[room_id] = []

    return room

# -----------------------------
# 특정 사용자 채팅방 목록
# -----------------------------
@app.get("/users/{user_id}/rooms")
def list_user_rooms(user_id: str):
    result = []
    for room in rooms.values():
        if user_id in room["members"]:
            result.append(room)
    return result

# -----------------------------
# 메시지 보내기
# -----------------------------
@app.post("/rooms/{room_id}/messages")
def send_message(room_id: str, body: SendMessageRequest):
    if room_id not in rooms:
        return {"error": "채팅방이 없습니다."}

    room = rooms[room_id]

    if body.sender_id not in room["members"]:
        return {"error": "이 사용자는 이 채팅방 멤버가 아닙니다."}

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "sender_id": body.sender_id,
        "text": body.text,
        "created_at": datetime.now().isoformat()
    }

    messages[room_id].append(msg)
    return msg

# -----------------------------
# 메시지 목록 보기
# -----------------------------
@app.get("/rooms/{room_id}/messages")
def list_messages(room_id: str):
    if room_id not in rooms:
        return {"error": "채팅방이 없습니다."}
    return messages[room_id]