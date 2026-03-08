# Taskrit Chat Service

Taskrit 프로젝트의 **채팅 기능을 담당하는 마이크로서비스(Chat Service)** 입니다.  
사용자 인증이나 회원 관리 기능은 담당하지 않고, **메인 백엔드에서 전달받은 `user_uuid`를 기준으로 채팅 데이터만 처리합니다.**

---

# Chat Service Overview

이 서비스는 다음 기능을 담당합니다.

## Core Features

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

이 구조는 **마이크로서비스 아키텍처에서 채팅 서비스가 맡는 역할에 맞게 설계되었습니다.**

---

# User Identification

채팅 서비스는 사용자를 **`user_uuid` 기준으로 식별합니다.**

| Field | Description |
|------|-------------|
| user_uuid | 사용자 고유 식별자 (채팅 데이터 저장 기준) |
| user_id | 로그인용 ID |
| nickname | 화면 표시용 이름 |

채팅 서비스에서는 **사용자 이름을 직접 저장하지 않고 `user_uuid`만 저장합니다.**

이렇게 하면 사용자의 닉네임이 변경되어도  
**기존 채팅 기록에 자동으로 새로운 이름이 반영됩니다.**

---

# Current Storage (MVP)

현재 채팅 서비스는 **MongoDB 연결 전 단계의 MVP 구조**로,  
데이터를 메모리에 저장하고 있습니다.

```
users             → 테스트용 사용자 목록
rooms             → 채팅방 정보
messages          → 채팅방 메시지 목록
read_status       → 사용자 읽음 상태
room_message_seq  → 메시지 순서 관리
```

이 구조는 서버를 재시작하면 데이터가 초기화되지만  
**기능 테스트와 프론트엔드 연동에는 충분한 구조입니다.**

---

# Core API

채팅 서비스의 기본 기능은 다음 **5개의 핵심 API**로 구성됩니다.

## Create DM Room

```
POST /dm/rooms
```

1:1 채팅방 생성

---

## Create Team Room

```
POST /team/rooms
```

팀 채팅방 생성

---

## Send Message

```
POST /rooms/{room_id}/messages
```

채팅 메시지 전송

---

## Get Messages

```
GET /rooms/{room_id}/messages
```

채팅 메시지 조회

---

## Get User Rooms

```
GET /users/{user_uuid}/rooms
```

사용자가 참여한 채팅방 목록 조회

---

# Message Structure

채팅 메시지는 다음과 같은 구조를 가집니다.

```json
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
```

`seq` 필드는 **채팅 메시지 순서를 안정적으로 관리하기 위해 사용됩니다.**

---

# Message Pagination

메시지 조회 시 **Pagination을 지원합니다.**

```
GET /rooms/{room_id}/messages?limit=30
GET /rooms/{room_id}/messages?before={message_id}&limit=30
GET /rooms/{room_id}/messages?after={message_id}&limit=30
```

이 방식으로

- 최근 메시지 조회
- 이전 메시지 불러오기
- 새 메시지 자동 갱신

이 가능합니다.

---

# File Sharing

파일 전송 기능을 제공합니다.

## Upload File

```
POST /rooms/{room_id}/files
```

파일을 업로드하면 채팅 메시지 형태로 기록됩니다.

---

## Download File

```
GET /files/{saved_filename}
```

업로드된 파일 다운로드

파일 메시지가 삭제되면 **서버에 저장된 실제 파일도 함께 삭제됩니다.**

---

# Message Deletion

메시지는 완전히 삭제되지 않고 다음처럼 표시됩니다.

```
삭제된 메시지입니다.
```

이 방식은

- 대화 흐름 유지
- 메신저 UX 유지

를 위한 설계입니다.

---

# Read Status

사용자의 읽음 상태를 저장합니다.

```
POST /rooms/{room_id}/read
GET /rooms/{room_id}/read-status
```

읽음 상태는

```
user_uuid → 마지막으로 읽은 message_id
```

형태로 관리됩니다.

---

# Chat Room Expansion

기존 채팅방에서 새 팀 채팅방을 생성할 수 있습니다.

```
POST /rooms/{room_id}/team
```

기존 멤버 + 새 멤버로 **새로운 팀 채팅방을 생성합니다.**

---

# Realtime Strategy

현재 채팅은 **자동 새로고침(Polling) 방식**으로 동작합니다.

```
server.py   → 채팅 데이터 제공
index.html  → 일정 시간마다 메시지 조회
```

향후에는 **WebSocket 기반 실시간 채팅으로 확장 예정입니다.**

---

# Future Plan

- MongoDB 데이터 저장
- WebSocket 실시간 채팅
- JWT 인증 연동
- 메시지 알림 시스템

---

# Project Structure

```
Taskrit-Chatting
 ├ server.py
 ├ index.html
 ├ uploads/
 └ README.md
```

---

# Project Role

Taskrit 프로젝트에서 각 서비스는 다음 역할을 담당합니다.

```
Taskrit-backend   → 사용자 / 인증 / JWT
Taskrit-teaming   → 팀 매칭 / 임베딩
Taskrit-chatting  → 채팅 서비스
Taskrit-frontend  → 사용자 인터페이스
```
