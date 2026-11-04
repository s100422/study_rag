---
part: backend
lesson: 1:N 관계
order: 10
source_type: web
tags: [sqlalchemy, one-to-many, relationship, foreignkey, cascade, type-checking, nested-response, fastapi]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1446/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 1:N 관계

## 1:N 관계 요약
1:N 관계 레슨은 게시글 하나에 댓글 여러 개가 달리는 구조를 SQLAlchemy의 `ForeignKey`와 `relationship()`으로 모델링하고, 댓글 CRUD API와 댓글을 포함한 게시글 상세 응답을 만든다. 코드는 `fastapi_ai/fastapi_basic/mysite_one_to_many/`에 있다.

## 1:N 관계 게시글·댓글 API 목록
1:N 관계 예제의 기본 주소는 `http://127.0.0.1:8000`이다.
- `POST /posts-1n`: 게시글 등록, 201
- `GET /posts-1n`: 게시글 목록, 200
- `GET /posts-1n/{post_id}`: 댓글 포함 상세 조회, 200
- `PUT /posts-1n/{post_id}`: 게시글 수정, 200
- `DELETE /posts-1n/{post_id}`: 게시글과 그 댓글 삭제, 204
- `POST /posts-1n/{post_id}/comments`: 댓글 등록, 201
- `PUT /posts-1n/{post_id}/comments/{comment_id}`: 댓글 수정, 200
- `DELETE /posts-1n/{post_id}/comments/{comment_id}`: 댓글 삭제, 204

## 1:N 관계 예제 프로젝트 구조와 테이블
1:N 관계 예제는 게시글 모델 `Post1N`(테이블 `post_1n`)과 댓글 모델 `Comment1N`(테이블 `comment_1n`)을 쓰며, 계층마다 게시글·댓글 파일을 나눈다.
```text
mysite_one_to_many/
├── models/  __init__.py, post_1n.py, comment_1n.py
├── schemas/  post.py, comment.py
├── repositories/  post_repository.py, comment_repository.py
├── services/  post_service.py, comment_service.py
└── routers/post_router.py
```
```text
post_1n (1)                    comment_1n (N)
┌─────────────┐               ┌─────────────┐
│ id (PK)     │◀──────────────│ post_id (FK)│
│ title       │               │ id (PK)     │
│ content     │               │ content     │
└─────────────┘               └─────────────┘
```

## 1:N 관계 실습 1단계: 게시글 모델 Post1N
1:N 관계의 "1" 쪽인 게시글 모델은 댓글 목록을 `relationship()`으로 가진다.
```python
# mysite_one_to_many/models/post_1n.py
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from .comment_1n import Comment1N

class Post1N(Base):
    __tablename__ = "post_1n"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    comments: Mapped[list["Comment1N"]] = relationship(
        "Comment1N",
        back_populates="post",
        cascade="all",
        order_by="Comment1N.id",
    )
```
- `Mapped[list["Comment1N"]]`: 게시글 하나에 댓글이 여러 개이므로 리스트로 선언한다.

## 1:N 관계 실습 2단계: 댓글 모델 Comment1N
1:N 관계의 "N" 쪽인 댓글 모델은 외래키 컬럼 `post_id`와 게시글 객체 속성 `post`를 가진다.
```python
# mysite_one_to_many/models/comment_1n.py
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from .post_1n import Post1N

class Comment1N(Base):
    __tablename__ = "comment_1n"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(String(200), nullable=False)
    post_id: Mapped[int] = mapped_column(ForeignKey("post_1n.id"), nullable=False)

    post: Mapped["Post1N"] = relationship("Post1N", back_populates="comments")
```
- `post_id`: DB에 실제 저장되는 컬럼. 여러 댓글이 같은 `post_id`를 가질 수 있어 1:N이 된다.
- `ForeignKey("post_1n.id")`: 클래스명이 아니라 테이블명.컬럼명을 쓴다.
- `nullable=False`: 모든 댓글은 소속 게시글이 있어야 한다.
- `post`: 연결된 게시글 객체에 접근하는 속성(컬럼 아님).

## SQLAlchemy relationship과 ForeignKey의 차이
SQLAlchemy 1:N 관계에서 `ForeignKey`와 `relationship()`은 역할이 다르다.
- `post_id = mapped_column(ForeignKey("post_1n.id"))`: DB에 게시글 ID 컬럼과 외래키 제약을 만든다.
- `post = relationship("Post1N", ...)`: 댓글에서 게시글 객체로 가는 파이썬 속성이다.
- `comments = relationship("Comment1N", ...)`: 게시글에서 댓글 목록으로 가는 파이썬 속성이다.

`relationship()`은 DB에 컬럼·외래키를 만들지 않는다. 외래키만으로도 DB 관계는 유지되지만, 객체로 탐색하려면 관계 속성이 필요하다. SQLAlchemy는 외래키 정보로 어떤 게시글과 댓글이 연결되는지 판단한다.
```python
comment.post_id      # 소속 게시글 ID
comment.post.title   # 소속 게시글 객체의 제목
post.comments        # 게시글의 댓글 객체 목록
```

## SQLAlchemy relationship 인자: back_populates, cascade, order_by
SQLAlchemy 게시글 모델의 `comments = relationship(...)`에 쓴 인자의 뜻은 다음과 같다.
```python
comments: Mapped[list["Comment1N"]] = relationship(
    "Comment1N",
    back_populates="post",
    cascade="all",
    order_by="Comment1N.id",
)
```
- `"Comment1N"`: 연결할 모델 클래스 이름(테이블명 `comment_1n`과 구분).
- `back_populates="post"`: 상대 모델의 관계 속성 이름. `Post1N.comments`와 `Comment1N.post`를 양방향으로 연결한다. 양방향은 필요할 때 선택한다.
- `cascade="all"`: 게시글에 하는 세션 작업을 댓글에도 전달한다. 게시글 삭제 시 댓글도 삭제된다.
- `order_by="Comment1N.id"`: 댓글 목록을 ID 순으로 정렬한다.

## SQLAlchemy cascade 옵션과 게시글 삭제
SQLAlchemy의 cascade는 부모 객체에 한 작업을 연결된 자식에 전달하는 설정이다.
- `save-update`: 연결된 객체도 세션에 추가
- `delete`: 부모 삭제 시 자식도 삭제
- `delete-orphan`: 부모와 관계가 끊긴 자식 삭제
- `all`: save-update, merge, refresh-expire, expunge, delete를 포함(delete-orphan은 미포함)

1:N 예제의 `Post1N.comments`는 `cascade="all"`이라 `db.delete(post)` 시 그 게시글의 댓글도 함께 삭제된다. 반대로 `db.delete(comment)`는 그 댓글만 지우고 게시글은 남긴다.

## Python TYPE_CHECKING으로 순환 import 피하기
1:N 관계의 두 모델은 타입 힌트에서 서로를 참조하므로, 파일 맨 위에서 서로 import하면 순환 import가 생길 수 있다(`post_1n.py` → `comment_1n.py` → 아직 정의되지 않은 `Post1N`을 가져오려 함).

`typing.TYPE_CHECKING`은 타입 검사 도구가 분석할 때는 `True`, 실제 실행 때는 `False`인 상수이다. 타입 검사는 코드를 실행하지 않고 타입 힌트를 분석해 잘못된 사용을 찾는 과정이다.
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .comment_1n import Comment1N
```
- 타입 검사 도구는 이 import로 `Comment1N`의 타입·속성을 파악한다.
- 실행 시에는 import를 건너뛰므로 순환이 생기지 않는다.

## SQLAlchemy 모델의 문자열 타입 힌트와 모델 등록
1:N 관계 모델에서 `TYPE_CHECKING` import는 실행 시 이름을 만들지 않으므로 타입 힌트에 따옴표를 붙여 참조를 미룬다.
```python
comments: Mapped[list["Comment1N"]]
```
- `"Comment1N"`은 댓글 클래스 이름이다(문자열 목록 `list[str]`이란 뜻이 아님). 따옴표 없이 쓰면 클래스 정의 시점에 이름이 없어 오류가 날 수 있다.
- `relationship("Comment1N", ...)`의 문자열도 SQLAlchemy가 나중에 등록된 모델에서 찾아 연결한다.

실행 시 모델 등록은 `models/__init__.py`에서 실제 import로 한다.
```python
# mysite_one_to_many/models/__init__.py
from .post_1n import Post1N
from .comment_1n import Comment1N
```
- `main.py`의 `from mysite_one_to_many import models as one_to_many_models`가 이 파일을 실행해 두 모델을 같은 `Base`에 등록한다.

## 1:N 관계 실습 3단계: 댓글 Pydantic 스키마
1:N 관계 예제의 댓글 스키마는 요청용 `CommentCreate`와 응답용 `CommentResponse`이다.
```python
# mysite_one_to_many/schemas/comment.py
from pydantic import BaseModel, ConfigDict, Field

class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=200)

class CommentResponse(BaseModel):
    id: int
    content: str

    model_config = ConfigDict(from_attributes=True)
```
- `CommentCreate`: 등록·수정 요청에 쓰며 내용은 1~200자.
- 소속 게시글 ID는 요청 본문이 아니라 URL 경로(`post_id`)로 받는다.

## 1:N 관계 실습 4단계: 댓글을 포함한 게시글 응답 스키마
1:N 관계 예제의 `PostDetailResponse`는 댓글 응답 목록을 필드로 가진다.
```python
# mysite_one_to_many/schemas/post.py
from pydantic import BaseModel, ConfigDict, Field

from mysite_one_to_many.schemas.comment import CommentResponse

class PostDetailResponse(BaseModel):
    id: int
    title: str
    content: str
    comments: list[CommentResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
```
- `Field(default_factory=list)`: 값이 없을 때 새 빈 리스트를 만든다. 댓글 없는 게시글은 `comments: []`.

## FastAPI 중첩 응답과 SQLAlchemy 지연 로딩
1:N 관계 예제의 상세 조회 Router는 `response_model=PostDetailResponse`로 Service가 준 `Post1N` 객체를 반환한다. `from_attributes=True` 덕분에 Pydantic이 `id`, `title`, `content`, `comments`를 읽고, 각 `Comment1N`도 `CommentResponse`로 변환한다. 응답 안에 댓글 응답 목록이 들어가는 이 형태를 중첩 응답이라고 한다.

이 예제의 `relationship()`은 기본값인 지연 로딩(lazy loading)이다. 게시글 조회 때 댓글을 같이 가져오지 않고, `post.comments`에 처음 접근할 때 추가 SELECT로 댓글을 읽는다. 그래서 응답을 만드는 중에 댓글 조회가 일어날 수 있고, 그때 세션이 열려 있어야 한다.

## 1:N 관계 실습 5단계: 댓글 Router 등록 API
1:N 관계 예제에서 댓글은 게시글에 속하므로 `/posts-1n/{post_id}/comments` 경로를 쓴다. `post_router.py`의 댓글 등록 부분이다.
```python
# mysite_one_to_many/routers/post_router.py
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from mysite_one_to_many.schemas.comment import CommentCreate, CommentResponse
from mysite_one_to_many.services.comment_service import comment_service

router = APIRouter(prefix="/posts-1n", tags=["mysite_one_to_many"])

@router.post("/{post_id}/comments", response_model=CommentResponse,
             status_code=status.HTTP_201_CREATED)
def create_comment(post_id: int, data: CommentCreate,
                   db: Annotated[Session, Depends(get_db)]):
    return comment_service.create_comment(db, post_id, data)
```
- `post_id`는 URL 경로에서, `data`는 요청 본문에서, `db`는 `get_db` 의존성에서 받는다.

## 1:N 관계 실습 5단계: 댓글 Router 수정·삭제 API
1:N 관계 예제 `post_router.py`의 댓글 수정·삭제는 경로에 `post_id`와 `comment_id`를 모두 받아 `comment_service`에 넘긴다.
```python
@router.put("/{post_id}/comments/{comment_id}", response_model=CommentResponse)
def update_comment(post_id: int, comment_id: int, data: CommentCreate,
                   db: Annotated[Session, Depends(get_db)]):
    return comment_service.update_comment(db, post_id, comment_id, data)

@router.delete("/{post_id}/comments/{comment_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(post_id: int, comment_id: int,
                   db: Annotated[Session, Depends(get_db)]):
    comment_service.delete_comment(db, post_id, comment_id)
```

## 1:N 관계 실습 6단계: 댓글 Service 등록 메서드
1:N 관계 예제의 `CommentService.create_comment()`는 게시글을 먼저 찾고 `post=post`로 댓글을 연결한다.
```python
# mysite_one_to_many/services/comment_service.py
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from mysite_one_to_many.models.comment_1n import Comment1N
from mysite_one_to_many.repositories.comment_repository import comment_repository
from mysite_one_to_many.schemas.comment import CommentCreate
from mysite_one_to_many.services.post_service import post_service

class CommentService:
    def create_comment(self, db: Session, post_id: int, data: CommentCreate):
        with db.begin():
            post = post_service.get_post(db, post_id)
            new_comment = Comment1N(content=data.content, post=post)
            comment_repository.save(db, new_comment)
        return new_comment
```
- 게시글이 없으면 `post_service.get_post()`가 404를 내서 댓글이 등록되지 않는다.
- `post=post`로 연결하면 저장 시 SQLAlchemy가 게시글 ID를 `post_id`에 채운다.

## 1:N 관계 실습 6단계: 댓글 Service 수정·삭제 메서드
1:N 관계 예제의 `CommentService` 수정·삭제는 `with db.begin():` 안에서 `_get_verified_comment()`로 댓글을 검증한 뒤 Repository를 호출한다.
```python
    def update_comment(self, db: Session, post_id: int, comment_id: int,
                       data: CommentCreate):
        with db.begin():
            comment = self._get_verified_comment(db, post_id, comment_id)
            updated_comment = comment_repository.update(db, comment, data)
        return updated_comment

    def delete_comment(self, db: Session, post_id: int, comment_id: int):
        with db.begin():
            comment = self._get_verified_comment(db, post_id, comment_id)
            comment_repository.delete(db, comment)
```
- 블록이 정상 종료되면 commit, 검증 실패(404) 등 예외가 나면 rollback된다.
- 수정 메서드는 commit이 끝난 뒤 댓글 객체를 반환한다.

## 1:N 관계 실습 6단계: 댓글 소속 검증 _get_verified_comment
1:N 관계 예제의 `CommentService._get_verified_comment()`는 댓글 ID뿐 아니라 URL의 `post_id`와 댓글의 `post_id`도 비교한다.
```python
    def _get_verified_comment(self, db: Session, post_id: int, comment_id: int):
        comment = comment_repository.find_by_id(db, comment_id)
        if comment is None or comment.post_id != post_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 게시글의 댓글을 찾을 수 없습니다.",
            )
        return comment

comment_service = CommentService()
```
- `comment is None`이면 `or` 오른쪽을 평가하지 않아 None의 `post_id` 접근을 피한다.
- 댓글이 없거나 다른 게시글 소속이면 404를 내서 수정·삭제가 진행되지 않는다.

## 1:N 관계 실습 7단계: 댓글 Repository
1:N 관계 예제의 `CommentRepository`는 세션으로 저장·조회·수정·삭제만 하고 commit은 하지 않는다. 확정은 Service의 트랜잭션이 끝날 때 일어난다.
```python
# mysite_one_to_many/repositories/comment_repository.py
from sqlalchemy.orm import Session

from mysite_one_to_many.models.comment_1n import Comment1N
from mysite_one_to_many.schemas.comment import CommentCreate

class CommentRepository:
    def save(self, db: Session, new_comment: Comment1N):
        db.add(new_comment)
        return new_comment

    def find_by_id(self, db: Session, comment_id: int):
        return db.get(Comment1N, comment_id)

    def update(self, db: Session, comment: Comment1N, data: CommentCreate):
        comment.content = data.content
        return comment

    def delete(self, db: Session, comment: Comment1N):
        db.delete(comment)

comment_repository = CommentRepository()
```
- `find_by_id()`: 없으면 `None`. `update()`: 속성만 바꾸면 변경 감지로 저장된다.

## 1:N 관계 실습 8단계: main.py 등록과 서버 실행
1:N 관계 예제의 모델과 Router를 `main.py`에 등록한다.
```python
# main.py
from mysite_one_to_many import models as one_to_many_models
from mysite_one_to_many.routers.post_router import router as one_to_many_router

# app 생성 후
app.include_router(one_to_many_router)
```
`fastapi_ai/fastapi_basic`에서 서버를 실행하고 `http://127.0.0.1:8000/docs`의 `mysite_one_to_many` 그룹에서 테스트한다.
```bash
uv run fastapi dev main.py
```

## 1:N 관계 실습 9단계: 게시글·댓글 등록과 상세 조회 확인
1:N 관계 예제에서 `POST /posts-1n`으로 게시글을 만들고, 받은 ID로 `POST /posts-1n/{post_id}/comments`에 댓글을 두 개 등록한다.
```json
{"title": "1:N 관계 예제", "content": "게시글에 댓글을 등록합니다."}
```
```json
{"content": "첫 번째 댓글입니다."}
```
게시글 ID 1, 댓글 ID 1·2일 때 상세 조회 응답 예시이다.
```json
{
  "id": 1,
  "title": "1:N 관계 예제",
  "content": "게시글에 댓글을 등록합니다.",
  "comments": [
    {"id": 1, "content": "첫 번째 댓글입니다."},
    {"id": 2, "content": "두 번째 댓글입니다."}
  ]
}
```

## 1:N 관계 실습 10단계: 수정·삭제와 cascade 확인
1:N 관계 예제에서 다음을 확인한다.
- 댓글 수정 후 게시글 상세 응답에 바뀐 내용이 나온다.
- 댓글 하나 삭제 후 상세 응답에서 그 댓글만 사라진다.
- 다른 게시글 ID로 댓글 수정·삭제를 요청하면 404이다.
- 게시글 삭제 후 상세 조회가 404이다.

게시글과 함께 댓글이 지워졌는지는 DB에서 확인한다(1은 삭제한 게시글 ID). 결과가 없으면 cascade 삭제가 된 것이다.
```sql
SELECT * FROM comment_1n WHERE post_id = 1;
```

## 1:N 관계 복습 Q&A
- Q. SQLAlchemy `relationship()`은 DB에 컬럼을 만드나?
  A. 아니다. 컬럼·외래키는 `ForeignKey`가 만들고, `relationship()`은 객체 탐색용 속성만 만든다.
- Q. `ForeignKey("post_1n.id")`에 클래스명 대신 무엇을 쓰나?
  A. 테이블 이름과 컬럼 이름을 쓴다.
- Q. 1:N 예제에서 게시글을 지우면 댓글도 지워지는 이유는?
  A. `Post1N.comments`에 `cascade="all"`(delete 포함)을 설정했기 때문이다.
- Q. 모델 파일에서 `TYPE_CHECKING`을 쓰는 이유는?
  A. 타입 검사용 import만 하고 실행 시에는 건너뛰어 순환 import를 피하기 위해서이다.
- Q. 다른 게시글의 댓글 ID로 수정 요청하면 어떻게 되나?
  A. `_get_verified_comment()`가 `comment.post_id != post_id`를 검사해 404를 낸다.
