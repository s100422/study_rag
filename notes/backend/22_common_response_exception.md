---
part: backend
lesson: 공통 응답과 예외 처리
order: 22
source_type: web
tags: [fastapi, success-response, error-response, exception-handler, apiexception, validation-error, generic]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1466/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 공통 응답과 예외 처리

## 공통 응답과 예외 처리 요약
fastapi_agent 프로젝트의 회원·게시글·댓글 API에 성공 응답(`data`, `message`)과 실패 응답(`error`)의 공통 형식을 적용하고, 커스텀 예외와 전역 예외 핸들러로 오류 응답을 한곳에서 만든다.

## FastAPI 공통 응답을 쓰는 이유
FastAPI 공통 응답은 성공 데이터는 `data`, 안내 문구는 `message`, 오류 정보는 `error`라는 정해진 위치에 담는 규칙이다.
- 클라이언트는 어느 API든 같은 위치에서 값을 꺼내므로 데이터 추출·오류 처리 코드를 재사용할 수 있다.
- Router마다 응답 필드를 직접 짜지 않아도 된다.
- 공통 응답 모델을 `response_model`로 쓰면 FastAPI가 응답 구조를 검증하고 Swagger 문서에도 표시한다.

## FastAPI 공통 응답 규칙: 상태 코드와 본문 형태
FastAPI 공통 응답에서 성공·실패 여부는 HTTP 상태 코드로 구분하고, 본문 형태는 다음과 같이 맞춘다.
- 조회·수정·로그인 성공: 200, `{"data": ..., "message": ...}`
- 생성 성공: 201, `{"data": ..., "message": ...}`
- 삭제 성공: 200, `{"data": null, "message": "삭제 안내 문구"}`
- 요청 처리 실패: 4xx/5xx, `{"error": ...}`

## FastAPI 공통 응답·예외 처리 구성 파일
FastAPI 공통 응답과 예외 처리는 다음 파일로 역할을 나눈다.
- `core/responses.py`: 성공·오류 응답 모델, API 문서용 오류 예시 함수 `error_responses()`
- `core/exceptions.py`: 공통 부모 `ApiException`과 오류 종류별 예외 클래스
- `core/exception_handlers.py`: 예외를 공통 HTTP 오류 응답으로 바꾸는 핸들러
- `main.py`: 전역 예외 핸들러 등록
- 도메인 `router.py`: 성공 응답 모델 선언과 응답 객체 생성
- 도메인 `service.py`: 업무 조건에 따라 예외 발생

## FastAPI 공통 성공 모델 SuccessResponse[T]
FastAPI 공통 성공 모델 `SuccessResponse`는 제네릭 클래스로, `data`의 타입만 바꿔 같은 구조를 재사용한다.
```python
# core/responses.py
from pydantic import BaseModel

class SuccessResponse[T](BaseModel):
    data: T
    message: str | None = None
```
- `class SuccessResponse[T]`: 파이썬 3.12+ 제네릭 선언 문법. `T`는 타입 매개변수다.
- `SuccessResponse[PostDetailResponse]`처럼 쓰면 Pydantic이 `data`를 해당 모델로 검증한다.
- `message`: 사용자 안내 문구. 생략하면 JSON에서 `null`이다.

사용 예:
- `SuccessResponse[UserResponse]`: 회원 한 명
- `SuccessResponse[list[PostListResponse]]`: 게시글 목록
- `SuccessResponse[TokenResponse]`: 토큰과 토큰 타입
- `SuccessResponse[None]`: 삭제 완료 시 `data`가 null

## FastAPI Router에서 SuccessResponse로 성공 응답 만들기
FastAPI Router는 Service 결과를 `SuccessResponse[...]`의 `data`에 담고 `response_model`에 같은 모델을 선언한다.
```python
# domains/posts/router.py (발췌)
router = APIRouter(prefix="/posts", tags=["posts"], responses=error_responses(422))

@router.post(
    "",
    response_model=SuccessResponse[PostDetailResponse],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401),
)
async def create_post(
    data: PostCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(get_current_user)],
):
    post = await post_service.create_post(db, data, current_user)
    return SuccessResponse[PostDetailResponse](data=post, message="게시글이 등록되었습니다.")

@router.get("", response_model=SuccessResponse[list[PostListResponse]])
async def get_posts(db: Annotated[AsyncSession, Depends(get_db)]):
    posts = await post_service.get_posts(db)
    return SuccessResponse[list[PostListResponse]](data=posts)
```
- 빈 목록 응답: `{"data": [], "message": null}`

## FastAPI error_responses()와 인증 오류 흐름
FastAPI 라우터의 `responses=error_responses(401)`은 Swagger 문서에 401 오류 모델과 예시를 보여 주는 설정일 뿐이다. 이 설정이 오류를 발생시키거나 응답을 만들지는 않는다. (`error_responses()`는 `core/responses.py`에 직접 정의한 함수인데, 강의 본문에 구현 코드는 나오지 않는다.)

실제 401은 다음 흐름으로 만들어진다.
- 게시글 생성 요청에 인증 정보가 없거나, 토큰이 유효하지 않거나 만료되면 `get_current_user()`가 `UnauthorizedException`을 발생시킨다.
- 전역 예외 핸들러가 이 예외를 401 공통 오류 응답으로 바꾼다.

## FastAPI 예외 처리를 공통화하는 이유
FastAPI 예외 처리를 공통화하면 업무 오류·입력 검증 오류·서버 오류가 모두 같은 `error` 구조로 응답된다.
- 클라이언트는 `error.code`로 오류 종류를 구분하고 `error.message`를 화면에 표시하는 코드를 재사용한다.
- 서버에서는 Service가 업무 조건에 맞는 예외만 발생시키고, HTTP 오류 응답 생성과 로그 기록은 전역 예외 핸들러가 맡는다.
- 오류 처리 코드가 한곳에 모여 중복이 줄고 수정이 쉬워진다.

## FastAPI 공통 오류 모델: ValidationIssue, ErrorDetail, ErrorResponse
FastAPI 공통 오류 응답 본문은 세 개의 Pydantic 모델로 정의한다.
```python
# core/responses.py (발췌)
from pydantic import BaseModel, Field

class ValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[ValidationIssue] = Field(default_factory=list)

class ErrorResponse(BaseModel):
    error: ErrorDetail
```
- `ValidationIssue`: 입력 검증 오류 한 건(위치·설명·종류). `error.details`의 각 항목.
- `ErrorDetail.code`: 프로그램이 오류 종류를 구분하는 값. `message`: 화면 표시용 설명.
- `details`: 입력 검증 오류 목록. 일반 업무 오류에서는 빈 배열.
- `ErrorResponse`: `{"error": ...}` 전체 본문.

```json
{"error": {"code": "POST_NOT_FOUND", "message": "게시글을 찾을 수 없습니다.", "details": []}}
```

## FastAPI 커스텀 예외: ApiException과 자식 클래스
FastAPI 커스텀 예외는 공통 부모 `ApiException`을 상속해 오류 종류별로 만든다. `status_code`·`headers`는 HTTP에, `code`·`message`는 본문에 쓴다.
```python
# core/exceptions.py (발췌)
class ApiException(Exception):
    def __init__(self, status_code: int, code: str, message: str,
                 headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status_code, self.code = status_code, code
        self.message, self.headers = message, headers

class NotFoundException(ApiException):
    def __init__(self, message: str = "요청한 리소스를 찾을 수 없습니다.", *, code: str = "NOT_FOUND"):
        super().__init__(status_code=404, code=code, message=message)

class UnauthorizedException(ApiException):
    def __init__(self, message: str = "인증이 필요합니다.", *, code: str = "UNAUTHORIZED"):
        super().__init__(status_code=401, code=code, message=message,
                         headers={"WWW-Authenticate": "Bearer"})
```
- 같은 패턴으로 `ForbiddenException`(403, 권한 없음), `ConflictException`(409, 이메일 중복 등)도 있다.

## FastAPI Service에서 상황에 맞는 예외 발생
FastAPI Service는 업무 조건을 검사해 알맞은 커스텀 예외를 `raise`한다. 기본 메시지로 충분하면 인자 없이, 구체적 안내가 필요하면 `code`와 `message`를 지정한다.
```python
from fastapi_agent.core.exceptions import NotFoundException

if post is None:
    raise NotFoundException(
        code="POST_NOT_FOUND",
        message="게시글을 찾을 수 없습니다.",
    )
```
- 같은 `NotFoundException`이라도 `POST_NOT_FOUND`, `COMMENT_NOT_FOUND`처럼 code를 달리해 클라이언트가 세부 상황을 구분하게 한다.
- 쓰기 작업의 `async with db.begin()` 안에서 예외가 나면 트랜잭션이 롤백되고, 전역 핸들러가 오류 응답을 만든다.

## FastAPI 전역 예외 핸들러 api_exception_handler
FastAPI 전역 예외 핸들러는 `ApiException`을 받아 공통 오류 모델로 본문을 만들고 JSONResponse로 반환한다.
```python
# core/exception_handlers.py (발췌)
from fastapi import Request
from fastapi.responses import JSONResponse

from fastapi_agent.core.exceptions import ApiException
from fastapi_agent.core.responses import ErrorDetail, ErrorResponse

async def api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message))
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(mode="json"),
        headers=exc.headers,
    )
```
- JSONResponse를 직접 반환하므로 `model_dump(mode="json")`으로 JSON에 쓸 수 있는 데이터로 바꾼다.
- `headers=exc.headers`: 401일 때 `WWW-Authenticate: Bearer` 헤더가 전달된다.

## FastAPI 예외 핸들러 등록 register_exception_handlers
FastAPI 앱에 예외 종류별 핸들러를 `add_exception_handler`로 등록한다.
```python
# core/exception_handlers.py (발췌)
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiException, api_exception_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
```
```python
# main.py (발췌)
app = FastAPI(title="FastAPI Agent", lifespan=lifespan, responses=error_responses(500))
register_exception_handlers(app)
```
- `ApiException`: 부모에 등록하면 상속한 네 예외도 모두 처리된다.
- Starlette `HTTPException`: 없는 경로 404, 허용 안 된 메서드 405 등. FastAPI의 HTTPException도 이를 상속해 같은 핸들러로 처리된다.
- `RequestValidationError`: 입력 검증 오류를 422 공통 응답으로.
- `Exception`: 예상 못한 오류를 로그에 남기고 500 공통 응답.

## FastAPI 입력 검증 오류 핸들러 validation_error_handler
FastAPI에서 필수 값 누락, 잘못된 타입, 길이 조건 위반은 `RequestValidationError`로 처리한다. `exc.errors()`의 각 항목을 `ValidationIssue`로 바꿔 `details`에 담는다.
```python
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        ValidationIssue(loc=list(error["loc"]), msg=error["msg"], type=error["type"])
        for error in exc.errors()
    ]
    body = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR", message="입력값을 확인해 주세요.", details=details
        )
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))
```
- `loc`: 오류 위치(`body`, `path` 등 + 필드명), `msg`: 검증 설명, `type`: 오류 종류.
- 세 필드만 골라 담아 비밀번호 같은 원본 입력값이 응답에 섞이지 않게 한다.

title 누락 시 응답 예:
```json
{"error": {"code": "VALIDATION_ERROR", "message": "입력값을 확인해 주세요.",
  "details": [{"loc": ["body", "title"], "msg": "Field required", "type": "missing"}]}}
```

## FastAPI 인증·권한·서버 오류 코드
FastAPI 프로젝트의 인증 오류는 `UnauthorizedException`(401), 권한 오류는 `ForbiddenException`(403)으로 발생시킨다.
- 401 `AUTHENTICATION_REQUIRED`: 인증 정보 없음
- 401 `INVALID_CREDENTIALS`: 로그인 정보 불일치
- 401 `INVALID_TOKEN`: 토큰 검증 실패 또는 사용자 없음
- 403 `POST_FORBIDDEN`: 다른 사람의 게시글 수정·삭제
- 403 `COMMENT_FORBIDDEN`: 다른 사람의 댓글 수정·삭제

예상하지 못한 서버 오류는 `INTERNAL_SERVER_ERROR` 코드와 공통 메시지로 응답하고, 상세 예외와 추적 정보는 서버 로그에만 남긴다. 응답 데이터가 `response_model`과 맞지 않는 경우도 서버 오류로 처리된다.

## FastAPI 공통 응답 동작 확인 (Swagger /docs)
FastAPI 공통 응답과 예외 처리는 `http://127.0.0.1:8000/docs`에서 다음을 확인한다.
- 회원가입 응답의 회원 정보가 `data`에 담긴다.
- 회원가입·게시글 생성·수정 응답의 `message`에 안내 문구가 있다.
- 로그인 응답의 `data.access_token`을 Authorize에 입력한다.
- 게시글 목록은 `data` 배열, 상세 조회는 `data` 객체다.
- 없는 게시글 조회는 404와 `POST_NOT_FOUND`.
- 필수 입력값이 없으면 422와 오류 위치 목록.
- 삭제 성공은 200, `data`는 null, `message`는 삭제 안내 문구.

## 공통 응답과 예외 처리 복습 Q&A
- Q. FastAPI 공통 응답에서 성공과 실패는 무엇으로 구분하나?
  A. HTTP 상태 코드로 구분한다. 본문은 성공이면 `data`/`message`, 실패면 `error`.
- Q. `SuccessResponse[T]`에서 `T`의 역할은?
  A. `data` 필드의 타입을 지정하는 타입 매개변수다. 예: `SuccessResponse[list[PostListResponse]]`.
- Q. 라우터의 `responses=error_responses(401)`이 401 응답을 만들어 주나?
  A. 아니다. Swagger 문서용 표시일 뿐이고, 실제 401은 `UnauthorizedException`을 전역 핸들러가 변환해서 만든다.
- Q. `ApiException`에만 핸들러를 등록해도 `NotFoundException`이 처리되는 이유는?
  A. `NotFoundException` 등 커스텀 예외가 모두 `ApiException`을 상속하기 때문이다.
- Q. 입력 검증 오류 응답에 `loc`, `msg`, `type`만 담는 이유는?
  A. 비밀번호 같은 원본 입력값이 응답에 노출되지 않게 하기 위해서다.
