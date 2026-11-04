---
part: langchain
lesson: ReAct Agent
order: 12
source_type: ipynb
tags: [react, agent, tool-calling, toolnode, tools-condition, messagesstate, create-agent]
source: C:\Users\tnwls\aim-ai-agent\langchain_\12-react-agent_answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# ReAct Agent

## ReAct Agent 요약
ReAct Agent 레슨은 LLM이 Tool 호출과 결과 관찰을 반복하는 ReAct 루프를 LangGraph의 `StateGraph`, `ToolNode`, `tools_condition`으로 직접 만들고, 같은 구조를 `create_agent()`로 간단히 만든다. 실습은 상품 검색 Agent(정답 노트북)와, 별도 실습 노트북 `12-react-agent-practice/12-react-agent-practice.ipynb`의 로컬 파일 Agent(검색·읽기·쓰기 Tool)이다.

## ReAct 패턴이란: Reasoning + Acting 루프
ReAct는 Reasoning + Acting의 줄임말로, Function Calling(Tool Use)을 루프 안에서 반복하는 패턴이다. LLM이 텍스트 대신 "이 함수를 이 인자로 호출해줘"라는 `tool_calls`를 응답하면, 시스템이 함수를 실행하고 결과를 다시 LLM에 넘긴다.
- Think: LLM이 지금까지의 메시지로 다음 행동을 정한다.
- Act: `tool_calls` 응답 → 시스템이 Tool 실행.
- Observe: Tool 결과를 LLM에게 전달.
- 반복하다가 `tool_calls`가 없는 응답이 나오면 그것이 최종 답변(Answer).

핵심은 어떤 Tool을 몇 번 부르고 언제 멈출지를 LLM이 매 턴 결정한다는 점이다. 단, 모델의 내부 추론 전체가 보이는 것은 아니고 애플리케이션은 `tool_calls`와 최종 응답만 관찰한다. (원본에는 ReAct 루프 그림 이미지가 있다.)

## ReAct Agent Tool 정의: @tool과 docstring
ReAct Agent의 모델은 함수 구현을 보지 않고, Tool 이름·docstring·인자 타입으로 만든 schema만 보고 Tool과 인자를 고른다. 그래서 Tool 설명에 용도와 입력 형식을 구체적으로 써야 한다.
```python
from datetime import datetime
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

@tool(parse_docstring=True)
def get_current_time() -> str:
    """서버의 현재 로컬 날짜와 시간을 반환한다."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

tools = [get_current_time]
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
llm_with_tools = llm.bind_tools(tools)
```
- `parse_docstring=True`: docstring의 `Args:` 부분을 인자 설명으로 파싱한다.
- `bind_tools(tools)`: 모델이 이 Tool들을 호출할 수 있게 schema를 붙인다.
- 원본 노트북의 `bind_tools` 셀 출력에는 `NameError: name 'tools' is not defined`가 남아 있다. 셀 실행 순서 문제로 보이며, Tool 정의 셀을 먼저 실행하면 된다(내 메모).

## ReAct Agent ToolNode: tool_calls 자동 실행
LangGraph `ToolNode`는 LLM 응답의 `tool_calls`를 받아 실제 함수를 실행하는 노드다. 자동으로 하는 일은 다음과 같다.
1. 마지막 AI 메시지의 `tool_calls`에서 함수 이름과 인자를 꺼낸다.
2. 해당 함수를 실행한다.
3. 결과를 `ToolMessage`로 감싸 State에 추가한다.

한 AI 메시지에 `tool_calls`가 여러 개일 수 있고, 서로 독립이면 `ToolNode`가 함께 실행할 수 있다. 그래서 Tool이 전역 상태를 함부로 바꾸지 않게 설계한다. 직접 구현하면 다음과 같다.
```python
for tool_call in response.tool_calls:
    tool_fn = tool_map[tool_call["name"]]
    result = tool_fn.invoke(tool_call["args"])
    messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))
```

## ReAct Agent tools_condition과 MessagesState
LangGraph `tools_condition`은 마지막 메시지에 `tool_calls`가 있으면 `"tools"` 노드로, 없으면 `END`로 보내는 라우팅 함수다. 직접 구현하면 다음과 같다.
```python
def should_continue(state: MessagesState):
    if state["messages"][-1].tool_calls:
        return "tools"
    return END
```
`MessagesState`는 `messages: Annotated[list, add_messages]`가 미리 정의된 State로, 사용자·AI·Tool 메시지를 계속 누적한다. 대부분의 챗봇과 에이전트는 이 State로 충분하다.

수동 구현과 LangGraph 대응:
- `if response.tool_calls` 분기 → `tools_condition` 조건부 엣지
- Tool 실행 + `ToolMessage` 추가 → `ToolNode`
- `messages` 리스트 직접 관리 → `MessagesState`

## ReAct Agent 그래프 구성: chatbot ↔ tools 루프
LangGraph ReAct 그래프는 `chatbot` 노드가 LLM을 호출하고, `tool_calls`가 있으면 `tools` 노드를 거쳐 다시 `chatbot`으로 돌아오는 구조다.
```python
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

def chatbot(state: MessagesState):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

graph_builder = StateGraph(MessagesState)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools))
graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph = graph_builder.compile()
```
- 조건부 엣지의 매핑 dict는 생략했다. 라우팅 함수의 반환값(`"tools"`, `END`)이 노드 이름·`END`와 그대로 같으면 생략할 수 있다. 명시하면 `{"tools": "tools", END: END}`이다.

## ReAct Agent 실행 결과 확인
ReAct Agent 그래프를 `invoke()`하면 최종 State의 `messages`에 human → ai(tool_calls) → tool → ai(답변) 순서로 기록이 쌓인다.
```python
result = graph.invoke({"messages": [("human", "지금 몇 시야?")]})
for msg in result["messages"]:
    print(f"[{msg.type}] {msg.text[:300]}")
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        print(f"  -> Tool 호출: {[tc['name'] for tc in msg.tool_calls]}")
```
```text
[human] 지금 몇 시야?
[ai]
  -> Tool 호출: ['get_current_time']
[tool] 2026-09-09 10:23:18
[ai] 현재 시간은 2026년 9월 9일 오전 10시 23분입니다.
```
- Tool을 호출하는 AI 메시지는 본문이 비어 있고 `tool_calls`만 있다.

## ReAct Agent를 create_agent로 간단히 만들기
LangChain `create_agent()`를 쓰면 직접 만든 chatbot ↔ tools 루프 그래프와 같은 구조를 한 줄로 만든다. 입력·출력 형식(`messages`)도 같다.
```python
from langchain.agents import create_agent

agent = create_agent(model=llm, tools=tools)
result = agent.invoke({"messages": [("human", "지금 몇 시야?")]})
```
- 실행 결과도 human → ai(`get_current_time` 호출) → tool → ai(현재 시간 답변)로 같다.
- 직접 구성은 동작 이해와 커스터마이징에, `create_agent`는 빠른 구성에 쓴다.

## ReAct Agent 실습 문제: 상품 검색 Agent
ReAct Agent 실습은 제공 함수로 상품 검색 Agent를 `StateGraph`+`ToolNode`+`tools_condition`과 `create_agent()` 두 방식으로 만들어 비교한다.
```python
PRODUCTS = {
    "A100": {"name": "무선 키보드", "price": 39_000, "stock": 12},
    "B200": {"name": "무선 마우스", "price": 25_000, "stock": 0},
    "C300": {"name": "노트북 거치대", "price": 32_000, "stock": 7},
}

def search_products(keyword: str) -> str:
    keyword = keyword.strip().lower()
    matched = [(pid, p["name"]) for pid, p in PRODUCTS.items()
               if keyword in p["name"].lower()]
    if not matched:
        return "검색된 상품이 없습니다."
    return "\n".join(f"- {pid}: {name}" for pid, name in matched)

def get_product(product_id: str) -> str:
    p = PRODUCTS.get(product_id.upper())
    if p is None:
        return "상품을 찾을 수 없습니다."
    return f"{p['name']}: {p['price']:,}원, 재고 {p['stock']}개"
```
- 풀이는 사람이 먼저 흐름을 따라가 본다: ID가 필요하니 `search_products('무선 마우스')`로 `B200`을 얻고 `get_product('B200')`.

## ReAct Agent 실습 풀이: 상품 Tool 정의
ReAct 상품 검색 풀이는 제공 함수를 `@tool`로 감싸고, docstring에 용도와 인자 형식(예: ID 예시 `A100`)을 적는다.
```python
@tool(parse_docstring=True)
def search_products_tool(keyword: str) -> str:
    """상품명을 검색하여 상품 ID를 반환하는 함수.

    Args:
        keyword: 상품명 검색어"""
    return search_products(keyword)

@tool(parse_docstring=True)
def get_product_tool(product_id: str) -> str:
    """상품 ID로 상품명, 가격, 재고를 조회하는 함수.

    Args:
        product_id: 조회할 상품의 ID. 예) A100
    """
    return get_product(product_id)

tools = [search_products_tool, get_product_tool]
llm_with_product_tools = llm.bind_tools(tools)
```
(원본 변수명은 오타인 `llm_with_prudct_tools`이다.)

## ReAct Agent 실습 풀이: StateGraph로 상품 Agent 구성
ReAct 상품 Agent 풀이는 `MessagesState`와 같은 State를 직접 정의해 쓰고, `ToolNode`와 `tools_condition`은 LangGraph 제공 것을 쓴다.
```python
class State(TypedDict):
    messages: Annotated[list, add_messages]   # MessagesState와 동일

def chatbot(state: State):
    return {"messages": [llm_with_product_tools.invoke(state["messages"])]}

graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools))
graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph = graph_builder.compile()

result = graph.invoke({"messages": [("human", "무선 마우스의 가격과 재고를 확인해줘.")]})
```
```text
[ai] -> Tool 호출: ['search_products_tool']
[tool] - B200: 무선 마우스
[ai] -> Tool 호출: ['get_product_tool']
[tool] 무선 마우스: 25,000원, 재고 0개
[ai] 무선 마우스(B200) 가격 25,000원, 재고 0개(품절)
```
- LLM이 스스로 검색 → 상세 조회 순서로 Tool 두 개를 연달아 불렀다. (출력은 줄여 옮겼다.)

## ReAct Agent 실습 풀이: create_agent로 상품 Agent 구성
ReAct 상품 Agent를 `create_agent()`로 만들면 같은 Tool 목록만 넘기면 된다.
```python
agent = create_agent(llm, tools)
result = agent.invoke({"messages": [("human", "무선 마우스의 가격과 재고를 확인해줘.")]})
```
- 결과: `search_products_tool` → `get_product_tool` 순서로 호출하고 "무선 마우스(상품 ID: B200) 가격 25,000원, 재고 0개(품절)"라고 답한다. 직접 구성한 그래프와 Tool 호출 순서와 답이 같다.

## 로컬 파일 Agent 실습: 작업 폴더와 안전한 경로 검사
로컬 파일 Agent 실습(`12-react-agent-practice.ipynb`)은 현재 작업 폴더의 `.txt` 파일만 검색·읽기·쓰기 하도록 제한한다. 예제 파일 `langgraph.txt`, `react.txt`, `tools.txt`를 만든 뒤, 경로 검사 함수로 폴더 밖 접근과 다른 확장자를 막는다.
```python
WORKSPACE = Path.cwd().resolve()

def _resolve_path(filename: str) -> Path:
    path = (WORKSPACE / filename).resolve()
    if path.parent != WORKSPACE:        # ../ 등으로 폴더를 벗어나는 경로 차단
        raise ValueError("현재 작업 폴더 안의 파일만 사용할 수 있습니다.")
    if path.suffix.lower() != ".txt":   # 확장자 제한
        raise ValueError("txt 파일만 사용할 수 있습니다.")
    return path
```
- `resolve()`로 절대 경로로 바꾼 뒤 부모 폴더를 비교하므로 하위 폴더도 허용되지 않는다.
- Agent에게 파일 쓰기 권한을 줄 때는 이렇게 범위를 코드로 제한해야 한다(내 메모).

## 로컬 파일 Agent 실습: 검색·읽기·쓰기 함수
로컬 파일 Agent 실습에서 실제 파일 처리는 제공 함수가 맡고, Tool은 이를 호출만 한다.
```python
def search_files_impl(keyword: str) -> str:
    keyword = keyword.strip().lower()
    matched = [p.name for p in WORKSPACE.glob("*.txt")
               if keyword in p.name.lower()
               or keyword in p.read_text(encoding="utf-8").lower()]
    return "\n".join(sorted(matched)) or "검색 결과가 없습니다."

def read_file_impl(filename: str) -> str:
    path = _resolve_path(filename)
    if not path.exists():
        return "파일을 찾을 수 없습니다."
    if path.stat().st_size > 10_000:
        return "파일이 너무 커서 읽을 수 없습니다."
    return path.read_text(encoding="utf-8")

def write_file_impl(filename: str, content: str) -> str:
    path = _resolve_path(filename)
    if len(content) > 5_000:
        return "내용이 너무 길어서 저장할 수 없습니다."
    path.write_text(content, encoding="utf-8")
    return f"{path.name} 파일을 작성했습니다."
```
- 테스트: `search_files_impl("ReAct")` → `react.txt`

(for문을 컴프리헨션으로 바꾸고 주석을 빼 압축했다.)

## 로컬 파일 Agent 실습 풀이: Tool 정의와 create_agent
로컬 파일 Agent 실습은 세 함수를 호출하는 Tool을 직접 정의하고 `create_agent`로 Agent를 만든다. Tool 이름과 설명이 모델의 Tool 선택에 영향을 준다.
```python
@tool(parse_docstring=True)
def search_files_tool(keyword: str):
    """파일 이름이나 내용에 검색어가 포함된 file을 찾는 함수.

    Args:
        keyword: 검색어"""
    return search_files_impl(keyword)

@tool(parse_docstring=True)
def read_files_tool(filename: str):
    """파일 이름을 바탕으로 해당 파일의 내용을 읽는 함수.

    Args:
        filename: 파일 이름"""
    return read_file_impl(filename)

@tool(parse_docstring=True)
def write_files_tool(filename: str, content: str):
    """입력받은 content를 파일에 작성하는 함수.

    Args:
        filename: 파일 이름
        content: 내용"""
    return write_file_impl(filename, content)

llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
agent = create_agent(llm, [search_files_tool, read_files_tool, write_files_tool])
```
- 풀이는 사람이 먼저 `search → read → (정보 수집) → write` 순서를 상상해 본 뒤 Tool로 옮긴다.

## 로컬 파일 Agent 실습: stream으로 Tool 선택 과정 보기
로컬 파일 Agent를 `stream_mode="values"`로 실행하면 단계마다 마지막 메시지를 출력해 어떤 Tool을 골랐는지 볼 수 있다.
```python
question = "ReAct 관련 파일을 찾아 읽고, 핵심 내용을 summary.txt에 저장해 줘."
for state in agent.stream(
    {"messages": [{"role": "human", "content": question}]},
    stream_mode="values",
):
    message = state["messages"][-1]
    print(f"[{message.type}] {message.text}")
    if getattr(message, "tool_calls", None):
        print(f"  -> Tool 호출: {[c['name'] for c in message.tool_calls]}")
```
- 원본은 `question`을 "세종대왕에 대해서 글을 작성해서 저장해줘."로 덮어써 실행했다. 이때 Agent는 검색·읽기 없이 `write_files_tool`만 한 번 호출해 새 txt 파일을 만들었다. 그래서 마지막 셀의 `summary.txt` 확인은 작성되지 않았다는 결과가 나올 수 있다.

## ReAct Agent 복습 Q&A
- Q. ReAct Agent 루프는 언제 끝나나?
  A. LLM 응답에 `tool_calls`가 없으면 `tools_condition`이 `END`로 보내고, 그 응답이 최종 답변이 된다.
- Q. ReAct Agent에서 `ToolNode`가 자동으로 해 주는 일은?
  A. 마지막 AI 메시지의 `tool_calls`를 파싱해 함수를 실행하고, 결과를 `ToolMessage`로 State에 추가한다.
- Q. ReAct 그래프에서 `add_conditional_edges("chatbot", tools_condition)`에 매핑 dict를 생략해도 되는 이유는?
  A. `tools_condition`이 반환하는 `"tools"`와 `END`가 노드 이름·`END`와 그대로 일치하기 때문이다.
- Q. ReAct Agent의 모델은 Tool을 무엇을 보고 고르나?
  A. 함수 구현이 아니라 Tool 이름, docstring, 인자 타입으로 만든 schema를 보고 고른다.
- Q. 로컬 파일 Agent 실습에서 파일 접근을 어떻게 제한했나?
  A. `_resolve_path`에서 절대 경로의 부모가 작업 폴더인지, 확장자가 `.txt`인지 검사하고, 읽기 10,000바이트·쓰기 5,000자로 크기를 제한했다.
