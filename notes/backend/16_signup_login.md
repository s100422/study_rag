---
part: backend
lesson: 회원가입, 로그인
order: 16
source_type: web
tags: [fastapi, jwt, pyjwt, pwdlib, argon2, httpbearer, signup, login]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1455/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 회원가입, 로그인

## 회원가입, 로그인 요약
FastAPI에서 이메일·비밀번호로 회원가입(Argon2id 해싱)하고, 로그인하면 PyJWT로 access token을 발급하며, `Authorization: Bearer` 헤더의 토큰을 `HTTPBearer` 의존성으로 검증해 `/me`에서 내 정보를 돌려주는 실습이다.

## FastAPI 회원가입·로그인 요청 흐름과 API 목록
```text
회원가입: 비밀번호 해싱 → 이메일 중복 확인 → 사용자 저장
로그인: 이메일로 사용자 조회 → 비밀번호 검증 → JWT 발급
내 정보 조회: Bearer 토큰 추출 → JWT 검증 → 사용자 조회 → 응답
```
- `POST /auth/signup`: 회원가입 (201)
- `POST /auth/login`: 로그인과 access token 발급 (200)
- `GET /me`: 인증된 사용자 정보 조회 (200)

인증 관련 파일은 두 개다.
- `security.py`: JWT 설정, 비밀번호 해싱·검증, JWT 발급·검증
- `dependencies.py`: 요청에서 토큰을 꺼내 인증된 사용자를 넘겨주는 의존성

## 회원가입·로그인 실습 1단계: 라이브러리 설치
비밀번호 해싱용 pwdlib(Argon2)와 JWT용 PyJWT를 설치한다.
```bash
uv add "pwdlib[argon2]" pyjwt
```
- `pwdlib[argon2]`: Argon2id 비밀번호 해싱과 검증
- `pyjwt`: JWT 생성과 검증 (import 이름은 `jwt`)

## 회원가입·로그인 실습 2단계: JWT 환경 변수 설정
JWT 서명용 비밀 키를 터미널에서 만들고 `.env`에 넣는다.
```bash
openssl rand -hex 32
```
```bash
# .env
JWT_SECRET_KEY=생성한_64자리_비밀_키
JWT_EXPIRE_MINUTES=3000
```
- `JWT_SECRET_KEY`: 서명 생성·검증에 쓰는 서버 비밀 키. 저장소에 올리지 않는다.
- `JWT_EXPIRE_MINUTES`: 토큰 유효 시간(분). 실습에선 로그인 반복을 피하려고 3000분으로 길게 둔다.

`security.py` 위쪽에서 `.env`를 읽는다.
```python
# security.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
```
- 모듈을 처음 import할 때 한 번만 실행되므로 `.env`를 고치면 서버를 재시작해야 한다.

## 회원가입 실습 3단계: User 모델 (user_auth 테이블)
`user_auth` 테이블에는 이메일과 비밀번호 해시를 저장하며, 이메일은 UNIQUE이다.
```python
# mysite_auth/models/user.py
from datetime import datetime
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class User(Base):
    __tablename__ = "user_auth"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```
- `DateTime(timezone=True)`: PostgreSQL에서 시간대 있는 시각 타입을 쓴다.
- `server_default=func.now()`: 행 생성 시 DB가 현재 시각을 넣는다.

## 회원가입 실습 4단계: UserCreate와 UserResponse 스키마
```python
# mysite_auth/schemas/user.py
class UserCreate(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=15, max_length=128, repr=False)

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```
- 회원가입 비밀번호는 15~128자이다.
- `repr=False`: 모델을 출력(로그 등)할 때 비밀번호 필드를 빼서 노출을 막는다.
- `UserResponse`에는 비밀번호 해시가 없으므로 응답에 해시가 나가지 않는다.

## 회원가입 실습 5단계: Argon2id 비밀번호 해싱
Argon2id는 비밀번호를 추측하는 데 드는 연산·메모리 비용을 키운 해시 알고리즘이다. `PasswordHash.recommended()`가 Argon2id 해시 객체를 만든다. 무작위 salt를 쓰므로 같은 비밀번호라도 해시 결과가 매번 다르며, 해시는 원문으로 되돌리지 않는다.
```python
# security.py
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password)
```

## 회원가입 실습 6단계: AuthService.signup 처리
이메일을 소문자로 통일하고(대소문자 구분 안 함), 비밀번호를 해싱한 뒤 이메일 중복이면 409를 반환한다.
```python
# mysite_auth/services/auth_service.py
def signup(self, db: Session, data: UserCreate) -> User:
    email = str(data.email).lower()
    hashed_password = hash_password(data.password)

    with db.begin():
        if user_repository.find_by_email(db, email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 등록된 이메일입니다.",
            )
        user = User(email=email, hashed_password=hashed_password)
        user_repository.save(db, user)

    return user
```
- 해싱은 시간이 걸리므로 트랜잭션을 열기 전에 먼저 한다 (코드 순서상 그렇게 되어 있음).

## 로그인 실습 1단계: UserLogin과 TokenResponse 스키마
```python
# mysite_auth/schemas/user.py
class UserLogin(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128, repr=False)

class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
```
- 로그인 비밀번호는 1~128자만 검사한다 (가입 때의 15자 제한과 다름).
- `Literal["bearer"]`: `token_type` 값을 `"bearer"`로 고정한다.
- Bearer 방식은 토큰을 가진 사람이면 누구나 인증 요청을 보낼 수 있으므로 토큰을 비밀번호처럼 보호해야 한다.

## 로그인 실습 2단계: 비밀번호 검증 verify_password
입력 비밀번호를 다시 해싱해서 문자열 비교하면 salt가 달라 일치하지 않는다. `verify()`는 저장된 해시 안의 salt와 매개변수로 검증해 True/False를 돌려준다.
```python
# security.py
from pwdlib.exceptions import UnknownHashError

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(password, hashed_password)
    except UnknownHashError:
        return False
```
- 저장된 해시 형식을 알 수 없을 때도 False로 처리해 인증 실패로 만든다.

## 로그인 실습 3단계: PyJWT로 access token 발급
`create_access_token()`은 사용자 ID, 발급·만료 시각을 페이로드에 담아 HS256으로 서명한다. 페이로드는 암호화되지 않으므로 비밀번호나 비밀 키를 넣지 않는다.
```python
# security.py
from datetime import datetime, timedelta, timezone
import jwt

ALGORITHM = "HS256"

def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)
```
- `sub`: 사용자 ID를 문자열로 변환한 값
- `iat`: 현재 UTC 시각, `exp`: 발급 시각 + 유효 시간
- PyJWT가 datetime을 숫자 타임스탬프로 바꿔 준다.

## 로그인 실습 4단계: AuthService.login 처리
이메일로 사용자를 찾고 비밀번호를 검증한다. 이메일이 없든 비밀번호가 틀리든 같은 401 메시지를 반환해, 어떤 이메일이 가입돼 있는지 드러나지 않게 한다.
```python
# mysite_auth/services/auth_service.py
def login(self, db: Session, data: UserLogin) -> str:
    email = str(data.email).lower()
    with db.begin():
        user = user_repository.find_by_email(db, email)
        if user is None or not verify_password(data.password, user.hashed_password):
            raise authentication_error("이메일 또는 비밀번호가 올바르지 않습니다.")

        user_id = user.id

    return create_access_token(user_id)
```

## 회원가입·로그인 실습: auth_router 작성
```python
# mysite_auth/routers/auth_router.py
router = APIRouter(prefix="/auth", tags=["mysite_auth"])

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(data: UserCreate, db: Annotated[Session, Depends(get_db)]):
    return auth_service.signup(db, data)

@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Annotated[Session, Depends(get_db)], response: Response):
    access_token = auth_service.login(db, data)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(access_token=access_token)
```
- `db: Annotated[Session, Depends(get_db)]`: Session은 타입, `Depends(get_db)`는 세션을 공급하는 의존성이다.
- `response: Response`: 응답 헤더를 설정하는 매개변수이다.
- `Cache-Control: no-store`: 토큰이 담긴 응답을 캐시에 저장하지 말라고 지시한다.

## 토큰 인증 1단계: 401 인증 실패 응답 함수
인증 실패 시 401과 `WWW-Authenticate: Bearer` 헤더를 반환한다. 이 헤더는 클라이언트에 필요한 인증 방식을 알려 준다.
```python
# security.py
from fastapi import HTTPException, status

def authentication_error(
    detail: str = "유효하지 않거나 만료된 토큰입니다.",
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
```

## 토큰 인증 2단계: PyJWT로 JWT 검증
`decode_access_token()`은 서명, 만료 시각, 필수 claim을 검증한 뒤 사용자 ID를 반환한다.
```python
# security.py
def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise authentication_error() from None
```
- `algorithms=[ALGORITHM]`: 서버가 허용하는 알고리즘을 HS256으로 고정한다.
- `options={"require": [...]}`: sub, iat, exp가 없는 토큰을 거부한다.
- 검증·정수 변환에 실패하면 모두 401이다.

## 토큰 인증 3단계: 토큰의 사용자 조회
`AuthService.get_current_user()`는 검증된 사용자 ID로 DB를 조회한다. 토큰이 유효해도 사용자가 삭제됐으면 401이다.
```python
# mysite_auth/services/auth_service.py
def get_current_user(self, db: Session, token: str) -> User:
    user_id = decode_access_token(token)
    user = user_repository.find_by_id(db, user_id)
    if user is None:
        raise authentication_error()
    return user
```

## 토큰 인증 4단계: HTTPBearer 인증 의존성
클라이언트는 인증이 필요한 요청마다 `Authorization: Bearer <access_token>` 헤더를 보낸다. `HTTPBearer`가 헤더에서 토큰을 꺼내고 Swagger UI에 인증 입력창도 만든다.
```python
# dependencies.py
bearer_scheme = HTTPBearer(bearerFormat="JWT", auto_error=False)

def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserResponse:
    if credentials is None:
        raise authentication_error("로그인이 필요합니다.")
    with SessionLocal() as db:
        user = auth_service.get_current_user(db, credentials.credentials)
        return UserResponse.model_validate(user)
```
- `credentials.scheme`은 `"Bearer"`, `credentials.credentials`는 접두사를 뺀 JWT 문자열이다.
- `auto_error=False`: 헤더가 없거나 형식이 틀리면 None이 되어 직접 401을 만든다.
- 별도 `SessionLocal()`을 쓰고, 세션이 열린 동안 ORM 객체를 `UserResponse`로 변환한 뒤 닫는다. 같은 세션에서 인증 조회가 먼저 트랜잭션을 시작하면 Service의 `with db.begin():`과 충돌할 수 있어서 세션을 분리한다.

## 토큰 인증 5단계: GET /me 내 정보 조회
`current_user: Annotated[UserResponse, Depends(get_current_user)]`를 선언하면 라우터 함수 실행 전에 인증을 거치고, 인증된 사용자 정보를 받는다.
```python
# mysite_auth/routers/user_router.py
from typing import Annotated
from fastapi import APIRouter, Depends
from dependencies import get_current_user
from mysite_auth.schemas.user import UserResponse

router = APIRouter(tags=["mysite_auth"])

@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[UserResponse, Depends(get_current_user)]):
    return current_user
```
- 토큰은 `Depends(get_current_user)`를 쓰는 API에만 필요하다.

## 회원가입·로그인 실행 확인: 서버 실행과 요청
`fastapi_ai/fastapi_basic`에서 서버를 실행하고 `http://127.0.0.1:8000/docs`의 `mysite_auth` 그룹을 연다.
```bash
uv run fastapi dev main.py
```
`POST /auth/signup`에 다음 JSON을 보낸다 (이메일은 예시 값으로 바꿔 적음).
```json
{
  "email": "user@example.com",
  "password": "my-long-password-123"
}
```
성공하면 201과 id, email, created_at이 온다. 같은 JSON으로 `POST /auth/login`을 실행하면 `{"access_token": "발급된_JWT", "token_type": "bearer"}`를 받는다.

## 회원가입·로그인 실행 확인: Swagger UI에서 /me 호출
- 로그인 응답의 `access_token`을 복사한다.
- 상단 Authorize의 Value에 토큰만 넣는다. `Bearer ` 접두사는 Swagger가 붙인다.
- Authorize를 누르고 창을 닫은 뒤 `GET /me`를 실행하면 내 정보가 나온다.
- Authorize → Logout으로 토큰을 지우고 다시 `/me`를 실행하면 401이다.

## 회원가입·로그인 실패 응답 상태 코드
- 같은 이메일로 다시 회원가입: 409
- 이메일 형식이나 비밀번호 길이 조건 위반: 422
- 가입되지 않은 이메일 또는 틀린 비밀번호로 로그인: 401
- 토큰 없이 `/me` 요청: 401
- 변조·만료·필수 claim 누락 토큰으로 `/me`: 401
- 삭제된 사용자의 토큰으로 `/me`: 401

## 회원가입, 로그인 복습 Q&A
- Q. 회원가입 시 비밀번호를 해싱해서 저장하고, 로그인 때 다시 해싱해 문자열 비교하면 안 되는 이유는?
  A. Argon2id는 무작위 salt를 써서 같은 비밀번호도 해시가 달라지므로, `password_hash.verify()`로 검증해야 한다.
- Q. 로그인 실패 시 이메일 없음과 비밀번호 틀림을 같은 401로 처리하는 이유는?
  A. 어떤 이메일이 가입돼 있는지 외부에 드러나지 않게 하기 위해서다.
- Q. `jwt.decode()`에서 `algorithms=[ALGORITHM]`과 `options={"require": [...]}`의 역할은?
  A. 허용 알고리즘을 고정하고, sub·iat·exp claim이 없는 토큰을 거부한다.
- Q. `HTTPBearer(auto_error=False)`로 두면 토큰이 없을 때 어떻게 되나?
  A. credentials가 None이 되고, 의존성 함수에서 직접 "로그인이 필요합니다." 401을 반환한다.
- Q. FastAPI에서 `/me`처럼 로그인한 사용자만 쓰는 API를 만드는 방법은?
  A. 라우터 매개변수에 `current_user: Annotated[UserResponse, Depends(get_current_user)]`를 선언한다.
