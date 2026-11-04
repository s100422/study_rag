---
part: langchain
lesson: 벡터 DB와 검색
order: 7
source_type: ipynb
tags: [vector-db, chroma, ann, hnsw, metadata-filter, similarity-search, retriever]
source: C:\Users\tnwls\aim-ai-agent\langchain_\07-vector-db.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# 벡터 DB와 검색

## 벡터 DB와 검색 요약
임베딩 벡터를 저장하고 빠르게 유사도 검색하는 벡터 DB의 원리(ANN, 메타데이터)를 정리하고, Chroma에 PDF 청크를 저장해 유사도 검색·메타데이터 필터링·Retriever 변환까지 실습한다.

## 벡터 DB란
벡터 DB는 임베딩 벡터를 저장하고 "이 벡터와 가장 비슷한 k개"를 빠르게 찾는 유사도 검색 전용 데이터베이스다. MySQL 같은 일반 DB는 값 일치(`=`)나 범위(`>`) 검색에 최적화되어 있어 유사도 검색에는 맞지 않는다. 예를 들어 1536차원 벡터 10만 개를 질문마다 하나씩 비교하면 너무 느리다.
- 직관: RDB가 데이터를 표(행·열)로 관리한다면, 벡터 DB는 지도처럼 다차원 좌표 공간에 점으로 배치한다. 의미가 비슷하면 가까이 놓인다.
- 물리적으로는 디스크에 저장되지만, 논리적으로는 위치가 곧 의미이고 검색은 거리를 재는 일이다.

## 벡터 DB와 일반 DB 비교
벡터 DB와 일반 DB는 검색 방식부터 다르다.
- 검색 방식: 일반 DB는 정확한 값 매칭(=, >, <), 벡터 DB는 유사도 기반 근사 검색
- 인덱스: 일반 DB는 B-Tree·Hash, 벡터 DB는 HNSW·IVF 같은 벡터 전용 인덱스
- 데이터: 일반 DB는 숫자·문자열·날짜, 벡터 DB는 수백~수천 차원 벡터
- 결과: 일반 DB는 조건에 맞는 정확한 결과, 벡터 DB는 "가장 비슷한" 근사 결과

일반 DB로 유사도를 계산하면 모든 행과 비교해야 하므로 O(n)이고, 데이터가 늘수록 선형으로 느려진다.

## 벡터 DB의 ANN(Approximate Nearest Neighbor) 검색
ANN(근사 최근접 이웃)은 벡터 DB의 핵심 알고리즘이다. 전수 조사(Exact Search)와 항상 같은 결과를 보장하지는 않지만, 인덱스로 후보를 빠르게 좁혀 대규모 벡터에서도 빠르게 검색한다. 재현율은 데이터와 인덱스 설정에 따라 달라진다.
- HNSW: 가까운 벡터끼리 간선으로 연결한 다층 그래프를 탐색한다. 속도와 재현율이 좋지만 그래프 저장에 메모리가 더 든다. 단일 노드 Chroma의 기본 인덱스.
- IVF: 벡터 공간을 여러 클러스터로 나누고 질문과 가까운 클러스터만 검색한다. 검색할 클러스터 수로 속도·재현율이 조절되고, PQ 같은 압축과 결합할 수 있다. FAISS가 대표적으로 지원.

실무에서 ANN을 직접 구현할 일은 없고, 벡터 DB가 왜 빠른지 원리만 이해하면 된다.

## 벡터 DB 동작 흐름: 저장과 검색
벡터 DB는 저장과 검색 두 흐름으로 동작한다.
- 저장: 문서 → 청킹 → 임베딩 모델 → 벡터 + 메타데이터 → 벡터 DB 저장(인덱스 구축)
- 검색: 질문 → 임베딩 모델 → 질문 벡터 → ANN 검색 → 상위 k개 문서 반환

저장할 때는 벡터뿐 아니라 원본 텍스트와 메타데이터(출처, 페이지 등)도 함께 저장한다. 검색 결과로 원본 텍스트를 돌려받아야 LLM에 전달할 수 있기 때문이다.

## 벡터 DB 메타데이터(Metadata)의 역할
벡터 DB에 저장되는 항목은 세 가지다.
- 벡터: 임베딩 좌표값. 유사도 검색에 쓴다.
- 원본 텍스트: LLM에 전달할 내용.
- 메타데이터: `{"source": "사내규정.pdf", "page": 3}` 같은 구조화 정보. 필터링·문서 식별·출처 표시에 쓴다.

메타데이터는 임베딩되지 않는다. 좌표에 찍힌 점에 포스트잇을 붙여 두는 것과 같다. 검색은 (1) 메타데이터 조건으로 대상을 정확 매칭으로 좁히고 (2) 그 안에서 질문과 가까운 k개를 고르는 식이다.
- 멀티테넌트: `user_id`로 본인 문서만 검색
- 문서 구분: 한 컬렉션의 여러 PDF 중 `source`로 특정 문서만 검색
- 페이지 범위 제한

`PyPDFLoader`는 `source`와 `page`(0부터)를 자동으로 넣는다. 추가 정보는 Document의 `metadata` dict에 직접 넣는다. 메타데이터 내용으로 의미 검색을 하려면 그 내용을 본문 텍스트에 넣어 함께 임베딩해야 한다.

## 벡터 DB 종류 비교: Chroma, pgvector, FAISS, Pinecone
대표적인 벡터 DB/라이브러리와 쓰임새다.
- Chroma: 임베디드·서버·클라우드 방식 지원. Python에서 로컬 디스크 저장이 간단하다. 학습, 프로토타입, 소규모 RAG.
- pgvector: PostgreSQL 확장. 관계형 데이터와 벡터를 함께 관리하고 Exact Search, HNSW, IVFFlat 지원. 기존 PostgreSQL 서비스.
- FAISS: Meta의 벡터 검색·클러스터링 라이브러리. CPU/GPU 지원, 원문·메타데이터 같은 DB 기능은 직접 구성해야 한다. 성능 세밀 조정용.
- Pinecone: API로 쓰는 완전 관리형 클라우드 벡터 DB. 운영 확장성과 관리 편의가 중요할 때.

이 실습은 Chroma의 Python 임베디드 방식을 쓴다. 서버 없이 `langchain-chroma`만 설치하면 되고, `persist_directory`를 지정하면 로컬 폴더에 저장돼 재실행해도 유지된다.

## Chroma 실습 1단계: PDF 청크를 벡터 스토어에 저장
Chroma 벡터 스토어에 PDF 청크를 저장한다. 컬렉션은 RDB의 테이블, 저장 폴더는 데이터베이스에 해당한다. 재실행 시 중복 저장을 막으려고 기존 컬렉션을 먼저 지운다. (import·로드 부분은 축약함)
```python
# pip install langchain-chroma
import chromadb
from langchain_chroma import Chroma

COLLECTION_NAME = "spri_ai_brief"
PERSIST_DIR = "./chroma_db"
embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")

docs = PyPDFLoader("data/SPRi AI Brief_9월호_산업동향_0909_F.pdf").load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(docs)

client = chromadb.PersistentClient(path=PERSIST_DIR)
if COLLECTION_NAME in [c.name for c in client.list_collections()]:
    client.delete_collection(COLLECTION_NAME)

vectorstore = Chroma.from_documents(
    documents=chunks, embedding=embeddings,
    collection_name=COLLECTION_NAME, persist_directory=PERSIST_DIR)
```
- `Chroma.from_documents`: 청크를 임베딩하고 저장까지 한 번에 한다.

## Chroma 실습 2단계: add_documents로 문서 추가
Chroma 벡터 스토어에 다른 PDF(10월호) 청크를 `add_documents()`로 추가한다. 각 청크에 `source`·`page` 메타데이터가 있어 9월호와 10월호 결과를 구분할 수 있다.
```python
october_docs = PyPDFLoader("data/SPRi AI Brief_10월호_산업동향_1002_F.pdf").load()
october_chunks = splitter.split_documents(october_docs)
document_ids = vectorstore.add_documents(october_chunks)
print(f"10월호 청크 {len(document_ids)}개를 추가했습니다.")
```
- `add_documents()`: 추가된 문서 ID 리스트를 반환한다.

## Chroma 실습 3단계: similarity_search로 유사도 검색
Chroma 벡터 스토어에서 질문과 가장 비슷한 청크 k개를 찾는다. `page`는 0부터라 사람이 보는 페이지 번호는 +1 한다.
```python
results = vectorstore.similarity_search("즈푸 AI의 AI 모델 이름이 뭐야?", k=3)
for i, doc in enumerate(results):
    page = doc.metadata.get("page")
    page_number = page + 1 if page is not None else "알 수 없음"
    print(i + 1, doc.metadata.get("source"), page_number)
    print(doc.page_content)
```

## Chroma 실습 4단계: filter로 메타데이터 필터링 검색
Chroma의 `similarity_search`에 `filter`를 주면 조건에 맞는 문서만 대상으로 유사도 검색한다.
```python
query = "AI 관련 정책은?"
target_page_index = 6   # 0부터 시작 → PDF 7페이지
results = vectorstore.similarity_search(query, k=3, filter={"page": target_page_index})
for doc in results:
    print(doc.metadata["page"] + 1, doc.page_content[:100])

results_no_filter = vectorstore.similarity_search(query, k=3)
print([d.metadata.get("page") + 1 for d in results_no_filter])
```
- 필터를 걸면 7페이지 청크만 나오고, 필터 없이 검색하면 여러 페이지에서 결과가 나온다.

## Chroma 실습 5단계: similarity_search_with_score로 점수 확인
Chroma의 `similarity_search_with_score`는 (문서, 점수) 튜플을 돌려준다. 기본 설정에서 점수는 유클리드 거리(L2)이므로 값이 작을수록 유사하다(0이면 동일, 클수록 무관). 설정에 따라 코사인 거리 등 다른 메트릭일 수 있다.
```python
results = vectorstore.similarity_search_with_score("오픈AI의 최신 모델은?", k=3)
for doc, score in results:
    print(f"[거리: {score:.4f}] {doc.page_content[:80]}...")
```

## Chroma 실습 6단계: 기존 벡터 스토어에 다시 연결
Chroma에 이미 저장된 컬렉션은 `from_documents` 대신 `Chroma(...)` 생성자로 연결하면 재임베딩 없이 바로 검색할 수 있다. `persist_directory`를 지정하면 데이터는 자동으로 디스크에 저장된다.
```python
existing_store = Chroma(
    embedding_function=embeddings,
    collection_name=COLLECTION_NAME,
    persist_directory=PERSIST_DIR,
)
results = existing_store.similarity_search("구글의 AI 관련 소식은?", k=3)
```
- 주의: 임베딩 모델을 바꾸면 벡터 DB를 처음부터 재구축해야 한다. 모델마다 차원이나 좌표 공간이 달라 기존 벡터와 섞어 쓸 수 없다. "검색 품질이 갑자기 나빠짐"의 흔한 원인이 모델 불일치이므로 저장에 쓴 모델을 기록해 둔다.

## Chroma 실습 7단계: as_retriever로 Retriever 변환
Retriever는 LangChain 체인에 연결하기 위한 통일된 검색 인터페이스로, `retriever.invoke(질문)`이 문서 리스트를 반환한다. 벡터 스토어의 `as_retriever()`로 만들고 검색 옵션은 `search_kwargs`로 준다.
```python
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
docs = retriever.invoke("AI 투자 규모는 어느 정도야?")
for doc in docs:
    print(doc.page_content[:150])
```

## 벡터 DB 실습 문제: PDF 문서 벡터 검색 파이프라인
벡터 DB 실습 문제: SPRi AI Brief 11월호 PDF를 Chroma에 저장하고 질문별 상위 4개 결과를 출력한다. 컬렉션 이름은 `spri_exercise`. 질문은 11월호 기술·연구 섹션 기사(제미나이 로보틱스 1.5, ShinkaEvolve, 페트리)를 겨냥한다.
- "구글 딥마인드가 발표한 로봇용 AI 모델은?"
- "사카나AI가 공개한 알고리즘 진화 프레임워크는?"
- "앤스로픽이 공개한 AI 모델 안전성 평가 자동화 도구는?"

## 벡터 DB 실습 풀이 1: 11월호 PDF를 Chroma에 저장
벡터 DB 실습 풀이(노트북에 직접 작성된 코드): 청크 크기를 700/70으로 키워 11월호를 `spri_exercise` 컬렉션에 저장한다. (축약함)
```python
pdf_path = "data/SPRi AI Brief_11월호_산업동향_1105_F.pdf"
COLLECTION_NAME = "spri_exercise"
PERSIST_DIR = "./chroma_db"

docs = PyPDFLoader(pdf_path).load()
splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=70)
chunks = splitter.split_documents(docs)

client = chromadb.PersistentClient(path=PERSIST_DIR)
if COLLECTION_NAME in [c.name for c in client.list_collections()]:
    client.delete_collection(COLLECTION_NAME)

vectorstore = Chroma.from_documents(
    documents=chunks, embedding=embeddings,
    collection_name=COLLECTION_NAME, persist_directory=PERSIST_DIR)
```

## 벡터 DB 실습 풀이 2: Retriever로 질문별 상위 4개 검색
벡터 DB 실습 풀이의 검색 부분: `as_retriever(k=4)`로 Retriever를 만들고 질문마다 결과의 출처·페이지·본문을 출력한다. (`similarity_search(question, k=4)`로 해도 결과는 같다.)
```python
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
for question in questions:
    for i, doc in enumerate(retriever.invoke(question)):
        page = doc.metadata.get("page")
        page_number = page + 1 if page is not None else "알 수 없음"
        print(f"--- 결과 {i+1} ({doc.metadata.get('source')} - {page_number}page) ---")
        print(doc.page_content)
    print("-" * 50)
```
- 첫 질문의 1위 결과는 11월호 21페이지의 제미나이 로보틱스 1.5 / 로보틱스-ER 1.5 설명 청크였다.
- PDF 메타데이터에는 `creator`, `total_pages`, `page_label` 등도 자동으로 들어 있다.

## 벡터 DB와 검색 복습 Q&A
- Q. 벡터 DB가 일반 DB보다 유사도 검색에 빠른 이유는?
  A. HNSW·IVF 같은 ANN 인덱스로 후보를 빠르게 좁혀 전수 비교(O(n))를 피하기 때문이다. 대신 결과는 근사값이다.
- Q. 벡터 DB 메타데이터는 임베딩되나? 어디에 쓰나?
  A. 임베딩되지 않는다. user_id·source·page 등으로 검색 대상을 필터링하고 출처를 표시할 때 쓴다.
- Q. Chroma similarity_search_with_score의 기본 점수는 클수록 좋은가?
  A. 아니다. 기본은 L2 거리라 작을수록 유사하다.
- Q. Chroma에 저장된 컬렉션을 재임베딩 없이 다시 쓰려면?
  A. `Chroma(embedding_function=..., collection_name=..., persist_directory=...)` 생성자로 연결한다. 단 저장 때와 같은 임베딩 모델이어야 한다.
- Q. 벡터 스토어를 Retriever로 바꾸는 이유는?
  A. LangChain 체인이 `retriever.invoke(질문) → 문서 리스트` 인터페이스를 기대하기 때문이다. `as_retriever(search_kwargs={"k": n})`로 변환한다.
