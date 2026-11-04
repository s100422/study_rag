---
part: backend
lesson: 간단한 Validation
order: 5
source_type: web
tags: [fastapi, validation, httpexception, 422, pydantic, empty-string]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1440/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 간단한 Validation

## 간단한 Validation 요약
Pydantic 타입 검증만으로는 막히지 않는 빈 문자열 제목·내용을, 게시판 생성·수정 함수에서 직접 검사해 HTTPException 422로 거부하는 실습이다.

## Validation(유효성 검증)이란
Validation은 입력 데이터가 미리 정한 조건에 맞는지 검사하는 과정이다. 저장·수정 전에 검사해 잘못된 데이터가 저장되지 않게 한다. 게시글 작성 시 확인할 기준은 다음과 같다.
- 필수 여부: 제목과 내용이 요청에 포함되어 있는가?
- 타입: 제목과 내용이 문자열인가?
- 값의 조건: 제목과 내용이 빈 문자열은 아닌가?

## Pydantic 타입 검증으로 막지 못하는 빈 문자열
Pydantic의 `PostCreate(title: str, content: str)`는 필수 여부와 타입만 검증하므로 빈 문자열은 통과한다.
```json
{"title": "", "content": "내용"}
```
이 요청은 title이 있고 문자열이라 기존 검증을 통과한다. 타입이 맞더라도 값이 조건을 만족하는지는 따로 확인해야 한다. 이 실습에서는 제목·내용이 빈 문자열이면 생성·수정을 멈추고 HTTPException으로 422와 메시지를 보낸다. 검증을 통과한 데이터만 저장·수정한다.

## 간단한 Validation 실습 1단계: 게시글 생성 빈 문자열 검증
게시판 `create_post`에서 제목·내용을 먼저 검사하고, 통과한 경우에만 ID를 늘리고 저장한다.
```python
@router.post("", response_model=PostDetailResponse, status_code=status.HTTP_201_CREATED)
def create_post(post_data: PostCreate):
    global post_id
    if post_data.title == "":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="title을 입력하세요")
    if post_data.content == "":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="content를 입력하세요")
    post_id += 1
    new_post = Post(post_id, post_data.title, post_data.content)
    posts.append(new_post)
    return new_post
```
- 예외가 발생하면 아래 저장 코드는 실행되지 않으므로 ID도 증가하지 않는다.

## 간단한 Validation 실습 2단계: 게시글 수정 빈 문자열 검증
게시판 `update_post`도 제목·내용을 먼저 검사한 뒤에만 기존 게시글을 바꾼다. 대상이 없으면 404를 보낸다.
```python
@router.put("/{id}", response_model=PostDetailResponse)
def update_post(id: int, updated_post: PostCreate):
    if updated_post.title == "":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="title을 입력하세요")
    if updated_post.content == "":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="content를 입력하세요")
    for post in posts:
        if post.id == id:
            post.title = updated_post.title
            post.content = updated_post.content
            return post
    raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
```

## 간단한 Validation 실습 대상 파일 (원문 불일치)
간단한 Validation 강의 페이지에는 같은 내용이 두 번 실려 있고, 수정할 파일이 서로 다르게 적혀 있다.
- 첫 번째 버전: `mysite3/post_api.py`(경로 `/posts-response`, mysite3 그룹)의 함수에 검증을 추가한다.
- 두 번째 버전: "앞 실습의 `mysite2/post_api2.py`를 `mysite2/post_api.py`로 이름을 바꾼 코드"에 추가한다고 되어 있다.

(두 번째 버전의 코드도 `PostDetailResponse`, `status`, `HTTPException`을 쓰는데, 이는 mysite3에서 도입된 것이므로 실제로는 mysite3 코드 기준으로 보는 것이 맞아 보인다.)

## 간단한 Validation 응답 확인
간단한 Validation 코드 적용 후 Swagger UI의 mysite3 그룹 `/posts-response`로 요청한다.
- 제목이나 내용이 빈 문자열인 생성·수정 요청 → 422와 "title을 입력하세요" 또는 "content를 입력하세요".
- 정상 입력으로 생성 → 201, id·title·content.
- 정상 입력으로 수정 → 200, id·title·content.

이런 간단한 입력 검증은 Pydantic의 `Field` 설정으로도 처리할 수 있으며, 이후 "데이터 검증 및 필드 제어" 레슨에서 다룬다.

## 간단한 Validation 복습 Q&A
- Q. Pydantic `title: str` 필드에 `""`를 보내면 Validation을 통과하나?
  A. 통과한다. 필수 여부와 타입만 검사하기 때문이다.
- Q. 간단한 Validation 실습에서 빈 제목이면 어떤 응답을 보내나?
  A. `HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="title을 입력하세요")`로 422를 보낸다.
- Q. 게시글 생성 Validation을 `post_id += 1`보다 먼저 하는 이유는?
  A. 검증 실패 시 ID 증가와 저장이 일어나지 않게 하기 위해서다.
- Q. Validation에서 확인하는 세 가지 기준은?
  A. 필수 여부, 타입, 값의 조건(예: 빈 문자열 아님).
