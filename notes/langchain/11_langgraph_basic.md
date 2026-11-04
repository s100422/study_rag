---
part: langchain
lesson: LangGraph 기초
order: 11
source_type: ipynb
tags: [langgraph, stategraph, state, node, edge, conditional-edge, reducer, workflow]
source: C:\Users\tnwls\aim-ai-agent\langchain_\11-langgraph-basic_answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# LangGraph 기초

## LangGraph 기초 요약
LangGraph의 State, Node, Edge로 직선형 그래프, 조건 분기, 루프를 만들고 Reducer로 State 병합 방식을 정하는 레슨이다. 실습으로 감정 분석 라우터, 숫자 맞히기, 글 작성→검토→재작성 그래프를 만들고, 그래프를 클래스로 감싸 LLM을 가짜 모델로 바꿔 테스트한다.

## LangGraph가 필요한 이유: 직선형 Chain의 한계
LangChain의 LCEL Chain은 `입력 → 프롬프트 → 모델 → 파서 → 결과`처럼 정해진 순서로 흐르는 직선형 파이프라인에 잘 맞는다. 하지만 실제 서비스에는 실행 중에 다음 행동을 정해야 하는 경우가 많다.
- 문의 유형(환불/제품 문의)에 따라 다른 처리 흐름으로 보내기 → 조건부 Edge
- 검색 결과가 부족하면 질문을 바꿔 재검색, 정해진 횟수에서 중단 → 순환 구조 + 조건부 Edge
- 단계마다 중간 결과 공유·누적 → State, Reducer
- 결제·메일 발송 전 사람 승인 대기 후 재개 → Interrupt, Checkpoint
- 여러 분석을 병렬로 돌리고 취합 → Send, Reducer
- 오류 후 저장된 상태에서 재개 → Checkpoint
- LLM이 어떤 Tool을 몇 번 쓸지 결정 → Agent, ToolNode

일반 Python 코드로도 구현은 되지만, 분기·반복·상태 저장이 늘수록 제어 로직이 Chain 밖의 if/for문으로 흩어져 추적과 재시작이 어려워진다. LangGraph는 이런 흐름과 상태 변화를 명시적인 그래프로 관리하게 해 주는 프레임워크다.

## LangGraph 이전 방식: Python 루프로 재검색 구현
LangGraph 없이 "검색 결과가 부족하면 질문을 바꿔 재검색"을 구현하면, 반복과 종료 조건을 Python `for`문이 직접 관리하게 된다. 모델 호출은 Chain 안에 있어도 흐름 제어는 밖에 있다.
```python
question = "AI 반도체 시장의 전망은?"
for attempt in range(3):
    context = format_docs(retriever.invoke(question))
    check = llm.invoke([HumanMessage(content=
        f"질문: {question}\n\n검색 결과:\n{context}\n\n"
        "이 검색 결과가 질문에 답변하기에 충분한가? 'yes' 또는 'no'로만 답해.")])
    if "yes" in check.text.lower():
        break
    rewrite = llm.invoke([HumanMessage(content=
        f"'{question}'으로 검색했지만 결과가 부족했다. "
        "같은 의도의 다른 표현으로 질문만 다시 써줘.")])
    question = rewrite.text
```
- 검색기는 Chroma(`collection_name="spri_ai_brief"`, `persist_directory="./chroma_db"`)에 `k=3`, 모델은 `ChatGoogleGenerativeAI(model="gemini-3.6-flash")`, 임베딩은 `gemini-embedding-2`이다.

(print 문을 빼고 프롬프트를 줄여 압축했다.)

## LangGraph 제어 방식 스펙트럼: Chain, Workflow, Agent
LangGraph 레슨은 AI 앱의 제어 방식을 "누가 흐름을 정하나"의 스펙트럼으로 설명한다.
- Chain: 개발자가 모든 흐름을 고정한다. 예: 번역 → 요약 → 출력.
- Workflow: 개발자가 분기와 루프를 설계한다. 예: 검색 결과가 부족하면 재검색.
- Agent: LLM이 다음 행동을 결정한다. 예: 어떤 Tool을 몇 번 쓸지 LLM이 판단.
- Autonomous Agent: 완전 자율.

Chain은 스펙트럼의 가장 왼쪽이고, LangGraph로는 이 스펙트럼 전체를 구현할 수 있다.

## LangGraph 핵심 개념: State, Node, Edge
LangGraph 그래프는 세 가지로 구성된다.
- State: 그래프 전체가 공유하는 데이터. 모든 노드가 읽고 쓰는 칠판과 같다.
- Node: 처리 단계 하나를 맡는 Python 함수. State를 받아 바꿀 값을 돌려준다.
- Edge: 노드 사이의 연결. 다음에 어느 노드로 갈지 정한다.

특수 노드 `START`와 `END`는 그래프의 시작과 종료 지점이다. (원본에는 그래프 개념 그림 이미지 2개가 있다.)

## LangGraph State 정의: TypedDict
LangGraph State는 보통 `TypedDict`로 정의한다. `TypedDict`는 `typing` 표준 라이브러리 타입으로, 딕셔너리의 키 이름과 값 타입을 명시한다. 실행 중에는 일반 `dict`와 같지만 IDE 자동완성과 타입 검사를 받을 수 있다.
```python
from typing import TypedDict

class State(TypedDict):
    question: str
    answer: str
```

## LangGraph Node 정의: State를 받아 업데이트 반환
LangGraph 노드는 State를 인자로 받아, 바꿀 필드만 dict로 반환하는 Python 함수다. 반환한 dict는 기존 State에 병합된다.
```python
llm = ChatGoogleGenerativeAI(model=MODEL_NAME)

def chatbot(state: State):
    response = llm.invoke(state["question"])
    return {"answer": response.text}
```
노드 함수 패턴은 항상 같다.
1. `state`를 인자로 받는다.
2. 필요한 값을 꺼내 처리한다.
3. 업데이트할 필드만 dict로 반환한다.

## LangGraph 기본 그래프: 구성, 컴파일, 실행
LangGraph 기본 그래프 `START → chatbot → END`는 `StateGraph`에 노드와 엣지를 등록하고 컴파일해서 만든다.
```python
from langgraph.graph import END, START, StateGraph

graph_builder = StateGraph(State)              # State 스키마로 생성
graph_builder.add_node("chatbot", chatbot)     # (이름, 함수)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()                # 실행 가능한 그래프

result = graph.invoke({"question": "LangGraph가 뭐야?"})
print(result["answer"])
```
- `graph.invoke(초기 State)`: 모든 노드를 실행한 뒤 최종 State를 반환한다.

## LangGraph 그래프 시각화
LangGraph 그래프 구조는 Mermaid 이미지로 그릴 수 있다. Jupyter에서는 `IPython.display`로 바로 보여 주고, 일반 `.py` 스크립트에서는 PNG 파일로 저장한다.
```python
# Jupyter
from IPython.display import Image, display
display(Image(graph.get_graph().draw_mermaid_png()))

# .py 파일
png_data = graph.get_graph().draw_mermaid_png()
with open("graph.png", "wb") as f:
    f.write(png_data)
```

## LangGraph 조건부 분기: 언어 감지 라우터 노드
LangGraph 조건 분기 예제는 질문 언어를 감지해 한국어면 한국어로, 영어면 영어로 답한다. 흐름은 `START → detect_language → answer_ko 또는 answer_en → END`이다.
```python
class RouterState(TypedDict):
    question: str
    language: str
    answer: str

def detect_language(state: RouterState):
    result = llm.invoke(
        f"다음 문장의 언어가 한국어면 'ko', 영어면 'en'으로만 답해: {state['question']}")
    return {"language": result.text.strip().lower()}

def answer_ko(state: RouterState):
    return {"answer": llm.invoke(f"한국어로 답변해줘: {state['question']}").text}

def answer_en(state: RouterState):
    return {"answer": llm.invoke(f"Answer in English: {state['question']}").text}
```

## LangGraph add_conditional_edges로 분기 연결
LangGraph에서 `add_edge`는 다음 노드가 고정이고, `add_conditional_edges`는 라우팅 함수의 반환 문자열에 따라 다음 노드가 정해진다. 라우팅 함수는 State를 받아 문자열을 돌려줄 뿐 State를 바꾸지 않는다.
```python
def route_by_language(state: RouterState):
    return "ko" if "ko" in state["language"] else "en"

graph_builder = StateGraph(RouterState)
graph_builder.add_node("detect_language", detect_language)
graph_builder.add_node("answer_ko", answer_ko)
graph_builder.add_node("answer_en", answer_en)
graph_builder.add_edge(START, "detect_language")
graph_builder.add_conditional_edges(
    "detect_language",          # 출발 노드
    route_by_language,          # 라우팅 함수
    {"ko": "answer_ko", "en": "answer_en"},  # 반환값 → 도착 노드
)
graph_builder.add_edge("answer_ko", END)
graph_builder.add_edge("answer_en", END)
router_graph = graph_builder.compile()
```
(라우팅 함수의 if/else를 한 줄로 줄였다.)

## LangGraph graph.stream으로 노드별 실행 확인
LangGraph `graph.stream()`은 노드가 하나 실행될 때마다 결과를 순서대로 내보내므로 어떤 분기를 탔는지 확인할 수 있다. `llm.stream()`이 토큰 조각 단위라면 `graph.stream()`은 노드 단위다.
```python
# 기본: 노드 이름 → 그 노드가 반환한 업데이트
for event in router_graph.stream({"question": "파이썬의 장점이 뭐야?"}):
    for node_name, value in event.items():
        print(f"[{node_name}] {value}")

# 단계마다 전체 State 보기
for state in router_graph.stream(
    {"question": "파이썬의 장점이 뭐야?"}, stream_mode="values"):
    print(state)
```
- 기본 모드는 각 노드가 반환한 State 업데이트만 준다.
- `stream_mode="values"`: 각 단계 후의 전체 State를 준다.

## LangGraph 루프: 조건부 엣지로 반복과 종료
LangGraph 루프는 조건부 엣지가 이전 노드로 다시 연결되게 만들면 된다. 예제는 `count`를 1씩 올리다가 5가 되면 끝낸다.
```python
class CountState(TypedDict):
    count: int

def increment(state: CountState):
    return {"count": state["count"] + 1}

def route_by_count(state: CountState):
    return "end" if state["count"] >= 5 else "continue"

count_builder = StateGraph(CountState)
count_builder.add_node("increment", increment)
count_builder.add_edge(START, "increment")
count_builder.add_conditional_edges(
    "increment", route_by_count,
    {"continue": "increment", "end": END})
count_graph = count_builder.compile()

for event in count_graph.stream({"count": 0}):
    print(event)   # {'increment': {'count': 1}} ... {'count': 5}
```
- `"continue": "increment"`: 자기 자신으로 돌아가 반복한다.
- 종료 조건이 없으면 무한 루프가 되므로 반드시 둔다(내 메모: LangGraph 기본 recursion_limit에 걸려 오류가 난다).

## LangGraph Node를 나누는 기준
LangGraph에서 작업을 별도 Node로 나눌지는 다음 기준으로 판단한다.
- 책임 분리: 역할이 다른 작업은 다른 Node로.
- 의미 있는 상태 변화: 중간 결과를 State에 저장해 다음 단계가 써야 하면 나눈다.
- 분기·재시도: 결과에 따라 경로가 달라지거나 그 작업만 다시 돌려야 하면 독립 Node로.
- 관찰: 결과, 소요 시간, 오류를 단계별로 보고 싶으면 나눈다.

반대로 항상 함께 실행되고 따로 분기·재시도·관찰할 필요가 없는 작은 작업은 한 Node 안에서 처리해도 된다. 예를 들어 언어 감지 예제는 감지와 답변 생성을 별도 Node로 나눴다.

## LangGraph Reducer: State 병합 방식 정하기
LangGraph에서 노드가 반환한 값은 기본적으로 기존 State 값을 덮어쓴다. State 필드에 Reducer를 붙이면 기존 값과 새 값을 합치는 방법을 정할 수 있다. `Annotated[기본 타입, 메타데이터]`의 메타데이터 자리에 함수를 넣으면 LangGraph가 그 함수를 Reducer로 쓴다.
```python
import operator
from typing import Annotated
from langgraph.graph.message import add_messages

class ReducerDemo(TypedDict):
    name: str                                # 덮어쓰기
    messages: Annotated[list, add_messages]  # 대화 메시지 누적
    logs: Annotated[list, operator.add]      # 리스트 이어붙이기
```
선택 기준:
- 최신 값만 필요(이름, 최종 판정): Reducer 없음
- 대화 기록: `add_messages`. 여러 입력 형식을 메시지 객체로 바꿔 누적하는 메시지 전용 Reducer다.
- 로그·결과 목록: `operator.add`. 단순 `+` 연결이다.

## LangGraph Reducer 실습: a → b → c 그래프
LangGraph Reducer 예제는 노드 a, b, c가 차례로 `name`, `messages`, `logs`를 반환하게 하고 최종 State를 본다.
```python
def step_a(state: ReducerDemo):
    return {"name": "A가 설정",
            "messages": [HumanMessage(content="안녕")],
            "logs": ["A 실행"]}
# step_b: "B가 덮어씀", AIMessage("반가워!"), ["B 실행"]
# step_c: "C가 덮어씀", HumanMessage("잘 가!"), ["C 실행"]

demo_builder = StateGraph(ReducerDemo)
for n, f in [("a", step_a), ("b", step_b), ("c", step_c)]:
    demo_builder.add_node(n, f)
demo_builder.add_edge(START, "a")
demo_builder.add_edge("a", "b")
demo_builder.add_edge("b", "c")
demo_builder.add_edge("c", END)
result = demo_builder.compile().invoke({"messages": [], "logs": []})
```
- `name`은 마지막 값 "C가 덮어씀"만 남는다.
- `logs`는 `["A 실행", "B 실행", "C 실행"]`으로 누적된다.
- `messages`는 human/ai/human 메시지 3개가 순서대로 쌓인다.

(step_b, step_c는 주석으로 줄이고 add_node를 for문으로 묶었다.)

## Chain과 LangGraph 비교
LangChain Chain과 LangGraph의 차이를 항목별로 정리하면 다음과 같다.
- 흐름: Chain은 직선(A → B → C), LangGraph는 분기와 루프가 가능하다.
- 상태: Chain은 이전 단계 출력만 넘기고, LangGraph는 State로 전체를 공유한다.
- 제어: Chain은 순서가 고정, LangGraph는 조건에 따라 동적으로 결정한다.
- 디버깅: Chain은 단계별 출력 확인, LangGraph는 그래프 시각화와 노드별 트레이싱.
- 적합한 경우: Chain은 단순 파이프라인, LangGraph는 분기·반복·상태 관리가 필요한 경우.

## LangGraph 실습 문제 1: 감정 분석 라우터
LangGraph 실습 1은 문장의 감정을 분석해 긍정이면 긍정 응답, 부정이면 위로 응답을 만드는 그래프다.
- 흐름: `START → analyze → (긍정) respond_positive / (부정) respond_negative → END`
- 테스트 입력: `{"text": "오늘 승진했어! 너무 기뻐!"}`, `{"text": "프로젝트가 엎어졌어... 힘들다"}`

## LangGraph 실습 1 풀이: 감정 분석 노드와 라우팅
LangGraph 감정 분석 풀이는 `analyze`가 LCEL 체인으로 `positive`/`negative`를 받고, 라우팅 함수가 정리 후 분기한다.
```python
class State(TypedDict):
    text: str
    sentiment: str
    response: str

def analyze(state: State):
    prompt = PromptTemplate.from_template(
        "다음 <text>에 대해서 감정을 분석해줘. 긍정이면 'positive' "
        "부정이면 'negative'로 응답해줘. <text>{text}</text>")
    chain = prompt | llm | StrOutputParser()
    return {"sentiment": chain.invoke({"text": state["text"]})}

def response_positive(state: State):
    r = llm.invoke(f"다음 <text>에 대해서 긍정적인 답변을 해줘. <text>{state['text']}</text>")
    return {"response": r.text}

def response_negative(state: State):
    r = llm.invoke(f"다음 <text>에 대해서 위로의 답변을 해줘. <text>{state['text']}</text>")
    return {"response": r.text}

def route_by_sentiment(state: State):
    s = state["sentiment"].strip().lower()   # 모델 출력 흔들림 대비
    return "positive" if s == "positive" else "negative"
```
- 풀이 주석: structured output을 쓰면 더 쉽게 해결된다.

## LangGraph 실습 1 풀이: 감정 분석 그래프 조립
LangGraph 감정 분석 라우터는 `analyze` 다음에 조건부 엣지로 두 응답 노드 중 하나를 고른다.
```python
graph = StateGraph(State)
graph.add_node("analyze", analyze)
graph.add_node("response_positive", response_positive)
graph.add_node("response_negative", response_negative)
graph.add_edge(START, "analyze")
graph.add_conditional_edges(
    "analyze", route_by_sentiment,
    {"positive": "response_positive", "negative": "response_negative"})
graph = graph.compile()

for event in graph.stream({"text": "와! 오늘 승진함!"}):
    for node_name, value in event.items():
        print(f"[{node_name}] {value}")
```
- 원본 풀이에는 응답 노드 → `END` 엣지가 없다. 나가는 엣지가 없는 노드에서 실행이 끝나지만, `add_edge("response_positive", END)`처럼 명시하는 편이 문제 그림과 맞다(내 메모).

## LangGraph 실습 문제 2: 숫자 맞히기 루프
LangGraph 실습 2는 LLM이 1~100 사이 숫자를 추측하고, 틀리면 범위를 좁혀 다시 추측하는 그래프다.
- 흐름: `START → guess → check → (정답) END / (오답) guess로 돌아감`
- 정답보다 작게 추측하면 `low`를 올리고, 크면 `high`를 내린다. 정답이 37일 때 50을 추측하면 다음 범위는 1~49.
- 테스트 입력: `guess_graph.stream({"target": 37})`

풀이 메모: 노드를 나누는 기준은 역할·책임·State 변경이다. 실제로는 "추측 노드 + 범위 조정 노드 + 라우팅 함수"로 구성했다.

## LangGraph 실습 2 풀이: 숫자 맞히기 노드와 라우팅
LangGraph 숫자 맞히기 풀이는 `guess` 노드가 추측하고, 라우팅 함수가 정답 또는 최대 시도(5회)를 확인한 뒤, 오답이면 `change_high_low` 노드가 범위를 좁힌다.
```python
MAX_ATTEMPT = 5

class GuessState(TypedDict):
    target: int
    low: int
    high: int
    guess: int
    attempt: int

def guess(state: GuessState):
    attempt = state.get("attempt", 0)
    r = llm.invoke(f"{state['low']} ~ {state['high']}까지의 숫자를 골라줘. 단, 정수만 답변해.")
    return {"guess": int(r.text), "attempt": attempt + 1}

def route_success(state: GuessState):
    if state["attempt"] >= MAX_ATTEMPT or state["target"] == state["guess"]:
        return "end"
    return "continue"

def change_high_low(state: GuessState):
    if state["target"] > state["guess"]:
        return {"low": state["guess"] + 1}
    return {"high": state["guess"] - 1}
```
(print 문과 주석을 빼고 두 종료 조건을 한 줄로 합쳐 압축했다.)

## LangGraph 실습 2 풀이: 숫자 맞히기 그래프 조립
LangGraph 숫자 맞히기 그래프는 `guess` 뒤 조건부 엣지로 끝내거나 `change_high_low`로 보내고, `change_high_low`는 다시 `guess`로 돌아가는 루프다.
```python
b = StateGraph(GuessState)
b.add_node("guess", guess)
b.add_node("change_high_low", change_high_low)
b.add_edge(START, "guess")
b.add_conditional_edges("guess", route_success,
                        {"end": END, "continue": "change_high_low"})
b.add_edge("change_high_low", "guess")
guess_graph = b.compile()

for event in guess_graph.stream({"target": 37, "low": 1, "high": 100}):
    for node_name, value in event.items():
        print(f"[{node_name}] {value}")
```
- 문제의 테스트 입력은 `{"target": 37}`뿐이지만, 풀이의 `guess` 노드는 `state['low']`를 바로 읽으므로 `low`, `high` 초기값도 넣어야 한다.
- `route_success`는 시도 횟수 초과면 정답 여부와 상관없이 종료한다(원본은 이때 '실패'를 출력).
- LLM이 정수 외 텍스트를 섞으면 `int(r.text)`에서 오류가 날 수 있다(내 메모).

## LangGraph 실습 문제 3: 글 작성 → 검토 → 재작성
LangGraph 실습 3은 주제로 짧은 글을 쓰고, 검토 결과가 미흡하면 피드백을 반영해 다시 쓰는 그래프다.
- 흐름: `START → write → review → (통과) END / (미흡) write로 돌아감`
- 테스트 입력: `writing_graph.stream({"topic": "AI가 교육에 미치는 영향"})`
- 검토는 통과 여부와 피드백 두 값을 함께 만들어야 하므로 structured output을 쓴다.

## LangGraph 실습 3 풀이: 검토 결과 structured output
LangGraph 글 검토 풀이는 Pydantic 모델 `ReviewResult`로 `result`(pass/fail)와 `feedback`을 동시에 받는다.
```python
from typing import Literal
from pydantic import BaseModel

class WriteState(TypedDict):
    topic: str
    sentense: str      # 원본 철자 그대로(sentence의 오타)
    feedback: str
    result: Literal["pass", "fail"]
    attempt: int

class ReviewResult(BaseModel):
    result: Literal["pass", "fail"]
    feedback: str

llm_with_review_result = llm.with_structured_output(ReviewResult)

def review(state: WriteState):
    r = llm_with_review_result.invoke(
        f"다음 <text>는 <topic>을 주제로 한 글이야. 검토해줘.\n"
        f"- result에는 pass 또는 fail, feedback에는 이유를 담아줘.\n"
        f"<topic>{state['topic']}</topic>\n<text>{state['sentense']}</text>")
    return {"result": r.result, "feedback": r.feedback}
```
(프롬프트를 줄였다. 처음 풀이에는 `attempt`가 없고 이후 버전에서 추가된다.)

## LangGraph 실습 3 풀이: 피드백 반영 작성과 재시도 제한
LangGraph 글 작성 노드는 이전 초안과 피드백을 프롬프트에 넣어 다시 쓴다. 처음엔 값이 없으므로 `state.get(키, 기본값)`으로 꺼낸다. 루프를 확인하려고 첫 시도는 일부러 짧은 글을 반환해 fail이 나게 만든다.
```python
def write(state: WriteState):
    topic = state["topic"]
    attempt = state.get("attempt", 0) + 1
    if attempt == 1:   # 일부러 부실한 첫 글
        return {"sentense": f"{topic}은 아주 좋은 것이야!", "attempt": attempt}
    r = llm.invoke(
        f"주제 : {topic}\nfeedback : {state.get('feedback', '')}\n"
        f"draft : {state.get('sentense', '')}\n"
        "draft는 이전 글이야. feedback을 바탕으로 간단한 글을 작성해줘. 작성된 글만 응답해줘.")
    return {"sentense": r.text, "attempt": attempt}

def route_by_result(state: WriteState):
    if state["attempt"] >= 3:      # 3번 시도하면 강제 종료
        return "pass"
    return "pass" if state["result"] == "pass" else "fail"
```
그래프: `START → write → review`, `review`에서 `{"pass": END, "fail": "write"}`로 연결.
- 실행 결과: 1차 글은 "너무 짧다"는 피드백으로 fail, 2차 글은 피드백을 반영해 길어진다.

## LangGraph 그래프를 클래스로 감싸 LLM 교체하기
LangGraph 그래프를 클래스로 만들면 생성자로 LLM을 주입받아 서비스와 테스트에서 모델만 바꿀 수 있다. 노드는 메서드가 되고 `build()`가 컴파일한다.
```python
class WriteGraph:
    def __init__(self, llm, llm_with_review_result):
        self.llm = llm
        self.llm_with_review_result = llm_with_review_result

    def write(self, state: WriteState): ...           # self.llm 사용
    def review(self, state: WriteState): ...          # self.llm_with_review_result 사용
    def route_by_result(self, state: WriteState): ...

    def build(self):
        b = StateGraph(WriteState)
        b.add_node("write", self.write)
        b.add_node("review", self.review)
        b.add_edge(START, "write")
        b.add_edge("write", "review")
        b.add_conditional_edges("review", self.route_by_result,
                                {"pass": END, "fail": "write"})
        return b.compile()

graph = WriteGraph(llm, llm_with_review_result).build()   # 실제 서비스
```
(메서드 본문은 `...`로 줄임. 클래스 버전 write에는 일부러 짧게 쓰는 첫 시도 분기가 없다.)

## LangGraph 테스트: FakeListChatModel로 LLM 대체
LangGraph 그래프를 테스트할 때는 `FakeListChatModel`에 미리 정한 응답 목록을 주면, 호출할 때마다 순서대로 그 응답을 돌려준다. 클래스 버전 그래프에 진짜 LLM 대신 넣으면 루프 동작을 확정적으로 재현할 수 있다.
```python
from langchain_core.language_models.fake_chat_models import FakeListChatModel

fake_llm = FakeListChatModel(responses=[
    "ai agent와 랭그래프은 아주 좋은 것이야!",   # review에서 fail 나올 짧은 글
    "AI Agent와 LangGraph의 개념, 역할, 활용법을 정리한 긴 글...",  # pass 나올 글
])

graph = WriteGraph(fake_llm, llm_with_review_result).build()
for event in graph.stream({"topic": "ai agent와 랭그래프"}):
    for node_name, value in event.items():
        print(f"[{node_name}] {value}")
```
- 출력: 1차 write는 짧은 글 → review가 fail과 피드백 → 2차 write는 두 번째 긴 응답.
- 검토용 모델은 그대로 진짜 LLM을 쓴다.

(두 번째 응답의 긴 본문은 생략했다.)

## LangGraph 기초 복습 Q&A
- Q. LangGraph의 세 가지 핵심 개념은?
  A. 공유 데이터인 State, 처리 함수인 Node, 노드 연결인 Edge.
- Q. LangGraph에서 `add_edge`와 `add_conditional_edges`의 차이는?
  A. `add_edge`는 다음 노드가 고정이고, `add_conditional_edges`는 라우팅 함수가 반환한 문자열을 매핑 dict로 바꿔 다음 노드를 정한다.
- Q. LangGraph State 필드에 Reducer가 없으면 노드 반환값은 어떻게 처리되나?
  A. 기존 값을 덮어쓴다. 누적하려면 `Annotated[list, add_messages]`나 `Annotated[list, operator.add]`를 쓴다.
- Q. LangGraph `graph.stream()`의 기본 모드와 `stream_mode="values"`의 차이는?
  A. 기본은 노드별 State 업데이트만, `values`는 단계마다 전체 State를 준다.
- Q. LangGraph 루프에서 무한 반복을 막는 방법은?
  A. State에 시도 횟수(`attempt`)를 두고 라우팅 함수에서 최대 횟수에 도달하면 `END`로 보내는 경로를 반환한다.
