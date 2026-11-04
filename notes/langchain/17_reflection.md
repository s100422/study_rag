---
part: langchain
lesson: Reflection + Evaluator-Optimizer
order: 17
source_type: ipynb
tags: [reflection, evaluator-optimizer, rubric, langgraph, structured-output, self-improvement, add-messages]
source: C:\Users\tnwls\aim-ai-agent\langchain_\17-reflection_answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Reflection + Evaluator-Optimizer

## Reflection + Evaluator-Optimizer 요약
Reflection + Evaluator-Optimizer 레슨은 Agent가 자기 출력을 검토하고 고치는 루프 패턴 두 가지를 LangGraph로 만든다. Reflection은 자연어 피드백으로 고정 횟수만큼 고치고, Evaluator-Optimizer는 루브릭 점수로 합격 여부를 판단한다. 마지막에 제품 리뷰 요약 실습 문제를 두 패턴으로 푼다.

## Reflection 패턴이란
Reflection 패턴은 가장 단순한 자기 개선 루프다.
```text
START → generate → should_continue? → END (종료)
          ↑                │ continue
          └──── reflect ←──┘
```
- generate 노드가 초안을 쓴다.
- should_continue가 반복 횟수를 확인하고, 상한이면 최종 초안을 남기고 끝낸다.
- 아니면 reflect 노드가 초안을 읽고 피드백(톤, 빠진 정보, 길이 등)을 준다.
- 피드백을 들고 다시 generate로 돌아간다.

State의 `messages`에 대화를 누적하므로 generate는 이전 피드백을 자연스럽게 참고한다. 실습 준비로 `ChatGoogleGenerativeAI(model="gemini-3.6-flash")`를 쓰고, API 키는 `.env` + `load_dotenv()`로 읽는다.

## Reflection 실습 1단계: State와 generate 노드
Reflection 실습 시나리오는 배송 지연 고객에게 보낼 사과 이메일을 반복 개선하는 것이다. generate는 시스템 프롬프트 + 누적 messages 전체를 LLM에 넘긴다.
```python
class ReflectionState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int

MAX_ITERATIONS = 3
generator_llm = ChatGoogleGenerativeAI(model=MODEL_NAME)
reviewer_llm = ChatGoogleGenerativeAI(model=MODEL_NAME)

def generate(state: ReflectionState):
    system = SystemMessage(content="""너는 고객 지원 이메일 작성 전문가다.
요청에 맞는 이메일을 작성하고, 리뷰 피드백이 있으면 빠짐없이 반영하되 수정 과정은 언급하지 마라.
(작성 원칙: 책임 명확, 진정성 있는 사과와 해결책, 과장 금지, 이름·주문번호 정확히 유지)
이메일 본문만 출력한다.""")
    response = generator_llm.invoke([system, *state["messages"]])
    return {"messages": [AIMessage(content=response.text)],
            "iteration": state.get("iteration", 0) + 1}
```
(시스템 프롬프트를 줄여 적음.)

## Reflection 실습 2단계: reflect 노드와 종료 조건
Reflection의 reflect 노드는 원래 요청(첫 메시지)과 최신 초안(마지막 메시지)을 태그로 감싸 리뷰어 LLM에 넘긴다. 피드백은 HumanMessage로 넣는데, generate 입장에서 피드백이 "사용자 지시"처럼 작용해야 하기 때문이다.
```python
def reflect(state: ReflectionState):
    system = SystemMessage(content="""너는 고객 지원 이메일 편집자다.
초안을 검토해 다음 수정에 바로 쓸 구체적 피드백을 써라. 이메일을 대신 다시 쓰지 않는다.
(기준: 사과의 진정성, 문제와 영향의 명확성, 해결책 포함, 정보 정확성, 간결성)
개선 필요 항목만 불릿으로, 문제점과 수정 방향을 함께. 칭찬·총평·점수 금지.""")
    original_request = state["messages"][0]
    latest_draft = state["messages"][-1]
    response = reviewer_llm.invoke([system, HumanMessage(content=(
        f"<request>\n{original_request.text}\n</request>\n\n"
        f"<draft>\n{latest_draft.text}\n</draft>"))])
    return {"messages": [HumanMessage(content=response.text)]}

def should_continue(state):
    return "end" if state["iteration"] >= MAX_ITERATIONS else "continue"
```
(프롬프트를 줄여 적음.)

## Reflection 실습 3단계: 그래프 구성과 실행
Reflection 그래프는 generate 뒤에 조건부 엣지(continue → reflect, end → END)를 걸고, reflect에서 generate로 돌아가는 엣지를 둔다.
```python
builder = StateGraph(ReflectionState)
builder.add_node("generate", generate)
builder.add_node("reflect", reflect)
builder.add_edge(START, "generate")
builder.add_conditional_edges("generate", should_continue,
                              {"continue": "reflect", "end": END})
builder.add_edge("reflect", "generate")
reflection_graph = builder.compile()

task = "배송이 2주 지연된 고객에게 사과 이메일을 작성해줘. 고객명: ..., 주문번호: ..."
result = reflection_graph.invoke({"messages": [HumanMessage(content=task)], "iteration": 0})
```
(task의 고객명·주문번호는 노트에서 생략.)
- 결과: 총 반복 3회, 메시지 6개(human 요청 → ai 초안 → human 피드백 → … → ai 최종). 초안은 지연 사유 설명, 우선 출고 안내, 할인 쿠폰, 취소 문의 안내를 담은 이메일이었다.

## Reflection 패턴의 한계
Reflection 패턴은 반복할수록 피드백이 반영되지만 한계가 있다.
- 피드백이 자연어라서 얼마나 좋아졌는지 정량화할 수 없다.
- "충분히 좋다"는 기준이 없어서 항상 `MAX_ITERATIONS`까지 돈다.
- 반복할수록 피드백이 미세해져 표현 차이만 지적하게 되고, 그게 진짜 개선인지는 따로 판단해야 한다.
- 반복이 많으면 원래 의도에서 벗어나거나 과하게 고쳐질 수 있다. 품질이 항상 오르지는 않는다.

Evaluator-Optimizer 패턴은 루브릭과 합격 기준을 명시해 종료 시점과 개선 대상을 분명히 한다. 다만 평가자가 LLM이면 점수의 주관성과 실행마다의 변동은 남는다.

## Evaluator-Optimizer 패턴과 Reflection 비교
Evaluator-Optimizer 패턴은 Reflection과 구조는 비슷하지만 평가를 구조화한다.
```text
START → generate → evaluate → pass → END
          ↑            │ fail
          └── optimize ←┘
```
- 평가 결과: Reflection은 자유 형식 자연어 피드백, Evaluator-Optimizer는 항목별 점수와 근거.
- 종료 조건: Reflection은 주로 고정 횟수, Evaluator-Optimizer는 합격 기준 달성 또는 최대 횟수.
- 개선 범위: Reflection은 전체 피드백, Evaluator-Optimizer는 미달 항목 우선 개선.
- 판정: Evaluator-Optimizer는 기준이 명시적이지만 LLM 점수는 달라질 수 있다.

실습 시나리오는 마케팅 카피 생성이다. 점수는 품질을 객관적으로 보장하는 값이 아니라 흐름 제어용 구조화된 판단으로 쓴다.

## Evaluator-Optimizer 루브릭 설계
루브릭(Rubric)은 평가 항목과 점수 기준을 정리한 채점표다. 좋은 루브릭은 구체적이고 측정 가능하다.
- "매력적인가?"보다 "감정을 자극하는 단어가 1개 이상 있는가?"
- "적절한 길이인가?"보다 "50자 이상 150자 이하인가?"
- "좋은 카피인가?"보다 "행동 유도(CTA)가 포함됐는가?"

루브릭은 도메인마다 다르다. 마케팅 카피는 감정 자극·CTA·글자 수, 기술 문서는 정확성·재현 가능성·코드 포함이 핵심이다. 설계 순서는 핵심 품질 기준 정의 → 측정 가능한 형태로 변환 → 점수 척도와 합격 기준 설정이다. 루브릭이 모호하면 점수가 들쭉날쭉해 Reflection과 다를 바 없다.

## Evaluator-Optimizer 실습 1단계: 평가 스키마와 State
Evaluator-Optimizer의 평가 결과는 Pydantic 모델로 구조화한다. 항목마다 1~10점과 근거 한 문장을 받는다.
```python
class CriterionResult(BaseModel):
    score: int = Field(description="1~10 점수", ge=1, le=10)
    reason: str = Field(description="점수 근거 (1문장)")

class EvaluationResult(BaseModel):
    clarity: CriterionResult = Field(description="핵심 가치 전달 평가")
    emotion: CriterionResult = Field(description="타겟 공감과 변화 표현 평가")
    cta: CriterionResult = Field(description="행동 유도 평가")
    conciseness: CriterionResult = Field(description="길이와 중복 표현 평가")
    summary: str = Field(description="전체 평가 요약 (1~2문장)")
```

## Evaluator-Optimizer 실습 1-2단계: State와 합격 기준 상수
Evaluator-Optimizer 마케팅 카피 실습의 State는 현재 카피, 평가 결과, 반복 횟수, 이력을 담는다. 합격 기준은 모든 항목 8점 이상, 최대 4회 반복이다.
```python
class EvalOptState(TypedDict):
    task: str
    copy: str
    evaluation: dict                 # EvaluationResult를 dict로 저장
    iteration: int
    history: Annotated[list, add]    # 이전 카피·평가·개선 지시 누적

MAX_ITERATIONS = 4
PASS_THRESHOLD = 8
EVALUATION_CRITERIA = ("clarity", "emotion", "cta", "conciseness")
evaluator = ChatGoogleGenerativeAI(model=MODEL_NAME).with_structured_output(EvaluationResult)
```
- `Annotated[list, add]`: `operator.add` 리듀서라 노드가 반환한 리스트가 뒤에 이어 붙는다.

## Evaluator-Optimizer 실습 2단계: generate_copy
Evaluator-Optimizer의 generate_copy는 history가 비어 있으면 처음 카피를 쓰고, 있으면 마지막 이력의 이전 카피와 개선 지시(optimize 노드가 만든 것)를 함께 넣어 다시 쓴다.
```python
def generate_copy(state):
    history = state.get("history", [])
    if history:
        last = history[-1]
        prompt = (f"작업: {state['task']}\n\n이전 카피:\n{last['copy']}\n\n"
                  f"개선 지시:\n{last['improvement']}\n\n위 지시를 반영해서 카피를 다시 작성해. 카피만 출력해.")
    else:
        prompt = f"다음 마케팅 카피를 작성해. 카피만 출력해.\n\n작업: {state['task']}"
    return {"copy": generator_llm.invoke(prompt).text}
```

## Evaluator-Optimizer 실습 2-2단계: evaluate_copy
Evaluator-Optimizer의 evaluate_copy는 루브릭으로 채점하고, 합격 여부(`overall_pass`)는 LLM이 아니라 코드가 모든 항목이 `PASS_THRESHOLD`(8) 이상인지로 판정한다.
```python
def evaluate_copy(state):
    system = SystemMessage(content="""너는 마케팅 카피 평가자다. 각 항목 1~10점, 근거 한 문장.
- clarity: 출퇴근 10분과 영어 실력 향상을 모두 명확히 전달하면 8점 이상
- emotion: 타겟의 문제나 기대 변화를 구체적으로 표현하면 8점 이상
- cta: 즉시 실행할 직접적 행동 유도가 있으면 8점 이상
- conciseness: 공백 포함 50~150자, 중복 없으면 8점 이상
기준 미충족 항목은 7점 이하.""")
    ev = evaluator.invoke([system, HumanMessage(content=f"<copy>\n{state['copy']}\n</copy>")]).model_dump()
    ev["overall_pass"] = all(ev[n]["score"] >= PASS_THRESHOLD for n in EVALUATION_CRITERIA)
    return {"evaluation": ev, "iteration": state.get("iteration", 0) + 1}
```
(프롬프트·변수명을 줄여 적음.)

## Evaluator-Optimizer 실습 3단계: optimize_copy와 종료 판단
Evaluator-Optimizer의 optimize는 8점 미만 항목의 점수·근거로 수정 지시를 만들어 history에 쌓는다.
```python
def optimize_copy(state):
    ev = state["evaluation"]
    failed_items = [f"- {n} ({ev[n]['score']}점): {ev[n]['reason']}"
                    for n in EVALUATION_CRITERIA if ev[n]["score"] < PASS_THRESHOLD]
    prompt = ("너는 카피 개선 편집자다. 미달 항목의 수정 지시를 써라. "
              "카피를 다시 쓰지 말고 유지/변경할 내용을 구분하라. 새 정보 추가 금지.\n"
              f"<task>\n{state['task']}\n</task>\n<current_copy>\n{state['copy']}\n</current_copy>\n"
              "<failed_criteria>\n" + "\n".join(failed_items) + "\n</failed_criteria>")
    response = generator_llm.invoke(prompt)
    return {"history": [{"copy": state["copy"], "evaluation": ev, "improvement": response.text}]}

def should_continue_eval(state):
    if state["evaluation"]["overall_pass"]:
        return "end"
    if state["iteration"] >= MAX_ITERATIONS:
        return "end"   # 상한 도달
    return "fail"
```
(f-string으로 줄임.)

## Evaluator-Optimizer 실습 4단계: 그래프 구성과 stream 실행
Evaluator-Optimizer 그래프는 generate → evaluate → (end → END | fail → optimize) → generate 루프다. `stream`으로 노드별 업데이트를 받아 카피, 항목별 점수, 개선 지시를 출력한다.
```python
builder = StateGraph(EvalOptState)
builder.add_node("generate", generate_copy)
builder.add_node("evaluate", evaluate_copy)
builder.add_node("optimize", optimize_copy)
builder.add_edge(START, "generate")
builder.add_edge("generate", "evaluate")
builder.add_conditional_edges("evaluate", should_continue_eval, {"end": END, "fail": "optimize"})
builder.add_edge("optimize", "generate")
eval_opt_graph = builder.compile()

task = "AI 기반 영어 학습 앱 'SmartLingo' 출시 광고 카피. 타겟: 20~30대 직장인. 핵심 가치: 출퇴근 10분으로 영어 실력 향상."
for event in eval_opt_graph.stream({"task": task, "iteration": 0, "history": []}):
    node_name = list(event.keys())[0]
    print(node_name, event[node_name])
```
(출력 부분을 한 줄로 줄임.)
- 1회차: clarity·emotion·cta는 9점이었지만 conciseness가 6점(약 280자로 150자 초과)이라 FAIL, optimize가 분량 축소 지시를 만들었다.

## Evaluator-Optimizer 자기 평가 편향 주의
Evaluator-Optimizer 예제는 같은 LLM이 생성과 평가를 모두 한다. 합격 규칙을 코드로 고정해도 LLM이 매기는 점수는 실행마다 달라질 수 있다. 실무에서는 평가에 더 강한 모델이나 생성과 다른 모델을 써서 자기 평가 편향(self-evaluation bias)을 줄인다.

## 리뷰 요약 실습 문제: 과제와 샘플 데이터
리뷰 요약 실습 문제는 무선 이어폰(StarBuds Pro) 사용 리뷰를 한 문단(3~5문장)으로 요약하는 과제를 Reflection과 Evaluator-Optimizer 두 패턴으로 각각 구현하는 것이다. 샘플 리뷰 `REVIEW` 문자열의 내용은 다음과 같다.
- 장점: 가격 대비 음질이 좋음(풍부한 저음, 깨끗한 고음, 또렷한 목소리), 노이즈 캔슬링이 소음을 70~80% 줄임, 앱에서 EQ·노캔 강도 조절 가능.
- 단점: 바람 부는 야외에서 노캔 약함, 배터리 공식 7시간이지만 실사용 약 5시간 반(노캔 켜면 4시간, 케이스 포함 약 20시간), 작은 귀엔 착용감 불편, 통화 품질 나쁨, 앱 연결 끊김 버그.
- 총평: 7만원대 가성비 제품, 음악 감상 위주 사용자에게 추천, 통화가 많은 사람에겐 비추천.

## 리뷰 요약 실습 문제 1: Reflection으로 요약
리뷰 요약 실습 문제 1은 Reflection 패턴(generate → should_continue → reflect 루프)으로 리뷰를 3~5문장으로 요약하는 그래프를 만드는 것이다. 장점, 단점, 추천 대상을 균형 있게 담고 반복 검토로 요약을 개선해야 한다. 결과 그래프는 `review_reflection_graph`에 저장하라고 되어 있다.
- 힌트: State는 `messages: Annotated[list, add_messages]`와 `iteration`만으로 충분하다(요청·결과·리뷰가 모두 messages로 합쳐짐). `MessagesState`를 상속해 `iteration`만 추가해도 된다.

## 리뷰 요약 실습 1 풀이: State와 generate
리뷰 요약 Reflection 풀이의 State는 messages와 iteration만 둔다. generate는 짧은 시스템 프롬프트와 messages 전체(원문 요청 + 이전 요약 + 리뷰)로 요약을 만든다.
```python
llm = ChatGoogleGenerativeAI(model=MODEL_NAME)

class State(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int

def generate(state: State):
    system_prompt = SystemMessage(content="입력받은 리뷰를 요약해줘.\n요약한 결과만 응답해줘.")
    response = llm.invoke([system_prompt, *state["messages"]])
    return {"messages": [response], "iteration": state.get("iteration", 0) + 1}
```

## 리뷰 요약 실습 1 풀이: reflect와 종료 조건
리뷰 요약 Reflection 풀이의 reflect 노드는 첫 메시지(원문 요청)와 마지막 메시지(최신 요약)를 비교해 편향·누락을 리뷰하고, 결과를 HumanMessage로 넣는다. 2회 생성하면 끝낸다.
```python
def reflect(state: State):
    request, result = state["messages"][0], state["messages"][-1]
    system_prompt = SystemMessage(content="""<result>는 <request>에 대한 요약문이야.
다음 기준으로 리뷰해줘
- 요약 과정에서 편향되지 않았는지
- 요약 과정에서 정보가 누락되지 않았는지
- review 결과만 응답해.""")
    human_prompt = HumanMessage(content=f"<request>{request}</request>\n<result>{result}</result>")
    response = llm.invoke([system_prompt, human_prompt])
    return {"messages": [HumanMessage(content=response.text)]}   # 사용자가 리뷰한 것처럼

def should_continue(state: State):
    return "end" if state["iteration"] >= 2 else "reflect"
```
(주석을 빼고 줄여 적음.)
- (내 메모) `f"{request}"`는 메시지 객체 전체 repr이 들어가므로 `request.text`를 쓰는 편이 깔끔하다.

## 리뷰 요약 실습 1 풀이: Reflection 그래프와 실행 오류
리뷰 요약 Reflection 풀이 그래프는 generate 뒤 조건부 엣지(reflect | END)와 reflect → generate 엣지로 만든다.
```python
builder = StateGraph(State)
builder.add_node("generate", generate)
builder.add_node("reflect", reflect)
builder.add_edge(START, "generate")
builder.add_edge("reflect", "generate")
builder.add_conditional_edges("generate", should_continue, {"reflect": "reflect", "end": END})
graph = builder.compile()

graph.invoke({"message": f"<review>{REVIEW}<review>"})   # 원본 그대로
```
- 원본 실행 셀은 키를 `"message"`로 잘못 적었다(State 키는 `messages`). 출력이 저장돼 있지 않다.
- (내 메모) 고친 호출: `graph.invoke({"messages": [HumanMessage(content=f"<review>{REVIEW}</review>")], "iteration": 0})`. 닫는 태그도 `</review>`가 맞다. 과제가 요구한 변수명 `review_reflection_graph` 대신 `graph`를 썼다.

## 리뷰 요약 실습 문제 2: Evaluator-Optimizer로 요약
리뷰 요약 실습 문제 2는 같은 리뷰를 Evaluator-Optimizer 패턴(generate → evaluate → optimize 루프)으로 요약하는 것이다. 모든 항목이 8점 이상이면 통과한다. 최종 요약은 `summary`, 평가 결과는 `evaluation`에 저장하고 그래프는 `review_eval_opt_graph`에 저장하라고 되어 있다. 참고 루브릭(각 1~10점, 수정·추가 가능)은 다음과 같다.
- completeness: 핵심 장점과 단점이 각각 1개 이상, 가격 정보 반영
- accuracy: 가격·사용 시간·성능이 원문과 일치하고 원문에 없는 정보 없음
- conciseness: 불필요한 반복 없이 3~5문장
- recommendation: 적합한 사용자와 부적합한 사용자를 원문 근거로 모두 언급

## 리뷰 요약 실습 2 풀이: 루브릭 스키마와 generate
리뷰 요약 Evaluator-Optimizer 풀이는 루브릭 네 항목을 Pydantic 필드로 만들고, generate는 이전 평가가 있으면 시스템 프롬프트 뒤에 "평가 결과"를 덧붙여 다시 요약한다.
```python
class EvalutionResultItem(BaseModel):
    score: int = Field(description="1 ~ 10 사이의 정수 점수")
    reason: str = Field(description="score를 매긴 이유")

class EvalutionResult(BaseModel):
    completeness: EvalutionResultItem = Field(description="핵심 장단점 각 1개 이상 + 가격 정보 반영?")
    accuracy: EvalutionResultItem = Field(description="제품 정보가 원문과 일치, 없는 정보 추가 안 함?")
    conciseness: EvalutionResultItem = Field(description="반복 없이 3~5문장?")
    recommendation: EvalutionResultItem = Field(description="적합/부적합 사용자 모두 근거와 함께 언급?")

llm_with_rubric = llm.with_structured_output(EvalutionResult)
```
(Field 설명을 줄임. `Evalution` 철자는 원본 그대로.)

## 리뷰 요약 실습 2 풀이: State와 generate
리뷰 요약 Evaluator-Optimizer 풀이의 State는 요청, 요약 결과, 평가 결과를 담는다. generate는 이전 평가가 있으면 시스템 프롬프트 뒤에 "평가 결과"를 덧붙여 다시 요약한다.
```python
class State(TypedDict):
    request: str
    result: str
    evalution: dict
    history: list

def generate(state: State):
    system_prompt = "입력받은 리뷰를 요약해줘. 다음 기준에 부합하도록 요약하고 평가 결과가 있다면 반영해줘.\n(루브릭 네 항목)"
    if state.get("evalution"):
        system_prompt += "평가 결과 : " + "".join(f"{k} {v}" for k, v in state["evalution"].items())
    result = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=state["request"])])
    return {"result": result.text}
```
(프롬프트를 줄이고 for 루프를 join으로 바꿈.)
- `history` 필드는 선언만 하고 쓰이지 않는다.

## 리뷰 요약 실습 2 풀이: 평가 노드와 미완성 부분
리뷰 요약 Evaluator-Optimizer 풀이의 평가 노드는 요청과 요약을 태그로 감싸 루브릭 구조화 출력으로 채점한다. 원본 주석은 생성과 평가에 같은 기준 프롬프트를 쓰는 건 좋지 않다고 적어 두었다.
```python
def evalutaion(state: State):
    system_prompt = SystemMessage(content="<result>는 <request>에 대한 요약문이야.\n다음 기준에 부합하도록 리뷰해줘.\n(루브릭 네 항목)")
    human_prompt = HumanMessage(content=f"<request>{state['request']}</request>\n<result>{state['result']}</result>")
    return {"evalution": llm_with_rubric.invoke([system_prompt, human_prompt]).model_dump()}

builder = StateGraph(State)
builder.add_node("generate", generate)
builder.add_node("evalutaion", evalutaion)
builder.add_edge(START, "generate")
builder.add_edge("generate", "evalutaion")
builder.add_conditional_edges("evalutaion", should_continue, {"generate": "generate", "end": END})
```
- 원본 풀이는 미완성이다. `should_continue`가 "score를 확인하고 ~ / if 충분하면:" 같은 의사코드라 실행되지 않고, optimize 노드·`compile()`·실행 셀이 없다.

## 리뷰 요약 실습 2 보완: should_continue 완성 (내 메모)
리뷰 요약 Evaluator-Optimizer 풀이에서 비어 있던 종료 판단을 채운 버전이다. 노트북에는 없는 내 코드다. 모든 항목이 8점 이상이면 끝내고, 무한 루프를 막으려고 반복 횟수 상한을 둔다.
```python
PASS = 8
MAX_ITER = 3
CRITERIA = ("completeness", "accuracy", "conciseness", "recommendation")

def should_continue(state):
    ev = state["evalution"]
    if all(ev[c]["score"] >= PASS for c in CRITERIA):
        return "end"
    if state.get("iteration", 0) >= MAX_ITER:   # State에 iteration 키 추가 필요
        return "end"
    return "generate"

review_eval_opt_graph = builder.compile()
review_eval_opt_graph.invoke({"request": REVIEW, "iteration": 0})
```
- (내 메모) `iteration`은 평가 노드에서 `state.get("iteration", 0) + 1`로 올려 줘야 한다. 과제 요구대로라면 최종 요약 키도 `result` 대신 `summary`여야 한다.

## Reflection + Evaluator-Optimizer 복습 Q&A
- Q. Reflection 패턴에서 reflect 노드의 피드백을 HumanMessage로 넣는 이유는?
  A. generate의 LLM 입장에서 피드백이 사용자 지시처럼 작용해야 하기 때문이다. `add_messages`로 누적되므로 generate가 이전 피드백을 자연스럽게 참고한다.
- Q. Reflection 패턴의 주요 한계는?
  A. 자연어 피드백이라 개선 정도를 정량화할 수 없고, 종료 기준이 없어 항상 최대 횟수까지 돌며, 반복할수록 과수정·의도 이탈이 생길 수 있다.
- Q. Evaluator-Optimizer에서 합격 여부는 누가 판정하나?
  A. LLM은 항목별 점수만 매기고, 모든 항목이 `PASS_THRESHOLD`(8) 이상인지는 코드가 판정한다. 최대 반복에 도달해도 종료한다.
- Q. 좋은 루브릭의 조건은?
  A. 구체적이고 측정 가능해야 한다. 예: "적절한 길이인가?" 대신 "50자 이상 150자 이하인가?".
- Q. Evaluator-Optimizer에서 자기 평가 편향을 줄이는 방법은?
  A. 평가에 더 강한 모델이나 생성 모델과 다른 모델을 쓴다.
