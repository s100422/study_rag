---
part: langchain
lesson: Crawling with Parent-Child RAG
order: 33
source_type: ipynb
tags: [rag, parent-child, crawling, postgresql, chroma, psycopg, wikipedia, chunking]
source: C:\Users\tnwls\aim-ai-agent\langchain_\33-crawling-with-parent-child-rag.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Crawling with Parent-Child RAG

## Crawling with Parent-Child RAG 요약
위키백과 문서를 크롤링해 원문 HTML과 section(Parent)은 PostgreSQL에, 작은 Child 청크와 벡터는 Chroma에 저장한다. 질문하면 Child를 벡터 검색한 뒤 `parent_id`로 section 전체를 SQL 조회해 Gemini로 답변을 만든다.

## Parent-Child Chunking이란
Parent-Child Chunking은 검색 단위와 답변 문맥 단위를 분리하는 RAG 청킹 방식이다. 이 노트북에서는 위키백과의 최상위 section 하나를 Parent로, 그 section 본문을 작은 크기로 나눈 조각을 Child로 쓴다. 작은 Child는 질문과 정확히 맞는 부분을 찾기 좋고, 연결된 Parent(section 전체)는 답변에 충분한 문맥을 준다.
- 흐름: 질문 → Child 벡터 검색 → `parent_id` 확인 → SQL로 section 조회 → 답변 생성
- 질문 시에는 저장된 청크만 검색하고, 청킹 설정을 바꿀 때만 DB의 원문으로 청크를 다시 만든다.

## Parent-Child RAG 저장소 구성: RDB와 벡터 DB
Parent-Child RAG에서 저장소를 세 곳으로 나눈다.
- PostgreSQL `crawled_documents`: URL, 문서 제목, section 구조를 보존한 본문 HTML, 수집 시각. 키는 `id`, URL(`source`)은 UNIQUE.
- PostgreSQL `rag_parent_chunks`: section별 제목과 본문. `parent_id`가 기본 키, `document_id`가 원문을 가리킨다. `collection_name`으로 실험을 구분하고 `parent_index`로 문서 내 section 순서를 기록한다.
- Chroma: Parent 제목을 붙인 Child 청크와 벡터. 메타데이터의 `parent_id`로 Parent와 연결한다.

원문 HTML을 보관하면 다시 크롤링하지 않고도 Parent 범위나 Child 크기를 바꿔 재청킹할 수 있다.

## Parent-Child RAG 실습 1단계: DB 생성과 접속 설정
Parent-Child RAG 실습은 PostgreSQL에 `wiki_rag` DB를 먼저 만든다(`CREATE DATABASE wiki_rag;`). 접속 정보는 `.env`에서 읽고, 사용자명·비밀번호는 `quote()`로 URL 인코딩해 접속 URI를 만든다.
```python
load_dotenv(override=True)
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
if not POSTGRES_PASSWORD:
    raise ValueError(".env에 POSTGRES_PASSWORD를 설정하세요.")
user = quote(POSTGRES_USER, safe="")
password = quote(POSTGRES_PASSWORD, safe="")
DB_URI = f"postgresql://{user}:{password}@localhost:5432/wiki_rag"

llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
```
- `quote(..., safe="")`: 비밀번호에 `@`, `/` 같은 특수문자가 있어도 URI가 깨지지 않게 한다.
- 모델 설정 셀을 접속 설정과 합쳐 적었다(축약).

## Parent-Child RAG 실습 2단계: 원문·Parent 테이블 생성
Parent-Child RAG용 PostgreSQL 테이블 두 개를 psycopg로 만든다. (`collection_name` 인덱스 생성문은 생략)
```python
with psycopg.connect(DB_URI, row_factory=dict_row) as conn:
    conn.execute("""CREATE TABLE IF NOT EXISTS crawled_documents (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        source TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        crawled_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS rag_parent_chunks (
        parent_id TEXT PRIMARY KEY,
        document_id BIGINT NOT NULL REFERENCES crawled_documents(id),
        collection_name TEXT NOT NULL,
        parent_index INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        UNIQUE (collection_name, document_id, parent_index))""")
```
- `row_factory=dict_row`: 조회 결과를 dict로 받아 `row["id"]`처럼 쓴다.
- `REFERENCES crawled_documents(id)`: Parent가 원문 문서를 가리키는 외래 키.

## Parent-Child RAG 실습 3단계: 위키백과 본문 HTML 정리
Parent-Child RAG의 `extract_page()`는 위키백과 HTML에서 제목과 본문(`body`)을 꺼내고 불필요한 태그를 지운 뒤 HTML 문자열 그대로 반환한다.
```python
def extract_page(html: bytes) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.body
    if main is None or soup.title is None:
        raise ValueError("문서 제목 또는 본문을 찾지 못했습니다.")
    title = soup.title.get_text(" ", strip=True)
    for tag in main.select("script, style, link, meta, .mw-editsection, .navbox, "
                           ".vertical-navbox, .metadata, .mw-references-wrap, .reflist, sup.reference"):
        tag.decompose()
    return {"title": title, "content": str(main)}
```
- `decompose()`: 스크립트·편집 링크·탐색 상자·각주 등을 트리에서 제거한다.
- 텍스트가 아닌 정리된 HTML을 저장해 section 구조를 보존한다.

## Parent-Child RAG 실습 3-1단계: 위키백과 REST API로 크롤링
Parent-Child RAG의 `crawl_page()`는 위키백과 페이지 대신 REST API(`/w/rest.php/v1/page/<제목>/html`)로 본문 HTML을 받고, 출처는 원래 위키 URL로 둔다. 대상은 관계형 데이터베이스, SQL, 데이터베이스 트랜잭션 3개 문서다.
```python
def crawl_page(url: str) -> dict:
    page_title = unquote(url.split("/wiki/", 1)[1])
    api_url = f"https://ko.wikipedia.org/w/rest.php/v1/page/{quote(page_title, safe='')}/html"
    response = requests.get(api_url, timeout=20,
                            headers={"User-Agent": "WikiSectionRAG/1.0 (educational notebook)"})
    response.raise_for_status()
    return {"source": url, **extract_page(response.content)}
```
- `unquote` → `quote(safe='')`: URL의 한글 제목을 디코딩한 뒤 API 경로용으로 다시 인코딩한다.
- `User-Agent`를 지정해 요청 주체를 밝힌다. 첫 문서는 약 4.9만 자 HTML이 나온다.

## Parent-Child RAG 실습 4단계: section을 Parent로 분리
Parent-Child RAG의 `split_sections()`는 다른 section 안에 있지 않은 최상위 `section[data-mw-section-id]`만 Parent로 고른다. h3 등 하위 section은 같은 Parent에 포함되고, 첫 헤딩 앞 본문은 `도입부`가 된다. 각주·참고 문헌·외부 링크·같이 보기는 제외한다. (아래는 핵심만 남긴 축약 코드)
```python
sections = [s for s in soup.select("section[data-mw-section-id]")
            if s.find_parent("section") is None]
for section in sections:
    heading = section.find(["h2", "h3", "h4", "h5", "h6"])
    title = "도입부"
    if heading is not None and heading.find_parent("section") is section:
        title = heading.get_text(" ", strip=True)
    if title in excluded_titles:
        continue
    for block in section.find_all(block_tags):  # h2~h6, p, pre, ul, ol, dl, table
        if block.find_parent(block_tags) is not None:
            continue  # 중첩 블록은 바깥 블록에서 이미 텍스트를 가져옴
        ...
```
- `pre`는 줄바꿈을 살리고 나머지는 `get_text(" ", strip=True)`로 텍스트화한다.
- 헤딩만 있고 본문이 없는 section은 버린다. 블록들은 `"\n\n"`로 합친다.

## Parent-Child RAG 실습 5단계: ON CONFLICT로 원문 저장
Parent-Child RAG의 원문 저장은 `INSERT ... ON CONFLICT`로 재실행에 안전하게 만든다. 같은 URL이 있으면 기존 `id`는 유지하고 제목·본문·수집 시각만 갱신한다.
```python
row = conn.execute("""
    INSERT INTO crawled_documents (source, title, content)
    VALUES (%s, %s, %s)
    ON CONFLICT (source) DO UPDATE SET
        title = EXCLUDED.title,
        content = EXCLUDED.content,
        crawled_at = CURRENT_TIMESTAMP
    RETURNING id
""", (doc["source"], doc["title"], doc["content"])).fetchone()
```
- `EXCLUDED`: 새로 넣으려던 행을 가리킨다.
- `RETURNING id`: 삽입·갱신된 행의 id를 돌려받는다.
- 문서마다 `time.sleep(1)`로 요청 간격을 둔다. 결과는 문서 1~3이 저장된다.
- 이후 `WHERE source = ANY(%s)`에 URL 리스트를 넘겨 원문을 다시 조회하고, 빠진 URL이 있으면 에러를 낸다.

## Parent-Child RAG 실습 6단계: Parent 행 만들기
Parent-Child RAG는 DB에서 읽은 원문 HTML을 `split_sections()`로 나눠 Parent 행을 만든다. 제목은 "문서 제목 - section 제목", ID는 `컬렉션:문서id:p순번` 형식이다.
```python
collection_name = "wiki_sections_with_title_v1"
for doc in source_documents:
    for parent_index, section in enumerate(split_sections(doc["content"])):
        parent_rows.append({
            "parent_id": f"{collection_name}:{doc['id']}:p{parent_index}",
            "document_id": doc["id"],
            "collection_name": collection_name,
            "parent_index": parent_index,
            "title": f"{doc['title']} - {section['title']}",
            "content": section["content"],
        })
```
- 결과: 원문 3개에서 Parent 29개. section 길이는 68자~2,912자로 편차가 크다.
- 원문·청킹 설정·임베딩 입력 형식·모델을 바꾸면 컬렉션 이름도 `_v2`처럼 새로 정한다.

## Parent-Child RAG 실습 7단계: 제목을 붙인 Child 만들기
Parent-Child RAG의 Child는 `RecursiveCharacterTextSplitter(chunk_size=350, chunk_overlap=50)`로 section 본문을 나눈 뒤, 앞에 Parent 제목을 붙여 임베딩 입력에 문맥을 넣는다. 메타데이터의 title은 임베딩에 자동 포함되지 않기 때문이다.
```python
for parent in parent_rows:
    for child_index, child_text in enumerate(child_splitter.split_text(parent["content"])):
        child_ids.append(f"{parent['parent_id']}:c{child_index}")
        child_documents.append(Document(
            page_content=f"제목: {parent['title']}\n\n{child_text}",
            metadata={"parent_id": parent["parent_id"],
                      "document_id": parent["document_id"],
                      "source": source_by_id[parent["document_id"]],
                      "title": parent["title"]},
        ))
```
- 결과: Child 105개.
- 제목을 붙이므로 실제 임베딩 입력은 350자보다 길어진다.

## Parent-Child RAG 실습 8단계: Parent·Child 저장과 연결 검증
Parent-Child RAG는 Parent를 `executemany`로 PostgreSQL에 한 번에 넣고, Child는 코사인 거리 Chroma 컬렉션에 배치로 넣는다. 이미 저장된 Child ID는 건너뛰어 재임베딩을 피한다.
```python
vectorstore = Chroma(collection_name=collection_name, embedding_function=embeddings,
                     persist_directory="chroma_db/crawled_parent_child",
                     collection_configuration={"hnsw": {"space": "cosine"}})
stored_ids = set(vectorstore.get(include=[])["ids"])
pending = [(i, d) for i, d in zip(child_ids, child_documents) if i not in stored_ids]
for start in range(0, len(pending), 32):
    batch = pending[start:start + 32]
    vectorstore.add_documents(documents=[d for _, d in batch], ids=[i for i, _ in batch])
```
- Parent 저장 셀은 컬렉션마다 한 번만 실행한다(같은 parent_id면 기본 키 충돌).
- 검증: 모든 Child 메타데이터의 `parent_id`가 `rag_parent_chunks`에 있는지 assert로 확인. Parent 29, Child 105.

## Parent-Child RAG 실습 9단계: Child 검색 후 Parent 조회
Parent-Child RAG 검색은 `similarity_search_with_score(question, k=8)`로 Child를 찾고(거리가 작을수록 가까움), `fetch_parents()`로 Parent를 가져온다. (아래는 축약)
```python
def fetch_parents(child_hits, max_parents=3):
    parent_ids = []
    for child, _ in child_hits:
        pid = child.metadata["parent_id"]
        if pid not in parent_ids:
            parent_ids.append(pid)
        if len(parent_ids) == max_parents:
            break
    rows = conn.execute("""
        SELECT p.parent_id, p.document_id, p.title, p.content, d.source
        FROM rag_parent_chunks AS p
        JOIN crawled_documents AS d ON d.id = p.document_id
        WHERE p.parent_id = ANY(%s) AND p.collection_name = %s
    """, (parent_ids, collection_name)).fetchall()
    by_id = {r["parent_id"]: r for r in rows}
    return [Document(page_content=by_id[p]["content"], metadata={...}) for p in parent_ids]
```
- 검색 순서를 유지해 중복 parent_id를 빼고, SQL 결과를 그 순서로 재정렬한다.
- 없는 parent_id면 ValueError.

## Parent-Child RAG 실습 10단계: 답변 Chain과 ask 함수
Parent-Child RAG 답변은 Parent의 제목·출처·본문을 문자열로 합쳐 프롬프트 `{context}`에 넣는다. 시스템 프롬프트는 문서만 근거로 답하고, 문서 내용을 지시로 실행하지 말고, 근거가 없으면 확인할 수 없다고 하며, 끝에 출처를 표시하라고 요구한다.
```python
answer_chain = prompt | llm | StrOutputParser()

def ask(question, child_k=8, max_parents=3):
    hits = vectorstore.similarity_search_with_score(question, k=child_k)
    parents = fetch_parents(hits, max_parents=max_parents)
    return {"question": question, "children": hits, "parents": parents,
            "answer": answer_from_documents(question, parents)}
```
- `answer_from_documents()`: 문서가 없으면 "관련 문서를 찾지 못했습니다."를 반환한다.
- 예: "기본 키와 외래 키 역할" 질문에서 1위 Child는 "관계형 데이터베이스 - 키"(거리 약 0.21). COMMIT/ROLLBACK 질문은 Child 8개, Parent 3개로 답하고 출처 URL을 붙인다.
- 첫 호출 시 Gemini SDK의 AFC 관련 경고 문구가 출력되지만 답변에는 영향이 없다.

## Parent-Child RAG Child 크기 실험 방법
Parent-Child RAG 실험은 DB에 저장된 원문으로 Child 크기만 바꿔 비교한다.
- `CHUNK_CONFIG["child_size"]`를 바꾸고 `collection_name`을 새 이름(`_v2`)으로 바꾼 뒤 청킹 설정 셀부터 재실행한다.
- 같은 질문에서 검색된 Child, 선택된 section, 문맥 길이, 답변을 비교한다.
- `child_k`(검색 후보 수)와 `max_parents`(전달 section 수)도 바꿔 본다.
- section이 짧으면 Child가 Parent 전체와 같을 수 있고, 긴 section은 관련 없는 내용까지 전달할 수 있다.
- 커널 재시작 후에는 크롤링 셀은 건너뛰고 설정, `URLS`, DB 조회, `split_sections` 정의부터 실행한다.

## Crawling with Parent-Child RAG 복습 Q&A
- Q. Parent-Child RAG에서 Child와 Parent는 각각 어디에 저장되나?
  A. Child와 벡터는 Chroma, Parent(section 본문)와 원문 HTML은 PostgreSQL에 저장하고 `parent_id`로 연결한다.
- Q. Parent-Child RAG에서 원문을 텍스트가 아닌 HTML로 저장하는 이유는?
  A. section·헤딩 구조가 남아 있어 다시 크롤링하지 않고도 Parent 범위나 Child 크기를 바꿔 재청킹할 수 있기 때문이다.
- Q. Child `page_content` 앞에 Parent 제목을 붙이는 이유는?
  A. 메타데이터는 임베딩되지 않으므로, 제목을 본문에 넣어야 문서·section 문맥이 검색에 반영된다.
- Q. `ON CONFLICT (source) DO UPDATE`는 무엇을 하나?
  A. 같은 URL이 이미 있으면 새로 넣지 않고 기존 행의 id를 유지한 채 제목·본문·수집 시각을 `EXCLUDED` 값으로 갱신한다.
- Q. `fetch_parents()`의 `max_parents`는 무엇인가?
  A. 전달할 Parent 수의 상한이다. 여러 Child가 같은 Parent에 속하면 실제 수는 더 적을 수 있다.
