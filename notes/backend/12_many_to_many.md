---
part: backend
lesson: M:N 관계
order: 12
source_type: web
tags: [sqlalchemy, many_to_many, association_proxy, uniqueconstraint, cascade, fastapi]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1445/
note: 개인 학습용 요약. 외부 공유 금지.
---

# M:N 관계

## M:N 관계 요약
게시글(PostMN)과 태그(TagMN)를 연결 테이블(PostTagMN)로 이어 M:N 관계를 만들고, SQLAlchemy `association_proxy`로 `post.tags`처럼 태그를 바로 다루는 FastAPI 예제이다. 코드는 `fastapi_ai/fastapi_basic/mysite_many_to_many/`에 있다.

## M:N 관계란: 게시글과 태그 예시
M:N 관계는 양쪽이 서로 여러 개와 연결되는 관계이다. 게시글 하나에 태그 여러 개를 달 수 있고, 태그 하나도 여러 게시글에서 쓰인다. DB에서는 두 테이블 사이에 연결 테이블을 두고, 연결 한 건마다 게시글 ID와 태그 ID를 한 행으로 저장한다.
- `post_mn`(PostMN): 게시글. id, title, content
- `tag_mn`(TagMN): 태그. id, name(UNIQUE)
- `post_tag_mn`(PostTagMN): 연결. id, post_id(FK), tag_id(FK)

결국 M:N은 `post_mn 1:N post_tag_mn`과 `tag_mn 1:N post_tag_mn` 두 개의 1:N 관계로 표현된다. 예를 들어 연결 행이 (1,1), (1,2), (2,1)이면 게시글 1에는 태그 1·2가 붙고, 태그 1은 게시글 1·2가 함께 쓴다.

## M:N 관계 예제 API 목록
기본 주소는 `http://127.0.0.1:8000`이다.
- `POST /posts-mn`: 태그 없이 게시글 등록 (201)
- `GET /posts-mn`: 게시글 목록 (200)
- `POST /posts-mn/with-tags`: 태그와 함께 게시글 등록 (201)
- `GET /posts-mn/{post_id}`: 태그 포함 상세 조회 (200)
- `PUT /posts-mn/{post_id}`: 제목·내용 수정 (200)
- `DELETE /posts-mn/{post_id}`: 게시글과 그 연결 삭제, 태그는 남김 (204)
- `POST /tags-mn`, `GET /tags-mn`: 태그 등록(201)·목록(200)
- `POST /posts-mn/{post_id}/tags`: 게시글에 태그 연결, 없는 태그는 생성 (201)
- `DELETE /posts-mn/{post_id}/tags/{tag_id}`: 연결만 해제 (204)

## M:N 관계 모델 1: 게시글 PostMN
PostMN은 연결 객체 목록(`post_tags`)과, 그 연결을 거쳐 태그에 바로 접근하는 프록시(`tags`)를 가진다.
```python
# mysite_many_to_many/models/post_mn.py
from .post_tag_mn import PostTagMN

class PostMN(Base):
    __tablename__ = "post_mn"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    post_tags: Mapped[list["PostTagMN"]] = relationship(
        "PostTagMN",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostTagMN.id",
    )
    tags: AssociationProxy[list["TagMN"]] = association_proxy(
        "post_tags", "tag", creator=lambda tag: PostTagMN(tag=tag)
    )
```
- `post_tags`: 태그 자체가 아니라 연결 객체 PostTagMN 목록이다.
- `cascade="all, delete-orphan"`: 목록에서 빠진 연결 객체는 DB에서도 삭제된다.
- `PostTagMN`은 creator에서 실제로 객체를 만들므로 `TYPE_CHECKING`이 아닌 일반 import로 가져온다.

## M:N 관계 모델 2: 태그 TagMN
여러 게시글이 같은 태그를 쓰면 TagMN 하나를 공유하고, 게시글마다 PostTagMN 연결 객체가 따로 생긴다.
```python
# mysite_many_to_many/models/tag_mn.py
class TagMN(Base):
    __tablename__ = "tag_mn"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    post_tags: Mapped[list["PostTagMN"]] = relationship(
        "PostTagMN",
        back_populates="tag",
        cascade="all, delete-orphan",
        order_by="PostTagMN.id",
    )
```
- `name`은 `unique=True`라 같은 이름의 태그는 하나만 존재한다.

## M:N 관계 모델 3: 연결 PostTagMN
PostTagMN은 게시글 ID와 태그 ID를 외래키로 갖는 연결 테이블 모델이다.
```python
# mysite_many_to_many/models/post_tag_mn.py
class PostTagMN(Base):
    __tablename__ = "post_tag_mn"
    __table_args__ = (
        UniqueConstraint("post_id", "tag_id", name="uq_post_tag_mn_post_tag"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post_mn.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag_mn.id"), nullable=False)
    post: Mapped["PostMN"] = relationship("PostMN", back_populates="post_tags")
    tag: Mapped["TagMN"] = relationship("TagMN", back_populates="post_tags")
```

## M:N 관계 중복 방지 제약 조건
M:N 예제는 두 가지 중복을 DB 제약으로 막는다.
- `TagMN.name`의 `unique=True`: 같은 이름의 태그가 여러 개 생기는 것을 막는다.
- `PostTagMN`의 `UniqueConstraint("post_id", "tag_id")`: 같은 게시글에 같은 태그를 두 번 연결하는 것을 막는다.

post_id 하나, tag_id 하나는 여러 행에 나올 수 있지만 (post_id, tag_id) 조합은 한 번만 있어야 한다. 두 컬럼을 묶는 제약은 `__table_args__`에 튜플로 넣는다.

모델은 `models/__init__.py`에서 모두 import해 등록한다.
```python
# mysite_many_to_many/models/__init__.py
from .post_mn import PostMN
from .tag_mn import TagMN
from .post_tag_mn import PostTagMN
```

## SQLAlchemy association_proxy 인자와 동작
프록시(Proxy)는 실제 대상 대신 접근을 처리해 주는 대리자이다. `association_proxy`를 쓰면 연결 객체를 거치지 않고 `post.tags`로 태그를 다룬다.
```python
tags = association_proxy(
    "post_tags",                          # 연결 객체를 담은 관계 속성 이름
    "tag",                                # 연결 객체에서 읽을 속성 이름
    creator=lambda tag: PostTagMN(tag=tag),  # 값을 받아 연결 객체 생성
)

post.post_tags[0].tag   # 연결 객체를 거쳐 접근
post.tags[0]            # 같은 TagMN 객체
post.tags.append(tag)   # creator가 PostTagMN(tag=tag)를 만들어 post_tags에 추가
```
- 첫째·둘째 인자는 속성 이름 문자열이다. 클래스명이나 테이블명이 아니다.
- creator는 추가할 때만 호출되고 조회할 때는 호출되지 않는다.
- 게시글이 세션에 등록되면 save-update cascade가 연결 객체와 새 태그도 함께 저장 대상으로 삼는다. 연결 객체를 따로 save할 필요가 없고, commit 시 확정된다.

## M:N 관계 요청·응답 스키마
태그 입력은 이름 문자열 목록, 상세 응답의 태그는 id·name 객체 목록이다.
```python
# schemas/tag.py
class TagCreate(BaseModel):
    name: str

class TagResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)

# schemas/post.py
class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)

class PostCreateWithTags(PostCreate):
    tags: list[str] = Field(default_factory=list)

class PostDetailResponse(BaseModel):
    id: int
    title: str
    content: str
    tags: list[TagResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

class PostListResponse(BaseModel):
    id: int
    title: str
    model_config = ConfigDict(from_attributes=True)
```
- `PostDetailResponse.tags`는 `PostMN.tags` 프록시에서 읽는다.
- `PostCreateWithTags.tags`를 생략하면 태그 없이 등록된다.

## M:N 관계 Repository: 태그 이름 조회와 연결 존재 확인
태그 Repository는 이름 하나 또는 여러 개로 태그를 찾고, 연결 Repository는 EXISTS로 연결이 이미 있는지 확인한다.
```python
# repositories/tag_repository.py
class TagRepository:
    def find_by_name(self, db: Session, name: str):
        return db.scalar(select(TagMN).where(TagMN.name == name))

    def find_by_names(self, db: Session, names: list[str]):
        if not names:
            return []
        return db.scalars(select(TagMN).where(TagMN.name.in_(names))).all()

# repositories/post_tag_repository.py
class PostTagRepository:
    def exists(self, db: Session, post_id: int, tag_id: int):
        stmt = (
            select(PostTagMN.id)
            .where(PostTagMN.post_id == post_id, PostTagMN.tag_id == tag_id)
            .exists()
        )
        return db.scalar(select(stmt))
```
- `find_by_names()`: IN 조건으로 한 번에 조회하고, 빈 목록이면 DB에 가지 않는다.

## M:N 관계 실습: 태그 등록 Service와 Router
태그 등록 시 같은 이름이 있으면 400을 반환한다.
```python
# services/tag_service.py
def create_tag(self, db: Session, data: TagCreate):
    with db.begin():
        if tag_repository.find_by_name(db, data.name) is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 존재하는 태그 이름입니다.",
            )
        new_tag = TagMN(name=data.name)
        tag_repository.save(db, new_tag)
    return new_tag

# routers/tag_router.py
router = APIRouter(prefix="/tags-mn", tags=["mysite_many_to_many"])

@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(data: TagCreate, db: Annotated[Session, Depends(get_db)]):
    return tag_service.create_tag(db, data)
```

## M:N 관계 실습: 기존 게시글에 태그 연결
`POST /posts-mn/{post_id}/tags`는 태그 이름을 받아 연결한다. 태그가 없으면 새로 만들고, 기존 태그일 때만 EXISTS로 중복 연결을 검사한다.
```python
# services/post_service.py
def add_tag_to_post(self, db: Session, post_id: int, data: TagCreate):
    with db.begin():
        post = self.get_post(db, post_id)
        tag = tag_repository.find_by_name(db, data.name)
        if tag is None:
            tag = TagMN(name=data.name)
        elif post_tag_repository.exists(db, post.id, tag.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 이 게시글에 등록된 태그입니다.",
            )
        post.tags.append(tag)
    return post
```
- 새 태그는 연결된 적이 없으니 중복 검사가 필요 없다.
- `post.tags.append(tag)`에 객체를 넘기므로 새 태그 ID를 미리 얻지 않아도 된다. 태그 생성과 연결이 한 트랜잭션에서 저장된다.
- Router는 `response_model=PostDetailResponse`, `status_code=201`로 선언하고 서비스만 호출한다.

## M:N 관계 실습: 태그와 함께 게시글 등록
`POST /posts-mn/with-tags`는 태그 이름 목록에서 중복을 지우고, 기존 태그는 재사용하며 없는 것만 만든다.
```python
# services/post_service.py
def create_post_with_tags(self, db: Session, data: PostCreateWithTags):
    with db.begin():
        names = list(dict.fromkeys(data.tags))
        tags_by_name = {
            tag.name: tag for tag in tag_repository.find_by_names(db, names)
        }
        new_post = PostMN(title=data.title, content=data.content)
        for name in names:
            tag = tags_by_name.get(name)
            if tag is None:
                tag = TagMN(name=name)
            new_post.tags.append(tag)
        post_repository.save(db, new_post)
    return new_post
```
- `dict.fromkeys(data.tags)`: 입력 순서를 유지하며 중복 이름을 제거한다.
- `new_post.tags.append(tag)`: 프록시 creator가 연결 객체를 만든다.
- 게시글만 save해도 save-update cascade로 연결 객체와 새 태그가 같이 저장된다. `tag_repository.save()`가 따로 필요 없다.

## M:N 관계 실습: 태그 연결 해제와 삭제 범위
`DELETE /posts-mn/{post_id}/tags/{tag_id}`는 게시글의 태그 목록에서 해당 ID를 찾아 연결만 지운다.
```python
# services/post_service.py
def remove_tag_from_post(self, db: Session, post_id: int, tag_id: int):
    with db.begin():
        post = self.get_post(db, post_id)
        tag = next((tag for tag in post.tags if tag.id == tag_id), None)
        if tag is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 게시글에 연결된 태그를 찾을 수 없습니다.",
            )
        post.tags.remove(tag)
```
- 연결된 태그가 없으면 404이다.
- `post.tags.remove(tag)`로 연결 객체가 목록에서 빠지면 delete-orphan에 의해 그 연결 행만 삭제된다. 게시글·태그 자체와 다른 게시글의 연결은 그대로다.
- Router는 `status_code=204`로 선언하고 반환값이 없다.

## M:N 관계 실습: main.py에 모델과 Router 등록
main.py에서 모델 패키지와 두 Router를 import한다. 모델은 `Base.metadata.create_all(bind=engine)` 실행 전에 import해야 테이블이 만들어진다.
```python
# main.py
from mysite_many_to_many import models as many_to_many_models
from mysite_many_to_many.routers.post_router import router as many_to_many_post_router
from mysite_many_to_many.routers.tag_router import router as many_to_many_tag_router

# app 생성 이후
app.include_router(many_to_many_post_router)
app.include_router(many_to_many_tag_router)
```
확인은 `http://127.0.0.1:8000/docs`의 `mysite_many_to_many` 그룹에서 한다.

## M:N 관계 예제의 요청 상황별 동작
- 같은 이름으로 태그 단독 등록: 400
- 없는 이름의 태그를 게시글에 연결: 태그를 생성해서 연결
- 이미 연결된 태그를 다시 연결: 400
- 없는 게시글에 연결·해제 요청: 404
- 없거나 게시글에 연결되지 않은 태그의 연결 해제: 404
- 태그 이름을 중복 입력: 한 번만 연결
- 태그 목록 생략 또는 빈 목록: 태그 없이 게시글 등록

태그 이름은 입력 문자열 그대로 비교하므로 `Python`과 `python`은 다른 태그로 처리된다.

## M:N 관계 동작 확인 1: 태그와 함께 등록하고 공유 확인
`POST /posts-mn/with-tags`로 중복 이름이 섞인 태그와 함께 게시글을 등록한다.
```json
{
  "title": "M:N 관계 예제",
  "content": "게시글에 여러 태그를 연결합니다.",
  "tags": ["Python", "FastAPI", "Python"]
}
```
응답의 `tags`에는 Python이 한 번만 들어간다 (예: `[{"id": 1, "name": "Python"}, {"id": 2, "name": "FastAPI"}]`).

이어서 `tags: ["Python", "SQLAlchemy"]`로 두 번째 게시글을 등록하면 두 응답의 Python ID가 같아야 하고, `GET /tags-mn`에도 Python은 하나만 있어야 한다.

## M:N 관계 동작 확인 2: 중복 연결, 연결 해제, 게시글 삭제
- `POST /posts-mn/{post_id}/tags`에 `{"name": "Database"}`를 보내 연결한다. 같은 이름을 다시 보내면 400, `POST /tags-mn`으로 기존 이름을 등록해도 400이다.
- 첫 번째 게시글에서 Python 연결을 해제하면 첫 게시글에서는 사라지고 두 번째 게시글에는 남는다. 같은 해제를 다시 하면 404이다.
- 첫 번째 게시글을 삭제해도 태그 목록과 두 번째 게시글의 연결은 유지된다.

DB에서는 다음처럼 확인한다 (1은 삭제한 게시글 ID로 바꾼다). 연결 행은 없고 태그 행은 남아 있어야 한다.
```sql
SELECT * FROM post_tag_mn WHERE post_id = 1;
SELECT * FROM tag_mn ORDER BY id;
```

## M:N 관계 복습 Q&A
- Q. SQLAlchemy에서 게시글-태그 M:N 관계는 어떤 구조로 표현하나?
  A. 연결 테이블(post_tag_mn)을 두고, 게시글-연결과 태그-연결 두 개의 1:N 관계로 표현한다.
- Q. M:N 연결 테이블에서 같은 게시글에 같은 태그가 두 번 연결되지 않게 하려면?
  A. `__table_args__`에 `UniqueConstraint("post_id", "tag_id")`를 지정한다.
- Q. `association_proxy("post_tags", "tag", creator=...)`에서 creator는 언제 호출되나?
  A. `post.tags.append(tag)`처럼 값을 추가할 때 연결 객체를 만들기 위해 호출되고, 조회할 때는 호출되지 않는다.
- Q. M:N 예제에서 `post.tags.remove(tag)`를 하면 무엇이 삭제되나?
  A. delete-orphan에 의해 연결 행만 삭제되고, 게시글과 태그 자체는 남는다.
- Q. 태그와 함께 게시글을 등록할 때 연결 객체나 새 태그를 따로 save하지 않아도 되는 이유는?
  A. 게시글을 세션에 추가하면 save-update cascade가 연결 객체와 새 태그도 함께 저장 대상으로 포함하기 때문이다.
