---
part: backend
lesson: 관심사 분리 및 레이어드 아키텍쳐
order: 6
source_type: web
tags: [fastapi, separation-of-concerns, layered-architecture, router, service, repository]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1442/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 관심사 분리 및 레이어드 아키텍쳐

## 관심사 분리 및 레이어드 아키텍쳐 요약
한 함수에 몰려 있던 게시판 로직을 Router(표현), Service(비즈니스), Repository(데이터 접근) 계층으로 나눠 `mysite4`에 다시 구현하는 실습이다. 경로는 `/posts-layered`를 쓴다.

## 관심사 분리(Separation of Concerns, SoC)란
관심사 분리는 프로그램을 독립된 관심사로 나눠 각 부분이 하나의 목적만 갖도록 하는 설계 원칙이다. 기존 `mysite3/post_api.py`의 `create_post`는 한 함수 안에서 다음을 모두 처리한다.
- 요청 경로와 응답 형식 지정 (데코레이터)
- 입력 검증 (빈 제목·내용이면 422)
- ID 부여, Post 객체 생성
- 리스트에 저장
이렇게 섞인 역할을 나누는 것이 이 레슨의 출발점이다.

## 레이어드 아키텍처(Layered Architecture)란
FastAPI는 특정 구조를 강제하지 않는다. 레이어드 아키텍처는 관심사 분리를 적용하는 한 방법으로, 코드를 역할별 계층으로 나눈다.
- Presentation Layer(표현 계층): HTTP 요청·응답 담당. URL, 메서드, 응답 모델, 성공 상태 코드를 지정하고 Pydantic이 검증한 데이터를 Service에 넘긴다. 실습의 APIRouter 함수들.
- Business Layer(비즈니스 계층): 규칙을 확인하고 한 작업의 처리 흐름을 완성한다. Repository에 데이터를 요청하고 결과에 따라 진행·중단하며, 여러 Repository를 조합할 수 있다. 실습의 PostService.
- Data Access Layer(데이터 접근 계층): 저장소 CRUD 담당. 실습의 PostRepository가 리스트와 ID 카운터를 관리하며, DB를 쓰면 SQL·ORM이 여기 들어간다.

## 레이어드 아키텍처의 요청·응답 흐름
레이어드 아키텍처에서 호출 방향은 클라이언트 → Router → Service → Repository이다. Router가 Service 메서드를 호출하고, Service는 데이터 처리가 필요할 때 Repository 메서드를 호출한다.
```text
클라이언트 --HTTP 요청--> Router --작업 호출--> Service --저장·조회 요청--> Repository
클라이언트 <--HTTP 응답-- Router <--결과 반환-- Service <--결과 반환-- Repository
```
정상 결과는 `return`으로 Repository → Service → Router 순으로 돌아온다. 되돌아오는 방향은 반환일 뿐, Repository가 Service나 Router를 호출한다는 뜻이 아니다.

## 레이어드 아키텍처에서 Service가 담당하는 비즈니스 로직
비즈니스 로직은 애플리케이션이 지켜야 할 규칙과 그 규칙을 적용하는 절차다. Service는 데이터를 조회하고, 실행 조건을 판단하고, 여러 기능을 이어 하나의 작업을 완성한다.
- 게시글 수정 예: 게시글이 존재하고, 요청자가 작성자이며, 내용이 유효해야 한다. 흐름은 조회 → 존재·권한·내용 확인 → 수정 요청.
- 상품 주문 예: 재고가 충분하고 쿠폰은 조건 충족 시에만 적용한다. 흐름은 상품·쿠폰 조회 → 조건 확인 → 최종 금액 계산 → 주문 저장·재고 반영.
- `get_posts()`처럼 추가 규칙이 없으면 Repository 결과를 그대로 반환해도 된다.

## 레이어드 아키텍처의 Pydantic 검증과 Service 검증 구분
형식이 올바른 요청이라도 작업을 진행할 수 있는지는 따로 확인해야 한다.
- Pydantic: 요청 데이터의 형식과 필드 조건. 예) 필수 값 존재, 제목 길이, 주문 수량이 1 이상 정수인가.
- Service: 작업 진행 조건과 업무 규칙. 예) 수정할 게시글이 존재하는가, 수정 권한이 있는가, 재고가 충분한가.

검증 위치는 규칙 성격에 따라 정한다. 입력값끼리 비교는 Pydantic에서도 되고, 할인 조건 같은 업무 규칙은 Service에 둘 수 있다. 이 실습에서 PostCreate는 필수·타입을, Service는 빈 문자열을 검사한다(빈 문자열은 Pydantic `Field`로도 가능). 게시글 존재 여부는 `PostRepository.find_by_id()`가 None을 주면 `PostService.get_post()`가 HTTPException을 던져 404가 나간다.

## 레이어드 아키텍처 계층 분리의 장점
- 유지보수: 요청 형식이나 저장 방식을 바꿀 때 수정 범위가 줄어든다.
- 테스트: Router 없이 Service·Repository 메서드를 직접 호출해 확인할 수 있다.
- 협업: 계층의 역할과 메서드 기준으로 작업을 나눌 수 있다.

변경 종류별로 주로 고칠 계층은 다음과 같다.
- API 경로나 성공 상태 코드 변경 → Router
- 할인 조건이나 계산 방식 변경 → Service
- 리스트 저장을 DB 저장으로 변경 → Repository

Repository의 메서드 이름·매개변수·반환 형태를 유지하면 저장 방식이 바뀌어도 다른 계층의 변경을 줄일 수 있다.

## 레이어드 아키텍처 실습: mysite4 파일 구조
레이어드 아키텍처 실습의 `fastapi_basic/mysite4`는 계층별 하위 폴더로 나뉜다.
```text
mysite4/
├── repositories/
│   └── post_repository.py   # PostRepository 클래스 + post_repository 객체
├── routers/
│   └── post_router.py       # 모듈 수준 Router 함수
├── schemas/
│   └── post.py              # Post 객체, 요청·응답 모델
└── services/
    └── post_service.py      # PostService 클래스 + post_service 객체
```
각 클래스 정의 아래에서 `post_service = PostService()`, `post_repository = PostRepository()` 객체를 만든다. Repository 객체가 `self.posts`, `self.post_id`를 보관하며 여러 요청에서 공유되고, 서버 재시작 시 초기화된다.

## 레이어드 아키텍처 실습 1단계: schemas/post.py
레이어드 아키텍처의 schemas에는 저장용 Post와 요청·응답 DTO를 둔다.
```python
from pydantic import BaseModel

class Post:
    def __init__(self, title, content):
        self.id = None
        self.title = title
        self.content = content

class PostCreate(BaseModel):
    title: str
    content: str

class PostDetailResponse(BaseModel):
    id: int
    title: str
    content: str

class PostListResponse(BaseModel):
    id: int
    title: str
```
- PostCreate는 요청 DTO, PostDetailResponse·PostListResponse는 응답 DTO이다.
- Post는 Service가 만들 때 아직 ID가 없어 `id=None`으로 시작한다. ID는 Repository가 저장할 때 부여하므로 생성자에 제목·내용만 받는다.

## 레이어드 아키텍처 실습 2단계: 라우터 생성과 main.py 연결
레이어드 아키텍처의 Router는 `routers/post_router.py`에 만들고 `main.py`에 등록한다.
```python
# mysite4/routers/post_router.py
from fastapi import APIRouter
router = APIRouter(prefix="/posts-layered", tags=["mysite4"])
```
```python
# main.py
from mysite4.routers.post_router import router as layered_router
app.include_router(layered_router)
```

## 레이어드 아키텍처 실습 3단계: Create - Repository
레이어드 아키텍처의 PostRepository.save는 Service가 만든 게시글에 ID를 부여하고 리스트에 저장한다.
```python
# mysite4/repositories/post_repository.py
from mysite4.schemas.post import Post, PostCreate

class PostRepository:
    def __init__(self):
        self.posts = []
        self.post_id = 0

    def save(self, new_post: Post):
        self.post_id += 1
        new_post.id = self.post_id
        self.posts.append(new_post)
        return new_post

post_repository = PostRepository()
```

## 레이어드 아키텍처 실습 4단계: Create - Service
레이어드 아키텍처의 PostService.create_post는 제목·내용 빈 문자열을 검사한 뒤 Post를 만들어 Repository에 저장을 요청한다.
```python
# mysite4/services/post_service.py
from fastapi import HTTPException, status
from mysite4.repositories.post_repository import post_repository
from mysite4.schemas.post import Post, PostCreate

class PostService:
    def create_post(self, data: PostCreate):
        if data.title == "":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail="title을 입력하세요")
        if data.content == "":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail="content를 입력하세요")
        new_post = Post(title=data.title, content=data.content)
        return post_repository.save(new_post)

post_service = PostService()
```

## 레이어드 아키텍처 실습 5단계: Create - Router
레이어드 아키텍처의 Router 함수는 HTTP 설정만 하고 실제 작업은 post_service에 맡긴다.
```python
# mysite4/routers/post_router.py
from fastapi import status
from mysite4.services.post_service import post_service
from mysite4.schemas.post import PostCreate, PostDetailResponse

@router.post("", response_model=PostDetailResponse, status_code=status.HTTP_201_CREATED)
def create_post(data: PostCreate):
    return post_service.create_post(data)
```

## 레이어드 아키텍처 실습 6단계: 전체 게시글 조회
레이어드 아키텍처의 전체 조회는 Repository가 리스트를 주고, Service는 추가 규칙 없이 그대로 반환한다.
```python
# PostRepository
def find_all(self):
    return self.posts

# PostService
def get_posts(self):
    return post_repository.find_all()

# post_router.py
from mysite4.schemas.post import PostCreate, PostDetailResponse, PostListResponse

@router.get("", response_model=list[PostListResponse])
def get_posts():
    return post_service.get_posts()
```

## 레이어드 아키텍처 실습 7단계: 단일 게시글 조회
레이어드 아키텍처의 단일 조회에서 Repository는 못 찾으면 None을 주고, Service가 None을 보고 404 예외를 발생시킨다.
```python
# PostRepository
def find_by_id(self, id: int):
    for post in self.posts:
        if post.id == id:
            return post
    return None

# PostService
def get_post(self, id: int):
    post = post_repository.find_by_id(id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="게시글을 찾을 수 없습니다.")
    return post

# post_router.py
@router.get("/{id}", response_model=PostDetailResponse)
def get_post(id: int):
    return post_service.get_post(id)
```

## 레이어드 아키텍처 실습 8단계: 게시글 수정
레이어드 아키텍처의 수정에서 Service는 빈 문자열 검사 후 `self.get_post(id)`로 존재를 확인(없으면 404)하고 Repository에 수정을 요청한다.
```python
# PostRepository
def update(self, id: int, data: PostCreate):
    for post in self.posts:
        if post.id == id:
            post.title = data.title
            post.content = data.content
            return post
    return None

# PostService
def update_post(self, id: int, data: PostCreate):
    if data.title == "":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="title을 입력하세요")
    if data.content == "":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="content를 입력하세요")
    self.get_post(id)
    return post_repository.update(id, data)

# post_router.py
@router.put("/{id}", response_model=PostDetailResponse)
def update_post(id: int, data: PostCreate):
    return post_service.update_post(id, data)
```

## 레이어드 아키텍처 실습 9단계: 게시글 삭제
레이어드 아키텍처의 삭제에서 Service는 `self.get_post(id)`로 존재를 확인한 뒤 Repository에 삭제를 요청하고, Router는 204를 반환한다.
```python
# PostRepository
def delete(self, id: int):
    for index, post in enumerate(self.posts):
        if post.id == id:
            return self.posts.pop(index)

# PostService
def delete_post(self, id: int):
    self.get_post(id)
    post_repository.delete(id)

# post_router.py
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(id: int):
    post_service.delete_post(id)
```

## 레이어드 아키텍처 실행 및 응답 확인
레이어드 아키텍처 게시판은 `fastapi_basic` 폴더에서 `uv run fastapi dev main.py`로 실행하고 `/docs`의 mysite4 그룹에서 확인한다. 생성 응답의 id를 조회·수정·삭제에 쓴다.
- 정상 입력으로 생성 → 201, id·title·content.
- 전체 조회 → 200, 각 게시글의 id·title만.
- 단일 조회·정상 수정 → 200, id·title·content.
- 빈 제목·내용으로 생성·수정 → 422, 검증 메시지, 데이터 변경 없음.
- 없는 ID 조회·삭제, 또는 없는 ID에 정상 입력으로 수정 → 404, "게시글을 찾을 수 없습니다."
- 삭제 성공 → 204, 본문 없음.

## 관심사 분리 및 레이어드 아키텍쳐 복습 Q&A
- Q. 레이어드 아키텍처 게시판의 호출 방향은?
  A. Router → Service → Repository. 결과는 return으로 역방향으로 돌아올 뿐, Repository가 위 계층을 호출하지 않는다.
- Q. 레이어드 아키텍처에서 "수정할 게시글이 존재하는가" 검증은 어느 계층에서 하나?
  A. Service. Repository의 `find_by_id()`가 None이면 Service가 404 HTTPException을 발생시킨다.
- Q. 레이어드 아키텍처에서 리스트 저장을 DB 저장으로 바꾸면 주로 어느 계층을 고치나?
  A. Repository. 메서드 이름·매개변수·반환 형태를 유지하면 다른 계층 변경이 줄어든다.
- Q. mysite4의 Post 생성자가 id를 받지 않는 이유는?
  A. ID는 Repository가 `save()`할 때 부여하므로, Service가 만들 때는 `id=None`으로 시작하기 때문이다.
- Q. 관심사 분리(SoC)란?
  A. 프로그램을 독립된 관심사로 나눠 각 부분이 하나의 목적만 갖게 하는 설계 원칙이다.
