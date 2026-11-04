---
part: langchain
lesson: Fault Tolerance
order: 27
source_type: ipynb
tags: [langgraph, fault-tolerance, retrypolicy, checkpoint, resume, timeout, error_handler, idempotency]
source: C:\Users\tnwls\aim-ai-agent\langchain_\27-fault-tolerance.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Fault Tolerance

## Fault Tolerance 요약
LangGraph에서 장애 허용(Fault Tolerance)을 구현하는 방법을 다룬다. `RetryPolicy` 자동 재시도, checkpoint 기반 재개(순차·병렬), `TimeoutPolicy` 실행 시간 제한, `error_handler`로 실패 결과 남기기, `set_node_defaults` 공통 정책, 멱등성 키로 중복 저장 막기까지 실습한다.

## 장애 허용(Fault Tolerance)이란
장애 허용(Fault Tolerance)은 장애가 났을 때 오류를 처리하거나 복구해서 작업을 계속하거나 다시 이어 갈 수 있게 하는 능력이다. LangGraph에서는 노드 단위 자동 재시도, checkpoint에서 재개, 시간 제한, 오류 처리 함수 등으로 구현한다.
```python
from typing import TypedDict
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy
```

## LangGraph RetryPolicy 설정 항목
LangGraph 노드에 `RetryPolicy`를 걸면 지정한 오류가 났을 때 **한 번의 그래프 호출 안에서** 그 노드를 자동으로 다시 실행한다. 설정 항목:
- `initial_interval`: 첫 재시도 전 대기 시간
- `backoff_factor`: 대기 시간 증가 배수
- `max_interval`: 최대 대기 시간
- `max_attempts`: 최초 실행을 포함한 최대 시도 횟수
- `jitter`: 대기 시간에 무작위 지연을 섞을지 여부
- `retry_on`: 재시도할 예외 타입 또는 판별 함수

## RetryPolicy 실습 1단계: 두 번 실패 후 성공하는 노드
`prepare → call_service` 그래프에서 `call_service`가 일시적 연결 오류로 두 번 실패하고 세 번째에 성공하도록 만든다. 카운터로 노드별 실행 횟수를 센다.
```python
class RetryState(TypedDict):
    query: str
    prepared_query: str
    response: str

retry_count = {"prepare": 0, "call_service": 0}

def retry_prepare(state: RetryState):
    retry_count["prepare"] += 1
    return {"prepared_query": state["query"].strip()}

def call_unstable_service(state: RetryState):
    retry_count["call_service"] += 1
    attempt = retry_count["call_service"]
    print(f"call_service 시도 {attempt}")
    if attempt < 3:   # 실습용 강제 예외. 실제로는 외부 API 호출 자리
        raise ConnectionError("일시적 연결 오류")
    return {"response": f"조회 성공: {state['prepared_query']}"}
```
(print 일부를 빼고 옮김)

## RetryPolicy 실습 2단계: 노드에 재시도 정책 연결
`add_node`의 `retry_policy` 인자로 `call_service`에만 정책을 건다. `max_attempts=3`이라 두 번 실패해도 세 번째 시도에서 성공한다.
```python
retry_policy = RetryPolicy(
    initial_interval=2.0, backoff_factor=2.0, max_interval=1.0,
    max_attempts=3, jitter=True, retry_on=ConnectionError,
)
rb = StateGraph(RetryState)
rb.add_node("prepare", retry_prepare)
rb.add_node("call_service", call_unstable_service, retry_policy=retry_policy)
rb.add_edge(START, "prepare")
rb.add_edge("prepare", "call_service")
rb.add_edge("call_service", END)
retry_graph = rb.compile()

print(retry_graph.invoke({"query": "배송 현황"})["response"])
print(retry_count)
```
```text
call_service 시도 1
call_service 시도 2
call_service 시도 3
조회 성공: 배송 현황
{'prepare': 1, 'call_service': 3}
```
- 실패한 `call_service`만 재시도되고, 끝난 `prepare`는 다시 실행되지 않는다.
- (내 메모) `initial_interval=2.0`인데 `max_interval=1.0`이라 실제 대기는 최대 1초로 잘릴 것으로 보인다.

## RetryPolicy 실습 3단계: 최대 시도 횟수 소진 시 예외
`max_attempts=2`로 줄이면 두 번 다 실패하고, 재시도를 다 쓰면 `invoke()`에서 예외가 호출 코드로 올라온다.
```python
retry_count = {"prepare": 0, "call_service": 0}
limited = RetryPolicy(initial_interval=1.0, backoff_factor=1.0, max_interval=1.0,
                      max_attempts=2, jitter=True, retry_on=ConnectionError)
# prepare → call_service(retry_policy=limited) 그래프를 같은 방식으로 구성
try:
    limited_retry_graph.invoke({"query": "배송 현황"})
except ConnectionError as error:
    print("최대 시도 횟수 후 실행 실패:", error)
print(retry_count)
```
(그래프 구성 코드는 앞 단계와 같아 생략)
- 기대 결과는 실패 메시지가 나오고 `prepare=1`, `call_service=2`이다.
- (기록상 이상) 저장된 출력은 `call_service 시도 3`과 `{'prepare': 2, 'call_service': 3}`로 실패 메시지 없이 끝나 설명과 맞지 않는다. 카운터 초기화 셀과 실행 순서가 꼬인 상태의 출력으로 보인다.

## RetryPolicy 실습 4단계: 재시도하지 않을 오류 구분
요청 형식이 잘못되어 몇 번을 다시 해도 안 되는 오류는 재시도하면 안 된다. `retry_on=ConnectionError` 정책을 건 노드에서 `ValueError`를 내면 바로 실패한다.
```python
permanent_count = {"attempts": 0}

def reject_invalid_input(state: RetryState):
    permanent_count["attempts"] += 1
    raise ValueError("잘못된 요청 형식")

pb = StateGraph(RetryState)
pb.add_node("validate", reject_invalid_input, retry_policy=retry_policy)
pb.add_edge(START, "validate")
pb.add_edge("validate", END)
permanent_graph = pb.compile()

try:
    permanent_graph.invoke({"query": "잘못된 요청"})
except ValueError as error:
    print(f"실행 실패: {error}")
print("총 시도 횟수:", permanent_count["attempts"])   # 1
```
- 노드가 예외 없이 `{"status": "failed"}`처럼 정상 반환하면 `RetryPolicy`는 동작하지 않는다.

## RetryPolicy와 with_retry·with_fallbacks 비교
LangGraph·LangChain의 재시도·대체 방식은 적용 단위가 다르다.
- `RetryPolicy`: 노드 단위로 다시 실행
- `with_retry()`: Runnable(모델·체인) 단위로 다시 실행
- `with_fallbacks()`: 지정한 다른 모델이나 체인으로 바꿔 실행

재시도는 실패할 수 있고 다시 돌려야 하는 **가장 작은 단위**에 건다. 노드 전체를 다시 해야 하면 `RetryPolicy`, 노드 안의 모델 호출만 다시 하면 되면 `model.with_retry()`를 쓴다.

## Checkpoint 재개와 super-step 개념
자동 재시도로도 해결되지 않아 실행이 실패한 뒤에는, 원인을 고치고 같은 `thread_id`로 `invoke(None, config)`를 부르면 저장된 실행을 이어 간다. `None`은 새 입력이 없다는 뜻이고, 재개할 노드는 checkpoint의 `next`로 확인한다.

super-step은 같은 차례에 실행되도록 예정된 노드들의 묶음이다. checkpointer가 있으면 super-step이 끝날 때마다 State가 checkpoint로 저장된다.
```text
순차: prepare → call_service → finish
병렬: prepare → [stable_branch, unstable_branch] → summarize
```
- 순차 실행은 노드마다 다른 super-step이라 노드마다 checkpoint가 생긴다.
- 병렬 실행에서 대괄호 안 두 노드는 같은 super-step이라 둘 다 끝난 뒤 checkpoint가 생긴다.

## Checkpoint 재개 실습 1단계: 실패 gate가 있는 순차 그래프
gate가 `False`면 서비스 노드가 연결 오류를 내고 `True`면 정상 처리한다. 반복 실험 시 초기화 셀부터 다시 돌린다.
```python
class SequentialState(TypedDict):
    request: str
    prepared: str
    response: str

sequential_count = {"prepare": 0, "call_service": 0}
sequential_gate = {"allow_service": False}

def sequential_prepare(state):
    sequential_count["prepare"] += 1
    return {"prepared": state["request"].strip()}

def sequential_call_service(state):
    sequential_count["call_service"] += 1
    if not sequential_gate["allow_service"]:
        raise ConnectionError("서비스 연결 실패")
    return {"response": f"처리 완료: {state['prepared']}"}

# START → prepare → call_service → END 로 연결
sequential_graph = sb.compile(checkpointer=InMemorySaver())
sequential_config = {"configurable": {"thread_id": "fault-sequential-1"}}
```
(Edge 등록 코드는 줄여 옮김)

## Checkpoint 재개 실습 2단계: 실패 후 저장 상태 확인과 재개
실패 직후 `get_state()`를 보면 `prepare` 결과는 저장돼 있고 `next`가 `call_service`다. gate를 열어 연결 복구를 흉내 낸 뒤 `invoke(None, config)`로 재개한다.
```python
try:
    sequential_graph.invoke({"request": "주문 확인"}, sequential_config)
except ConnectionError as error:
    print("실행 실패:", error)   # 서비스 연결 실패

snap = sequential_graph.get_state(sequential_config)
print(snap.values)  # {'request': '주문 확인', 'prepared': '주문 확인'}
print(snap.next)    # ('call_service',)

sequential_gate["allow_service"] = True        # 문제 해결
result = sequential_graph.invoke(None, sequential_config)
print(result["response"])   # 처리 완료: 주문 확인
print(sequential_count)     # {'prepare': 1, 'call_service': 2}
```
- 끝난 `prepare`는 반복하지 않고, 실패한 `call_service`만 처음부터 다시 실행됐다.

## Checkpoint 재개는 누가 요청하나: 사용자와 worker
LangGraph checkpoint 재개 요청은 사용자나 프로그램이 보낼 수 있다.
- 사용자 요청: "다시 시도" 버튼을 누르면 서버가 그 작업을 재개한다.
- 자동 재개: 실패한 작업을 기록해 두고 일정 시간 뒤 worker(백그라운드 작업 실행 프로그램)가 재개한다.

어느 쪽이든 실제 재개는 같은 `thread_id`로 `invoke(None, config)`를 호출해 시작한다. 자동 재개라면 재개할 오류 종류, 대기 시간, 최대 횟수를 정하고 같은 작업이 동시에 돌지 않게 관리해야 한다.

## Checkpoint 재개 실습 3단계: except 블록에서 대기 후 재개
연결 실패 후 호출 코드가 잠시 기다렸다가 한 번 재개하는 상황이다. 그래프는 순차 재개 실습과 같은 구조(`auto_prepare`, `auto_call_service`, gate, 카운터)로 새로 만든다.
```python
import time

auto_config = {"configurable": {"thread_id": "delayed-resume-1"}}
try:
    auto_result = auto_graph.invoke({"request": "주문 확인"}, auto_config)
except ConnectionError as error:
    print("실행 실패:", error)
    print("2초 후 재개합니다.")
    time.sleep(5)
    auto_resume_gate["allow_service"] = True   # 연결 복구 가정
    auto_result = auto_graph.invoke(None, auto_config)

print("결과:", auto_result["response"])   # 처리 완료: 주문 확인
print("호출 횟수:", auto_resume_count)      # {'prepare': 1, 'call_service': 2}
```
(그래프 정의는 순차 재개 실습과 같아 생략)
- (원문 불일치) 메시지와 설명은 "2초 후"인데 코드는 `time.sleep(5)`이다.
- 실제 연결 문제가 안 풀렸다면 재개 호출에서도 예외가 난다. 실서비스에서는 worker가 이 역할을 맡는다.

## Checkpoint 재개 실습 4단계: 병렬 분기 그래프 만들기
같은 super-step의 두 노드 중 하나만 실패하는 경우다. 성공한 결과는 보존되고 재개 시 실패 노드만 다시 돈다.
```python
class ParallelState(TypedDict):
    request: str
    prepared: str
    stable_result: str
    unstable_result: str
    summary: str

call_count = {"prepare": 0, "stable": 0, "unstable": 0}
failure_gate = {"allow_unstable": False}

def stable_branch(state):
    call_count["stable"] += 1
    return {"stable_result": f"검증 완료: {state['prepared']}"}

def unstable_branch(state):
    call_count["unstable"] += 1
    if not failure_gate["allow_unstable"]:
        raise ConnectionError("외부 서비스에 일시적으로 연결할 수 없습니다.")
    return {"unstable_result": f"조회 완료: {state['prepared']}"}

def summarize(state):
    return {"summary": f"{state['stable_result']} | {state['unstable_result']}"}

# prepare(카운트 후 request.strip())
# START → prepare → stable_branch, unstable_branch → summarize → END
parallel_graph = builder.compile(checkpointer=InMemorySaver())
```
(prepare와 Edge 등록은 주석으로 줄임)

## Checkpoint 재개 실습 5단계: 병렬 실패 상태 확인과 재개
LangGraph 병렬 실행에서 한 분기가 실패하면 `get_state()`의 `values`에 성공한 `stable_result`가 남고, `next`에는 다시 돌릴 `unstable_branch`만 표시된다. `tasks`의 `error`, `result`로 분기별 성공·실패를 본다.
```python
config = {"configurable": {"thread_id": "fault-parallel-1"}}
try:
    parallel_graph.invoke({"request": "주문 상태 확인"}, config)
except ConnectionError as e:
    print("실행 실패:", e)

snap = parallel_graph.get_state(config)
print(snap.next)   # ('unstable_branch',)
for task in snap.tasks:
    print(task.name, task.error, task.result)
# stable_branch None {'stable_result': '검증 완료: 주문 상태 확인'}
# unstable_branch ConnectionError(...) None

failure_gate["allow_unstable"] = True
result = parallel_graph.invoke(None, config)
print(result["summary"])  # 검증 완료: 주문 상태 확인 | 조회 완료: 주문 상태 확인
print(call_count)         # {'prepare': 1, 'stable': 1, 'unstable': 2}
```
- 재개 후 `get_state(config).next`는 `()`로, 더 실행할 노드가 없다.

## 자동 재시도와 checkpoint 재개 비교
LangGraph의 자동 재시도(`RetryPolicy`)와 checkpoint 재개는 다음처럼 다르다.
- 실행 범위: 재시도는 노드 하나를 다시 시도하고, 재개는 저장된 그래프 실행을 이어서 진행한다.
- 호출 코드가 그래프를 다시 불러야 하나: 재시도는 아니고, 재개는 `invoke(None, config)`로 다시 부른다.
- 필요한 설정: 재시도는 `RetryPolicy`, 재개는 checkpointer와 `thread_id`

둘을 함께 쓸 수 있다. 짧은 일시 오류는 제한된 횟수만큼 자동 재시도하고, 끝내 실패하면 나중에 checkpoint에서 재개한다.

## LangGraph TimeoutPolicy로 노드 실행 시간 제한
외부 서비스 응답이 늦을 때 `TimeoutPolicy(run_timeout=...)`로 노드 한 번 실행 시간을 제한한다. **비동기 노드에만 적용**된다. `NodeTimeoutError`를 재시도 대상으로 지정하면 새 시도마다 시간 제한이 다시 시작된다.
```python
import asyncio
from langgraph.errors import NodeTimeoutError
from langgraph.types import TimeoutPolicy

async def slow_service(state):
    await asyncio.sleep(3)   # 작업 3초, 제한 2초
    return {"response": "완료"}

tb = StateGraph(TimeoutState)   # TimeoutState: response: str
tb.add_node("slow_service", slow_service,
    timeout=TimeoutPolicy(run_timeout=2.0),
    retry_policy=RetryPolicy(initial_interval=1.0, backoff_factor=1.0,
        max_interval=1.0, max_attempts=2, jitter=False, retry_on=NodeTimeoutError))
# START → slow_service → END 후 compile
try:
    await timeout_graph.ainvoke({})
except NodeTimeoutError as error:
    print(error.node, error.kind)   # slow_service run
```
(카운터·시간 측정 코드는 줄여 옮김) 두 번 다 시간 초과로 실패했고 총 시도 2회, 경과 약 5초였다. (내 메모: 2초 제한 + 1초 대기 + 2초 제한으로 보임)

## TimeoutPolicy 시간 초과가 계속될 때 서비스 대응
LangGraph 노드가 재시도 후에도 계속 시간 초과면, 작업 성격에 맞게 대응한다.
- 실패 안내: "응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요"라고 알리고 재시도 버튼 제공
- 대체 처리: 다른 모델로 바꿔 응답
- 백그라운드 처리: 오래 걸려도 끝내야 하는 작업은 worker에 맡기고 완료 시 사용자에게 알림

`except`에서 단순히 출력하는 대신 사용자 응답을 만들거나 별도 처리를 요청하면 된다.

## LangGraph error_handler: 재시도 소진 후 실패 결과 남기기
노드 오류가 나면 먼저 `RetryPolicy`가 재시도 여부를 판단하고, 재시도 대상이 아니거나 횟수를 다 쓰면 등록한 `error_handler`가 실행된다. 이 함수는 `NodeError`에서 노드 이름(`error.node`)과 예외(`error.error`)를 읽고 `Command`로 State를 고치거나 다음 노드로 이동할 수 있다.
```python
from langgraph.errors import NodeError

class RecoveryState(TypedDict):
    status: str
    error_message: str

def failing_service(state):
    raise ConnectionError("서비스 연결 실패")

def service_error_handler(state, error: NodeError) -> Command:
    return Command(
        update={"status": "failed", "error_message": f"{error.node}: {error.error}"},
        goto="finalize",
    )

def finalize(state):
    return {"status": state["status"]}
```
(카운터·print는 빼고 옮김)

## error_handler 실습: 노드 등록과 실행 결과
LangGraph `add_node`에 `retry_policy`와 `error_handler`를 함께 건다. `call_service`에서 나가는 Edge는 없고, handler의 `goto`가 `finalize`로 보낸다.
```python
rb = StateGraph(RecoveryState)
rb.add_node(
    "call_service", failing_service,
    retry_policy=RetryPolicy(initial_interval=2.0, backoff_factor=2, max_interval=1.0,
                             max_attempts=2, jitter=False, retry_on=ConnectionError),
    error_handler=service_error_handler,
)
rb.add_node("finalize", finalize)
rb.add_edge(START, "call_service")
rb.add_edge("finalize", END)
recovery_graph = rb.compile()
print(recovery_graph.invoke({}))
```
```text
call_service 시도 1: 연결 실패
call_service 시도 2: 연결 실패
error_handler 실행: 실패 상태를 기록하고 finalize로 이동
finalize 실행: status=failed
{'status': 'failed', 'error_message': 'call_service: 서비스 연결 실패'}
```
- 예외가 호출 코드로 올라오지 않고, 실패 정보가 State에 남은 채 정상 종료한다.

## LangGraph set_node_defaults: 공통 노드 정책
여러 노드에 같은 재시도 정책과 오류 처리 함수를 걸 때 `StateGraph.set_node_defaults()`로 한 번에 지정한다. 노드에 직접 준 값이 공통 설정보다 우선한다.
```python
builder.set_node_defaults(
    retry_policy=RetryPolicy(max_attempts=3),
    error_handler=service_error_handler,
)
builder.add_node("call_api", call_api)  # 기본값: 최대 3번 시도
builder.add_node("validate", validate,
                 retry_policy=RetryPolicy(max_attempts=1))  # 1번만 시도
```
- 두 노드 모두 오류 처리는 `service_error_handler`를 쓴다.

## 중복 저장 방지와 멱등성(idempotency)
DB 저장이나 메시지 전송은 그래프 State 밖에 흔적을 남기는 작업(side effect)이다. checkpoint는 이미 한 외부 작업을 되돌리지 않고, 실패한 노드는 재개 시 처음부터 다시 실행되므로 오류 전에 끝난 저장 코드가 또 실행돼 중복 기록이 생길 수 있다.

**멱등성**은 같은 요청을 여러 번 처리해도 한 번 처리한 것과 결과가 같은 성질이다. 요청마다 붙이는 **멱등성 키**(예: `request_id`)로 이미 처리했는지 확인해 중복 저장을 막는다.

노트북 예제의 리스트·집합은 한 프로세스 안에서만 중복을 막는다. 실제 저장소에서는 저장 결과와 처리한 요청 ID를 함께(둘 다 기록되거나 둘 다 안 되게) 처리하거나, 외부 서비스의 멱등성 키 기능을 쓴다.

## 멱등성 실습: request_id로 중복 저장 막는 노드
저장 노드가 기록 후 응답 직전에 실패하게 만들고, 같은 `request_id`로 재개해 중복 저장이 없는지 본다.
```python
external_rows: list = []          # 외부 DB를 단순화
processed_request_ids: set = set()
save_gate = {"allow_completion": False}

def idempotent_save(state):
    rid = state["request_id"]
    if rid not in processed_request_ids:   # 처음 보는 요청만 저장
        external_rows.append({"request_id": rid, "content": state["content"]})
        processed_request_ids.add(rid)
    if not save_gate["allow_completion"]:
        raise ConnectionError("저장 후 응답을 받지 못했습니다.")
    return {"saved": True}

# SaveState(request_id, content, saved), START → save → END, InMemorySaver로 compile
```

## 멱등성 실습: 실패 후 재개해도 기록 1건 유지
LangGraph 저장 그래프를 실행하면 기록은 남았지만 응답 전에 실패한다. 연결을 복구하고 같은 thread로 재개해도 같은 `request_id`라 기록이 늘지 않는다.
```python
save_config = {"configurable": {"thread_id": "save-1"}}
try:
    save_graph.invoke({"request_id": "req-2026-001", "content": "주문 기록"}, save_config)
except ConnectionError:
    print(len(external_rows))   # 1
    save_gate["allow_completion"] = True
    print(save_graph.invoke(None, save_config)["saved"])  # True
    print(len(external_rows))   # 1 (중복 없음)
```
(State·그래프 정의는 주석으로 줄임)

## Fault Tolerance 실습 문제: 재시도 후 실패 결과 남기기
실습 문제: 외부 조회 서비스에 연결 오류가 계속 난다. 잠시 기다렸다 다시 요청하되, 세 번 시도해도 실패하면 실패 사유를 남기고 작업을 마무리하는 그래프를 만들고 출력으로 과정을 확인한다.

풀이 코드(노드와 오류 처리 함수):
```python
class State(TypedDict):
    status: str
    error_message: str
    is_success: bool

def practice_call_service(state: State):
    if state["is_success"]:
        return {"state": "success"}
    print("조회 시도 - 연결 실패")
    raise ConnectionError("외부 조회 서비스 연결 실패")

def service_error_handler(state: State, error: NodeError) -> Command:
    print("error_handler 실행: 실패 상태를 기록하고 finalize로 이동")
    return Command(
        update={"status": "failed", "error_message": f"{error.node}: {error.error}"},
        goto="finalize",
    )

def finalize(state: State):
    print("마무리 작업")
    return {}
```
- (원본 오타) 성공 분기의 `{"state": "success"}`는 State에 없는 키다. `{"status": "success"}`가 맞아 보인다. 실습은 실패 경로만 실행해 드러나지 않았다.

## Fault Tolerance 실습 문제 풀이: 그래프 구성과 실행 결과
풀이 코드. `max_attempts=3`, `retry_on=ConnectionError` 정책과 `error_handler`를 서비스 노드에 건다.
```python
builder = StateGraph(State)
builder.add_node(
    "practice_call_service", practice_call_service,
    retry_policy=RetryPolicy(initial_interval=2.0, backoff_factor=2.0, max_interval=1.0,
                             max_attempts=3, jitter=True, retry_on=ConnectionError),
    error_handler=service_error_handler,
)
builder.add_node("finalize", finalize)
builder.add_edge(START, "practice_call_service")
builder.add_edge("practice_call_service", "finalize")
builder.add_edge("finalize", END)
graph = builder.compile()
print(graph.invoke({"is_success": False}))
```
```text
조회 시도 - 연결 실패   (3회)
error_handler 실행: 실패 상태를 기록하고 finalize로 이동
마무리 작업
{'status': 'failed', 'error_message': 'practice_call_service: 외부 조회 서비스 연결 실패', 'is_success': False}
```
- 강의 예제와 달리 `practice_call_service → finalize` Edge도 등록해 성공 경로에서도 finalize로 가게 했다.

## Fault Tolerance 복습 Q&A
- Q. LangGraph `RetryPolicy`의 `max_attempts=3`은 재시도를 몇 번 한다는 뜻인가?
  A. 최초 실행을 포함해 최대 3번 시도한다. 즉 재시도는 최대 2번이다.
- Q. `retry_on=ConnectionError` 정책을 건 노드에서 `ValueError`가 나면?
  A. 재시도하지 않고 한 번에 실패해 예외가 호출 코드로 올라간다(`error_handler`가 있으면 그것이 실행된다).
- Q. 실패한 LangGraph 실행을 checkpoint에서 이어 가려면?
  A. 원인을 고친 뒤 같은 `thread_id` config로 `graph.invoke(None, config)`를 부른다. 끝난 노드는 건너뛰고 `next`의 노드부터 실행된다.
- Q. 병렬 super-step에서 한 분기만 실패하면 재개 시 무엇이 다시 실행되나?
  A. 실패한 분기만 다시 실행되고, 성공한 분기의 결과는 보존돼 재사용된다.
- Q. `TimeoutPolicy(run_timeout=...)`의 적용 조건은?
  A. 비동기(async) 노드에만 적용되며, `NodeTimeoutError`를 `retry_on`에 지정하면 시간 초과도 재시도할 수 있다.
- Q. 재개 시 외부 저장이 중복되는 문제는 어떻게 막나?
  A. 멱등성 키(`request_id` 등)로 이미 처리한 요청인지 확인해 다시 저장하지 않게 한다.
