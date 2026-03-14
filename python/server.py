from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from pymongo import MongoClient
from pymongo.collection import Collection
from dotenv import load_dotenv
import uuid
import os
import shutil

load_dotenv()

app = FastAPI()

# =====================================
# 기본 설정
# =====================================

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "chat_app")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

users_collection: Collection = db["users"]
rooms_collection: Collection = db["rooms"]
messages_collection: Collection = db["messages"]
read_status_collection: Collection = db["read_status"]

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


def serialize_doc(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


def serialize_docs(docs: List[dict]) -> List[dict]:
    result = []
    for doc in docs:
        doc.pop("_id", None)
        result.append(doc)
    return result


def find_user_by_uuid(user_uuid: str):
    return serialize_doc(users_collection.find_one({"user_uuid": user_uuid}))


def user_exists(user_uuid: str) -> bool:
    return users_collection.find_one({"user_uuid": user_uuid}, {"_id": 1}) is not None


def room_exists(room_id: str) -> bool:
    return rooms_collection.find_one({"room_id": room_id}, {"_id": 1}) is not None


def get_room(room_id: str):
    return serialize_doc(rooms_collection.find_one({"room_id": room_id}))


def find_message_by_id(message_id: str):
    msg = messages_collection.find_one({"message_id": message_id})
    if not msg:
        return None, None
    room_id = msg["room_id"]
    return serialize_doc(msg), room_id


def get_next_seq(room_id: str) -> int:
    last_msg = messages_collection.find_one(
        {"room_id": room_id},
        sort=[("seq", -1)]
    )
    return 1 if not last_msg else last_msg["seq"] + 1


def seed_users():
    seed_data = [
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

    for user in seed_data:
        if not users_collection.find_one({"user_uuid": user["user_uuid"]}):
            users_collection.insert_one(user)


def create_indexes():
    users_collection.create_index("user_uuid", unique=True)
    rooms_collection.create_index("room_id", unique=True)
    rooms_collection.create_index("dm_key")
    messages_collection.create_index("message_id", unique=True)
    messages_collection.create_index([("room_id", 1), ("seq", 1)])
    read_status_collection.create_index([("room_id", 1), ("user_uuid", 1)], unique=True)


@app.on_event("startup")
def startup_event():
    create_indexes()
    seed_users()

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
    users = list(users_collection.find({}, {"_id": 0}))
    return users

# =====================================
# 1. 1대1 채팅방 생성
# POST /dm/rooms
# =====================================

@app.post("/dm/rooms")
def create_dm_room(body: CreateDMRoomRequest):
    if not body.room_name.strip():
        raise HTTPException(status_code=400, detail="room_name은 비어 있을 수 없습니다.")

    if body.user1_uuid == body.user2_uuid:
        raise HTTPException(status_code=400, detail="자기 자신과는 1대1 채팅방을 만들 수 없습니다.")

    if not user_exists(body.user1_uuid):
        raise HTTPException(status_code=404, detail=f"{body.user1_uuid} 사용자가 존재하지 않습니다.")

    if not user_exists(body.user2_uuid):
        raise HTTPException(status_code=404, detail=f"{body.user2_uuid} 사용자가 존재하지 않습니다.")

    dm_key = make_dm_key(body.user1_uuid, body.user2_uuid)

    existing_room = rooms_collection.find_one(
        {"room_type": "dm", "dm_key": dm_key},
        {"_id": 0}
    )
    if existing_room:
        return existing_room

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

    rooms_collection.insert_one(room)
    return room

# =====================================
# 2. 팀 채팅방 생성
# POST /team/rooms
# =====================================

@app.post("/team/rooms")
def create_team_room(body: CreateTeamRoomRequest):
    if not body.room_name.strip():
        raise HTTPException(status_code=400, detail="room_name은 비어 있을 수 없습니다.")

    if not user_exists(body.creator_uuid):
        raise HTTPException(status_code=404, detail=f"{body.creator_uuid} 사용자가 존재하지 않습니다.")

    if len(body.members) < 2:
        raise HTTPException(status_code=400, detail="팀 채팅방은 최소 2명 이상이어야 합니다.")

    unique_members = list(dict.fromkeys(body.members))
    if body.creator_uuid not in unique_members:
        unique_members.insert(0, body.creator_uuid)

    for member_uuid in unique_members:
        if not user_exists(member_uuid):
            raise HTTPException(status_code=404, detail=f"{member_uuid} 사용자가 존재하지 않습니다.")

    room_id = str(uuid.uuid4())

    room = {
        "room_id": room_id,
        "room_type": "team",
        "room_name": body.room_name,
        "members": unique_members,
        "created_at": now_iso(),
        "created_by": body.creator_uuid
    }

    rooms_collection.insert_one(room)
    return room

# =====================================
# 3. 메시지 보내기
# POST /rooms/{room_id}/messages
# =====================================

@app.post("/rooms/{room_id}/messages")
def send_message(room_id: str, body: SendMessageRequest):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if not user_exists(body.sender_uuid):
        raise HTTPException(status_code=404, detail="보내는 사용자가 존재하지 않습니다.")

    if body.sender_uuid not in room["members"]:
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    if not body.text.strip():
        raise HTTPException(status_code=400, detail="메시지 내용은 비어 있을 수 없습니다.")

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "seq": get_next_seq(room_id),
        "sender_uuid": body.sender_uuid,
        "text": body.text,
        "message_type": "text",
        "is_deleted": False,
        "file_name": None,
        "saved_filename": None,
        "file_url": None,
        "created_at": now_iso()
    }

    messages_collection.insert_one(msg)
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
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit는 1 이상이어야 합니다.")

    if before and after:
        raise HTTPException(status_code=400, detail="before와 after는 동시에 사용할 수 없습니다.")

    # 기본: 최근 limit개
    if not before and not after:
        result = list(
            messages_collection.find(
                {"room_id": room_id},
                {"_id": 0}
            ).sort("seq", -1).limit(limit)
        )
        result.reverse()
        return result

    # before 기준
    if before:
        target_msg = messages_collection.find_one(
            {"message_id": before, "room_id": room_id},
            {"_id": 0, "seq": 1}
        )
        if not target_msg:
            raise HTTPException(status_code=404, detail="before에 해당하는 메시지를 찾을 수 없습니다.")

        target_seq = target_msg["seq"]

        result = list(
            messages_collection.find(
                {"room_id": room_id, "seq": {"$lt": target_seq}},
                {"_id": 0}
            ).sort("seq", -1).limit(limit)
        )
        result.reverse()
        return result

    # after 기준
    if after:
        target_msg = messages_collection.find_one(
            {"message_id": after, "room_id": room_id},
            {"_id": 0, "seq": 1}
        )
        if not target_msg:
            raise HTTPException(status_code=404, detail="after에 해당하는 메시지를 찾을 수 없습니다.")

        target_seq = target_msg["seq"]

        result = list(
            messages_collection.find(
                {"room_id": room_id, "seq": {"$gt": target_seq}},
                {"_id": 0}
            ).sort("seq", 1).limit(limit)
        )
        return result

# =====================================
# 5. 사용자 채팅방 목록 조회
# GET /users/{user_uuid}/rooms
# =====================================

@app.get("/users/{user_uuid}/rooms")
def list_user_rooms(user_uuid: str):
    if not user_exists(user_uuid):
        raise HTTPException(status_code=404, detail="사용자가 존재하지 않습니다.")

    result = list(
        rooms_collection.find(
            {"members": user_uuid},
            {"_id": 0}
        ).sort("created_at", -1)
    )
    return result

# =====================================
# 6. 메시지 삭제
# DELETE /messages/{message_id}
# =====================================

@app.delete("/messages/{message_id}")
def delete_message(message_id: str, body: DeleteMessageRequest):
    if not user_exists(body.requester_uuid):
        raise HTTPException(status_code=404, detail="요청한 사용자가 존재하지 않습니다.")

    msg, room_id = find_message_by_id(message_id)

    if msg is None:
        raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")

    if msg["sender_uuid"] != body.requester_uuid:
        raise HTTPException(status_code=403, detail="본인이 보낸 메시지만 삭제할 수 있습니다.")

    # 파일 메시지면 실제 파일도 삭제
    if msg.get("message_type") == "file":
        saved_filename = msg.get("saved_filename")
        if saved_filename:
            file_path = os.path.join(UPLOAD_DIR, saved_filename)
            if os.path.exists(file_path):
                os.remove(file_path)

    messages_collection.update_one(
        {"message_id": message_id},
        {
            "$set": {
                "text": "삭제된 메시지입니다.",
                "is_deleted": True,
                "message_type": "deleted",
                "file_name": None,
                "saved_filename": None,
                "file_url": None
            }
        }
    )

    return {"message": "메시지가 삭제 처리되었습니다."}

# =====================================
# 7. 파일 전송
# POST /rooms/{room_id}/files
# =====================================

@app.post("/rooms/{room_id}/files")
def upload_file_to_room(
    room_id: str,
    sender_uuid: str = Form(...),
    file: UploadFile = File(...)
):
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if not user_exists(sender_uuid):
        raise HTTPException(status_code=404, detail="보내는 사용자가 존재하지 않습니다.")

    if sender_uuid not in room["members"]:
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="파일 이름이 없습니다.")

    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "seq": get_next_seq(room_id),
        "sender_uuid": sender_uuid,
        "text": file.filename,
        "message_type": "file",
        "is_deleted": False,
        "file_name": file.filename,
        "saved_filename": saved_filename,
        "file_url": f"/files/{saved_filename}",
        "created_at": now_iso()
    }

    messages_collection.insert_one(msg)

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
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

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
    room = get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    if not user_exists(body.user_uuid):
        raise HTTPException(status_code=404, detail="사용자가 존재하지 않습니다.")

    if body.user_uuid not in room["members"]:
        raise HTTPException(status_code=403, detail="이 사용자는 해당 채팅방 멤버가 아닙니다.")

    # 메시지 존재 확인은 선택 사항이지만, 안전하게 체크
    target_msg = messages_collection.find_one(
        {"message_id": body.last_read_message_id, "room_id": room_id},
        {"_id": 1}
    )
    if not target_msg:
        raise HTTPException(status_code=404, detail="last_read_message_id에 해당하는 메시지가 없습니다.")

    read_status_collection.update_one(
        {"room_id": room_id, "user_uuid": body.user_uuid},
        {
            "$set": {
                "last_read_message_id": body.last_read_message_id,
                "updated_at": now_iso()
            }
        },
        upsert=True
    )

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
        raise HTTPException(status_code=404, detail="채팅방이 없습니다.")

    docs = list(
        read_status_collection.find(
            {"room_id": room_id},
            {"_id": 0, "user_uuid": 1, "last_read_message_id": 1}
        )
    )

    result = {}
    for doc in docs:
        result[doc["user_uuid"]] = doc["last_read_message_id"]

    return result

# =====================================
# 11. 기존 방 기반 새 팀방 생성
# POST /rooms/{room_id}/team
# =====================================

@app.post("/rooms/{room_id}/team")
def create_team_from_existing_room(room_id: str, body: CreateTeamFromRoomRequest):
    base_room = get_room(room_id)
    if not base_room:
        raise HTTPException(status_code=404, detail="기존 채팅방이 없습니다.")

    if not user_exists(body.creator_uuid):
        raise HTTPException(status_code=404, detail="creator_uuid 사용자가 존재하지 않습니다.")

    if not body.room_name.strip():
        raise HTTPException(status_code=400, detail="새 팀방 이름(room_name)은 비어 있을 수 없습니다.")

    if body.creator_uuid not in base_room["members"]:
        raise HTTPException(status_code=403, detail="초대하는 사용자는 기존 채팅방 멤버여야 합니다.")

    new_members = list(base_room["members"])

    for new_member_uuid in body.new_members:
        if not user_exists(new_member_uuid):
            raise HTTPException(status_code=404, detail=f"{new_member_uuid} 사용자가 존재하지 않습니다.")
        if new_member_uuid not in new_members:
            new_members.append(new_member_uuid)

    if len(new_members) < 2:
        raise HTTPException(status_code=400, detail="팀 채팅방은 최소 2명 이상이어야 합니다.")

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

    rooms_collection.insert_one(new_room)
    return new_room