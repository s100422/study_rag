---
part: backend
lesson: DB를 연동한 게시판 구현
order: 8
source_type: web
tags: [fastapi, sqlalchemy, postgresql, session, depends, transaction, lifespan, dirty-checking]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1448/
note: 개인 학습용 요약. 외부 공유 금지.
---

# DB를 연동한 게시판 구현

## DB를 연동한 게시판 구현 요약
DB 연동 게시판 실습은 게시글을 메모리 리스트 대신 PostgreSQL에 저장해, 서버를 재시작해도 데이터가 남는 게시판 CRUD API를 SQLAlchemy와 Router → Service → Repository 구조로 만드는 것이다. 코드는 `fastapi_ai/fastapi_basic/mysite_db/`에 둔다.

## DB 게시판 API 목록
DB 연동 게시판의 기본 주소는 `http://127.0.0.1:8000`이고, `{id}`에는 게시글 ID가 들어간다.
- `POST /posts-db`: 게시글 등록, 201
- `GET /posts-db`: 게시글 목록 조회, 200
- `GET /posts-db/{id}`: 게시글 상세 조회, 200
- `PUT /posts-db/{id}`: 제목과 내용 수정, 200
- `DELETE /posts-db/{id}`: 게시글 삭제, 204

## DB 게시판 프로젝트 구조
DB 연동 게시판은 `fastapi_basic` 아래에 공통 DB 설정(`database.py`, `.env`)과 계층별 폴더를 둔다.
```text
fastapi_basic/
├── .env
├── database.py
├── main.py
└── mysite_db/
    ├── models/
    │   ├── __init__.py
    │   └── post.py
    ├── schemas/post.py
    ├── repositories/post_repository.py
    ├── services/post_service.py
    └── routers/post_router.py
```

## DB 게시판 실습 1단계: 라이브러리 설치와 DB 준비
DB 연동 게시판에 필요한 라이브러리를 `fastapi_ai/fastapi_basic`에서 설치한다.
```bash
uv add sqlalchemy psycopg[binary] python-dotenv
```
- `sqlalchemy`: ORM 라이브러리
- `psycopg[binary]`: PostgreSQL 드라이버
- `python-dotenv`: `.env` 파일의 환경변수를 읽는다.

PostgreSQL에서 데이터베이스를 만든다.
```sql
CREATE DATABASE mysite;
```
`fastapi_basic/.env`에 자기 계정·비밀번호로 접속 주소를 적는다.
```bash
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/mysite
```

## SQLAlchemy Engine과 연결 풀
SQLAlchemy의 Engine은 DB 연결과 SQL 실행을 관리하는 객체이다. `DATABASE_URL`로 어떤 DB에 어떤 드라이버로 붙을지 정한다.

연결 풀(Connection Pool)은 DB 연결을 보관해 두었다가 재사용하는 공간이다. Engine은 연결 풀을 써서 작업할 때마다 연결을 새로 만드는 비용을 줄인다.

## SQLAlchemy 세션(Session)
SQLAlchemy 세션은 DB 작업을 수행하고, 파이썬 객체의 변경 사항을 추적하는 객체이다. 게시판 코드의 `db: Session`에서 `db`가 세션이다.

DB 게시판에서는 요청마다 세션을 하나 만들고, 같은 세션을 Router → Service → Repository로 전달한다.

## SQLAlchemy Base와 테이블 정보
SQLAlchemy의 `DeclarativeBase`는 파이썬 클래스를 DB 테이블과 연결하는 모델의 기반 클래스이다. 이를 상속한 `Base`를 만들고, 게시글 모델은 `class Post(Base)`로 선언한다. 이렇게 선언한 모델들의 테이블 이름·컬럼·제약 조건은 `Base.metadata`에 모인다.

## DB 게시판 실습 2단계: database.py 작성
DB 게시판의 `database.py`에는 DB 연결과 공통 모델 기반을 작성한다.
```python
# database.py
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).with_name(".env"))
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(".env 파일에 DATABASE_URL을 설정하세요.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass
```
- `load_dotenv(Path(__file__).with_name(".env"))`: `database.py`와 같은 폴더의 `.env`를 읽는다.
- `create_engine(DATABASE_URL)`: Engine(연결 풀 포함)을 만든다.
- `sessionmaker(bind=engine)`: 호출할 때마다 새 세션을 만드는 팩토리 `SessionLocal`을 만든다.

## DB 게시판 실습 3단계: SQLAlchemy Post 모델
DB 게시판의 `Post` 클래스는 `posts` 테이블에 대응하고, `Post` 객체 하나가 게시글 한 행이다.
```python
# mysite_db/models/post.py
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
```
- `Mapped[T]`: 속성의 파이썬 타입
- `mapped_column()`: DB 컬럼의 자료형과 제약 조건
- `primary_key=True`: 기본키, `autoincrement=True`: 숫자 기본키 자동 생성
- `String(50)`: 최대 50자 문자열, `Text`: 긴 텍스트
- `nullable=False`: NULL 불허

## DB 게시판 실습 4단계: models/__init__.py에 모델 등록
DB 게시판의 `models/__init__.py`에서 모델을 import한다. 새 모델을 만들면 여기에 추가한다.
```python
# mysite_db/models/__init__.py
from .post import Post
```
- `main.py`에서 `from mysite_db import models`를 하면 이 파일이 실행되어 `Post`의 테이블 정보가 `Base.metadata`에 등록된다.

## DB 게시판 실습 5단계: lifespan으로 테이블 생성
FastAPI의 lifespan은 애플리케이션 시작·종료 때 실행할 코드를 두는 곳이다. DB 게시판은 시작할 때 테이블을 만들고, 종료할 때 연결 풀을 정리한다.
```python
# main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import Base, engine
from mysite_db import models

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        yield
    finally:
        engine.dispose()

app = FastAPI(lifespan=lifespan)
```
- `yield` 이전: 요청을 받기 전에 테이블을 준비한다. `yield` 동안 서버가 요청을 처리한다.
- `engine.dispose()`: 서버 종료 시 연결 풀을 정리한다.
- `create_all()`: 없는 테이블만 생성한다. 이미 있는 테이블 구조는 바꾸지 않는다.

## DB 게시판 실습 6단계: get_db()로 요청별 세션 관리
DB 게시판의 `get_db()`는 lifespan과 달리 요청마다 세션을 준비하고 정리한다. `database.py`에 추가한다.
```python
# database.py
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
- `SessionLocal()`: 이 요청에서 쓸 새 세션을 만든다.
- `yield db`: 세션을 넘기고 실행을 멈춘다. FastAPI가 요청 처리를 끝내면 나머지 코드가 실행된다.
- `db.close()`: 세션을 닫는다. `finally`라서 예외가 나도 실행된다.
- `get_db`는 Router에서 `Depends()`로 연결한다.

## FastAPI 의존성 주입(Depends)이란
FastAPI에서 의존성은 기능 실행에 필요한 객체나 기능(예: DB 세션)이고, 의존성 주입은 그것을 외부에서 준비해 함수에 넘겨주는 방식이다. DB 게시판에서는 FastAPI가 `get_db()`로 세션을 만들어 Router 함수에 넣어 준다.

Router마다 `SessionLocal()`과 `try/finally`를 반복하지 않고 의존성 주입을 쓰면 좋은 점은 다음과 같다.
- 중복 감소: 세션 생성·종료를 `get_db()` 한곳에서 관리해 정리 코드 누락을 줄인다.
- 역할 분리: Router는 세션 준비 방법을 몰라도 받은 `db`로 Service를 호출하면 된다.
- 테스트 편의: 테스트 때 `get_db`를 테스트용 세션을 주는 함수로 교체할 수 있다.

## FastAPI Annotated와 Depends(get_db) 선언
FastAPI Router 함수에서 세션을 주입받는 매개변수는 다음처럼 선언한다.
```python
db: Annotated[Session, Depends(get_db)]
```
- `Annotated[타입, 추가 정보]`: 타입에 추가 정보를 붙이는 문법이다.
- `db`: 세션을 받는 매개변수
- `Session`: 받을 객체의 타입. 이 선언만으로 세션이 생기지는 않는다.
- `Depends(get_db)`: FastAPI가 `get_db`를 실행해 준비한 값을 넣도록 지정한다. 괄호 없이 함수 자체를 넘긴다.

등록 API의 `data: PostCreate`는 클라이언트가 보낸 본문(제목·내용)을 검증한 값이고, `db`는 서버가 준비한 세션이다.

## DB 게시판 실습 7단계: Router 작성 (등록·목록)
DB 게시판 Router는 주입받은 `db`를 Service에 그대로 넘긴다. 아래는 `post_router.py`의 앞부분이다.
```python
# mysite_db/routers/post_router.py
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from mysite_db.schemas.post import PostCreate, PostDetailResponse, PostListResponse
from mysite_db.services.post_service import post_service

router = APIRouter(prefix="/posts-db", tags=["mysite_db"])

@router.post("", response_model=PostDetailResponse, status_code=status.HTTP_201_CREATED)
def create_post(data: PostCreate, db: Annotated[Session, Depends(get_db)]):
    return post_service.create_post(db, data)

@router.get("", response_model=list[PostListResponse])
def get_posts(db: Annotated[Session, Depends(get_db)]):
    return post_service.get_posts(db)
```

## DB 게시판 실습 7단계: Router 작성 (상세·수정·삭제)
DB 게시판 `post_router.py`의 나머지 엔드포인트도 `db: Annotated[Session, Depends(get_db)]`로 세션을 받아 `post_service`에 넘긴다.
```python
@router.get("/{id}", response_model=PostDetailResponse)
def get_post(id: int, db: Annotated[Session, Depends(get_db)]):
    return post_service.get_post(db, id)

@router.put("/{id}", response_model=PostDetailResponse)
def update_post(id: int, data: PostCreate, db: Annotated[Session, Depends(get_db)]):
    return post_service.update_post(db, id, data)

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(id: int, db: Annotated[Session, Depends(get_db)]):
    post_service.delete_post(db, id)
```
- 수정도 등록과 같은 `PostCreate` 스키마를 요청 본문으로 쓴다.
- 삭제는 204이므로 아무것도 반환하지 않는다.

## DB 게시판 실습 8단계: Pydantic 스키마
DB 게시판의 Pydantic 스키마는 요청을 검증하고 `response_model`의 응답 형식을 정한다. `PostCreate`는 등록·수정 요청용이며 제목 1~50자, 내용 1자 이상이다.
```python
# mysite_db/schemas/post.py
from pydantic import BaseModel, ConfigDict, Field

class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)

class PostDetailResponse(BaseModel):
    id: int
    title: str
    content: str

    model_config = ConfigDict(from_attributes=True)

class PostListResponse(BaseModel):
    id: int
    title: str

    model_config = ConfigDict(from_attributes=True)
```
- `from_attributes=True`: SQLAlchemy 객체의 `post.id`, `post.title` 같은 속성에서 응답 필드를 읽게 한다.

## SQLAlchemy with db.begin() 트랜잭션
DB 게시판 Service는 등록·수정·삭제를 각각 `with db.begin():` 블록으로 묶어 하나의 트랜잭션으로 처리한다.
- 블록이 정상 종료되면 자동으로 commit한다.
- 블록 안이나 commit 중 예외가 나면 자동으로 rollback하고 예외를 그대로 전달한다.
- 같은 블록에서 같은 세션으로 Repository를 여러 번 호출해도 변경은 함께 확정되거나 함께 취소된다.

조회도 트랜잭션을 자동으로 시작할 수 있기 때문에, 수정·삭제 대상을 찾는 조회는 `with db.begin():` 안에 둔다. 등록·수정은 블록이 끝나 commit이 된 뒤 객체를 반환한다.

## DB 게시판 실습 9단계: Service 작성 (등록·조회)
DB 게시판 `PostService`의 등록·목록·상세 조회 부분이다. 상세 조회에서 게시글이 없으면 404를 낸다.
```python
# mysite_db/services/post_service.py
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from mysite_db.models.post import Post
from mysite_db.repositories.post_repository import post_repository
from mysite_db.schemas.post import PostCreate

class PostService:
    def create_post(self, db: Session, data: PostCreate):
        with db.begin():
            new_post = Post(title=data.title, content=data.content)
            post_repository.save(db, new_post)
        return new_post

    def get_posts(self, db: Session):
        return post_repository.find_all(db)

    def get_post(self, db: Session, id: int):
        post = post_repository.find_by_id(db, id)
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="게시글을 찾을 수 없습니다.",
            )
        return post
```

## DB 게시판 실습 9단계: Service 작성 (수정·삭제)
DB 게시판 `PostService`의 수정·삭제는 `with db.begin():` 안에서 `get_post()`로 대상을 찾고(없으면 404) Repository를 호출한다. 클래스 끝에서 인스턴스 `post_service`를 만든다.
```python
    def update_post(self, db: Session, id: int, data: PostCreate):
        with db.begin():
            post = self.get_post(db, id)
            updated_post = post_repository.update(db, post, data)
        return updated_post

    def delete_post(self, db: Session, id: int):
        with db.begin():
            post = self.get_post(db, id)
            post_repository.delete(db, post)

post_service = PostService()
```
- 404 예외가 블록 안에서 나면 rollback되어 아무것도 바뀌지 않는다.

## DB 게시판 실습 10단계: Repository 작성
DB 게시판 Repository는 Service에서 받은 세션으로 저장·조회·수정·삭제만 하고, commit은 하지 않는다.
```python
# mysite_db/repositories/post_repository.py
from sqlalchemy import select
from sqlalchemy.orm import Session

from mysite_db.models.post import Post
from mysite_db.schemas.post import PostCreate

class PostRepository:
    def save(self, db: Session, new_post: Post):
        db.add(new_post)
        return new_post

    def find_all(self, db: Session):
        return db.scalars(select(Post).order_by(Post.id)).all()

    def find_by_id(self, db: Session, id: int):
        return db.get(Post, id)

    def update(self, db: Session, post: Post, data: PostCreate):
        post.title = data.title
        post.content = data.content
        return post

    def delete(self, db: Session, post: Post):
        db.delete(post)

post_repository = PostRepository()
```

## SQLAlchemy 변경 감지(Dirty Checking)
SQLAlchemy 변경 감지는 세션이 관리하는 객체의 속성 변경을 알아채 DB 수정에 반영하는 기능이다. DB 게시판에서 `db.get(Post, id)`로 가져온 `post`는 세션이 관리하는 객체라서, Repository의 `update()`는 속성만 바꾼다.
```python
post.title = data.title
post.content = data.content
```
- 다시 `db.add()`하거나 UPDATE문을 쓸 필요가 없다.
- 속성 변경: 세션이 변경을 추적한다.
- flush: 변경을 UPDATE SQL로 실행하지만 아직 확정하지 않는다.
- commit: 트랜잭션을 확정한다. commit에 flush가 포함되므로 `with db.begin():` 블록이 끝나면 저장된다.

## DB 게시판 실습 11단계: main.py에 Router 등록
DB 게시판 Router를 lifespan이 있는 `main.py`에 등록한다. 강의의 `main.py`는 이전 실습(mysite, mysite2, mysite3, mysite4)의 Router도 함께 등록하지만, 여기서는 DB 게시판 관련 부분만 적는다.
```python
# main.py (lifespan 정의는 5단계와 동일)
from database import Base, engine
from mysite_db import models
from mysite_db.routers.post_router import router as db_router

app = FastAPI(lifespan=lifespan)
app.include_router(db_router)

@app.get("/")
def get_root():
    return {"Hello": "World"}
```

## DB 게시판 실습 12단계: 서버 실행과 동작 확인
DB 게시판은 PostgreSQL을 켜고 `.env`를 설정한 뒤 서버를 실행한다.
```bash
uv run fastapi dev main.py
```
`http://127.0.0.1:8000/docs`의 `mysite_db` 그룹에서 아래 데이터로 게시글을 등록한다.
```json
{
  "title": "첫 번째 게시글",
  "content": "데이터베이스에 저장할 내용입니다."
}
```
- 서버를 재시작해도 게시글이 조회되는지 확인한다.
- 수정 후 변경된 내용이 조회되는지 확인한다.
- 삭제 후 상세 조회가 404인지 확인한다.

## DB를 연동한 게시판 구현 복습 Q&A
- Q. DB 게시판에서 `get_db()`의 `finally: db.close()`는 왜 필요한가?
  A. 요청 처리 중 예외가 나도 세션을 반드시 닫기 위해서이다.
- Q. `Depends(get_db)`에 왜 괄호 없이 `get_db`를 넘기나?
  A. FastAPI가 요청마다 그 함수를 직접 실행해 `yield`된 세션을 넣어 주기 때문이다.
- Q. DB 게시판 Repository의 `update()`가 속성만 바꿔도 저장되는 이유는?
  A. 세션이 변경 감지(dirty checking)로 변경을 추적하고, `with db.begin():` 종료 시 commit(flush 포함)되기 때문이다.
- Q. `Base.metadata.create_all()`은 기존 테이블 구조를 바꾸나?
  A. 아니다. 없는 테이블만 생성한다.
- Q. 응답 스키마에 `from_attributes=True`를 두는 이유는?
  A. SQLAlchemy 객체의 속성에서 응답 필드 값을 읽어 오기 위해서이다.
