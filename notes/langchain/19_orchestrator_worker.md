---
part: langchain
lesson: Orchestrator-worker
order: 19
source_type: ipynb
tags: [orchestrator-worker, send-api, langgraph, dynamic-fan-out, reducer, rate-limit, max-concurrency]
source: C:\Users\tnwls\aim-ai-agent\langchain_\19-orchestrator-worker.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Orchestrator-worker

## Orchestrator-worker 요약
Orchestrator-worker 레슨은 Orchestrator가 요청을 분석해 작업을 나누고, LangGraph `Send` API로 작업 수만큼 Worker를 동적으로 병렬 실행한 뒤 결과를 종합하는 패턴을 다룬다. `max_concurrency`로 동시 실행 수를 제한하는 Rate Limit 대응과 맞춤형 학습 자료 생성 실습도 한다.
```text
START → Orchestrator ─┬→ Worker
                      ├→ Worker ─→ 결과 종합 → END
                      └→ Worker
```

## Orchestrator-worker와 Send API란
Orchestrator-worker 패턴은 고정 Fan-out과 달리 실행 시점에 작업 종류와 개수가 정해진다. Orchestrator가 사용자 요청을 분석해 작업을 계획하고, `Send` API로 각 작업을 Worker에 넘긴다.
- `Send(노드이름, state)`: 지정한 Worker 노드를 새 입력 State로 실행한다.
- 라우팅 함수가 `Send` 리스트를 반환하면 리스트 길이만큼 동적 Fan-out이 일어난다. 요청마다 Worker 수가 달라도 된다.

실행 흐름:
- `create_plan`(Orchestrator)이 작업 목록을 만든다.
- `assign_workers`가 작업마다 `Send`를 하나씩 만든다.
- 여러 `analyze_task`(Worker)가 각자 독립 입력으로 실행된다.
- Worker 결과가 `results`에 병합되고, 모두 끝나면 `make_report`가 보고서로 종합한다.

실습 준비: `from langgraph.types import Send`, 모델은 `ChatGoogleGenerativeAI(model="gemini-3.6-flash")`, API 키는 `.env`를 `load_dotenv(override=True)`로 읽는다.

## Orchestrator-worker 전체 State와 Worker State
Orchestrator-worker에서 `ReportState`는 그래프 전체가 공유하는 상태(원본 요청, 작업 목록, Worker 결과, 최종 보고서)이고, `WorkerState`는 Worker 하나가 자기 작업을 처리하는 데 필요한 값만 가진다.
- Worker들은 같은 `WorkerState` 스키마를 쓰지만 `Send`마다 전달되는 값은 독립적이다. Worker가 공유 State에서 자기 작업을 다시 찾을 필요 없이 받은 State를 바로 쓴다.
- `task_id`는 Worker를 구분하는 객체가 아니라, 합쳐진 결과가 어느 작업에서 왔는지 식별하고 원래 계획 순서로 정렬하기 위한 값이다.
- `results: Annotated[list, operator.add]`의 `operator.add`는 reducer다. 여러 Worker가 각각 반환한 리스트를 덮어쓰지 않고 이어 붙인다. reducer가 없으면 같은 키를 동시에 갱신할 때 충돌한다.

## Orchestrator-worker 실습 1단계: 계획 스키마와 State 정의
Orchestrator-worker 실습은 요청에 대한 분석 보고서 작성이다. Orchestrator는 Structured Output으로 작업 목록(`AnalysisPlan`)을 받는다.
```python
class AnalysisTask(BaseModel):
    title: str = Field(description="분석 항목 제목")
    description: str = Field(description="분석할 내용")

class AnalysisPlan(BaseModel):
    tasks: list[AnalysisTask] = Field(description="보고서 작성에 필요한 분석 작업")

class ReportState(TypedDict):
    request: str
    tasks: list[AnalysisTask]
    results: Annotated[list, operator.add]
    final_report: str

class WorkerState(TypedDict):
    request: str
    task_id: int
    title: str
    description: str
```

## Orchestrator-worker 실습 2단계: Orchestrator와 Send 라우팅 함수
Orchestrator-worker의 `create_plan`은 작업을 3~5개로 나누고, 이 목록 길이가 Worker 수가 된다. `assign_workers`는 노드가 아니라 라우팅 함수이며, 각 작업을 `Send("analyze_task", worker_state)`로 바꾼다. 두 번째 인자 dict는 그 Worker만 받는 입력이고 `WorkerState` 구조와 맞아야 한다.
```python
def create_plan(state: ReportState):
    planner = llm.with_structured_output(AnalysisPlan)
    plan = planner.invoke(
        f"다음 요청에 대한 분석 보고서를 작성하려고 한다. "
        f"필요한 분석 작업을 3~5개로 나눠줘.\n\n요청: {state['request']}")
    return {"tasks": plan.tasks}

def assign_workers(state: ReportState):
    return [
        Send("analyze_task", {
            "request": state["request"],
            "task_id": task_id,
            "title": task.title,
            "description": task.description,
        })
        for task_id, task in enumerate(state["tasks"])
    ]
```

## Orchestrator-worker 실습 3단계: Worker와 종합 노드
Orchestrator-worker의 `analyze_task`는 모든 작업에 공통인 Worker 함수다. 입력만 다르고, 결과 하나를 리스트에 담아 반환한다. `make_report`는 병렬 완료 순서에 흔들리지 않도록 `task_id`로 다시 정렬한 뒤 보고서를 만든다.
```python
def analyze_task(state: WorkerState):
    result = llm.invoke(
        f"전체 요청을 고려하여 담당 항목을 구체적으로 분석해줘.\n\n"
        f"전체 요청: {state['request']}\n담당 항목: {state['title']}\n"
        f"분석 내용: {state['description']}")
    return {"results": [{"task_id": state["task_id"], "title": state["title"],
                         "content": result.text}]}

def make_report(state: ReportState):
    sorted_results = sorted(state["results"], key=lambda item: item["task_id"])
    all_results = "\n\n".join(f"### {i['title']}\n{i['content']}" for i in sorted_results)
    result = llm.invoke(
        f"다음 요청과 분석 결과를 바탕으로 하나의 보고서를 작성해줘.\n\n"
        f"요청: {state['request']}\n\n{all_results}")
    return {"final_report": result.text}
```
- Worker 함수 안의 `### {title}`은 LLM에게 넘기는 문자열 속 마크다운이다.

## Orchestrator-worker 실습 4단계: 동적 Fan-out 그래프 구성
Orchestrator-worker 그래프는 `create_plan` 뒤에 `add_conditional_edges`로 `assign_workers`를 붙여 동적 Fan-out을 만들고, `analyze_task → make_report` 엣지로 Fan-in을 만든다.
```python
gb = StateGraph(ReportState)
gb.add_node("create_plan", create_plan)
gb.add_node("analyze_task", analyze_task)
gb.add_node("make_report", make_report)
gb.add_edge(START, "create_plan")
gb.add_conditional_edges("create_plan", assign_workers, ["analyze_task"])
gb.add_edge("analyze_task", "make_report")
gb.add_edge("make_report", END)
send_graph = gb.compile()
```
- `["analyze_task"]`: 라우팅 함수가 갈 수 있는 노드 목록이다. `{"analyze_task": "analyze_task"}`와 같은 뜻이다.
- Fan-in: LangGraph는 같은 단계에서 생긴 Worker들이 모두 끝날 때까지 기다린 뒤, reducer로 합친 `results`를 `make_report`에 한 번에 넘긴다. Worker마다 보고서를 따로 만들지 않는다.

## Orchestrator-worker 실행: stream으로 진행 확인
Orchestrator-worker 그래프를 `stream_mode="updates"`로 실행하면 `{노드 이름: 갱신 내용}`을 받아 계획 → Worker 완료 → 최종 보고서 순으로 볼 수 있다.
```python
request = "소규모 카페가 키오스크를 도입할 때 기대 효과와 위험을 분석해줘."
for chunk in send_graph.stream({"request": request}, stream_mode="updates"):
    for node_name, update in chunk.items():
        if node_name == "create_plan":
            print("[Orchestrator]", [t.title for t in update["tasks"]])
        elif node_name == "analyze_task":
            print("[Worker 완료]", update["results"][0]["title"])
        elif node_name == "make_report":
            print("[최종 보고서]", update["final_report"][:500])
```
(출력 형식을 줄여 적음.)
- 결과: Orchestrator가 작업 4개(기대 효과, 주요 위험 요소, 소규모 카페 특성·고객층, 리스크 완화·도입 전략)를 만들었고, Worker 완료 순서는 계획 순서와 달랐다(3번째 작업이 먼저 끝남).

## Rate Limit이란
Rate Limit은 LLM API 제공자가 서비스 안정과 과도한 사용 방지를 위해 일정 시간 동안 요청량을 제한하는 정책이다. 한도는 제공자, 모델, 사용 등급마다 다르다.
- RPM (Requests Per Minute): 분당 요청 수
- TPM (Tokens Per Minute): 분당 처리 토큰 수
- RPD (Requests Per Day): 일일 요청 수
- 동시 요청 수: 같은 시점에 처리할 수 있는 요청 수

한도를 넘으면 보통 `429 Too Many Requests` 같은 오류가 난다. Orchestrator가 작업 5개를 만들면 Worker LLM 요청 5개가 거의 동시에 시작되므로 순차 실행보다 Rate Limit에 걸리기 쉽다.

## LangGraph max_concurrency로 동시 실행 제한
LangGraph의 `max_concurrency` 설정은 그래프 한 번 실행에서 동시에 도는 태스크 수를 제한한다. 전체 Worker 수를 줄이는 게 아니라, 실행 중인 Worker가 끝나면 대기하던 다음 Worker가 시작된다. 순간적인 요청 몰림은 완화하지만 RPM·TPM을 계산하지는 않으므로, 실제 Rate Limit 대응엔 재시도, exponential backoff, 요청 속도 제한을 함께 쓴다. 특정 API 호출이나 코드 블록만 제한하려면 `asyncio.Semaphore`를 쓸 수 있다.
```python
result = graph.invoke(inputs, config={"max_concurrency": 3})
```

## LangGraph max_concurrency 실습: 8개 주제를 동시 3개로 분석
LangGraph `max_concurrency` 실습은 주제 8개를 `Send`로 보내되 동시에 최대 3개만 실행한다. START에서 바로 Send를 보낼 수도 있다.
```python
class RateLimitState(TypedDict):
    topics: list[str]
    results: Annotated[list, operator.add]

def dispatch_topics(state):
    return [Send("analyze_with_limit", {"topic": t}) for t in state["topics"]]

def analyze_with_limit(state):
    result = llm.invoke(f"'{state['topic']}'에 대해 한 문장으로 설명해줘.")
    return {"results": [f"[{state['topic']}] {result.text}"]}

gb = StateGraph(RateLimitState)
gb.add_node("analyze_with_limit", analyze_with_limit)
gb.add_conditional_edges(START, dispatch_topics, ["analyze_with_limit"])
gb.add_edge("analyze_with_limit", END)
rate_limit_graph = gb.compile()

topics = ["AI", "블록체인", "IoT", "클라우드", "5G", "메타버스", "드론", "AR/VR"]
result = rate_limit_graph.invoke({"topics": topics}, config={"max_concurrency": 3})
```
(print를 뺌.)
- 출력: 처음 3개(AI, 블록체인, IoT)가 시작되고 하나가 끝날 때마다 다음 주제가 시작돼, 동시 실행이 3개를 넘지 않았다.

## 맞춤형 학습 자료 생성 실습 문제
맞춤형 학습 자료 생성 실습 문제는 학습 요청을 받아 Orchestrator-worker 그래프로 학습 자료를 만드는 것이다. 사용자는 목차를 주지 않고, Orchestrator가 대상과 시간을 고려해 목차를 동적으로 만든다.
```text
학습 요청 → 목차 생성 ─┬→ 목차별 Worker ─┐
                       ├→ 목차별 Worker ─┼→ 학습 자료 완성
                       └→ 목차별 Worker ─┘
```
요구사항:
- Orchestrator가 목차를 3~5개 생성한다.
- 목차마다 Worker를 동적으로 실행해 설명과 간단한 예제를 쓴다.
- 결과를 모아 하나의 학습 자료로 완성하고 실행 과정을 출력한다.

구현 요소: 목차 항목·목차 Structured Output 모델, 전체 State, 목차 하나만 받는 Worker State, Orchestrator 함수, `Send` 라우팅 함수, Worker 함수, 순서대로 정리하는 종합 함수, `stream_mode="updates"` 실행 출력. 완료 순서는 보장되지 않으므로 순번을 함께 넘기고 종합 단계에서 정렬한다.

## 학습 자료 실습 풀이 1단계: 목차 모델과 State
맞춤형 학습 자료 실습 풀이(노트북에 작성된 내 풀이)는 전체를 course, 부분을 section으로 나눈다. 목차 항목은 제목과 학습 목표를 가진다.
```python
course_request = "파이썬을 처음 배우는 비전공자를 위한 2시간 분량의 학습 자료를 만들어줘."

class Section(BaseModel):
    title: str = Field(description="수업 자료 제목")
    objective: str = Field(description="학습 목표")

class CoursePlan(BaseModel):
    sections: list[Section] = Field(description="수업자료의 제목, 학습 목표를 담은 리스트")

llm_with_courseplan_output = llm.with_structured_output(CoursePlan)

class CourseState(TypedDict):      # 전체
    request: str
    sections: list                          # Structured Output 결과
    results: Annotated[list, operator.add]  # Worker들이 만든 자료 모음
    final_result: str                       # results를 한 문자열로 합친 것

class SectionState(TypedDict):     # 부분 (Worker 입력)
    request: str
    title: str
    objective: str
    order: int
```

## 학습 자료 실습 풀이 2단계: Orchestrator와 Send 분배
맞춤형 학습 자료 실습 풀이의 `course_plan`이 Orchestrator로 목차를 만들고, `assign_sections`가 목차마다 순번(`order`)을 붙여 `Send`로 Worker에 나눠 준다.
```python
def course_plan(state: CourseState):
    response = llm_with_courseplan_output.invoke(f"""
다음 <request>에 맞는 학습 목차를 만들어줘.
목차에는 수업자료의 제목과 학습 목표를 포함해줘.
<request>
{state['request']}
</request>
""")
    return {"sections": response.sections}

def assign_sections(state: CourseState):
    return [
        Send("write_section", {
            "request": state["request"],
            "title": section.title,
            "objective": section.objective,
            "order": index,
        })
        for index, section in enumerate(state["sections"])
    ]
```
(원본의 for 루프 버전 주석은 생략.)
- (내 메모) 요구사항의 "3~5개"가 프롬프트에 빠져 있다. 실행에선 4개가 나왔다.

## 학습 자료 실습 풀이 3단계: Worker와 종합 함수
학습 자료 실습 풀이의 `write_section` Worker는 목차 하나의 마크다운 자료를 쓰고, `merge_results`가 `order`로 정렬해 합친다.
```python
def write_section(state: SectionState):
    response = llm.invoke(f"""다음 <request>에 따른 학습자료를 만들어줘.
학습 제목은 <title> 학습 목표는 <objective>야. 마크다운 형식으로 깔끔하게 작성해줘.
<request>{state['request']}</request>
<title>{state['title']}</title>
<objective>{state['objective']}</objective>""")
    return {"results": [{"title": state["title"], "objective": state["objective"],
                         "content": response.text, "order": state["order"]}]}

def merge_results(state: CourseState):
    results = sorted(state["results"], key=lambda x: x["order"])
    return {"final_result": "\n\n".join(
        f"title : {r['title']}\nobjective : {r['objective']}\ncontent : {r['content']}"
        for r in results)}
```
(줄여 적음. 원본은 닫는 태그를 `<request>`, `<objective`로 잘못 썼고 `results.sort()`로 State 리스트를 직접 정렬했다.)
- (내 메모) Worker가 전체 요청을 그대로 받아 섹션마다 "2시간"짜리 자료를 만들었다.

## 학습 자료 실습 풀이 4단계: 그래프 구성과 실행
맞춤형 학습 자료 실습 풀이 그래프는 course_plan → (Send) write_section → merge_results → END 구조다.
```python
builder = StateGraph(CourseState)
builder.add_node("course_plan", course_plan)
builder.add_node("write_section", write_section)
builder.add_node("merge_results", merge_results)
builder.add_edge(START, "course_plan")
builder.add_conditional_edges("course_plan", assign_sections, ["write_section"])
builder.add_edge("write_section", "merge_results")
builder.add_edge("merge_results", END)
graph = builder.compile()

result = graph.invoke({"request": course_request})
print(result["final_result"])

for item in graph.stream({"request": course_request}):
    for node_name, update in item.items():
        print(node_name, update)
```
- 결과: 목차 4개(입문·환경 설정, 변수와 데이터 타입, 조건문·반복문, 미니 프로젝트)가 생성됐고 최종 자료는 목차 순서대로 합쳐졌다(수만 자 분량이라 생략).
- `stream` 실행에선 `write_section` 중 4번째 목차가 가장 먼저 끝나, 완료 순서가 계획 순서와 다름을 확인했다.

## 면접 문제 생성 추가 실습 문제
면접 문제 생성 추가 실습 문제는 Orchestrator-worker 패턴으로 면접 질문을 만드는 과제다. 노트북에는 과제 설명만 있고 풀이는 없다.
- 입력: 지원자의 직무, 경력 등 필요한 정보
- Orchestrator: 평가할 역량 목록을 LLM이 판단
- Worker: 역량 하나에 대한 질문 생성

(내 메모) 학습 자료 실습과 같은 구조로, `Competency(name, reason)` 목록을 Structured Output으로 받고, 역량마다 `Send("write_questions", {...,"order": i})`를 보낸 뒤 order로 정렬해 합치면 된다.

## Orchestrator-worker 복습 Q&A
- Q. Orchestrator-worker 패턴이 고정 Fan-out과 다른 점은?
  A. 작업 종류와 개수를 그래프 작성 시점이 아니라 실행 시점에 Orchestrator가 정한다. 라우팅 함수가 `Send` 리스트를 반환해 그 수만큼 Worker를 동적으로 실행한다.
- Q. LangGraph `Send("analyze_task", {...})`의 두 번째 인자는 무엇인가?
  A. 그 Worker만 받는 독립 입력 State다. Worker State 스키마(`WorkerState`) 구조와 맞아야 한다.
- Q. Orchestrator-worker에서 `task_id`(또는 `order`)를 넘기는 이유는?
  A. 병렬 완료 순서가 보장되지 않아서, 합쳐진 결과를 원래 계획 순서로 정렬하기 위해서다.
- Q. LangGraph `max_concurrency`는 무엇을 제한하나?
  A. 한 번의 그래프 실행에서 동시에 도는 태스크 수다. 전체 Worker 수는 그대로이고, RPM·TPM을 직접 계산하진 않으므로 재시도·backoff를 함께 쓴다.
- Q. Orchestrator-worker에서 Worker 결과가 덮어써지지 않고 모이는 이유는?
  A. `results: Annotated[list, operator.add]` reducer가 각 Worker의 리스트를 이어 붙이기 때문이다.
