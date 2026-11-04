---
part: backend
lesson: SQLAlchemy
order: 9
source_type: web
tags: [sqlalchemy, orm, session, select, transaction, commit, dirty-checking]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1447/
note: 개인 학습용 요약. 외부 공유 금지.
---

# SQLAlchemy

## SQLAlchemy 요약
SQLAlchemy 레슨은 ORM 개념과, 세션(`db`)으로 데이터를 생성·조회·수정·삭제하는 주요 메서드를 SQL문과 짝지어 정리한다. 예제의 `Post`는 게시글 모델(`posts` 테이블), `db`는 세션이다.

## ORM(Object-Relational Mapping)이란
ORM은 파이썬 클래스·객체를 DB 테이블·행과 연결해, SQL 대신 클래스와 메서드로 CRUD를 하게 해 주는 기술이다. SQLAlchemy가 대표적인 파이썬 ORM이다.
- 생산성: 반복적인 SQL 작성을 줄인다.
- 유지보수: 공통 CRUD 코드를 여러 DB에서 재사용하기 쉽다.
- 직관성: 데이터를 파이썬 객체와 속성으로 다룬다.

## SQLAlchemy 트랜잭션과 변경 반영 메서드
SQLAlchemy에서 트랜잭션은 여러 DB 작업을 하나로 묶어 확정하거나 취소하는 단위이다. 세션의 주요 메서드는 다음과 같다.
- `add()`: 새 객체를 세션에 등록
- `flush()`: 변경을 SQL로 실행하지만 확정하지 않음
- `commit()`: flush 후 트랜잭션 확정
- `rollback()`: 아직 확정하지 않은 변경 취소
- `refresh()`: DB에서 객체 값을 다시 읽어 옴

## SQLAlchemy 데이터 생성: add와 add_all
SQLAlchemy에서 새 데이터는 모델 객체를 만들어 세션에 추가하고 commit한다.
```python
new_post = Post(title="첫 번째 글", content="내용입니다")
db.add(new_post)
db.commit()
```
```sql
INSERT INTO posts (title, content) VALUES ('첫 번째 글', '내용입니다') RETURNING posts.id;
```
여러 객체는 `add_all()`로 한 번에 추가한다.
```python
posts = [
    Post(title="두 번째", content="내용2"),
    Post(title="세 번째", content="내용3")
]
db.add_all(posts)
db.commit()
```
```sql
INSERT INTO posts (title, content) VALUES ('두 번째', '내용2'), ('세 번째', '내용3');
```

## SQLAlchemy 기본키 조회: db.get
SQLAlchemy의 `db.get(모델, 기본키)`는 기본키로 객체 하나를 조회하고, 없으면 `None`을 돌려준다.
```python
post = db.get(Post, 1)
```
```sql
SELECT posts.id, posts.title, posts.content FROM posts WHERE posts.id = 1;
```

## SQLAlchemy 조회문 구성: select, scalars, scalar
SQLAlchemy 조회는 조회문을 만든 뒤 세션으로 실행하는 두 단계이다.
- `stmt`(Statement): 조회문을 담는 변수. `select(Post)`는 게시글 조회 구문을 만든다.
- `db.scalars(stmt)`: 조회문을 실행하고 결과 객체들을 꺼낼 수 있게 한다. `.all()`을 붙이면 리스트가 된다.
- `db.scalar(stmt)`: 조회문을 실행하고 첫 번째 객체를 돌려준다. 없으면 `None`.

## SQLAlchemy 결과 추출 메서드
SQLAlchemy에서 `db.scalars(stmt)` 뒤에 붙여 결과를 꺼내는 메서드는 다음과 같다.
- `.all()`: 전체 결과를 리스트로. 없으면 `[]`
- `.first()`: 첫 번째 결과. 없으면 `None`
- `.one()`: 결과 하나. 없거나 여러 개면 오류
- `.one_or_none()`: 결과 하나. 없으면 `None`, 여러 개면 오류

## SQLAlchemy 조회 예제: 전체·단일 조건·키워드 검색
SQLAlchemy의 `select()`에 `.where()`로 조건을 붙인다.
```python
stmt = select(Post)
posts = db.scalars(stmt).all()            # SELECT ... FROM posts;

stmt = select(Post).where(Post.id == 1)
post = db.scalar(stmt)                    # ... WHERE posts.id = 1;

stmt = select(Post).where(Post.title.like("%FastAPI%"))
posts = db.scalars(stmt).all()            # ... WHERE posts.title LIKE '%FastAPI%';
```
- `Post.title.like("%FastAPI%")`: 제목에 FastAPI가 포함된 행을 찾는 LIKE 조건이다.

## SQLAlchemy 조회 예제: and·or 다중 조건
SQLAlchemy의 `where()`에 조건을 쉼표로 여러 개 넘기면 AND로 묶이고, OR는 `or_()`, 명시적 AND는 `and_()`를 쓴다.
```python
stmt = select(Post).where(Post.id > 10, Post.title.like("%공부%"))
# WHERE posts.id > 10 AND posts.title LIKE '%공부%'

stmt = select(Post).where(or_(Post.id == 1, Post.title == "공지"))
# WHERE posts.id = 1 OR posts.title = '공지'

stmt = select(Post).where(
    and_(
        Post.id > 10,
        or_(Post.title == "공지", Post.title == "이벤트")
    )
)
# WHERE posts.id > 10 AND (posts.title = '공지' OR posts.title = '이벤트')
posts = db.scalars(stmt).all()
```
- `or_`, `and_`는 `sqlalchemy`에서 import한다.

## SQLAlchemy 조회 예제: 정렬과 결과 제한
SQLAlchemy에서 정렬은 `order_by()`, 개수 제한은 `limit()`으로 한다.
```python
stmt = select(Post).order_by(Post.id.desc())
posts = db.scalars(stmt).all()
# ORDER BY posts.id DESC

stmt = select(Post).order_by(Post.id.desc()).limit(10)
posts = db.scalars(stmt).all()
# ORDER BY posts.id DESC LIMIT 10
```
- `Post.id.desc()`: ID 내림차순(최신 글 먼저)

## SQLAlchemy 데이터 수정과 더티 체킹
SQLAlchemy에서 수정은 조회한 객체의 속성을 바꾸고 `commit()`하면 끝난다. 객체 변경을 SQLAlchemy가 자동으로 감지하는 것을 더티 체킹(변경 감지)이라고 한다.
```python
post = db.get(Post, 1)
post.title = "수정된 제목"
db.commit()
```
- UPDATE문을 직접 쓰거나 `db.add()`를 다시 할 필요가 없다.

## SQLAlchemy 데이터 삭제
SQLAlchemy에서 삭제는 `db.delete()`로 대상을 지정하고 `commit()`으로 확정한다.
```python
post = db.get(Post, 1)
db.delete(post)
db.commit()
```
```sql
DELETE FROM posts WHERE posts.id = 1;
```
페이지네이션, 전체 개수, 특정 컬럼 조회 같은 기능은 필요할 때 SQLAlchemy 문법을 찾아 적용한다.

## SQLAlchemy 복습 Q&A
- Q. SQLAlchemy의 `flush()`와 `commit()`의 차이는?
  A. `flush()`는 SQL을 실행만 하고 확정하지 않으며, `commit()`은 flush 후 트랜잭션을 확정한다.
- Q. `db.get(Post, 1)`에서 해당 행이 없으면?
  A. `None`을 반환한다.
- Q. `.one()`과 `.one_or_none()`의 차이는?
  A. 결과가 없을 때 `.one()`은 오류, `.one_or_none()`은 `None`이다. 여러 개면 둘 다 오류이다.
- Q. SQLAlchemy에서 OR 조건은 어떻게 쓰나?
  A. `select(Post).where(or_(조건1, 조건2))`
- Q. 조회한 객체의 속성만 바꾸고 commit해도 수정되는 이유는?
  A. 세션의 더티 체킹이 변경을 감지해 UPDATE를 실행하기 때문이다.
