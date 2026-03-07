from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

app = FastAPI()

# -----------------------------
# 데이터베이스 설정
# -----------------------------
DATABASE_URL = "sqlite:///./chat.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# -----------------------------
# 데이터베이스 모델
# -----------------------------
class RoomModel(Base):
    __tablename__ = "rooms"

    room_id = Column(String, primary_key=True, index=True)
    type = Column(String, nullable=False)
    dm_key = Column(String, nullable=False, unique=True, index=True)
    member1_id = Column(String, nullable=False)
    member2_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MessageModel(Base):
    __tablename__ = "messages"

    message_id = Column(String, primary_key=True, index=True)
    room_id = Column(String, nullable=False, index=True)
    sender_id = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def room_to_dict(room: RoomModel) -> dict:
    return {
        "room_id": room.room_id,
        "type": room.type,
        "dm_key": room.dm_key,
        "members": [room.member1_id, room.member2_id],
        "created_at": room.created_at.isoformat(),
    }

def message_to_dict(msg: MessageModel) -> dict:
    return {
        "message_id": msg.message_id,
        "room_id": msg.room_id,
        "sender_id": msg.sender_id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
    }

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
def create_dm_room(body: CreateDMRoomRequest, db: Session = Depends(get_db)):
    dm_key = make_dm_key(body.user1_id, body.user2_id)

    existing = db.query(RoomModel).filter(
        RoomModel.type == "dm",
        RoomModel.dm_key == dm_key
    ).first()

    if existing:
        return room_to_dict(existing)

    room = RoomModel(
        room_id=str(uuid.uuid4()),
        type="dm",
        dm_key=dm_key,
        member1_id=body.user1_id,
        member2_id=body.user2_id,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room_to_dict(room)

# -----------------------------
# 특정 사용자 채팅방 목록
# -----------------------------
@app.get("/users/{user_id}/rooms")
def list_user_rooms(user_id: str, db: Session = Depends(get_db)):
    rooms_result = db.query(RoomModel).filter(
        (RoomModel.member1_id == user_id) | (RoomModel.member2_id == user_id)
    ).all()
    return [room_to_dict(r) for r in rooms_result]

# -----------------------------
# 메시지 보내기
# -----------------------------
@app.post("/rooms/{room_id}/messages")
def send_message(room_id: str, body: SendMessageRequest, db: Session = Depends(get_db)):
    room = db.query(RoomModel).filter(RoomModel.room_id == room_id).first()

    if not room:
        return {"error": "채팅방이 없습니다."}

    if body.sender_id not in [room.member1_id, room.member2_id]:
        return {"error": "이 사용자는 이 채팅방 멤버가 아닙니다."}

    msg = MessageModel(
        message_id=str(uuid.uuid4()),
        room_id=room_id,
        sender_id=body.sender_id,
        text=body.text,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return message_to_dict(msg)

# -----------------------------
# 메시지 목록 보기
# -----------------------------
@app.get("/rooms/{room_id}/messages")
def list_messages(room_id: str, db: Session = Depends(get_db)):
    room = db.query(RoomModel).filter(RoomModel.room_id == room_id).first()

    if not room:
        return {"error": "채팅방이 없습니다."}

    msgs = db.query(MessageModel).filter(
        MessageModel.room_id == room_id
    ).order_by(MessageModel.created_at).all()
    return [message_to_dict(m) for m in msgs]