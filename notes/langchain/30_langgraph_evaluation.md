---
part: langchain
lesson: LangGraph Evaluation
order: 30
source_type: ipynb
tags: [langgraph, evaluation, langsmith, golden-set, llm-as-judge, openevals, agentevals, trajectory]
source: C:\Users\tnwls\aim-ai-agent\langchain_\30-langgraph-evaluation.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# LangGraph Evaluation

## LangGraph Evaluation 요약
LangGraph Evaluation 레슨은 금융 Supervisor Agent를 Golden set과 LangSmith Dataset으로 평가한다. 최종 답변은 LLM-as-judge(openevals)로, Tool 호출 기록(Trajectory)과 승인 절차는 agentevals와 직접 만든 평가 함수로 채점하고 Experiment 결과를 비교한다.

## LangGraph Agent 평가 흐름: Dataset, target, evaluator, Experiment
Agent 평가는 사용자 요청에 대한 최종 답변과 처리 과정을 기대값과 비교하는 작업이다. 흐름은 "입력과 기대값 준비 → Agent 실행 → 실제 결과 채점 → 실험 결과 비교"이다.
- Dataset: 입력과 기대값을 모아 둔 것. 예: "생활비에서 저축으로 10만 원 보내줘" → 올바른 계좌·금액으로 이체하고 완료를 안내해야 함.
- target: 입력으로 Agent를 실행하는 함수.
- evaluator: 실제 결과가 기대값을 충족하는지 채점하는 함수. 직접 만들거나 제공되는 것을 쓴다.
- Experiment: Dataset으로 평가한 실행 한 번. 실제 결과와 점수가 기록된다.

모델·프롬프트를 바꾼 뒤 같은 Dataset과 기준으로 다시 평가하면 개선 전후를 비교할 수 있다.

## LangGraph Agent 평가 환경 설정
LangGraph Agent 평가에는 `openevals`(LLM 채점)와 `agentevals`(실행 과정 채점)를 설치한다.
```bash
pip install openevals agentevals
```
- `.env`에 `LANGSMITH_API_KEY`와 `LANGSMITH_TRACING=true`가 있어야 한다. 코드에서는 `load_dotenv()` 후 `bool(os.getenv("LANGSMITH_API_KEY"))`로 설정 여부만 확인한다.
- 노트북은 `financial_agent_example` 폴더와 같은 위치에 두고 `sys.path.insert(0, "financial_agent_example")`로 불러온다.
```python
from agents.supervisor import create_supervisor_agent
import data_store

model = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
agent = create_supervisor_agent(model)
```
- 주요 import: `langsmith.Client, traceable`, `langgraph.types.Command`, `openevals.llm.create_llm_as_judge`, `openevals.prompts.CORRECTNESS_PROMPT`, `agentevals.trajectory.match.create_trajectory_match_evaluator`, `langchain_core.tracers.context.collect_runs`.

## LangGraph Agent 평가용 Golden set 만드는 원칙
Golden set은 입력과 그 입력에 기대하는 결과를 정리한 평가용 사례 모음이다. 기대 결과는 신뢰할 수 있는 자료나 업무 규칙을 근거로 정하고 사람이 검토한다. 답변 평가라면 정답 문장이나 반드시 들어갈 사실을, 과정 평가라면 필요한 Tool 호출·인자·금지 동작을 적는다.
- 정상 요청뿐 아니라 정보 부족, 처리 불가, 허용 범위 경계의 요청도 넣는다.
- 결과에 영향을 주는 데이터·초기 상태를 명시하고, 실행할 때도 같은 조건을 맞춘다.
- 포함해야 할 사실과 하면 안 되는 행동을 구체적으로 쓰되, 의미가 같은 표현은 허용한다.
- Agent나 LLM이 만든 답을 검토 없이 정답으로 쓰지 않는다.
- 수정 전후 비교에는 같은 사례와 평가 기준을 쓴다.

## LangGraph 금융 Agent 답변 평가 Golden set 사례
금융 Agent 답변 평가용 Golden set의 각 사례는 `case_id`, `inputs`(`question`, 승인 중단에 줄 `decisions`), `reference`(`answer_criteria`: 답변에 들어갈 사실)로 구성된다. 사례는 네 개다.
- `accounts`: "내 계좌 목록과 잔액을 보여줘." → 본인 계좌 3개와 잔액(생활비 1,431,800원, 저축 2,280,000원, 여행 자금 390,000원)을 정확히, 타인 계좌 없이 안내.
- `transfer_approve`: "생활비에서 저축으로 10만 원 보내줘." + `["approve"]` → 100,000원 이체 완료 안내. 잔액을 말하면 생활비 1,331,800원, 저축 2,380,000원.
- `transfer_reject`: 같은 질문 + `["reject"]` → 거절로 취소되어 돈이 이동하지 않았다고 안내, 완료라고 말하지 않음.
- `missing_amount`: "생활비에서 저축으로 돈 보내줘." → 금액을 되묻고 임의로 정하지 않음.
```python
cases = {case["case_id"]: case for case in golden_set}
```
(golden_set 리스트 정의는 위 내용을 dict로 적은 것이라 생략했다.)

## LangGraph Agent 평가 run_agent (1): 격리된 실행 준비
`run_agent(inputs)`는 사례마다 독립된 초기 데이터와 새 스레드에서 Agent를 실행한다. `@traceable`은 최초 실행과 승인 후 재개를 LangSmith에서 한 사례로 묶는다.
```python
@traceable(name="financial-supervisor-evaluation")
def run_agent(inputs):
    config = {"configurable": {"thread_id": str(uuid4())}, "recursion_limit": 40}
    context = {"owner_id": "user-001"}
    decisions = iter(inputs["decisions"])
    interrupt_tools, used_decisions = {}, []

    with TemporaryDirectory() as directory:
        bank_path = Path(directory) / "bank_data.json"
        copyfile(data_store.INITIAL_PATH, bank_path)
        with patch.object(data_store, "BANK_PATH", bank_path):
            result = agent.invoke({"messages": [("user", inputs["question"])]},
                                  config=config, context=context)
            # interrupt 처리 루프로 이어짐
```
(원본 함수를 둘로 나눠 적었다.)
- 새 `thread_id`: 이전 사례의 대화·승인 상태와 분리한다.
- 초기 데이터를 임시 폴더에 복사하고 `patch.object`로 블록 안에서만 데이터 경로를 바꿔, 모든 사례가 같은 잔액에서 시작한다.

## LangGraph Agent 평가 run_agent (2): 승인 interrupt 처리 루프
`run_agent`의 중간 부분은 결과에 `__interrupt__`가 있으면 준비한 결정을 `Command(resume=...)`로 전달해 같은 스레드에서 재개한다. (`with` 블록 안쪽 코드다.)
```python
            while result.get("__interrupt__"):
                interrupts = result["__interrupt__"]
                for item in interrupts:
                    interrupt_tools[item.id] = item.value.get("tool_name")
                pending = interrupts[0]
                decision = next(decisions, None)
                if decision is None:
                    break  # 준비한 결정이 없으면 승인 대기로 종료
                used_decisions.append(decision)
                result = agent.invoke(Command(resume={pending.id: decision}),
                                      config=config, context=context)
```
- 같은 중단은 ID별로 한 번만 센다(`interrupt_tools` dict의 key가 중단 ID).
- 결정을 다 쓰면 `break`로 빠져나가고, 승인 대기 상태가 남는다.

## LangGraph Agent 평가 run_agent (3): 반환값과 answer_target
`run_agent`의 마지막 부분은 최종 답변과 승인 상태를 dict로 반환한다. 승인 대기가 남았으면 답변은 빈 문자열이다. 답변 평가용 `answer_target`은 그중 `answer`만 넘긴다.
```python
    approval_pending = bool(result.get("__interrupt__"))
    return {
        "answer": "" if approval_pending else result["messages"][-1].text,
        "approval": {"interrupt_count": len(interrupt_tools),
                     "tool_names": list(interrupt_tools.values()),
                     "used_decisions": used_decisions, "pending": approval_pending},
    }

def answer_target(inputs):
    return {"answer": run_agent(inputs)["answer"]}
```
- `approval`에는 중단 수, 중단 대상 Tool 이름, 사용한 결정, 대기 여부가 담겨 승인 절차 평가에 쓰인다.

## LangGraph Agent 최종 답변 평가: create_llm_as_judge
openevals의 `create_llm_as_judge()`는 LLM이 채점하는 평가 함수를 만든다. 다른 표현이어도 의미가 맞으면 통과할 수 있지만, LLM 판단이므로 점수와 근거(comment)를 함께 본다.
```python
answer_judge = create_llm_as_judge(
    prompt=CORRECTNESS_PROMPT,     # 정확성 평가 지침
    judge=model,                   # 채점 LLM
    feedback_key="answer_correct", # 점수 항목 이름
)

def evaluate_answer(inputs, outputs, reference_outputs):
    return answer_judge(
        inputs=inputs["question"],
        outputs=outputs["answer"],
        reference_outputs=reference_outputs["answer_criteria"],
    )
```
`transfer_approve` 사례 실행 결과 답변은 "생활비(acc-001)에서 저축(acc-002)으로 100,000원 이체 완료, 생활비 잔액 1,331,800원"이었고, 채점 결과는 다음과 같았다.
```text
{'key': 'answer_correct', 'score': True, 'comment': 'The model output accurately confirms the transfer ...'}
```
- Gemini의 AFC 관련 경고가 함께 출력됐지만 결과에는 영향이 없었다.

## LangSmith Dataset과 Example, Experiment
LangSmith Dataset은 LangSmith에 저장해 평가에 쓰는 사례 모음이고, 개별 사례를 Example이라 한다. Example은 `inputs`(입력), `outputs`(기대 출력), `metadata`(사례 식별 정보 등)를 담는다. `outputs`에는 Agent의 실제 답변이 아니라 비교 기준인 기대값을 저장한다.
```python
client = Client()
answer_dataset = client.create_dataset(dataset_name=f"financial-answer-{uuid4().hex[:8]}")
client.create_examples(
    dataset_id=answer_dataset.id,
    examples=[{"inputs": c["inputs"], "outputs": c["reference"],
               "metadata": {"case_id": c["case_id"]}} for c in golden_set],
)
```
- 실행할 때마다 새 이름의 Dataset이 생긴다(예: `financial-answer-d41b03cc`, 사례 4개).
- 수정 전후 비교에는 같은 Dataset을 써야 하므로, 커널 재시작 후에는 `client.read_dataset(dataset_name="기존 이름")`으로 불러온다.

## LangSmith client.evaluate로 답변 평가 Experiment 실행
LangSmith `client.evaluate()`에 target, Dataset, evaluators를 넘기면 Dataset 전체로 Experiment를 실행한다.
```python
answer_experiment = client.evaluate(
    answer_target,
    data=answer_dataset.id,
    evaluators=[evaluate_answer],
    experiment_prefix="answer-only",
    metadata={"model": MODEL_NAME},
)
```
평가 함수 인자 이름은 필요한 것만 선언하되 다음 이름에 맞춘다.
- `inputs`: Dataset의 입력
- `outputs`: target이 반환한 실제 결과
- `reference_outputs`: Dataset `outputs`에 저장한 기대값

반환 형식은 `{"key": "answer_correct", "score": True, "comment": "..."}`이다. 실행하면 LangSmith 실험 링크가 출력되고(4건, 약 50초), 실험마다 Dataset 전체를 새로 실행하므로 답변·점수는 매번 달라질 수 있다.

## LangSmith에서 답변 평가 결과 확인할 점
LangSmith의 `answer-only` Experiment에서는 사례별 입력, 기대값, 실제 답변, `answer_correct` 점수를 비교하고, 평가 근거를 읽어 빠지거나 틀린 사실을 찾는다. 실행 오류나 평가 오류로 점수가 없는 경우는 실패 점수와 구분한다.

한계: `answer_correct`는 최종 답변만 채점하고 Tool 사용과 승인 절차는 보지 않는다. 이체 완료·취소를 맞게 안내했더라도 실제로 올바르게 처리됐는지는 Trajectory 평가로 따로 확인해야 한다.

## LangGraph Agent Trajectory 평가와 Golden set 구조
Trajectory는 Agent의 실행 기록이며, 최종 답변만으로 알기 어려운 Tool 호출·인자, 승인·거절 절차를 평가한다. Trajectory Golden set의 `reference`에는 `answer_criteria`에 더해 다음을 적는다.
- `expected_calls`: 필수 Tool 이름(`name`)과 핵심 인자(`args`) 목록. `args={}`이면 이름만 비교.
- `allowed_tools`: 실행이 허용되는 Tool 목록.
- `expected_interrupts`: 기대 승인 중단 횟수.
- `expected_interrupt_tools`: 승인 중단 대상 Tool 이름 목록.

필수 Tool과 허용 Tool은 구분한다. 필요한 Tool이 다 실행됐어도 허용하지 않은 Tool이 추가로 실행됐을 수 있기 때문이다.

## LangGraph 금융 Agent Trajectory Golden set 사례
금융 Agent Trajectory 사례별 기대 처리 과정은 다음과 같다.
- `accounts`: 필수 `run_transfer_agent`, `lookup_accounts`. 허용도 이 둘. 중단 0회.
- `transfer_approve`: 필수 `run_transfer_agent`, `lookup_accounts`, 그리고 `transfer_money`(acc-001 → acc-002, 100000). 허용에 `transfer_money` 포함. `transfer_money` 중단 1회.
- `transfer_reject`: 필수 `run_transfer_agent`, `lookup_accounts`. 허용에 `transfer_money` 없음(실행되면 안 됨). `transfer_money` 중단 1회.
- `missing_amount`: 필수 호출 없음. 허용은 `run_transfer_agent`, `lookup_accounts`. 중단 0회.
```python
{"name": "transfer_money",
 "args": {"from_account_id": "acc-001", "to_account_id": "acc-002", "amount": 100000}}
```
- 위는 `transfer_approve`의 `expected_calls` 항목 하나다.

## LangGraph Agent Trajectory 평가: collect_runs로 Tool 실행 기록 수집
`trajectory_target()`은 `collect_runs()` 안에서 `run_agent()`를 실행해 실제 Tool 실행 기록을 `tool_calls`로 덧붙인다(거절 시 middleware가 실행을 막으므로 요청이 아닌 실행 기록을 본다). 하위 Agent 기록이 중첩되어 `child_runs`를 재귀로 따라간다.
```python
def recorded_tools(roots):
    runs = {}
    def visit(run):
        runs[run.id] = run
        for child in run.child_runs:
            visit(child)
    for root in roots:
        visit(root)
    tools = [r for r in runs.values() if r.run_type == "tool"]
    return sorted(tools, key=lambda r: r.start_time)

def trajectory_target(inputs):
    with collect_runs() as traces:
        result = run_agent(inputs)
    result["tool_calls"] = [
        {"id": str(run.id), "name": run.name,
         "args": {k: v for k, v in run.inputs.items() if k != "runtime" and v is not None}}
        for run in recorded_tools(traces.traced_runs)
    ]
    return result
```
(원본 for 루프를 컴프리헨션으로 줄였다. `runtime`과 None 인자는 비교에서 뺀다.)

## agentevals trajectory_match_mode 종류
AgentEvals는 Agent 실행 과정을 평가하는 라이브러리이고, `create_trajectory_match_evaluator()`로 호출 기록을 규칙대로 비교하는 평가 함수를 만든다. `trajectory_match_mode`는 비교 방식이다.
- `strict`: 기대 호출과 순서까지 일치.
- `unordered`: 순서는 달라도 호출들이 일치.
- `subset`: 기대 기록 안의 호출만 허용(일부 생략 가능).
- `superset`: 기대 호출이 모두 포함돼야 하고 추가 호출은 허용.

인자 비교는 `tool_args_match_mode`로 따로 정한다(`superset`, `ignore` 등). 필수 Tool 평가는 필요한 조회·이체가 있는지 보면서 추가 조회는 허용해야 하므로 둘 다 `superset`을 쓴다.

## agentevals 필수 Tool·인자 평가 (superset)
agentevals 평가 함수는 메시지 형식을 받으므로, Tool 기록을 `tool_calls`가 담긴 `AIMessage`로 바꿔 넘긴다.
```python
required_match = create_trajectory_match_evaluator(
    trajectory_match_mode="superset",
    tool_args_match_mode="superset",
)

def as_messages(tool_calls):
    return [AIMessage(content="", tool_calls=[{"id": str(i), **call}])
            for i, call in enumerate(tool_calls)]

def evaluate_required_tools(outputs, reference_outputs):
    return required_match(
        outputs=as_messages(outputs["tool_calls"]),
        reference_outputs=as_messages(reference_outputs["expected_calls"]),
    )
```
```text
{'key': 'trajectory_superset_match', 'score': True, 'comment': None, 'metadata': None}
```
- 인자도 `superset`이라 기대한 계좌·금액이 실제 인자에 포함되면 통과하고, 추가 인자는 허용한다.

## agentevals 허용 Tool 평가 (subset)
agentevals `superset`은 필수 호출이 있는지만 보므로, 거절 사례에서 금지된 `transfer_money`가 추가 실행돼도 통과해 버린다. 그래서 허용 범위 밖 호출이 없는지 `subset`으로 따로 검사한다.
```python
allowed_match = create_trajectory_match_evaluator(
    trajectory_match_mode="subset",
    tool_args_match_mode="ignore",
)

def evaluate_allowed_tools(outputs, reference_outputs):
    actual_names = {call["name"] for call in outputs["tool_calls"]}  # 반복 호출은 하나로
    actual_calls = [{"name": n, "args": {}} for n in actual_names]
    allowed_calls = [{"name": n, "args": {}} for n in reference_outputs["allowed_tools"]]
    return allowed_match(outputs=as_messages(actual_calls),
                         reference_outputs=as_messages(allowed_calls))
```
- 결과 key는 `trajectory_subset_match`. 거절 사례에서 `transfer_money`가 실행되면 False가 된다.
- `as_messages`는 Tool 기록을 `AIMessage(tool_calls=...)` 목록으로 바꾸는 helper다.

## LangGraph Agent 승인 절차 평가 함수 evaluate_approval
`evaluate_approval()`은 승인 중단 횟수, 중단 대상 Tool, 사용한 결정, 남은 승인 대기를 직접 비교하는 평가 함수다. 승인·거절 사례는 `transfer_money` 중단을 한 번 거쳐야 하고, 조회·금액 누락 사례는 중단 없이 끝나야 한다.
```python
def evaluate_approval(inputs, outputs, reference_outputs):
    approval = outputs["approval"]
    passed = (
        approval["interrupt_count"] == reference_outputs["expected_interrupts"]
        and approval["tool_names"] == reference_outputs["expected_interrupt_tools"]
        and approval["used_decisions"] == inputs["decisions"]
        and not approval["pending"]
    )
    return {"key": "approval_flow", "score": passed,
            "comment": f"중단 횟수: {approval['interrupt_count']}, 중단 대상: {approval['tool_names']}, "
                       f"사용한 결정: {approval['used_decisions']}, 승인 대기: {approval['pending']}"}
```
(comment 문자열의 기대값 표기는 줄였다.)
- 승인 사례 결과: `approval_flow` True, 중단 1회, 대상 `['transfer_money']`, 결정 `['approve']`, 대기 False.

## LangSmith Trajectory 평가 Dataset과 Experiment 실행
Trajectory 평가용 Dataset은 답변 Dataset과 같은 방식으로 만들되 `trajectory_golden_set`을 등록한다(`outputs`에 답변·Tool·승인 기대값). 이름은 `financial-trajectory-<8자리>`, 사례 4개.
```python
trajectory_experiment = client.evaluate(
    trajectory_target,
    data=trajectory_dataset.id,
    evaluators=[evaluate_answer, evaluate_required_tools,
                evaluate_allowed_tools, evaluate_approval],
    experiment_prefix="with-trajectory",
    metadata={"model": MODEL_NAME},
)
```
LangSmith `with-trajectory` Experiment에서 볼 점수와 실패 시 확인할 내용:
- `answer_correct`: 이체 결과를 잘못 안내하거나 정보를 빠뜨렸나?
- `trajectory_superset_match`: 필요한 호출이 없거나 계좌·금액이 다른가?
- `trajectory_subset_match`: 거절 사례에서 이체 Tool이 실행됐나?
- `approval_flow`: 승인 생략, 잘못된 중단 대상, 안 쓴 결정, 남은 대기가 있나?

Trace에서 `evaluate_answer` 아래 모델 호출은 Agent가 아니라 채점자 실행 기록이다.

## LangSmith Experiment 결과를 노트북에서 읽기
LangSmith Experiment 객체를 순회하면 사례별 실행 오류와 점수를 읽을 수 있다. `True`/`1`은 통과, `False`/`0`은 실패이고, 점수가 없거나 평가 오류면 "미채점"으로 표시해 통과로 치지 않는다.
```python
score_keys = ["answer_correct", "trajectory_superset_match",
              "trajectory_subset_match", "approval_flow"]
for row in trajectory_experiment:
    example = row["example"]
    print((example.metadata or {}).get("case_id", str(example.id)))
    print("실행 오류:", row["run"].error or "없음")
    feedback = {item.key: item for item in row["evaluation_results"]["results"]}
    for key in score_keys:
        item = feedback.get(key)
        if item is None:
            print(f"{key}: 미채점 (평가 결과 없음)")
        elif item.score is None or (item.extra or {}).get("error"):
            print(f"{key}: 미채점 ({item.comment or '점수 없음'})")
        else:
            print(f"{key}: {item.score}")
```
- 실행 결과 네 사례 모두 실행 오류 없이 네 점수 전부 True였다.

## LangGraph Agent 승인·거절 Trajectory 비교
같은 이체 질문에 승인과 거절을 각각 전달하면 최종 답변과 실행 Tool이 달라진다. 두 사례는 각자 초기 데이터와 별도 스레드에서 실행한다.
```python
comparison_results = {
    "transfer_approve": trajectory_result,
    "transfer_reject": trajectory_target(trajectory_cases["transfer_reject"]["inputs"]),
}
for case_id, output in comparison_results.items():
    tool_names = sorted({call["name"] for call in output["tool_calls"]})
    print(case_id, ", ".join(tool_names))
```
(원본은 답변과 `evaluate_approval` 결과도 함께 출력한다. 출력 줄을 줄였다.)
- 승인: 이체 완료 안내, 실행 Tool `lookup_accounts, run_transfer_agent, transfer_money`.
- 거절: 거절되어 취소됐다고 안내, 실행 Tool `lookup_accounts, run_transfer_agent`(이체 없음).
- 두 경우 모두 중단 1회를 거쳐 준비한 결정을 썼으므로 `approval_flow`는 True.
- Tool 목록은 중복 제거한 이름이라 순서·횟수는 나타내지 않는다.

## agentevals 실패 점수 해석: 금액이 다른 이체 기록
agentevals 채점 연습으로, `transfer_approve`의 기대 호출을 `deepcopy`한 뒤 `transfer_money`의 `amount`만 200000으로 바꾼 가짜 기록을 평가한다.
```python
from copy import deepcopy

sample_reference = trajectory_cases["transfer_approve"]["reference"]
sample_calls = deepcopy(sample_reference["expected_calls"])  # 기대값 원본 보호
for call in sample_calls:
    if call["name"] == "transfer_money":
        call["args"]["amount"] = 200000
sample_outputs = {"tool_calls": sample_calls}
print(evaluate_required_tools(sample_outputs, sample_reference))
print(evaluate_allowed_tools(sample_outputs, sample_reference))
```
- `trajectory_superset_match`: False. `transfer_money`는 호출됐지만 금액 100000 ≠ 200000.
- `trajectory_subset_match`: True. 인자를 무시하고 Tool 이름만 보며, 이름은 모두 허용 목록에 있다.

허용 Tool 평가를 통과해도 올바른 계좌·금액으로 실행했는지는 필수 Tool·인자 평가에서 따로 확인해야 한다. 실패하면 점수와 실행 기록으로 원인을 찾고 모델·프롬프트·코드를 고친 뒤 같은 Dataset과 기준으로 다시 비교한다.

## LangGraph Evaluation 실습 과제
LangGraph Evaluation 실습 과제는 각자 만든 금융 Agent에서 기능 2~3개를 골라 평가용 Dataset(Golden set)과 평가 함수를 만들고 평가해 보는 것이다. 노트북에는 과제 설명만 있고 풀이는 없다.

(내 메모) 진행 순서 예시: 기능별로 정상·정보 부족·거절 사례를 `inputs`/`reference`로 적고 → `client.create_dataset` + `create_examples`로 등록 → 답변은 `create_llm_as_judge`, Tool 호출은 `create_trajectory_match_evaluator`의 superset/subset으로 평가 → `client.evaluate`로 Experiment 실행.

## LangGraph Evaluation 복습 Q&A
- Q. LangSmith 평가에서 target과 evaluator의 역할은?
  A. target은 Dataset 입력으로 Agent를 실행해 결과를 반환하고, evaluator는 그 결과를 기대값과 비교해 점수(`key`, `score`, `comment`)를 낸다.
- Q. LangSmith Dataset Example의 `outputs`에는 무엇을 넣나?
  A. Agent의 실제 답변이 아니라 비교 기준이 되는 기대값(reference)을 넣는다.
- Q. agentevals에서 `superset`과 `subset` 평가를 둘 다 쓰는 이유는?
  A. `superset`은 필수 호출이 다 있는지만 보고 추가 호출은 허용하므로, 금지 Tool 실행을 잡으려면 허용 범위만 보는 `subset`이 따로 필요하다.
- Q. 최종 답변 평가(`answer_correct`)만으로 충분하지 않은 이유는?
  A. 답변 문장만 채점하므로 실제 Tool 실행, 인자, 승인 절차가 올바른지는 알 수 없다.
- Q. Trajectory 수집에서 모델의 tool call 요청 대신 Tool 실행 기록(`collect_runs`)을 쓰는 이유는?
  A. 거절 시 middleware가 실행을 막으므로, 요청이 아니라 실제로 실행된 Tool을 봐야 승인·거절의 실제 동작을 평가할 수 있다.
