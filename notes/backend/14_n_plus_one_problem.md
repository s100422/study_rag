---
part: backend
lesson: N+1 문제
order: 14
source_type: web
tags: [sqlalchemy, n+1, lazy_loading, eager_loading, joinedload, selectinload, fastapi]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1451/
note: 개인 학습용 요약. 외부 공유 금지.
---

# N+1 문제

## N+1 문제 요약
목록 조회 후 연관 데이터를 항목마다 따로 조회해 SQL이 1+N번 실행되는 N+1 문제를, SQLAlchemy의 `joinedload()`와 `selectinload()` 즉시 로딩으로 줄이는 방법을 익히고, API 응답의 SQL 실행 횟수로 개선 전후를 비교한다. 코드는 `fastapi_ai/fastapi_basic/mysite_nplusone/`에 있다.

## N+1 문제란
N+1 문제는 목록을 한 번 조회한 뒤, 각 항목의 연관 데이터를 가져오려고 개별 조회를 반복하는 현상이다. 게시글 N개와 각 게시글의 댓글을 가져오면 게시글 목록 1회 + 게시글마다 댓글 조회 N회로 총 1+N회의 SQL이 실행된다. 목록이 커질수록 DB 왕복과 쿼리 처리 시간이 쌓여 응답이 느려진다.

## N+1 문제 예제 모델: 사용자, 게시글, 댓글
예제는 세 모델로 구성된다. 모두 `relationship()`과 `back_populates`로 양방향 연결된다.
- `UserNPlusOne`(`user_nplusone`): id, name. `posts`, `comments` 관계
- `PostNPlusOne`(`post_nplusone`): id, title, user_id(FK). `user`(N:1), `comments`(1:N) 관계
- `CommentNPlusOne`(`comment_nplusone`): id, content, post_id(FK), user_id(FK). `post`, `user`(N:1) 관계

```python
class PostNPlusOne(Base):
    __tablename__ = "post_nplusone"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_nplusone.id"), nullable=False
    )

    user: Mapped["UserNPlusOne"] = relationship(
        "UserNPlusOne", back_populates="posts"
    )
    comments: Mapped[list["CommentNPlusOne"]] = relationship(
        "CommentNPlusOne", back_populates="post", order_by="CommentNPlusOne.id",
    )
```
- `ForeignKey`는 테이블 연결, `relationship()`은 ORM 객체 접근 속성, `back_populates`는 양쪽 관계를 묶는다.

## N+1 문제의 원인: SQLAlchemy 지연 로딩
지연 로딩(Lazy Loading)은 연관 데이터를 실제로 사용할 때까지 조회를 미루는 방식이고, SQLAlchemy `relationship()`의 기본값이다. 게시글 조회 시에는 게시글만 가져오고, 아직 불러오지 않은 `post.comments`를 읽는 순간 댓글 SELECT가 실행된다.
```python
from sqlalchemy import select
from mysite_nplusone.models import PostNPlusOne

posts = db.scalars(select(PostNPlusOne)).all()  # SQL 1회

for post in posts:
    print(post.comments)  # 게시글마다 추가 SELECT → N회
```
이 반복이 바로 N+1이다.

## N+1 문제 해결: 즉시 로딩 joinedload
즉시 로딩(Eager Loading)은 조회 시점에 필요한 연관 데이터도 미리 가져오는 방식으로, 조회문의 `.options()`에 지정한다. `joinedload()`는 JOIN으로 같은 SQL 안에서 연관 데이터를 가져온다.
```python
from sqlalchemy import select
from sqlalchemy.orm import joinedload

stmt = (
    select(PostNPlusOne)
    .options(joinedload(PostNPlusOne.user))
    .order_by(PostNPlusOne.id)
)
posts = db.scalars(stmt).all()
```
```sql
SELECT p.id, p.title, p.user_id, u.id AS loaded_user_id, u.name AS user_name
FROM post_nplusone AS p
LEFT OUTER JOIN user_nplusone AS u ON u.id = p.user_id
ORDER BY p.id;
```
- 게시글과 작성자를 한 번에 가져오므로 이후 `post.user.name`을 읽어도 추가 SQL이 없다.

## joinedload로 1:N 컬렉션을 로딩할 때 unique()
`joinedload()`는 1:N인 댓글에도 쓸 수 있지만, JOIN 결과에서 댓글 수만큼 게시글 컬럼이 반복된다.
```python
stmt = (
    select(PostNPlusOne)
    .options(joinedload(PostNPlusOne.comments))
    .order_by(PostNPlusOne.id)
)
posts = db.scalars(stmt).unique().all()
```
```sql
SELECT p.id, p.title, p.user_id, c.id AS comment_id, c.content, c.post_id, c.user_id
FROM post_nplusone AS p
LEFT OUTER JOIN comment_nplusone AS c ON c.post_id = p.id
ORDER BY p.id, c.id;
```
- 컬렉션을 joinedload할 때는 같은 게시글 객체가 중복 반환되지 않도록 `.unique()`가 필수이고, 생략하면 예외가 난다.
- `.unique()`는 파이썬 쪽 중복 제거일 뿐, DB에서 가져오는 행 수가 줄지는 않는다.

## N+1 문제 해결: 즉시 로딩 selectinload
`selectinload()`는 게시글을 먼저 조회한 뒤, 그 게시글 ID를 모아 IN 조건으로 댓글을 한 번에 가져온다.
```python
from sqlalchemy.orm import selectinload

stmt = (
    select(PostNPlusOne)
    .options(selectinload(PostNPlusOne.comments))
    .order_by(PostNPlusOne.id)
)
posts = db.scalars(stmt).all()
```
```sql
SELECT p.id, p.title, p.user_id FROM post_nplusone AS p ORDER BY p.id;

SELECT c.id, c.content, c.post_id, c.user_id
FROM comment_nplusone AS c
WHERE c.post_id IN (1, 2, 3, ..., 25)
ORDER BY c.id;
```
- 댓글은 post_id 기준으로 각 게시글의 `comments`에 채워진다. `.all()` 이후 `post.comments`를 읽어도 추가 조회가 없다.
- 보통 SQL 2회이다. 게시글이 없으면 댓글 조회를 생략하고, 게시글이 아주 많으면 ID를 나눠 조회해 횟수가 늘 수 있다.

## joinedload와 selectinload 선택 기준
- N:1 또는 1:1 관계: `joinedload`를 먼저 고려한다. 연결된 객체 하나를 JOIN으로 가져오기 좋다.
- 1:N 또는 M:N 관계: `selectinload`를 먼저 고려한다. JOIN 결과에서 부모 데이터가 반복되는 것을 피한다.

두 전략 모두 단일 객체와 컬렉션 관계에 쓸 수 있다. SQL 횟수뿐 아니라 가져오는 데이터 양도 따져야 하고, 응답에 필요한 관계만 로딩한다. SQL 1회가 항상 더 빠른 것은 아니다.

## 즉시 로딩 복합 관계 1: 여러 관계를 함께 로딩
게시글의 작성자와 댓글처럼 서로 다른 관계가 필요하면 `.options()`에 나란히 적는다.
```python
from sqlalchemy.orm import joinedload, selectinload

stmt = (
    select(PostNPlusOne)
    .options(
        joinedload(PostNPlusOne.user),
        selectinload(PostNPlusOne.comments),
    )
    .order_by(PostNPlusOne.id)
)
posts = db.scalars(stmt).all()
```
- 게시글+작성자는 JOIN 1회, 댓글은 IN 조회 1회로 기본 실습 데이터에서 총 2회이다.

## 즉시 로딩 복합 관계 2: 관계를 따라 이어서 로딩
게시글 → 댓글 → 댓글 작성자까지 필요하면 경로를 따라 로딩 옵션을 체인으로 잇는다.
```python
from mysite_nplusone.models import CommentNPlusOne, PostNPlusOne

stmt = (
    select(PostNPlusOne)
    .options(
        selectinload(PostNPlusOne.comments).joinedload(CommentNPlusOne.user)
    )
    .order_by(PostNPlusOne.id)
)
posts = db.scalars(stmt).all()
```
```sql
SELECT p.id, p.title, p.user_id FROM post_nplusone AS p ORDER BY p.id;

SELECT c.id, c.content, c.post_id, c.user_id, u.id AS loaded_user_id, u.name AS user_name
FROM comment_nplusone AS c
LEFT OUTER JOIN user_nplusone AS u ON u.id = c.user_id
WHERE c.post_id IN (1, 2, ..., 25)
ORDER BY c.id;
```
- 게시글-댓글은 1:N이라 `selectinload`, 댓글-작성자는 N:1이라 `joinedload`를 쓴다. 총 2회이고 이후 `comment.user.name`도 추가 조회가 없다.

## N+1 문제 실습 1단계: SQL 로그 켜기와 데이터 초기화
터미널에서 SQL을 보려면 `database.py`의 엔진에 `echo=True`를 준다.
```python
engine = create_engine(DATABASE_URL, echo=True)
```
- `http://127.0.0.1:8000/docs`의 `mysite_nplusone` 그룹에서 API를 실행한다.
- `POST /nplusone/setup`을 본문 없이 호출하면 실습 데이터를 지우고 다시 만든다. 기본 데이터는 사용자 5명, 게시글 25개, 댓글 125개(게시글마다 사용자 5명이 하나씩)이다.
- 조회 API 응답에는 `query_count`(SQL 실행 횟수), `queries`(실행된 SQL 목록), `posts`(결과 데이터)가 들어 있다. 지연 로딩으로 생긴 추가 조회도 포함되며, echo 설정과 무관하게 제공된다.

## N+1 문제 실습 2단계: 작성자 조회 지연 로딩 vs joinedload
- `GET /nplusone/posts/with-user`: 게시글을 먼저 조회하고 작성자가 필요할 때 사용자 테이블을 추가 조회한다. 같은 작성자는 세션에서 재사용되므로 게시글 1회 + 작성자 5회 = 총 6회이다.
- `GET /nplusone/posts/with-user/optimized`: `joinedload(PostNPlusOne.user)` 적용. 게시글과 사용자를 LEFT OUTER JOIN 하므로 총 1회이다.

두 API의 `posts`는 같고, 작성자별 개별 SELECT가 사라졌는지 `queries`로 비교한다.

## N+1 문제 실습 3단계: 댓글 조회 지연 로딩 vs selectinload vs joinedload
- `GET /nplusone/posts/with-comments`: 게시글마다 댓글을 조회해 게시글 1회 + 댓글 25회 = 총 26회이다.
- `GET /nplusone/posts/with-comments/optimized`: `selectinload(PostNPlusOne.comments)` 적용. 게시글 조회 + `post_id IN (...)` 댓글 조회 = 총 2회이다.
- `GET /nplusone/posts/with-comments/joined`: `joinedload(PostNPlusOne.comments)` 적용. JOIN 1회이다. JOIN 결과에선 게시글 컬럼이 댓글마다 반복되지만 Repository의 `find_all_with_comments_joined()`에서 `.unique()`를 적용해 응답 `posts`는 25개이다.

세 API의 데이터는 같다. joinedload는 JOIN 한 번, selectinload는 게시글과 댓글을 따로 조회한다는 차이에 주목하고, 1회가 항상 빠르다는 뜻은 아님을 기억한다.

## N+1 문제 실습 4단계: 작성자와 댓글을 함께 조회
- `GET /nplusone/posts/full`: 게시글마다 `user`(게시글 작성자)와 `comments`를 반환한다. 둘 다 지연 로딩이라 게시글 1회 + 작성자 5회 + 댓글 25회 = 총 31회이다.
- `GET /nplusone/posts/full/optimized`: 작성자에 `joinedload(PostNPlusOne.user)`, 댓글에 `selectinload(PostNPlusOne.comments)`를 함께 적용. 첫 SQL은 게시글+작성자 JOIN, 두 번째는 댓글 IN 조회로 총 2회이다.

개선 전후 `posts`의 user와 comments가 같은지 확인한다.

## N+1 문제 실습 5단계: 게시글 → 댓글 → 댓글 작성자 조회
- `GET /nplusone/posts/with-comment-users`: 댓글 목록과 댓글 작성자를 지연 로딩해 게시글 1회 + 댓글 25회 + 댓글 작성자 5회 = 총 31회이다. 여러 댓글이 같은 사용자를 공유하므로 사용자 조회는 5회뿐이다.
- `GET /nplusone/posts/with-comment-users/optimized`: `selectinload(PostNPlusOne.comments).joinedload(CommentNPlusOne.user)` 적용. 게시글 조회 1회 + 댓글에 사용자를 JOIN한 IN 조회 1회 = 총 2회이다.

`/full/optimized`도 2회지만 JOIN 대상이 다르다. `/full/optimized`는 게시글과 작성자를, 이 API는 댓글과 작성자를 JOIN한다. `queries`의 JOIN 조건과 응답에서 `user`가 들어 있는 위치(posts 아래 vs comments 아래)를 비교한다.

## SQLAlchemy 일반 join()과 joinedload()의 차이
`join()`은 연결한 테이블의 컬럼으로 필터링·정렬할 때 쓰고, 관계 객체를 채워 주지는 않는다.
```python
from mysite_nplusone.models import PostNPlusOne, UserNPlusOne

stmt = (
    select(PostNPlusOne)
    .join(PostNPlusOne.user)
    .where(UserNPlusOne.name == "Alice")
)
posts = db.scalars(stmt).all()
```
```sql
SELECT p.id, p.title, p.user_id
FROM post_nplusone AS p
JOIN user_nplusone AS u ON u.id = p.user_id
WHERE u.name = 'Alice';
```
- SELECT에 게시글 컬럼만 있으므로 `post.user`는 미리 채워지지 않는다. 관계 객체도 필요하면 `joinedload()` 같은 로딩 옵션을 추가한다.

## N+1 문제 복습 Q&A
- Q. N+1 문제에서 1과 N은 각각 무엇인가?
  A. 1은 목록을 가져오는 첫 조회, N은 목록 항목마다 연관 데이터를 가져오는 추가 조회 횟수이다.
- Q. SQLAlchemy relationship()의 기본 로딩 방식과 N+1의 관계는?
  A. 기본은 지연 로딩이라, 루프에서 관계 속성에 접근할 때마다 SELECT가 실행되어 N+1이 생긴다.
- Q. 1:N 컬렉션에 joinedload를 쓸 때 꼭 필요한 것은?
  A. `db.scalars(stmt).unique().all()`처럼 `.unique()`를 붙여야 한다. 없으면 예외가 난다.
- Q. N:1 관계와 1:N 관계에 우선 고려할 즉시 로딩 전략은?
  A. N:1·1:1은 `joinedload`, 1:N·M:N은 `selectinload`이다.
- Q. `select(Post).join(Post.user)`만으로 post.user가 미리 로딩되나?
  A. 아니다. join()은 필터·정렬용이며, 관계 객체를 채우려면 `joinedload()` 등을 추가해야 한다.
