---
part: backend
lesson: 비동기 CRUD
order: 21
source_type: web
tags: [fastapi, async, sqlalchemy, asyncsession, lazy-loading, joinedload, run_in_threadpool]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1465/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 비동기 CRUD

## 비동기 CRUD 요약
fastapi_agent에서 AsyncSession 기반 CRUD를 작성할 때 어디에 `await`를 붙이는지, 관계 로딩을 어떻게 미리 준비하는지, 비동기 함수 안의 동기 연산을 어떻게 처리하는지 다룬다.

## 비동기 ORM 관계 로딩: lazy="raise" 설정
비동기 ORM에서는 관계 속성에 `lazy="raise"`를 설정해 암묵적인 DB 조회를 막는다.
```python
# src/fastapi_agent/domains/posts/models.py (Post 클래스 발췌)
user: Mapped["User"] = relationship(back_populates="posts", lazy="raise")
```
- 로딩하지 않은 관계에 접근하면 SQL을 실행하지 않고 `InvalidRequestError`가 난다.
- 이미 로딩된 관계는 일반 속성처럼 읽을 수 있다.

## 비동기 환경에서 lazy loading이 안 되는 이유
AsyncSession에서는 `post.user` 같은 일반 속성 접근으로 생기는 DB I/O를 await할 수 없어 `MissingGreenlet` 오류가 날 수 있다. 응답 모델 변환·직렬화도 관계 속성을 동기적으로 읽기 때문에, 응답에 필요한 관계는 미리 로딩해야 한다.
- 조회 쿼리에 `joinedload()`나 `selectinload()`를 붙이면 `await db.scalar(...)` / `await db.scalars(...)`가 끝날 때 관계도 함께 로딩된다.
- 명시적인 await 호출(예: `await db.refresh(obj, ["관계명"])`)로 관계를 로딩할 수도 있다.

## 비동기 CRUD 예시: 게시글 생성 후 작성자 정보 반환
비동기 세션에서 게시글을 `user_id=current_user.id`로 만들면 작성자 ID만 정해진 것이고 `post.user`는 로딩되지 않는다. 동기 세션이라면 응답 모델이 `post.user`를 읽을 때 추가 조회가 되지만, 비동기 세션에서는 그 조회를 기다릴 수 없다.
- 방법 1: 저장 후 `joinedload(Post.user)`를 적용한 조회를 await해 다시 불러온다.
- 방법 2: `await db.refresh(post, ["user"])`로 작성자 관계만 로딩한 뒤 반환한다.

## 비동기 CRUD에서 await를 붙이는 대상
비동기 CRUD는 Router → Service → Repository → DB I/O로 이어지는 호출마다 `async def`와 `await`를 적용한다.
```text
Router → await Service → await Repository → await DB I/O
```
- await 필요: `await db.flush()`, `await db.scalar(...)`, `await db.get(...)`, `await db.scalars(...)`, `await db.delete(post)`.
- await 불필요: `db.add(post)`(객체 등록), `post.title = data.title`(속성 변경), `result.all()`(버퍼링된 결과 읽기).
- `delete()`는 관계 처리 중 DB I/O가 필요할 수 있어 await를 쓴다.

## 비동기 CRUD 실습 1단계: Repository 비동기 메서드
비동기 PostRepository는 `add()` 뒤 `await db.flush()`로 INSERT를 실행하고, 상세 조회에서 작성자·댓글·댓글 작성자를 미리 로딩한다.
```python
# src/fastapi_agent/domains/posts/repository.py (PostRepository 발췌)
async def save(self, db: AsyncSession, post: Post) -> Post:
    db.add(post)
    await db.flush()
    return post

async def find_by_id(self, db: AsyncSession, post_id: int) -> Post | None:
    return await db.scalar(
        select(Post)
        .options(
            joinedload(Post.user),
            selectinload(Post.comments).joinedload(Comment.user),
        )
        .where(Post.id == post_id)
    )
```
- `selectinload(Post.comments).joinedload(Comment.user)`: 댓글 목록과 각 댓글 작성자까지 연쇄 로딩한다.
- `flush`를 해야 `post.id`가 채워져 바로 재조회할 수 있다.

## 비동기 CRUD 실습 2단계: Service의 async with db.begin()
비동기 PostService는 트랜잭션 블록에 `async with db.begin()`을 쓰고, 저장 후 상세 조회를 await해 응답에 필요한 관계를 준비한다.
```python
# src/fastapi_agent/domains/posts/service.py (PostService 발췌)
async def create_post(
    self, db: AsyncSession, data: PostCreate, current_user: UserResponse
) -> Post:
    async with db.begin():
        post = Post(
            title=data.title,
            content=data.content,
            user_id=current_user.id,
            comments=[],
        )
        await post_repository.save(db, post)
        result = await self.get_post(db, post.id)
    return result
```
- `comments=[]`: 새 게시글의 댓글 목록을 빈 리스트로 지정한다.
- `await self.get_post(...)`: `find_by_id`의 joinedload로 작성자까지 로딩된 게시글을 반환한다.

## 비동기 CRUD 실습 3단계: Router와 인증 의존성의 비동기 호출
비동기 Router 핸들러는 `async def`로 선언하고 `AsyncSession`을 주입받아 Service를 await로 호출한다.
```python
# src/fastapi_agent/domains/posts/router.py (발췌)
async def get_posts(db: Annotated[AsyncSession, Depends(get_db)]):
    posts = await post_service.get_posts(db)
    return SuccessResponse[list[PostListResponse]](data=posts)
```
인증 의존성 `get_current_user`도 세션을 `async with`로 열고 비동기 Service를 await한다.
```python
# src/fastapi_agent/core/dependencies.py (get_current_user 내부 발췌)
async with SessionLocal() as db:
    user = await user_service.get_current_user(db, credentials.credentials)
    return UserResponse.model_validate(user)
```
- `SuccessResponse[...]`: 프로젝트의 공통 응답 래퍼로 보인다(이 레슨에 정의는 없음).

## 비동기 CRUD에서 비밀번호 해싱을 스레드 풀로 실행
비밀번호 해싱·검증은 CPU를 쓰는 동기 연산이라 비동기 Service에서 직접 실행하면 이벤트 루프를 점유한다. `run_in_threadpool()`로 별도 스레드에서 실행하고 완료를 await한다.
```python
from starlette.concurrency import run_in_threadpool

# 비동기 함수 내부
hashed_password = await run_in_threadpool(hash_password, data.password)
valid = await run_in_threadpool(verify_password, data.password, user.hashed_password)
```
- 첫 인자는 실행할 함수, 나머지는 그 함수에 넘길 인자이다.

## 비동기 CRUD 복습 Q&A
- Q. 비동기 SQLAlchemy에서 관계에 `lazy="raise"`를 두는 이유는?
  A. 로딩되지 않은 관계 접근 시 몰래 SQL을 실행하지 않고 즉시 `InvalidRequestError`를 내서 문제를 드러내기 위해서다.
- Q. AsyncSession에서 `db.add()`와 `db.delete()` 중 await가 필요한 것은?
  A. `db.delete()`이다. `add()`는 등록만 하므로 await하지 않는다.
- Q. 비동기 게시글 생성 후 작성자 정보를 응답에 넣으려면?
  A. `joinedload(Post.user)` 조회를 await해 다시 불러오거나 `await db.refresh(post, ["user"])`를 쓴다.
- Q. 비동기 Service에서 비밀번호 해싱은 어떻게 실행하나?
  A. `await run_in_threadpool(hash_password, data.password)`처럼 스레드 풀에서 실행한다.
- Q. 비동기 Service의 트랜잭션 블록은 어떻게 쓰나?
  A. `async with db.begin():`을 쓴다.
