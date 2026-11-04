---
part: langchain
lesson: Time Travel
order: 22
source_type: ipynb
tags: [langgraph, time-travel, checkpoint, replay, fork, update_state, get_state_history]
source: C:\Users\tnwls\aim-ai-agent\langchain_\22-time-travel.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Time Travel

## Time Travel 요약
LangGraph Checkpointer에 저장된 과거 State를 조회하고, 특정 checkpoint부터 그대로 다시 실행(Replay)하거나 값을 바꿔 다른 경로로 실행(Fork)하는 방법을 `주제 정리 → 초안 작성 → 검토` 그래프로 실습한다.

## LangGraph Time Travel이란
Checkpointer를 붙인 LangGraph 그래프는 실행 중 State를 checkpoint로 기록한다. Time Travel은 이 기록을 활용하는 기능이며 동작은 세 가지다.
- 조회: 과거 checkpoint의 State와 다음 실행 노드(`next`)를 확인한다.
- Replay: 과거 값을 그대로 써서 그 시점 이후를 다시 실행한다.
- Fork: 과거 값을 고친 뒤 다른 경로로 실행한다.

## Time Travel 실습 1단계: 게시글 작성 그래프 만들기
Time Travel 실습용으로 노드 3개짜리 순차 그래프를 만든다. 각 노드는 실행될 때 이름을 출력해서, 과거로 돌아갔을 때 어떤 노드가 다시 실행되는지 볼 수 있다.
```python
from typing import TypedDict
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

class PostState(TypedDict, total=False):
    request: str
    topic: str
    draft: str
    review: str

def choose_topic(state: PostState):
    print("[실행] 주제 정리")
    return {"topic": f"{state['request']} 입문"}

def write_draft(state: PostState):
    print("[실행] 초안 작성")
    return {"draft": f"{state['topic']}: 쉽게 설명하는 게시글입니다."}

def review_draft(state: PostState):
    print("[실행] 검토")
    return {"review": f"검토 완료: {state['draft']}"}
```
- `total=False`: 모든 키를 선택 항목으로 만들어 처음엔 `request`만 넣어도 된다.

## Time Travel 실습 2단계: Checkpointer 연결 후 실행
그래프를 `START → choose_topic → write_draft → review_draft → END`로 잇고 `InMemorySaver`를 붙여 컴파일한 뒤 `thread_id`로 실행한다.
```python
builder = StateGraph(PostState)
builder.add_node("choose_topic", choose_topic)
builder.add_node("write_draft", write_draft)
builder.add_node("review_draft", review_draft)
builder.add_edge(START, "choose_topic")
builder.add_edge("choose_topic", "write_draft")
builder.add_edge("write_draft", "review_draft")
builder.add_edge("review_draft", END)
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "post-1"}}
result = graph.invoke({"request": "LangGraph"}, config)
```
```text
[실행] 주제 정리
[실행] 초안 작성
[실행] 검토
```
- 결과 State에는 `topic='LangGraph 입문'`, `draft`, `review`가 모두 채워진다.

## Time Travel 현재 State 조회: get_state
LangGraph의 `get_state(config)`는 최신 `StateSnapshot`을 돌려준다.
- `values`: 저장된 State
- `next`: 다음에 실행할 노드. 실행이 끝났으면 빈 튜플 `()`
- `config`: `thread_id`, `checkpoint_ns`, `checkpoint_id`를 담은 설정
```python
current = graph.get_state(config)
print(current.values)
print(current.next)    # ()
print(current.config)  # {'configurable': {'thread_id': 'post-1', 'checkpoint_ns': '', 'checkpoint_id': '...'}}
```

## Time Travel 과거 State 조회: get_state_history
LangGraph의 `get_state_history(config)`는 최신 checkpoint부터 과거 순서로 snapshot을 돌려준다.
```python
history = list(graph.get_state_history(config))
for index, snapshot in enumerate(history):
    cid = snapshot.config["configurable"]["checkpoint_id"]
    print(f"{index}: next={snapshot.next}, topic={snapshot.values.get('topic')!r}, id={cid[-8:]}")
```
```text
0: next=(), topic='LangGraph 입문'
1: next=('review_draft',), topic='LangGraph 입문'
2: next=('write_draft',), topic='LangGraph 입문'
3: next=('choose_topic',), topic=None
4: next=('__start__',), topic=None
```
(출력의 checkpoint_id 부분은 생략)
- 노드 3개 실행에 checkpoint가 5개 생긴다: 시작 전, 각 노드 전, 완료 후.

## Time Travel에서 thread_id와 checkpoint_id의 차이
LangGraph Time Travel에서 `thread_id`는 하나의 실행 이력 전체를 구분하고, `checkpoint_id`는 그 이력 안의 특정 시점을 구분한다.
```text
thread_id: post-1
├── checkpoint_id: A → 주제 정리 전
├── checkpoint_id: B → 초안 작성 전
├── checkpoint_id: C → 검토 전
└── checkpoint_id: D → 실행 완료
```
- snapshot의 `next`로 원하는 시점을 찾는다. `next == ('write_draft',)`이면 초안 작성 직전이다.
- 과거 시점에서 실행하려면 `checkpoint_id`가 포함된 그 snapshot의 `config`를 쓴다.
```python
before_draft = next(s for s in history if s.next == ("write_draft",))
print(before_draft.values)  # {'request': 'LangGraph', 'topic': 'LangGraph 입문'}
```
(원본의 for+break 탐색을 `next()` 한 줄로 바꿔 적음)

## Time Travel Replay: 과거 checkpoint에서 그대로 재실행
Replay는 과거 checkpoint의 State를 바꾸지 않고 그 시점부터 다시 실행하는 방식이다. 선택한 snapshot의 `config`와 함께 입력에 `None`을 넣으면 새 State 없이 그 지점부터 이어 간다.
```python
replayed = graph.invoke(None, before_draft.config)
```
```text
[실행] 초안 작성
[실행] 검토
```
- 이미 끝난 `choose_topic`은 다시 실행하지 않고 `write_draft`부터 실행한다.
- 값이 같아도 이후 노드의 코드는 실제로 다시 호출된다(내 메모: LLM 노드라면 결과가 달라질 수 있다).

## Time Travel Replay 이후 checkpoint 구조와 parent_config
LangGraph Replay는 기존 checkpoint를 지우거나 덮어쓰지 않고 같은 `thread_id` 이력에 새 checkpoint를 추가한다. 각 checkpoint는 `parent_config`로 직전 checkpoint를 가리키는데, 과거 B에서 Replay하면 새 C'의 부모는 최신 D가 아니라 B다.
```text
저장 순서: A, B, C, D, C', D'
부모 관계: A → B → C → D
                └→ C' → D'
```
```python
for s in graph.get_state_history(config):
    parent = s.parent_config["configurable"]["checkpoint_id"][-8:] if s.parent_config else None
    print(s.config["configurable"]["checkpoint_id"][-8:], parent, s.next)
```
- 실습 결과 checkpoint 수가 5개 → 8개로 늘었고, 새 `('write_draft',)` checkpoint의 부모가 원래 B였다.
- `thread_id`만으로 `get_state()`를 부르면 가장 최근 checkpoint(D')를 돌려준다.

## Time Travel Fork: update_state로 과거 State 수정
Fork는 과거 checkpoint의 State를 고친 뒤 그 State에서 다시 실행하는 방식이다. LangGraph의 `update_state()`는 기존 checkpoint를 덮어쓰지 않고 수정된 새 checkpoint를 만들고, 그 config를 반환한다.
```python
config = {"configurable": {"thread_id": "post-fork"}}
result = graph.invoke({"request": "LangGraph"}, config)
history = list(graph.get_state_history(config))
before_draft = next(s for s in history if s.next == ("write_draft",))

fork_config = graph.update_state(
    before_draft.config,
    {"topic": "LangGraph Time Travel 심화"},
    as_node="choose_topic",
)
print(graph.get_state(fork_config).next)  # ('write_draft',)
```
- `as_node="choose_topic"`: 이 값을 `choose_topic` 노드가 쓴 것처럼 처리한다. 그래서 다음 노드는 `write_draft`가 된다.

## Time Travel Fork 실행과 원래 경로 비교
LangGraph Fork로 만든 checkpoint config로 `invoke(None, fork_config)`를 부르면 그 `next`부터 실행된다.
```python
forked = graph.invoke(None, fork_config)   # [실행] 초안 작성, [실행] 검토
for key in ("topic", "draft"):
    print(key, "원래:", result[key], "| 분기:", forked[key])
```
```text
topic 원래: LangGraph 입문 | 분기: LangGraph Time Travel 심화
draft 원래: LangGraph 입문: ... | 분기: LangGraph Time Travel 심화: ...
```
- Fork 후에도 원래 결과와 과거 checkpoint는 바뀌지 않는다.
- 구조는 `A → B → C → D`와 `B → U → C' → D'`로 갈라진다. U는 `update_state()`가 만든 수정 checkpoint이며, Replay와 달리 checkpoint가 하나 더 생긴다.
- 실습 출력에서 Fork 후 checkpoint 수는 5 → 8(U, C', D')이었다. U는 `next=('write_draft',)`이고 부모가 B다.
- (기록상) Replay 출력에서도 5 → 8이었고, 새로 생긴 첫 checkpoint가 `next=('write_draft',)`, 부모 B였다. 즉 출력상으로는 Replay도 B의 복사 checkpoint를 하나 만든 것으로 보여, 설명(C', D'만 추가)과 개수가 다르다.

## Time Travel 활용 사례와 UI 표현
LangGraph Time Travel의 Replay는 과거 State를 그대로 써서 특정 시점부터 다시 돌린다.
- 장애가 난 지점부터 다시 실행해 Agent 판단 과정 분석
- prompt·model·로직을 바꾼 뒤 같은 과거 State에서 결과 비교
- 앞부분의 비싼 검색·Tool 결과를 유지한 채 뒤 단계만 테스트

Fork는 과거 State 일부를 고쳐 새 경로로 실행한다.
- 사용자 수정 요청이나 검토 피드백을 반영해 이어서 작업
- 같은 중간 State에 다른 조건을 줘서 결과 비교
- 긴 조사 결과를 재사용해 여러 전략 생성

서비스 화면에는 checkpoint라는 말 대신 작업 이름으로 보여 준다. "다시 생성", "이 단계부터 다시 실행"은 Replay, "수정 후 계속", "이 버전에서 다시 작성"은 Fork에 해당한다.

## Time Travel 외부 작업 주의사항
LangGraph Time Travel로 State는 과거로 되돌릴 수 있지만, 이미 보낸 메일이나 처리한 결제 같은 외부 작업은 되돌아가지 않는다. Replay·Fork 이후 노드에 외부 작업이 있으면 중복 실행되지 않도록 주의해야 한다.

## Time Travel 실습 문제: 검토 직전 draft 수정 분기
실습 문제: 초안 작성이 끝나고 검토하기 직전 checkpoint(`next == ('review_draft',)`)를 찾아 `draft`를 직접 고친 분기를 만들고, 수정된 초안으로 `review_draft`만 실행되는지 확인한다. 노트북에는 TODO만 있고 풀이 코드는 없다.

(내 메모) 풀이 예시:
```python
practice_config = {"configurable": {"thread_id": "post-review-practice"}}
graph.invoke({"request": "LangGraph"}, practice_config)

before_review = next(
    s for s in graph.get_state_history(practice_config)
    if s.next == ("review_draft",)
)
new_config = graph.update_state(
    before_review.config,
    {"draft": "직접 수정한 초안입니다."},
    as_node="write_draft",
)
print(graph.invoke(None, new_config))  # [실행] 검토 만 출력되어야 함
```
- `as_node="write_draft"`로 지정해야 다음 노드가 `review_draft`가 된다.

## Time Travel 복습 Q&A
- Q. LangGraph에서 과거 checkpoint 목록은 어떻게 조회하나?
  A. `graph.get_state_history(config)`로 최신순 `StateSnapshot` 목록을 받는다. 각 snapshot의 `next`, `values`, `config`를 확인한다.
- Q. Time Travel의 Replay와 Fork는 무엇이 다른가?
  A. Replay는 과거 State를 그대로 두고 `invoke(None, snapshot.config)`로 재실행하고, Fork는 `update_state()`로 State를 고친 새 checkpoint를 만든 뒤 그 config로 실행한다.
- Q. Replay나 Fork를 하면 기존 checkpoint는 어떻게 되나?
  A. 지워지거나 덮어써지지 않는다. 같은 `thread_id` 이력에 새 checkpoint가 추가되고, `parent_config`로 갈라진 경로를 추적할 수 있다.
- Q. `update_state()`의 `as_node` 인자는 무슨 역할인가?
  A. 수정 값을 해당 노드가 쓴 것처럼 처리해서, 그 노드의 다음 노드부터 실행되게 한다.
- Q. Time Travel로 재실행할 때 주의할 점은?
  A. 메일 발송, 결제 같은 외부 작업은 되돌아가지 않으므로 이후 노드에서 중복 실행되지 않도록 해야 한다.
