```
# Taskrit Chat Service

Taskrit 프로젝트의 채팅 기능을 담당하는 마이크로서비스(Chat Service) 입니다.
사용자 인증이나 회원 관리 기능은 담당하지 않고,
메인 백엔드에서 전달받은 user_uuid를 기준으로 채팅 데이터만 처리합니다.

이 서비스는 FastAPI + MongoDB + WebSocket 기반으로 구현된 실시간 채팅 서버입니다.

--------------------------------------------------

Chat Service Overview

이 서비스는 다음 기능을 담당합니다.

Core Features

- 1:1 채팅방 생성
- 팀 채팅방 생성
- 메시지 전송
- 메시지 조회
- 채팅방 목록 조회
- 메시지 삭제 (삭제 표시 방식)
- 파일 업로드 / 다운로드
- 읽음 상태 관리
- 기존 채팅방 기반 팀 채팅방 생성
- 메시지 Pagination (대량 메시지 처리)
- WebSocket 기반 실시간 채팅
- 사용자 입장 / 퇴장 이벤트
- typing indicator
- reconnect resume

이 구조는 마이크로서비스 아키텍처에서 채팅 서비스가 맡는 역할에 맞게 설계되었습니다.

--------------------------------------------------

User Identification

채팅 서비스는 사용자를 user_uuid 기준으로 식별합니다.

Field        Description
----------------------------------------
user_uuid    사용자 고유 식별자 (채팅 데이터 저장 기준)
user_id      로그인용 ID
nickname     화면 표시용 이름

채팅 서비스에서는 사용자의 모든 채팅 데이터가 user_uuid 기준으로 저장됩니다.

이렇게 하면

- 사용자 닉네임 변경
- 계정 정보 수정

같은 변화가 있어도 채팅 기록에는 영향이 없습니다.

--------------------------------------------------

Database Structure

채팅 서비스는 MongoDB를 사용합니다.

Collections

users
rooms
messages
read_status

각 컬렉션의 역할은 다음과 같습니다.

Collection      Description
----------------------------------------
users           사용자 정보
rooms           채팅방 정보
messages        채팅 메시지
read_status     사용자 읽음 상태

--------------------------------------------------

Room Structure

채팅방 데이터 구조

{
  "room_id": "uuid",
  "room_name": "team chat",
  "members": ["user_uuid1", "user_uuid2"],
  "room_type": "dm | team",
  "created_at": "timestamp"
}

채팅방은 다음 두 가지 타입을 가집니다.

Type    Description
-------------------------
DM      1:1 채팅
TEAM    그룹 채팅

--------------------------------------------------

Message Structure

채팅 메시지는 다음과 같은 구조를 가집니다.

{
  "message_id": "uuid",
  "room_id": "room_id",
  "seq": 1,
  "sender_uuid": "user_uuid",
  "text": "message text",
  "message_type": "text",
  "is_deleted": false,
  "created_at": "timestamp"
}

Field           Description
----------------------------------------
message_id      메시지 고유 ID
room_id         채팅방 ID
seq             메시지 순서
sender_uuid     메시지 보낸 사용자
text            메시지 내용
message_type    text / file
is_deleted      삭제 여부
created_at      생성 시간

seq 필드는 채팅 메시지 순서를 안정적으로 관리하기 위해 사용됩니다.

--------------------------------------------------

Message Pagination

메시지 조회 시 Pagination을 지원합니다.

GET /rooms/{room_id}/messages?limit=30
GET /rooms/{room_id}/messages?before={message_id}&limit=30
GET /rooms/{room_id}/messages?after={message_id}&limit=30

이 방식으로

- 최근 메시지 조회
- 이전 메시지 불러오기
- 새 메시지 자동 갱신

이 가능합니다.

--------------------------------------------------

File Sharing

파일 전송 기능을 제공합니다.

Upload File
POST /rooms/{room_id}/files

파일을 업로드하면 채팅 메시지 형태로 저장됩니다.

Download File
GET /files/{saved_filename}

업로드된 파일 다운로드

파일 메시지가 삭제되면 서버에 저장된 실제 파일도 함께 삭제됩니다.

--------------------------------------------------

Message Deletion

메시지는 완전히 삭제되지 않고 다음처럼 표시됩니다.

삭제된 메시지입니다.

이 방식은

- 대화 흐름 유지
- 메신저 UX 유지

를 위한 설계입니다.

--------------------------------------------------

Read Status

사용자의 읽음 상태를 저장합니다.

POST /rooms/{room_id}/read
GET /rooms/{room_id}/read-status

읽음 상태는

user_uuid → 마지막으로 읽은 message_id

형태로 관리됩니다.

--------------------------------------------------

Realtime Chat (WebSocket)

실시간 채팅은 WebSocket을 사용합니다.

Connection Endpoint

/ws/rooms/{room_id}?token=...

지원 기능

- 실시간 메시지 전달
- 사용자 입장 이벤트
- 사용자 퇴장 이벤트
- typing indicator
- ping / pong 연결 유지
- reconnect resume

--------------------------------------------------

Connection Manager

WebSocket 연결은 다음 구조로 관리됩니다.

room_id
 └ connection_id
     ├ user_uuid
     └ websocket

특징

- 동일 사용자 다중 탭 지원
- 멀티 브라우저 접속 지원
- 안정적인 broadcast

--------------------------------------------------

Core API

채팅 서비스의 기본 기능은 다음 API로 구성됩니다.

Create DM Room
POST /dm/rooms

Create Team Room
POST /team/rooms

Send Message
POST /rooms/{room_id}/messages

Get Messages
GET /rooms/{room_id}/messages

Get User Rooms
GET /users/{user_uuid}/rooms

--------------------------------------------------

Environment Variables

.env

APP_NAME=chat-service
UPLOAD_DIR=uploads
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=chat_app

USER_API_BASE_URL=https://api.taskr.it
USER_ME_ENDPOINT=/user/me

--------------------------------------------------

Run Server

의존성 설치

pip install -r requirements.txt

서버 실행

uvicorn --app-dir python app.main:app --host 0.0.0.0 --port 8001 --reload

--------------------------------------------------

Project Structure

Taskrit-Chatting
 ├ python
 │ ├ app
 │ │ ├ main.py
 │ │ ├ config.py
 │ │ ├ database.py
 │ │ ├ dependencies.py
 │ │ ├ routers
 │ │ ├ schemas
 │ │ ├ services
 │ │ ├ websocket
 │ │ └ utils
 │ └ server.py
 ├ server.py
 ├ uploads
 ├ requirements.txt
 └ README.md

--------------------------------------------------

Architecture Role

이 서비스는 채팅 데이터 처리만 담당하는 마이크로서비스입니다.

Component        Role
----------------------------------------
Main Backend     회원가입 / 로그인 / JWT
Chat Service     채팅 데이터 처리
MongoDB          메시지 저장

즉

Frontend
   ↓
Main Backend (Auth)
   ↓ JWT
Chat Service
   ↓
MongoDB

구조로 동작합니다.

--------------------------------------------------

Future Plan

- Push Notification
- Message Reaction
- Message Search
- Chat Thread
- Message Edit
- WebSocket Scaling
- Redis Pub/Sub
```
