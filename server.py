from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import uuid
import os
import shutil

app = FastAPI()

# =====================================
# 기본 설정
# =====================================

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =====================================
# 메모리 저장소
# =====================================
# 현재는 MVP용으로 메모리에 저장합니다.
# 나중에는 MongoDB로 바꾸면 됩니다.

users = [
    {
        "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": "john_doe",
        "nickname": "John"
    },
    {
        "user_uuid": "660e8400-e29b-41d4-a716-446655440111",
        "user_id": "alice_01",
        "nickname": "Alice"
    },
    {
        "user_uuid": "770e8400-e29b-41d4-a716-446655440222",
        "user_id": "bob_02",
        "nickname": "Bob"
    },
    {
        "user_uuid": "880e8400-e29b-41d4-a716-446655440333",
        "user_id": "charlie_03",
        "nickname": "Charlie"
    }
]

# 채팅방 저장
# key = room_id
rooms: Dict[str, Dict] = {}

# 메시지 저장
# key = room_id, value = 메시지 리스트
messages: Dict[str, List[Dict]] = {}

# 읽음 상태 저장
# key = room_id
# value = { user_uuid: last_read_message_id }
read_status: Dict[str, Dict[str, str]] = {}

# 채팅방별 메시지 순번 저장
# key = room_id, value = 마지막 메시지 번호
room_message_seq: Dict[str, int] = {}

# =====================================
# 요청 형식
# =====================================

class CreateDMRoomRequest(BaseModel):
    room_name: str
    user1_uuid: str
    user2_uuid: str


class CreateTeamRoomRequest(BaseModel):
    room_name: str
    creator_uuid: str
    members: List[str]


class SendMessageRequest(BaseModel):
    sender_uuid: str
    text: str


class ReadMessageRequest(BaseModel):
    user_uuid: str
    last_read_message_id: str


class DeleteMessageRequest(BaseModel):
    requester_uuid: str


class CreateTeamFromRoomRequest(BaseModel):
    creator_uuid: str
    room_name: str
    new_members: List[str]

# =====================================
# 도우미 함수
# =====================================

def now_iso() -> str:
    return datetime.now().isoformat()


def make_dm_key(a: str, b: str) -> str:
    return "|".join(sorted([a, b]))


def find_user_by_uuid(user_uuid: str):
    for user in users:
        if user["user_uuid"] == user_uuid:
            return user
    return None


def user_exists(user_uuid: str) -> bool:
    return find_user_by_uuid(user_uuid) is not None


def room_exists(room_id: str) -> bool:
    return room_id in rooms


def find_message_by_id(message_id: str):
    for room_id, room_messages in messages.items():
        for msg in room_messages:
            if msg["message_id"] == message_id:
                return msg, room_id
    return None, None

# =====================================
# 메인 페이지
# =====================================

@app.get("/")
def read_index():
    return FileResponse("index.html")

# =====================================
# 사용자 목록 조회
# =====================================

@app.get("/users")
def get_users():
    return users

# =====================================
# 1. 1대1 채팅방 생성
# POST /dm/rooms
# =====================================

@app.post("/dm/rooms")
def create_dm_room(body: CreateDMRoomRequest):
    if not body.room_name.strip():
        return {"error": "room_name은 비어 있을 수 없습니다."}

    if body.user1_uuid == body.user2_uuid:
        return {"error": "자기 자신과는 1대1 채팅방을 만들 수 없습니다."}

    if not user_exists(body.user1_uuid):
        return {"error": f"{body.user1_uuid} 사용자가 존재하지 않습니다."}

    if not user_exists(body.user2_uuid):
        return {"error": f"{body.user2_uuid} 사용자가 존재하지 않습니다."}

    dm_key = make_dm_key(body.user1_uuid, body.user2_uuid)

    # 같은 두 사용자 간 DM 방이 이미 있으면 기존 방 반환
    for room in rooms.values():
        if room["room_type"] == "dm" and room.get("dm_key") == dm_key:
            return room

    room_id = str(uuid.uuid4())

    room = {
        "room_id": room_id,
        "room_type": "dm",
        "room_name": body.room_name,
        "dm_key": dm_key,
        "members": [body.user1_uuid, body.user2_uuid],
        "created_at": now_iso(),
        "created_by": body.user1_uuid
    }

    rooms[room_id] = room
    messages[room_id] = []
    read_status[room_id] = {}
    room_message_seq[room_id] = 0

    return room

# =====================================
# 2. 팀 채팅방 생성
# POST /team/rooms
# =====================================

@app.post("/team/rooms")
def create_team_room(body: CreateTeamRoomRequest):
    if not body.room_name.strip():
        return {"error": "room_name은 비어 있을 수 없습니다."}

    if not user_exists(body.creator_uuid):
        return {"error": f"{body.creator_uuid} 사용자가 존재하지 않습니다."}

    if len(body.members) < 2:
        return {"error": "팀 채팅방은 최소 2명 이상이어야 합니다."}

    unique_members = list(dict.fromkeys(body.members))
    if body.creator_uuid not in unique_members:
        unique_members.insert(0, body.creator_uuid)

    for member_uuid in unique_members:
        if not user_exists(member_uuid):
            return {"error": f"{member_uuid} 사용자가 존재하지 않습니다."}

    room_id = str(uuid.uuid4())

    room = {
        "room_id": room_id,
        "room_type": "team",
        "room_name": body.room_name,
        "members": unique_members,
        "created_at": now_iso(),
        "created_by": body.creator_uuid
    }

    rooms[room_id] = room
    messages[room_id] = []
    read_status[room_id] = {}
    room_message_seq[room_id] = 0

    return room

# =====================================
# 3. 메시지 보내기
# POST /rooms/{room_id}/messages
# =====================================

@app.post("/rooms/{room_id}/messages")
def send_message(room_id: str, body: SendMessageRequest):
    if not room_exists(room_id):
        return {"error": "채팅방이 없습니다."}

    room = rooms[room_id]

    if not user_exists(body.sender_uuid):
        return {"error": "보내는 사용자가 존재하지 않습니다."}

    if body.sender_uuid not in room["members"]:
        return {"error": "이 사용자는 해당 채팅방 멤버가 아닙니다."}

    if not body.text.strip():
        return {"error": "메시지 내용은 비어 있을 수 없습니다."}

    room_message_seq[room_id] += 1

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "seq": room_message_seq[room_id],
        "sender_uuid": body.sender_uuid,
        "text": body.text,
        "message_type": "text",
        "is_deleted": False,
        "file_name": None,
        "saved_filename": None,
        "file_url": None,
        "created_at": now_iso()
    }

    messages[room_id].append(msg)
    return msg

# =====================================
# 4. 메시지 조회
# GET /rooms/{room_id}/messages
# =====================================

@app.get("/rooms/{room_id}/messages")
def list_messages(
    room_id: str,
    limit: int = 30,
    before: Optional[str] = None,
    after: Optional[str] = None
):
    """
    메시지 Pagination 조회

    사용 예시:
    1) 최근 메시지 30개
       GET /rooms/{room_id}/messages?limit=30

    2) 특정 메시지 이전 30개
       GET /rooms/{room_id}/messages?before={message_id}&limit=30

    3) 특정 메시지 이후 30개
       GET /rooms/{room_id}/messages?after={message_id}&limit=30
    """

    if not room_exists(room_id):
        return {"error": "채팅방이 없습니다."}

    if limit <= 0:
        return {"error": "limit는 1 이상이어야 합니다."}

    room_messages = messages[room_id]

    # seq 기준 정렬 (안정성 확보)
    sorted_messages = sorted(room_messages, key=lambda m: m["seq"])

    # before와 after를 동시에 쓰지 못하게 제한
    if before and after:
        return {"error": "before와 after는 동시에 사용할 수 없습니다."}

    # 기본: 최근 limit개
    if not before and not after:
        result = sorted_messages[-limit:]
        return result

    # before 기준
    if before:
        target_index = None

        for i, msg in enumerate(sorted_messages):
            if msg["message_id"] == before:
                target_index = i
                break

        if target_index is None:
            return {"error": "before에 해당하는 메시지를 찾을 수 없습니다."}

        result = sorted_messages[max(0, target_index - limit):target_index]
        return result

    # after 기준
    if after:
        target_index = None

        for i, msg in enumerate(sorted_messages):
            if msg["message_id"] == after:
                target_index = i
                break

        if target_index is None:
            return {"error": "after에 해당하는 메시지를 찾을 수 없습니다."}

        result = sorted_messages[target_index + 1: target_index + 1 + limit]
        return result
    
# =====================================
# 5. 사용자 채팅방 목록 조회
# GET /users/{user_uuid}/rooms
# =====================================

@app.get("/users/{user_uuid}/rooms")
def list_user_rooms(user_uuid: str):
    if not user_exists(user_uuid):
        return {"error": "사용자가 존재하지 않습니다."}

    result = []

    for room in rooms.values():
        if user_uuid in room["members"]:
            result.append(room)

    result.sort(key=lambda r: r["created_at"], reverse=True)
    return result

# =====================================
# 6. 메시지 삭제
# DELETE /messages/{message_id}
# =====================================

@app.delete("/messages/{message_id}")
def delete_message(message_id: str, body: DeleteMessageRequest):
    if not user_exists(body.requester_uuid):
        return {"error": "요청한 사용자가 존재하지 않습니다."}

    msg, room_id = find_message_by_id(message_id)

    if msg is None:
        return {"error": "메시지를 찾을 수 없습니다."}

    if msg["sender_uuid"] != body.requester_uuid:
        return {"error": "본인이 보낸 메시지만 삭제할 수 있습니다."}

    # 파일 메시지면 실제 파일도 삭제
    if msg.get("message_type") == "file":
        saved_filename = msg.get("saved_filename")
        if saved_filename:
            file_path = os.path.join(UPLOAD_DIR, saved_filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        msg["file_name"] = None
        msg["saved_filename"] = None
        msg["file_url"] = None

    msg["text"] = "삭제된 메시지입니다."
    msg["is_deleted"] = True
    msg["message_type"] = "deleted"

    return {"message": "메시지가 삭제 처리되었습니다."}

# =====================================
# 7. 파일 전송
# POST /rooms/{room_id}/files
# =====================================

@app.post("/rooms/{room_id}/files")
def upload_file_to_room(
    room_id: str,
    sender_uuid: str,
    file: UploadFile = File(...)
):
    if not room_exists(room_id):
        return {"error": "채팅방이 없습니다."}

    room = rooms[room_id]

    if not user_exists(sender_uuid):
        return {"error": "보내는 사용자가 존재하지 않습니다."}

    if sender_uuid not in room["members"]:
        return {"error": "이 사용자는 해당 채팅방 멤버가 아닙니다."}

    if not file.filename:
        return {"error": "파일 이름이 없습니다."}

    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    room_message_seq[room_id] += 1

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "seq": room_message_seq[room_id],
        "sender_uuid": sender_uuid,
        "text": file.filename,
        "message_type": "file",
        "is_deleted": False,
        "file_name": file.filename,
        "saved_filename": saved_filename,
        "file_url": f"/files/{saved_filename}",
        "created_at": now_iso()
    }

    messages[room_id].append(msg)

    return {
        "message": "파일 업로드 성공",
        "message_data": msg
    }

# =====================================
# 8. 파일 다운로드
# GET /files/{saved_filename}
# =====================================

@app.get("/files/{saved_filename}")
def download_file(saved_filename: str):
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    if not os.path.exists(file_path):
        return {"error": "파일을 찾을 수 없습니다."}

    original_name = saved_filename.split("_", 1)[1] if "_" in saved_filename else saved_filename

    return FileResponse(
        path=file_path,
        filename=original_name
    )

# =====================================
# 9. 읽음 표시
# POST /rooms/{room_id}/read
# =====================================

@app.post("/rooms/{room_id}/read")
def mark_room_as_read(room_id: str, body: ReadMessageRequest):
    if not room_exists(room_id):
        return {"error": "채팅방이 없습니다."}

    room = rooms[room_id]

    if not user_exists(body.user_uuid):
        return {"error": "사용자가 존재하지 않습니다."}

    if body.user_uuid not in room["members"]:
        return {"error": "이 사용자는 해당 채팅방 멤버가 아닙니다."}

    read_status[room_id][body.user_uuid] = body.last_read_message_id

    return {
        "message": "읽음 상태가 업데이트되었습니다.",
        "room_id": room_id,
        "user_uuid": body.user_uuid,
        "last_read_message_id": body.last_read_message_id
    }

# =====================================
# 10. 읽음 상태 조회
# GET /rooms/{room_id}/read-status
# =====================================

@app.get("/rooms/{room_id}/read-status")
def get_read_status(room_id: str):
    if not room_exists(room_id):
        return {"error": "채팅방이 없습니다."}

    return read_status[room_id]

# =====================================
# 11. 기존 방 기반 새 팀방 생성
# POST /rooms/{room_id}/team
# =====================================

@app.post("/rooms/{room_id}/team")
def create_team_from_existing_room(room_id: str, body: CreateTeamFromRoomRequest):
    if not room_exists(room_id):
        return {"error": "기존 채팅방이 없습니다."}

    if not user_exists(body.creator_uuid):
        return {"error": "creator_uuid 사용자가 존재하지 않습니다."}

    if not body.room_name.strip():
        return {"error": "새 팀방 이름(room_name)은 비어 있을 수 없습니다."}

    base_room = rooms[room_id]

    if body.creator_uuid not in base_room["members"]:
        return {"error": "초대하는 사용자는 기존 채팅방 멤버여야 합니다."}

    new_members = list(base_room["members"])

    for new_member_uuid in body.new_members:
        if not user_exists(new_member_uuid):
            return {"error": f"{new_member_uuid} 사용자가 존재하지 않습니다."}
        if new_member_uuid not in new_members:
            new_members.append(new_member_uuid)

    if len(new_members) < 2:
        return {"error": "팀 채팅방은 최소 2명 이상이어야 합니다."}

    new_room_id = str(uuid.uuid4())

    new_room = {
        "room_id": new_room_id,
        "room_type": "team",
        "room_name": body.room_name,
        "members": new_members,
        "created_at": now_iso(),
        "created_by": body.creator_uuid,
        "created_from_room_id": room_id
    }

    rooms[new_room_id] = new_room
    messages[new_room_id] = []
    read_status[new_room_id] = {}
    room_message_seq[new_room_id] = 0

    return new_room