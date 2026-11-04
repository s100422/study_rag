---
part: langchain
lesson: Postgres Checkpointer
order: 31
source_type: ipynb
tags: [langgraph, postgresql, checkpointer, postgressaver, postgresstore, thread_id, memory, psycopg]
source: C:\Users\tnwls\aim-ai-agent\langchain_\31-postgres-checkpointer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Postgres Checkpointer

## Postgres Checkpointer 요약
Postgres Checkpointer 레슨은 LangGraph의 `PostgresSaver`로 대화(State)를, `PostgresStore`로 사용자 프로필을 PostgreSQL에 저장해 커널을 재시작해도 대화와 프로필이 복원되는 챗봇을 만든다.

## LangGraph PostgreSQL 실습 1단계: 패키지 설치와 DB 생성
LangGraph PostgreSQL 저장에는 `langgraph-checkpoint-postgres`와 PostgreSQL 드라이버 `psycopg`가 필요하다.
```bash
pip install langgraph-checkpoint-postgres "psycopg[binary]"
```
실행 중인 PostgreSQL에서 실습용 DB를 먼저 만든다.
```sql
CREATE DATABASE langgraph_prac;
```
`.env`에는 DB 접속 정보를 개별 변수로 둔다(값은 노트에 적지 않는다).
```dotenv
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_DB=langgraph_prac
```

## LangGraph PostgreSQL 실습 2단계: 환경 변수로 DB_URI 만들기
DB 접속 URI는 `postgresql://사용자:비밀번호@호스트:포트/DB이름` 형식이다. 비밀번호에 특수문자가 있을 수 있으므로 `quote(..., safe="")`로 URI 인코딩한 뒤 조합한다.
```python
import os
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv(override=True)
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_NAME = os.getenv("POSTGRES_DB", "langgraph_prac")
if not POSTGRES_PASSWORD:
    raise ValueError(".env에 POSTGRES_PASSWORD를 설정하세요.")

user = quote(POSTGRES_USER, safe="")
password = quote(POSTGRES_PASSWORD, safe="")
db = quote(DB_NAME, safe="")
DB_URI = f"postgresql://{user}:{password}@localhost:5432/{db}"
```
- 비밀번호는 코드에 직접 쓰지 않고 `.env`에서만 읽는다.
- 모델은 `ChatGoogleGenerativeAI(model="gemini-3.6-flash")`를 쓴다.

## LangGraph PostgreSQL 연결 확인
psycopg로 접속해 현재 DB와 사용자를 조회하면 연결이 잘 되는지 확인할 수 있다.
```python
import psycopg

with psycopg.connect(DB_URI) as sql_conn:
    with sql_conn.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        database, user = cursor.fetchone()
        print("데이터베이스:", database)
        print("접속 사용자:", user)
```
```text
데이터베이스: langgraph_prac
접속 사용자: postgres
```

## LangGraph PostgresSaver Checkpointer 준비
`PostgresSaver`는 LangGraph 체크포인트(대화 State)를 PostgreSQL에 저장하는 Checkpointer다. psycopg 연결 객체 `conn`으로 만들고 이후 셀에서 재사용한다.
```python
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

conn = psycopg.connect(
    DB_URI,
    autocommit=True,       # 변경 사항 즉시 반영
    prepare_threshold=0,   # 첫 실행부터 준비된 쿼리 사용
    row_factory=dict_row,  # 조회 결과를 dict로 반환
)
checkpointer = PostgresSaver(conn)
checkpointer.setup()  # 체크포인트 테이블 생성
```
`setup()`이 만드는 테이블(PostgresSaver가 자동 관리):
- `checkpoints`: 체크포인트 상태 정보와 메타데이터
- `checkpoint_blobs`: 메시지 목록 등 State 값의 직렬화 데이터
- `checkpoint_writes`: 노드 실행 중 중간 결과. 복구 시 활용
- `checkpoint_migrations`: 테이블 스키마 변경 이력

## LangGraph PostgresSaver로 대화 저장하는 챗봇
`create_agent`에 `checkpointer=PostgresSaver`를 넘기면 대화가 PostgreSQL에 저장된다. 같은 `thread_id`로 호출하면 이전 메시지를 다시 보내지 않아도 대화가 이어진다.
```python
graph = create_agent(
    model=llm, tools=[],
    system_prompt="한국어로 간결하게 답하세요. 사용자 정보는 대화 기록에 근거해 답하고, 없으면 모른다고 말하세요.",
    checkpointer=checkpointer,
)
config = {"configurable": {"thread_id": "postgres-chat-demo2"}}

graph.invoke({"messages": [("human", "내 이름은 민수야. PostgreSQL을 공부하고 있어.")]}, config=config)
result = graph.invoke({"messages": [("human", "내 이름과 공부 중인 내용을 알려줘.")]}, config=config)
print(result["messages"][-1].text)
```
- 두 번째 질문에 모델이 첫 메시지의 이름과 "PostgreSQL을 공부 중"을 기억해 답했다.
- `thread_id`는 커널 재시작 후에도 같은 값을 써야 대화를 이어 갈 수 있다.

## LangGraph get_state로 저장된 대화 확인과 재시작 후 복원
LangGraph `graph.get_state(config)`는 해당 `thread_id`의 저장된 State를 PostgreSQL에서 읽는다.
```python
snapshot = graph.get_state(config)
for message in snapshot.values["messages"]:
    message.pretty_print()
```
커널 재시작 후 복원 순서: 환경 설정 → Checkpointer 준비 → 챗봇 생성 → `config` 정의 셀만 다시 실행하고, 대화 저장 셀은 실행하지 않는다.
```python
snapshot = graph.get_state(config)
if not snapshot.values.get("messages"):
    raise ValueError("저장된 대화가 없습니다. 대화 저장 실습과 thread_id를 확인하세요.")
result = graph.invoke({"messages": [("human", "내가 공부 중인 주제로 짧은 복습 문제를 하나 내줘.")]}, config=config)
```
- 재시작 후에도 이전 메시지가 출력되고, 모델이 PostgreSQL 관련 복습 문제를 낸다.

## LangGraph PostgresStore로 사용자 프로필 저장소 준비
`PostgresStore`는 namespace와 key로 구분한 JSON 데이터를 저장하는 장기 저장소로, `langgraph-checkpoint-postgres`에 포함되어 있다. Checkpointer와 같은 DB를 쓰지만 테이블은 따로이며, 연결도 별도로 만들어 재사용한다.
```python
from langgraph.store.postgres import PostgresStore

store_conn = psycopg.connect(DB_URI, autocommit=True, prepare_threshold=0, row_factory=dict_row)
store = PostgresStore(store_conn)
store.setup()
```
`setup()`이 만드는 테이블:
- `store`: namespace·key별 JSON 데이터. `prefix` 컬럼에 namespace 문자열, `value`는 JSONB 타입.
- `store_migrations`: 스키마 변경 이력.

SQL은 저장 내용 확인용으로만 쓰고, 저장·수정은 Store 메서드로 한다.

## LangGraph PostgresStore put과 get으로 프로필 저장·조회
LangGraph Store의 `put`은 namespace와 key로 값을 저장하며, 같은 namespace·key로 다시 저장하면 갱신된다. 저장된 값은 연결을 닫아도 PostgreSQL에 남는다.
```python
user_id = "user-001"
user_namespace = ("users", user_id)
store.put(namespace=user_namespace, key="profile",
          value={"name": "철수", "interest": "Python"})

profile = store.get(user_namespace, "profile")
if profile is None:
    raise ValueError("저장된 프로필이 없습니다.")
print(profile.namespace, profile.key, profile.value)
```
```text
('users', 'user-001') profile {'name': '철수', 'interest': 'Python'}
```
(출력은 세 줄을 한 줄로 합쳤다.)

## LangGraph 노드에서 Store 읽는 프로필 챗봇 그래프
LangGraph 노드 함수가 `config`, `store` 인자를 선언하면 실행 설정과 Store를 주입받는다. `user_id`로 프로필을 조회해 시스템 메시지에 넣는다.
```python
def memory_chatbot(state: MessagesState, config: RunnableConfig, store: BaseStore):
    user_id = config["configurable"]["user_id"]
    profile = store.get(("users", user_id), "profile")
    system = ("한국어로 간결하게 답하세요. "
              "사용자 정보는 제공된 프로필과 대화에 근거해 답하고, 없으면 모른다고 말하세요.")
    if profile:
        system += f"\n이름: {profile.value['name']}\n관심 분야: {profile.value['interest']}"
    else:
        system += "\n저장된 사용자 프로필이 없습니다."
    response = llm.invoke([SystemMessage(content=system), *state["messages"]])
    return {"messages": [response]}

profile_builder = StateGraph(MessagesState)
profile_builder.add_node("chatbot", memory_chatbot)
profile_builder.add_edge(START, "chatbot")
profile_builder.add_edge("chatbot", END)
profile_graph = profile_builder.compile(checkpointer=checkpointer, store=store)
```

## LangGraph Checkpointer와 Store 함께 사용하기
LangGraph에서 Checkpointer는 스레드(`thread_id`)별 대화를, Store는 사용자(`user_id`)별 장기 정보를 저장한다.
```python
profile_config = {"configurable": {"thread_id": "postgres-profile-chat", "user_id": "user-001"}}
result = profile_graph.invoke(
    {"messages": [("human", "나는 등산을 좋아해. 내 이름과 관심 분야도 알려줘.")]},
    config=profile_config,
)
```
- 이름·관심 분야는 Store에서 읽어 "철수, Python"으로 답한다.
- "등산을 좋아한다"는 정보는 Store가 아니라 이 스레드의 대화 State(Checkpointer)에만 저장된다. 호출 후에도 Store 프로필은 그대로다.

## LangGraph 재시작 후 기존 스레드와 새 스레드 비교
LangGraph에서 커널 재시작 후 같은 `user_id`로 기존 `thread_id`와 새 `thread_id`에 같은 질문을 하면 Store와 Checkpointer 차이가 드러난다. 재시작 후 환경 설정 → Checkpointer → Store → 그래프 → `profile_config` 셀만 다시 실행한다.
```python
new_profile_config = {"configurable": {
    "thread_id": f"postgres-profile-new-{uuid4().hex}", "user_id": user_id}}
print(profile_graph.get_state(new_profile_config).values)  # {}
question = "내 이름, 관심 분야, 취미를 알려줘. 모르는 정보는 모른다고 해줘."
for label, chat_config in [("기존 대화", profile_config), ("새 대화", new_profile_config)]:
    result = profile_graph.invoke({"messages": [("human", question)]}, config=chat_config)
    print(f"[{label}] {result['messages'][-1].text}")
```
(프로필·기존 State가 없으면 예외를 내는 확인 코드는 생략했다.)
- 기존 대화: 이름 철수, 관심 분야 Python, 취미 등산까지 답한다.
- 새 대화: 이름·관심 분야는 Store에서 읽어 답하지만, 취미는 그 스레드 대화에 없어 "모릅니다"라고 한다.

## LangGraph PostgreSQL 연결 종료
실습을 마치면 Checkpointer와 Store 연결을 닫는다. 커널을 종료하거나 재시작해도 연결은 끊기지만, PostgreSQL에 저장된 대화와 프로필은 남는다.
```python
conn.close()
store_conn.close()
```

## Postgres Checkpointer 복습 Q&A
- Q. LangGraph `PostgresSaver`와 `PostgresStore`는 무엇을 저장하나?
  A. `PostgresSaver`는 `thread_id`별 대화 State(체크포인트)를, `PostgresStore`는 namespace·key로 구분한 사용자 프로필 같은 장기 데이터를 저장한다.
- Q. `checkpointer.setup()`과 `store.setup()`은 언제 왜 호출하나?
  A. 처음 연결할 때 저장에 필요한 테이블(`checkpoints`, `store` 등)을 만들기 위해 호출한다.
- Q. DB_URI를 만들 때 사용자 이름과 비밀번호를 `quote(..., safe="")`로 감싸는 이유는?
  A. 특수문자가 URI 구분자(`@`, `:`, `/`)로 잘못 해석되지 않도록 URI 인코딩하기 위해서다.
- Q. 새 `thread_id`로 물으면 왜 이름은 알고 취미는 모르나?
  A. 이름은 `user_id` 기준 Store에 있어 어느 스레드에서나 읽히지만, 취미는 이전 스레드의 대화 State에만 있기 때문이다.
- Q. 커널 재시작 후 대화를 이어 가려면 무엇이 같아야 하나?
  A. 같은 DB에 연결하고 같은 `thread_id`를 써야 한다. 대화 저장 셀은 다시 실행하지 않는다.
