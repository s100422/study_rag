---
part: langchain
lesson: Handoff
order: 26
source_type: ipynb
tags: [langgraph, multi-agent, handoff, command, goto, toolruntime, command-parent]
source: C:\Users\tnwls\aim-ai-agent\langchain_\26-handoff.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Handoff

## Handoff 요약
LangGraph에서 `Command(update, goto)`로 노드가 State 변경과 다음 이동을 함께 정하는 법을 익히고, 이를 이용해 Sales Agent와 Support Agent가 대화 담당권을 주고받는 Handoff 고객 상담 시스템을 만든다. 마지막에 Router·Supervisor·Handoff 패턴을 비교한다.

## Multi-Agent Handoff란
Handoff는 현재 Agent가 다른 Agent에게 대화 제어권을 넘기는 방식이다. 결과가 중앙 Agent로 돌아가는 Supervisor와 달리, Handoff에서는 전환된 Agent가 새 담당자가 되어 사용자에게 직접 답하고 이후 대화도 이어 간다.

## LangGraph Command로 State 변경과 노드 이동
LangGraph의 `Command`는 그래프 실행을 제어하는 객체다. HITL에서는 `resume`으로 중단된 그래프에 값을 넘겼고, 여기서는 `update`와 `goto`를 쓴다.
- 일반 노드: dict를 반환해 State를 바꾸고, 다음 노드는 Edge가 정한다.
- `Command`를 반환하는 노드: State 변경과 다음 실행 위치를 함께 정한다.
```python
return Command(
    update={"category": "support"},  # State에 반영할 값
    goto="support",                  # 다음에 실행할 노드 이름
)
```

## Command 실습: 문의 분류 후 판매·기술지원으로 이동
문의 내용에 "오류"나 "고장"이 있으면 `support`, 아니면 `sales` 노드로 `Command`를 이용해 이동한다. `classify`에서 나가는 Edge는 등록하지 않는다.
```python
from typing import Literal, TypedDict
from langgraph.types import Command

class RoutingState(TypedDict):
    query: str
    category: str
    result: str

def classify_query(state: RoutingState) -> Command[Literal["sales", "support"]]:
    if "오류" in state["query"] or "고장" in state["query"]:
        return Command(update={"category": "support"}, goto="support")
    return Command(update={"category": "sales"}, goto="sales")
```
- 반환 타입 `Command[Literal[...]]`로 이동 가능한 노드를 표시한다.

## Command 실습: 분류 그래프 조립과 실행
LangGraph 분류 그래프에서는 `START → classify`와 두 처리 노드의 `→ END`만 Edge로 등록하고, `classify` 다음 노드는 `Command.goto`가 정한다.
```python
def handle_sales(state): return {"result": "판매 문의로 처리했습니다."}
def handle_support(state): return {"result": "기술 지원 문의로 처리했습니다."}

b = StateGraph(RoutingState)
b.add_node("classify", classify_query)
b.add_node("sales", handle_sales)
b.add_node("support", handle_support)
b.add_edge(START, "classify")
b.add_edge("sales", END)
b.add_edge("support", END)
routing_graph = b.compile()
routing_graph.invoke({"query": "제품에서 오류가 발생했어요.", "category": "", "result": ""})
# → {'category': 'support', 'result': '기술 지원 문의로 처리했습니다.', ...}
```
(핸들러를 한 줄 함수로 줄여 옮김)

## LangGraph Edge와 Command 선택 기준
LangGraph에서 다음 노드를 정하는 방법은 상황에 따라 고른다.
- 다음 단계가 항상 같다: `add_edge()`
- 작업과 라우팅 판단을 분리하고 싶다: `add_conditional_edges()`
- State 변경과 이동이 하나의 제어 동작이다: `Command(update=..., goto=...)`

`Command[Literal["sales", "support"]]`의 `Literal`은 이동 가능한 대상을 적어 둔 것이다. 정적 Edge가 없어도 LangGraph가 이 타입 정보로 동적 이동 후보를 그래프 그림에 표시한다. `Literal`을 빼도 실행은 되지만 시각화 도구가 목적지를 알 수 없다.

고정 흐름과 일반 라우팅은 Edge로 나누는 편이 구조 파악과 노드 재사용에 유리하다.

## Command 실습 문제: 문서 검토 상태 전환
실습 문제: 문서 검토 결과에 따라 State를 바꾸고 다음 노드로 이동하는 그래프를 만든다.
- State: `document`, `approved`, `status`, `result`
- `approved=True`: `status="approved"`로 바꾸고 `publish`로 이동
- `approved=False`: `status="revision_required"`로 바꾸고 `revise`로 이동
- `publish`, `revise`는 처리 결과를 `result`에 저장하고 종료
- 같은 흐름을 Conditional Edge로 구현하면 어떤 코드가 분리되는지 비교

제공 코드:
```python
class ReviewState(TypedDict):
    document: str
    approved: bool
    status: str
    result: str

def publish_document(state: ReviewState) -> dict:
    return {"result": "문서를 게시했습니다."}

def revise_document(state: ReviewState) -> dict:
    return {"result": "문서를 수정 단계로 보냈습니다."}
```

## Command 실습 문제 풀이: 검토 결과에 따른 이동
풀이 코드. 판정 노드가 `Command`로 status를 바꾸며 이동하고, 두 처리 노드만 END로 잇는다.
```python
def node(state: ReviewState) -> Command[Literal["publish_document", "revise_document"]]:
    if state["approved"]:
        return Command(goto="publish_document", update={"status": "approved"})
    return Command(goto="revise_document", update={"status": "revision_required"})

builder = StateGraph(ReviewState)
builder.add_node("publish_document", publish_document)
builder.add_node("revise_document", revise_document)
builder.add_node("node", node)
builder.add_edge(START, "node")
builder.add_edge("publish_document", END)
builder.add_edge("revise_document", END)
graph = builder.compile()
```
- 노트북에는 그래프 그림만 출력돼 있고 `invoke` 실행 결과는 없다.
- (내 메모) Conditional Edge 버전이라면 status 변경은 판정 노드가 dict로 반환하고, 이동 판단은 별도 라우터 함수 + `add_conditional_edges`로 분리된다.

## Handoff 실습 시나리오: Sales와 Support 고객 상담
Handoff 실습은 제품 판매 회사의 고객 상담 시스템이다. 사용자는 Sales Agent와 대화를 시작하고, 문의 내용에 따라 담당이 바뀐다.
- Sales Agent: 제품, 가격, 구매 방법 문의
- Support Agent: 설치, 오류, 고장 등 기술 문의
```text
사용자 → Sales Agent
            └─ 기술 문의 → Support Agent
                              └─ 구매 문의 → Sales Agent
```
현재 Agent가 담당 범위를 벗어난 요청을 받으면 Handoff Tool을 호출한다. 부모 `StateGraph`는 대화 메시지와 현재 활성 Agent(`active_agent`)를 State에 저장하고 Agent 간 이동을 관리한다.

## Handoff Tool의 동작: Command.PARENT와 ToolRuntime
Handoff Tool은 다른 Agent로 제어권을 넘기려고 호출하는 Tool이다. 일반 Tool은 결과 문자열을 돌려주지만, Handoff Tool은 `Command`를 돌려줘 담당 Agent를 바꾸고 다른 Agent 노드로 이동한다.
- `graph=Command.PARENT`: Agent 내부 그래프가 아니라 Agent들을 담은 부모 그래프의 노드로 이동하라는 뜻
- `ToolRuntime`: Tool 실행 시 LangChain이 자동 주입하는 실행 정보(모델이 만드는 인자가 아님). `runtime.state`로 현재 메시지를, `runtime.tool_call_id`로 Tool 호출 ID를 얻는다.

주의점: 모델의 Handoff Tool 호출 `AIMessage`는 Agent 내부 State에만 들어가고, `Command.PARENT`로 나가면 부모 State에 자동 전달되지 않는다. 그래서 내부 State의 마지막 `AIMessage`와 그 호출을 완료하는 `ToolMessage`(같은 `tool_call_id`)를 `Command.update`로 부모 State에 함께 넣어 준다.

## Handoff 실습 1단계: Handoff Tool 정의
Handoff Tool은 마지막 AIMessage와 전환 ToolMessage를 부모 State에 넣고 담당을 바꾼다.
```python
def find_last_ai_message(messages: list) -> AIMessage:
    # 원본은 for문 + 못 찾으면 ValueError
    return next(m for m in reversed(messages) if isinstance(m, AIMessage))

@tool
def transfer_to_support(runtime: ToolRuntime) -> Command:
    """설치, 오류, 고장 등 기술 문의를 Support Agent에게 넘긴다."""
    last_ai_message = find_last_ai_message(runtime.state["messages"])
    transfer_message = ToolMessage(
        content="Support Agent로 전환했습니다.",
        tool_call_id=runtime.tool_call_id,
    )
    return Command(
        goto="support_agent",
        update={"active_agent": "support_agent",
                "messages": [last_ai_message, transfer_message]},
        graph=Command.PARENT,
    )
```
- import: `langchain.messages`의 `AIMessage`, `ToolMessage`, `langchain.tools`의 `ToolRuntime`, `tool`
- `transfer_to_sales`는 같은 구조에 목적지만 `sales_agent`다. (하나만 옮기고 헬퍼는 줄여 적음)

## Handoff 실습 2단계: Sales·Support Agent 만들기
각 Agent에는 상대 Agent로 넘기는 Handoff Tool만 준다. 자기 담당이면 직접 답하고, 아니면 Handoff Tool만 호출하도록 system prompt에 적는다.
```python
from langchain.agents import create_agent

sales_agent = create_agent(
    model=llm, tools=[transfer_to_support], name="sales_agent",
    system_prompt=(
        "너는 제품 판매 상담을 담당하는 Sales Agent다. "
        "대화 기록에서 최신 사용자 요청의 주된 의도를 확인해. "
        "제품 정보, 가격, 구매 방법에 관한 문의라면 사용자에게 직접 답해. "
        "설치, 오류, 고장 등 기술 지원이 필요한 문의라면 직접 답하지 말고 "
        "transfer_to_support만 호출해. Handoff Tool은 한 번에 하나만 호출해."
    ),
)
support_agent = create_agent(
    model=llm, tools=[transfer_to_sales], name="support_agent",
    system_prompt="(Sales와 대칭: 기술 문의는 직접 답하고, "
                  "제품·가격·구매 문의는 transfer_to_sales만 호출)",
)
```
(support_agent의 prompt는 대칭 구조라 요약해 적음)
- (내 메모) `name`: Subgraph namespace와 스트리밍 로그에 표시되는 이름

## Handoff 실습 3단계: 부모 State와 active_agent 라우팅 함수
부모 State는 `MessagesState`에 `active_agent`를 더한다. START에서는 요청 내용을 분류하지 않고 저장된 `active_agent`로 보낸다. Agent가 Handoff 없이 답을 끝내면 종료한다.
```python
from langgraph.graph import MessagesState

class MultiAgentState(MessagesState):
    active_agent: str

def route_to_active_agent(state) -> Literal["sales_agent", "support_agent"]:
    return state["active_agent"]

def route_after_agent(state) -> Literal["sales_agent", "support_agent", "__end__"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and not last.tool_calls:
        return "__end__"
    return state["active_agent"]
```
- `route_after_agent`: 마지막 메시지가 Tool 호출 없는 AIMessage면 답변 완료이므로 종료한다.

## Handoff 실습 4단계: 부모 그래프 조립과 Checkpointer
LangGraph 부모 그래프에 두 Agent를 노드로 넣고, START와 각 Agent 뒤에 조건 Edge를 단 뒤 Checkpointer로 컴파일한다.
```python
hb = StateGraph(MultiAgentState)
hb.add_node("sales_agent", sales_agent)
hb.add_node("support_agent", support_agent)
hb.add_conditional_edges(START, route_to_active_agent, ["sales_agent", "support_agent"])
for agent in ["sales_agent", "support_agent"]:
    hb.add_conditional_edges(agent, route_after_agent,
                             ["sales_agent", "support_agent", END])
handoff_graph = hb.compile(checkpointer=InMemorySaver())
```
(두 Agent의 조건 Edge 등록을 for문으로 줄여 옮김)
- Checkpointer 덕분에 같은 thread의 다음 요청은 바뀐 `active_agent`부터 시작한다.

## Handoff 실습 5단계: Sales에서 시작해 Support로 전환
첫 요청은 `active_agent="sales_agent"`로 시작한다. 이어서 기술 문의를 `subgraphs=True`로 스트리밍하면 Handoff 과정이 보인다.
```python
config = {"configurable": {"thread_id": "customer-123"}}
first = handoff_graph.invoke(
    {"messages": [HumanMessage(content="AI 스피커 가격과 구매 방법을 알려줘.")],
     "active_agent": "sales_agent"}, config=config)
print(first["active_agent"])   # sales_agent (가격대·구매처 안내로 직접 답변)

for namespace, update in handoff_graph.stream(
    {"messages": [HumanMessage(content="구매한 제품이 Wi-Fi에 연결되지 않아.")]},
    config=config, stream_mode="updates", subgraphs=True,
):
    graph_name = namespace[-1].split(":")[0] if namespace else "parent"
    print(graph_name, "->", next(iter(update)))
```
```text
sales_agent -> model        (Tool calls: ['transfer_to_support'])
parent -> sales_agent       (Support Agent로 전환했습니다.)
support_agent -> model      (Wi-Fi 2.4GHz 확인, 재부팅 등 조치 안내)
```
(원본의 메시지 출력 로직은 줄여 옮기고, 출력 괄호는 요약)

## Handoff 실습 6단계: 담당 유지와 Sales 복귀 확인
같은 config로 `active_agent`를 다시 넣지 않고 후속 질문을 보내면, 저장된 담당 Agent부터 실행된다.
- "재부팅했는데도 Wi-Fi에 연결되지 않아…" → 로그가 `support_agent -> model`에서 바로 시작하고, Support Agent가 SSID 분리·초기화·핫스팟 테스트 등을 안내했다. `active_agent`는 그대로 `support_agent`.
- "그럼 다른 색상도 있는지와 가격을 알려줘." → `support_agent -> model (transfer_to_sales)` → `parent -> support_agent (Sales Agent로 전환했습니다.)` → `sales_agent -> model`이 모델별 색상·가격을 답했다.
```python
state = handoff_graph.get_state(config).values
print(state["active_agent"], state["messages"][-1].text)
```
- 현재 담당자는 `get_state(config).values["active_agent"]`로 확인한다.
- (내 메모) 색상·가격 정보는 실제 데이터 없이 LLM이 지어낸 값이다. 실서비스라면 상품 조회 Tool이 필요하다.

## Router·Supervisor·Handoff 패턴 비교
Router, Supervisor, Handoff는 요청을 나누고 작업을 이어 가는 대표 Multi-Agent 패턴이며, 엄격히 구분하지 않고 섞어 쓸 수도 있다.
- Router: 요청을 분류해 적절한 Agent에 분배한다. 하나를 고르거나 여러 Agent에 나눠 결과를 모을 수 있다. 예: 문의를 판매/기술 지원으로 분류
- Supervisor: 작업을 위임하고 중간 결과를 보며 다음 작업을 정한다. 조사가 부족하면 추가 조사, 보고서에 문제가 있으면 재작성을 맡긴다.
- Handoff: 현재 담당자를 State에 저장하고 담당권을 넘긴다. 다시 Handoff가 일어나기 전까지 그 Agent가 대화를 맡는다.

고르는 기준: 분류·분배가 중심이면 Router, 중간 결과에 따른 작업 조율이 중심이면 Supervisor, 여러 턴에 걸친 담당 유지·전환이 중심이면 Handoff.

## Handoff 복습 Q&A
- Q. LangGraph 노드가 `Command(update=..., goto=...)`를 반환하면 무엇이 달라지나?
  A. 노드가 State 변경과 다음 실행 노드를 한 번에 정한다. 그 노드에서 나가는 Edge를 따로 등록하지 않아도 된다.
- Q. `Command[Literal["sales", "support"]]`처럼 반환 타입에 Literal을 적는 이유는?
  A. 가능한 이동 대상을 LangGraph에 알려 그래프 시각화에 동적 이동 경로를 표시하기 위해서다. 실행 자체는 없어도 된다.
- Q. Handoff Tool에서 `graph=Command.PARENT`는 무슨 뜻인가?
  A. Agent 내부 그래프가 아니라 Agent들을 담은 부모 그래프의 노드로 이동하라는 뜻이다.
- Q. Handoff Tool이 마지막 AIMessage와 ToolMessage를 `update`에 넣는 이유는?
  A. Tool 호출 AIMessage는 Agent 내부 State에만 있어 부모로 자동 전달되지 않으므로, 같은 `tool_call_id`의 ToolMessage와 짝지어 부모 State에 넣어 대화 기록을 맞춘다.
- Q. Handoff와 Supervisor의 차이는?
  A. Supervisor는 결과가 중앙으로 돌아와 Supervisor가 다음을 정하고, Handoff는 전환된 Agent가 새 담당자로 사용자와 직접 대화를 이어 간다.
