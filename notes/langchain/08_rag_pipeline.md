---
part: langchain
lesson: RAG 파이프라인
order: 8
source_type: ipynb
tags: [rag, rag-chain, lcel, runnablepassthrough, retriever, citation, chroma]
source: C:\Users\tnwls\aim-ai-agent\langchain_\08-rag-pipeline_answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# RAG 파이프라인

## RAG 파이프라인 요약
Chroma에서 검색한 문서를 context로 묶어 프롬프트에 넣고 LLM 답변과 출처까지 연결하는 RAG Chain을 단계별 호출과 LCEL 두 방식으로 만들고, 사내 규정 문서로 RAG를 구성하는 실습 문제를 푼다.

## RAG 파이프라인의 인덱싱 단계와 질의 단계
RAG 파이프라인은 두 단계로 나뉜다.
- 인덱싱 단계: 문서 로드 → 청킹 → 문서 임베딩 → 벡터 DB 저장. 문서를 검색 가능한 벡터로 미리 준비한다.
- 질의 단계: 질문 임베딩 → 유사 문서 검색 → context 구성 → 프롬프트 입력 → LLM 답변 생성. 검색된 청크가 LLM이 참고할 `context`가 된다.

## RAG 파이프라인 실습 1단계: import와 모델 준비
RAG 파이프라인 실습은 Gemini 임베딩 모델, Gemini 채팅 모델, Chroma를 쓴다. API 키는 `.env`에 두고 `load_dotenv()`로 읽는다. (import 일부 축약)
```python
import chromadb
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

load_dotenv()
embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
```
- import 시 `langchain-community`가 유지보수 종료 예정이라는 DeprecationWarning이 출력된다.

## RAG 파이프라인 실습 2단계: PDF로 Chroma 벡터 DB 구축
RAG 파이프라인의 인덱싱 단계로, 9월호 PDF를 500/50으로 잘라 90개 청크를 Chroma에 저장한다. 이번에는 `persist_directory` 대신 `PersistentClient`를 `client=`로 넘겨 컬렉션 삭제와 생성이 같은 경로를 쓰게 했다.
```python
docs = PyPDFLoader("data/SPRi AI Brief_9월호_산업동향_0909_F.pdf").load()
chunks = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(docs)

client = chromadb.PersistentClient(path="./chroma_db")
if "spri_ai_brief" in [c.name for c in client.list_collections()]:
    client.delete_collection("spri_ai_brief")
vectorstore = Chroma.from_documents(documents=chunks, embedding=embeddings,
                                    collection_name="spri_ai_brief", client=client)
```

## RAG 파이프라인 실습 3단계: 검색 문서를 context로 포매팅하고 프롬프트 작성
RAG에서 검색된 Document 리스트는 하나의 문자열로 합쳐 프롬프트의 `{context}`에 넣는다. 시스템 프롬프트에 "검색 결과에 없으면 '해당 정보를 찾을 수 없습니다'라고 답하라"는 규칙을 넣어 지어내기를 막는다.
```python
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

def format_docs(docs):
    return "\n\n-----\n\n".join(doc.page_content for doc in docs)

prompt = ChatPromptTemplate.from_messages([
    ("system", """너는 AI 산업 동향 전문가야. 아래 검색된 문서를 참고하여 질문에 답변해줘.
검색 결과에 없는 내용은 "해당 정보를 찾을 수 없습니다"라고 답변해.

# 검색된 문서
{context}"""),
    ("human", "{question}"),
])
```
- `"구분자".join(...)`: 리스트 원소 사이에 구분자를 끼워 하나의 문자열로 만든다(원본 구분자는 더 긴 대시 줄).

## RAG 파이프라인 실습 4단계: 단계별로 직접 호출하는 RAG
RAG를 검색 → 포매팅 → 체인 호출 순서로 하나씩 실행하고, 마지막에 검색 문서의 페이지를 출처로 출력한다. (`retriever`, `format_docs`, `prompt`, `llm`은 앞 단계에서 만든 객체)
```python
question = "오픈AI의 차세대 모델에 대해 설명해줘"
docs = retriever.invoke(question)          # 1. 검색
context = format_docs(docs)                # 2. 포매팅
chain = prompt | llm | StrOutputParser()   # 3. 프롬프트 + LLM
response = chain.invoke({"context": context, "question": question})
print(response)

for i, doc in enumerate(docs):             # 출처
    print(f"[{i+1}] 페이지 {doc.metadata.get('page', '?')}: {doc.page_content[:200]}...")
```
- 단계별 호출은 중간값(docs, context)을 변수로 바로 확인할 수 있어 디버깅에 편하다.

## RAG 파이프라인 실습 5단계: RunnablePassthrough.assign으로 하나의 LCEL 체인
RAG의 여러 단계를 LCEL로 하나의 chain으로 합친다. `RunnablePassthrough.assign(context=함수)`는 입력 dict를 유지한 채 `context` 키를 추가하므로, prompt에는 `{"question": ..., "context": ...}`가 전달된다.
```python
def retrieve_context(inputs):
    docs = retriever.invoke(inputs["question"])
    return format_docs(docs)

rag_chain = (
    RunnablePassthrough.assign(context=retrieve_context)
    | prompt | llm | StrOutputParser()
)
print(rag_chain.invoke({"question": "오픈AI의 차세대 모델에 대해 설명해줘"}))
print(rag_chain.invoke({"question": "삼성전자의 2024년 매출은?"}))
```
- 첫 질문은 문서 근거로 GPT-5의 특징(GPQA 88.4%, 사고 모드·실시간 라우터, 환각 감소)을 정리해 답한다.
- 문서에 없는 질문은 다음처럼 답한다.
```text
해당 정보를 찾을 수 없습니다.
```

## RAG 파이프라인을 LCEL로 구성하는 이유
RAG를 단계별 직접 호출로 짤지 LCEL 파이프라인으로 짤지 비교한다.
- 실행 방식: 직접 호출은 각 단계 결과를 변수로 넘기고, LCEL은 여러 단계를 하나의 chain으로 조합한다.
- 중간값 확인: 직접 호출은 변수로 바로 보기 쉽고, LCEL은 반환 구조를 따로 구성해야 한다.
- 비동기·스트리밍: 직접 호출은 단계마다 구현해야 하고, LCEL은 체인 전체에 공통 인터페이스가 적용된다.
- LangSmith: 직접 호출은 trace가 따로 기록될 수 있고, LCEL은 한 trace에서 전체 흐름을 보기 쉽다.

둘 중 하나만 고를 필요는 없다. 검색 결과 검사나 조건 분기는 함수로 쓰고 전체 흐름은 LCEL로 조합할 수 있다.

## RAG 파이프라인 실습 6단계: 딕셔너리로 context와 question 병렬 구성
RAG 체인 맨 앞에 dict를 두면 각 key의 처리가 같은 입력(질문 문자열)을 받는다. `context`는 `retriever | format_docs`로 검색·포매팅하고, `question`은 `RunnablePassthrough()`로 질문을 그대로 넘긴다. 이 방식은 `invoke`에 dict가 아닌 문자열을 넣는다.
```python
rag_chain_parallel = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | prompt | llm | StrOutputParser()
)
print(rag_chain_parallel.invoke("오픈AI의 차세대 모델에 대해 설명해줘"))
```
- 결과는 GPT-5 특징에 더해 오픈 가중치 모델 gpt-oss 등 관련 내용까지 마크다운으로 정리된 답변이 나온다.

## RAG 출처 표시 방식: Inline Citation과 Source List
RAG 출처 표시는 LLM 답변이 어떤 원본 문서에 근거하는지 보여 주는 것으로, 사용자가 근거를 확인하고 할루시네이션을 점검하는 데 도움이 된다.
- Inline Citation: 답변 문장 안에 `[1]`, `[2]` 같은 참조 번호를 넣는다(논문 스타일).
- Source List: 답변 아래에 참조 문서 목록을 따로 보여 준다(Perplexity 스타일).

출처 번호도 LLM이 생성한 것이라 정확성이 보장되지 않는다. 번호를 잘못 달거나, 인용 문서가 답을 충분히 뒷받침하지 못할 수 있으므로 실제 문서와 함께 확인해야 한다.

## RAG 파이프라인 실습 7단계: 출처 번호를 붙이는 Citation RAG
RAG context의 각 문서에 `[번호] (페이지 n)`을 붙여 넣고, 프롬프트로 문장마다 출처 번호를 달게 한다. 검색을 함수 안에서 한 번만 하고 답변과 문서를 함께 반환해 retriever 이중 호출을 막는다. (프롬프트는 축약함)
```python
citation_prompt = ChatPromptTemplate.from_messages([
    ("system", """규칙:
1. 답변의 각 문장 끝에 출처 번호를 [1], [2] 형태로 표시해
2. 검색 결과에 없는 내용은 절대 만들어내지 마
3. 답변할 수 없으면 "해당 정보를 찾을 수 없습니다"라고 답변해
[검색된 문서]
{context}"""),
    ("human", "{question}"),
])

def format_docs_with_index(docs):
    return "\n\n".join(f"[{i+1}] (페이지 {d.metadata.get('page', '?')}) {d.page_content}"
                       for i, d in enumerate(docs))

def citation_rag(question):
    docs = retriever.invoke(question)
    answer = (citation_prompt | llm | StrOutputParser()).invoke(
        {"context": format_docs_with_index(docs), "question": question})
    return answer, docs
```
- "AI 기업들의 최근 제품 출시 현황" 질문에 구글 줄스, 제미나이 데이터 에이전트 등을 `[1], [2]` 번호와 함께 답하고, 아래에 참조 문서 목록을 출력했다.

## RAG 파이프라인 실습 문제: 사내 규정 RAG
RAG 파이프라인 실습 문제: `data/company_rules/` 폴더의 사내 규정 마크다운 5개(IT지원, 경비처리, 보안, 윤리, 인사규정)로 기본 RAG를 만든다.
- `TextLoader`로 UTF-8 마크다운 파일 5개를 로드한다. `TextLoader`는 마크다운 문법을 해석하지 않고 제목·목록 기호까지 원문 그대로 불러온다.
- 문서를 청킹해 벡터 스토어에 저장한다.
- Retriever 검색 결과로 context를 구성한다.
- 검색된 문서만 근거로 답하고 출처를 출력한다.
- 테스트 질문: "연차는 며칠이야?", "USB 꽂아서 파일 옮겨도 돼?", "결혼하면 회사에서 뭘 해줘?"

## 사내 규정 RAG 풀이 1: 마크다운 로드·청킹·Chroma 저장
사내 규정 RAG 풀이: 파일마다 `TextLoader`로 읽고 800/50으로 잘라 한 리스트에 모은 뒤, `company_rules` 컬렉션에 저장하고 k=3 Retriever를 만든다. 결과는 청크 24개.
```python
file_names = [f"data/company_rules/{n}.md" for n in
              ["IT지원규정", "경비처리규정", "보안규정", "윤리규정", "인사규정"]]
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=50)

rule_documents = []
for file_name in file_names:
    docs = TextLoader(file_name, encoding="utf-8").load()
    rule_documents.extend(splitter.split_documents(docs))

client = chromadb.PersistentClient(path="./chroma_db")
if "company_rules" in [c.name for c in client.list_collections()]:
    client.delete_collection("company_rules")
vectorstore = Chroma.from_documents(documents=rule_documents, embedding=embeddings,
                                    collection_name="company_rules", client=client)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
```
- 파일 목록은 리스트 컴프리헨션으로 줄여 적었다(원본은 경로 5개를 직접 나열).

## 사내 규정 RAG 풀이 2: 출처(파일명·조항) 표시 체인
사내 규정 RAG 풀이의 체인 부분: context에 `[번호] (source: 파일명)`을 붙이고, 프롬프트로 답변마다 "몇 조 몇 항"을 표시하게 한다. dict 병렬 구성 LCEL로 체인을 만든다.
```python
def format_docs_with_source(docs):
    return "\n\n".join(
        f"[{i+1}] (source : {d.metadata.get('source', '?').split('/')[-1]}) {d.page_content}"
        for i, d in enumerate(docs))

prompt = ChatPromptTemplate.from_messages([
    ("system", """주어진 <context>을 활용하여 대답해라.
- <context>로 대답할 수 없으면 "해당 정보를 찾을 수 없습니다"라고 답변해
- 각 답변에 참고한 source의 몇조 몇항인지를 표시해.
- <context>에 없는 내용은 절대 만들어내지마.
<context>
{context}
</context>"""),
    ("human", "{question}"),
])
rag_chain = ({"context": retriever | format_docs_with_source,
              "question": RunnablePassthrough()} | prompt | llm | StrOutputParser())
for q in ["연차는 며칠이야?", "개인 USB 연결해도 되나?", "결혼하면 회사에서 뭘 해줘?"]:
    print(rag_chain.invoke(q))
```

## 사내 규정 RAG 풀이 결과 확인
사내 규정 RAG 체인을 세 질문으로 실행한 결과, 답변마다 파일명과 조항이 함께 표시됐다.
- 연차: 80% 이상 출근 시 15일, 3년 이상 근속 시 2년마다 1일 가산, 최대 25일 (인사규정.md 제7조 1~3항)
- 개인 USB: 외부 저장 매체의 업무용 PC 연결 금지 (보안규정.md 제7조 제2항)
- 결혼: 본인 결혼 시 축의금·화환과 유급 특별휴가 5일, 자녀 결혼 시 유급 1일 (경비처리규정 제14조, 인사규정 제8조)

실행 시 Gemini SDK가 "automatic function calling(AFC)을 Models.generate_content에서 직접 쓰는 것은 권장하지 않는다"는 경고를 한 번 출력하지만 결과에는 영향이 없다.

## RAG 파이프라인 복습 Q&A
- Q. RAG 체인에서 `RunnablePassthrough.assign(context=f)`는 무엇을 하나?
  A. 입력 dict를 그대로 유지하면서 f의 결과를 `context` 키로 추가해 다음 단계(prompt)로 넘긴다.
- Q. RAG 체인 앞에 `{"context": retriever | format_docs, "question": RunnablePassthrough()}`를 두면 invoke에 무엇을 넣나?
  A. 질문 문자열 하나. 같은 입력이 두 키에 동시에 전달되어 하나는 검색·포매팅, 하나는 그대로 질문이 된다.
- Q. RAG에서 검색 결과에 없는 질문에 지어내지 않게 하려면?
  A. 시스템 프롬프트에 "검색 결과에 없으면 '해당 정보를 찾을 수 없습니다'라고 답하라"는 규칙을 넣는다.
- Q. RAG Inline Citation 번호를 그대로 믿어도 되나?
  A. 아니다. 번호도 LLM이 생성한 것이라 틀릴 수 있어 실제 문서와 대조해야 한다.
- Q. citation_rag 함수가 검색 결과를 답변과 함께 반환하는 이유는?
  A. 출처 목록 출력용으로 retriever를 한 번 더 호출하지 않기 위해서다(이중 호출 방지).
