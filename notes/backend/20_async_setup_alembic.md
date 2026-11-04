---
part: backend
lesson: 비동기 앱 초기 설정과 Alembic
order: 20
source_type: web
tags: [fastapi, async, sqlalchemy, alembic, pydantic-settings, migration, lifespan, postgresql]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1467/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 비동기 앱 초기 설정과 Alembic

## 비동기 앱 초기 설정과 Alembic 요약
fastapi_agent 프로젝트에 Pydantic Settings 기반 환경 설정과 비동기 DB 연결(AsyncSession)을 구성한다. Alembic으로 최초 테이블을 만들고, Post에 created_at 컬럼을 추가하는 변경 마이그레이션까지 적용한 뒤 lifespan으로 엔진 종료를 처리한다.

## fastapi_agent 프로젝트 구조
fastapi_agent 프로젝트의 `src` 안에는 역할별로 세 개의 파이썬 패키지가 있다.
```text
src/
├── fastapi_agent/   # HTTP 요청·응답, 인증, 업무 규칙, 데이터 관리
│   ├── main.py      # 앱 생성과 라우터 등록
│   ├── core/        # 설정, DB 연결, 보안 등 공통 기능
│   └── domains/     # users, posts, comments, chat
├── agents/          # 챗봇·RAG Agent 구성과 실행 (chatbot/, rag/)
└── rag/             # 문서 로딩·분할, 임베딩, 벡터 저장소와 검색
```
- `domains`는 기능 영역(도메인) 단위로 나눠, 한 기능의 코드를 한 폴더에서 찾게 한다.
- 각 도메인 안에서 `router.py`는 요청·응답, `service.py`는 업무 규칙, `repository.py`는 DB 접근, `models.py`는 SQLAlchemy 모델, `schemas.py`는 Pydantic 모델을 맡는다.
- AI 기능이 필요한 Service는 `agents`를 호출하고, Agent는 필요하면 `rag`의 검색을 쓴다.

## FastAPI에서 비동기를 쓰는 이유
FastAPI 비동기의 핵심은 I/O를 기다리는 동안 다른 요청을 처리하는 것이다. 게시글 API는 DB 응답을, AI 채팅 API는 외부 LLM 답변을 기다리는데, `async def` 경로 함수에서 비동기 호출을 `await`하면 그 사이 이벤트 루프가 다른 요청을 처리한다.
```text
요청 A: LLM API 호출 → 답변 대기 ─────────→ 답변 반환
요청 B:                     게시글 조회 → 응답
```
- 비동기로 바꿔도 쿼리 하나나 LLM 답변 생성 자체가 빨라지지는 않는다. 동시 요청 처리에 유리할 뿐이다.

## FastAPI 비동기 적용 시 주의점
FastAPI는 일반 `def` 경로 함수도 스레드 풀에서 돌리므로 여러 요청을 처리할 수 있지만, 동기 I/O를 기다리는 동안 스레드를 점유한다. 비동기 I/O를 쓰면 대기 중에 스레드를 붙잡지 않는다.
- Router를 `async def`로 바꾸고, DB 엔진·세션과 외부 API 클라이언트도 비동기 API를 쓰며, Service·Repository까지 `await`로 연결해야 한다.
- `async def` 안에서 동기 DB·HTTP 호출을 직접 하면 그동안 이벤트 루프 전체가 막힌다.
- FastAPI는 Service나 Repository의 일반 함수를 스레드 풀로 자동으로 보내주지 않는다.

## 비동기 앱 초기 설정 작업 파일 목록
비동기 앱 초기 설정에서 손대는 파일은 fastapi_agent 디렉터리 기준으로 다음과 같다.
- `pyproject.toml`: 의존성과 FastAPI 실행 진입점.
- `.env`: DB 접속 정보와 JWT 설정값.
- `src/fastapi_agent/core/config.py`: 환경변수를 읽고 검증하는 설정 클래스.
- `src/fastapi_agent/core/database.py`: 비동기 엔진·세션.
- `src/fastapi_agent/domains/posts/models.py`: Post에 created_at 추가.
- `alembic.ini`, `alembic/`: Alembic 설정과 마이그레이션.
- `src/fastapi_agent/main.py`: lifespan에서 비동기 엔진 종료.

## 비동기 앱 실습 1단계: 의존성 설치와 DB 생성
fastapi_agent 프로젝트 디렉터리에서 `uv sync`로 의존성을 설치하고, PostgreSQL에 프로젝트 DB를 만든다. 이후 명령도 같은 디렉터리에서 실행한다.
```bash
cd fastapi_agent
uv sync
```
```sql
CREATE DATABASE fastapi_agent;
```
pyproject.toml의 주요 의존성은 다음과 같다.
- 웹·설정: `fastapi[standard]`, `pydantic-settings`, `python-dotenv`(RAG 모듈의 .env 로딩).
- DB: `sqlalchemy[asyncio]`(비동기 ORM), `psycopg[binary]`(PostgreSQL 드라이버), `alembic`(마이그레이션).
- 인증: `pwdlib[argon2]`(비밀번호 해싱), `pyjwt`(JWT).
- AI: `langchain`, `langchain-core`, `langchain-google-genai`(Gemini·임베딩), `langgraph`, `langgraph-checkpoint-postgres`(에이전트 상태 체크포인트).
- RAG: `langchain-community`, `pypdf`, `langchain-text-splitters`, `chromadb`, `langchain-chroma`.

## 비동기 앱 실습 2단계: .env 환경변수 파일 작성
fastapi_agent 프로젝트 디렉터리에 `.env` 파일을 만들어 DB 주소와 JWT 설정을 적는다. `JWT_SECRET_KEY`에는 `openssl rand -hex 32`로 만든 64자리 값을 넣는다.
```bash
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/fastapi_agent
JWT_SECRET_KEY=생성한_64자리_비밀_키
JWT_EXPIRE_MINUTES=3000
DB_ECHO=false
```
- `postgresql+psycopg`: psycopg 드라이버를 쓴다. 이 주소를 `create_async_engine()`에 넘기면 psycopg의 비동기 연결이 사용된다.

## 비동기 앱 실습 3단계: Pydantic Settings 설정 클래스
Pydantic Settings는 `.env` 로딩, 타입 변환, 필수 값 검사를 선언한 타입과 조건대로 처리해 준다. `os.getenv()`만 쓰면 이를 직접 구현해야 한다. 설정이 많아지면 DB·인증·AI 모델처럼 역할별 클래스로 나눌 수도 있다.
```python
# src/fastapi_agent/core/config.py
from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = Field(min_length=1)
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_expire_minutes: int = Field(default=30, gt=0)
    db_echo: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
```
- `SecretStr`: 출력 시 비밀 키 값이 노출되지 않게 한다.
- `@lru_cache`: 설정 객체를 캐시해 `get_settings()`를 여러 번 불러도 같은 객체를 쓴다.

## 비동기 앱 실습 4단계: 비동기 엔진과 세션 구성
비동기 DB 연결은 동기 API를 `sqlalchemy.ext.asyncio`의 비동기 API로 바꾼다.
- `create_engine()` → `create_async_engine()`
- `sessionmaker()` → `async_sessionmaker()`
- `Session` → `AsyncSession`
- `def get_db()` / `with SessionLocal()` → `async def get_db()` / `async with SessionLocal()`
```python
# src/fastapi_agent/core/database.py
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from fastapi_agent.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.db_echo)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as db:
        yield db
```
- `expire_on_commit=False`: 기본값 True면 commit 후 속성이 만료되는데, 응답 모델 생성 중에는 만료된 속성의 재조회를 await할 수 없으므로 False로 두어 읽은 값을 유지한다.

## Alembic과 마이그레이션이란
Alembic은 SQLAlchemy용 DB 마이그레이션 도구이다. 마이그레이션은 테이블 생성이나 컬럼 추가처럼 DB 구조를 바꾸는 작업을 말한다.
- Alembic은 변경 내용을 파일로 기록하고, 순서대로 DB에 적용하며, 어디까지 적용했는지 관리한다.
- 같은 마이그레이션 파일로 개발 DB와 배포 DB에 똑같은 변경을 적용할 수 있다.
- Alembic은 `Base.metadata`와 실제 DB 구조를 비교해 변경 파일을 만든다.

fastapi_agent의 마이그레이션 대상 모델은 다음과 같다.
- `domains/users/models.py`의 User → users
- `domains/posts/models.py`의 Post → posts
- `domains/comments/models.py`의 Comment → comments
- `domains/chat/models.py`의 ChatRoom → chat_rooms, ChatMessage → chat_messages

## Alembic 실습 1단계: 비동기 템플릿으로 초기화
Alembic을 비동기 DB 연결용 템플릿(`-t async`)으로 초기화하면 `alembic.ini`와 `alembic/` 폴더가 생긴다.
```bash
uv run alembic init -t async alembic
```

## Alembic 실습 2단계: env.py에 DB 주소와 모델 메타데이터 연결
Alembic `env.py` 앞부분에서 DB 주소를 설정하고 모든 모델을 import한다.
```python
# alembic/env.py (앞부분)
import asyncio, selectors, sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from fastapi_agent.core.config import get_settings
from fastapi_agent.core.database import Base
from fastapi_agent.domains.chat.models import ChatMessage, ChatRoom
from fastapi_agent.domains.comments.models import Comment
from fastapi_agent.domains.posts.models import Post
from fastapi_agent.domains.users.models import User

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
if config.config_file_name and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata
```
- 모델 모듈을 import해야 테이블이 `Base.metadata`에 등록된다. Base만 import하면 비교 대상이 빠질 수 있다.

## Alembic 실습 3단계: env.py에서 체크포인트 테이블 제외
Alembic의 `env.py`에 `include_name()`을 두어 LangGraph 체크포인터(AsyncPostgresSaver)가 관리하는 테이블을 자동 변경 감지에서 뺀다. 오프라인 모드 설정에도 이 함수를 넘긴다.
```python
# alembic/env.py (include_name, 오프라인 모드)
def include_name(name, type_, parent_names):
    # 체크포인트 테이블은 AsyncPostgresSaver가 관리한다.
    checkpoint_tables = {"checkpoints", "checkpoint_blobs",
                         "checkpoint_writes", "checkpoint_migrations"}
    return type_ != "table" or name not in checkpoint_tables

def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()
```
- 채팅방·메시지 테이블은 모델로 등록해 Alembic이 관리하고, 체크포인트 테이블만 제외한다.

## Alembic 실습 4단계: env.py의 비동기 마이그레이션 실행
Alembic `env.py` 뒷부분은 비동기 엔진 연결에서 `run_sync()`로 마이그레이션을 실행한다. Windows는 SelectorEventLoop를 쓴다.
```python
# alembic/env.py (온라인 모드)
def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata,
                      include_name=include_name)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
elif sys.platform == "win32":
    asyncio.run(run_async_migrations(),
                loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
else:
    asyncio.run(run_async_migrations())
```

## Alembic 실습 5단계: 초기 마이그레이션 생성과 적용
Alembic 초기 마이그레이션은 `alembic/versions/`에 파일이 없는 새 프로젝트에서 생성한다. 이미 초기 파일이 있으면 내용을 확인하고 적용만 한다.
```bash
uv run alembic revision --autogenerate -m "create initial tables"
uv run alembic upgrade head
```
- `revision --autogenerate`: `<revision_id>_create_initial_tables.py` 파일만 만든다. revision ID는 실행마다 다르고, 이 단계에서는 테이블 생성 SQL이 실행되지 않는다.
- `upgrade head`: head는 최신 마이그레이션 버전이다. DB에 아직 적용하지 않은 파일의 `upgrade()`를 순서대로 실행한다.

## Alembic 실습 6단계: Post 모델에 created_at 추가
Alembic 변경 마이그레이션 예시로 posts 테이블에 생성 시각 컬럼을 추가한다. Post 모델 파일에 import를 추가하고 클래스에 `created_at`을 넣는다.
```python
# src/fastapi_agent/domains/posts/models.py (추가 부분)
from datetime import datetime
from sqlalchemy import DateTime, func

class Post(Base):
    # 기존 컬럼과 관계는 유지
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
```
- `server_default=func.now()`: INSERT에서 값을 생략하면 DB가 현재 트랜잭션 시작 시각을 채운다.
- 모델을 고쳐도 DB 구조는 자동으로 바뀌지 않으므로 마이그레이션이 필요하다.

## Alembic 실습 7단계: 변경 마이그레이션 생성·검토·적용
Alembic 변경 마이그레이션은 초기 파일을 그대로 두고 새 파일로 만든다. 새 파일의 `down_revision`은 초기 마이그레이션 ID를 가리킨다.
```bash
uv run alembic revision --autogenerate -m "add post created_at"
```
생성된 `upgrade()`에 created_at 추가 코드가 있는지, 의도하지 않은 변경·삭제가 없는지 확인한다.
```python
def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
```
```bash
uv run alembic upgrade head
```
- 적용 후 DB 관리 도구에서 posts 테이블에 created_at 컬럼이 생겼는지 본다.

## 비동기 앱 실습 5단계: lifespan으로 DB 엔진 정리
FastAPI lifespan은 앱이 요청을 받기 전에 공용 자원을 준비하고 종료 시 정리하는 흐름으로, 요청마다 도는 Router나 `get_db()`와 달리 앱 시작·종료에 한 번 실행된다. 여러 요청이 공유하는 비동기 엔진의 연결 풀을 종료 시 정리한다.
```python
# src/fastapi_agent/main.py (앱 생성 부분)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_agent.core.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await engine.dispose()

app = FastAPI(lifespan=lifespan)
```
- `yield` 전: 공용 자원 준비(이 예제는 없음).
- `yield` 동안: FastAPI가 요청을 처리한다.
- 종료 시: `await engine.dispose()`로 연결 풀을 정리한다.
- 테이블 생성·변경은 앱 시작 코드가 아니라 Alembic 명령으로 한다.

## 비동기 앱 실습 6단계: 실행 진입점 설정과 서버 실행
fastapi_agent의 pyproject.toml에 FastAPI 앱 위치를 지정하면 `fastapi dev`를 인자 없이 실행할 수 있다.
```toml
[tool.fastapi]
entrypoint = "fastapi_agent.main:app"
```
```bash
uv run fastapi dev
```
- `fastapi_agent.main`은 `src/fastapi_agent/main.py`이고 `app`은 그 안의 FastAPI 객체다. `uv sync`로 패키지가 설치되므로 경로에 `src`를 넣지 않는다.
- 서버는 `http://127.0.0.1:8000`에서 뜨고 코드 변경 시 자동 재시작된다. DB 마이그레이션을 먼저 적용한 뒤 실행한다.

## 비동기 앱 초기 설정과 Alembic 복습 Q&A
- Q. FastAPI를 비동기로 바꾸면 LLM 답변이 빨라지나?
  A. 아니다. 기다리는 동안 다른 요청을 처리할 수 있어 동시 처리에 유리할 뿐, 개별 응답 시간은 줄지 않는다.
- Q. 비동기 SQLAlchemy 세션에서 `expire_on_commit=False`를 쓰는 이유는?
  A. commit 후 속성이 만료되면 응답 모델 생성 중 재조회를 await할 수 없으므로, 읽은 값을 유지하려고 쓴다.
- Q. Alembic `env.py`에서 모델 모듈을 import해야 하는 이유는?
  A. import해야 테이블 정보가 `Base.metadata`에 등록되어 autogenerate가 비교할 수 있다.
- Q. Alembic에서 마이그레이션 파일 생성과 DB 적용 명령은?
  A. 생성은 `uv run alembic revision --autogenerate -m "메시지"`, 적용은 `uv run alembic upgrade head`.
- Q. FastAPI lifespan에서 `engine.dispose()`를 호출하는 이유는?
  A. 여러 요청이 공유한 비동기 엔진의 연결 풀을 앱 종료 시 정리하기 위해서다.
