---
part: langchain
lesson: Plan-and-Execute
order: 20
source_type: ipynb
tags: [plan-and-execute, planner, executor, replanner, langgraph, google-search, union, recursion-limit]
source: C:\Users\tnwls\aim-ai-agent\langchain_\20-plan-and-execute_answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Plan-and-Execute

## Plan-and-Execute 요약
Plan-and-Execute 레슨은 복잡한 작업을 먼저 단계별로 계획하고, 한 단계씩 실행하며, 중간 결과에 따라 남은 계획을 고치는 패턴을 LangGraph로 만든다. 강릉 당일치기 여행 계획 예제, 생성형 AI 트렌드 조사 실습 문제, Replanner 없는 변형 실습을 다룬다.

## Plan-and-Execute란
Plan-and-Execute는 전체 계획을 먼저 세운 뒤 각 단계를 실행하고, 실행 결과를 검토해 필요하면 남은 계획을 수정하는 패턴이다.
```text
입력 → Planner → Executor → Replanner → Executor → ... → 최종 응답
```
- Planner: 실행할 단계 목록을 만든다.
- Executor: 현재 계획의 첫 단계를 수행한다.
- Replanner: 결과가 충분한지 판단해 종료(최종 응답)하거나 남은 계획을 교체한다.

## Plan-and-Execute와 ReAct 비교
Plan-and-Execute와 ReAct는 계획 범위가 다르다.
- ReAct: 매 순간 다음 행동을 정한다. 단순하고 빠르지만 전체 흐름을 놓칠 수 있다. 단일 조회나 간단한 질의에 맞다.
- Plan-and-Execute: 전체 계획을 먼저 세운다. 복잡한 목표와 제약 조건 처리에 유리하지만 계획·재계획 비용이 든다. 조사, 비교, 일정 설계, 보고서 작성에 맞다.

## Plan-and-Execute State 설계
Plan-and-Execute State는 현재 계획뿐 아니라 완료한 단계와 최종 응답도 추적한다.
- `input` (str): 사용자의 원래 요청
- `plan` (list[str]): 앞으로 실행할 단계. Replanner가 남은 계획 전체를 바꿀 수 있도록 reducer 없이 덮어쓴다.
- `past_steps` (list[tuple[str, str]]): `(실행한 단계, 실행 결과)` 목록. 이력을 보존해야 하므로 `operator.add`로 누적한다.
- `response` (str): 최종 응답
```python
class PlanExecuteState(TypedDict):
    input: str
    plan: list[str]
    past_steps: Annotated[list[tuple[str, str]], operator.add]
    response: str
```
실습 모델은 `ChatGoogleGenerativeAI(model="gemini-3.6-flash")`, API 키는 `.env` + `load_dotenv()`로 읽는다.

## Plan-and-Execute 출력 모델과 Union
Plan-and-Execute의 Planner·Replanner 출력은 Pydantic 모델로 정의한다. Replanner는 한 번 호출에 "남은 계획" 또는 "최종 응답" 중 하나만 내면 되므로 `decision: Union[Plan, Response]`로 둘 중 하나를 고르게 한다. `Union[A, B]`는 A 또는 B 타입 값을 허용한다는 뜻이다. 반면 그래프 State에서는 `plan`과 `response`의 역할이 달라 필드를 따로 둔다.
```python
class Plan(BaseModel):
    """앞으로 수행할 계획"""
    steps: list[str] = Field(description="순서대로 수행할 단계")

class Response(BaseModel):
    """사용자에게 전달할 최종 응답"""
    response: str = Field(description="검색 결과를 반영한 최종 여행 계획")

class ReplanDecision(BaseModel):
    """Replanner가 선택한 다음 결정"""
    decision: Union[Plan, Response]
```

## Plan-and-Execute 실습 1단계: Planner
Plan-and-Execute의 Planner는 여행 요청을 Google Search로 조사 가능한 구체적 단계로 나눈다. 한 단계에는 조사 목표 하나만 넣는다.
```python
planner_prompt = ChatPromptTemplate.from_messages([
    ("system", """당신은 여행 요청을 실행 계획으로 만드는 Planner입니다.
각 단계는 Google Search로 조사할 수 있는 구체적인 작업이어야 합니다.
교통, 숙박, 관광지 운영 정보, 식당, 예산 검증처럼 서로 다른 조사 목표를 나누세요.
실행하지 않은 결과를 미리 판단하지 마세요.
계획은 최대 5단계로 작성하세요."""),
    ("human", "{input}"),
])
planner = planner_prompt | llm.with_structured_output(Plan)

def plan_step(state: PlanExecuteState):
    result = planner.invoke({"input": state["input"]})
    return {"plan": result.steps}
```

## Plan-and-Execute 실습 2단계: Google Search Executor
Plan-and-Execute의 Executor는 계획의 첫 단계만 실행한다. Gemini에 Google Search 도구를 붙여 최신 정보를 찾고 출처 URL과 함께 정리한다. 이전 결과(`past_steps`)를 문맥으로 함께 넘긴다.
```python
search_llm = llm.bind_tools([{"google_search": {}}])

def execute_step(state: PlanExecuteState):
    current_step = state["plan"][0]
    past_context = ""
    if state.get("past_steps"):
        past_context = "\n\n지금까지 확인한 결과:\n" + "\n".join(
            f"- {step}: {result}" for step, result in state["past_steps"])
    task = f"""다음 여행 조사 단계를 수행하세요.
현재 단계:
{current_step}
요구사항:
- Google Search로 최신 정보를 확인하세요.
- 가격, 운영시간, 이동시간을 구체적으로 정리하세요.
- 확인한 정보의 출처 URL을 포함하세요.
- 현재 단계에 필요한 내용만 간결하게 작성하세요.
{past_context}"""
    result = search_llm.invoke(task)
    return {"past_steps": [(current_step, result.text)]}
```
- `bind_tools([{"google_search": {}}])`: Gemini 내장 Google Search grounding을 켠다.

## Plan-and-Execute Replanner 판단 기준
Plan-and-Execute의 Replanner는 매 실행 후 원래 요청과 `past_steps`를 비교한다.
- 필요한 정보가 부족하면 추가 조사 단계를 계획에 넣는다.
- 검색 결과가 조건에 안 맞으면(휴무, 매진, 예산 초과 등) 대안 조사로 계획을 고친다.
- 모든 조건을 판단할 수 있으면 최종 응답을 만든다.

완료한 단계를 새 계획에서 빼지 않으면 같은 검색이 반복될 수 있다. 그래서 프롬프트에서 반복을 금지하고 `recursion_limit`으로 무한 반복을 막는다. `recursion_limit`은 그래프 한 번 실행에서 허용하는 최대 노드 실행 횟수(같은 노드 반복도 매번 셈)이고, 넘으면 `GraphRecursionError`가 난다.

## Plan-and-Execute 실습 3단계: Replanner 프롬프트
Plan-and-Execute의 Replanner 프롬프트는 목표, 현재 계획, 완료한 단계를 보고 남은 Plan 또는 최종 Response 중 하나를 고르게 한다. 출력은 `ReplanDecision` 구조화 출력이다.
```python
replanner_prompt = ChatPromptTemplate.from_messages([
    ("system", """당신은 여행 계획의 진행 상황을 검토하는 Replanner입니다.
- 정보가 부족하면 완료한 단계를 반복하지 말고 남은 Plan을 반환합니다.
- 조건을 충족하는 여행 계획을 쓸 수 있으면 Response를 반환합니다.
- 제약 조건을 못 맞춘 항목이 있으면 대안 조사 단계를 추가합니다.
- 최종 응답에는 일정, 예상 비용, 이동 방법, 주의사항, 출처를 포함합니다."""),
    ("human", "목표:\n{input}\n\n현재 계획:\n{plan}\n\n완료한 단계:\n{past_steps}"),
])
replanner = replanner_prompt | llm.with_structured_output(ReplanDecision)
```
(시스템 프롬프트를 조금 줄임.)

## Plan-and-Execute 실습 3-2단계: replan_step과 종료 판단
Plan-and-Execute의 replan_step은 계획과 완료 단계를 문자열로 정리해 Replanner에 넘기고, 결과가 `Response`면 `response`를, `Plan`이면 새 `plan`을 반환한다. `should_continue`는 `response`가 있으면 종료한다.
```python
def replan_step(state: PlanExecuteState):
    result = replanner.invoke({
        "input": state["input"],
        "plan": "\n".join(f"- {s}" for s in state["plan"]),
        "past_steps": "\n".join(f"- {s}: {r}" for s, r in state["past_steps"]),
    })
    if isinstance(result.decision, Response):
        return {"response": result.decision.response}
    return {"plan": result.decision.steps}

def should_continue(state: PlanExecuteState):
    return "end" if state.get("response") else "continue"
```
(원본 `should_continue`의 if/else 주석 버전은 생략.)

## Plan-and-Execute 실습 4단계: 그래프 구성
Plan-and-Execute 그래프는 planner → executor → replanner 순서이고, replanner 뒤 조건부 엣지로 최종 응답이 생길 때까지 executor로 돌아간다.
```python
gb = StateGraph(PlanExecuteState)
gb.add_node("planner", plan_step)
gb.add_node("executor", execute_step)
gb.add_node("replanner", replan_step)
gb.add_edge(START, "planner")
gb.add_edge("planner", "executor")
gb.add_edge("executor", "replanner")
gb.add_conditional_edges("replanner", should_continue,
                         {"continue": "executor", "end": END})
graph = gb.compile()
```
(변수명 `graph_builder`를 `gb`로 줄임.)

## Plan-and-Execute 실습 5단계: 여행 계획 실행
Plan-and-Execute 그래프를 여러 조건(대중교통, 관광지 2곳 이상, 현지 식당, 1인 15만 원 이하, 운영시간·비용)이 있는 강릉 당일치기 요청으로 실행한다. `stream_mode=["updates", "values"]`로 두 모드를 함께 받으면 `(mode, event)` 튜플이 나온다.
```python
inputs = {"input": "다음 주 토요일에 서울에서 출발하는 강릉 당일치기 여행 계획을 만들어줘. "
                   "대중교통을 중심으로 이동하고, 관광지 2곳 이상과 현지 식당을 포함해줘. "
                   "1인 총예산은 15만 원 이하야. 운영시간과 예상 비용도 알려줘."}
state_history = []
for mode, event in graph.stream(inputs, config={"recursion_limit": 20},
                                stream_mode=["updates", "values"]):
    if mode == "values":
        state_history.append(event)   # 매 단계 전체 State 스냅샷
        continue
    for node_name, value in event.items():
        print(node_name, value)
```
(노드별 출력 분기를 한 줄로 줄임.)
- 초기 계획은 4단계(KTX 시간표·요금, 관광지 운영시간·입장료, 맛집 가격·운영시간, 예산 검증·일정표)였고, Executor가 KTX 소요 시간·첫차/막차 등을 출처와 함께 정리했다.
- `state_history`를 출력하면 State 0(input만) → State 1(plan 추가) → 이후 past_steps가 늘어나는 흐름을 볼 수 있다.

## 생성형 AI 트렌드 조사 실습 문제
생성형 AI 트렌드 조사 실습 문제는 Plan-and-Execute 그래프를 처음부터 만들어 다음 요청을 처리하는 것이다.
- 요청: 2026년 생성형 AI 트렌드를 조사하고, 주요 트렌드 5개를 골라 근거와 함께 요약 보고서를 작성. 각 트렌드의 특징과 예상 영향, 출처를 포함.

풀이 구조(노트북의 풀이):
- State: `input`, `plans`(reducer 없음, Planner·Replanner가 덮어씀), `results`(`operator.add`로 누적), `response`.
- 출력 모델: `Plan(plans: list[str])`, `Response(response: str)`, `ReplanDecision(decision: Union[Plan, Response])`.
- 그래프: planning → execute → replanning → (continue → execute | end → END). 구조는 여행 예제와 같다.

## 트렌드 조사 실습 풀이 1단계: State와 planning
생성형 AI 트렌드 조사 풀이의 planning 노드는 요청에서 조사 목표·제약·결과물 요구사항을 파악하고, 최종 보고서 작성은 빼고 조사 단계만 최대 5개 만든다.
```python
class State(TypedDict):
    input: str
    plans: list[str]
    results: Annotated[list, operator.add]
    response: str

class Plan(BaseModel):
    plans: list[str]
class Response(BaseModel):
    response: str
class ReplanDecision(BaseModel):
    decision: Union[Plan, Response]

def planning(state: State):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 조사 계획을 수립하는 Planner입니다.
요청에서 조사 목표, 제약 조건, 결과물 요구사항을 파악하세요.
각 단계는 하나의 명확한 조사 목표를 가지며 Google Search로 수행할 수 있어야 합니다.
앞 단계 정보가 필요하면 의존 관계가 순서에 드러나야 합니다.
조사하지 않은 내용을 사실처럼 가정하지 마세요.
최종 보고서 작성은 계획에 넣지 말고 조사 단계만 최대 5개로 반환하세요."""),
        ("human", "조사 요청:\n{input}"),
    ])
    response = (prompt | llm.with_structured_output(Plan)).invoke({"input": state["input"]})
    return {"plans": response.plans}
```
(프롬프트를 조금 줄임.)

## 트렌드 조사 실습 풀이 2단계: execute (Researcher)
생성형 AI 트렌드 조사 풀이의 execute 노드는 프롬프트 템플릿에 Google Search가 붙은 LLM을 연결해, 현재 단계 하나만 조사하고 이전 결과는 문맥으로만 쓴다.
```python
def execute(state: State):
    current_plan = state["plans"][0]
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 계획에서 지정된 조사 단계 하나를 수행하는 Researcher입니다.
원래 요청과 이전 결과는 문맥으로만 쓰고 현재 단계 목표에 집중하세요.
신뢰할 수 있는 최신 출처를 우선하고, 사실과 해석을 구분하며, 자료 충돌은 밝히세요.
자료 제목, 발행 주체, 발행 시점, URL을 제시하세요.
근거를 못 찾은 내용은 추측하지 말고 확인하지 못했다고 쓰세요."""),
        ("human", "조사 요청:\n{input}\n\n현재 단계:\n{current_step}\n\n이전 조사 결과:\n{findings}"),
    ])
    research_executor = prompt | llm.bind_tools([{"google_search": {}}])
    response = research_executor.invoke({
        "input": state["input"],
        "current_step": current_plan,
        "findings": "\n".join(f"{p} - {t}" for p, t in state["results"]),
    })
    return {"results": [[current_plan, response.text]]}
```
(프롬프트·주석을 줄임.)

## 트렌드 조사 실습 풀이 3단계: replanning 노드
생성형 AI 트렌드 조사 풀이의 replanning 노드는 Router처럼 "계속 조사할지, 보고서로 끝낼지"를 정한다. 근거가 약하거나 출처가 충돌하면 새 계획을, 충분하면 보고서를 낸다. 계획이 남아 있어도 이미 충분하면 조사를 멈추라고 지시한다.
```python
def replanning(state: State):
    # system: 근거 부족·충돌 → 남은 조사 단계만 계획, 충분 → 보고서
    #         (조사 결과 정보만 사용, 불확실성·한계 명시, 출처 표기)
    chain = replanner_prompt | llm.with_structured_output(ReplanDecision)
    response = chain.invoke({
        "input": state["input"],
        "plan": "\n".join(state["plans"]),
        "findings": "\n".join(f"{p} - {t}" for p, t in state["results"]),
    })
    if isinstance(response.decision, Response):
        return {"response": response.decision.response}
    return {"plans": response.decision.plans}

def should_continue(state: State):
    return "end" if state.get("response") else "continue"
```
(원본은 `replanner_prompt`를 함수 안에서 정의함. 프롬프트는 주석으로 요약.)
- 원본 Replanner 프롬프트는 `ResearchPlan`/`ResearchReport`를 반환하라고 쓰지만 실제 모델 이름은 `Plan`/`Response`다.

## 트렌드 조사 실습 풀이 4단계: 그래프 구성과 결과
생성형 AI 트렌드 조사 풀이 그래프는 planning → execute → replanning → (continue → execute | end → END) 구조로, 여행 예제와 같다.
```python
builder = StateGraph(State)
builder.add_node("planning", planning)
builder.add_node("execute", execute)
builder.add_node("replanning", replanning)
builder.add_edge(START, "planning")
builder.add_edge("planning", "execute")
builder.add_edge("execute", "replanning")
builder.add_conditional_edges("replanning", should_continue, {"continue": "execute", "end": END})
graph = builder.compile()
response = graph.invoke({"input": research_request})
print(response["response"])
```
- 결과: Agentic AI·멀티에이전트, 도메인 특화 언어 모델(DSLM) 등 5대 트렌드와 시장 전망을 Gartner·IDC 출처와 함께 정리한 보고서가 생성됐다.

## Replanner 없는 Plan-and-Execute 추가 실습 문제
Replanner 없는 Plan-and-Execute 추가 실습 문제는 Replanner가 필수가 아님을 확인하는 과제다. 초기 계획을 고칠 필요가 없다면 Planner 계획을 그대로 순서대로 모두 실행하면 된다. 여행 계획 그래프에서 Replanner를 빼고 이렇게 바꾸는 것이 과제다.
- 힌트: Executor가 현재 단계를 실행한 뒤 `{"plan": state["plan"][1:]}`을 반환하면 완료 단계가 계획에서 빠진다.
- 힌트: `plan`이 비었는지로 Executor 반복과 최종 응답 생성 노드 사이를 분기한다.

## Replanner 없는 실습 풀이: 실행 노드와 분기
Replanner 없는 Plan-and-Execute 풀이는 State(`PlanExecuteState`)와 `plan_step`을 재사용한다. Executor는 실행 후 계획에서 첫 단계를 지우고, 계획이 남아 있으면 다시 실행, 비면 `finalize`로 간다.
```python
def execute_no_replan(state: PlanExecuteState):
    current_step = state["plan"][0]
    # task 프롬프트 조립·검색 호출은 execute_step과 동일
    result = search_llm.invoke(task)
    return {"past_steps": [(current_step, result.text)],
            "plan": state["plan"][1:]}   # 0번째 단계 제거

def should_continue(state: PlanExecuteState):
    return "continue" if state["plan"] else "finalize"
```
(task 조립 부분을 주석으로 줄임.)

## Replanner 없는 실습 풀이: finalize 노드
Replanner 없는 Plan-and-Execute 풀이의 finalize 노드는 모든 단계가 끝난 뒤 `past_steps` 전체를 모아 최종 응답(일정, 비용, 이동 방법, 주의사항, 출처)을 만든다.
```python
def finalize(state: PlanExecuteState):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "다음 조사결과를 바탕으로 최종 응답을 만들어라.\n"
                   "- 최종 응답에는 일정, 예상 비용, 이동 방법, 주의사항, 출처를 포함합니다."),
        ("human", "{input} 조사 결과 : {results}"),
    ])
    response = (prompt | llm).invoke({
        "input": state["input"],
        "results": "\n".join(f"- {s}: {r}" for s, r in state["past_steps"]),
    })
    return {"response": response.text}
```
(원본 프롬프트의 "배탕"은 "바탕"의 오타.)

## Replanner 없는 실습 풀이: 그래프와 실행
Replanner 없는 Plan-and-Execute 그래프는 plan → execute → (execute 반복 | finalize) → END다.
```python
builder = StateGraph(PlanExecuteState)
builder.add_node("plan", plan_step)
builder.add_node("execute", execute_no_replan)
builder.add_node("finalize", finalize)
builder.add_edge(START, "plan")
builder.add_edge("plan", "execute")
builder.add_conditional_edges("execute", should_continue,
                              {"continue": "execute", "finalize": "finalize"})
builder.add_edge("finalize", END)
graph = builder.compile()
```
- 같은 강릉 여행 요청을 `recursion_limit=20`, `stream_mode=["updates", "values"]`로 실행했다. 초기 계획은 5단계(KTX, 관광지, 식당·카페, 시내버스·택시비, 예산 검증·일정)였고 각 단계가 순서대로 실행됐다.
- 루프 안의 `print('--node--')`가 values/updates 이벤트마다 찍혀 두 번씩 보인다.
- (내 메모) 계획 단계 수 + 2(plan, finalize)만큼 노드가 실행되므로 5단계면 7회라 `recursion_limit=20` 안에 들어간다.

## Plan-and-Execute 복습 Q&A
- Q. Plan-and-Execute에서 Planner, Executor, Replanner의 역할은?
  A. Planner는 단계 목록을 만들고, Executor는 계획의 첫 단계를 실행하며, Replanner는 결과를 보고 남은 계획을 바꾸거나 최종 응답을 만든다.
- Q. Plan-and-Execute State에서 `past_steps`엔 reducer를 쓰고 `plan`엔 안 쓰는 이유는?
  A. `past_steps`는 실행 이력을 누적해야 하고, `plan`은 Replanner가 남은 계획 전체를 교체(덮어쓰기)해야 하기 때문이다.
- Q. Replanner 출력 모델에서 `decision: Union[Plan, Response]`를 쓰는 이유는?
  A. 한 번 호출에 남은 계획과 최종 응답 중 하나만 필요하므로 둘 중 하나를 고르게 하려는 것이다. `isinstance`로 어느 쪽인지 확인한다.
- Q. LangGraph `recursion_limit`은 무엇이고 넘으면 어떻게 되나?
  A. 한 번 실행에서 허용하는 최대 노드 실행 횟수(반복 포함)이고, 넘으면 `GraphRecursionError`가 난다.
- Q. Replanner 없이 Plan-and-Execute를 구현하려면?
  A. Executor가 `{"plan": state["plan"][1:]}`로 완료 단계를 지우고, `plan`이 비면 finalize 노드로 분기해 최종 응답을 만든다.
