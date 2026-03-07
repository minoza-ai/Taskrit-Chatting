# Taskrit-Chatting
1. 채팅 서비스가 맡는 역할 (범위)

server.py는 회원가입/로그인/JWT 발급은 하지 않고, 메인 백엔드가 넘겨주는 user_uuid 기준으로 채팅 데이터만 처리하는 구조입니다.
즉 이 서버는 다음만 책임집니다:

1대1 채팅방 생성
팀 채팅방 생성
메시지 전송
메시지 조회
채팅방 목록 조회
메시지 삭제(삭제 표시)
파일 업로드/다운로드
읽음 표시
기존 방 기반 새 팀방 생성
메시지 Pagination(메시지 ID 기반)

이 방향은 마이크로서비스 구조에서 “채팅 서비스”가 맡아야 할 범위와 잘 맞습니다.


2. 사용자 식별 기준을 user_uuid로 정리
3. 
처음에는 설명용으로 user_001, A, B 같은 값을 썼지만, 이후 메인 백엔드 문서(Taskrit-backend의 사용자 구조)를 보고 사용자 식별 기준을 user_uuid로 통일하기로 했습니다.
즉 지금 설계는 다음처럼 가는 게 맞다고 정리했습니다:

user_uuid = 고정 식별자 → 채팅방/메시지 저장의 기준
user_id = 로그인용 ID → 채팅 저장 기준 아님
nickname = 화면 표시 이름 → 나중에 언제든 바뀔 수 있음

그래서 채팅 메시지/채팅방 멤버는 이름이 아니라 user_uuid만 저장하고, 이름은 나중에 사용자 서비스에서 가져와 표시하는 구조로 가게 됩니다. 이 설계 덕분에 사용자 이름(닉네임)이 바뀌어도 기존 채팅 기록에 새 이름이 자동 반영되는 방향이 됩니다.


3. 메모리 저장 구조로 MVP 구성

현재는 MongoDB를 아직 붙이지 않고, 메모리 딕셔너리로 저장하는 MVP 단계입니다. 대략 이런 구조를 잡았습니다:

users : 예시 사용자 목록
rooms : 채팅방 정보
messages : 채팅방별 메시지 목록
read_status : 채팅방별 읽음 상태
room_message_seq : 채팅방별 메시지 순번

이 구조는 서버를 재시작하면 데이터가 날아가지만, 기능 검증과 화면 연동에는 충분한 상태입니다.


4. 기본 핵심 API 5개를 설계하고 구현 방향을 잡음

처음에 채팅 서비스의 뼈대 5개 API를 잡았습니다. 이 5개가 채팅 서비스의 최소 골격입니다.
POST /dm/rooms
→ 1대1 채팅방 생성

POST /team/rooms
→ 팀 채팅방 생성

POST /rooms/{room_id}/messages
→ 메시지 전송

GET /rooms/{room_id}/messages
→ 메시지 조회

GET /users/{user_uuid}/rooms
→ 사용자의 채팅방 목록 조회

여기에 더해 프론트 연동을 위해:
GET /users → 사용자 목록 조회
GET / → index.html 반환

도 들어가도록 정리했습니다.


5. 1대1 채팅방 생성 로직 (POST /dm/rooms)

1대1 채팅방은 방 이름을 생성자가 직접 입력하는 구조로 가기로 했습니다. 이때 두 사용자 간의 기존 1대1 방이 있으면 중복 생성하지 않고 기존 방을 반환하도록 dm_key를 두었습니다.

즉:
입력: room_name, user1_uuid, user2_uuid

처리:
자기 자신과는 1대1 방 생성 불가

사용자 존재 확인
dm_key로 기존 동일 DM 방 확인

결과:

없으면 새로 생성

있으면 기존 방 반환

이 설계로 1대1 방이 깔끔하게 유지됩니다.

6. 팀 채팅방 생성 로직 (POST /team/rooms)

팀방도 생성자가 방 이름을 직접 입력하는 구조로 잡았습니다.
요청에는 대략:

room_name

creator_uuid

members

가 들어가고, 서버는:

room_name이 비어 있지 않은지 확인

생성자 존재 확인

멤버가 최소 2명 이상인지 확인

생성자를 멤버 목록에 자동 포함

각 멤버의 존재 여부 확인

room_type = "team" 으로 새 방 생성

이렇게 처리하도록 정리했습니다.

7. 메시지 전송 (POST /rooms/{room_id}/messages)

메시지 전송 API는 채팅방 존재 여부, 사용자 존재 여부, 멤버 여부를 확인한 뒤 메시지를 저장합니다.
처음에는 단순히 message_id, sender_uuid, text 등을 저장했지만, 이후 메시지 순서 관리와 Pagination을 위해 seq를 붙이는 구조로 업그레이드했습니다.

즉 텍스트 메시지는 대략 이런 필드를 가집니다:

message_id

room_id

seq

sender_uuid

text

message_type = "text"

is_deleted = False

file_name = None

saved_filename = None

file_url = None

created_at

그리고 각 채팅방마다 room_message_seq[room_id] += 1 하면서 순번을 관리하도록 했습니다.

8. 메시지 조회 (GET /rooms/{room_id}/messages)를 Pagination 구조로 업그레이드

처음에는 채팅방의 메시지를 전부 반환하는 아주 단순한 구조였습니다.
하지만 나중에 “이건 실제 서비스에선 너무 비효율적이다”라고 정리하면서 메시지 ID 기반 Pagination을 넣기로 했습니다.

이제 조회 API는 다음을 지원하는 방향입니다:

limit : 한 번에 가져올 메시지 수

before : 특정 메시지보다 이전 메시지들

after : 특정 메시지보다 이후 메시지들

즉:

GET /rooms/{room_id}/messages?limit=30

GET /rooms/{room_id}/messages?before={message_id}&limit=30

GET /rooms/{room_id}/messages?after={message_id}&limit=30

형태로 사용할 수 있게 했습니다.
이렇게 하면:

처음 열 때 최근 30개만 가져오기

위로 스크롤할 때 이전 메시지 더 가져오기

자동 새로고침 때 새 메시지만 가져오기

가 가능해집니다. 이 구조는 실제 채팅 서비스 설계에 훨씬 가깝습니다.

9. 사용자 채팅방 목록 조회 (GET /users/{user_uuid}/rooms)

특정 사용자가 참여한 채팅방 목록을 돌려주는 API입니다.
이 API로 왼쪽 패널에:

내가 참여 중인 채팅방 목록

최근 만든 방

나중에는 최근 메시지 기준 정렬

같은 것을 보여줄 수 있게 됩니다.

현재 단계에서는:

사용자가 존재하는지 확인

rooms 중 해당 user_uuid가 멤버인 방만 필터링

created_at 기준으로 정렬

하는 구조를 잡았습니다.

10. 메시지 삭제 기능 추가 (DELETE /messages/{message_id})

메시지를 완전히 제거하는 대신 “삭제된 메시지입니다.”로 바꾸는 방식으로 설계를 정했습니다. 이유는:

대화 흐름 유지

실제 메신저 느낌

메시지가 있었다는 흔적 보존

로직은 대략:

요청한 사용자가 존재하는지 확인

해당 메시지를 찾기

본인이 보낸 메시지인지 확인

파일 메시지라면 실제 파일도 삭제

메시지 내용을 "삭제된 메시지입니다." 로 바꾸고

is_deleted = True

message_type = "deleted" 로 변경

즉, 텍스트 메시지든 파일 메시지든 “삭제된 메시지”로 바뀌고, 파일 메시지면 서버에 저장된 파일까지 같이 제거되도록 설계를 다듬었습니다.

11. 파일 업로드/다운로드 기능 추가

파일 전송은 단순 메시지와 별도로 다음을 하도록 정리했습니다.

업로드: POST /rooms/{room_id}/files

채팅방 존재 확인

사용자 존재 확인

멤버 여부 확인

실제 파일을 uploads/ 폴더에 저장

파일명 충돌을 막기 위해 saved_filename = {uuid}_{원래파일명} 구조 사용

채팅 메시지처럼 기록

파일 메시지는 대략 이런 구조를 갖습니다:

message_id

room_id

seq

sender_uuid

text = 원래 파일 이름

message_type = "file"

is_deleted = False

file_name

saved_filename

file_url = /files/{saved_filename}

created_at

다운로드: GET /files/{saved_filename}

실제 파일이 존재하는지 확인

원래 파일명으로 다운로드되게 처리

그리고 중요한 보완으로, 파일 메시지를 삭제하면 서버에 저장된 실제 파일도 삭제되도록 했습니다.

12. 읽음 표시 기능 추가 (POST /rooms/{room_id}/read)

읽음 표시는 메시지 하나하나에 읽음 수를 붙이는 대신, 우선 “이 사용자가 이 채팅방에서 어디까지 읽었는가” 를 저장하는 구조로 갔습니다.

즉 read_status[room_id][user_uuid] = last_read_message_id 같은 식으로 저장하고:

POST /rooms/{room_id}/read → 읽음 상태 업데이트

GET /rooms/{room_id}/read-status → 읽음 상태 조회

가 가능하도록 설계했습니다.

이 구조는 나중에:

안 읽은 메시지 수 계산

1 표시

마지막 읽은 위치 저장

에 활용할 수 있습니다.

13. 기존 방 기반 새 팀방 생성 (POST /rooms/{room_id}/team)

처음엔 “기존 채팅방에 다른 사람을 초대”하는 방식도 생각했지만, 나중에 기존 방에 멤버를 직접 추가하지 않고, 새 팀방을 생성하는 쪽이 더 좋다고 정리했습니다.

즉:

1대1 방은 그대로 보존

새 멤버를 추가하고 싶으면

기존 방 멤버 + 새 멤버로 새 팀방 생성

그리고 팀 이름은 초대한 사람이 직접 정하는 방식으로 설계했습니다.

요청에는 대략:

creator_uuid

room_name

new_members

가 들어가고, 서버는:

기존 방 존재 확인

생성자가 기존 방 멤버인지 확인

새 멤버 존재 여부 확인

기존 멤버 + 새 멤버를 합쳐서

새 team 방 생성

created_from_room_id 로 어느 방에서 파생됐는지 기록

하게 됩니다.

이 방향은 1대1 채팅방의 의미를 보존하고, 대화 맥락도 깔끔하게 분리할 수 있어 좋은 선택이었습니다.

14. 자동 새로고침 구조와 프론트 역할 정리

실시간 채팅처럼 보이게 하려면 두 가지가 필요하다고 정리했습니다.

상대방도 실제로 같은 서버에 접속해 있어야 함

메시지가 자동으로 갱신되어야 함

그리고 이 자동 갱신은 server.py가 혼자 하는 게 아니라,
서버는 최신 메시지를 반환하고, index.html이 2초마다 다시 묻는 구조로 정리했습니다.

즉:

server.py = 데이터를 주는 쪽

index.html = 주기적으로 다시 요청해서 화면 갱신하는 쪽

그래서 지금 설계는 **WebSocket 전 단계의 “자동 새로고침 기반 채팅”**에 맞춰져 있습니다.

15. 마이크로서비스 관점으로 정리

이 server.py는 단순 실습 파일이 아니라, 지금은 Taskrit 전체 서비스 안에서 “Chat Service” 역할을 하는 마이크로서비스를 향해 가고 있다고 정리했습니다.

즉 이 파일이 맡는 건:

사용자 인증 ❌

회원가입 ❌

JWT 발급 ❌

지갑 연결 ❌

팀 매칭 ❌

가 아니라,

채팅방

메시지

파일

읽음 상태

만 책임지는 독립 채팅 서비스입니다.

이 방향은:

Taskrit-backend (인증/사용자/메인 로직)

Taskrit-teaming (매칭/임베딩)

Taskrit-Chatting (채팅)

Taskrit-frontend (화면)

같이 기능별로 저장소를 분리해 개발 중인 팀 구조와도 잘 맞습니다.

16. MongoDB와의 관계

지금까지 만든 건 전부 메모리 저장입니다.
그래서 서버를 끄면 데이터가 날아갑니다.

하지만 메인 백엔드 문서를 보고:

메인 서비스가 MongoDB를 기준으로 가고 있고

채팅 서비스도 나중엔 MongoDB로 가는 것이 자연스럽다

고 정리했습니다.

즉 현재 server.py는 MongoDB 붙이기 전 단계의 MVP 채팅 서비스입니다.
MongoDB는 쉽게 말해:

채팅방

메시지

읽음 상태

파일 메타데이터

를 영구 저장하는 창고 역할을 하게 됩니다.
