---
part: langchain
lesson: RAG 기초 - 문서 처리와 임베딩
order: 6
source_type: ipynb
tags: [rag, document-loader, text-splitter, chunk, embedding, cosine-similarity, gemini]
source: C:\Users\tnwls\aim-ai-agent\langchain_\06-rag-basic.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# RAG 기초 - 문서 처리와 임베딩

## RAG 기초 - 문서 처리와 임베딩 요약
RAG의 인덱싱 앞부분(문서 로드 → 청크 분할 → 임베딩)을 LangChain으로 직접 해 보고, 코사인 유사도로 질문과 문서를 비교하는 간단한 검색까지 구현하는 노트북이다.

## RAG(Retrieval-Augmented Generation)란
RAG는 질문과 관련된 문서를 먼저 검색(Retrieval)하고, 그 문서를 프롬프트에 함께 넣어 LLM이 답을 생성(Generation)하게 하는 방식이다. LLM은 학습 이후의 정보나 사내 규정 같은 비공개 문서를 모르고, 모르는 내용을 그럴듯하게 지어낼 수 있다. RAG를 쓰면 모델을 다시 학습시키지 않고 외부 문서를 답변 근거로 쓸 수 있다. 단, 검색된 문서가 틀리거나 질문과 맞지 않으면 답변도 틀릴 수 있다.
- 예: "연차 신청은 어떻게 해?" → LLM만 쓰면 "HR에 문의하세요" 같은 모호한 답, RAG를 쓰면 사내 규정을 찾아 구체적인 신청 경로를 답한다.

## RAG 파이프라인 전체 흐름: 인덱싱과 질의 응답
RAG 파이프라인은 두 단계로 나뉜다.
- 인덱싱 단계(질문 전에 미리): 문서 → 로드(DocumentLoader) → 분할(TextSplitter) → 임베딩 → 벡터 DB 저장
- 질의 응답 단계(질문이 들어오면): 질문 → 임베딩 → 벡터 DB 검색 → 관련 문서 추출 → LLM에 전달 → 응답 생성

## RAG 실습 준비: 패키지와 import
RAG 기초 실습은 PDF 로드를 위해 `pypdf`가 필요하고, 임베딩은 Gemini 임베딩 모델을 쓴다. API 키는 `.env`에 두고 `load_dotenv()`로 환경변수에 올린다(`GOOGLE_API_KEY`를 쓰는 것으로 보임 — 내 메모).
```bash
pip install pypdf
```
```python
import math
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
EMBEDDING_MODEL_NAME = "gemini-embedding-2"
```

## LangChain Document Loader란
Document Loader는 RAG에 쓸 문서를 읽어 `Document` 객체 리스트로 돌려주는 도구다(`load()` 메서드).
- `TextLoader`: `.txt`, `langchain_community`
- `PyPDFLoader`: `.pdf`, `langchain_community` + `pypdf`
- `CSVLoader`: `.csv`
- `WebBaseLoader`: 웹페이지

`Document`는 `page_content`(검색·임베딩할 본문)와 `metadata`(출처, 페이지 번호 등 부가 정보 dict)로 이루어진다. metadata는 "이 내용이 어디서 왔나"를 추적할 때 쓰며, 로더마다 채우는 항목이 다르다.
```python
Document(page_content="문서의 텍스트 내용...",
         metadata={"source": "파일경로", "page": 0})
```
로더가 파일 구조를 완벽히 복원하지는 못한다. 스캔 PDF는 OCR이 필요할 수 있고, 표나 다단 편집 문서는 읽는 순서가 바뀔 수 있다.

## Document Loader 실습 1단계: TextLoader로 텍스트 파일 로드
`TextLoader`는 텍스트 파일 전체를 Document 하나로 반환한다. 한글 파일은 `encoding="utf-8"`을 지정한다.
```python
loader = TextLoader("data/sample_rules.txt", encoding="utf-8")
docs = loader.load()
print(len(docs), docs[0].metadata)
print(docs[0].page_content[:200])
```
```text
1 {'source': 'data/sample_rules.txt'}
```
- 내용 미리보기에는 회사 연차 규정(목적, 연차 부여 일수, 신청 방법 조항)이 출력된다.

## Document Loader 실습 2단계: PyPDFLoader로 PDF 로드
`PyPDFLoader`는 PDF를 페이지 단위로 나눠 페이지마다 Document 하나를 만든다. `metadata['page']`는 0부터 시작한다.
```python
loader = PyPDFLoader("data/SPRi AI Brief_9월호_산업동향_0909_F.pdf")
docs = loader.load()
print(f"문서 수 (= 페이지 수): {len(docs)}")
for doc in docs[:3]:
    print(doc.metadata['page'], doc.page_content[:200])
```
- 출력: 문서 수 28, 페이지 0은 표지, 페이지 1은 목차(정책·법제 기사 제목들)가 보인다.

## Text Splitter(텍스트 분할)가 필요한 이유
Text Splitter는 문서를 작은 청크(chunk)로 나누는 도구다. 문서를 통째로 임베딩하면 두 가지 문제가 생긴다.
- 검색 정확도 저하: 긴 문서에 여러 주제가 섞여 질문과 무관한 내용까지 같이 잡힌다.
- 입력 크기 제한: 임베딩 모델과 LLM은 한 번에 처리할 수 있는 토큰 수가 정해져 있다.

그래서 적당한 크기의 청크로 나눈 뒤 청크마다 임베딩한다.

## Text Splitter 핵심 파라미터: chunk_size와 chunk_overlap
Text Splitter의 핵심 파라미터는 두 개다.
- `chunk_size`: 청크의 최대 크기(문자 수). 예: 500
- `chunk_overlap`: 인접한 청크끼리 겹치는 길이. 예: 50

overlap이 있으면 청크 경계에서 문맥이 끊기는 것을 줄인다.
```text
원본: [ABCDEFGHIJ], chunk_size=5, overlap=2
청크1: [ABCDE]  청크2: [DEFGH]  청크3: [GHIJ]
```
`RecursiveCharacterTextSplitter`의 `chunk_size`는 문자 수 기준이지만 임베딩 모델의 입력 제한은 토큰 수 기준이므로, 청크가 모델 한도를 넘지 않는지 따로 확인해야 한다.

## RecursiveCharacterTextSplitter 실습: PDF 청크 분할
`RecursiveCharacterTextSplitter`는 범용으로 권장되는 분할기로, `\n\n`(문단) → `\n`(줄) → ` `(공백) 순으로 자르고, 그래도 크면 문자 단위로 자른다. 문단·줄·단어 경계를 최대한 지킨다.
```python
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(docs)   # docs: PyPDFLoader 결과
print(len(docs), len(chunks))
for chunk in chunks[8:12]:
    print(len(chunk.page_content), chunk.metadata.get("page"))
```
- `split_documents()`: Document 리스트를 받아 청크 Document 리스트를 반환하며, 원래 metadata(page 등)가 청크에 그대로 따라온다.

## 다른 청킹 방법론 비교
`RecursiveCharacterTextSplitter` 외에도 문서 특성에 맞춘 청킹 방법이 있다.
- `TokenTextSplitter`: 토큰 수 기준. 임베딩 모델 토큰 한도를 정확히 맞춰야 할 때.
- `MarkdownHeaderTextSplitter`: `#`, `##` 등 마크다운 헤더 기준. 섹션 구조를 유지한다.
- `HTMLHeaderTextSplitter`: `h1`, `h2` 등 HTML 헤더 기준. 웹 크롤링 결과에 적합.
- `SemanticChunker`: 인접 문장의 임베딩 유사도로 주제 전환 지점을 찾는다. 문장마다 임베딩하므로 계산량·API 사용량이 늘 수 있다.
- Parent-Child Chunking: 작은 검색용 청크와 큰 전달용 청크를 연결한다. 세밀한 검색과 넓은 문맥이 모두 필요할 때 쓰며, 청크 간 매핑 관리가 필요하다.

## 임베딩(Embedding)이란
임베딩은 텍스트를 숫자 벡터로 바꾸는 것이다. 의미가 비슷한 텍스트는 가까운 벡터가 되므로, 벡터 사이 거리로 의미 유사도를 잴 수 있다. 예를 들어 "고양이"와 "강아지"의 벡터는 가깝고 "자동차"는 멀다.
- 벡터 차원 수는 모델과 설정에 따라 다르다.
- 개별 숫자를 사람이 해석하기는 어렵다. 임베딩은 의미의 정답이 아니라 모델이 학습한 방식의 표현이다.
- 중요한 것은 벡터 간 상대적 거리다.
- 문서와 질문은 반드시 같은 임베딩 모델, 같은 차원 설정으로 변환해야 비교할 수 있다.

## Gemini 임베딩 실습: embed_query와 embed_documents
LangChain 임베딩 모델은 입력의 역할에 따라 두 메서드를 쓴다.
- `embed_query(text)`: 검색 질문 하나 → 벡터 하나
- `embed_documents(texts)`: 저장할 문서 리스트 → 벡터 리스트
```python
embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL_NAME)

vector = embeddings.embed_query("고양이는 귀엽다")
print(len(vector), vector[:5])

texts = ["고양이는 귀엽다", "강아지는 충성스럽다", "Python은 프로그래밍 언어다"]
vectors = embeddings.embed_documents(texts)
```
```text
3072 [-0.008659504, 0.004564434, 0.003567579, 0.012966436, 0.004280134]
```
- `gemini-embedding-2` 벡터는 3072차원이다(전체 벡터를 print하면 매우 긴 출력이 나온다).

## 코사인 유사도(Cosine Similarity)란
코사인 유사도는 두 벡터가 얼마나 같은 방향을 가리키는지 재는 값으로, 범위는 -1~1이고 1에 가까울수록 유사하다.
```text
cosine_similarity(A, B) = (A · B) / (|A| × |B|)
```
- `A · B`: 내적(원소끼리 곱해서 합산)
- `|A|`: 벡터 크기(원소 제곱합의 제곱근)

노트북은 2차원 벡터 그림으로 직관을 설명한다. 실제 임베딩은 수천 차원이지만 원리는 같다.
- 코사인 값은 방향 관계일 뿐, "같은 뜻/무관/반대 뜻"을 그대로 보장하지 않는다.
- 관련 여부를 가르는 보편적 기준 점수는 없다. 점수 분포가 모델·데이터마다 달라서 평가 데이터로 기준을 정해야 한다.
- 다른 거리 함수로 유클리드 거리(L2), 내적(Inner Product)이 있다. 거리 함수는 임베딩 모델과 벡터 저장소 설정에 맞춘다.

## 코사인 유사도 실습: 직접 구현과 문장 비교
코사인 유사도를 파이썬으로 직접 구현하고 Gemini 임베딩 문장끼리 비교한다. (노트북 주석상 구현 코드는 참고용)
```python
def cosine_similarity(vec1, vec2):
    if len(vec1) != len(vec2):
        raise ValueError("두 벡터의 차원이 같아야 합니다.")
    dot = sum(a * b for a, b in zip(vec1, vec2))
    m1 = math.sqrt(sum(a ** 2 for a in vec1))
    m2 = math.sqrt(sum(b ** 2 for b in vec2))
    if m1 == 0 or m2 == 0:
        raise ValueError("0 벡터는 계산할 수 없습니다.")
    return dot / (m1 * m2)
```
기준 "고양이가 소파에서 낮잠을 잔다"와 비교한 결과:
```text
고양이가 침대에서 자고 있다   → 0.7754
강아지가 공원에서 뛰어놀고 있다 → 0.4716
주식 시장이 급락했다          → 0.4775
```
- 비슷한 문장은 확실히 높지만, 무관한 문장끼리의 점수 차는 작을 수 있다.

## 임베딩 기반 유사도 검색 실습: 사내 규정 Top-2 찾기
사내 규정 문장들을 `embed_documents`로 임베딩하고, 질문을 `embed_query`로 임베딩한 뒤 모든 문서와 코사인 유사도를 계산해 상위 2개를 뽑는다. 질문과 문서 표현이 달라도(예: "휴가" vs "연차", "집에서 일하기" vs "재택근무") 의미가 비슷하면 찾는다. (코드는 축약함, `cosine_similarity`는 직접 구현한 함수)
```python
documents = ["연차 신청은 그룹웨어의 근태 관리 메뉴에서 제출합니다.",
             "재택근무를 하려면 근무일 3일 전까지 팀장의 승인을 받아야 합니다.",
             "법인카드 사용 후 영수증은 경비 처리 시스템에 등록해야 합니다."]  # 원본은 6개
document_vectors = embeddings.embed_documents(documents)

query_vector = embeddings.embed_query("휴가를 쓰려면 어디에서 신청하나요?")
scores = [(cosine_similarity(query_vector, v), d)
          for d, v in zip(documents, document_vectors)]
scores.sort(key=lambda x: x[0], reverse=True)
for rank, (score, doc) in enumerate(scores[:2], start=1):
    print(rank, f"{score:.4f}", doc)
```
- 벡터 DB 없이 전수 비교하는 방식이라 문서가 많아지면 느리다(내 메모).

## RAG 기초 - 문서 처리와 임베딩 복습 Q&A
- Q. RAG는 LLM만 쓸 때의 어떤 문제를 해결하나?
  A. 학습 이후 정보나 비공개 문서를 모르는 문제. 관련 문서를 검색해 프롬프트에 넣어 근거 있는 답을 만든다(재학습 불필요).
- Q. TextLoader와 PyPDFLoader는 Document를 어떻게 나누나?
  A. TextLoader는 파일 전체를 Document 1개로, PyPDFLoader는 페이지마다 1개로 나눈다(page는 0부터).
- Q. Text Splitter의 chunk_overlap은 왜 두나?
  A. 청크 경계에서 문맥이 끊기는 것을 줄이기 위해 인접 청크가 일부 겹치게 한다.
- Q. 임베딩의 embed_query와 embed_documents 차이는?
  A. embed_query는 질문 문자열 1개 → 벡터 1개, embed_documents는 문서 리스트 → 벡터 리스트.
- Q. 코사인 유사도 점수로 "관련 있음"을 판단하는 기준값은?
  A. 보편적 기준은 없다. 모델·데이터마다 분포가 달라 평가 데이터로 정해야 한다.
