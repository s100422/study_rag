---
part: langchain
lesson: Memory & State 관리
order: 13
source_type: ipynb
tags: [langgraph, memory, checkpointer, memorysaver, thread-id, store, summarization, trim-messages]
source: C:\Users\tnwls\aim-ai-agent\langchain_\13-memory-state_answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Memory & State 관리

## Memory & State 관리 요약
LangGraph에서 대화를 이어가기 위해 Checkpointer(`MemorySaver`, 단기 메모리)로 `thread_id`별 State를 저장·복원하고, Store(`InMemoryStore`, 장기 메모리)로 대화 스레드를 넘어 사용자 정보를 공유하는 방법을 배운다. 대화가 길어지면 `trim_messages`와 `RemoveMessage`로 오래된 메시지를 요약해 토큰을 줄인다.

## LangGraph Memory 실습용 기본 챗봇 그래프
LangGraph Memory 실습의 출발점은 `MessagesState` 하나와 LLM 노드 하나로 된 챗봇이다.
```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, MessagesState, StateGraph

llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")

def simple_chatbot(state: MessagesState):
    return {"messages": [llm.invoke(state["messages"])]}

simple_builder = StateGraph(MessagesState)
simple_builder.add_node("chatbot", simple_chatbot)
simple_builder.add_edge(START, "chatbot")
simple_builder.add_edge("chatbot", END)
```
- 이 그래프를 checkpointer 없이 컴파일하면 `invoke()`할 때마다 State가 새로 시작된다. "나는 철수야" 다음 호출에서 "내가 누구라고?"를 물어도 모른다.

## LangGraph Checkpointer와 Saver란
LangGraph Checkpointer는 그래프 State의 스냅샷을 저장하고 복원하는 기능이다. 실행 시작 시점과 각 노드 실행 후에 State를 저장하고, 같은 `thread_id`로 다시 호출하면 저장된 State에 이어서 실행한다.

Saver는 Checkpointer가 만든 스냅샷을 실제로 저장하는 구현체다. 저장 위치에 따라 메모리, SQLite, PostgreSQL 등을 고를 수 있고, 어떤 Saver든 `thread_id`로 상태 이력을 구분한다. 실습에서는 메모리에 저장하는 `MemorySaver`를 쓴다(프로세스가 끝나면 사라진다 — 내 메모).

## LangGraph Checkpointer 실습: thread_id로 대화 이어가기
LangGraph 그래프를 `compile(checkpointer=MemorySaver())`로 컴파일하고, 호출할 때 `config`의 `configurable.thread_id`로 대화 세션을 지정한다.
```python
from langgraph.checkpoint.memory import MemorySaver

graph_with_memory = simple_builder.compile(checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "session-1"}}

graph_with_memory.invoke(
    {"messages": [("human", "내 이름은 철수야. 반가워!")]}, config=config)
result = graph_with_memory.invoke(
    {"messages": [("human", "내 이름이 뭐라고 했지?")]}, config=config)
# 같은 thread_id → 이전 대화를 기억해 "철수"라고 답한다

config2 = {"configurable": {"thread_id": "session-2"}}
graph_with_memory.invoke(
    {"messages": [("human", "내 이름이 뭐야?")]}, config=config2)
# 다른 thread_id → 별도 세션이라 이름을 모른다
```
- 새 입력 메시지는 `add_messages` Reducer로 저장된 기록 뒤에 붙으므로 매번 새 질문만 넘기면 된다.

## LangGraph 저장된 State 조회: get_state와 get_state_history
LangGraph Checkpointer가 저장한 State는 `get_state(config)`로 해당 `thread_id`의 최신 State를, `get_state_history(config)`로 과거 스냅샷 전체를 볼 수 있다. 실제 데이터는 `.values`에 있다.
```python
state = graph_with_memory.get_state(config)
print(f"저장된 메시지 수: {len(state.values['messages'])}")
for msg in state.values["messages"]:
    print(f"  [{msg.type}] {msg.text}")

history = list(graph_with_memory.get_state_history(config))
for index, snapshot in enumerate(history):
    print(f"\n[스냅샷 {index}]")
    for msg in snapshot.values.get("messages", []):
        print(f"  [{msg.type}] {msg.text}")
```
- `get_state_history()`는 iterator를 반환하며 최신 스냅샷부터 나온다.

## LangGraph Store란: Long-term Memory
LangGraph Store는 대화 스레드를 넘어 사용자 정보 등을 저장하는 Long-term Memory다. 여기서 long-term은 영구 보존이 아니라 "한 스레드를 넘어 공유된다"는 뜻이다.
- Checkpointer: `thread_id`로 구분. 같은 대화를 이어가는 용도.
- Store: namespace + key로 구분. 다른 대화에서도 사용자 정보를 쓰는 용도.

Store 데이터 구성:
- namespace: 사용자별 데이터를 묶는 경로(튜플). 예: `("users", "user-001")`
- key: namespace 안에서 항목을 식별하는 값. 예: `"profile"`
- value: 저장할 dict. 예: 이름, 관심 분야

## LangGraph Store를 쓸 때와 Checkpointer를 쓸 때
LangGraph에서 정보를 어디에 저장할지는 "현재 대화에만 필요한가, 다른 대화에서도 다시 필요한가"로 정한다.
- 현재 대화의 흐름과 중간 결과(메시지 기록, 작업 단계, Tool 결과) → State와 Checkpointer
- 여러 대화에서 재사용할 정보(사용자 프로필, 선호 언어, 관심 분야, 장기 설정) → Store
- 모든 사용자가 함께 쓰는 정보(공통 정책, 앱 설정) → Store

Store에는 다시 쓸 가치가 있는 정보만 넣는다. 매번 바뀌는 임시 값이나 전체 대화 기록을 넣으면 오래된 정보가 쓰이거나 데이터가 쌓인다. 실제 앱에서는 회원가입·설정 변경 때 저장하거나, 사용자가 기억해 달라고 한 내용을 별도 노드나 Tool이 저장한다.

## LangGraph Store 기본 메서드: put, get, search
LangGraph Store는 namespace와 key로 데이터를 저장하고 조회한다.
- `put(namespace, key, value)`: 저장
- `get(namespace, key)`: 항목 하나 조회 (없으면 `None`)
- `search(namespace)`: namespace 안의 항목 목록 조회
```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
user_namespace = ("users", "user-001")
store.put(
    namespace=user_namespace,
    key="profile",
    value={"name": "철수", "interest": "Python"},
)
profile = store.get(user_namespace, "profile")
print(f"key={profile.key}, value={profile.value}")
```
- 조회 결과는 Item 객체로, `.key`, `.value`로 값을 꺼낸다.

## LangGraph Store를 사용하는 노드: config와 store 매개변수
LangGraph 노드 함수에 `config: RunnableConfig`, `store: BaseStore` 매개변수를 선언하면 LangGraph가 실행 설정과 연결된 Store를 자동으로 넣어 준다.
```python
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore

def memory_chatbot(state: MessagesState, config: RunnableConfig, store: BaseStore):
    user_id = config["configurable"]["user_id"]
    profile = store.get(("users", user_id), "profile")
    if profile:
        system = ("다음 사용자 프로필을 참고하여 답변하세요.\n"
                  f"이름: {profile.value['name']}\n"
                  f"관심 분야: {profile.value['interest']}")
    else:
        system = "저장된 사용자 프로필이 없습니다."
    response = llm.invoke([SystemMessage(content=system), *state["messages"]])
    return {"messages": [response]}
```
- `config`의 `configurable`에는 `thread_id` 외에 `user_id` 같은 임의 값도 넣을 수 있다.
- Store는 `compile(store=store)`로 그래프에 연결해야 노드에 전달된다.

## LangGraph Store 실습: 새 대화에서도 사용자 정보 사용
LangGraph에서 `thread_id`가 다르면 Checkpointer의 대화 State는 공유되지 않지만, 같은 `user_id`로 Store를 조회하면 새 대화에서도 사용자 정보를 쓸 수 있다. Store를 읽는 `memory_chatbot` 노드로 그래프를 만들고 Checkpointer와 Store를 함께 연결한다.
```python
memory_builder = StateGraph(MessagesState)
memory_builder.add_node("chatbot", memory_chatbot)
memory_builder.add_edge(START, "chatbot")
memory_builder.add_edge("chatbot", END)
memory_graph = memory_builder.compile(checkpointer=MemorySaver(), store=store)

config_1 = {"configurable": {"thread_id": "conversation-1", "user_id": "user-001"}}
config_2 = {"configurable": {"thread_id": "conversation-2", "user_id": "user-001"}}

result_1 = memory_graph.invoke(
    {"messages": [("human", "내 이름과 관심 분야를 알려줘.")]}, config=config_1)
result_2 = memory_graph.invoke(
    {"messages": [("human", "나에 대해 알고 있는 정보를 알려줘.")]}, config=config_2)
```
- 두 대화 모두 Store의 프로필(철수, Python)을 바탕으로 답한다.

## LangGraph Store namespace로 사용자 데이터 분리
LangGraph Store는 namespace와 key 조합으로 데이터를 구분하므로, 같은 key `"profile"`이라도 namespace에 사용자 ID를 넣으면 사용자별 데이터가 섞이지 않는다.
```python
user_profiles = {
    "user-001": {"name": "철수", "interest": "Python"},
    "user-002": {"name": "영희", "interest": "JavaScript"},
}
for user_id, profile in user_profiles.items():
    store.put(namespace=("users", user_id), key="profile", value=profile)

for user_id in user_profiles:
    config = {"configurable": {"thread_id": f"{user_id}-thread", "user_id": user_id}}
    result = memory_graph.invoke(
        {"messages": [("human", "내 이름과 관심 분야를 알려줘.")]}, config=config)
    print(f"[{user_id}] {result['messages'][-1].text}")
```
- namespace는 논리적 분리 규칙일 뿐 인증·권한 검사를 하지 않는다. 실제 서비스에서는 클라이언트가 보낸 `user_id`를 그대로 믿지 말고 인증된 사용자 정보로 namespace를 만든다.

(원본의 `user_configs` dict를 for문 안 f-string으로 줄였다.)

## LangGraph invoke, Checkpointer, Store 관계 정리
LangGraph 메모리 동작을 정리하면 다음과 같다.
1. LLM `invoke` 호출은 하나하나 독립적이다.
2. ReAct Agent에서 human → ai → tool → ai가 이어져 보이는 것은 한 번의 그래프 실행 안에서 같은 State로 관리되기 때문이다.
3. 같은 그래프라도 `invoke`를 여러 번 하면 각 실행은 서로 독립이다.
4. Checkpointer를 쓰면 여러 `invoke`가 하나의 대화처럼 이어진다.
5. 대화는 `thread_id`로 구분되며 서로 독립이다.
6. Store를 쓰면 서로 다른 대화끼리 특정 정보를 공유할 수 있다.

## LangGraph 대화 요약 관리란
LangGraph 대화가 길어지면 메시지가 계속 쌓여 토큰 비용이 커진다. 대화 요약 패턴은 전체 토큰 수가 임계값을 넘으면 요약 노드를 실행해, 최근 메시지만 남기고 나머지는 요약문으로 대체한다.
- 흐름: `START → chatbot → (토큰 초과) summarize → END / (이내) END`
- `trim_messages`: 토큰 기준으로 최근 메시지만 골라낸다.
- `RemoveMessage(id=...)`: `add_messages` Reducer가 이 메시지를 만나면 같은 ID의 메시지를 State에서 지운다.

요약 후 State는 `messages`에 최근 메시지만, `summary`에 삭제된 메시지의 요약을 갖는다. 지운 메시지는 현재 State에서 사라지지만 Checkpointer 히스토리의 과거 스냅샷에는 남아 있다.

## LangGraph 대화 요약 1단계: SummaryState와 답변 노드
LangGraph 요약 State는 `MessagesState`를 상속해 `summary` 필드를 추가한다. 답변 노드는 기존 요약을 합성 `HumanMessage`로 최근 메시지 앞에 붙여 모델에 넘기되, 이 메시지는 State에 저장하지 않는다.
```python
MAX_TOKENS = 200   # 네 번째 대화 전에 요약되도록 낮게 설정

class SummaryState(MessagesState):
    summary: str

def chatbot_with_summary(state: SummaryState):
    messages = [SystemMessage(content="모든 답변을 2문장 이내로 짧게 해줘.")]
    if state.get("summary"):
        messages.append(HumanMessage(
            content=f"이전 대화 요약:\n{state['summary']}",
            additional_kwargs={"lc_source": "summarization"},
        ))
    messages.extend(state["messages"])
    return {"messages": [llm.invoke(messages)]}

def route_after_chatbot(state: SummaryState):
    token_count = llm.get_num_tokens_from_messages(state["messages"])
    return "summarize" if token_count > MAX_TOKENS else END
```
- 반환값에는 새 AI 응답만 있으므로 요약 메시지와 시스템 메시지는 State에 쌓이지 않는다.

## LangGraph 대화 요약 2단계: trim_messages로 유지할 메시지 고르기
LangGraph 요약 노드는 먼저 `trim_messages`로 최근 100토큰 이내 메시지를 원문 그대로 남길 목록으로 고르고, 나머지를 요약 대상으로 분리한다.
```python
from langchain_core.messages import trim_messages

def summarize_conversation(state: SummaryState):
    messages = state["messages"]
    existing_summary = state.get("summary", "")

    kept_messages = trim_messages(
        messages,
        max_tokens=100,
        strategy="last",       # 뒤(최신)부터 남긴다
        token_counter=llm,     # 모델로 토큰 계산
        start_on="human",      # 남긴 목록이 human 메시지로 시작하게
    )
    kept_ids = {m.id for m in kept_messages}
    messages_to_summarize = [m for m in messages if m.id not in kept_ids]
    ...
```
- 함수의 나머지(요약 생성과 삭제)는 3단계에 이어진다.

## LangGraph 대화 요약 3단계: 요약 갱신과 RemoveMessage
LangGraph 요약 노드는 요약 대상 메시지(human/ai만)를 프롬프트에 넣어 요약을 만들고, 기존 요약이 있으면 함께 넣어 갱신한다. 마지막으로 요약한 원본을 `RemoveMessage`로 지운다.
```python
    summary_instruction = (
        "대화 맥락에 필요한 핵심 정보만 요약해줘.\n"
        "- 2문장, 150자 이내\n- 제목, 불릿, 서론 없이 요약문만 출력\n"
        "- 중복된 내용은 제거\n"
        "- 사용자 이름과 선호처럼 이후 대화에 필요한 정보는 반드시 유지")
    if existing_summary:
        prompt = f"{summary_instruction}\n\n기존 요약:\n{existing_summary}\n\n새 대화:\n"
    else:
        prompt = f"{summary_instruction}\n\n대화:\n"
    for m in messages_to_summarize:
        if m.type in ("human", "ai") and m.content:
            prompt += f"{m.type}: {m.content}\n"

    summary_response = llm.invoke(prompt)
    return {
        "summary": summary_response.text,
        "messages": [RemoveMessage(id=m.id) for m in messages_to_summarize],
    }
```
(원본은 압축 전·대상·후 기록을 출력하는 `print_history` 호출도 있다. 생략했다.)

## LangGraph 대화 요약 4단계: 그래프 구성과 실행
LangGraph 요약 그래프는 `chatbot` 뒤에서 `summarize` 또는 `END`로 분기한다.
```python
summary_builder = StateGraph(SummaryState)
summary_builder.add_node("chatbot", chatbot_with_summary)
summary_builder.add_node("summarize", summarize_conversation)
summary_builder.add_edge(START, "chatbot")
summary_builder.add_conditional_edges(
    "chatbot", route_after_chatbot, {"summarize": "summarize", END: END})
summary_builder.add_edge("summarize", END)
summary_graph = summary_builder.compile(checkpointer=MemorySaver())

config = {"configurable": {"thread_id": "summary-test"}}
for q in ["내 이름은 철수야. 기억해줘.", "파이썬이 뭐야?", "자바스크립트와 비교하면?",
          "웹 개발에는 어떤 게 좋아?", "데이터 분석에는?", "내 이름이 뭐라고 했지?"]:
    result = summary_graph.invoke({"messages": [("human", q)]}, config=config)
    print(result.get("summary"))
```
- 6턴 동안 `messages`가 쌓이다 `summary`로 압축되고, 마지막 질문에서 요약 덕에 이름을 기억하는지 본다.
- 원본 출력은 AI `content`가 서명 데이터 붙은 블록 리스트라 매우 길다. `.text`로 보면 된다(내 메모).

(원본 `run_turn` 헬퍼를 for문으로 풀었다.)

## LangGraph 대화 요약 시 원본 대화 보관
LangGraph 요약 예제는 오래된 메시지를 요약한 뒤 현재 State에서 지우고 원본은 따로 보관하지 않는다. 실무에서는 원본 대화를 데이터베이스나 로그 저장소에 별도로 남기고, LangGraph State에는 요약과 최근 메시지만 둔다. Checkpointer는 그래프 실행 상태를 저장하는 장치이지 원본 대화 저장소를 대신하지 않는다.

## LangGraph Memory 실습 문제: 대화와 사용자 정보 기억하기
LangGraph Memory 실습은 Checkpointer와 Store를 쓰는 챗봇을 단계별로 완성한다.
- 메모리 없음: 같은 그래프에 "나는 철수야!" → "내가 누구라고?"를 차례로 `invoke`하면 기억하지 못한다.
- Checkpointer 추가: 같은 `thread_id`면 이어서 기억하고, 다른 `thread_id`면 모른다.
- Checkpointer + Store: 미리 저장한 프로필을 서로 다른 대화창(`thread_id`)에서 모두 활용한다.

## LangGraph Memory 실습 풀이: Checkpointer 유무 비교
LangGraph Memory 실습 풀이는 같은 챗봇 노드를 checkpointer 없이, 그리고 있게 컴파일해 비교한다. `thread_id`는 ChatGPT·Claude의 "채팅창 식별자"와 같다.
```python
def chatbot(state: MessagesState):
    return {"messages": [llm.invoke(state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)

graph = builder.compile()                         # 메모리 없음
graph.invoke({"messages": "나는 철수야!"})
graph.invoke({"messages": "내가 누구라고?"})       # 모른다

graph = builder.compile(checkpointer=MemorySaver())
cfg = {"configurable": {"thread_id": "채팅창 식별자"}}
graph.invoke({"messages": "나는 철수야!"}, config=cfg)
graph.invoke({"messages": "내가 누구라고?"}, config=cfg)  # 철수라고 답함
graph.invoke({"messages": "내가 누구라고?"},
             config={"configurable": {"thread_id": "다른 무언가"}})  # 모른다
```
- `{"messages": "문자열"}`처럼 문자열 하나를 넘겨도 `add_messages`가 human 메시지로 바꿔 준다.

(원본은 builder를 두 번 다시 만든다. 하나로 합쳤다.)

## LangGraph Memory 실습 풀이: Checkpointer + Store 챗봇
LangGraph Memory 실습의 마지막 풀이는 대화 전에 Store에 프로필을 미리 넣어 두고(ChatGPT 설정에 직업 등을 적어 두는 것과 비슷), 노드가 `config`의 사용자 키로 프로필을 읽는다.
```python
memory = MemorySaver()    # 한 대화창 안에서 대화 이어가기
store = InMemoryStore()   # 여러 대화창이 같은 맥락 공유
store.put(namespace=("users", "user-a"), key="profile",
          value={"name": "user-a", "interest": "ai agent"})

def chatbot(state: MessagesState, config, store):
    profile = store.get(("users", config["configurable"]["my_data"]), "profile")
    system = ("다음 사용자 프로필을 참고하여 답변하세요.\n"
              f"이름: {profile.value['name']}\n관심 분야: {profile.value['interest']}"
              if profile else "저장된 사용자 프로필이 없습니다.")
    return {"messages": [llm.invoke([SystemMessage(content=system), *state["messages"]])]}
```
- 원본 사용자 키 값은 `"user-a"`로 바꿔 적었다. config 키 이름 `my_data`는 원본 그대로다.
- system 문자열을 조건 표현식 하나로 합쳐 줄였다.

## LangGraph Memory 실습 풀이: Store 공유와 thread_id 독립 확인
LangGraph Memory 실습 풀이에서 Store 프로필을 읽는 `chatbot` 노드를 Checkpointer와 Store를 함께 연결해 컴파일하고, 서로 다른 대화창에서 실행한다.
```python
builder = StateGraph(MessagesState)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)
graph = builder.compile(checkpointer=memory, store=store)

for tid in ["채팅창 식별자-1", "채팅창 식별자-2"]:
    graph.invoke({"messages": "내 profile 알려줘"},
                 config={"configurable": {"thread_id": tid, "my_data": "user-a"}})
```
- 두 대화창 모두 Store의 프로필을 안다.
- 한 창에서 "나는 고기를 좋아해"라고 말해도 다른 창은 모른다. Store는 공유되지만 대화 State는 `thread_id`별로 독립이기 때문이다.

## LangGraph Memory: 기억 저장을 Agent에게 맡기는 Tool 아이디어
LangGraph Memory 실습 마지막 메모는, 사용자가 "기억해줘"라고 할 때 Store에 저장하는 Tool을 만들어 ReAct Agent가 저장 시점을 스스로 판단하게 하는 방법을 제시한다. 원본의 의사코드는 따옴표·쉼표가 빠져 그대로는 실행되지 않으므로 고쳐서 적는다(내 메모).
```python
from langchain_core.tools import tool

@tool
def remember_info(text: str) -> str:
    """사용자가 기억해 달라고 한 내용을 Store에 저장한다."""
    store.put(namespace=("users", user_id), key="info", value={"data": text})
    return "저장했습니다."
```
- 실제로는 `user_id`를 전역 변수가 아니라 실행 설정이나 인증 정보에서 가져와야 한다(내 메모).

## Memory & State 관리 복습 Q&A
- Q. LangGraph Checkpointer는 대화를 무엇으로 구분하나?
  A. `config={"configurable": {"thread_id": ...}}`의 `thread_id`로 구분한다. 같은 `thread_id`면 이전 State에 이어서 실행한다.
- Q. LangGraph Checkpointer와 Store의 차이는?
  A. Checkpointer는 `thread_id`별 대화 State를 저장하고, Store는 namespace+key로 스레드를 넘어 공유할 정보(사용자 프로필 등)를 저장한다.
- Q. LangGraph 노드에서 Store를 쓰려면?
  A. `compile(store=store)`로 연결하고 노드 함수에 `store: BaseStore`(와 `config: RunnableConfig`) 매개변수를 선언하면 LangGraph가 넣어 준다.
- Q. LangGraph 대화 요약 패턴에서 오래된 메시지는 어떻게 지우나?
  A. 요약 노드가 `RemoveMessage(id=...)` 목록을 `messages`로 반환하면 `add_messages` Reducer가 해당 ID 메시지를 State에서 제거한다.
- Q. LangGraph `get_state`와 `get_state_history`의 차이는?
  A. `get_state`는 해당 `thread_id`의 최신 State, `get_state_history`는 최신부터 과거 순서의 모든 스냅샷을 준다.
