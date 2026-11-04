---
part: langchain
lesson: Supervisor
order: 25
source_type: ipynb
tags: [langchain, multi-agent, supervisor, create_agent, subagent, tool, google-search]
source: C:\Users\tnwls\aim-ai-agent\langchain_\25-supervisor.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Supervisor

## Supervisor 요약
Multi-Agent 구성 방식 중 Supervisor 패턴을 다룬다. `create_agent`로 조사·작성·검토 Subagent를 만들고, 각각을 `@tool` 함수로 감싸 Supervisor Agent의 Tool로 등록해 보고서 작성 팀을 구현한다.

## Multi-Agent 시스템이란
Multi-Agent 시스템은 Agent 하나가 모든 일을 처리하는 대신, 역할이 다른 여러 Agent가 협력해 하나의 목표를 이루는 구조다. 각 Agent는 역할에 맞는 Prompt, Tool, Context를 따로 가질 수 있고, Agent 사이에 작업을 넘기고 결과를 공유하며 복잡한 일을 나눠 처리한다.

## Multi-Agent를 고려하는 이유와 주의점
Agent 하나가 역할·Tool·Context를 너무 많이 맡으면 지시가 충돌하고 Tool 선택 오류가 늘 수 있다. Multi-Agent로 역할을 나누면 이런 이점이 있다.
- 역할과 Context 분리: 각 Agent가 맡은 일에 필요한 정보에만 집중
- Tool과 권한 분리: Agent마다 필요한 Tool만 제공
- 독립적인 설계와 평가: 역할별로 Prompt, 모델, 평가 기준을 다르게 설정
- 동적인 작업 위임: 요청과 중간 결과에 따라 알맞은 Agent 선택

반대로 역할이 단순하고 순서가 고정이면 단일 Agent나 일반 Workflow가 낫다. Multi-Agent는 모델 호출 수, 지연 시간, 비용, 실패 지점을 늘리므로 역할 분리와 동적 위임의 이득이 클 때만 쓴다.

## Supervisor 패턴이란
Supervisor 패턴은 중앙의 Supervisor가 작업을 분석해 알맞은 Subagent에 나눠 주고, 각 결과를 모아 최종 응답을 만드는 Multi-Agent 구조다.
```text
사용자 → Supervisor Agent
             ├─→ Research Agent
             ├─→ Writer Agent
             └─→ Reviewer Agent
```
이 예제의 Supervisor도 ReAct 방식으로 동작한다. 필요한 작업을 판단하고 Tool을 실행한 뒤 결과를 보고 다음 행동을 정한다. 다만 여기서 Tool은 독립된 지시와 Context를 가진 Subagent를 부르는 함수다.

## Supervisor 실습 1단계: 모델과 Google Search 바인딩
Supervisor 실습에서는 일반 LLM과, Gemini의 내장 Google Search를 바인딩한 조사용 LLM을 따로 만든다. API 키는 `.env`에서 `load_dotenv()`로 불러온다.
```python
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
search_llm = llm.bind_tools([{"google_search": {}}])
```
- `bind_tools([{"google_search": {}}])`: Gemini가 서버 쪽에서 Google 검색을 쓰게 하는 내장 도구 설정

## Supervisor 실습 2단계: 조사·작성·검토 Subagent 만들기
Supervisor 아래에서 일할 Subagent 3개를 `create_agent`로 만든다. 각자 system prompt로 역할을 정한다.
```python
researcher_agent = create_agent(
    model=search_llm, tools=[], name="researcher",
    system_prompt="너는 자료 조사 전문가다. 요청받은 주제를 Google Search로 조사해. "
                  "핵심 사실과 근거를 정리하고, 각 내용의 출처를 함께 제시해.",
)
writer_agent = create_agent(
    model=llm, tools=[], name="writer",
    system_prompt="너는 보고서 작성 전문가다. 전달받은 조사 결과만을 근거로 보고서를 작성해. "
                  "제목, 개요, 본문, 결론 순서로 구성하고 출처를 유지해.",
)
reviewer_agent = create_agent(
    model=llm, tools=[], name="reviewer",
    system_prompt="너는 보고서 검토 전문가다. 구조, 가독성, 일관성, 출처 표기를 검토해. "
                  "수정이 필요하면 구체적으로 제시하고, 문제가 없으면 '승인'이라고 명시해.",
)
```
(system prompt 문장을 조금 줄여 옮김)
- 조사 Agent만 Google Search가 붙은 `search_llm`을 쓴다.

## Supervisor 실습 3단계: Subagent를 @tool로 감싸기
각 Subagent를 `@tool` 함수로 감싸 Supervisor가 Tool처럼 부를 수 있게 한다. Tool은 작업 설명(query)을 Subagent에 넘기고 마지막 응답 텍스트만 돌려준다.
```python
@tool
def research(query: str) -> str:
    """주제에 관한 최신 자료와 출처를 조사한다."""
    result = researcher_agent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].text

@tool
def write_report(query: str) -> str:
    """조사 결과를 바탕으로 보고서를 작성한다."""
    result = writer_agent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].text

@tool
def review_report(query: str) -> str:
    """보고서를 검토하고 수정 사항이나 승인 여부를 반환한다."""
    result = reviewer_agent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].text
```
- Subagent 내부의 중간 메시지는 Supervisor 대화에 섞이지 않고, 최종 결과만 ToolMessage로 들어간다.
- (내 메모) docstring이 Tool 설명이 되어 Supervisor가 어떤 Tool을 고를지 판단하는 근거가 된다.

## Supervisor 실습 4단계: Supervisor Agent 만들기
Supervisor는 Subagent Tool 세 개를 가진 Agent다. Checkpointer는 전체 대화를 관리하는 최상위 Supervisor에만 붙인다.
```python
supervisor_agent = create_agent(
    model=llm,
    tools=[research, write_report, review_report],
    system_prompt=(
        "너는 보고서 작성 팀의 Supervisor다. "
        "사용자의 요청을 분석하고 필요한 작업을 적절한 전문가에게 위임해. "
        "작업을 위임할 때는 해당 전문가에게 필요한 맥락을 충분히 전달해. "
        "전문가의 결과를 검토하고 필요한 경우 추가 작업을 요청해. "
        "근거와 출처가 포함된 완성도 높은 보고서를 최종 응답으로 제공해. "
        "중간 작업 과정은 사용자에게 설명하지 마."
    ),
    checkpointer=InMemorySaver(),
)
```
- (내 메모) "필요한 맥락을 충분히 전달해": Subagent는 Supervisor 대화 기록을 못 보므로 query에 맥락을 담아야 한다.

## Supervisor 실습 5단계: 스트리밍으로 위임 과정 확인
`stream_mode="updates"`로 실행하면 Supervisor의 `model` 노드가 어떤 Tool을 불렀는지, `tools` 노드가 무엇을 돌려줬는지 볼 수 있다.
```python
config = {"configurable": {"thread_id": "report-session-1"}}
for event in supervisor_agent.stream(
    {"messages": [HumanMessage(content="AI Agent 기술 동향에 대한 보고서를 작성해줘.")]},
    config=config, stream_mode="updates",
):
    for node_name, state in event.items():
        message = state["messages"][-1]
        print(f"Node: {node_name}")
        if getattr(message, "tool_calls", None):
            print("Tool calls:", [c["name"] for c in message.tool_calls])
        if message.text:
            print(message.text[:500])
```
- 첫 요청에서 `model → Tool calls: ['research']`, 이어서 `tools` 노드에 조사 결과(에이전틱 AI 개념, 기업 사례 등)가 찍혔다.
- 같은 thread로 "정보가 부족한 것 같은데, 추가 정보를 모아줘."를 보내자 `research`를 다시 부른 뒤 `write_report`로 넘어갔다. Checkpointer 덕분에 이전 대화를 기억한 채 추가 위임을 한 것이다.

## Supervisor 복습 Q&A
- Q. Supervisor 패턴이란?
  A. 중앙 Supervisor가 작업을 분석해 Subagent에 나눠 맡기고, 결과를 보고 다음 위임을 정하며 최종 응답을 종합하는 Multi-Agent 구조다.
- Q. 이 예제에서 Subagent를 Supervisor에 연결한 방법은?
  A. `create_agent`로 만든 Subagent를 `@tool` 함수 안에서 `invoke()`하고 마지막 메시지 텍스트를 반환하게 해, 그 함수를 Supervisor의 `tools`로 등록했다.
- Q. Supervisor 구조에서 Checkpointer는 어디에 두나?
  A. 전체 대화를 관리하는 최상위 Supervisor에만 둔다.
- Q. Multi-Agent를 쓰지 않는 편이 나은 경우는?
  A. 역할이 단순하고 실행 순서가 고정된 경우다. Multi-Agent는 호출 수, 지연, 비용, 실패 지점을 늘리기 때문이다.
- Q. Supervisor가 Subagent에 작업을 넘길 때 맥락을 충분히 담아야 하는 이유는?
  A. (내 메모) Subagent Tool은 query만 새 메시지로 넘겨 `invoke()`하므로, Subagent는 Supervisor의 대화 기록을 보지 못하고 query에 담긴 내용만 본다.
