---
part: langchain
lesson: RAG Agent
order: 14
source_type: ipynb
tags: [rag, agent, retriever-tool, create-retriever-tool, create-agent, checkpointer, system-prompt, chroma]
source: C:\Users\tnwls\aim-ai-agent\langchain_\14-rag-agent.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# RAG Agent

## RAG Agent 요약
RAG Agent 레슨은 Retriever를 `create_retriever_tool`로 Tool로 바꿔 ReAct Agent(`create_agent`)에 등록하고, 필요할 때만 검색하는 대화형 RAG를 만든다. System Prompt로 문서 기반 답변만 허용하는 방법과 Checkpointer로 후속 질문을 처리하는 방법도 다루고, 실습으로 SPRi AI Brief PDF 검색 Agent를 만든다.

## RAG Agent란: 기본 RAG 파이프라인과의 차이
RAG Agent는 ReAct Agent에 Retriever를 Tool로 등록한 대화형 RAG다. 기본 RAG 파이프라인은 질문마다 무조건 검색하지만, RAG Agent는 질문을 보고 검색이 필요할 때만 Retriever Tool을 호출한다.
- 검색 판단: 기본 RAG는 항상 검색, RAG Agent는 LLM이 필요 여부를 판단한다.
- 대화 기억: 기본 RAG는 별도 구현이 필요하고, RAG Agent는 Checkpointer로 유지한다.
- 검색 도구: 기본 RAG는 Retriever를 직접 호출하고, RAG Agent는 Retriever를 Tool로 호출한다.

인사처럼 검색 없이 답할 수 있는 질문은 Tool 호출을 건너뛴다.

## RAG Agent 준비: 429 오류 대비 재시도 클라이언트
RAG Agent 노트북은 임베딩 API의 429(요청 한도 초과) 오류에 대비해 지수 백오프 재시도 옵션을 가진 `genai.Client`를 만들고, 임베딩 객체의 `client`로 바꿔 끼운다.
```python
from google import genai
from google.genai.types import HttpOptions, HttpRetryOptions
from langchain_google_genai import GoogleGenerativeAIEmbeddings

retry_client = genai.Client(
    http_options=HttpOptions(
        retry_options=HttpRetryOptions(
            attempts=8,         # 최초 요청 포함 총 8회
            initial_delay=2.0,  # 첫 재시도 대기(초)
            max_delay=60.0,     # 최대 대기
            exp_base=2,         # 2초 → 4초 → 8초 ...
            jitter=1.0,         # 랜덤 지연으로 동시 재시도 분산
        )
    ),
)
embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
embeddings.client = retry_client
```
- API 키는 `.env`에 두고 `load_dotenv()`로 불러온다(`GOOGLE_API_KEY` 환경 변수 — 내 메모).

## RAG Agent 1단계: Chroma 컬렉션 존재 여부 확인
RAG Agent 노트북은 사내 규정 컬렉션에 이미 청크가 있는지 먼저 확인해, 있으면 재사용하고 없을 때만 새로 만든다.
```python
import chromadb
from pathlib import Path

DATA_DIR = Path("data/company_rules")
PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "company_rules_search_advanced"

client = chromadb.PersistentClient(path=PERSIST_DIR)
existing_collections = [c.name for c in client.list_collections()]
has_documents = (
    COLLECTION_NAME in existing_collections
    and client.get_collection(COLLECTION_NAME).count() > 0
)
if has_documents:
    sample = client.get_collection(COLLECTION_NAME).peek(limit=1)
    print(sample["metadatas"][0])
```
- `PersistentClient`: 디스크 폴더에 저장되는 Chroma 클라이언트.
- `peek(limit=1)`: 저장된 청크 하나를 미리 본다. 출력은 77개 청크, 메타데이터 예: `{'source': 'IT지원규정.md', 'chunk_id': 'IT지원규정:0'}`.

## RAG Agent 2단계: 사내 규정 벡터 저장소 생성
RAG Agent 노트북은 컬렉션이 없거나 비어 있을 때만 `data/company_rules/*.md`를 읽어 청크로 나누고 Chroma에 저장한다. 메타데이터에 `source`(파일명)와 `policy_name`(확장자 뺀 이름)을 넣는다.
```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=700, chunk_overlap=100,
    separators=["\n### ", "\n\n", "\n", " "],   # 조항(###) 경계 우선
)
documents = []
for path in sorted(DATA_DIR.glob("*.md")):
    loaded = TextLoader(path, encoding="utf-8").load()
    for doc in loaded:
        doc.metadata.update({"source": path.name, "policy_name": path.stem})
    documents.extend(splitter.split_documents(loaded))

if COLLECTION_NAME in existing_collections:
    client.delete_collection(COLLECTION_NAME)   # 중복 저장 방지
vectorstore = Chroma.from_documents(
    documents=documents, embedding=embeddings,
    collection_name=COLLECTION_NAME, client=client)
```
- 결과: 규정 청크 77개 저장.
- (원본은 `if has_documents:` 분기 안에 있고, 문서가 없으면 `ValueError`를 낸다. 분기를 빼서 줄였다.)

## RAG Agent create_retriever_tool이 하는 일
LangChain `create_retriever_tool`은 Retriever를 Agent가 호출할 수 있는 Tool로 바꾼다. Agent는 Tool의 `name`과 `description`을 보고 호출할지 정하고, 질문을 `query` 인자로 넘긴다.
- Retriever의 `invoke(query)`를 부르는 함수를 만든다.
- 검색된 Document들을 하나의 문자열로 합쳐 반환한다.
- `document_prompt`: 각 Document를 텍스트로 바꾸는 형식. `{page_content}`엔 본문, `{policy_name}`, `{source}` 같은 나머지 변수엔 같은 이름의 metadata 값이 들어간다.
- `document_separator`: 여러 문서 사이 구분자.

기본 설정은 `page_content`만 넘기고 metadata는 빠진다. 출처처럼 답변에 쓸 metadata는 `document_prompt`에 넣어야 한다. 이때 쓴 metadata 키가 검색된 모든 문서에 있어야 하며, 없으면 변환 중 오류가 난다. `description`에는 검색 대상과 호출 조건을 구체적으로 쓴다.

## RAG Agent 3단계: 사내 규정 Retriever Tool 만들기
RAG Agent 노트북은 저장된 컬렉션으로 Retriever(k=3)를 만들고, 규정명과 출처가 붙도록 `document_prompt`를 지정해 Tool로 변환한다.
```python
from langchain_core.prompts import PromptTemplate
from langchain_core.tools.retriever import create_retriever_tool

vectorstore = Chroma(collection_name=COLLECTION_NAME,
                     embedding_function=embeddings, client=client)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

document_prompt = PromptTemplate.from_template(
    "[규정명: {policy_name}]\n[출처: {source}]\n{page_content}")

retriever_tool = create_retriever_tool(
    retriever,
    name="search_company_rules",
    description=(
        "회사 내부 규정에서 근무 시간, 휴가, 복리후생, 출장비, "
        "보안 및 인사 정책을 검색한다. "
        "회사 규정이나 사내 정책에 관한 질문을 받았을 때 사용한다."),
    document_prompt=document_prompt,
    document_separator="\n\n---\n\n",
)
```

## RAG Agent 4단계: Retriever Tool 직접 호출해 보기
RAG Agent에 붙이기 전에 Retriever Tool을 직접 `invoke`해 입력 형식과 반환 텍스트를 확인한다. 입력은 `{"query": ...}` dict다.
```python
retrieved_text = retriever_tool.invoke({"query": "연차 휴가는 며칠인가요?"})
print(retrieved_text)
```
```text
[규정명: 인사규정]
[출처: 인사규정.md]
### 제6조 (초과 근무) ...
### 제7조 (연차 유급휴가)
1. 1년간 80% 이상 출근한 직원에게 15일의 연차 유급휴가를 부여한다. ...
---
[규정명: 출장규정]
...
```
- 각 문서에 `document_prompt` 형식이 적용되고 문서 사이에 `---`가 들어간다.
- `policy_name`이 없다는 오류가 나면 이전 방식으로 만든 컬렉션일 수 있으므로 벡터 DB를 새로 만든다(원본 주석). (출력은 줄여 옮겼다.)

## RAG Agent 5단계: create_agent로 Agent 만들고 검색 판단 확인
RAG Agent는 `create_agent`에 Retriever Tool을 넘기면 완성된다. `stream()`으로 보면 규정 질문에는 Tool을 부르고 인사에는 바로 답한다.
```python
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
graph = create_agent(model=llm, tools=[retriever_tool])

for event in graph.stream({"messages": [("user", "회사 규정상 연차는 며칠이야?")]}):
    for node_name, value in event.items():
        last_msg = value["messages"][-1]
        print(f"[{node_name}] {last_msg.type}: {last_msg.text[:200]}")
        for tc in getattr(last_msg, "tool_calls", None) or []:
            print(f"  Tool 이름: {tc['name']}, 인자: {tc['args']}")
```
```text
[model] ai:
  Tool 이름: search_company_rules, 인자: {'query': '연차 휴가 일수 부여 기준'}
[tools] tool: [규정명: 인사규정] ...
[model] ai: 인사규정 제7조에 따라 기본 15일, 3년 이상 근속 시 2년마다 1일 가산, 최대 25일 ...
```
- "안녕하세요!"는 `[model] ai: 안녕하세요! 무엇을 도와드릴까요? ...`로 Tool 없이 끝난다.
- 노드 이름은 `model`, `tools`이다. Agent가 질문을 검색에 맞게 바꿔 `query`로 보낸다.

(Tool 출력 반복문을 줄였고 출력도 요약했다.)

## RAG Agent System Prompt로 문서 기반 답변만 허용
RAG Agent는 검색 결과가 부족해도 LLM 일반 지식으로 답할 수 있다. 사내 문서 QA나 고객 응대 봇처럼 승인된 문서 근거만 허용해야 하면 `system_prompt`로 제어한다.
```python
strict_rag_agent = create_agent(
    model=llm,
    tools=[retriever_tool],
    system_prompt="""
사내 규정과 관련된 질문에는 search_company_rules 도구를 반드시 사용한다.
답변은 검색된 사내 규정만 근거로 작성하고, 참고한 규정명과 출처를 포함한다.
검색 결과에 질문에 답할 충분한 근거가 없으면
'해당 정보를 사내 규정에서 찾을 수 없습니다.'라고 답한다.
사내 규정과 관련 없는 질문에도 같은 문장으로 답하고 도구를 호출하지 않는다.
문서에 없는 내용을 추측하거나 일반 지식으로 보완하지 않는다.
""",
)
```
- "오늘 날씨 어때?" → "해당 정보를 사내 규정에서 찾을 수 없습니다."
- "출장 숙박비 한도는 얼마야?" → 국내(서울·수도권 1박 15만 원 등)·해외 한도를 정리하고 출장규정, 경비처리규정 출처를 붙여 답한다.

용도별 선택: 개방형(System Prompt 없음, 문서+일반 지식)과 제한형(문서 근거만, 정확성이 중요할 때).

## RAG Agent Checkpointer로 대화형 RAG 만들기
RAG Agent에 `checkpointer=MemorySaver()`를 넘기면 이전 대화를 기억해 "아까 내용에서 더 알려줘" 같은 후속 질문을 처리한다.
```python
from langgraph.checkpoint.memory import MemorySaver

rag_agent = create_agent(model=llm, tools=[retriever_tool],
                         checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "rag-session-1"}}

for q in ["회사 규정상 재택근무는 일주일에 몇 번 가능해?",
          "그 중에서 가장 중요한 것 하나만 골라줘",
          "위 내용을 영어로 번역해줘"]:
    result = rag_agent.invoke({"messages": [("user", q)]}, config=config)
    print(result["messages"][-1].text)
```
- 1번 질문: `search_company_rules` 호출 → 일반 직원 주 2회, 수습 주 1회, 육아기 주 3회 등 규정 기반 답변.
- 2번 질문: Tool 없이 이전 답변에서 "주 2회까지 가능"을 고른다.
- 3번 질문: Tool 없이 대화 맥락으로 영어 번역.
- Checkpointer가 없으면 "그 중에서", "위 내용"이 무엇을 가리키는지 알 수 없다.

(세 셀을 for문 하나로 합쳤다.)

## RAG Agent 실습 문제: SPRi AI Brief 대화형 RAG Agent
RAG Agent 실습은 SPRi AI Brief 9월호, 10월호, 11월호 PDF로 AI 산업 동향을 검색하는 대화형 RAG Agent를 만드는 것이다. 풀이는 먼저 필요한 재료와 순서를 한글로 적고 코드로 조립한다.
1. RAG 준비: 데이터 로드 → 청킹 → 임베딩 → 벡터 DB 저장. 검색 필터·출처 표기용 metadata에 신경 쓴다. 벡터 저장소를 Retriever로 만든다.
2. Tool calling이 가능한 LLM Agent(ReAct)가 필요하다.
3. Retriever를 Tool로 바꿔 Agent에 준다. 어떤 Retriever를 쓸지, 검색 문서를 어떻게 합쳐 넘길지 정한다.
4. 대화형을 위해 Checkpointer를 붙인다.

## RAG Agent 실습 풀이 1: SPRi PDF 로드와 월별 metadata
RAG Agent 실습 풀이는 파일명 패턴으로 월간 보고서 PDF를 찾고, 파일명에서 월을 뽑아 페이지 metadata에 넣은 뒤 청크마다 고유 `chunk_id`를 붙인다.
```python
DATA_DIR = Path("data")
COLLECTION_NAME = "spri_search_advanced"
splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)

pdf_paths = sorted(DATA_DIR.glob("SPRi AI Brief_*월호*.pdf"))
documents = []
for path in pdf_paths:
    month = int(path.name.split("_")[1].removesuffix("월호"))  # "9월호" → 9
    pages = PyPDFLoader(path).load()
    for page in pages:
        page.metadata.update({"source": path.name, "year": 2025,
                              "month": month, "company": "SPRi"})
    chunks = splitter.split_documents(pages)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = f"{path.stem}:{i}"
    documents.extend(chunks)
```
- 이후 같은 이름 컬렉션이 있으면 `client.delete_collection()`으로 지우고 `Chroma.from_documents(..., client=client)`로 저장한다.
- 결과: PDF 3개, 청크 220개.

## RAG Agent 실습 풀이 2: SPRi Retriever Tool과 Agent
RAG Agent 실습 풀이는 Retriever(k=3)를 출처가 붙는 Tool로 바꾸고, 검색 근거만 쓰도록 System Prompt와 Checkpointer를 넣어 Agent를 만든다.
```python
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
SPRi_retriever_tool = create_retriever_tool(
    retriever,
    name="search_SPRi_ai_Brief",
    description="SPRi_ai_Brief에 들어있는 ai 산업 관련 동향을 검색한다.",
    document_prompt=PromptTemplate.from_template("[출처: {source}]\n{page_content}"),
    document_separator="\n\n---\n\n",
)
agent = create_agent(
    model=llm,
    tools=[SPRi_retriever_tool],
    system_prompt="""
질문에 대해서 SPRi_retriever_tool 도구를 반드시 사용한다.
답변은 검색된 자료만 근거로 작성하고, 참고한 출처를 포함한다.
검색 결과에 질문에 답할 충분한 근거가 없으면 근거가 없다고 말해.
""",
    checkpointer=MemorySaver(),
)
```
- System Prompt의 도구 이름 `SPRi_retriever_tool`은 변수명이고 실제 Tool 이름은 `search_SPRi_ai_Brief`라 서로 다르다. 프롬프트에는 Tool `name`을 쓰는 편이 정확하다(내 메모).
- 실습 import 셀의 BM25·Ensemble은 쓰이지 않고, `create_agent` 등은 앞쪽 셀 import에 의존한다.

## RAG Agent 실습 풀이 3: 검색어를 바꿔 가며 재검색
RAG Agent 실습 풀이를 `thread_id="rag-session-3"`으로 "즈푸 ai의 동향에 대해서 알려줘."라고 물으면, Agent가 결과가 부족하다고 보고 검색어를 바꿔 여러 번 Tool을 호출한다.
```text
[model] ai:  Tool 인자: {'query': '즈푸 AI'}
[tools] tool: [출처: SPRi AI Brief_9월호_...pdf] 두 모델 모두 하이브리드 추론 모델로 ...
[model] ai:  Tool 인자: {'query': '즈푸'}
[tools] tool: (같은 청크)
[model] ai:  Tool 인자: {'query': 'ZhipuAI GLM'}
[tools] tool: [출처: SPRi AI Brief_9월호_...pdf] 즈푸 AI, 추론과 에이전트 성능 강화한 'GLM-4.5' 공개 ...
```
- 한글 음역 검색어로는 원하는 청크가 안 나오자 영문 회사명·모델명(ZhipuAI GLM)으로 바꿔 관련 기사를 찾았다. ReAct 루프가 재검색을 스스로 하는 예다.
- 고유명사 검색에 약한 벡터 검색을 보완하려면 BM25를 섞은 Hybrid 검색기를 Tool로 쓰는 방법도 있다(내 메모).
- 풀이 주석 아이디어: 직접 `@tool` 함수를 만들어 LLM이 `query`와 함께 metadata 필터(예: month)를 인자로 넘기게 할 수도 있다(원본은 미완성 의사코드).

(출력은 줄여 옮겼다.)

## RAG Agent 복습 Q&A
- Q. RAG Agent와 기본 RAG 파이프라인의 가장 큰 차이는?
  A. 기본 RAG는 매 질문마다 검색하지만, RAG Agent는 LLM이 판단해 검색이 필요할 때만 Retriever Tool을 호출한다.
- Q. `create_retriever_tool`에서 출처를 답변에 쓰게 하려면?
  A. 기본은 `page_content`만 넘기므로 `document_prompt`에 `{source}` 같은 metadata 변수를 넣는다. 그 키는 모든 검색 문서에 있어야 한다.
- Q. RAG Agent가 문서에 없는 내용을 일반 지식으로 답하지 않게 하려면?
  A. `create_agent(system_prompt=...)`에 검색 결과만 근거로 답하고, 근거가 없으면 정해진 거절 문장으로 답하라고 지시한다.
- Q. RAG Agent에서 "위 내용을 영어로 번역해줘" 같은 후속 질문을 처리하려면?
  A. `create_agent(..., checkpointer=MemorySaver())`로 만들고 같은 `thread_id`로 호출한다.
- Q. RAG Agent Tool의 `description`이 중요한 이유는?
  A. Agent가 Tool 설명을 보고 어떤 정보가 들어 있는지, 언제 호출할지를 판단하기 때문이다.
