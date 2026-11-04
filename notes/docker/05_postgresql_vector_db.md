---
part: docker
lesson: PostgreSQL을 벡터 DB로 사용하기
order: 5
source_type: web
tags: [docker, pgvector, postgresql, vector-db, langchain-postgres, pgvectorstore, embedding, retriever]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1475/
note: 개인 학습용 요약. 외부 공유 금지.
---

# PostgreSQL을 벡터 DB로 사용하기

## PostgreSQL을 벡터 DB로 사용하기 요약
pgvector가 포함된 Docker 이미지로 PostgreSQL을 실행하고, Python(langchain-postgres)으로 텍스트 임베딩을 저장한 뒤 retriever와 FastAPI로 유사도 검색을 해 보는 실습이다.

## pgvector란
pgvector는 PostgreSQL에 벡터 저장과 유사도 검색 기능을 더하는 확장 기능이다. pgvector를 설치하면 PostgreSQL을 벡터 DB로도 쓸 수 있어, 메모 같은 일반 데이터와 텍스트 임베딩을 같은 PostgreSQL에서 관리할 수 있다. pgvector는 PostgreSQL 안에서 동작하므로 별도의 벡터 DB 서버를 띄울 필요가 없다.

## pgvector 실습 1단계: pgvector 이미지로 compose.yaml 변경
기존 PostgreSQL 설정에서 `image`만 pgvector 포함 이미지로 바꾼다.
```yaml
name: docker-practice

services:
  db:
    image: pgvector/pgvector:pg17-trixie
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: "1234"
      POSTGRES_DB: docker_prac
    ports:
      - "127.0.0.1:5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```
```bash
docker compose up -d db
```
- `pgvector/pgvector:pg17-trixie`: PostgreSQL 17에 pgvector가 설치된 이미지.
- 서비스 이름, 접속 정보, 데이터 경로, 볼륨 이름(`postgres_data`)을 그대로 두어 기존 PostgreSQL 17 데이터를 계속 쓴다.

## pgvector 실습 2단계: .env에 DB 주소와 Gemini API 키 설정
pgvector 실습에서는 문서와 질문의 임베딩을 Gemini API로 만들므로 `.env`에 유효한 API 키가 필요하다.
```bash
DATABASE_URL=postgresql://postgres:1234@localhost:5433/docker_prac
GEMINI_API_KEY=<GEMINI_API_KEY>
```
- `DATABASE_URL`: 호스트 5433 포트를 통해 Docker PostgreSQL에 접속하는 주소.
- `GEMINI_API_KEY`: 직접 발급받은 키를 넣는다. 노트에는 자리표시자로 적었다.

## pgvector를 Python에서 쓰기: langchain-postgres의 PGVectorStore
Python에서는 `langchain-postgres` 패키지의 `PGVectorStore`로 pgvector에 텍스트와 임베딩을 저장하고 검색한다. 강의 본문에는 `PGVectorStore` 연결 코드가 나오지 않고, 제공 파일 `ingest.py`, `retriever.py`, `main.py` 안에서 사용된다.

## pgvector 실습 3단계: ingest.py로 텍스트 임베딩 등록
`ingest.py`는 Docker 이미지·Compose·볼륨·FastAPI·LangGraph·React에 관한 문자열 6개를 임베딩해 pgvector에 저장한다.
```bash
uv sync
uv run ingest.py
```
문서를 같은 ID로 저장하므로 다시 실행해도 문서가 중복으로 늘어나지 않는다. (`ingest.py` 소스는 강의 본문에 없음)

## pgvector 실습 4단계: retriever.py로 유사도 검색
`retriever.py`는 pgvector에 저장된 텍스트를 검색하는 `search()` 함수를 갖고 있고, 직접 실행하면 `if __name__ == "__main__":` 아래 예제가 돈다.
```bash
uv run retriever.py
```
```python
if __name__ == "__main__":
    query = "컨테이너를 삭제해도 데이터를 유지하려면 어떻게 해야 하나요?"
    for document in search(query):
        print(document.page_content)
```
- `search(query)`: 질문을 임베딩해 비슷한 문서를 찾아 반환한다.
- `document.page_content`: 검색된 문서의 원문 텍스트.

실행하면 관련 텍스트 2개가 출력된다. `query`를 바꿔 다른 검색어도 시험해 본다.

## pgvector 실습 5단계: FastAPI POST /search로 검색
FastAPI의 `POST /search`도 `retriever.py`와 같은 `search()` 함수를 호출한다. 개발 서버를 실행한다.
```bash
uv run fastapi dev main.py
```
`http://localhost:8000/docs`에서 `POST /search`에 다음 JSON을 넣고 실행하면 pgvector에서 찾은 관련 텍스트가 응답으로 온다.
```json
{"query": "컨테이너를 삭제해도 데이터를 유지하려면 어떻게 해야 하나요?"}
```

## PostgreSQL을 벡터 DB로 사용하기 복습 Q&A
- Q. pgvector를 쓰면 별도의 벡터 DB 서버가 필요한가?
  A. 필요 없다. pgvector는 PostgreSQL 확장 기능이라 PostgreSQL 안에서 동작한다.
- Q. 이 실습에서 PostgreSQL 17 + pgvector Docker 이미지 이름은?
  A. `pgvector/pgvector:pg17-trixie`
- Q. 이미지를 pgvector로 바꿔도 기존 데이터를 쓸 수 있는 이유는?
  A. 서비스 이름, 데이터 경로, 볼륨 이름(`postgres_data`)을 그대로 유지해 같은 볼륨을 연결하기 때문이다.
- Q. `ingest.py`를 여러 번 실행해도 문서가 중복되지 않는 이유는?
  A. 같은 ID로 저장하기 때문이다.
- Q. Python에서 pgvector를 다룰 때 쓰는 LangChain 클래스는?
  A. `langchain-postgres`의 `PGVectorStore`
