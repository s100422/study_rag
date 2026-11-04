---
part: backend
lesson: 간단한 게시판 구현
order: 2
source_type: web
tags: [fastapi, crud, apirouter, restful, path-parameter, board]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1437/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 간단한 게시판 구현

## 간단한 게시판 구현 요약
FastAPI의 APIRouter로 id·제목·내용을 가진 게시글을 메모리 리스트에 저장하고, 생성·조회·수정·삭제(CRUD) API를 만드는 실습이다. 이 단계에서는 요청 본문 없이 고정된 값으로 게시글을 만들고 수정한다.

## 게시판 RESTful API의 경로와 HTTP 메서드
RESTful API는 자원을 URL로, 그 자원에 할 행위를 HTTP 메서드로 표현한다. 게시판에서는 게시글 목록을 `/posts`, 특정 게시글을 `/posts/{id}`로 나타낸다.
- 게시글 생성: `POST /posts` → `@router.post("")`
- 전체 게시글 조회: `GET /posts` → `@router.get("")`
- 단일 게시글 조회: `GET /posts/{id}` → `@router.get("/{id}")`
- 게시글 수정: `PUT /posts/{id}` → `@router.put("/{id}")`
- 게시글 삭제: `DELETE /posts/{id}` → `@router.delete("/{id}")`

PUT은 자원 전체를 바꿀 때, PATCH는 일부만 바꿀 때 쓴다. 이 게시판은 제목과 내용을 모두 바꾸므로 PUT을 쓴다.

## 간단한 게시판 파일 구조
`fastapi_basic` 프로젝트에서 게시판 관련 파일은 세 개다.
- `main.py`: FastAPI 앱을 만들고 게시판 라우터를 연결한다.
- `mysite/post.py`: 게시글 데이터 구조(Post 클래스)를 정의한다.
- `mysite/post_api.py`: 게시글을 저장하고 CRUD 요청을 처리한다.

## 간단한 게시판 실습 1단계: Post 클래스 정의
게시판의 Post 클래스는 게시글의 식별자, 제목, 내용을 속성으로 담는 일반 파이썬 클래스다.
```python
# mysite/post.py
class Post:
    def __init__(self, id, title, content):
        self.id = id
        self.title = title
        self.content = content
```

## 간단한 게시판 실습 2단계: APIRouter와 메모리 저장소
게시판의 `post_api.py`에 라우터와 게시글 리스트, 마지막 ID를 둔다.
```python
# mysite/post_api.py
from fastapi import APIRouter
from .post import Post

router = APIRouter(prefix="/posts", tags=["mysite"])

posts = [Post(1, "기본 제목", "기본 내용")]  # 초기 데이터
post_id = 1                                 # 마지막으로 부여한 ID
```
- `APIRouter`: `main.py`와 다른 파일에 있는 엔드포인트를 묶는다.
- `prefix="/posts"`: 모든 엔드포인트 경로 앞에 붙는 공통 경로다.
- `tags=["mysite"]`: Swagger UI에서 게시판 API를 mysite 그룹으로 묶는다.
- 게시글은 메모리에만 있으므로 서버가 재시작되거나 코드 변경으로 리로드되면 초기 데이터로 돌아간다.

## 간단한 게시판 실습 3단계: main.py에 라우터 연결
게시판 라우터는 `app.include_router()`로 FastAPI 앱에 등록해야 동작한다.
```python
# main.py
from fastapi import FastAPI
from mysite.post_api import router as post_router

app = FastAPI()
app.include_router(post_router)
```
서버 실행 후 `http://127.0.0.1:8000/docs`의 mysite 그룹에서 `Try it out` → `Execute`로 요청을 보낸다. 브라우저 주소창 접속은 GET만 보내므로, 생성·수정·삭제는 Swagger UI에서 실행한다.
```bash
uv run fastapi dev main.py
```

## 간단한 게시판 실습 4단계: 게시글 생성(Create)
게시판의 `POST /posts`는 ID를 1 늘리고 새 Post 객체를 리스트에 추가한 뒤 반환한다. 제목과 내용은 아직 고정값이다.
```python
@router.post("")
def create_post():
    global post_id
    post_id += 1
    post = Post(post_id, "제목", "내용")
    posts.append(post)
    return post
```
- `global post_id`: 함수 안에서 모듈 변수 `post_id`를 바꾸기 위해 필요하다.

## 간단한 게시판 실습 5단계: 전체 게시글 조회(Read)
게시판의 `GET /posts`는 리스트에 저장된 게시글 전체를 그대로 반환한다.
```python
@router.get("")
def get_posts():
    return posts
```

## 게시판 경로 매개변수(path parameter)란
경로 매개변수는 URL 경로 안에 변수를 넣어 값을 전달하는 방식으로, 중괄호로 변수명을 지정한다. `/posts/{id}`에서 `id`는 게시글 식별자이며, `/posts/1`로 요청하면 함수의 `id` 매개변수에 1이 들어간다. 매개변수를 `id: int`로 선언하면 FastAPI가 경로 값을 정수로 변환하고 검증한다.

## 간단한 게시판 실습 6단계: 단일 게시글 조회(Read)
게시판의 `GET /posts/{id}`는 리스트를 돌며 id가 일치하는 게시글을 반환하고, 없으면 `None`을 반환한다.
```python
@router.get("/{id}")
def get_post(id: int):
    for post in posts:
        if post.id == id:
            return post
    return None
```

## 간단한 게시판 실습 7단계: 게시글 수정(Update)
게시판의 `PUT /posts/{id}`는 해당 게시글의 제목과 내용을 고정값으로 바꾼다.
```python
@router.put("/{id}")
def update_post(id: int):
    for post in posts:
        if post.id == id:
            post.title = "수정된 제목"
            post.content = "수정된 내용"
            return post
    return None
```

## 간단한 게시판 실습 8단계: 게시글 삭제(Delete)
게시판의 `DELETE /posts/{id}`는 일치하는 게시글을 리스트에서 꺼내 반환한다. 못 찾으면 문자열 "삭제 실패"를 반환한다.
```python
@router.delete("/{id}")
def delete_post(id: int):
    for i, post in enumerate(posts):
        if post.id == id:
            return posts.pop(i)
    return "삭제 실패"
```
- `enumerate(posts)`: 인덱스와 게시글을 함께 꺼낸다.
- `posts.pop(i)`: 해당 인덱스를 제거하면서 그 요소를 반환한다.

## 간단한 게시판 실행 확인 순서
게시판 서버를 재시작해 초기 데이터 상태로 만든 뒤, Swagger UI에서 다음 순서로 요청하고 응답을 예상과 비교한다.
- `GET /posts`: 초기 게시글(id=1)이 보인다.
- `POST /posts`: 제목 "제목", 내용 "내용"인 id=2 게시글이 생긴다.
- `GET /posts/2`: 방금 만든 게시글이 조회된다.
- `PUT /posts/2`: 제목·내용이 "수정된 제목", "수정된 내용"으로 바뀐다.
- `GET /posts/2`: 바뀐 내용이 조회된다.
- `DELETE /posts/2`: 삭제된 게시글이 응답으로 돌아온다.
- `GET /posts`: 삭제한 게시글이 목록에 없다.

## 간단한 게시판 구현 복습 Q&A
- Q. 게시판 API에서 `prefix="/posts"`인 APIRouter에 `@router.get("/{id}")`를 쓰면 실제 경로는?
  A. `GET /posts/{id}`이다.
- Q. 게시판 라우터를 FastAPI 앱에 등록하는 코드는?
  A. `app.include_router(post_router)`
- Q. 게시판 `create_post`에서 `global post_id`가 필요한 이유는?
  A. 함수 안에서 모듈 수준 변수 `post_id`의 값을 바꾸기 위해서다.
- Q. 게시판 데이터가 서버 재시작 후 초기화되는 이유는?
  A. 게시글을 DB가 아닌 메모리의 파이썬 리스트에 저장하기 때문이다.
- Q. 게시판 수정에 PATCH가 아닌 PUT을 쓴 이유는?
  A. 제목과 내용을 모두 바꾸는 전체 수정이기 때문이다.
