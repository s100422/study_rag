---
part: backend
lesson: 작성자가 있는 게시글
order: 17
source_type: web
tags: [fastapi, sqlalchemy, relationship, joinedload, authorization, jwt, foreign-key]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1453/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 작성자가 있는 게시글

## 작성자가 있는 게시글 요약
mysite_auth 프로젝트에 게시글 기능을 붙여, 로그인한 사용자를 게시글 작성자로 저장한다. 게시글 수정·삭제는 작성자 본인만 할 수 있도록 Service에서 권한을 검사한다.

## 작성자가 있는 게시글 API 목록
작성자가 있는 게시글 API는 `/posts-auth` 경로와 사용자별 조회 경로로 구성된다.
- `POST /posts-auth`: 게시글 작성. 로그인 필요. 성공 시 201.
- `GET /posts-auth`: 전체 목록 조회. 인증 불필요. 200.
- `GET /posts-auth/{post_id}`: 상세 조회. 인증 불필요. 200.
- `PUT /posts-auth/{post_id}`: 수정. 작성자 본인만. 200.
- `DELETE /posts-auth/{post_id}`: 삭제. 작성자 본인만. 204.
- `GET /me/posts`: 내가 쓴 글 조회. 로그인 필요. 200.
- `GET /users/{user_id}/posts`: 특정 사용자의 글 조회. 인증 불필요. 200.

## 작성자가 있는 게시글 실습 1단계: PostAuth 모델에 작성자 외래 키 추가
게시글 모델 PostAuth에 작성자 ID를 담는 외래 키 `user_id`와, 작성자 객체에 접근하는 관계 속성 `user`를 둔다.
```python
# mysite_auth/models/post.py
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

if TYPE_CHECKING:
    from mysite_auth.models.user import User

class PostAuth(Base):
    __tablename__ = "post_auth"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_auth.id"), nullable=False)

    user: Mapped["User"] = relationship(back_populates="posts")
```
- `ForeignKey("user_auth.id")`: user_auth 테이블의 id를 참조한다.
- `TYPE_CHECKING`: 타입 힌트용 import만 하여 순환 import를 피한다.

## 작성자가 있는 게시글 실습 2단계: User 모델에 posts 관계 추가
User 모델에 `posts` 관계를 추가하고, `back_populates`로 `PostAuth.user`와 양방향 연결한다.
```python
# mysite_auth/models/user.py (관계 부분)
if TYPE_CHECKING:
    from mysite_auth.models.post import PostAuth

class User(Base):
    __tablename__ = "user_auth"
    # id, email, hashed_password, created_at 컬럼은 기존과 동일
    posts: Mapped[list["PostAuth"]] = relationship(back_populates="user")
```
모델 패키지의 `__init__.py`에서 두 모델을 import해 등록한다.
```python
# mysite_auth/models/__init__.py
from .post import PostAuth
from .user import User
```

## 작성자가 있는 게시글 실습 3단계: 요청·응답 스키마
게시글 요청 스키마는 제목과 내용만 받는다. 작성자는 요청에서 받지 않고 인증된 `current_user.id`로 정한다. 응답의 작성자 정보는 비밀번호가 빠진 `UserResponse`를 쓴다.
```python
# mysite_auth/schemas/post.py
from pydantic import BaseModel, ConfigDict, Field
from mysite_auth.schemas.user import UserResponse

class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)

class PostListResponse(BaseModel):
    id: int
    title: str
    user: UserResponse
    model_config = ConfigDict(from_attributes=True)

class PostDetailResponse(BaseModel):
    id: int
    title: str
    content: str
    user: UserResponse
    model_config = ConfigDict(from_attributes=True)
```
- `from_attributes=True`: ORM 객체의 속성(`post.user` 포함)을 읽어 응답 모델을 만든다.

## 작성자가 있는 게시글 실습 4단계: Repository 조회 메서드
게시글 PostRepository의 조회 메서드는 `joinedload(PostAuth.user)`로 게시글과 작성자를 한 번에 가져온다.
```python
# mysite_auth/repositories/post_repository.py (조회 메서드)
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from mysite_auth.models.post import PostAuth

class PostRepository:
    def find_all(self, db: Session):
        return db.scalars(
            select(PostAuth).options(joinedload(PostAuth.user)).order_by(PostAuth.id)
        ).all()

    def find_by_id(self, db: Session, post_id: int):
        return db.scalar(
            select(PostAuth).options(joinedload(PostAuth.user))
            .where(PostAuth.id == post_id)
        )

    def find_by_user_id(self, db: Session, user_id: int):
        return db.scalars(
            select(PostAuth).options(joinedload(PostAuth.user))
            .where(PostAuth.user_id == user_id).order_by(PostAuth.id)
        ).all()
```
- `find_by_user_id`: `/me/posts`와 `/users/{user_id}/posts`에서 함께 쓴다.

## 작성자가 있는 게시글 실습 5단계: Repository 저장·수정·삭제 메서드
게시글 PostRepository의 쓰기 메서드는 세션에 객체를 등록·변경·삭제만 하고, commit은 Service의 트랜잭션이 맡는다.
```python
# mysite_auth/repositories/post_repository.py (쓰기 메서드)
from mysite_auth.schemas.post import PostCreate

class PostRepository:
    def save(self, db: Session, new_post: PostAuth):
        db.add(new_post)
        return new_post

    def update(self, db: Session, post: PostAuth, data: PostCreate):
        post.title = data.title
        post.content = data.content
        return post

    def delete(self, db: Session, post: PostAuth):
        db.delete(post)

post_repository = PostRepository()
```

## 작성자가 있는 게시글 실습 6단계: Service의 게시글 작성
게시글 PostService의 `create_post`는 요청의 제목·내용에 `current_user.id`를 작성자로 넣어 게시글을 만들고, `with db.begin()` 트랜잭션으로 저장한다.
```python
# mysite_auth/services/post_service.py (작성)
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from mysite_auth.models.post import PostAuth
from mysite_auth.repositories.post_repository import post_repository
from mysite_auth.schemas.post import PostCreate
from mysite_auth.schemas.user import UserResponse

class PostService:
    def create_post(self, db: Session, data: PostCreate, current_user: UserResponse):
        with db.begin():
            new_post = PostAuth(title=data.title, content=data.content,
                                user_id=current_user.id)
            post_repository.save(db, new_post)
        return new_post
```
- `with db.begin()`: 블록이 정상 종료되면 commit, 예외가 나면 rollback된다.

## 작성자가 있는 게시글 실습 7단계: Service의 게시글 조회
게시글 PostService의 조회 메서드는 Repository를 호출하고, 없는 게시글이면 404를 낸다.
```python
# mysite_auth/services/post_service.py (조회)
class PostService:
    def get_posts(self, db: Session):
        return post_repository.find_all(db)

    def get_post(self, db: Session, post_id: int):
        post = post_repository.find_by_id(db, post_id)
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="게시글을 찾을 수 없습니다.")
        return post

    def get_posts_by_user_id(self, db: Session, user_id: int):
        return post_repository.find_by_user_id(db, user_id)
```

## 작성자가 있는 게시글 실습 8단계: Service의 수정 작성자 검사
게시글 PostService의 `update_post`는 `post.user_id`와 `current_user.id`를 비교해 작성자 본인이 아니면 403을 낸다.
```python
# mysite_auth/services/post_service.py (수정)
class PostService:
    def update_post(self, db: Session, post_id: int, data: PostCreate,
                    current_user: UserResponse):
        with db.begin():
            post = self.get_post(db, post_id)
            if post.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="본인의 게시글만 수정할 수 있습니다.")
            updated_post = post_repository.update(db, post, data)
        return updated_post
```

## 작성자가 있는 게시글 실습 9단계: Service의 삭제 작성자 검사
게시글 PostService의 `delete_post`도 작성자 본인인지 확인한 뒤 삭제하며, 남의 글이면 403을 낸다.
```python
# mysite_auth/services/post_service.py (삭제)
class PostService:
    def delete_post(self, db: Session, post_id: int, current_user: UserResponse):
        with db.begin():
            post = self.get_post(db, post_id)
            if post.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="본인의 게시글만 삭제할 수 있습니다.")
            post_repository.delete(db, post)

post_service = PostService()
```

## 작성자가 있는 게시글의 인증과 인가 차이
게시글 API에서 인증과 인가는 확인하는 내용과 실패 응답이 다르다.
- 인증(Authentication): 유효한 토큰을 가진 사용자인지 확인한다. Router의 `Depends(get_current_user)`가 처리하고, 실패하면 401이다.
- 인가(Authorization): 로그인한 사용자가 그 게시글의 작성자인지 확인한다. Service의 `post.user_id != current_user.id` 검사가 처리하고, 실패하면 403이다.

## 작성자가 있는 게시글 실습 10단계: 게시글 Router 작성
게시글 Router는 `Depends(get_db)`로 DB 세션을 받고, 인증이 필요한 작성·수정·삭제에만 `Depends(get_current_user)`를 추가한다.
```python
# mysite_auth/routers/post_router.py (작성)
from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from mysite_auth.schemas.post import PostCreate, PostDetailResponse, PostListResponse
from mysite_auth.schemas.user import UserResponse
from mysite_auth.services.post_service import post_service

router = APIRouter(prefix="/posts-auth", tags=["mysite_auth"])

@router.post("", response_model=PostDetailResponse, status_code=status.HTTP_201_CREATED)
def create_post(data: PostCreate, db: Annotated[Session, Depends(get_db)],
                current_user: Annotated[UserResponse, Depends(get_current_user)]):
    return post_service.create_post(db, data, current_user)
```
- `prefix="/posts-auth"`: 이 라우터의 모든 경로 앞에 붙는다. `""`는 `/posts-auth` 자체이다.

## 작성자가 있는 게시글 실습 11단계: 게시글 Router 조회
게시글 Router의 목록·상세 조회는 인증 없이 `Depends(get_db)`만 받는다.
```python
# mysite_auth/routers/post_router.py (조회)
@router.get("", response_model=list[PostListResponse])
def get_posts(db: Annotated[Session, Depends(get_db)]):
    return post_service.get_posts(db)

@router.get("/{post_id}", response_model=PostDetailResponse)
def get_post(post_id: int, db: Annotated[Session, Depends(get_db)]):
    return post_service.get_post(db, post_id)
```

## 작성자가 있는 게시글 실습 12단계: 게시글 Router 수정·삭제
게시글 Router의 수정·삭제 핸들러는 `current_user`를 받아 Service에 넘기고, 작성자 검사는 Service가 한다.
```python
# mysite_auth/routers/post_router.py (수정·삭제)
@router.put("/{post_id}", response_model=PostDetailResponse)
def update_post(post_id: int, data: PostCreate,
                db: Annotated[Session, Depends(get_db)],
                current_user: Annotated[UserResponse, Depends(get_current_user)]):
    return post_service.update_post(db, post_id, data, current_user)

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: Annotated[Session, Depends(get_db)],
                current_user: Annotated[UserResponse, Depends(get_current_user)]):
    post_service.delete_post(db, post_id, current_user)
```
- 삭제는 204이므로 반환값이 없다.

## 작성자가 있는 게시글 실습 13단계: 사용자 Router의 내 글 조회
사용자 Router에서 `/me/posts`는 토큰의 사용자 ID로, `/users/{user_id}/posts`는 URL의 사용자 ID로 게시글을 조회한다.
```python
# mysite_auth/routers/user_router.py
router = APIRouter(tags=["mysite_auth"])

@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[UserResponse, Depends(get_current_user)]):
    return current_user

@router.get("/me/posts", response_model=list[PostListResponse])
def get_my_posts(db: Annotated[Session, Depends(get_db)],
                 current_user: Annotated[UserResponse, Depends(get_current_user)]):
    return post_service.get_posts_by_user_id(db, current_user.id)

@router.get("/users/{user_id}/posts", response_model=list[PostListResponse])
def get_posts_by_user(user_id: int, db: Annotated[Session, Depends(get_db)]):
    return post_service.get_posts_by_user_id(db, user_id)
```

## 작성자가 있는 게시글 실습 14단계: main.py에 라우터 등록
공통 서버의 main.py에서 mysite_auth 모델과 인증·게시글·사용자 라우터를 import해 등록한다.
```python
# main.py
from mysite_auth import models as auth_models
from mysite_auth.routers.auth_router import router as auth_router
from mysite_auth.routers.post_router import router as auth_post_router
from mysite_auth.routers.user_router import router as user_router

app.include_router(auth_router)
app.include_router(auth_post_router)
app.include_router(user_router)
```

## 작성자가 있는 게시글 실습 15단계: Swagger로 권한 확인
작성자가 있는 게시글 권한은 Swagger UI에서 로그인 후 토큰을 Authorize에 넣고 `POST /posts-auth`로 글을 써서 확인한다.
```json
{
  "title": "작성자가 있는 게시글",
  "content": "로그인한 사용자가 작성자로 저장됩니다."
}
```
- 응답의 `user.id`가 로그인한 사용자 ID인지 본다.
- `/me/posts`에 본인 글만 나오는지 본다.
- 다른 계정으로 로그인해 수정·삭제하면 403인지 본다.
- 토큰 없이 작성·수정·삭제하면 401인지 본다.

## 작성자가 있는 게시글 복습 Q&A
- Q. 작성자가 있는 게시글에서 작성자 ID는 어디서 정하나?
  A. 요청 본문이 아니라 인증된 사용자의 `current_user.id`로 정한다.
- Q. 게시글 조회 시 작성자 정보를 함께 가져오는 방법은?
  A. `select(PostAuth).options(joinedload(PostAuth.user))`로 게시글과 작성자를 함께 조회한다.
- Q. 게시글 수정 시 토큰이 없을 때와 남의 글일 때 응답 코드는?
  A. 토큰이 없으면 인증 실패로 401, 남의 글이면 인가 실패로 403이다.
- Q. `User.posts`와 `PostAuth.user`는 어떻게 연결하나?
  A. 양쪽 `relationship`에 `back_populates`로 서로의 속성 이름을 지정한다.
