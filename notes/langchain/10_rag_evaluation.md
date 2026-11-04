---
part: langchain
lesson: RAG 평가
order: 10
source_type: ipynb
tags: [rag-evaluation, hit-at-k, recall-at-k, mrr, ragas, faithfulness, llm-as-judge]
source: C:\Users\tnwls\aim-ai-agent\langchain_\10-rag-evaluation.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# RAG 평가

## RAG 평가 요약
사내 규정 50문항 평가 데이터셋으로 Similarity, MMR, BM25, Hybrid 검색을 같은 조건에서 비교하고(Hit@k, Precision@k, Recall@k, MRR, latency), 생성된 답변은 인용 규칙 검사, RAGAS, 직접 정의한 LLM-as-Judge로 따로 평가한다.

## RAG 평가가 필요한 이유와 평가 방법 종류
RAG 평가는 청크 크기, 검색 문서 수 k, 검색 전략, 프롬프트를 고를 근거를 만든다. 대표 질문 몇 개를 눈으로 보는 것은 질문이 많아지면 느리고 주관적이다. 평가는 한 도구에만 의존하지 않는다.
- 수동 확인: 대표 질문과 답변을 직접 읽는다. 초기 개발·빠른 검증용.
- 검색 지표: Hit@k, Precision@k, Recall@k, MRR. 검색 설정 비교용.
- RAGAS: LLM으로 답변의 근거성·관련성을 평가. 파이프라인 비교용.
- LLM-as-Judge: 도메인 기준을 직접 정의. 규정 답변의 정확성·완전성 평가용.
- 사용자 피드백: 실제 반응 수집. 서비스 운영용.

## RAG 평가 순서: 검색 먼저, 답변은 나중
RAG 평가는 검색 실패와 답변 생성 실패를 구분하려고 검색 평가부터 한다.
- 검색: 정답 규정을 찾았는가 → Hit@k, Precision@k, Recall@k, MRR
- 답변: 근거를 빠짐없이 썼는가 → 직접 정의한 LLM-as-Judge
- 근거성: 검색 문서에 없는 내용을 만들지 않았는가 → 인용 검사, RAGAS
- 운영: 응답 시간이 적절한가 → latency

흐름: 질문과 정답 문서 → 검색기 실행 → Hit@k·Recall@k·MRR → 답변 생성 → 인용 검사·RAGAS·LLM-as-Judge. 검색 평가는 `question`, `relevant_sources`, 검색 결과만 있으면 되고, 답변 평가는 `retrieved_contexts`, `response`, `reference`가 추가로 필요하다.

## RAG 평가 데이터셋 구성
RAG 평가 데이터셋은 질문, 기대 정답, 정답 문서를 사람이 미리 정리한 기준 데이터다. 한 레코드는 네 필드로 구성할 수 있고, 메트릭마다 필요한 필드만 쓴다.
- `user_input`: 사용자 질문 (직접 작성)
- `reference`: 기대 정답 (직접 작성)
- `retrieved_contexts`: 검색된 문서 내용 (검색기 실행으로 채움)
- `response`: LLM 답변 (RAG 파이프라인 실행으로 채움)

`eval_qa_50.json`은 easy·medium·hard를 섞었다. 쉬운 질문만 쓰면 점수가 과하게 높고, 어려운 질문만 쓰면 기본 검색 문제와 복수 문서 검색 문제를 구분하기 어렵다. 검색기는 청크를 반환하지만 정답은 규정 파일 단위이므로, 청크의 `source`가 정답 파일 목록에 들어 있는지로 판정한다.

## RAG 평가 실습 1단계: 패키지 설치와 모델 준비
RAG 평가 실습은 RAGAS 0.4.3을 쓰는데 최신 `langchain-community`와 호환 문제가 있어 버전을 고정해 설치하고 커널을 재시작한다. Gemini API 키는 `.env`에서 `load_dotenv()`로 읽는다.
```bash
pip install "ragas==0.4.3" "langchain-community==0.4.1" "instructor[google-genai]==1.15.4"
```
```python
load_dotenv()
embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
```
- import는 json, time, Path, chromadb, Kiwi, Chroma, BM25Retriever, TextLoader, EnsembleRetriever, splitter, pydantic(BaseModel, Field)를 쓴다.

## RAG 평가 실습 2단계: 429 오류 대비 재시도 설정
RAG 평가처럼 임베딩 호출이 많으면 Gemini API의 429(Resource exhausted) 오류가 날 수 있다. `google.genai` 클라이언트에 지수 백오프 재시도 옵션을 넣어 임베딩 객체의 client로 교체한다.
```python
from google import genai
from google.genai.types import HttpOptions, HttpRetryOptions

retry_client = genai.Client(http_options=HttpOptions(
    retry_options=HttpRetryOptions(
        attempts=8,         # 최초 요청 포함 총 8회
        initial_delay=2.0,  # 첫 재시도 대기(초)
        max_delay=60.0,     # 최대 대기
        exp_base=2,         # 2→4→8→16초…
        jitter=1.0,         # 랜덤 지연으로 동시 재시도 분산
    )))
embeddings.client = retry_client
```

## RAG 평가 실습 3단계: 사내 규정 마크다운 청킹
RAG 평가 실습은 `data/company_rules/*.md`를 700/100으로 자르되 separators에 `"\n### "`를 맨 앞에 둬 마크다운 조항 경계에서 먼저 자른다. 청크마다 `source`와 `chunk_id`를 붙인다. (축약함)
```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=700, chunk_overlap=100, separators=["\n### ", "\n\n", "\n", " "])
documents = []
for path in sorted(Path("data/company_rules").glob("*.md")):
    loaded = TextLoader(path, encoding="utf-8").load()
    for doc in loaded:
        doc.metadata["source"] = path.name
    for i, chunk in enumerate(splitter.split_documents(loaded)):
        chunk.metadata["chunk_id"] = f"{path.stem}:{i}"
        documents.append(chunk)
```
- `"\n### "` separator를 맨 앞에 두면 조항 단위로 먼저 나뉘어 청크가 조항 경계를 덜 넘는다(내 메모).

## RAG 평가 실습 4단계: 기존 벡터 저장소 불러오기 또는 재생성
RAG 평가 실습은 앞선 검색 실습의 `company_rules_search_advanced` 컬렉션을 재사용한다. `LOAD_EXISTING_VECTORSTORE=True`면 기존 컬렉션에 연결하고(없으면 ValueError), False면 기존 컬렉션을 지우고 청크를 새로 임베딩해 저장한다. (축약함)
```python
client = chromadb.PersistentClient(path="./chroma_db")
if LOAD_EXISTING_VECTORSTORE:   # 없으면 ValueError
    vectorstore = Chroma(collection_name="company_rules_search_advanced",
                         embedding_function=embeddings, client=client)
else:                           # 기존 컬렉션 삭제 후 재생성
    vectorstore = Chroma.from_documents(documents, embeddings,
        collection_name="company_rules_search_advanced", client=client)
```
- 출력은 "규정 청크 77개를 새로 저장했습니다."(코드의 기본값은 True인데 출력은 재생성 경로라 실행 시점 값이 달랐던 것으로 보임).

## RAG 평가 실습 5단계: 평가 데이터 로드
RAG 평가 데이터 `eval_qa_50.json`을 읽고, 각 문항의 `source`(정답 규정 파일 목록)를 `relevant_sources` 키로 복사한다.
```python
eval_cases = json.loads((DATA_DIR / "eval_qa_50.json").read_text(encoding="utf-8"))
for case in eval_cases:
    case["relevant_sources"] = case["source"]
print(f"전체 문항: {len(eval_cases)}")   # 50
```
- 문항에는 `id`, `question`, `difficulty`, `expected_answer`, `source` 필드가 쓰인다(코드에서 사용하는 키 기준).

## RAG 평가 실습 6단계: 검색 전략 4종 준비
RAG 평가에서는 모든 검색 전략이 같은 문서와 같은 후보 수(FETCH_K=5)를 쓰게 맞춘다. Hybrid는 `EnsembleRetriever`로 벡터와 BM25 순위를 RRF로 결합한다. `kiwi_tokenize`는 Kiwi로 명사·동사 등과 외국어·숫자 토큰만 남기는 함수다.
```python
FETCH_K = 5
similarity_retriever = vectorstore.as_retriever(search_kwargs={"k": FETCH_K})
mmr_retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": FETCH_K, "fetch_k": 20, "lambda_mult": 0.5})
bm25_retriever = BM25Retriever.from_documents(
    documents, preprocess_func=kiwi_tokenize, k=FETCH_K)
hybrid_retriever = EnsembleRetriever(
    retrievers=[similarity_retriever, bm25_retriever],
    weights=[0.5, 0.5], id_key="chunk_id")

SEARCH_STRATEGIES = {
    "Similarity": similarity_retriever.invoke,
    "MMR": mmr_retriever.invoke,
    "BM25": bm25_retriever.invoke,
    "Hybrid": hybrid_retriever.invoke,
}
```
- 원본은 `similarity_search(query)` 같은 래퍼 함수 4개를 만들어 dict에 넣었다. 여기서는 `.invoke`로 줄였다.
- MMR은 `as_retriever(search_type="mmr")`로도 만들 수 있다.

## RAG 검색 평가 예시 문항: 8번 질문
RAG 검색 지표 계산 예시로 8번 문항을 Similarity로 검색하고, 상위 5개 청크의 `source` 리스트(`ranked`)와 정답 목록(`relevant`)을 만든다.
```python
case = eval_cases[7]
docs = SEARCH_STRATEGIES["Similarity"](case["question"])
ranked = [doc.metadata["source"] for doc in docs[:5]]
relevant = case["relevant_sources"]
```
```text
질문: 업무 자료가 외부로 나간 것 같아. 누구에게 먼저 알리고 심각도에 따라 언제까지 보고해야 해?
검색 결과: ['개인정보보호규정.md', '지식재산권규정.md', '보안규정.md', '보안규정.md', '보안규정.md']
정답 문서: ['보안규정.md']
```
- 정답 규정이 3위에 처음 나온다. 이 예시로 Hit@k, Precision@k, Recall@k, RR을 계산한다.

## RAG 검색 지표 Hit@k
Hit@k는 상위 k개 검색 결과에 정답 출처가 하나라도 있으면 1, 없으면 0이다. 1이면 상위 k개 안에 답변 근거를 찾았다는 뜻이다.
```python
def hit_at_k(ranked, relevant, k):
    return int(bool(set(ranked[:k]) & set(relevant)))
```
- 예시(ranked = 개인정보보호, 지식재산권, 보안, 보안, 보안 / 정답 = 보안규정)에서 Hit@1 = 0, Hit@3 = 1.
- 정답이 하나뿐이면 `relevant in ranked[:k]`와 같은 의미다.

## RAG 검색 지표 Precision@k
Precision@k는 상위 k개 청크 중 정답 출처에 속한 청크의 비율이다. 높을수록 LLM에 들어가는 불필요한 문맥이 적다.
```text
Precision@k = 상위 k개 중 관련 청크 수 / 상위 k개 청크 수
```
```python
def precision_at_k(ranked, relevant, k):
    selected = ranked[:k]
    hits = sum(source in relevant for source in selected)
    return hits / len(selected) if selected else 0.0
```
- 노트북 출력은 `Precision@3: 0.6`인데, ranked 상위 3개 중 보안규정은 1개라 계산상 0.333이어야 한다. 0.6은 상위 5개 기준(3/5) 값과 같아 출력이 코드와 맞지 않는다.

## RAG 검색 지표 Recall@k
Recall@k는 필요한 정답 출처 전체 중 상위 k개에서 찾은 출처의 비율이다. 같은 출처 청크가 여러 번 나와도 한 번으로 센다(set 사용). 높을수록 필요한 근거를 빠짐없이 가져왔다는 뜻이며, 여러 규정을 종합해야 하는 질문에서 중요하다.
```text
Recall@k = 상위 k개에서 찾은 정답 출처 수 / 전체 정답 출처 수
```
```python
def recall_at_k(ranked, relevant, k):
    hits = len(set(ranked[:k]) & set(relevant))
    return hits / len(set(relevant))
```
- 예시(정답 = 보안규정 1개, 상위 3개에 포함)에서 Recall@3 = 1.0.

## RAG 검색 지표 RR과 MRR
RR(Reciprocal Rank)은 한 질문에서 처음 나온 정답 출처 순위의 역수다(정답이 여러 개여도 첫 번째만 본다). MRR(Mean Reciprocal Rank)은 여러 질문 RR의 평균이다. 1에 가까울수록 첫 근거가 앞쪽에 나온다는 뜻이다.
```text
RR = 1 / 첫 번째 정답 출처의 순위
MRR = 모든 질문의 RR 합 / 전체 질문 수
```
```python
def reciprocal_rank(ranked, relevant):
    relevant = set(relevant)
    for rank, source in enumerate(ranked, start=1):
        if source in relevant:
            return 1 / rank
    return 0.0
```
- 예시에서 정답이 3위라 RR = 0.333.

## RAG 검색 전략 비교 실습: evaluate_strategy 함수
RAG 검색 전략마다 50문항을 검색해 질문별 지표와 질문당 평균 검색 시간(latency)을 기록한다. (축약함)
```python
def evaluate_strategy(label, search_fn, cases, max_k=5):
    rows, started = [], time.perf_counter()
    for case in cases:
        ranked = [d.metadata["source"] for d in search_fn(case["question"])[:max_k]]
        relevant = case["relevant_sources"]
        rows.append({
            "id": case["id"], "difficulty": case["difficulty"],
            "relevant": relevant, "retrieved": ranked,
            "hit@1": hit_at_k(ranked, relevant, 1),
            "precision@5": precision_at_k(ranked, relevant, 5),
            "recall@5": recall_at_k(ranked, relevant, 5),
            "rr": reciprocal_rank(ranked, relevant),
        })
    latency = (time.perf_counter() - started) * 1000 / len(cases)
    return {"label": label, "rows": rows, "latency_ms": latency}
```
- 원본은 hit@3·hit@5·recall@3도 기록하고, `summarize`(평균, rr 평균=MRR)·`show_table`로 표를 출력한다.

## RAG 검색 전략 비교 결과: 50문항 전체
RAG 검색 전략 4종을 `evaluate_strategy`로 50문항 평가한 결과(Hybrid 행은 출력이 일부 잘림):
```python
evaluation_results = {label: evaluate_strategy(label, fn, eval_cases)
                      for label, fn in SEARCH_STRATEGIES.items()}
```
- Similarity: hit@1 0.98, hit@3 1.0, precision@5 0.66, recall@3 0.918, recall@5 0.942, MRR 0.987, latency 약 499ms
- MMR: hit@1 0.98, hit@3 1.0, precision@5 0.36, recall@3 0.855, recall@5 0.893, MRR 0.987, 약 486ms
- BM25: hit@1 0.72, hit@3 0.90, hit@5 0.98, precision@5 0.464, recall@3 0.815, recall@5 0.907, MRR 0.816, 약 1.4ms
- Hybrid: hit@1 0.98, hit@3 1.0, precision@5 0.58, recall@3 0.925

관찰: 이 데이터에서는 Similarity가 가장 균형이 좋고, MMR은 다양성 때문에 precision이 크게 떨어졌다. BM25는 품질은 낮지만 임베딩 호출이 없어 수백 배 빠르다. 난이도별(easy/medium/hard)로 다시 집계하면 easy에서는 대부분 만점이라, 전체 평균에 가려진 차이는 어려운 문항에서 드러난다.

## RAG 검색 실패 사례 분석: Recall@5 < 1인 질문
RAG 검색 평가는 평균뿐 아니라 정답 출처를 다 찾지 못한 질문(`recall@5 < 1`)을 직접 본다.
```python
for label, result in evaluation_results.items():
    failures = [r for r in result["rows"] if r["recall@5"] < 1]
    print(label, len(failures))
    for r in failures[:10]:
        print(r["id"], r["question"], r["relevant"], r["retrieved"])
```
- Similarity는 7개 실패. 대부분 여러 규정을 종합해야 하는 질문이었다.
- 예: "혼인 신고를 앞두고… 휴가·금액·증빙" → 정답은 인사·경비처리·복리후생규정인데 인사규정을 놓쳤다.
- 예: "재택근무 날 접속·장비·자료 기준" → 정답 4개 규정인데 재택근무규정 청크만 4번 반복됐다.
- 같은 규정 청크가 상위를 독차지하면 다른 필요한 규정이 밀려난다.

## RAG 검색 평가 결과 해석과 k 선택
RAG 검색 지표는 각각 다른 능력을 보여 준다.
- Hit@k: 최소 하나의 근거를 찾는 능력
- Recall@k: 여러 규정을 종합하는 질문의 검색 범위
- MRR: 제한된 context에서 첫 근거가 얼마나 빨리 나오는지
- 품질이 비슷하면 latency와 구현 복잡도가 낮은 전략을 고른다. 가장 복잡한 전략이 항상 최고는 아니다.
- `retrieval_strategy_scenarios.json`은 특징 관찰용 fixture라 전체 성능 평가에는 쓰지 않는다.

검색 문서 수 `k`가 작으면 비용과 잡음은 줄지만 근거를 놓칠 수 있고, 크면 근거 포함 가능성은 높지만 무관한 문서와 context 길이가 늘어 품질·비용·응답 시간에 영향을 준다. 적절한 k는 검색 지표와 실제 답변을 함께 보고 정한다.

## RAG 답변 생성과 규칙 기반 인용 검사
RAG 답변 평가의 첫 단계로, 검색 문서로 답변을 만들고 LLM이 표시한 출처를 규칙으로 검사한다. LLM은 답변과 사용한 규정 파일명을 구조화 출력으로 돌려준다.
- `valid_citation`: 인용이 하나 이상 있고, 인용한 출처가 모두 실제 검색 결과에 있는가
- `relevant_citation`: 인용한 출처 중 정답 문서가 하나 이상 있는가

규칙 검사는 같은 입력에 항상 같은 결과를 내지만, 문장 내용이 근거와 맞는지나 질문에 충분히 답했는지는 판단하지 못한다. 그 의미적 품질은 RAGAS와 직접 정의한 Judge로 평가한다. 실습은 Similarity와 Hybrid에 같은 질문 3개를 넣어 답변 6개를 만든다. 구조화 출력 스키마는 다음과 같다.
```python
class GroundedAnswer(BaseModel):
    answer: str = Field(description="검색 근거로 작성한 답변")
    citations: list[str] = Field(description="답변에 사용한 규정 파일명")
```

## RAG 답변 생성 실습: GroundedAnswer와 generate_answer
RAG 답변 생성 실습: 문서마다 `[출처: 파일명]`을 붙여 context를 만들고, `GroundedAnswer` 구조화 출력을 받아 집합 연산으로 인용을 검사한다. (축약)
```python
answer_llm = llm.with_structured_output(GroundedAnswer)

def generate_answer(strategy, search_fn, case, k=5):
    docs = search_fn(case["question"])[:k]
    contexts = [f"[출처: {d.metadata['source']}]\n{d.page_content}" for d in docs]
    result = answer_llm.invoke(
        "검색 근거만 사용해 답하고, 사용한 파일명을 citations에 작성하세요.\n\n"
        f"질문: {case['question']}\n\n검색 근거:\n" + "\n\n".join(contexts))
    retrieved = {d.metadata["source"] for d in docs}
    cited = set(result.citations)
    return {**case, "strategy": strategy, "response": result.answer,
            "citations": result.citations, "retrieved_contexts": contexts,
            "valid_citation": bool(cited) and cited <= retrieved,
            "relevant_citation": bool(cited & set(case["relevant_sources"]))}
```
- `<=`는 부분집합, `&`는 교집합. 6개 답변 모두 두 검사가 True였다.

## RAGAS란: 입력 필드와 메트릭 종류
RAGAS는 RAG의 검색 결과와 생성 답변을 LLM과 임베딩으로 평가하는 라이브러리다. 순위만 계산하는 검색 지표와 달리 답변의 의미를 평가한다. 입력은 `user_input`, `response`, `retrieved_contexts`, `reference` 네 필드다.
- Faithfulness(user_input, response, retrieved_contexts): 답변 주장이 검색 문서로 뒷받침되는가
- Answer Relevancy(user_input, response): 답변이 질문 핵심과 관련되는가
- Context Precision(user_input, reference, retrieved_contexts): 정답 작성에 유용한 문서가 앞쪽에 있는가
- Context Recall(같은 필드): 기준 정답에 필요한 내용을 검색 문서가 다 담았는가
- Factual Correctness(response, reference): 답변 사실이 기준 정답과 일치하는가
- Semantic Similarity(response, reference): 답변과 기준 정답의 의미가 비슷한가

모든 메트릭을 쓸 필요는 없다. 이 수업은 검색 지표와 겹치지 않게 Faithfulness와 Answer Relevancy만 쓴다. RAGAS의 LLM은 답을 만드는 게 아니라 평가하는 역할이며, 여러 번 호출해 비용·시간이 들어 `RUN_RAGAS` 플래그로 필요할 때만 실행한다.

## RAGAS 실습 1단계: 생성 결과를 RAGAS 입력으로 변환
RAGAS 실습: 전략별 답변 생성 결과를 RAGAS 필드 이름(`user_input`, `response`, `retrieved_contexts`, `reference`)으로 바꾼다. 기준 답변은 데이터셋의 `expected_answer`다.
```python
ragas_records = {
    strategy: [
        {"user_input": item["question"],
         "response": item["response"],
         "retrieved_contexts": item["retrieved_contexts"],
         "reference": item["expected_answer"]}
        for item in generation_results if item["strategy"] == strategy
    ]
    for strategy in GENERATION_STRATEGIES   # "Similarity", "Hybrid"
}
```
- 예: "연차는 며칠이야?" → "80% 이상 출근 시 15일, 3년 이상 근속 시 2년마다 1일 가산, 최대 25일."
- 예: 비밀번호 질문 → "90일마다 변경, 최근 5회 비밀번호 재사용 불가."

## RAGAS 실습 2단계: 평가 모델 준비 (Gemini + instructor)
RAGAS 평가용 LLM(instructor로 감싼 Gemini)과 임베딩을 만든다. 단건·batch 임베딩 차원 차이를 피하려고 `aembed_texts`를 하나씩 처리하게 바꾼다. (노트북에 "볼 필요 없음" 표시, 축약)
```python
import instructor
from google import genai
from ragas.embeddings.base import embedding_factory
from ragas.llms import InstructorLLM
from ragas.metrics.collections import AnswerRelevancy, Faithfulness

google_client = genai.Client()
evaluator_llm = InstructorLLM(
    client=instructor.from_genai(google_client, use_async=True),
    model=MODEL_NAME, provider="google")
evaluator_embeddings = embedding_factory(
    "google", model=EMBEDDING_MODEL_NAME, client=google_client)

async def embed_texts_individually(texts, **kwargs):
    return [await evaluator_embeddings.aembed_text(t, **kwargs) for t in texts]
evaluator_embeddings.aembed_texts = embed_texts_individually

faithfulness_metric = Faithfulness(llm=evaluator_llm)
relevancy_metric = AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings)
```

## RAGAS 실습 3단계: Faithfulness·Answer Relevancy 일괄 채점
RAGAS 메트릭의 `abatch_score`에 메트릭별로 필요한 필드만 담은 dict 리스트를 넘겨 채점하고 전략별 평균을 낸다. 노트북 셀에서 바로 `await`를 쓴다. (축약함)
```python
for strategy, records in ragas_records.items():
    f_scores = await faithfulness_metric.abatch_score([
        {k: r[k] for k in ("user_input", "response", "retrieved_contexts")}
        for r in records])
    r_scores = await relevancy_metric.abatch_score([
        {k: r[k] for k in ("user_input", "response")} for r in records])
    print(strategy,
          sum(s.value for s in f_scores) / len(f_scores),
          sum(s.value for s in r_scores) / len(r_scores))
```
```text
Similarity  faithfulness 1.0  answer_relevancy 0.774
Hybrid      faithfulness 1.0  answer_relevancy 0.811
```
- 원본은 dict 리스트를 직접 펼쳐 쓰고 결과를 `ragas_results`에 저장한 뒤 JSON으로 출력한다. 마크다운에는 `RUN_RAGAS = False`가 기본이라고 했지만 코드 셀은 True로 되어 있다.

## RAGAS Faithfulness 점수 해석
RAGAS 점수는 0~1이고 높을수록 기준을 잘 만족하지만, 모든 프로젝트에 통하는 절대 합격선은 없다. 같은 데이터셋으로 설정 A와 B를 비교하고 낮은 문항을 직접 보는 데 쓴다.

Faithfulness는 답변을 검증 가능한 주장 여러 개로 쪼갠 뒤, 각 주장이 `retrieved_contexts`로 뒷받침되는 비율을 본다. 문서에 없는 수치·조건·예외를 덧붙이면 낮아진다.
- 예: 문서에는 "재택근무 주 2회 가능"뿐인데 답변이 "팀장 승인 없이 주 2회 가능"이라 하면 '팀장 승인 없이'가 근거 없는 주장이 되어 점수가 떨어진다.
- Faithfulness가 높다고 정답은 아니다. 검색 문서가 무관하거나 오래돼도 답변이 그 문서에 충실하면 높게 나온다. 그래서 검색된 문서가 올바른지는 Hit@k와 함께 확인한다.

## RAGAS Answer Relevancy 점수 해석
RAGAS Answer Relevancy는 답변만 보고 그 답변에 맞는 질문을 여러 개(기본 3개) 역으로 생성한 뒤, 생성 질문들의 임베딩과 원래 `user_input` 임베딩의 평균 유사도로 점수를 낸다. 회피성 답변으로 판단되면 낮아질 수 있다.
- 질문 핵심에 바로 답하면 높고, 장황한 배경 설명이나 다른 주제 설명이면 낮다.
- `retrieved_contexts`나 `reference`와 사실을 대조하지 않으므로, 그럴듯하게 답한 틀린 내용도 높은 점수를 받을 수 있다.
- 한국어 어미·표현 차이와 평가 LLM이 만든 역질문 품질에 따라 흔들리므로 절대 점수보다 같은 문항·모델·설정에서의 상대 비교에 집중한다.

## RAGAS Faithfulness와 Answer Relevancy 함께 보기
RAGAS 두 점수 조합별 해석:
- Faithfulness 높음 + Relevancy 높음: 검색 근거로 질문에 직접 답했다.
- Faithfulness 높음 + Relevancy 낮음: 근거에는 충실하지만 질문 핵심을 벗어났다.
- Faithfulness 낮음 + Relevancy 높음: 질문에는 답했지만 근거 밖 내용을 만들었다.
- 둘 다 낮음: 근거성도 질문 관련성도 부족하다.

점수가 낮으면 `response`만 보지 말고 `user_input`과 `retrieved_contexts`도 함께 본다. 원인이 생성 모델이 아니라 앞 단계 검색 실패일 수 있다.

## RAGAS와 직접 정의한 LLM-as-Judge 비교
RAGAS는 범용 근거성·답변 관련성을 빠르게 평가할 때 좋고, 직접 정의한 Judge는 규정 답변에 필요한 정확성·완전성·출처 정확성처럼 기준을 자유롭게 정할 수 있다.
- RAGAS 장점: 공통 메트릭을 바로 쓴다. 주의점: 평가 모델과 언어에 따라 점수가 달라진다.
- 직접 Judge 장점: 도메인 기준을 직접 정의한다. 주의점: 채점 프롬프트와 기준 자체를 검증해야 한다.

Judge에는 "좋은 답변인가?" 같은 모호한 질문 대신 수치·조건 일치, 누락 여부, 근거 밖 주장 여부처럼 구체적인 기준을 준다. 이 실습은 정확성, 완전성, 근거성, 출처 정확성을 각각 1~10점(1 거의 미충족, 5 일부 충족, 10 완전 충족)으로 매기고 평균을 내며, 항목별 점수와 감점 이유도 함께 본다.

## LLM-as-Judge 실습 1단계: JudgeScore 채점 기준 정의
LLM-as-Judge 실습: Pydantic 필드의 `description`에 항목별 채점 기준(1점/5점/10점 의미)을 구체적으로 적어 구조화 출력 스키마로 쓴다. (설명 문구 축약)
```python
class JudgeScore(BaseModel):
    correctness: int = Field(ge=1, le=10, description=
        "기준 정답 대비 사실 정확성. 수치·조건·대상·예외가 틀리면 감점. "
        "대부분 틀리면 1, 핵심은 맞고 일부 오류 5, 모두 정확 10")
    completeness: int = Field(ge=1, le=10, description=
        "필요한 핵심 내용을 빠짐없이 포함한 정도. 조건과 예외까지 모두 답하면 10")
    groundedness: int = Field(ge=1, le=10, description=
        "답변 주장이 검색 문서로 뒷받침되는 정도. 근거 없거나 모순되면 1")
    citation_accuracy: int = Field(ge=1, le=10, description=
        "인용 파일이 답변을 지지하고 올바른 검색 출처인지. 인용 없거나 틀리면 1")
    reason_of_correctness: str = Field(description="항목별 판단 근거와 감점 이유")

judge_llm = llm.with_structured_output(JudgeScore)
```

## LLM-as-Judge 실습 2단계: judge_answer로 채점과 평균
LLM-as-Judge 실습: 질문, 기준 정답, 모델 답변, 인용, 검색 문서를 모두 넣어 채점하고 4개 항목 평균을 소수 둘째 자리로 낸다.
```python
def judge_answer(item):
    contexts = "\n\n".join(item["retrieved_contexts"])
    result = judge_llm.invoke(
        "각 항목을 설명된 기준에 따라 1~10점의 정수로 평가하세요. "
        "reason에는 항목별 판단과 감점 이유를 구체적으로 작성하세요.\n\n"
        f"질문: {item['question']}\n기준 정답: {item['expected_answer']}\n"
        f"모델 답변: {item['response']}\n인용: {item['citations']}\n검색 문서:\n{contexts}")
    score = result.model_dump()
    names = ["correctness", "completeness", "groundedness", "citation_accuracy"]
    score["average"] = round(sum(score[n] for n in names) / len(names), 2)
    return score

judge_results = [judge_answer(item) for item in generation_results]
```
- 6개 답변 모두 평균 10.0/10이었고, 근거로 "인사규정 제7조 내용과 일치" 같은 설명이 붙었다.
- 출력 코드는 `score['reason']`을 읽는데 스키마 필드명은 `reason_of_correctness`라 이대로면 KeyError가 난다. 출력은 필드명이 `reason`이던 이전 실행 결과로 보인다.

## RAG 평가 비용·실행 시간과 적용 시점
RAG 검색 지표(Hit@k, Precision@k, Recall@k, MRR)는 정답 문서와 순위만으로 계산해 LLM을 부르지 않으므로 반복 실행이 쉽다. 답변 생성, RAGAS, Judge는 질문 수 × 메트릭 수만큼 API 호출이 는다.
- 개발 중에는 전체 검색 평가를 자주 돌린다.
- 생성 평가는 난이도별 대표 문항부터 돌린다.
- RAGAS와 Judge는 필요한 메트릭만 고른다.
- 비교 결과에는 품질 점수와 latency를 함께 기록한다.

적용 시점: 초기 개발은 대표 질문 직접 확인, 검색 설정 변경은 Hit@k·Recall@k·MRR 회귀 평가, 프롬프트 변경은 RAGAS나 Judge로 답변 비교, 문서 변경은 관련 질문의 정답·검색 결과 재검증, 운영 중에는 사용자 피드백과 실패 질문 수집. 평가 데이터셋은 실패 질문을 추가하고 문서가 바뀌면 기대 정답·정답 출처도 갱신하며 계속 관리한다.

## RAG 평가 복습 Q&A
- Q. RAG 평가에서 검색 평가를 답변 평가보다 먼저 하는 이유는?
  A. 답이 틀렸을 때 검색 실패인지 생성 실패인지 구분하기 위해서다.
- Q. Hit@k와 Recall@k의 차이는?
  A. Hit@k는 정답 출처를 하나라도 찾으면 1, Recall@k는 필요한 정답 출처 전체 중 찾은 비율이다. 여러 규정을 종합하는 질문은 Recall@k로 봐야 한다.
- Q. 정답이 3위에 처음 나오면 RR은? MRR은?
  A. RR = 1/3. MRR은 모든 질문 RR의 평균이다.
- Q. RAGAS Faithfulness가 1.0이면 답이 맞다고 볼 수 있나?
  A. 아니다. 검색 문서에 충실하다는 뜻일 뿐, 문서 자체가 틀리거나 무관할 수 있어 Hit@k 등 검색 평가와 함께 봐야 한다.
- Q. 직접 정의한 LLM-as-Judge 기준은 어떻게 써야 하나?
  A. "좋은 답인가" 대신 수치·조건 일치, 누락, 근거 밖 주장 같은 구체적 항목과 점수 의미(1/5/10점)를 명시한다.
