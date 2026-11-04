---
part: langchain
lesson: Subgraph
order: 24
source_type: ipynb
tags: [langgraph, subgraph, state, wrapper, stream, subgraphs, namespace]
source: C:\Users\tnwls\aim-ai-agent\langchain_\24-subgraph.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Subgraph

## Subgraph 요약
LangGraph에서 컴파일한 그래프를 다른 그래프의 노드로 넣는 Subgraph를 다룬다. 부모와 State 스키마가 같을 때는 그대로 `add_node`하고, 다를 때는 래퍼 함수로 입력·출력을 변환하며, `subgraphs=True` 스트리밍으로 내부 실행을 확인한다.

## LangGraph Subgraph란
LangGraph에서는 따로 만든 그래프를 부모 그래프의 노드로 등록할 수 있고, 이렇게 다른 그래프 안에 들어간 그래프를 Subgraph라고 한다. 쓰는 이유는 다음과 같다.
- 재사용: 만들어 둔 그래프를 여러 워크플로우의 노드로 쓴다.
- 개발·관리 용이: 복잡한 흐름을 역할별 그래프로 나눠 따로 만들고 테스트하며, 부모는 전체 순서에 집중한다.
- State 분리: Subgraph가 내부 데이터를 따로 관리하고 부모와는 필요한 입력·출력만 주고받는다.

단순 작업은 일반 노드로 충분하다. 여러 단계로 된 흐름을 한 단위로 묶거나 재사용할 때 Subgraph가 유리하다.

## Subgraph 공유 State: 같은 스키마일 때 그대로 add_node
LangGraph에서 부모와 Subgraph의 State 스키마가 같으면 컴파일된 그래프를 그대로 `add_node`에 넘긴다. 예제는 `messages`와 `research`를 가진 공통 `AgentState`를 쓴다.
- `messages`: 사용자 요청과 최종 보고서
- `research`: 리서치 Subgraph가 쓰고, 작성 Subgraph가 읽는 조사 결과

노드가 돌려주는 값은 State의 변경분이며, 반환하지 않은 필드는 기존 값이 유지된다. 같은 스키마여도 각 노드는 필요한 필드만 갱신하면 된다.
```python
from typing import Annotated, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")  # 키는 .env에서 로드

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    research: str
```

## Subgraph 실습 1단계: 리서치 Subgraph 만들기
리서치 Subgraph는 시작 알림 노드와 조사 노드 두 개로 이뤄지고, 조사 결과를 `research` 필드에 쓴다.
```python
def research_start_node(state: AgentState):
    print("리서치 작업을 시작합니다.")
    return {}

def research_node(state: AgentState):
    system = SystemMessage(content="너는 리서치 전문가다. 주어진 주제의 핵심 사실 3개를 정리해.")
    response = llm.invoke([system] + state["messages"])
    return {"research": response.text}

research_builder = StateGraph(AgentState)
research_builder.add_node("research_start", research_start_node)
research_builder.add_node("research", research_node)
research_builder.add_edge(START, "research_start")
research_builder.add_edge("research_start", "research")
research_builder.add_edge("research", END)
research_graph = research_builder.compile()
```
- `return {}`: State를 바꾸지 않는 노드는 빈 dict를 돌려준다.

## Subgraph 실습 2단계: 작성 Subgraph 만들기
작성 Subgraph는 `research` 조사 결과와 사용자 요청을 함께 LLM에 넘겨 보고서를 만들고, 결과를 `messages`에 추가한다.
```python
def writing_node(state: AgentState):
    system = SystemMessage(content="너는 보고서 작성 전문가다. 사용자 요청과 조사 결과를 바탕으로 간결한 보고서를 작성해.")
    request = HumanMessage(content=f"다음 조사 결과로 보고서를 작성해.\n\n{state['research']}")
    response = llm.invoke([system] + state["messages"] + [request])
    return {"messages": [response]}

writing_builder = StateGraph(AgentState)
writing_builder.add_node("write", writing_node)
writing_builder.add_edge(START, "write")
writing_builder.add_edge("write", END)
writing_graph = writing_builder.compile()
```

## Subgraph 실습 3단계: 부모 그래프에 Subgraph를 노드로 등록
부모 그래프는 일반 노드 `prepare` 다음에 컴파일된 두 Subgraph를 노드로 이어 붙인다.
```python
def prepare_node(state: AgentState):
    print("요청 처리를 시작합니다.")
    return {}

parent_builder = StateGraph(AgentState)
parent_builder.add_node("prepare", prepare_node)         # 일반 노드
parent_builder.add_node("researcher", research_graph)   # 컴파일된 그래프를 그대로
parent_builder.add_node("writer", writing_graph)
parent_builder.add_edge(START, "prepare")
parent_builder.add_edge("prepare", "researcher")
parent_builder.add_edge("researcher", "writer")
parent_builder.add_edge("writer", END)
parent_graph = parent_builder.compile()
```
- 흐름: `START → prepare → researcher(Subgraph) → writer(Subgraph) → END`

## Subgraph 스트리밍: subgraphs=False와 True 차이
LangGraph `stream()`의 기본값 `subgraphs=False`에서는 부모 그래프 노드의 결과만 오고, Subgraph는 노드 하나로 보인다. `subgraphs=True`로 하면 Subgraph 내부 노드의 결과까지 온다.
- `subgraphs=False`: `chunk`만 돌려준다.
- `subgraphs=True`: `(namespace, chunk)` 튜플을 돌려준다.
- `namespace`: 이벤트가 난 그래프의 경로. 부모는 `()`, Subgraph는 `('researcher:<id>',)` 형태
- `chunk`: 그 단계의 State 변경분. `stream_mode="updates"`에서는 `{노드 이름: 변경분}`
```python
for namespace, chunk in parent_graph.stream(
    {"messages": [HumanMessage(content="LangGraph의 Subgraph 기능에 대해 정리해줘.")]},
    subgraphs=True,
    stream_mode="updates",
):
    for node_name, state in chunk.items():
        print(f"Graph: {namespace} / Node: {node_name}")
```
(원본의 research·messages 앞 300자 출력 부분은 생략)

## Subgraph 스트리밍 실행 결과 비교
LangGraph Subgraph를 `subgraphs=False`로 스트리밍하면 노드가 `prepare`, `researcher`, `writer` 세 개만 보인다. `prepare`는 State 변경이 없어 `None`으로 찍힌다.

`subgraphs=True`로 스트리밍하면 순서가 다음처럼 바뀐다.
```text
Graph: () / Node: prepare
Graph: ('researcher:6d45...',) / Node: research_start
Graph: ('researcher:6d45...',) / Node: research
Graph: () / Node: researcher
...
```
(출력 형식을 한 줄로 줄여 옮김)
- Subgraph 내부 노드(`research_start`, `research`)가 namespace와 함께 추가로 나온다.
- 내부 노드가 끝나면 부모 기준의 `researcher` 노드 업데이트가 한 번 더 나온다.

## Subgraph State가 다를 때: 래퍼 함수로 변환
LangGraph에서 부모와 Subgraph의 State 전체 구조가 달라도, 주고받는 필드 이름과 형식이 맞으면 컴파일된 Subgraph를 그대로 `add_node`할 수 있다. 필드 이름이나 형식이 다르면 래퍼 함수에서 입력·출력을 변환한다.
- 필드 이름이 다른 경우: 부모 `analysis_result` ↔ Subgraph `analysis`
- 데이터 형식이 다른 경우: 부모는 `messages`(메시지 목록), Subgraph는 `request`(문자열)

기존 그래프를 State 구조가 다른 부모에서 재사용할 때 이런 변환이 필요하다. 예제는 주제를 분석한 뒤 보고서로 쓰며, 래퍼가 마지막 사용자 메시지를 `request`로 넘기고 돌아온 `analysis`를 `analysis_result`에 저장한다.

## Subgraph 실습 4단계: 다른 State를 쓰는 분석 Subgraph
분석 Subgraph는 `request` 문자열을 받아 `analysis`를 만드는 독립된 State를 쓴다.
```python
class AnalysisState(TypedDict):
    request: str
    analysis: str

def analysis_node(state: AnalysisState):
    system = SystemMessage(content="사용자가 요청한 주제를 분석하여 핵심 쟁점 3개와 각각의 장단점을 정리해.")
    response = llm.invoke([system, HumanMessage(content=state["request"])])
    return {"analysis": response.text}

analysis_builder = StateGraph(AnalysisState)
analysis_builder.add_node("analyze", analysis_node)
analysis_builder.add_edge(START, "analyze")
analysis_builder.add_edge("analyze", END)
analysis_graph = analysis_builder.compile()
```

## Subgraph 실습 5단계: 부모 State와 래퍼 함수 정의
부모 State는 `messages`, `analysis_result`를 가진다. 래퍼 함수가 부모 State → Subgraph 입력 → 부모 State로 값을 옮긴다.
```python
class ParentState(TypedDict):
    messages: Annotated[list, add_messages]
    analysis_result: str

def analysis_wrapper(state: ParentState):
    sub_result = analysis_graph.invoke({"request": state["messages"][-1].text})
    return {"analysis_result": sub_result["analysis"]}

def report_node(state: ParentState):
    system = SystemMessage(content="분석 결과를 바탕으로 간결한 보고서를 작성해.")
    response = llm.invoke([system, HumanMessage(content=state["analysis_result"])])
    return {"messages": [response]}
```
- 래퍼는 `messages` 목록의 마지막 텍스트를 `request` 문자열로, `analysis`를 `analysis_result`로 옮긴다.

## Subgraph 실습 6단계: 래퍼 노드로 부모 그래프 조립
LangGraph 부모 그래프에는 Subgraph 대신 래퍼 함수 `analysis_wrapper`를 노드로 등록하고, 보고서 노드로 잇는다.
```python
parent_builder = StateGraph(ParentState)
parent_builder.add_node("analysis", analysis_wrapper)  # 래퍼 함수를 노드로
parent_builder.add_node("report", report_node)
parent_builder.add_edge(START, "analysis")
parent_builder.add_edge("analysis", "report")
parent_builder.add_edge("report", END)
diff_state_graph = parent_builder.compile()
```
- 래퍼 안에서 `invoke()`로 부른 Subgraph도 `subgraphs=True` 스트리밍에서 `('analysis:<id>',)` namespace의 `analyze` 노드로 보였다.

## Subgraph 실습 문제: 학습 콘텐츠 생성 그래프
실습 문제: 학습 주제를 설명하고, 그 설명으로 확인 문제 3개를 만드는 그래프를 구현한다.
- 부모 `LearningState`: `topic`, `explanation`, `quiz`
- 설명 Subgraph: 부모와 같은 `LearningState`를 쓰며 `topic`으로 `explanation`을 갱신
- 퀴즈 Subgraph: 별도 `QuizState`를 쓰며 `source_text`로 `questions` 생성
- 래퍼 함수: `explanation` → `source_text`로 넘기고, `questions` → 부모 `quiz`에 저장
- 부모 흐름: 설명 → 퀴즈 생성
- `{"topic": "LangGraph의 State와 Reducer"}`로 `subgraphs=True` 실행

State에는 작업 데이터만 두고, LLM 메시지는 각 노드에서 구성한다.

## Subgraph 실습 문제 풀이: 설명 Subgraph
풀이 코드. 부모와 같은 `LearningState`로 노드 하나짜리 설명 Subgraph를 만든다.
```python
class LearningState(TypedDict):
    topic: str
    explanation: str
    quiz: str

def explanation_node(state: LearningState):
    system = SystemMessage(content="너는 개념 설명 전문가다. 학습 주제를 초보자도 이해할 수 있게 설명해.")
    response = llm.invoke([system, HumanMessage(content=state["topic"])])
    return {"explanation": response.text}

builder = StateGraph(LearningState)
builder.add_node("explanation_node", explanation_node)
builder.add_edge(START, "explanation_node")
builder.add_edge("explanation_node", END)
explanation_graph = builder.compile()

# 단독 테스트
print(explanation_graph.invoke({"topic": "랭그래프의 서브그래프"})["explanation"])
```
- 단독 테스트 결과로 서브그래프를 회사 전담팀에 비유한 초보자용 설명이 나왔다.

## Subgraph 실습 문제 풀이: 퀴즈 Subgraph와 래퍼 함수
풀이 코드. 퀴즈 Subgraph는 `QuizState`를 쓰고, 래퍼 함수가 부모 State와 값을 주고받는다.
```python
class QuizState(TypedDict):
    source_text: str
    questions: str

def quiz_node(state: QuizState):
    system = SystemMessage(content="너는 퀴즈 출제 전문가다. 설명 내용만 활용해 확인 문제 3개를 만들어.")
    response = llm.invoke([system, HumanMessage(content=state["source_text"])])
    return {"questions": response.text}

builder = StateGraph(QuizState)
builder.add_node("quiz_node", quiz_node)
builder.add_edge(START, "quiz_node")
builder.add_edge("quiz_node", END)
quiz_graph = builder.compile()

def quiz_wrapper(state: LearningState):   # 부모 그래프의 노드
    result = quiz_graph.invoke({"source_text": state["explanation"]})
    return {"quiz": result["questions"]}
```
- 노트북에서는 "파이썬은 프로그래밍 언어다…" 같은 짧은 문장으로 `quiz_graph`를 단독 테스트해 문제 3개와 정답이 나오는 것을 확인했다.

## Subgraph 실습 문제 풀이: 부모 그래프 조립과 실행
풀이 코드. 설명 Subgraph는 그래프 그대로, 퀴즈는 래퍼 함수로 등록한다.
```python
builder = StateGraph(LearningState)
builder.add_node("explanation", explanation_graph)  # 노드가 그래프 그 자체
builder.add_node("quiz", quiz_wrapper)              # 그래프를 감싼 함수
builder.add_edge(START, "explanation")
builder.add_edge("explanation", "quiz")
builder.add_edge("quiz", END)
parent_graph = builder.compile()

for namespace, chunk in parent_graph.stream(
    {"topic": "LangGraph의 State와 Reducer"},
    subgraphs=True, stream_mode="updates",
):
    for node_name, state in chunk.items():
        print(f"Graph: {namespace} / Node: {node_name}")
        print(state)
```
(출력 부분은 줄여 옮김)
- 첫 이벤트는 `('explanation:<id>',)` namespace의 `explanation_node`로, State를 "공유 노트", Reducer를 "업데이트 규칙"에 비유한 설명이 담겼다.

## Subgraph 복습 Q&A
- Q. LangGraph에서 부모와 Subgraph의 State 스키마가 같을 때 Subgraph를 어떻게 등록하나?
  A. 컴파일된 Subgraph를 그대로 `add_node("이름", compiled_graph)`로 넘긴다.
- Q. 부모와 Subgraph의 필드 이름이나 형식이 다르면 어떻게 하나?
  A. 래퍼 함수 안에서 부모 State를 Subgraph 입력으로 바꿔 `invoke()`하고, 결과를 부모 필드로 옮겨 반환한 뒤 그 함수를 노드로 등록한다.
- Q. Subgraph 내부 노드 실행까지 스트리밍으로 보려면?
  A. `stream(..., subgraphs=True)`를 쓴다. 그러면 `(namespace, chunk)`가 오고, namespace로 어느 그래프의 이벤트인지 구분한다.
- Q. `subgraphs=True` 스트리밍에서 부모 그래프 이벤트의 namespace는?
  A. 빈 튜플 `()`이다. Subgraph 이벤트는 `('노드이름:<id>',)` 형태다.
- Q. Subgraph를 쓰면 좋은 경우는?
  A. 여러 단계로 된 작업 흐름을 한 단위로 묶어 관리·재사용하거나, 내부 State를 부모와 분리하고 싶을 때다. 단순 작업은 일반 노드로 충분하다.
