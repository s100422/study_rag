---
part: langchain
lesson: RAG 평가 실습
order: 10
source_type: ipynb
tags: [rag, evaluation, golden-set, hit-at-k, mrr, bm25, hybrid-search, mmr]
source: C:\Users\tnwls\aim-ai-agent\langchain_\10-rag-evaluation-practice-answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# RAG 평가 실습

## RAG 평가 실습 요약
공공 PDF 문서로 검색기를 만들고 golden set으로 File Hit@k, Page Hit@k, MRR을 계산해 Similarity, MMR, BM25, Hybrid 검색 전략을 비교하는 실습이다. 이 노트는 정답 노트북(`10-rag-evaluation-practice-answer.ipynb`)을 기준으로 하고, 같은 주제의 다음 노트북도 함께 정리했다.
- `10-rag-evaluation-practice.ipynb`: 전처리 코드는 제공되고 검색기·지표·평가만 TODO인 실습판 (Similarity, MMR만 비교).
- `10-rag-evaluation-practice-with-preprocessing.ipynb`: 메타데이터 정리와 문서 분할까지 직접 채우는 실습판.
- `10-rag-evalution-script/RAG_EXPERIMENT_GUIDE.ipynb`: config 파일과 CLI(argparse)로 RAG 실험을 설계하는 가이드.

## RAG 평가 실습 데이터: 공공 PDF와 golden set
RAG 평가 실습의 검색 대상은 `data/public/*.pdf`(공공 PDF 11개, 236페이지)이고, 평가 데이터는 `public_paragraph_golden_set.json`(35문항)이다. 출처는 Hugging Face의 `allganize/RAG-Evaluation-Dataset-KO`이다.
- `question`: 검색 질의
- `target_answer`: 기준 답변
- `target_file_name`: 정답 파일명 (경로 없이 파일명만)
- `target_page_no`: 정답 페이지 번호 (1부터 시작)

```python
eval_cases = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
print(f"평가 문항: {len(eval_cases)}개")   # 평가 문항: 35개
```
- 정답 노트북은 결과를 보기 좋게 출력하려고 `show_table(items, keys, widths)`라는 고정폭 표 출력 헬퍼를 따로 만들어 쓴다.

## RAG 평가 실습 1단계: 라이브러리와 경로 설정
RAG 평가 실습은 Chroma 벡터 저장소, Gemini 임베딩, BM25(Kiwi 형태소 분석)를 사용한다. API 키는 `.env`에 두고 `load_dotenv()`로 불러온다 (Google 임베딩은 `GOOGLE_API_KEY` 환경 변수를 읽는다 — 내 메모).
```python
import json, time
from pathlib import Path
from dotenv import load_dotenv
from kiwipiepy import Kiwi
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
DATA_DIR = Path("data/public")
GOLDEN_SET_PATH = DATA_DIR / "public_paragraph_golden_set.json"
EMBEDDING_MODEL_NAME = "gemini-embedding-2"
```
(import 두 줄을 한 줄로 합쳐 줄였다.)

## RAG 평가 실습 2단계: PDF 로드와 메타데이터 정규화
RAG 평가에서 검색 결과를 golden set과 비교하려면 메타데이터 형식을 맞춰야 한다. `PyPDFLoader`의 `source`는 `data/public/파일명.pdf`처럼 경로를 포함하고 `page`는 0부터 시작하지만, golden set은 파일명만 쓰고 페이지는 1부터 센다. 그래서 `source`는 `Path(...).name`으로 파일명만 남기고, `page_no = page + 1`을 새로 저장한다. 원래 `page`는 그대로 둔다.
```python
page_documents = []
for pdf_path in sorted(DATA_DIR.glob("*.pdf")):
    pages = PyPDFLoader(pdf_path).load()   # 문서 1개 = PDF 1페이지
    for page in pages:
        page.metadata["source"] = Path(page.metadata["source"]).name
        page.metadata["page_no"] = page.metadata["page"] + 1
    page_documents.extend(pages)
```
```text
로드한 PDF: 11개
로드한 페이지: 236개
```
- with-preprocessing 실습판에서는 이 for문 안이 `# TODO`로 비어 있다.

## RAG 평가 실습 3단계: 페이지 메타데이터를 유지한 문서 분할
RAG 평가 실습에서는 페이지 문서를 `RecursiveCharacterTextSplitter`로 나눈다. `split_documents()`는 원본 문서의 메타데이터를 각 청크에 그대로 복사하므로, 청크도 `source`와 `page_no`를 가진다.
```python
splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
documents = splitter.split_documents(page_documents)
print(f"생성한 청크: {len(documents)}개")   # 생성한 청크: 402개
```
- `chunk_size=700`: 청크 최대 글자 수
- `chunk_overlap=100`: 이웃 청크끼리 겹치는 글자 수

## RAG 평가 실습 4단계: Similarity·MMR 검색기 구성
RAG 평가 실습은 같은 청크와 같은 검색 개수(k=5)로 검색기들을 만들어 공정하게 비교한다. 벡터 검색기는 Chroma에서 만든다 (저장 경로 없이 메모리에 생성).
```python
embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL_NAME)
vectorstore = Chroma.from_documents(documents=documents, embedding=embeddings)

FETCH_K = 5
similarity_retriever = vectorstore.as_retriever(search_kwargs={"k": FETCH_K})
mmr_retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": FETCH_K, "fetch_k": 20},
)
```
- Similarity: 질의와 임베딩이 가장 가까운 청크 k개
- MMR: 후보 `fetch_k=20`개 중 관련성과 다양성을 함께 고려해 k개를 고른다
- 실습판 두 개는 Similarity와 MMR만 `retrievers = {"Similarity": ..., "MMR": ...}`로 구성한다.

## RAG 평가 실습 5단계: Kiwi BM25와 Hybrid 검색기 구성
RAG 평가 정답 노트북은 키워드 기반 BM25와, 벡터 검색과 BM25를 섞은 Hybrid도 추가한다. 한국어는 띄어쓰기만으로 토큰을 나누면 조사 때문에 매칭이 약하므로 Kiwi 형태소 분석으로 토큰을 만든다.
```python
kiwi = Kiwi()

def kiwi_tokenize(text):
    return [
        t.form.lower() for t in kiwi.tokenize(text)
        if t.tag.startswith(("N", "V", "M", "X")) or t.tag in {"SL", "SN"}
    ]

bm25_retriever = BM25Retriever.from_documents(
    documents, preprocess_func=kiwi_tokenize, k=FETCH_K)
hybrid_retriever = EnsembleRetriever(
    retrievers=[similarity_retriever, bm25_retriever], weights=[0.5, 0.5])

retrievers = {"Similarity": similarity_retriever, "MMR": mmr_retriever,
              "BM25": bm25_retriever, "Hybrid": hybrid_retriever}
```
- 품사 태그 N(명사)·V(용언)·M(수식언)·X(접사)와 SL(외국어)·SN(숫자)만 남긴다.
- `EnsembleRetriever`: 두 검색 결과를 가중치 0.5:0.5로 결합(RRF 방식 — 내 메모).

(코드는 변수명을 줄여 압축했다.)

## RAG 평가 지표: File Hit@k, Page Hit@k, MRR
RAG 검색 평가 지표는 검색 결과 문서 `doc`과 golden set 문항 `case`를 비교해 계산한다.
- File Hit@k: 상위 k개 안에 정답 파일(`source == target_file_name`)이 있으면 1, 없으면 0.
- Page Hit@k: 상위 k개 안에 파일과 페이지(`page_no == target_page_no`)가 모두 맞는 문서가 있으면 1.
- RR(Reciprocal Rank): 정답 페이지가 처음 나온 순위의 역수. 3위에서 처음 나오면 `1/3`, 결과에 없으면 0.0.
- MRR: 여러 문항의 RR 평균.

File Hit은 "맞는 문서를 찾았나", Page Hit은 "맞는 위치까지 찾았나"를 보므로 Page Hit이 항상 같거나 더 낮다.

## RAG 평가 실습 6단계: 평가 지표 함수 구현
RAG 평가 지표 함수는 검색 결과 리스트 `docs`의 앞 k개만 보고 0/1을 돌려준다.
```python
def file_hit_at_k(docs, case, k):
    return int(any(
        doc.metadata["source"] == case["target_file_name"]
        for doc in docs[:k]))

def page_hit_at_k(docs, case, k):
    return int(any(
        doc.metadata["source"] == case["target_file_name"]
        and doc.metadata["page_no"] == case["target_page_no"]
        for doc in docs[:k]))

def reciprocal_rank(docs, case):
    for rank, doc in enumerate(docs, start=1):
        if (doc.metadata["source"] == case["target_file_name"]
                and doc.metadata["page_no"] == case["target_page_no"]):
            return 1 / rank
    return 0.0
```
- `int(any(...))`: True/False를 1/0으로 바꿔 평균 내기 쉽게 한다.
- `enumerate(..., start=1)`: 순위를 1부터 센다.

## RAG 평가 실습 7단계: 전략별 전체 평가 함수
RAG 평가 함수 `evaluate_retriever`는 문항마다 검색해 지표, 지연 시간(ms), 검색 위치를 한 행에 담는다.
```python
def evaluate_retriever(name, retriever, cases):
    rows = []
    for case in cases:
        started = time.perf_counter()
        docs = retriever.invoke(case["question"])
        latency_ms = (time.perf_counter() - started) * 1000
        rows.append({
            "strategy": name, "question": case["question"],
            "target_page_no": case["target_page_no"],
            "file_hit_1": file_hit_at_k(docs, case, 1),
            **{f"page_hit_{k}": page_hit_at_k(docs, case, k) for k in (1, 3, 5)},
            "reciprocal_rank": reciprocal_rank(docs, case),
            "latency_ms": latency_ms,
            "retrieved": [{"rank": r, "source": d.metadata["source"],
                           "page_no": d.metadata["page_no"]}
                          for r, d in enumerate(docs, start=1)],
        })
    return rows
```
(압축본: 원본은 `target_file_name`도 저장한다.)

## RAG 평가 실습 8단계: 전체 실행과 전략별 평균 요약
RAG 평가는 모든 검색기를 돌려 결과 행을 모은 뒤, 전략별로 각 지표의 평균을 낸다. `reciprocal_rank`의 평균이 곧 MRR이다.
```python
evaluation_results = []
for name, retriever in retrievers.items():
    evaluation_results.extend(evaluate_retriever(name, retriever, eval_cases))

metric_names = ["file_hit_1", "page_hit_1", "page_hit_3",
                "page_hit_5", "reciprocal_rank", "latency_ms"]
summary = []
for strategy in retrievers:
    rows = [r for r in evaluation_results if r["strategy"] == strategy]
    summary.append({
        "strategy": strategy,
        "count": len(rows),
        **{m: sum(r[m] for r in rows) / len(rows) for m in metric_names},
    })
```
- `**{...}`: 지표 이름별 평균 dict를 펼쳐서 한 행에 합친다.

## RAG 평가 실습 결과: 검색 전략 비교 수치
RAG 평가 정답 노트북의 35문항 결과(k=5)는 다음과 같다.
- Similarity: File Hit@1 1.000, Page Hit@1 0.886, Page Hit@3·@5 0.943, MRR 0.914, 약 520ms
- MMR: Similarity와 지표가 같음, 약 536ms
- BM25: File Hit@1 0.971, Page Hit@1 0.886, Page Hit@3 0.914, Page Hit@5 0.943, MRR 0.907, 약 3ms
- Hybrid: File Hit@1 1.000, Page Hit@1 0.914, Page Hit@3·@5 0.943, MRR 0.929, 약 620ms

해석(내 메모): Hybrid가 Page Hit@1과 MRR이 가장 높아 정답 페이지를 가장 앞에 올린다. BM25는 임베딩 API 호출이 없어 수백 배 빠르고 정확도도 비슷하다. 벡터 검색 지연 시간은 대부분 질의 임베딩 API 호출 시간이다. File Hit은 거의 1인데 Page Hit은 낮으므로, 파일은 맞히지만 같은 파일의 다른 페이지를 가져오는 경우가 실패의 주원인이다.

## RAG 평가 실습 9단계: 실패 문항 분석
RAG 평가 실패 분석은 `page_hit_5 == 0`인 행을 모아 `retrieved`(순위·파일·페이지)를 정답과 비교한다. 같은 파일의 다른 페이지가 나왔는지, 아예 다른 파일만 나왔는지를 구분한다.
```python
failures = [row for row in evaluation_results if row["page_hit_5"] == 0]
```
- 정답 노트북 출력에서는 청년농 우대보증 한도, 담보 설정 시 대출 가능 금액 같은 질문이 Similarity·MMR에서 실패했다. 1순위로 검색된 문서는 정답과 같은 청년농 보증 책자 파일이었지만 페이지가 달랐다(정답 22, 25페이지).
- 숫자·조건이 많은 질문은 비슷한 내용의 여러 페이지가 경쟁해 페이지 단위로 틀리기 쉽다(내 메모).

## RAG 평가 실습 결과 정리 과제
RAG 평가 실습판 노트북은 마지막에 다음 내용을 직접 정리하게 한다(정답 노트북에는 서술 답이 없어 아래는 내 메모).
- 가장 좋은 전략과 근거: Hybrid. Page Hit@1 0.914, MRR 0.929로 가장 높다. 속도가 중요하면 BM25.
- File Hit과 Page Hit이 다른 이유: 파일 안에 주제가 비슷한 페이지가 많아, 파일은 맞혀도 정답 페이지가 아닌 이웃 페이지 청크가 뽑힌다.
- 실패 문항 특징: 정답 파일은 상위에 나오지만 다른 페이지가 검색된다.
- 개선해 볼 설정: `chunk_size`/`chunk_overlap` 조정, k 늘리기, Hybrid 가중치 조정, MMR `fetch_k`·`lambda_mult` 조정, 리랭커 추가, 다른 임베딩 모델.

## RAG 실험 설계: config 파일로 조건 분리
RAG 실험 설계 가이드(`RAG_EXPERIMENT_GUIDE.ipynb`)는 여러 조건으로 RAG 파이프라인을 돌려 결과를 비교하는 프로젝트를 Claude Code와 함께 만드는 과제다. 실험 조건을 코드에 직접 쓰면 바꿀 때마다 코드를 고쳐야 하므로, 조건을 config 파일로 분리하면 같은 코드로 여러 설정을 실행하고 기록으로 남길 수 있다.
- config에 넣을 수 있는 항목: 문서·평가 데이터 경로, 청킹 설정, 검색 설정, 생성 설정, 평가 방법
- 형식과 항목은 프로그램 구조에 맞게 직접 설계한다.
- 결과를 비교하려면 어떤 데이터(조건, 지표, 검색 결과 등)를 저장해야 할지 미리 생각한다.

## RAG 실험 설계: argparse로 CLI 옵션 받기
RAG 실험 스크립트는 `argparse`로 터미널에서 문서 경로, 결과 폴더, 실험 이름 같은 값을 받을 수 있다.
```powershell
python app.py --document-path data.pdf --result-dir outputs --experiment-name chunk-test
```
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--document-path")
parser.add_argument("--result-dir")
parser.add_argument("--experiment-name")
args = parser.parse_args()

print(args.document_path)
print(args.result_dir)
print(args.experiment_name)
```
- 옵션 이름의 하이픈(`-`)은 파이썬 속성에서 언더스코어(`_`)로 바뀐다. `--document-path` → `args.document_path`

## RAG 평가 실습 복습 Q&A
- Q. RAG 평가에서 PyPDFLoader 메타데이터를 golden set과 맞추려면 무엇을 바꾸나?
  A. `source`는 `Path(source).name`으로 파일명만 남기고, 0부터 시작하는 `page`에 1을 더해 `page_no`로 저장한다.
- Q. RAG 평가에서 File Hit@k와 Page Hit@k의 차이는?
  A. File Hit은 상위 k개에 정답 파일이 있는지, Page Hit은 정답 파일과 페이지가 모두 일치하는 문서가 있는지를 본다.
- Q. RAG 평가 MRR은 어떻게 계산하나?
  A. 문항마다 정답 페이지가 처음 나온 순위의 역수(없으면 0)를 구하고 전체 평균을 낸다.
- Q. RAG 평가 실습에서 한국어 BM25에 Kiwi를 쓰는 이유는?
  A. 형태소 단위로 토큰을 나눠 조사 등에 덜 흔들리게 키워드를 매칭하기 위해서다.
- Q. RAG 평가 실습에서 Hybrid 검색기는 어떻게 만드나?
  A. `EnsembleRetriever(retrievers=[similarity, bm25], weights=[0.5, 0.5])`로 벡터 검색과 BM25를 결합한다.
