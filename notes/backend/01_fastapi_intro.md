---
part: backend
lesson: FastAPI Intro
order: 1
source_type: web
tags: [fastapi, uv, endpoint, json, swagger, redoc]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1443/
note: 개인 학습용 요약. 외부 공유 금지.
---

# FastAPI Intro

## FastAPI Intro 요약
FastAPI로 프로젝트를 만들고 GET 엔드포인트를 작성한 뒤, JSON 응답과 자동 문서(Swagger UI, ReDoc)를 확인하는 첫 실습이다.

## FastAPI란
FastAPI는 파이썬 웹 프레임워크로, 파이썬 프레임워크 중에서도 빠른 편이다. 웹 서비스에 필요한 기능이 미리 구현되어 있어 비즈니스 로직에 집중할 수 있다. 비동기 처리와 스트리밍 응답을 지원하므로 LLM이나 AI 에이전트 기능을 HTTP API로 제공할 때 쓰기 좋다.

## 클라이언트와 서버의 요청·응답
클라이언트(브라우저, 앱)가 서버에 HTTP 요청을 보내면, 서버(FastAPI 애플리케이션)가 요청을 처리하고 JSON 등의 형태로 응답을 돌려준다. FastAPI는 서버 쪽 애플리케이션을 만드는 데 쓰인다.

## FastAPI 실습 1단계: uv로 프로젝트 생성
uv로 새 프로젝트 폴더를 만들고 그 안으로 이동한다.
```bash
uv init fastapi_basic
cd fastapi_basic
```

## FastAPI 실습 2단계: FastAPI 설치
`fastapi[standard]`로 설치하면 FastAPI와 함께 개발 서버 실행 도구도 설치된다. 이때 프로젝트 가상환경인 `.venv`가 자동으로 생성된다.
```bash
uv add "fastapi[standard]"
```

## FastAPI 실습 3단계: main.py에 첫 API 작성
프로젝트 폴더의 `main.py`에 아래 코드를 작성한다.
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
```
- `app = FastAPI()`: 요청을 처리할 애플리케이션 객체를 만든다.
- `@app.get("/")`: 루트 경로 `/`로 들어오는 GET 요청을 아래 함수와 연결하는 데코레이터이다.
- `read_root()`: 요청이 들어오면 실행되는 함수이다. 함수 이름은 자유롭게 정할 수 있고, 어떤 경로를 처리할지는 데코레이터가 결정한다. (강의 본문 설명에는 `get_root()`로 적혀 있지만 코드의 함수명은 `read_root()`이다.)
- `return {"Hello": "World"}`: dict를 반환하면 FastAPI가 JSON으로 변환해서 응답한다.

## FastAPI 실습 4단계: 개발 서버 실행
`main.py`가 있는 폴더에서 FastAPI 개발 서버를 실행한다.
```bash
uv run fastapi dev main.py
```
- 코드를 저장하면 서버가 자동으로 다시 로드된다.
- 터미널에서 `Ctrl + C`를 누르면 서버가 종료된다.
- `fastapi dev`는 개발용 명령이다. 배포할 때는 다른 실행 방식을 쓴다.

## FastAPI 실습 5단계: 브라우저에서 응답 확인
개발 서버가 실행 중일 때 브라우저에서 `http://127.0.0.1:8000/`에 접속하면 다음 JSON 응답이 보인다.
```json
{"Hello": "World"}
```

## FastAPI 엔드포인트란
엔드포인트는 클라이언트가 특정 기능을 요청하는 API의 접점이며, HTTP 메서드와 URL 경로로 구분한다. 예를 들어 `@app.get("/")`로 만든 엔드포인트는 `GET /`이다. 하나의 FastAPI 애플리케이션은 엔드포인트를 여러 개 가질 수 있다.

## FastAPI 반환 타입별 JSON 응답 형태
FastAPI 엔드포인트 함수가 반환한 값은 JSON으로 변환된다.
- dict를 반환하면 JSON 객체가 된다. `{"Hello": "World"}`
- str을 반환하면 JSON 문자열이 된다. `"Hello World!"`
- list를 반환하면 JSON 배열이 된다. `["hello", "World", "!"]`

```python
@app.get("/hello")
def hello():
    return "Hello World!"           # GET /hello → "Hello World!"

@app.get("/hi")
def hi():
    return ["hello", "World", "!"]  # GET /hi → ["hello", "World", "!"]
```

## FastAPI 자동 문서화: Swagger UI와 ReDoc
FastAPI는 등록된 엔드포인트를 바탕으로 API 명세서를 자동으로 만든다. 개발 서버가 실행 중일 때 다음 주소에서 볼 수 있다.
- `http://127.0.0.1:8000/docs`: **Swagger UI**. API 명세를 확인하고 요청을 직접 보내 볼 수 있다. 엔드포인트를 펼친 뒤 `Try it out` → `Execute`를 누르면 상태 코드(200)와 응답 본문이 나온다.
- `http://127.0.0.1:8000/redoc`: **ReDoc**. API 명세를 읽기 좋게 보여주며, 요청을 보내는 기능은 없다.

## FastAPI Intro 복습 Q&A
- Q. FastAPI 엔드포인트는 무엇으로 구분하나?
  A. HTTP 메서드와 URL 경로로 구분한다. (예: `GET /hello`)
- Q. FastAPI 함수가 list를 반환하면 클라이언트는 무엇을 받나?
  A. JSON 배열을 받는다.
- Q. FastAPI의 `/docs`와 `/redoc`은 어떻게 다른가?
  A. `/docs`(Swagger UI)에서는 요청을 직접 실행할 수 있고, `/redoc`(ReDoc)은 명세를 읽는 용도이다.
- Q. FastAPI 개발 서버를 실행하는 명령어는?
  A. `uv run fastapi dev main.py`
