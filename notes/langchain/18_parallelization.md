---
part: langchain
lesson: Parallelization
order: 18
source_type: ipynb
tags: [parallelization, langgraph, fan-out, fan-in, voting, operator-add, reducer, stream]
source: C:\Users\tnwls\aim-ai-agent\langchain_\18-parallelization.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Parallelization

## Parallelization 요약
Parallelization 레슨은 LangGraph에서 여러 노드를 동시에 실행하는 방법을 다룬다. Fan-out/Fan-in으로 문서를 세 관점에서 병렬 분석하고, 결과 순서 정렬, 여러 후보 중 하나를 고르는 Voting 패턴, 병렬 번역 실습을 한다.

## Parallelization이 필요한 이유
LangGraph Parallelization은 서로 독립적인 작업을 동시에 돌려 전체 시간을 줄인다. 예를 들어 한 문서를 법률·재무·기술 관점으로 각각 3초씩 분석하면 순차로는 9초, 병렬로는 약 3초 + 종합 시간이다.
```text
순차: 법률(3초) → 재무(3초) → 기술(3초) = 9초
병렬: 법률(3초) ─┐
      재무(3초) ─┼→ 종합 = 3초 + α
      기술(3초) ─┘
```
단, LLM 응답 내용과 병렬 결과가 합쳐지는 순서는 실행마다 달라질 수 있다. LangGraph는 이런 병렬 실행을 그래프 구조(한 노드에서 여러 엣지)로 표현한다. 실습 모델은 `ChatGoogleGenerativeAI(model="gemini-3.6-flash")`, API 키는 `.env` + `load_dotenv()`로 읽는다.

## LangGraph Fan-out/Fan-in 1단계: State와 분석 노드
LangGraph Fan-out/Fan-in에서 핵심은 State 필드에 `Annotated[list, operator.add]` 리듀서를 붙여, 병렬 노드들이 반환한 리스트를 하나로 누적하는 것이다.
```python
class AnalysisState(TypedDict):
    document: str
    analyses: Annotated[list, operator.add]  # 각 분석 결과가 누적됨
    summary: str

def legal_analysis(state):
    result = llm.invoke(f"다음 문서를 법률 관점에서 핵심 리스크 2가지를 분석해줘. 간결하게.\n\n{state['document']}")
    return {"analyses": [f"[법률] {result.text}"]}

# financial_analysis, technical_analysis도 같은 형태 (관점과 접두어만 [재무], [기술])

def summarize(state):
    all_analyses = "\n\n".join(state["analyses"])
    result = llm.invoke(f"다음 3가지 관점의 분석을 종합해서 3줄로 요약해줘:\n\n{all_analyses}")
    return {"summary": result.text}
```
(재무·기술 노드는 같은 구조라 주석으로 줄임. 원본은 노드마다 완료 print가 있다.)
- 리듀서가 없으면 같은 키를 여러 노드가 동시에 쓸 때 충돌한다 (내 메모: LangGraph는 이때 InvalidUpdateError를 낸다).

## LangGraph Fan-out/Fan-in 2단계: 병렬 엣지 연결
LangGraph Fan-out은 START에서 여러 노드로 엣지를 거는 것이고, Fan-in은 `add_edge`에 노드 이름 리스트를 넘겨 모두 끝난 뒤 다음 노드를 실행하는 것이다.
```python
gb = StateGraph(AnalysisState)
gb.add_node("legal_analysis", legal_analysis)
gb.add_node("financial_analysis", financial_analysis)
gb.add_node("technical_analysis", technical_analysis)
gb.add_node("summarize", summarize)

# Fan-out: START → 3개 분석 노드 (병렬)
gb.add_edge(START, "legal_analysis")
gb.add_edge(START, "financial_analysis")
gb.add_edge(START, "technical_analysis")
# Fan-in: 3개 노드가 모두 끝난 뒤 summarize
gb.add_edge(["legal_analysis", "financial_analysis", "technical_analysis"], "summarize")
gb.add_edge("summarize", END)
analysis_graph = gb.compile()
```
(변수명 `graph_builder`를 `gb`로 줄임.)
```text
START ─┬→ legal_analysis     ─┐
       ├→ financial_analysis ─┼→ summarize → END
       └→ technical_analysis ─┘
```

## LangGraph Fan-out/Fan-in 3단계: stream으로 실행과 시간 측정
LangGraph 병렬 그래프를 `stream_mode="updates"`로 돌리면 노드가 끝날 때마다 그 노드의 업데이트만 받는다. 예제 문서는 투자 유치, 경량 LLM, 저작권 논란, 고평가 지적이 담긴 AI 스타트업 기사다.
```python
start = time.perf_counter()
result = {"analyses": []}
for event in analysis_graph.stream({"document": document}, stream_mode="updates"):
    for node_name, update in event.items():
        print(f"[노드 완료] {node_name} -> {list(update.keys())}")
        if "analyses" in update:
            result["analyses"].extend(update["analyses"])
        if "summary" in update:
            result["summary"] = update["summary"]
print(f"소요 시간: {time.perf_counter() - start:.1f}초")
```
- 출력에는 Gemini AFC 경고가 노드 수만큼 찍히고, 세 분석 노드 완료 후 summarize가 실행된다(긴 출력이라 생략).

## LangGraph 병렬 결과 순서 정렬
LangGraph 병렬 노드 결과는 먼저 끝난 순서로 쌓이므로 순서가 중요하면 결과에 식별자를 넣고 후처리에서 정렬한다. 분석 노드가 `(순서, 내용)` 튜플을 반환하고 summarize에서 정렬한다.
```python
def ordered_legal(state):
    result = llm.invoke(f"다음 문서를 법률 관점에서 핵심 리스크 2가지를 분석해줘. 간결하게.\n\n{state['document']}")
    return {"analyses": [(0, f"[법률] {result.text}")]}
# ordered_financial은 (1, "[재무] ..."), ordered_technical은 (2, "[기술] ...")

def ordered_summarize(state):
    sorted_analyses = sorted(state["analyses"], key=lambda x: x[0])
    all_analyses = "\n\n".join(content for _, content in sorted_analyses)
    result = llm.invoke(f"다음 3가지 관점의 분석을 종합해서 3줄로 요약해줘:\n\n{all_analyses}")
    return {"summary": result.text}
```
(나머지 두 노드와 그래프 구성은 Fan-out/Fan-in 예제와 같아서 줄임. 노드 이름만 legal/financial/technical/summarize. 원본 셀은 출력이 저장돼 있지 않다.)

## LangGraph Voting 패턴이란
Voting 패턴은 한 질문에 여러 LLM 응답을 동시에 생성하고, 판정용(judge) LLM이 그중 최선을 고르는 패턴이다.
```text
START ─┬→ generate_1 ─┐
       ├→ generate_2 ─┼→ vote → END
       └→ generate_3 ─┘
```
- 같은 모델에 접근 방식이 다른 프롬프트를 줘서 다양한 답을 만들거나, 서로 다른 Gemini 모델을 동시에 호출할 수 있다.
- judge LLM은 후보 생성과 평가 기준을 분리해 객관적으로 판단하게 구성한다.
- 마케팅 카피, 코드 생성, 번역처럼 결과 품질 편차가 큰 작업에 쓴다.

## LangGraph Voting 1단계: 후보 생성 노드
Voting 패턴의 후보 생성 노드는 공통 함수 하나에 접근 방식(핵심 중심, 예시 중심, 비유 중심)만 바꿔 호출한다. 후보는 id와 답변을 담은 dict로 누적한다.
```python
creative_llm = ChatGoogleGenerativeAI(model=MODEL_NAME)
judge_llm = ChatGoogleGenerativeAI(model=MODEL_NAME)

class VotingState(TypedDict):
    question: str
    candidates: Annotated[list, operator.add]
    best_answer: str

def generate_candidate(question, candidate_id, approach):
    result = creative_llm.invoke(f"다음 질문에 {approach}으로 유용하게 답변해줘:\n\n{question}")
    return {"candidates": [{"id": candidate_id, "answer": result.text}]}

def generate_concise(state): return generate_candidate(state["question"], 0, "핵심 중심")
def generate_example(state): return generate_candidate(state["question"], 1, "구체적인 예시 중심")
def generate_analogy(state): return generate_candidate(state["question"], 2, "비유와 쉬운 설명 중심")
```

## LangGraph Voting 2단계: vote 노드와 그래프
Voting 패턴의 vote 노드는 후보들을 텍스트로 이어 붙여 judge LLM에 주고, Structured Output으로 가장 좋은 후보 id와 이유를 받는다.
```python
class VoteResult(BaseModel):
    best_id: int = Field(description="가장 좋은 답변의 ID (0부터 시작)")
    reason: str = Field(description="선택 이유")

def vote(state):
    candidates = state["candidates"]
    text = "".join(f"\n--- 후보 {c['id']} ---\n{c['answer']}\n" for c in candidates)
    result = judge_llm.with_structured_output(VoteResult).invoke(
        f"다음 질문에 대한 여러 답변 후보가 있다. 가장 정확하고 유용한 답변을 골라줘.\n\n"
        f"질문: {state['question']}\n\n후보 답변들:{text}\n\n가장 좋은 답변의 ID와 이유를 알려줘.")
    best = next(c for c in candidates if c["id"] == result.best_id)
    return {"best_answer": best["answer"]}
```
(후보 텍스트 조립을 join으로 줄임.)

## LangGraph Voting 3단계: 그래프 구성
Voting 패턴 그래프는 START에서 후보 생성 노드 세 개로 Fan-out하고, 세 노드가 모두 끝나면 vote 노드로 Fan-in한다.
```python
vb = StateGraph(VotingState)
nodes = {"generate_concise": generate_concise, "generate_example": generate_example,
         "generate_analogy": generate_analogy}
for name, fn in nodes.items():
    vb.add_node(name, fn)
    vb.add_edge(START, name)
vb.add_node("vote", vote)
vb.add_edge(list(nodes), "vote")
vb.add_edge("vote", END)
voting_graph = vb.compile()
```
(노드 등록을 dict 루프로 줄임.)

## LangGraph Voting 실행 결과
Voting 그래프에 "프로그래밍을 처음 배우는 사람에게 파이썬을 추천하는 이유를 설명해줘"를 넣어 `stream_mode="updates"`로 실행했다.
- 후보 생성 완료 순서는 0 → 2 → 1로, 정의 순서와 달랐다(병렬 완료 순서 비보장).
- judge가 후보 1(구체적인 예시 중심)을 골랐다. 이유는 C와 파이썬 코드 비교, 엑셀 자동화 같은 실생활 사례로 초보자에게 가장 직관적이라는 것이었다.
```text
[후보 0] 생성 완료
[후보 2] 생성 완료
[후보 1] 생성 완료
[투표 결과] 후보 1 선택 — ...
[노드 완료] vote -> ['best_answer']
```

## LangGraph 병렬 처리는 언제 쓰는가
LangGraph 병렬 처리는 작업들이 서로의 결과를 기다릴 필요가 없을 때 쓴다. 판단 기준은 "각 작업이 다른 작업의 결과 없이 시작할 수 있는가?"이다.
- 적합한 예: 한 문서를 여러 관점으로 분석 후 종합, 한 문장을 여러 언어로 번역, 여러 후보 답변 생성 후 선택.
- B가 A의 결과를 입력으로 쓰면 `A → B` 순서로 실행한다. 전체 중 독립 구간만 병렬화할 수도 있다.
- 작업 종류·개수가 미리 정해져 있고 그래프에서 따로 관리하려면 노드를 여러 개 연결한다. 같은 모델에 여러 입력을 보내고 결과만 받으면 되면 한 노드에서 `batch()`가 더 간단하다.

주의할 점:
- 병렬 요청이 많으면 API Rate Limit에 걸릴 수 있다(동적 병렬화와 실행 수 제한은 Orchestrator-worker 레슨에서 다룸).
- 완료 순서가 보장되지 않으므로 순서가 중요하면 식별자를 넣고 정렬한다.
- 전체 시간은 가장 오래 걸리는 작업보다 짧아질 수 없다.

## 병렬 번역 실습 문제
병렬 번역 실습 문제는 한 문장을 영어, 일본어, 스페인어로 동시에 번역하는 LangGraph 그래프를 처음부터 만드는 것이다. 완성 조건은 다음과 같다.
- 상태와 노드 함수를 직접 정의한다.
- 세 번역을 병렬로 실행하고 결과를 하나로 모은다.
- 결과를 영어, 일본어, 스페인어 순서로 출력한다.
- 같은 작업을 순차로 실행해 소요 시간을 비교한다.

## 병렬 번역 실습 풀이: State와 번역 노드
병렬 번역 실습 풀이(노트북에 작성된 내 풀이)는 언어별 노드가 `(언어, 번역문)` 튜플을 `operator.add` 리스트에 넣고, merge 노드가 한 문자열로 합친다.
```python
class State(TypedDict):
    text: str
    results: Annotated[list, operator.add]
    merge_text: str

def english_translater(state):
    response = llm.invoke(f"다음 문장을 영어로 번역해줘 {state['text']}. 번역된 문장만 응답해.")
    return {"results": [("영어", response.text)]}
# japanesse_translater → ("일본어", ...), spanish_translater → ("스페인", ...) 도 같은 형태

def merge_translate(state):
    return {"merge_text": "".join(f"{lang} - {text} \n" for lang, text in state["results"])}
```
(merge를 join으로 줄임. 원본은 f-string 안에 같은 종류 따옴표를 겹쳐 써서 Python 3.12 이상에서만 동작한다.)

## 병렬 번역 실습 풀이: 그래프 구성과 실행
병렬 번역 실습 풀이 그래프는 START에서 번역 노드 세 개로 Fan-out하고, 세 노드가 끝나면 `merge_translate`로 Fan-in한다.
```python
builder = StateGraph(State)
names = ["english_translater", "japanesse_translater", "spanish_translater"]
for name, fn in zip(names, [english_translater, japanesse_translater, spanish_translater]):
    builder.add_node(name, fn)
    builder.add_edge(START, name)
builder.add_node("merge_translate", merge_translate)
builder.add_edge(names, "merge_translate")
graph = builder.compile()
print(graph.invoke({"text": "안녕하세요 반갑습니다."})["merge_text"])
```
(노드 등록을 루프로 줄임. 원본은 노드와 엣지를 하나씩 등록했고, 마지막 노드에서 END로 가는 엣지는 없다.)
```text
영어 - Hello, nice to meet you.
일본어 - こんにちは、お会いできて嬉しいです。
스페인 - Hola, mucho gusto.
```

## 병렬 번역 실습 풀이에서 빠진 부분
병렬 번역 실습 풀이는 완성 조건 중 두 가지를 채우지 않았다.
- 순서 보장: 결과가 우연히 영어·일본어·스페인어 순으로 나왔을 뿐 정렬하지 않았다. (내 메모) 튜플에 순번을 넣고 `sorted(state["results"], key=lambda x: x[0])`로 정렬하면 된다.
- 순차 실행 시간 비교: 구현되지 않았다. (내 메모) 아래처럼 `time.perf_counter()`로 두 방식을 재면 된다.
```python
# (내 메모) 노트북에 없는 코드
import time
t = time.perf_counter(); graph.invoke({"text": "안녕하세요 반갑습니다."})
print("병렬", time.perf_counter() - t)
t = time.perf_counter()
for fn in (english_translater, japanesse_translater, spanish_translater):
    fn({"text": "안녕하세요 반갑습니다."})
print("순차", time.perf_counter() - t)
```

## Parallelization 복습 Q&A
- Q. LangGraph에서 병렬 노드 결과를 한 리스트에 모으려면 State를 어떻게 정의하나?
  A. 필드를 `Annotated[list, operator.add]`로 선언해, 각 노드가 반환한 리스트가 이어 붙게 한다.
- Q. LangGraph에서 여러 병렬 노드가 모두 끝난 뒤 다음 노드를 실행하는 Fan-in 코드는?
  A. `builder.add_edge(["a", "b", "c"], "summarize")`처럼 노드 이름 리스트를 넘긴다.
- Q. 병렬 결과의 순서가 중요할 때는 어떻게 하나?
  A. 결과에 `(순서, 내용)`처럼 식별자를 넣고 합치는 노드에서 정렬한다. 완료 순서는 보장되지 않는다.
- Q. Voting 패턴은 어떻게 동작하나?
  A. 접근 방식이 다른 프롬프트로 후보를 병렬 생성하고, judge LLM이 Structured Output(`best_id`, `reason`)으로 최선을 고른다.
- Q. 병렬화가 가능한지 판단하는 기준은?
  A. 각 작업이 다른 작업의 결과 없이 시작할 수 있는지다. 전체 시간은 가장 긴 작업보다 짧아지지 않는다.
