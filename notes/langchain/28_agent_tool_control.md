---
part: langchain
lesson: Agent Tool Control
order: 28
source_type: ipynb
tags: [langchain, agent, middleware, wrap_tool_call, wrap_model_call, tool-validation, context, toolcalllimit]
source: C:\Users\tnwls\aim-ai-agent\langchain_\28-agent-tool-control.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Agent Tool Control

## Agent Tool Control 요약
Agent Tool Control 레슨은 LLM이 제안한 Tool 호출을 프로그램이 Middleware로 검사·차단하는 방법을 다룬다. 계좌 조회·송금 예제로 실행 전 검사(인자·권한·승인), 실행 후 결과 검사, 호출 횟수 제한(`ToolCallLimitMiddleware`)을 차례로 적용한다.

## Agent Tool 실행 통제가 필요한 이유
Agent는 사용자 요청을 보고 어떤 Tool을 어떤 인자로 호출할지 "제안"할 뿐이다. 실제 실행 여부는 Tool을 돌리는 프로그램이 결정해야 한다. 프로그램은 인자 형식, 사용자 권한, 승인 여부를 확인하고 허용된 작업만 실행한다. 예제에서는 잔액 조회는 접근 가능한 계좌에만, 송금은 금액·권한·승인을 모두 통과해야 실행되도록 만든다.

## LangChain Agent Middleware 실행 흐름
LangChain Middleware는 모델 호출이나 Tool 호출 전후에 공통 처리를 끼워 넣는 기능이며, `create_agent(middleware=[...])`로 등록한다. Agent 실행 순서는 다음과 같다.
- `before_agent`: Agent 시작 시 한 번
- `before_model` → 모델 호출(`wrap_model_call`) → `after_model`
- 모델이 Tool 호출을 냈으면 Tool 실행(`wrap_tool_call`) 후 다시 `before_model`로 반복
- Tool 호출이 없으면 `after_agent`로 종료

`wrap_model_call`과 `wrap_tool_call`은 호출 자체를 감싸서 전후 처리나 차단을 할 수 있다. Tool 호출이 여러 개면 `wrap_tool_call`은 호출마다 따로 적용된다.

## LangChain wrap_tool_call의 request와 handler
`@wrap_tool_call`로 만든 Middleware 함수는 `request`와 `handler`를 받는다.
- `request.tool_call`: 호출할 Tool 이름(`name`), 인자(`args`), 호출 ID(`id`)
- `request.runtime.context`: Agent 실행 시 넘긴 Context(권한 정보 등)
- `handler(request)`: 다음 Middleware 또는 실제 Tool 실행으로 넘긴다.

`handler` 호출 전에는 인자·권한·승인을 검사하고, 반환된 결과로는 실행 후 검사를 한다. 실행을 막으려면 `handler`를 부르지 않고 사유를 담은 `ToolMessage`를 직접 반환한다. 실행 후 검사는 이미 일어난 작업(예: 송금)을 되돌리지 못하므로, 부작용이 있는 Tool은 반드시 실행 전에 막아야 한다.

## Agent Tool 인자 검증: Pydantic 스키마
Tool 인자 검증은 Pydantic 모델로 필드별 길이·범위를 정의해서 한다. 이 모델은 `@tool(args_schema=...)`에도 그대로 쓴다.
```python
from pydantic import BaseModel, Field

class LookupAccountArgs(BaseModel):
    account_id: str = Field(min_length=3, max_length=40)

class TransferArgs(BaseModel):
    account_id: str = Field(min_length=3, max_length=40)
    amount: int = Field(gt=0, le=1000000)
    request_id: str = Field(min_length=8, max_length=80)
```
- `amount`는 형식상 100만 원까지 허용하지만, 업무 한도(10만 원)는 별도 로직에서 검사한다.
- `request_id`는 송금 승인 여부를 확인하는 키로 쓰인다.

## Agent Tool 실행 전 검사 함수 validate_proposal (1): 이름·인자·권한
`validate_proposal(proposal, context)`는 통과하면 검증된 인자 객체를, 실패하면 상태·사유 dict를 반환한다. 앞부분은 취소·Tool 이름·인자·계좌 권한을 본다.
```python
TOOL_SCHEMAS = {'lookup_account': LookupAccountArgs, 'transfer': TransferArgs}
MAX_TRANSFER = 100000

def failure(code, message):
    return {'status': 'failed', 'code': code, 'message': message, 'data': {}}

def validate_proposal(proposal, context):
    if context['cancelled']:
        return {'status': 'cancelled', 'code': 'USER_CANCELLED', 'message': '요청이 취소되었습니다.', 'data': {}}
    schema = TOOL_SCHEMAS.get(proposal['name'])
    if schema is None:
        return failure('UNKNOWN_TOOL', '허용되지 않은 Tool입니다.')
    try:
        args = schema.model_validate(proposal['args'])
    except ValidationError:
        return failure('INVALID_ARGUMENT', 'Tool 인자가 올바르지 않습니다.')
    if args.account_id not in context['allowed_accounts']:
        return failure('FORBIDDEN', '이 계좌에 접근할 권한이 없습니다.')
```
(원본 함수를 둘로 나눠 적고 주석을 뺐다.)

## Agent Tool 실행 전 검사 함수 validate_proposal (2): 송금 한도·승인
`validate_proposal`의 뒷부분은 Tool이 `transfer`일 때만 업무 한도와 승인 상태를 검사하고, 모두 통과하면 Pydantic 인자 객체를 돌려준다.
```python
    if proposal['name'] == 'transfer':
        if args.amount > MAX_TRANSFER:
            return failure('LIMIT_EXCEEDED', '송금 한도를 초과했습니다.')
        if args.request_id in context['rejected_request_ids']:
            return {'status': 'cancelled', 'code': 'APPROVAL_REJECTED',
                    'message': '승인이 거절되었습니다.', 'data': {}}
        if args.request_id not in context['approved_request_ids']:
            return {'status': 'waiting_for_human', 'code': 'APPROVAL_REQUIRED',
                    'message': '송금 승인을 기다립니다.',
                    'data': {'request_id': args.request_id, 'amount': args.amount}}
    return args
```
- 거절은 `cancelled`, 승인 기록이 없으면 `waiting_for_human`(사람 승인 대기)으로 상태를 구분한다.
- 승인 여부는 프로그램이 가진 `approved_request_ids`로만 판단한다.

## Agent Tool 예제: 조회·송금 Tool 정의
계좌 조회 Tool은 예제 dict에서 잔액 정보를 돌려주고, 송금 Tool은 본문을 `pass`로 둬서 실행 여부만 확인한다.
```python
account_responses = {"acct-001": {"account_id": "acct-001", "balance": 80000, "currency": "KRW"}}

@tool("lookup_account", args_schema=LookupAccountArgs)
def lookup_account_tool(account_id: str):
    """계좌 ID로 잔액을 조회한다."""
    return account_responses[account_id].copy()

@tool("transfer", args_schema=TransferArgs)
def transfer_tool(account_id: str, amount: int, request_id: str):
    """계좌 ID, 금액, 요청 ID로 송금을 요청한다."""
    pass

tools = [lookup_account_tool, transfer_tool]
```
- 모델은 `ChatGoogleGenerativeAI(model="gemini-3.6-flash")`, API 키는 `load_dotenv()`로 `.env`에서 읽는다.

## LangChain wrap_model_call로 tool_choice 바꾸기
`@wrap_model_call`은 모델 호출을 감싸는 Middleware를 만든다. 예제는 첫 모델 호출에서는 Tool 호출을 강제(`"any"`)하고, Tool 결과를 받은 뒤에는 Tool 없이 안내만 하도록(`"none"`) 바꾼다.
```python
from langchain.agents.middleware import wrap_model_call
from langchain_core.messages import ToolMessage

@wrap_model_call
def force_tool_call(request, handler):
    if isinstance(request.messages[-1], ToolMessage):
        tool_choice = "none"
    else:
        tool_choice = "any"
    return handler(request.override(tool_choice=tool_choice))
```
- `request.override(...)`: 모델 호출 설정을 바꾼 새 request를 만든다.
- 마지막 메시지가 `ToolMessage`인지로 "Tool 결과를 받은 뒤"인지 판단한다.

## LangChain Agent State와 Context 차이
LangChain Agent에서 State는 Agent가 실행 중 갱신하는 정보(예: 대화 기록)이고, Context는 프로그램이 실행 기준으로 넘기는 정보(예: 사용자 권한)이다.
- Tool 인자: LLM이 호출을 제안하면서 만든다. (조회할 계좌 ID, 송금 금액)
- 실행 Context: 프로그램이 `agent.invoke(..., context=...)`로 넘긴다. (접근 가능한 계좌, 승인된 요청 ID)
- Middleware 안에서는 `request.runtime.context`로 읽는다.

LLM이 어떤 계좌를 조회하자고 해도, 실행 여부는 LLM이 바꿀 수 없는 Context의 권한 정보로 판단한다.

## Agent Tool 실행 전 검증 Middleware validate_tool_call
`validate_tool_call`은 `request.tool_call`과 `request.runtime.context`를 `validate_proposal`에 넘기고, 결과가 dict(거절·취소·승인 대기)면 Tool을 실행하지 않고 `ToolMessage`를 반환한다.
```python
@wrap_tool_call
def validate_tool_call(request: ToolCallRequest, handler):
    print("실행 전 검사:", request.tool_call["name"])
    result = validate_proposal(request.tool_call, request.runtime.context)
    if isinstance(result, dict):
        return ToolMessage(
            content=json.dumps(result, ensure_ascii=False),
            tool_call_id=request.tool_call["id"],
            name=request.tool_call["name"],
            status="error",
        )
    print("Tool 실행:", request.tool_call["name"])
    return handler(request)
```
- `tool_call_id`를 원래 호출 ID와 맞춰야 모델이 어느 호출의 결과인지 안다.
- `status="error"`로 실패한 Tool 결과임을 표시한다.

## Agent Tool 실행 전 검사 적용과 권한 없는 계좌 조회
실행 Context를 만들고, `create_agent`의 `middleware`에 모델 설정과 실행 전 검사를 등록한 뒤 권한 없는 계좌를 조회한다.
```python
execution_context = {"user_id": "user-1", "allowed_accounts": {"acct-001"},
                     "approved_request_ids": set(), "rejected_request_ids": set(), "cancelled": False}
agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt,
                     middleware=[force_tool_call, validate_tool_call])
result = agent.invoke({"messages": [HumanMessage(content="acct-991 계좌의 잔액을 조회해 줘.")]},
                      context=execution_context)
```
- 시스템 프롬프트: 지정 계좌·금액으로 Tool 호출을 제안하고, 오류면 사유만 안내하며 잔액·성공 여부를 추측하지 말라는 내용.
- 출력에는 `실행 전 검사`만 찍히고 `Tool 실행`은 없다. ToolMessage는 `FORBIDDEN` JSON이고, 마지막 AI 응답은 권한이 없어 조회에 실패했다고 안내한다.
- (설명 셀은 `acct-999`라고 했지만 실제 실행 메시지는 `acct-991`이었다.)

## Agent Tool 거절 조건 직접 테스트하기
Tool 호출 제안 dict를 직접 만들어 `validate_proposal`에 넣으면 LLM 없이 거절 조건을 확인할 수 있다.
```python
for proposal in cases:
    print(proposal['name'], validate_proposal(proposal, context))
```
케이스별 결과는 다음과 같다. (`cases` 목록 정의는 생략하고 결과만 정리했다.)
- `delete_account`(미등록 Tool) → `UNKNOWN_TOOL`
- `lookup_account`, `account_id='x'`(최소 길이 미달) → `INVALID_ARGUMENT`
- `lookup_account`, `acct-999`(권한 없음) → `FORBIDDEN`
- `transfer`, 150000원(한도 초과) → `LIMIT_EXCEEDED`
- `transfer`, 10000원 + 인자에 `approved=True` 끼워 넣기 → `waiting_for_human` / `APPROVAL_REQUIRED`

마지막 케이스가 핵심이다. LLM이 인자에 "승인됨"을 넣어도 Pydantic이 모르는 필드는 무시되고, 승인은 Context의 승인 목록으로만 인정된다.

## Agent Tool 실행 후 결과 검증이 필요한 경우
Tool 실행 후 결과 검증은 외부 API처럼 반환값을 보장하기 어려울 때 쓴다. 직접 만든 Tool이라도 외부 데이터를 쓰면 필요할 수 있다.
- 실행 전 검사 대상: LLM이 제안한 호출(이름·인자)
- 실행 후 검사 대상: Tool이 돌려준 데이터

예제는 조회 결과에 계좌 ID·잔액·통화가 있는지, 요청한 계좌와 같은 계좌인지 검사한다. 잘못된 결과는 LLM에 전달되기 전에 오류 메시지로 바꾼다. 응답 형식은 Pydantic 모델로 정의한다.
```python
from typing import Literal

class LookupResponse(BaseModel):
    account_id: str
    balance: int
    currency: Literal["KRW"]
```

## Agent Tool 결과 검증 Middleware validate_tool_result
`validate_tool_result`는 Tool 실행 후 조회 결과가 형식 오류면 `INVALID_TOOL_RESULT`, 계좌 불일치면 `RESULT_MISMATCH`로 바꾸고, 그 외 결과는 그대로 넘긴다.
```python
@wrap_tool_call
def validate_tool_result(request: ToolCallRequest, handler):
    message = handler(request)
    if request.tool_call["name"] != "lookup_account" or message.status == "error":
        return message
    error = None
    try:
        response = LookupResponse.model_validate_json(message.content)
    except ValidationError:
        error = failure("INVALID_TOOL_RESULT", "조회 결과의 필드나 형식이 잘못됨")
    else:
        if response.account_id != request.tool_call["args"]["account_id"]:
            error = failure("RESULT_MISMATCH", "요청한 계좌와 반환된 계좌가 다릅니다.")
    if error is not None:
        return ToolMessage(content=json.dumps(error, ensure_ascii=False),
            tool_call_id=request.tool_call["id"], name=request.tool_call["name"], status="error")
    return message
```
(print 줄은 빼고 메시지 문구를 줄였다.)

## Agent Tool Middleware 등록 순서와 결과 검사 실행
Middleware는 리스트 순서대로 바깥에서 안쪽으로 감싼다. `[force_tool_call, validate_tool_call, validate_tool_result]`로 등록하면 호출은 `validate_tool_call → validate_tool_result → Tool` 순으로 들어가고, 결과는 돌아오면서 `validate_tool_result`가 검사한다. 실행 전 검사에서 거절되면 `handler`가 불리지 않으므로 Tool 실행과 결과 검사 모두 일어나지 않는다.

예제는 `account_responses["acct-001"]`를 잠시 "정상 / 필드 누락(balance 없음) / 계좌 불일치(acct-999)" 데이터로 바꿔 실행하고 `finally`에서 원래 값으로 되돌린다. "계좌 불일치" 실행 결과:
```text
실행 전 검사: lookup_account
Tool 실행: lookup_account
실행 후 검사: lookup_account
```
ToolMessage는 `RESULT_MISMATCH` 오류로 바뀌고, 마지막 AI 응답도 잘못된 잔액 대신 오류 사유를 안내한다.

## LangChain ToolCallLimitMiddleware로 Tool 호출 횟수 제한
`ToolCallLimitMiddleware`는 Tool 호출 횟수를 관리하는 내장 Middleware다. `run_limit`은 Agent 실행 한 번에서 허용할 호출 수이고, 횟수는 새 실행마다 초기화된다.
```python
from langchain.agents.middleware import ToolCallLimitMiddleware

limited_agent = create_agent(
    model=llm, tools=tools, system_prompt=system_prompt,
    middleware=[
        ToolCallLimitMiddleware(run_limit=0, exit_behavior="continue"),
        force_tool_call, validate_tool_call, validate_tool_result,
    ],
)
```
- `exit_behavior="continue"`: 한도 초과 호출에 오류 메시지를 돌려주고, 모델이 그걸 보고 사용자에게 안내한다.
- `run_limit=0`으로 조회하면 Tool은 실행되지 않고 ToolMessage가 다음과 같다.
```text
Tool call limit exceeded. Do not make additional tool calls.
```
- `run_limit=1`이면 조회 한 번이 허용된다.
- 특정 Tool만 제한: `ToolCallLimitMiddleware(tool_name="lookup_account", run_limit=2)`

## Agent Tool 검사 위치 정리
Agent Tool 통제는 검사 종류마다 실행 시점이 다르다.
- 인자·권한·승인 검사: Tool 실행 전. `@wrap_tool_call`에서 `handler(request)` 호출 전에 한다.
- 반환값 검사: Tool 실행 후, LLM에 전달하기 전. `handler(request)`가 돌려준 결과를 검사한다.
- 호출 횟수 검사: 허용 횟수를 넘긴 호출의 실행 전. `ToolCallLimitMiddleware`가 맡는다.

검증 함수는 "무엇을 검사할지"를 정의하고, Middleware는 그 검사를 "언제 실행할지"에 연결한다.

## Agent Tool이 많을 때 Tool별 검증 함수 연결
Tool이 많아지면 `validate_proposal` 하나에서 이름으로 분기하는 대신, Tool별 검증 함수를 dict로 연결할 수 있다. 각 검증 함수는 통과 시 인자 객체, 거절 시 사유 dict를 반환한다고 가정한다.
```python
TOOL_GUARDS = {"lookup_account": validate_lookup, "transfer": validate_transfer}

@wrap_tool_call
def validate_by_tool(request: ToolCallRequest, handler):
    tool_call = request.tool_call
    guard = TOOL_GUARDS.get(tool_call["name"])
    if guard is None:
        result = failure("UNKNOWN_TOOL", "등록되지 않은 Tool입니다.")
    else:
        result = guard(tool_call["args"], request.runtime.context)
    if isinstance(result, dict):
        return ToolMessage(content=json.dumps(result, ensure_ascii=False),
                           tool_call_id=tool_call["id"], name=tool_call["name"], status="error")
    return handler(request)
```
- `validate_lookup`, `validate_transfer`는 노트북에서 정의하지 않은 가정 함수다.

## Agent Tool Control 실습 문제: Context로 Tool 실행 허용하기
Agent Tool Control 실습은 Context 값에 따라 `get_notice` Tool 실행을 허용하거나 막는 것이다. 허용이면 안내 문구를 조회하고, 아니면 Tool 없이 거절 사유를 안내한다. `context={"allow_tool": True}`와 `False`로 각각 실행해 비교한다.

## Agent Tool Control 실습 풀이: allow_tool Context 검사 Middleware
Agent Tool Control 실습 풀이는 Tool 실행 전 Middleware에서 Context의 `allow_tool`을 확인해, False면 Tool 대신 거절 `ToolMessage`를 돌려준다.
```python
@tool
def get_notice() -> str:
    """안내 문구를 조회한다."""
    print("Tool 실행")
    return "오늘 수업은 오후 6시에 시작합니다."

@wrap_tool_call
def check_tool_permission(request, handler):
    if not request.runtime.context['allow_tool']:
        return ToolMessage(content="실행 불가 함수입니다.",
                           tool_call_id=request.tool_call["id"],
                           name=request.tool_call["name"], status="error")
    return handler(request)

agent = create_agent(model=llm, tools=[get_notice], middleware=[check_tool_permission])
result = agent.invoke({'messages': [HumanMessage(content="function call을 활용해서 안내 문구를 출력해줘.")]},
                      context={'allow_tool': True})
```
(디버그 print 일부를 뺐다.)
- `True`: `Tool 실행`이 찍히고 응답에 "오늘 수업은 오후 6시에 시작합니다."가 나온다.
- `False`: Tool이 실행되지 않고, 모델이 함수가 실행 불가 상태라고 안내한다.

## Agent Tool Control 복습 Q&A
- Q. `@wrap_tool_call` Middleware에서 Tool 실행을 막으려면 어떻게 하나?
  A. `handler(request)`를 호출하지 않고, 원래 `tool_call_id`와 사유를 담은 `ToolMessage`(status="error")를 반환한다.
- Q. Agent Tool 실행 후 결과 검사만으로 송금 같은 작업을 막을 수 있나?
  A. 없다. 실행 후 검사는 이미 수행된 작업을 되돌리지 못하므로 부작용 있는 Tool은 실행 전에 막아야 한다.
- Q. LLM이 Tool 인자에 `approved=True`를 넣으면 송금이 승인되나?
  A. 아니다. 승인은 프로그램이 넘긴 Context의 `approved_request_ids`로만 판단하므로 `APPROVAL_REQUIRED`(승인 대기)가 된다.
- Q. Middleware 안에서 Agent 실행 Context는 어디서 읽나?
  A. `request.runtime.context`. 값은 `agent.invoke(..., context=...)`로 넘긴다.
- Q. `ToolCallLimitMiddleware(run_limit=0, exit_behavior="continue")`의 동작은?
  A. Tool을 실행하지 않고 "Tool call limit exceeded" 메시지를 돌려주며, 모델이 그걸 받아 사용자에게 안내한다. 횟수는 실행마다 초기화된다.
