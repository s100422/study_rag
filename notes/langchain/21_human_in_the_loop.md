---
part: langchain
lesson: Human-in-the-Loop
order: 21
source_type: ipynb
tags: [langgraph, human-in-the-loop, interrupt, command, resume, checkpointer, thread_id]
source: C:\Users\tnwls\aim-ai-agent\langchain_\21-human-in-the-loop_answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Human-in-the-Loop

## Human-in-the-Loop 요약
LangGraph에서 `interrupt()`로 그래프를 멈추고, 사람이 승인·거절·추가 입력을 한 뒤 `Command(resume=...)`로 재개하는 HITL 흐름을 결제 Tool, 게시글 발행, 계획 검토, 추가 질문 생성 예제로 실습한다.

## Human-in-the-Loop(HITL)란
Human-in-the-Loop는 AI가 모든 일을 자동 처리하지 않고, 중요한 판단 지점에서 사람이 검토하거나 결정하게 하는 방식이다. 사람이 끼어들어야 하는 대표적인 경우는 다음과 같다.
- 결제, 삭제, 이메일 발송처럼 되돌리기 어려운 작업의 승인
- LLM이 만든 답변·문서의 검토와 수정
- 작업에 필요한 정보가 부족할 때 추가 입력 요청

흐름은 `AI 작업 → 판단 지점에서 중단 → 사람이 검토·입력 → 작업 재개`이다. LangGraph는 그래프 실행을 중단하고, 입력을 받은 뒤 재개하는 방식으로 HITL을 구현한다.

## HITL 준비: 사용 모듈과 모델 설정
HITL 실습에서 쓰는 주요 import와 모델 설정이다. API 키는 `.env`에 두고 `load_dotenv()`로 불러온다(예: `os.environ["GOOGLE_API_KEY"]`). (import 목록은 핵심만 줄여 옮김)
```python
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt

load_dotenv()
MODEL_NAME = "gemini-3.6-flash"
```
- `interrupt`: 실행을 멈추고 값을 호출자에게 넘기는 함수
- `Command`: 멈춘 그래프에 결정을 전달(`resume`)할 때 쓰는 객체
- `MemorySaver`: 중단 지점을 기억하는 Checkpointer

## LangGraph interrupt() 동작 원리
LangGraph의 `interrupt(value)`는 노드나 Tool 안에서 호출할 수 있다.
- 실행이 `interrupt()`에 닿으면 그래프가 멈추고 `value`가 호출자에게 `__interrupt__`로 전달된다.
- Checkpointer가 그 시점의 그래프 state와 중단된 작업을 저장한다.
- 같은 `thread_id`로 `Command(resume=결정)`을 보내면 노드·Tool이 **처음부터 다시 실행**되고, 이번에는 `interrupt()`가 멈추지 않고 그 결정을 반환값으로 돌려준다.

그래서 결제 같은 부작용 있는 코드는 반드시 `interrupt()` 뒤에 둔다. `interrupt()` 앞의 코드(예: print)는 재개할 때 한 번 더 실행된다.

## HITL 중단에 쓰이는 세 가지 값
LangGraph HITL에서 구분해야 할 값은 세 가지다.
- 그래프 state: 노드들이 읽고 고치는 내부 실행 상태
- interrupt payload: 호출자가 검토할 질문, Tool 이름·인자 (`interrupt(value)`의 value)
- resume value: 승인자가 그래프에 돌려주는 결정 (`Command(resume=...)`)

payload와 resume 값은 Checkpointer가 저장할 수 있도록 문자열·숫자·리스트·딕셔너리 같은 JSON 직렬화 가능한 값을 쓴다.
```text
1차 요청: graph.invoke(작업, config) → interrupt()에서 중단 → payload 반환
2차 요청: graph.invoke(Command(resume=결정), 같은 config)
         → 같은 thread_id 상태 복원 → 결정이 interrupt() 반환값이 되어 재개
```

## HITL 실습 1단계: 승인이 필요한 결제 Tool 만들기
결제 Tool `send_payment` 안에서 `interrupt()`로 승인 요청을 보내고, 돌아온 결정에 따라 결제를 진행하거나 취소한다.
```python
@tool(parse_docstring=True)
def send_payment(amount: int, recipient: str) -> str:
    """수신자에게 결제를 실행한다.

    Args:
        amount: 결제 금액
        recipient: 수신자 이름
    """
    print(f"결제 요청 검토: {recipient}, {amount:,}원")  # 재개 시 다시 출력됨
    decision = interrupt({
        "question": "이 결제를 실행하시겠습니까?",
        "tool": "send_payment",
        "args": {"amount": amount, "recipient": recipient},
    })
    if decision["action"] == "reject":
        return f"결제가 취소되었습니다. 사유: {decision.get('reason', '사유 없음')}"
    return f"{recipient}에게 {amount:,}원 결제 완료."  # 부작용은 interrupt 뒤에
```
- `parse_docstring=True`: docstring의 Args 설명을 Tool 인자 설명으로 사용

## HITL 실습 2단계: Agent 그래프와 Checkpointer 구성
Agent 노드가 Tool 호출을 만들면 `ToolNode`가 `send_payment`를 실행하고, Tool 안의 `interrupt()`에서 멈춘다. 나중에 재개하려면 Checkpointer와 `thread_id`가 꼭 있어야 한다.
```python
class State(TypedDict):
    messages: Annotated[list, add_messages]

tools = [send_payment]
llm = ChatGoogleGenerativeAI(model=MODEL_NAME).bind_tools(tools)

def agent(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

builder = StateGraph(State)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")
graph = builder.compile(checkpointer=MemorySaver())
```
- `tools_condition`: 마지막 메시지에 Tool 호출이 있으면 `tools`로, 없으면 종료로 보낸다.

## HITL 실습 3단계: 첫 invoke에서 Tool 실행 전 중단 확인
첫 `invoke()`는 결제를 실행하지 않는다. `interrupt()`에 넘긴 질문과 인자가 `result["__interrupt__"]`에 담겨 돌아오고, 다음 노드는 `tools`로 남는다.
```python
config = {"configurable": {"thread_id": "payment-2"}}
result = graph.invoke({"messages": [("user", "홍길동에게 50000원 결제해줘")]}, config)

request = result["__interrupt__"][0].value
print(request["question"], request["tool"], request["args"])
print(graph.get_state(config).next)
```
```text
결제 요청 검토: 홍길동, 50,000원
이 결제를 실행하시겠습니까? send_payment {'amount': 50000, 'recipient': '홍길동'}
('tools',)
```
(출력 형식은 한 줄로 합쳐 옮김)

## HITL 실습 4단계: Command(resume)로 승인 또는 거절 전달
같은 config로 `Command(resume=...)`를 보내면 Tool이 처음부터 다시 실행되고, `interrupt()`는 resume 값을 반환한다.
```python
# 승인
result = graph.invoke(Command(resume={"action": "approve"}), config)
print(result["messages"][-1].text)
# → 홍길동님에게 50,000원 결제가 완료되었습니다.

# 거절 (다른 thread에서 새 요청을 중단시킨 뒤)
config2 = {"configurable": {"thread_id": "payment-3"}}
graph.invoke({"messages": [("user", "김철수에게 100000원 결제해줘")]}, config2)
result = graph.invoke(
    Command(resume={"action": "reject", "reason": "금액을 다시 확인해야 합니다."}),
    config2,
)
print(result["messages"][-1].text)
# → ...금액 확인이 필요하여 결제가 취소되었습니다.
```
- 재개 시에도 "결제 요청 검토: ..." 줄이 다시 출력된다. Tool이 처음부터 재실행되기 때문이다.

## HITL 실습 5단계: input()으로 직접 승인·거절하기
노트북에서는 `input()`으로 승인 여부를 받아 resume 값을 만든다. 실제 서비스에서는 웹 화면이나 API로 결정을 전달한다.
```python
input_config = {"configurable": {"thread_id": "payment-input"}}
result = graph.invoke({"messages": [("user", "이영희에게 70000원 결제해줘")]}, input_config)
request = result["__interrupt__"][0].value
print(request["question"], request["args"])

answer = input("결제를 승인하시겠습니까? (y/n): ").strip().lower()
if answer == "y":
    decision = {"action": "approve"}
else:
    decision = {"action": "reject", "reason": input("거절 사유를 입력하세요: ")}

result = graph.invoke(Command(resume=decision), input_config)
print(result["messages"][-1].text)
```
- 실행 기록에서는 거절을 골라 "결제를 시도하였으나 취소되었습니다"가 출력됐다.

## HITL 서버 요청 흐름: /chat과 /resume 두 번의 API 호출
실제 서비스에서 서버는 승인될 때까지 요청 하나를 붙잡고 있지 않는다. HITL을 두 번의 API 요청으로 나눈다.
- `POST /chat`: 서버가 그래프를 실행 → `interrupt()`에서 중단 → `thread_id`와 질문(payload)을 응답하고 요청 종료
- 클라이언트: `thread_id`를 저장하고 사용자에게 [승인]/[거절] UI를 보여 줌
- `POST /resume`: 같은 `thread_id`와 action(approve/reject)을 보냄 → 서버가 `Command(resume=...)`로 중단된 그래프를 찾아 재개 → action에 따라 분기 후 완료 응답

핵심은 `thread_id`가 두 요청을 이어 주는 열쇠라는 점이다.

## HITL 실습 6단계: Server endpoint 함수 만들기
노트북 안에서 서버 API endpoint(`POST /chat`, `POST /resume`)를 함수로 흉내 낸다. Client는 LangGraph 코드를 직접 다루지 않고 이 함수들만 호출한다.
```python
# Backend: POST /chat (interrupt가 반드시 발생한다고 가정)
def post_chat(message: str, thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"messages": [("user", message)]}, config)
    request = result["__interrupt__"][0].value
    return {"thread_id": thread_id, "question": request["question"],
            "tool": request["tool"], "args": request["args"]}

# Backend: POST /resume
def post_resume(thread_id: str, decision: dict) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(Command(resume=decision), config)
    return {"message": result["messages"][-1].text}
```

## HITL 실습 7단계: Client에서 승인 요청 처리하기
Client(Frontend)는 `post_chat()`으로 요청을 보내고 받은 질문을 화면에 보여 준 뒤, 사용자 결정을 `post_resume()`으로 다시 보내 최종 결과를 표시한다. 두 호출은 응답의 `thread_id`로 이어진다.
```python
response = post_chat("박민수에게 30000원 결제해줘", "payment-client-server")
print(response["question"], response["args"])
decision = {"action": "approve"}  # 실제로는 input()으로 y/n을 받아 만든다
print(post_resume(response["thread_id"], decision)["message"])
```
(Frontend 부분의 input 분기는 한 줄로 줄여 옮김)

## HITL 실습 문제 1: 게시글 발행 승인하기
실습 문제: `publish_post(title, content)` Tool을 만들고, 게시글을 발행하기 전에 사용자 승인을 받는 HITL 흐름을 구현한다. 승인과 거절을 각각 실행해 결과를 확인한다.

풀이 코드(Tool 정의와 Agent 생성):
```python
from langchain.agents import create_agent

@tool
def publish_post(title: str, content: str) -> str:
    """게시글을 발행한다."""
    print("게시글 발행 검토를 해주세요.")
    decision = interrupt({
        "question": "이 게시글을 공개하겠습니까?",
        "tool": "publish_post",
        "args": {"title": title, "content": content},
    })
    if decision["action"] == "approve":
        return "게시글 발행 성공!"
    elif decision["action"] == "reject":
        return "게시글 발행 실패!"

agent = create_agent(model=llm, tools=[publish_post], checkpointer=MemorySaver())
```
- `create_agent`에 checkpointer를 넘기면 직접 StateGraph를 짜지 않아도 interrupt/resume이 된다.
- (내 메모) 원본은 Tool이 이미 바인딩된 `llm`을 model로 넘긴다. 순수 모델을 넘기는 편이 깔끔해 보인다.

## HITL 실습 문제 1 풀이: 게시글 발행 실행과 재개
풀이 코드(중단 후 사용자 입력으로 재개):
```python
config = {"configurable": {"thread_id": "thread-2"}}
result = agent.invoke({"messages": [("human", "점심식사에 대한 게시글을 발행해줘.")]}, config=config)
print(result["__interrupt__"][0].value)   # 질문, 제목, 본문 확인

user_input = input("할꺼면 - y, 안할꺼면 - n")
action = "approve" if user_input == "y" else "reject"
result = agent.invoke(Command(resume={"action": action}), config=config)

for r in result["messages"]:
    print(r.type, r.text)
```
```text
human 점심식사에 대한 게시글을 발행해줘.
ai
tool 게시글 발행 실패!
ai 점심식사에 대한 게시글 발행을 시도했으나 실패했습니다. ...
```
- 첫 출력에는 LLM이 지은 게시글 제목·본문이 payload의 `args`에 담겨 보인다.
- 실행 기록에서는 거절(n)을 골라 Tool이 "게시글 발행 실패!"를 반환했다. (원본 if/elif 분기를 한 줄로 줄여 옮김)

## HITL 실습 문제 2: Plan-and-Execute 계획 검토 그래프
실습 문제: Planner가 만든 계획을 실행 전에 사람이 검토한다. 승인하면 Executor가 실행하고, 거절하면 추가 의견을 Planner에 넘겨 계획을 다시 만든 뒤 다시 검토받는다.
```text
Planner → 계획 검토(HITL) ├─ 승인 → Executor
                          └─ 거절+의견 → Planner → 계획 검토
```
제공된 기본 코드(State, Planner, Executor):
```python
class SimplePlanState(TypedDict):
    task: str
    plan: list[str]
    completed: Annotated[list[str], operator.add]
    action: str
    feedback: str

class SimplePlan(BaseModel):
    steps: list[str] = Field(description="순서대로 수행할 단계")

simple_planner = ChatGoogleGenerativeAI(model=MODEL_NAME).with_structured_output(SimplePlan)

def simple_execute_step(state: SimplePlanState):
    step = state["plan"][0]
    return {"plan": state["plan"][1:], "completed": [f"완료: {step}"]}

def route_execution(state: SimplePlanState):
    return "continue" if state["plan"] else "end"
```
- `completed`는 `operator.add` 리듀서라 실행할 때마다 리스트에 누적된다.

## HITL 실습 문제 2 풀이: 피드백 반영 Planner와 승인 노드
풀이 코드. Planner는 feedback이 있으면 기존 계획과 피드백을 함께 넣어 다시 계획하고, 승인 노드는 `interrupt()`로 계획을 보여 주고 결정을 받는다.
```python
def simple_plan_step(state: SimplePlanState):
    task = state["task"]
    if state.get("feedback"):
        task += f"기존 계획 : {state.get('plan')} 다음 피드백을 바탕으로 작성해줘. {state.get('feedback')}"
    result = simple_planner.invoke(f"{task}\n실행 계획을 3단계 이내로 작성하세요.")
    return {"plan": result.steps}

def human_approval(state: SimplePlanState):
    decision = interrupt({"plan": state["plan"], "question": "이 계획으로 실행할까요?"})
    return {"action": decision["action"], "feedback": decision.get("feedback", "")}

def route_human_appoval(state: SimplePlanState):
    return "edit" if state["action"] == "edit" else "approve"
```
- 원본 f-string은 바깥과 안쪽 따옴표가 모두 `'`라 Python 3.12 이상에서만 동작한다. (내 메모: 여기서는 안쪽을 `'`, 바깥을 `"`로 바꿔 적음)

## HITL 실습 문제 2 풀이: 계획 검토 그래프 연결
풀이 코드. `planner → approval` 다음에 조건 분기로 `edit`이면 planner로, `approve`이면 executor로 보낸다.
```python
base_builder = StateGraph(SimplePlanState)
base_builder.add_node("planner", simple_plan_step)
base_builder.add_node("executor", simple_execute_step)
base_builder.add_node("approval", human_approval)

base_builder.add_edge(START, "planner")
base_builder.add_edge("planner", "approval")
base_builder.add_conditional_edges(
    "approval", route_human_appoval,
    {"edit": "planner", "approve": "executor"},
)
base_builder.add_conditional_edges(
    "executor", route_execution, {"continue": "executor", "end": END},
)
hitl_graph = base_builder.compile(checkpointer=MemorySaver())
```
- 그래프 이미지는 `planner → approval → (planner | executor)`, executor 자기 루프 구조로 그려진다.
- (원본 오타) 함수명 `route_human_appoval`은 approval의 오타지만 동작에는 문제 없다.

## HITL 실습 문제 2 풀이: 계획 수정 후 승인 실행
풀이 코드. 첫 실행에서 계획이 interrupt로 나오고, `edit`+피드백으로 재계획, `approve`로 실행한다.
```python
config = {"configurable": {"thread_id": "plan-review-2"}}
result = hitl_graph.invoke({"task": "팀 회의 준비하기"}, config)
print(result["__interrupt__"][0].value)  # {'plan': [...3단계...], 'question': ...}

result = hitl_graph.invoke(
    Command(resume={"action": "edit", "feedback": input()}), config)
print(result["__interrupt__"][0].value)  # 피드백이 반영된 새 계획

result = hitl_graph.invoke(Command(resume={"action": "approve"}), config)
print(*result["completed"], sep="\n")   # "완료: ..." 3줄
```
- `get_state_history(config)`로 보면 `('planner',) → ('approval',) → ('planner',) → ('approval',) → ('executor',) ×3 → ()` 순서가 최신순 역순으로 나와, 계획을 한 번 되돌렸다가 승인한 경로를 확인할 수 있다.

## HITL 실습 문제 3: 부족한 정보를 객관식 질문으로 묻기
실습 문제: 요청에 필요한 정보가 부족하면 LLM이 추가 질문(객관식 선택지 포함)을 만들고, 사용자 답을 받은 뒤 원래 요청을 처리한다. 예: "여행 계획을 짜 줘", "퇴근 후 운동 루틴 추천해 줘".

풀이 코드(State와 구조화 출력 스키마):
```python
llm = ChatGoogleGenerativeAI(model=MODEL_NAME)

class QuestionState(TypedDict):
    request: str
    message: str
    questions: list
    answer: list
    result: str

class Question(BaseModel):
    question: str = Field(description="질문")
    options: list[str] = Field(description="질문에 대한 선택지.")

class Questions(BaseModel):
    message: str = Field(description="질문에 대한 안내 메시지.")
    questions: list[Question]
```
- 흐름: `START → make_questions → ask_questions(interrupt) → summarize → END`

## HITL 실습 문제 3 풀이: 질문 생성·interrupt·응답 노드
풀이 코드(노드 3개와 그래프):
```python
def make_questions(state: QuestionState):
    response = llm.with_structured_output(Questions).invoke(
        f"{state['request']}를 처리하기 위해 유저에게 요청할 질문을 만들어줘.")
    return {"message": response.message,
            "questions": [q.model_dump() for q in response.questions]}

def ask_questions(state: QuestionState):
    answer = interrupt({"message": state["message"], "questions": state["questions"]})
    return {"answer": answer["answer"]}

def summarize(state: QuestionState):
    result = llm.invoke(f"사용자 요청 : {state['request']}\n"
                        f"사용자에게 받은 추가 정보 : {state['answer']}\n"
                        "사용자의 요청에 대해서 응답해줘.")
    return {"result": result.text}
```
(프롬프트 문자열을 줄여 옮김)
- (내 메모) `model_dump()`: Pydantic 객체를 dict로 바꿔 JSON 직렬화 가능한 payload로 만든다.
- `ask_questions`가 `interrupt()`로 질문 목록을 내보내고, resume 값의 `answer`를 State에 저장한다.

## HITL 실습 문제 3 풀이: 질문 그래프 연결
풀이 코드. 세 노드를 일직선으로 잇고, interrupt 재개를 위해 Checkpointer를 붙여 컴파일한다.
```python
builder = StateGraph(QuestionState)
builder.add_node("make_questions", make_questions)
builder.add_node("ask_questions", ask_questions)
builder.add_node("summarize", summarize)
builder.add_edge(START, "make_questions")
builder.add_edge("make_questions", "ask_questions")
builder.add_edge("ask_questions", "summarize")
builder.add_edge("summarize", END)
question_graph = builder.compile(checkpointer=MemorySaver())
```

## HITL 실습 문제 3 풀이: 답변 수집 후 resume
풀이 코드. interrupt payload의 질문을 하나씩 보여 주고 `(질문, 답)` 목록을 모아 resume으로 넘긴다.
```python
config = {"configurable": {"thread_id": "session-2"}}
result = question_graph.invoke(
    {"request": "여행 계획을 짤꺼야. 나한테 맞는 여행계획을 추천해줘."}, config=config)

request = result["__interrupt__"][0].value
print(request["message"])
answer = []
for q in request["questions"]:
    print(q["question"], q["options"])
    answer.append((q["question"], input("너의 선택을 입력하세요.")))

response = question_graph.invoke(Command(resume={"answer": answer}), config=config)
print(response["result"])
```
- 생성된 질문 예: 동행자(혼자/친구/가족…), 여행 스타일, 기간, 선호 분위기 — 각각 선택지 4~5개.
- 답을 넣고 재개하면 답변에 맞춘 당일치기 도심 여행 코스 같은 추천이 `result`에 담긴다.
- (기록상 이상) resume 셀 출력에 `AttributeError: 'dict' object has no attribute 'result'`가 남아 있지만 다음 셀의 `response['result']`는 정상 출력된다. 이전 실행의 오래된 에러 출력으로 보인다.

## Human-in-the-Loop 복습 Q&A
- Q. LangGraph HITL에서 `interrupt()`로 멈춘 그래프를 재개하려면 무엇이 필요한가?
  A. 컴파일 시 Checkpointer, 같은 `thread_id`의 config, 그리고 `graph.invoke(Command(resume=결정), config)` 호출이 필요하다.
- Q. HITL 재개 시 Tool·노드는 어디서부터 다시 실행되나?
  A. 처음부터 다시 실행된다. 단 `interrupt()`는 멈추지 않고 resume 값을 반환하므로, 부작용 있는 코드는 `interrupt()` 뒤에 둬야 한다.
- Q. interrupt payload와 resume value에는 어떤 값을 써야 하나?
  A. Checkpointer가 저장할 수 있는 JSON 직렬화 가능한 값(문자열, 숫자, 리스트, 딕셔너리)을 쓴다.
- Q. 실서비스에서 HITL 승인 흐름을 API로 나누면 어떻게 되나?
  A. `/chat`이 interrupt payload와 `thread_id`를 돌려주고 끝나며, 사용자가 결정하면 `/resume`이 같은 `thread_id`로 `Command(resume=...)`를 보내 재개한다.
- Q. 중단된 그래프의 다음 실행 노드는 어떻게 확인하나?
  A. `graph.get_state(config).next`를 본다. 결제 예제에서는 `('tools',)`였다.
