---
part: backend
lesson: 상호작용이 가능한 게시판
order: 3
source_type: web
tags: [fastapi, pydantic, basemodel, request-body, dto, validation, crud]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1438/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 상호작용이 가능한 게시판

## 상호작용이 가능한 게시판 요약
클라이언트가 요청 본문(JSON)으로 보낸 제목과 내용을 Pydantic 모델로 검증받아 게시글을 생성·수정하는 실습이다. 경로는 `/posts-pydantic`, 코드는 `mysite2` 폴더에 둔다.

## Pydantic이란
Pydantic은 파이썬 타입 힌트로 데이터 구조를 정의하고 입력값을 검증하는 라이브러리다. FastAPI에서는 클라이언트가 보내는 요청 데이터의 형식을 정의할 때 쓴다.
- `BaseModel`을 상속하고 필드 이름과 타입을 선언한다.
- 기본값이 없는 필드는 필수, 기본값이 있는 필드는 생략 가능하다.
- 입력값은 모델 규칙에 따라 타입 변환·검증을 거치며, 필수 필드 누락이나 허용되지 않는 값이 오면 검증에 실패한다.

## HTTP 요청 본문(Request Body)이란
요청 본문은 클라이언트가 서버로 보낼 데이터를 담는 영역이다. 게시판에서는 게시글 생성·수정 시 제목과 내용을 JSON으로 담아 보내고, FastAPI가 이 JSON을 Pydantic 모델로 받아 검증한다.

## 상호작용 게시판 실습 1단계: PostCreate 모델 정의
`mysite2/post.py`에 요청용 Pydantic 모델 PostCreate와 서버용 Post 클래스를 둔다.
```python
# mysite2/post.py
from pydantic import BaseModel

class PostCreate(BaseModel):
    title: str
    content: str

class Post:
    def __init__(self, id, title, content):
        self.id = id
        self.title = title
        self.content = content
```
- `title: str`, `content: str`: 기본값이 없으니 둘 다 필수 문자열이다.
- `str` 선언은 길이를 제한하지 않으므로 빈 문자열 `""`도 통과한다.

## 상호작용 게시판의 요청 DTO와 Post 객체 구분
DTO(Data Transfer Object)는 주고받을 값을 묶어 담는 객체이며, Pydantic 모델 PostCreate가 요청 DTO 역할을 한다.
- PostCreate: `title`, `content`만 담는다. 클라이언트 요청 데이터를 받고 필수 값·타입을 검증한다.
- Post: `id`, `title`, `content`를 담는다. 서버가 관리하는 게시글이며 `posts` 리스트에 저장된다.

게시글 생성 시 클라이언트는 제목과 내용만 보내고, 서버가 검증된 값에 직접 만든 id를 더해 Post를 만든다. 받는 데이터와 관리하는 데이터의 구성이 달라 클래스를 둘로 나눈다.

## 상호작용 게시판 실습 2단계: 라우터와 저장소 설정
`mysite2/post_api.py`에 라우터, 빈 게시글 리스트, ID 카운터를 두고 `main.py`에서 라우터를 연결한다.
```python
# mysite2/post_api.py
from fastapi import APIRouter
from mysite2.post import PostCreate, Post

router = APIRouter(prefix="/posts-pydantic", tags=["mysite2"])
posts = []
post_id = 0
```
```python
# main.py
from fastapi import FastAPI
from mysite2.post_api import router as pydantic_router

app = FastAPI()
app.include_router(pydantic_router)
```

## 상호작용 게시판 실습 3단계: 요청 본문으로 게시글 생성
함수 매개변수를 `post_data: PostCreate`로 선언하면 FastAPI가 요청 본문 JSON을 읽고 검증해 PostCreate 객체로 넘겨준다.
```python
@router.post("")
def create_post(post_data: PostCreate):
    global post_id
    post_id += 1
    new_post = Post(post_id, post_data.title, post_data.content)
    posts.append(new_post)
    return new_post
```
- 흐름: JSON 요청 본문 → PostCreate 검증 → `create_post()` 실행 → JSON 응답.
- 검증에 실패하면 함수는 실행되지 않고 검증 오류 응답이 나간다.

## 상호작용 게시판 실습 4단계: 전체·단일 조회
게시판 조회는 리스트 전체를 반환하거나, 경로 매개변수 id로 찾아 반환한다. 못 찾으면 메시지 dict를 반환한다.
```python
@router.get("")
def get_posts():
    return posts

@router.get("/{id}")
def get_post(id: int):
    for post in posts:
        if post.id == id:
            return post
    return {"message": "데이터를 찾을 수 없습니다."}
```

## 상호작용 게시판 실습 5단계: 요청 본문으로 게시글 수정
게시판의 `PUT /posts-pydantic/{id}`는 경로로 id를, 요청 본문으로 새 제목·내용을 받는다. 두 필드가 모두 필요하므로 생성과 같은 PostCreate를 재사용한다.
```python
@router.put("/{id}")
def update_post(id: int, updated_post: PostCreate):
    for post in posts:
        if post.id == id:
            post.title = updated_post.title
            post.content = updated_post.content
            return post
    return {"message": "수정할 대상이 없습니다."}
```

## 상호작용 게시판 실습 6단계: 게시글 삭제
게시판 삭제는 DELETE 메서드와 경로 매개변수로 대상을 찾아 리스트에서 꺼내 반환한다.
```python
@router.delete("/{id}")
def delete_post(id: int):
    for index, post in enumerate(posts):
        if post.id == id:
            return posts.pop(index)
    return {"message": "삭제할 대상이 없습니다."}
```

## 상호작용 게시판 실습 7단계: Swagger UI로 생성·수정 확인
`uv run fastapi dev main.py`로 서버를 띄우고 `/docs`의 mysite2 그룹에서 `POST /posts-pydantic` → `Try it out`에 다음 본문을 넣고 `Execute`한다.
```json
{"title": "첫 게시글", "content": "안녕하세요."}
```
응답의 id로 `GET /posts-pydantic/{id}`를 실행해 저장을 확인한다. 같은 id로 `PUT /posts-pydantic/{id}`에 아래 본문을 보내고 다시 조회해 변경을 확인한다.
```json
{"title": "수정한 게시글", "content": "내용을 변경했습니다."}
```

## 상호작용 게시판 Pydantic 검증 결과 확인
`POST /posts-pydantic`에 다음 본문을 보내 Pydantic 검증 결과를 비교한다.
- `{"title": "제목", "content": "내용"}`: 통과, 게시글 생성.
- `{"title": "제목"}`: 필수 필드 content가 없어 실패.
- `{"title": ["제목"], "content": "내용"}`: title이 리스트라 실패.
- `{"title": "제목", "content": null}`: content가 None을 허용하지 않아 실패.

실패 응답의 `detail`에서 문제 필드와 이유를 확인하고, `GET /posts-pydantic`으로 잘못된 요청으로는 게시글이 생기지 않았음을 확인한다.

## 상호작용이 가능한 게시판 복습 Q&A
- Q. FastAPI 게시판에서 요청 본문을 Pydantic 모델로 받으려면 어떻게 선언하나?
  A. 함수 매개변수 타입을 모델로 지정한다. 예: `def create_post(post_data: PostCreate)`
- Q. Pydantic PostCreate에서 `title: str`만 선언하면 빈 문자열은 막히나?
  A. 막히지 않는다. 타입과 필수 여부만 검사한다.
- Q. 게시판에서 PostCreate와 Post를 나누는 이유는?
  A. 클라이언트가 보내는 데이터(title, content)와 서버가 관리하는 데이터(id 포함)의 구성이 다르기 때문이다.
- Q. Pydantic 검증에 실패하면 엔드포인트 함수는 실행되나?
  A. 실행되지 않고 검증 오류 응답이 반환된다.
