---
part: langchain
lesson: Chat Memory
order: 3
source_type: ipynb
tags: [memory, chat-history, inmemorychatmessagehistory, trim-messages, context-window, session]
source: C:\Users\tnwls\aim-ai-agent\langchain_\03-memory.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Chat Memory

## Chat Memory 요약
LLM 호출은 stateless이므로 대화 맥락을 유지하려면 이전 메시지를 매번 함께 보내야 한다. 메시지 리스트 수동 관리, `InMemoryChatMessageHistory`로 세션별 관리, `trim_messages()`로 context window 관리를 실습한다.

## LLM 대화 메모리란: stateless 호출
LLM 호출은 기본적으로 이전 호출을 기억하지 않는 stateless 요청이다. 대화 메모리는 이전 메시지를 저장해 두었다가 다음 호출에 함께 전달해 맥락을 유지하는 방법이다. 노트북은 LangChain Core의 메시지 클래스와 히스토리 인터페이스로 직접 관리한다.
```python
from dotenv import load_dotenv
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, trim_messages
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
```

## 메모리 없는 대화와 수동 히스토리 전달
대화 메모리 없이 "내 이름은 철수야" → "내 이름이 뭐였지?"를 각각 따로 `invoke()`하면 모델은 두 번째 호출에서 이름을 알 수 없다. 이전 메시지와 응답을 리스트에 누적해 함께 보내면 맥락이 유지된다.
```python
messages = [
    SystemMessage(content="너는 친절한 상담사야."),
    HumanMessage(content="내 이름은 철수야"),
]
response1 = llm.invoke(messages)

messages.extend([response1, HumanMessage(content="내 이름이 뭐였지?")])
response2 = llm.invoke(messages)
print(response2.content)  # "철수님이에요" 취지의 답
```
- `response1`(AIMessage)을 그대로 리스트에 넣어 대화 기록을 만든다.
- 이 노트북의 Gemini 3 모델은 `content`가 문자열이 아니라 `[{'type': 'text', 'text': ..., 'extras': {'signature': ...}}]` 형태의 블록 리스트로 출력된다. 텍스트만 보려면 `response.text`를 쓰면 된다. (`response.text`는 내 메모)

## InMemoryChatMessageHistory로 세션별 대화 관리
`InMemoryChatMessageHistory`는 메시지 추가·조회를 위한 LangChain Core의 기본 인메모리 히스토리다. 세션 ID별로 객체를 나누면 여러 대화를 독립적으로 관리할 수 있다.
```python
history_store: dict[str, InMemoryChatMessageHistory] = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in history_store:
        history_store[session_id] = InMemoryChatMessageHistory()
    return history_store[session_id]

def chat(session_id: str, user_input: str) -> str:
    history = get_session_history(session_id)
    user_message = HumanMessage(content=user_input)
    response = llm.invoke([
        SystemMessage(content="너는 친절한 상담사야."),
        *history.messages,
        user_message,
    ])
    history.add_messages([user_message, response])
    return response.content

chat("user-1", "내 이름은 철수야")
chat("user-1", "내 이름이 뭐였지?")   # 철수라고 기억함
chat("user-2", "내 이름이 뭐야?")     # user-1 기록이 없어 모름
```
- `history.messages`로 조회, `history.add_messages([...])`로 질문과 응답을 함께 저장한다.

## InMemoryChatMessageHistory의 한계
`InMemoryChatMessageHistory`는 대화 히스토리의 기본 동작을 배우기에 좋지만 프로세스가 종료되면 기록이 사라진다. 이후 LangGraph에서는 같은 흐름을 state와 checkpointer로 관리하고, 데이터베이스 기반 저장소를 연결해 대화를 영속적으로 유지한다.

## 대화 메모리 Context window 관리 방법 비교
대화 메모리에서 원본 메시지를 저장하는 것과 모델에 보낼 메시지를 고르는 것은 별개의 문제다. 대화가 길어지면 비용과 지연 시간이 늘고 context window를 넘을 수 있다.
- 메시지 트리밍: 단순하고 추가 호출 비용이 없지만 오래된 맥락이 사라진다.
- 대화 요약: 오래된 핵심 맥락을 압축하지만 추가 호출 비용과 요약 오류 가능성이 있다.
- 검색 기반 선택: 관련 과거 정보만 고를 수 있지만 검색·인덱싱 설계가 필요하다.

요약 + 최근 메시지를 함께 유지하는 방식이 흔한 패턴이지만, 서비스 특성과 평가 결과에 맞춰 고른다. 트리밍만 쓰면 이름 같은 중요한 사용자 정보도 잘려 나갈 수 있으므로 실서비스에서는 요약이나 검색한 과거 정보를 함께 전달하는 것을 고려한다.

## trim_messages 옵션 정리
`trim_messages()`는 전체 히스토리에서 모델에 보낼 메시지만 골라 새 리스트로 돌려준다. 원본 리스트나 히스토리 객체의 메시지는 삭제하지 않으므로 전체 대화는 저장소에 남기고 최근 대화만 모델에 보낼 수 있다.
- `max_tokens`: 결과에 허용할 최대 토큰 수. 남는 메시지 수는 메시지 길이에 따라 달라진다.
- `strategy`: `"last"`면 뒤쪽(최근) 메시지를, `"first"`면 앞쪽 메시지를 우선해 남긴다.
- `token_counter`: 토큰 수를 셀 모델이나 함수. 예제는 `llm`을 넘긴다.
- `include_system`: 첫 system 메시지를 유지할지 여부.
- `start_on` / `end_on`: 잘린 대화가 어떤 역할 메시지로 시작/끝나야 하는지.

처리 흐름: 전체 히스토리 저장 → 토큰 수 계산 → 최근 메시지 선택 → 시작 역할 정리 → 모델에 전달.

## trim_messages 실습: 긴 히스토리 트리밍
trim_messages로 system + 9개 대화 메시지(이름 소개, Python, FastAPI 질문 등)로 된 10개 메시지 히스토리를 최근 위주로 자른다.
```python
trimmer = trim_messages(
    max_tokens=60,
    strategy="last",
    token_counter=llm,
    include_system=True,
    start_on="human",
)
trimmed = trimmer.invoke(long_history)  # long_history: 메시지 10개 리스트
print("원본 메시지 수:", len(long_history))
print("트리밍 후 메시지 수:", len(trimmed))
```
```text
원본 메시지 수: 10
트리밍 후 메시지 수: 6
[system] 너는 친절한 상담사야.
[human] Python에 대해 알려줘
...
[human] 내 이름이 뭐였지?
```
- `long_history`로 호출하면 "철수님"이라고 답하지만, `trimmed`에는 이름 소개 메시지가 빠져 있어 모델이 이름을 알 수 없다.
- (원문 설명은 최대 토큰 80이라고 했지만 코드는 `max_tokens=60`이다.)

## Short-term memory와 long-term memory 차이
대화 메모리의 short-term과 long-term은 저장 기간이 아니라 기억을 쓰는 범위(scope)로 나눈다.
- Short-term memory: 현재 대화 세션 범위. 현재 대화 메시지와 작업 맥락을 담는다. 예: "앞에서 내 이름을 철수라고 말했어".
- Long-term memory: 여러 세션에 걸친 범위. 사용자 선호, 프로필, 기억할 사실·경험을 담는다. 예: "이 사용자는 Python 백엔드 개발자다".

이 노트북은 short-term memory만 다루고, long-term memory는 이후 과정에서 다룬다.

## Chat Memory 실습 문제 1: 세션별 대화 메모리 만들기
Chat Memory 실습 문제 1은 `InMemoryChatMessageHistory`로 대화를 기억하는 함수를 만들고, 같은 세션은 이전 대화를 기억하고 다른 세션끼리는 섞이지 않는지 확인하는 것이다.

풀이(노트북 코드): 히스토리 하나를 만들고 `input()`으로 10번 대화하며 매번 전체 히스토리 + 새 메시지를 보낸다.
```python
my_history = InMemoryChatMessageHistory()

for _ in range(10):
    user_message = HumanMessage(content=input())
    response = llm.invoke([*my_history.messages, user_message])
    my_history.add_messages([user_message, response])
    print("response: ", response.content)
```
- 노트북 풀이는 세션 하나만 다룬다. 세션 분리까지 확인하려면 `get_session_history(session_id)`처럼 dict에 세션별 히스토리를 두고 세션 ID를 바꿔 호출한다. (내 메모)
- 출력은 매 턴의 응답과 누적된 메시지 리스트로 매우 길다.

## Chat Memory 실습 문제 2: trim_messages로 최근 대화만 전달
Chat Memory 실습 문제 2는 세션 대화 함수에 `trim_messages()`를 붙여, 히스토리에는 전체 대화를 남기고 모델에는 최근 대화만 보내는 것이다. 긴 대화 후 전체 메시지 수와 전달된 메시지 수가 다른지 확인한다.

풀이: 호출 직전에 전체 메시지를 트리밍하고, 저장은 원래 메시지로 한다.
```python
my_history = InMemoryChatMessageHistory()
trimmer = trim_messages(
    max_tokens=30,
    strategy="last",
    token_counter=llm,
    include_system=True,
    start_on="human",
)

for _ in range(10):
    user_message = HumanMessage(content=input())
    all_messages = [*my_history.messages, user_message]
    trimmed_message = trimmer.invoke(all_messages)   # 모델에는 잘린 메시지
    response = llm.invoke(trimmed_message)
    my_history.add_messages([user_message, response]) # 히스토리에는 전부 저장
    print(len(my_history.messages), len(trimmed_message))
```
- 원문은 매 턴 전체 히스토리와 트리밍 결과를 `pprint`로 출력한다(마지막 print는 줄여서 바꿈).
- `max_tokens=30`이라 몇 턴만 지나도 앞쪽 대화가 모델 입력에서 빠진다.

## Chat Memory 복습 Q&A
- Q. LLM이 이전 대화를 기억하게 하려면 기본적으로 어떻게 하나?
  A. LLM 호출은 stateless라서, 이전 메시지(Human/AI)를 리스트에 누적해 매 호출에 함께 보낸다.
- Q. `InMemoryChatMessageHistory`로 여러 사용자의 대화를 분리하려면?
  A. 세션 ID를 키로 하는 dict에 세션별 히스토리 객체를 두고 `get_session_history(session_id)`로 꺼내 쓴다.
- Q. `trim_messages()`는 원본 히스토리를 지우나?
  A. 지우지 않는다. 조건에 맞게 고른 새 메시지 리스트를 반환하므로 전체 기록은 저장소에 남는다.
- Q. 메시지 트리밍만 쓸 때의 위험은?
  A. 오래된 메시지가 빠지면서 사용자 이름 같은 중요한 정보도 모델이 알 수 없게 된다. 요약이나 검색 기반 선택을 함께 고려한다.
- Q. short-term memory와 long-term memory를 나누는 기준은?
  A. 기억을 쓰는 범위다. short-term은 현재 세션, long-term은 여러 세션에 걸친 사용자 정보다.
