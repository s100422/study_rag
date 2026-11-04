---
part: backend
lesson: 세션과 ORM 객체 상태
order: 19
source_type: web
tags: [sqlalchemy, session, orm, flush, lazy-loading, detached, selectinload]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1464/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 세션과 ORM 객체 상태

## 세션과 ORM 객체 상태 요약
SQLAlchemy 세션 안에서 ORM 객체가 어떤 상태(비영속·대기·영속·삭제·분리)를 거치는지, 추가·수정·삭제·관계 로딩·DTO 변환 상황별로 살펴본다. 예시는 `expire_on_commit=False`인 동기 Session과 mysite의 게시글(Post)·댓글(Comment) 모델을 기준으로 하며, import와 연결 설정은 생략한다.

## SQLAlchemy ORM 객체의 다섯 가지 상태
SQLAlchemy ORM 객체는 세션과의 관계에 따라 다섯 상태를 가진다.
- 비영속(transient): 만들었지만 아직 세션에 등록하지 않은 새 객체.
- 대기(pending): 세션에 등록했지만 INSERT는 아직 실행되지 않은 객체.
- 영속(persistent): DB에서 조회했거나 INSERT가 실행되어 세션이 관리하는 객체.
- 삭제(deleted): DELETE가 실행됐지만 아직 commit되지 않은 객체.
- 분리·준영속(detached): DB 식별 정보는 있지만 세션에서 떨어져 관리받지 않는 객체.

영속 상태여도 commit 전에는 저장이 확정된 것이 아니다. 상태 이름보다 "지금 세션이 이 객체를 관리하고 있나?"를 기준으로 코드를 읽으면 된다.

## ORM 객체 상태 예시: 새 게시글을 add()할 때
새 게시글 객체는 `add()`로 대기 상태가 되고, flush 때 INSERT가 실행되어 영속 상태가 된다.
```python
with SessionLocal() as db:
    with db.begin():
        post = Post(title="첫 번째 글")  # 비영속
        db.add(post)                     # 대기: 등록만, INSERT 전
        db.flush()                       # INSERT → 영속
    # commit: 저장 확정, 영속 유지
# 세션 종료: 분리(detached)
```
- `db.flush()`를 직접 부르지 않아도 begin 블록이 정상 종료되면 flush와 commit이 자동으로 진행된다.

## ORM 객체 상태 예시: 조회한 게시글 제목 수정
세션이 영속 객체의 변경을 추적하므로 조회한 게시글의 속성을 바꾸면 다시 `add()`할 필요가 없다. UPDATE는 속성을 바꾸는 순간이 아니라 flush 때 실행된다.
```python
with SessionLocal() as db:
    with db.begin():
        post = db.get(Post, post_id)  # SELECT → 영속
        post.title = "수정된 제목"     # 변경 추적
        db.flush()                     # UPDATE 실행
    # commit: 수정 확정, 영속 유지
# 세션 종료: 분리
```

## ORM 객체 상태 예시: post.comments에 댓글 append()
영속 게시글의 `post.comments`에 새 댓글을 append하면 관계의 기본 save-update cascade가 댓글도 세션에 등록하므로 `db.add(comment)`가 필요 없다.
```python
with SessionLocal() as db:
    with db.begin():
        post = db.get(Post, post_id)         # 영속, comments는 미조회
        comment = Comment(content="좋은 글입니다")  # 비영속
        post.comments.append(comment)        # 댓글 목록 SELECT 후 추가 → 대기
        db.flush()                           # 댓글 INSERT → 영속
    # commit: 둘 다 영속 유지
# 세션 종료: 둘 다 분리
```
- 아직 조회하지 않은 `post.comments`에 접근하는 순간 댓글 목록 SELECT가 실행된다.
- 댓글의 `post_id`는 flush 때 관계에 맞게 채워진다.

## ORM 객체 상태 예시: 댓글을 delete()할 때
댓글 객체에 `db.delete()`를 호출하면 삭제 대상으로 표시만 되고, 실제 DELETE는 flush 때 실행된다.
```python
with SessionLocal() as db:
    with db.begin():
        comment = db.get(Comment, comment_id)  # 영속
        db.delete(comment)                     # 삭제 예약, 아직 영속
        db.flush()                             # DELETE → 삭제 상태
    # commit: 삭제 확정 → 분리
```
- 삭제가 확정돼도 파이썬 객체는 남지만 해당 DB 행은 사라진다.

## ORM 객체 상태 예시: 게시글만 조회 후 begin 밖에서 DTO 변환
begin 블록이 끝나도 세션이 열려 있으면, DTO 변환 중 `post.comments`에 접근할 때 새 트랜잭션으로 댓글을 지연 로딩(lazy loading)한다. PostDTO와 댓글 DTO에는 `from_attributes=True`가 설정돼 있다고 가정한다.
```python
with SessionLocal() as db:
    with db.begin():
        post = db.get(Post, post_id)  # 영속, comments 미조회
    # commit 후에도 post는 영속, comments는 여전히 미조회

    dto = PostDTO.model_validate(post)  # comments 접근 → 댓글 SELECT
# 세션 종료: ORM 객체는 분리, dto 값은 유지
```

## ORM 객체 상태 예시: selectinload로 댓글까지 미리 조회
게시글을 조회할 때 `selectinload(Post.comments)`로 댓글까지 미리 읽어 두면 DTO 변환 중 추가 SELECT가 발생하지 않는다.
```python
with SessionLocal() as db:
    with db.begin():
        post = db.scalar(
            select(Post)
            .where(Post.id == post_id)
            .options(selectinload(Post.comments))
        )  # 게시글 SELECT + 댓글 SELECT
    # commit 후에도 영속, 읽은 값 유지

    dto = PostDTO.model_validate(post)  # 추가 SELECT 없음
```

## ORM 객체 상태 예시: 세션을 닫은 뒤 DTO 변환하면 오류
세션이 닫혀 분리 상태가 된 게시글은 이미 읽은 `title`은 쓸 수 있지만, 아직 조회하지 않은 `comments`는 불러올 세션이 없다.
```python
with SessionLocal() as db:
    post = db.get(Post, post_id)  # 영속, comments 미조회
# 세션 종료: post는 분리

dto = PostDTO.model_validate(post)  # ValidationError
```
- 관계 접근에서 난 `DetachedInstanceError`가 Pydantic `ValidationError` 안에 담겨 나온다.
- 해결하려면 세션이 열려 있을 때 DTO로 바꾸거나 `selectinload`로 관계를 미리 읽어 둔다.

## 세션과 ORM 객체 상태 복습 Q&A
- Q. SQLAlchemy에서 `db.add()`만 호출한 객체는 어떤 상태인가?
  A. 대기(pending) 상태이며, INSERT는 flush 때 실행된다.
- Q. 영속 객체의 속성을 바꾼 뒤 다시 `add()`해야 하나?
  A. 아니다. 세션이 변경을 추적하고 flush 때 UPDATE를 실행한다.
- Q. `post.comments.append(comment)` 후 `db.add(comment)`가 필요 없는 이유는?
  A. 관계의 기본 save-update cascade가 새 댓글을 세션에 등록하기 때문이다.
- Q. 세션을 닫은 뒤 미조회 관계를 DTO로 변환하면 어떻게 되나?
  A. `DetachedInstanceError`가 나고 Pydantic `ValidationError`로 감싸져 발생한다.
- Q. DTO 변환 시 추가 SELECT를 막으려면?
  A. 조회할 때 `selectinload(Post.comments)` 같은 옵션으로 관계를 미리 로딩한다.
