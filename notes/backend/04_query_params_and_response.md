---
part: backend
lesson: 쿼리 파라미터와 응답
order: 4
source_type: web
tags: [fastapi, query-parameter, status-code, httpexception, response-model, dto]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1439/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 쿼리 파라미터와 응답

## 쿼리 파라미터와 응답 요약
게시판에 쿼리 파라미터 검색을 추가하고, HTTP 상태 코드·HTTPException·응답 모델(response_model)로 처리 결과를 정확히 전달하는 실습이다. 코드는 `mysite3`, 경로는 `/posts-response`를 쓴다.

## 쿼리 파라미터 실습 준비: mysite3 라우터 등록
`mysite3/post.py`는 게시글 객체와 요청·응답 모델을, `mysite3/post_api.py`는 검색·상태 코드·예외·응답 모델이 적용된 CRUD를 담는다.
```python
# mysite3/post_api.py
router = APIRouter(prefix="/posts-response", tags=["mysite3"])
```
```python
# main.py
from mysite3.post_api import router as response_router
app.include_router(response_router)
```
```bash
uv run fastapi dev main.py
```
Swagger UI(`/docs`)의 mysite3 그룹에서 요청을 실행한다.

## FastAPI 경로 매개변수와 쿼리 파라미터란
경로 매개변수는 URL 경로의 일부로 전달하는 값이다. `/posts-response/{id}`의 id가 대상 게시글을 식별하며 `id: int`로 선언하면 정수 변환·검증된다.

쿼리 파라미터는 URL의 `?` 뒤에 `key=value`로 붙이는 값으로, 검색·필터·정렬 조건에 쓴다. `/posts-response/search?keyword=FastAPI`에서 `keyword`가 이름, `FastAPI`가 값이다.

## FastAPI의 경로·쿼리 파라미터 자동 구분 규칙
FastAPI는 경로 선언과 함수 매개변수의 이름·타입을 보고 값을 어디서 받을지 정한다.
- 경로의 `{변수명}`과 이름이 같은 매개변수는 경로에서 받는다. (`/{id}` ↔ `id: int`)
- 경로에 없는 `int`, `str`, `bool` 같은 단순 타입 매개변수는 쿼리 파라미터로 받는다. (`/search` ↔ `keyword`)
- Pydantic 모델 매개변수(예: `post_data: PostCreate`)는 따로 지정하지 않아도 요청 본문으로 받는다.
- 매개변수 선언 순서와는 무관하며, 타입 힌트는 값 변환·검증에 쓰인다.

## 쿼리 파라미터 실습 1단계: 게시글 검색 엔드포인트
게시판 검색은 `keyword` 쿼리 파라미터로 제목에 키워드가 포함된 게시글만 반환한다.
```python
@router.get("/search", response_model=list[PostListResponse])
def search_posts(keyword: str | None = None):
    if keyword:
        return [post for post in posts if keyword in post.title]
    return posts
```
- `str | None = None`: 문자열 또는 None 허용, 생략 시 기본값 None.
- keyword를 생략하거나 빈 문자열이면 전체 게시글을 반환한다.
- FastAPI는 등록 순서대로 경로를 확인하므로 `/search`를 `/{id}`보다 먼저 정의해야 한다. 아니면 "search"가 id로 해석된다.

## 쿼리 파라미터를 Query()로 명시하기
FastAPI의 `Query()`로 쿼리 파라미터임을 명시할 수도 있다. 클라이언트는 똑같이 `?keyword=FastAPI`로 보낸다.
```python
from fastapi import Query

@router.get("/search", response_model=list[PostListResponse])
def search_posts(keyword: str | None = Query(default=None)):
    if keyword:
        return [post for post in posts if keyword in post.title]
    return posts
```
- `Query(default=None)`: 생략 가능함을 뜻하며, 검증 조건이나 설명도 추가할 수 있다.
- 같은 방식으로 경로 매개변수는 `Path()`, 요청 본문은 `Body()`로 명시한다.

## FastAPI 데이터 전달 방식 비교: Path, Query, Body
- Path: `/posts-response/1` → `id: int` → 특정 게시글 식별.
- Query: `/posts-response/search?keyword=FastAPI` → `keyword: str | None = None` → 검색 조건 전달.
- Body: `{"title": "제목", "content": "내용"}` → `post_data: PostCreate` → 생성·수정할 데이터 전달.

## HTTP 상태 코드란
HTTP 상태 코드는 요청 처리 결과를 나타내는 숫자로, 응답 본문과 함께 전달되며 Swagger UI 응답 영역에서 볼 수 있다. 게시판에서의 쓰임은 다음과 같다.
- 200: 성공. 조회·수정 성공. 지정하지 않으면 기본값이다.
- 201: 자원 생성 성공. 게시글 생성.
- 204: 성공했지만 응답 본문 없음. 게시글 삭제.
- 404: 자원을 찾을 수 없음. 없는 게시글 요청.
- 422: 요청 데이터 검증 실패. 필수 필드 누락, 잘못된 타입. PostCreate 규칙 위반 시 FastAPI가 자동 반환한다.

## FastAPI HTTPException으로 404 응답 보내기
`{"message": "..."}` dict를 반환하면 상태 코드는 여전히 200이다. 게시글이 없음을 404로 알리려면 `HTTPException`을 발생시킨다.
```python
from fastapi import APIRouter, HTTPException, status

raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
```
- `raise` 시 요청 처리가 즉시 중단되고, FastAPI가 404와 `{"detail": "게시글을 찾을 수 없습니다."}`를 응답한다.
- 별도의 try-except는 필요 없다.
- `status`: `status.HTTP_201_CREATED` 같은 상태 코드 상수를 제공한다.
- `get_post`, `update_post`, `delete_post`는 게시글을 못 찾으면 이 예외를 발생시킨다.

## FastAPI 생성·삭제 엔드포인트의 상태 코드 지정
게시판 `create_post` 데코레이터에 `status_code=status.HTTP_201_CREATED`를 지정해 생성 시 201을 반환한다. `delete_post`는 성공 시 204를 반환하고 본문은 보내지 않는다.
```python
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(id: int):
    for index, post in enumerate(posts):
        if post.id == id:
            posts.pop(index)
            return
    raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
```

## FastAPI 응답 모델(응답 DTO)이란
응답 모델은 서버가 클라이언트에 보낼 데이터의 구조를 정의하는 응답 DTO다. PostCreate가 요청 형식을 정의하듯, 응답 모델은 반환할 필드와 타입을 정의한다. 게시판에서는 목록·검색에는 id·title만, 상세·생성·수정에는 content까지 보낸다.
```python
# mysite3/post.py
class PostListResponse(BaseModel):
    id: int
    title: str

class PostDetailResponse(BaseModel):
    id: int
    title: str
    content: str
```

## FastAPI response_model 지정과 동작
게시판 각 엔드포인트 데코레이터에 `response_model`을 지정한다.
```python
from mysite3.post import PostDetailResponse, PostListResponse

@router.get("", response_model=list[PostListResponse])            # get_posts
@router.get("/search", response_model=list[PostListResponse])     # search_posts
@router.get("/{id}", response_model=PostDetailResponse)           # get_post
@router.post("", response_model=PostDetailResponse, status_code=status.HTTP_201_CREATED)  # create_post
@router.put("/{id}", response_model=PostDetailResponse)           # update_post
```
- FastAPI는 반환값을 응답 모델로 검증하고 모델에 정의된 필드만 응답에 넣는다. Post에 content가 있어도 목록 응답에서는 빠진다.
- 응답 모델은 정상 응답 형식이다. 메시지 dict를 정상 응답으로 반환하면 필수 필드가 없어 응답 검증 오류가 난다. 오류는 HTTPException으로 보낸다.

## 쿼리 파라미터와 응답 실행 확인
게시판 서버 재시작 시 메모리 게시글이 초기화되므로, 먼저 게시글을 생성하고 받은 id로 확인한다.
- `POST /posts-response` → 201, id·title·content.
- `GET /posts-response` → 200, 각 게시글의 id·title만.
- `GET /posts-response/search?keyword=FastAPI` → 200, 제목에 FastAPI가 든 게시글의 id·title.
- `GET /posts-response/{id}` → 200, id·title·content.
- `PUT /posts-response/{id}` → 200, 변경된 id·title·content.
- `DELETE /posts-response/{id}` → 204, 본문 없음.
- 삭제한 id로 조회·수정·삭제 → 404, detail에 "게시글을 찾을 수 없습니다."
- content 없이 생성 → 422, detail에 필수 필드 누락 오류.

## 쿼리 파라미터와 응답 복습 Q&A
- Q. FastAPI에서 경로에 없는 `keyword: str` 매개변수는 어디서 값을 받나?
  A. 쿼리 파라미터(`?keyword=...`)에서 받는다.
- Q. FastAPI 게시판에서 `/search`를 `/{id}`보다 먼저 정의해야 하는 이유는?
  A. 경로를 등록 순서대로 확인하므로, 뒤에 두면 "search"가 `/{id}`에 먼저 매칭되기 때문이다.
- Q. FastAPI에서 게시글이 없을 때 404를 보내려면?
  A. `raise HTTPException(status_code=404, detail="...")`를 사용한다. dict를 반환하면 200이 된다.
- Q. FastAPI `response_model=list[PostListResponse]`를 지정하면 content는 어떻게 되나?
  A. 모델에 없는 필드라 응답에서 제외된다.
- Q. FastAPI 삭제 성공에 204를 쓸 때 응답 본문은?
  A. 보내지 않는다. 함수는 그냥 `return`한다.
