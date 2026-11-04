---
part: backend
lesson: 멀티턴 챗봇과 체크포인트
order: 25
source_type: web
tags: [langgraph, checkpoint, asyncpostgressaver, thread_id, cursor-pagination, row-lock, astream_events, multiturn]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1469/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 멀티턴 챗봇과 체크포인트

## 멀티턴 챗봇과 체크포인트 요약
같은 채팅방에서 질문을 이어 가고 서버를 재시작해도 대화 맥락이 복원되는 챗봇을 만든다. 화면용 질문·답변 기록(chat_messages)과 Agent 실행 상태(LangGraph 체크포인트)를 따로 저장하고, 커서 페이지네이션·행 잠금·astream_events로 조회·동시성·도구 상태 표시를 다룬다.

## LangGraph 체크포인트와 체크포인터란
LangGraph 체크포인트는 그래프 실행 중 특정 시점의 상태를 저장한 것이다. 사용자 메시지와 최종 답변뿐 아니라 도구 호출·결과, 다음에 실행할 작업 정보까지 담기며, 질문 하나를 처리하는 동안에도 체크포인트가 여러 개 생긴다.

체크포인터는 이 상태를 저장하고 다시 읽는 객체로, Agent에 연결해 같은 대화의 상태를 불러와 후속 질문을 처리한다. 이 앱은 서버 프로세스가 꺼져도 상태가 남도록 PostgreSQL에 저장하는 `AsyncPostgresSaver`를 쓴다.

## 멀티턴 챗봇: 화면 기록, Agent 상태, LLM 컨텍스트 구분
멀티턴 챗봇에서는 대화 기록 보존과 LLM 입력 구성을 다른 문제로 보고 세 가지를 구분한다.
- 화면용 대화 기록: 사용자가 주고받은 질문과 최종 답변 원문. 다시 읽을 수 있게 시간순 저장.
- Agent 상태: 대화를 잇고 실행을 재개하는 데 필요한 데이터. 화면에 안 보이는 도구 호출·결과와 다음 작업 정보도 포함.
- LLM 컨텍스트: 이번 모델 호출에 실제로 넣는 입력(시스템 지시문, 이전 메시지, 새 질문, 도구 결과 등). Agent 상태로 구성하지만 체크포인트 실행 정보 전체를 그대로 보내지는 않는다.

## 멀티턴 챗봇에서 화면 기록을 따로 저장하는 이유
멀티턴 챗봇의 대화가 길어지면 전체 기록을 매번 LLM에 넣을 때 컨텍스트 길이 제한, 토큰 비용, 응답 시간 문제가 생긴다. 그래서 오래된 대화를 요약하거나 필요한 메시지만 골라 모델 입력을 줄인다.
- 예: 화면 기록엔 질문·답변 100개를 그대로 두고, LLM엔 오래된 대화 요약 + 최근 메시지 + 필요한 도구 결과만 보낸다.
- 화면 기록을 따로 저장하면 Agent 메시지 상태를 요약으로 바꿔도 화면에서는 원문을 계속 볼 수 있다.
- 반대로 Agent는 최종 답변에 드러나지 않은 도구 결과를 후속 질문에 활용할 수 있다.

## 멀티턴 챗봇 저장 위치: chat_rooms, chat_messages, 체크포인트 테이블
멀티턴 챗봇은 세 곳에 나눠 저장한다.
- `chat_rooms`: 소유자·제목, 확정한 `checkpoint_id` → 채팅방 관리와 다음 대화 시작점 선택.
- `chat_messages`: 사용자 질문과 최종 답변 원문 → 기록 보존과 화면 표시.
- 체크포인트 테이블: 메시지, 도구 호출·결과, 그래프 실행 상태 → Agent 상태와 맥락 복원.

구조: `ChatService` → `ChatRepository` → chat_rooms/chat_messages, 그리고 `ChatService` → 챗봇 Agent → `AsyncPostgresSaver` → 체크포인트 테이블.

두 저장소는 같은 PostgreSQL DB를 써도 연결과 트랜잭션이 별개다. 그래서 화면 기록 저장이 실패해도 체크포인트 저장이 자동으로 취소되지 않는다.

## LangGraph thread_id와 checkpoint_id의 역할
LangGraph 대화 상태를 복원하려면 "어느 대화"인지와 "그 대화의 어느 시점"인지를 구분해야 한다.
- `thread_id`: 체크포인트를 묶는 대화 식별자. 채팅방끼리 맥락이 섞이지 않게 한다.
- `checkpoint_id`: 한 대화 안의 특정 체크포인트 식별자. 화면 기록과 함께 저장에 성공한 시점부터 다음 대화를 시작하게 한다.

이 앱의 `ChatRoom.thread_id`는 `chat:{room.id}`다. 같은 방은 항상 같은 값, 방이 다르면 다른 값을 쓴다. 클라이언트는 방 ID와 새 질문만 보내고, 서버가 방 소유권을 확인한 뒤 `thread_id`와 `checkpoint_id`를 정한다. `thread_id` 자체에는 접근 권한 검사 기능이 없으므로 소유권 확인은 서버가 해야 한다.

## AsyncPostgresSaver 체크포인터를 lifespan에서 연결
FastAPI `src/fastapi_agent/main.py`의 lifespan 안에서 체크포인터를 준비한다. 대화 요청마다 상태를 읽고 쓰므로 서버가 도는 동안 연결이 열려 있어야 한다.
```python
# lifespan 내부의 체크포인터 초기화 부분
checkpoint_url = make_url(get_settings().database_url).set(drivername="postgresql")
async with AsyncPostgresSaver.from_conn_string(
    checkpoint_url.render_as_string(hide_password=False)
) as checkpointer:
    await checkpointer.setup()
    app.state.chat_agent = create_chat_agent(checkpointer)
    yield
```
- `make_url(...).set(drivername="postgresql")`: SQLAlchemy용 DB URL의 드라이버 이름을 일반 `postgresql`로 바꿔 체크포인터에 쓴다.
- `render_as_string(hide_password=False)`: 비밀번호를 가리지 않은 접속 문자열로 변환.
- `checkpointer.setup()`: 체크포인트 테이블 생성·준비.
- `yield`를 `async with` 안에 두어 요청 처리 중 연결을 유지하고, 앱 종료 시 블록을 벗어나며 연결이 정리된다.
- (강의 페이지에 내용 없이 `|`만 든 코드 블록이 하나 더 있는데, 편집 잔여물로 보인다.)

## Alembic 자동 변경 감지에서 체크포인트 테이블 제외
서비스 데이터 테이블은 Alembic이, 체크포인트 테이블은 `checkpointer.setup()`이 관리한다. 체크포인트 테이블은 SQLAlchemy `Base.metadata`에 없어서 Alembic autogenerate가 "불필요한 테이블"로 보고 삭제 코드를 만들 수 있으므로 감지 대상에서 뺀다.
```python
# alembic/env.py
def include_name(name, type_, parent_names):
    checkpoint_tables = {
        "checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"
    }
    return type_ != "table" or name not in checkpoint_tables
```
- `False`를 반환한 대상은 변경 감지에서 빠진다.
- 체크포인트 테이블 4개에만 `False`, 나머지에는 `True`가 된다.

## 채팅 메시지 조회: 커서 기반 페이지네이션 개념
채팅방을 열면 최근 대화부터 보여 주고, 요청할 때 더 오래된 기록을 불러오기 위해 커서 기반 페이지네이션을 쓴다. 커서는 다음 조회의 기준값으로, 이 API에서는 이번에 받은 가장 오래된 메시지 ID다.
- 오프셋 방식은 앞에서 몇 행을 건너뛸지 지정한다.
- 커서 방식은 기준값보다 이전/이후 데이터를 조회한다. `id < cursor`로 조회하므로 새 메시지가 추가돼도 기준이 밀리지 않고, ID가 연속일 필요도 없다.

요청·응답 값:
- `limit`(요청): 한 번에 받을 최대 개수.
- `cursor`(요청): 이 ID보다 작은 메시지 조회. 첫 요청엔 생략.
- `items`(응답): 이번 메시지들, 오래된 순.
- `next_cursor`(응답): 다음 요청에 보낼 cursor. 더 없으면 null.
- `has_more`(응답): 과거 기록이 더 있는지.

## 채팅 메시지 커서 페이지네이션 구현: find_messages와 get_messages
채팅 메시지 조회에서 `ChatRepository.find_messages()`는 커서 조건을 걸고 ID 내림차순으로 `limit + 1`개를 읽는다.
```python
statement = select(ChatMessage).where(ChatMessage.room_id == room_id)
if cursor is not None:
    statement = statement.where(ChatMessage.id < cursor)
result = await db.scalars(
    statement.order_by(ChatMessage.id.desc()).limit(limit + 1)
)
return result.all()
```
`ChatService.get_messages()`는 응답할 만큼 자른 뒤 화면용으로 순서를 뒤집는다.
```python
has_more = len(rows) > params.limit
page = rows[:params.limit]
return MessagePageResponse(
    items=[MessageResponse.model_validate(m) for m in reversed(page)],
    next_cursor=page[-1].id if has_more else None,
    has_more=has_more,
)
```
- `limit + 1`: 한 개 더 읽어 다음 페이지 존재 여부를 판단. 여분 1개는 다음 요청에서 다시 조회된다.
- `reversed(page)`: DB는 최신순, 화면은 오래된 순.
- `next_cursor`: 뒤집기 전 `page[-1].id` = 이번 응답의 가장 오래된 ID. `<` 조건이라 경계 메시지가 중복되지 않는다.

## 채팅 메시지 커서 페이지네이션 예시와 화면 이어 붙이기
채팅방에 ID 115~120 메시지가 있고 `limit=3`이면 다음처럼 동작한다.
- `/chat/rooms/{room_id}/messages?limit=3`: DB 조회 120, 119, 118, 117 → items 118, 119, 120 / `next_cursor` 118 / `has_more` true.
- `/chat/rooms/{room_id}/messages?limit=3&cursor=118`: DB 조회 117, 116, 115 → items 115, 116, 117 / `next_cursor` null / `has_more` false.

클라이언트는 첫 요청에 cursor를 빼고, 더 불러올 때 받은 `next_cursor`를 넘기며, `has_more`가 false면 멈춘다. 화면의 "이전 메시지 불러오기" 버튼은 과거 기록을 현재 목록 앞에 붙이고(118~120 앞에 115~117 → 115~120), `has_more`가 false면 버튼을 숨긴다.

## 멀티턴 챗봇 흐름 1: 새 채팅방 생성과 채팅방 열기
멀티턴 챗봇 화면은 "새 채팅" 버튼으로 방을 먼저 만든 뒤 그 방에서 질문한다. 기존 방을 고르면 저장된 방과 대화 상태를 그대로 쓴다.
- 새 채팅 시작: `POST /chat/rooms`, 본문 `{"title": "새 채팅"}`. 서버는 방 ID와 `thread_id`를 정하고 빈 체크포인트를 만든 뒤, 그 체크포인트 ID를 포함해 chat_rooms에 저장하고 방 ID를 반환한다.
- 채팅방 열기: `GET /chat/rooms/{room_id}`와 `GET /chat/rooms/{room_id}/messages?limit=30`. 방 정보와 화면용 메시지만 조회하고 Agent는 실행하지 않는다. 새 방이면 메시지가 비어 있다.
- 입력창에 글 작성: 요청 없음. 입력 중인 글은 화면에서만 관리하며 메시지·체크포인트를 저장하지 않는다.

## 멀티턴 챗봇 흐름 2: 질문 전송부터 저장 완료까지
멀티턴 챗봇에서 질문 하나는 다음 순서로 처리된다.
- 질문 전송: `POST /chat/rooms/{room_id}/messages/stream`, 본문 `{"content": "질문"}`. 방에 저장된 체크포인트에서 Agent를 실행하고, 단계마다 체크포인트를 저장하며 답변 조각과 도구 실행 이벤트를 보낸다.
- 답변 생성 완료: 같은 요청 안에서 질문·최종 답변을 chat_messages에 저장하고, 방의 `checkpoint_id`를 완료 상태의 ID로 갱신한다. 두 변경은 같은 SQLAlchemy 트랜잭션으로 커밋한다.
- 저장 완료: 같은 연결의 `done` 이벤트로 저장된 질문·답변을 돌려주고, 화면은 임시 메시지를 저장된 메시지로 교체한다.

이후 화면은 `GET /chat/rooms`로 방 목록을 갱신하고, 후속 질문은 같은 방의 스트리밍 API로 보내 갱신된 `checkpoint_id`에서 이어 간다.

## 멀티턴 챗봇 구현 시 주의점: 체크포인트와 화면 기록 저장 구분
멀티턴 챗봇 구현에서 구분해야 할 점:
- 체크포인트는 Agent 실행 중에, 화면용 메시지는 최종 답변을 얻은 뒤 저장한다. 연결·트랜잭션이 달라 화면 메시지 저장이 실패해도 체크포인트는 남을 수 있다.
- 방 생성 때 만드는 빈 체크포인트는 첫 질문이 실패했을 때의 시작점이다. 방 생성 시 모델 호출이나 빈 메시지 행 저장은 하지 않는다. 첫 질문의 화면 기록 저장이 실패하면 방의 `checkpoint_id`를 초기값으로 두어, 다음 질문이 화면에 없는 대화 상태를 이어받지 않게 한다.
- 질문 한 번엔 전송 API 하나만 호출한다. 일반 JSON용 `POST /chat/rooms/{room_id}/messages`와 스트리밍용 `/messages/stream`은 둘 다 실행과 저장을 하므로 연달아 부르지 않는다.
- 서버는 JWT·방 소유권을 확인하고 같은 방의 동시 실행을 잠금으로 막는다.
- 답변이 화면에 보이는 것과 저장 완료는 다르다. 저장 완료는 커밋 후 보내는 `done`으로 확인하고, 연결이 끊겨 불확실하면 메시지 조회 API로 확인한다.

## 멀티턴 챗봇: 확정된 checkpoint_id에서 새 질문 실행
멀티턴 챗봇의 `POST /chat/rooms/{room_id}/messages`는 `{"content": "질문"}`을 받고, Service가 방의 확정 체크포인트 위치와 새 사용자 메시지를 Agent에 넘긴다.
```python
config = {
    "configurable": {
        "thread_id": room.thread_id,
        "checkpoint_id": room.checkpoint_id,
    }
}
inputs = {"messages": [{"role": "user", "content": content}]}
result = await self.agent.ainvoke(inputs, config=config)
```
- `inputs`: 대화에 추가할 새 메시지만. 화면 기록 전체를 다시 넘길 필요가 없다.
- `config`: 복원할 상태의 위치. Agent는 지정 체크포인트의 메시지·도구 결과를 복원한 뒤 새 메시지를 붙인다.
- `thread_id`만 주면 최신 체크포인트를 불러오는데, 최신 상태엔 실패한 실행의 중간 기록이 남아 있을 수 있어 확정한 `checkpoint_id`도 함께 지정한다.

## 채팅방 동시 요청 문제: 트랜잭션과 잠금이 필요한 이유
채팅방 질문 처리에서 트랜잭션은 여러 DB 작업을 하나로 묶어 성공 시 커밋, 실패 시 롤백한다. 이 앱은 `async with db.begin()`으로 질문·답변 저장과 방의 `checkpoint_id` 변경을 묶는다. 하지만 트랜잭션만으로는 읽은 데이터를 독점하지 않아, 여러 요청이 같은 값을 읽고 동시에 작업을 시작할 수 있다.

잠금이 없을 때의 문제(체크포인트 ID를 cp-100 등으로 줄여 표기):
- 요청 A, B가 모두 cp-100에서 시작한다.
- A가 먼저 끝나 A 답변을 포함한 cp-101을 확정한다. B는 A 결과를 모른 채 계속 실행 중이다.
- B가 끝나 B 답변만 포함한 cp-102를 확정한다.

결과적으로 화면에는 A·B가 모두 저장돼도, 다음 대화가 쓰는 cp-102에는 A의 결과가 없다. 그래서 대화 실행·제목 변경·삭제 시 채팅방 행에 행 단위 잠금(row-level lock)을 건다.

## 채팅방 행 잠금: with_for_update(nowait=True)
채팅방 행 잠금은 `ChatRepository.find_room()`을 `lock=True`로 부를 때 조회문에 옵션을 붙여 건다.
```python
statement = statement.with_for_update(nowait=True)
```
- SQL에 `FOR UPDATE NOWAIT`가 붙는다. 쿼리 실행 시 조회한 행의 잠금을 얻고, 현재 트랜잭션이 끝날 때까지 유지한다.
- 다른 트랜잭션이 같은 행을 수정·삭제하거나 `FOR UPDATE`로 잠그려 하면 충돌한다.
- `FOR UPDATE`는 기본적으로 잠금이 풀릴 때까지 기다리지만, `nowait=True`는 바로 못 얻으면 즉시 오류를 낸다.
- PostgreSQL 행 잠금은 일반 SELECT를 막지 않으므로 기록 조회는 계속 된다.
- 같은 방의 대화 실행·제목 변경·삭제가 모두 이 행 잠금을 얻도록 해서 서로 겹치지 않게 한다. 다른 방의 행은 독립적으로 잠긴다.

## 채팅방 질문 처리 중 트랜잭션·잠금 범위와 409 CHAT_ROOM_BUSY
채팅방 질문 하나를 처리하는 동안 트랜잭션과 잠금은 다음과 같이 흐른다.
- 요청 시작: `async with db.begin()`으로 트랜잭션 시작.
- 방 조회: 소유한 방을 `FOR UPDATE NOWAIT`로 조회해 행 잠금 획득, `checkpoint_id` 읽기.
- Agent 실행: 잠금을 유지한 채 상태 복원과 답변 생성.
- 결과 저장: 질문·답변 저장과 방 `checkpoint_id` 변경.
- 정상 종료: 커밋 후 잠금 해제. 예외 종료: SQLAlchemy 트랜잭션 롤백 후 잠금 해제(체크포인터의 별도 트랜잭션까지 롤백되지는 않는다).

Service는 잠금 획득 실패를 409 `CHAT_ROOM_BUSY`로 바꿔 응답한다. A 처리 중 들어온 B는 Agent를 실행하지 않고 409를 받으며, A가 cp-101을 확정한 뒤 B를 다시 보내면 cp-101에서 시작한다. 이는 동시 실행을 막을 뿐, 요청을 대기열에 넣어 순서대로 처리하지는 않는다. 처리 동안 잠금과 SQLAlchemy 연결 하나가 유지된다.

## LangGraph astream stream_mode 종류와 astream_events 비교
LangGraph `astream()`과 `astream_events()`는 둘 다 그래프를 비동기로 돌리며 중간 정보를 준다. `astream()`은 `stream_mode`로 데이터 종류를 고르고, `astream_events(..., version="v2")`는 모델·도구·그래프 내부 실행 이벤트를 준다.
- `stream_mode="messages"`: 모델 메시지 조각과 메타데이터(도구 호출 인자 조각 포함 가능) → 답변 텍스트 실시간 표시.
- `stream_mode="updates"`: 노드 완료 시 반환한 상태 변경 → 도구 호출 요청과 결과 ToolMessage 확인.
- `stream_mode="values"`: 단계마다 전체 상태 → 누적 메시지 등 현재 상태 확인.
- `stream_mode="custom"`: 노드·도구가 직접 내보낸 데이터 → "문서 100개 중 30개 처리" 같은 진행 상황.
- `astream_events(version="v2")`: 모델·도구의 시작·스트리밍·종료 이벤트 → 도구별 실행 시작·종료와 답변 조각을 함께 표시.

`astream()`은 `stream_mode=["messages", "updates"]`처럼 여러 모드를 같이 쓸 수 있다. `astream_events`는 `event`, `name`, `run_id`, `data` 등이 든 딕셔너리를 주므로 `event` 값으로 구분한다. `version="v2"`는 이벤트 형식 버전이지 stream_mode가 아니다.

## 멀티턴 챗봇에서 astream_events를 쓰는 이유
멀티턴 챗봇 화면은 도구별로 "조회 중 → 완료" 상태를 보여 준다. `updates` 모드의 `tool_calls`나 `messages` 모드의 도구 호출 조각은 "도구를 실행하라"는 모델의 요청일 뿐, 실제 실행 시작·완료 알림이 아니다.
- `astream_events(version="v2")`의 `on_tool_start`/`on_tool_end`는 실제 도구 실행 시점을 주고, 같은 `run_id`로 시작과 종료를 짝지을 수 있다.
- 도구 코드에 진행 알림을 넣지 않아도 실행 상태를 표시할 수 있다.
- 도구 내부의 처리 개수·진행률까지 보이려면 도구에서 `get_stream_writer()`로 데이터를 내보내고 `astream()`의 `custom` 모드로 받는다.
- 표시할 정보에 맞춰 방식을 하나 고른다. 한 질문에 두 메서드를 각각 호출하면 그래프가 두 번 실행된다.

## 멀티턴 챗봇 스트리밍: astream_events를 SSE 이벤트로 변환
멀티턴 챗봇의 `POST /chat/rooms/{room_id}/messages/stream`은 `astream_events()`에서 필요한 이벤트만 골라 SSE 이벤트로 바꾼다.
- `on_chat_model_start` → "답변 생성 중" `status` 전송.
- `on_chat_model_stream` → 텍스트 조각을 `token`으로 전송.
- `on_tool_start` → 도구 실행 ID와 이름을 담아 `tool_start` 전송.
- `on_tool_end` → 도구 결과 상태에 따라 `tool_end` 또는 `tool_error` 전송.
- 최상위 그래프의 `on_chain_end` → 저장할 최종 메시지 목록(result) 확보.

(강의 본문은 이 대응표에서 끝나며, 변환 코드 자체는 페이지에 나오지 않는다.)

## 멀티턴 챗봇과 체크포인트 복습 Q&A
- Q. 멀티턴 챗봇에서 화면용 기록(chat_messages)과 LangGraph 체크포인트를 따로 두는 이유는?
  A. 화면 기록은 사용자가 읽을 질문·답변 원문 보존용이고, 체크포인트는 도구 결과·실행 정보까지 담은 Agent 상태 복원용이라 목적이 다르다. 따로 두면 LLM 입력을 요약해도 원문을 유지할 수 있다.
- Q. LangGraph에서 `thread_id`만 주지 않고 확정한 `checkpoint_id`도 지정하는 이유는?
  A. `thread_id`만 주면 최신 체크포인트를 쓰는데, 거기에 실패한 실행의 중간 기록이 남아 있을 수 있기 때문이다.
- Q. 채팅 메시지 커서 페이지네이션에서 `limit + 1`개를 조회하는 이유는?
  A. 하나 더 읽혀 오면 다음 페이지가 있다는 뜻이므로 `has_more`를 판단할 수 있다.
- Q. 채팅방 행 잠금 `with_for_update(nowait=True)`는 무엇을 막고, 잠금 실패 시 응답은?
  A. 같은 방의 동시 실행으로 체크포인트가 서로의 결과를 놓치는 것을 막는다. 잠금을 바로 못 얻으면 409 `CHAT_ROOM_BUSY`.
- Q. 도구별 "조회 중 → 완료" 표시에 `astream_events`가 적합한 이유는?
  A. `on_tool_start`/`on_tool_end`가 실제 도구 실행 시점을 알려 주고 `run_id`로 짝지을 수 있기 때문이다. `tool_calls`는 실행 요청일 뿐이다.
