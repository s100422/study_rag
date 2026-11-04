---
part: docker
lesson: 도커에서 FastAPI 실행하기
order: 6
source_type: web
tags: [docker, dockerfile, compose, fastapi, healthcheck, depends_on, bind-mount, dockerignore]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1476/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 도커에서 FastAPI 실행하기

## 도커에서 FastAPI 실행하기 요약
FastAPI 앱을 Dockerfile로 이미지로 만들고, Docker Compose로 PostgreSQL(pgvector) 컨테이너와 함께 실행한다. 이어서 개발용 Compose 파일과 bind mount로 이미지를 다시 빌드하지 않고 코드 수정을 반영하는 방법을 익힌다.

## Dockerfile이란
Dockerfile은 Docker 이미지를 만드는 방법을 적은 텍스트 파일이다. FastAPI 앱을 실행하려면 Python, 라이브러리, 앱 코드가 필요하므로 Dockerfile에 이 환경을 준비하는 과정과 앱 시작 명령을 적는다.
- Dockerfile로 이미지를 만드는 과정을 빌드(build)라고 한다.
- 흐름: Dockerfile → (빌드) → 이미지(Python·라이브러리·앱 코드) → (컨테이너 생성·시작) → FastAPI 실행
- Dockerfile을 저장하는 것만으로는 이미지도 서버도 생기지 않는다. 이 실습에서는 `docker compose up -d --build`로 빌드와 실행을 함께 한다.

## Dockerfile, compose.yaml, .dockerignore의 역할
Docker로 FastAPI를 실행할 때 세 파일이 역할을 나눈다. PostgreSQL은 이미 만들어진 이미지를 쓰지만, FastAPI는 내 코드와 라이브러리를 담아야 해서 Dockerfile로 이미지를 직접 만든다.
- `Dockerfile`: FastAPI 이미지를 만드는 방법
- `compose.yaml`: 이미지로 컨테이너를 실행하고 서로 연결하는 방법
- `.dockerignore`: 이미지 빌드에 보내지 않을 파일 목록

## FastAPI Dockerfile 작성
FastAPI용 Dockerfile은 아래처럼 작성한다. 터미널 명령이 아니라 `Dockerfile` 파일의 내용이다.
```dockerfile
FROM python:3.13-slim

WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .

CMD ["uv", "run", "--no-sync", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
```
- `FROM python:3.13-slim`: 출발점이 되는 베이스 이미지(Python 3.13 포함)
- `WORKDIR /app`: 이미지 안의 작업 폴더. 없으면 만들고, 컨테이너 실행 시 기본 폴더도 된다.
- 첫 `RUN`: 이미지 안에 uv 설치 / 두 번째 `RUN`: 잠금 파일대로 라이브러리 설치
- `COPY pyproject.toml uv.lock ./`: 의존성 파일만 먼저 `/app`에 복사
- `COPY . .`: `.dockerignore`에 적힌 파일을 빼고 소스 전체 복사
- `CMD`: 컨테이너 시작 시 실행할 기본 명령

## Dockerfile 명령 동작 원리: RUN, CMD, 레이어 캐시
FastAPI Dockerfile에서 `RUN`과 `CMD`는 실행 시점이 다르다.
- `RUN`: 이미지를 만드는 동안 실행되고, 결과(uv·라이브러리 설치)가 이미지에 담긴다.
- `CMD`: 빌드 중엔 실행되지 않고 "컨테이너 시작 시 실행할 명령"만 저장된다. 대괄호의 첫 항목은 프로그램, 나머지는 인자다.
- `--no-sync`: 빌드 때 설치한 환경을 그대로 사용한다.
- `fastapi run main.py`: 자동 재시작 없이 앱 실행(`fastapi[standard]`의 CLI).
- `COPY`의 앞부분은 빌드 컨텍스트에서 가져올 파일, 마지막 인자는 이미지 안의 복사 위치다. `COPY . .`를 쓰면 파이썬 파일이 늘어도 이름을 나열할 필요가 없다.
- 의존성 파일과 코드를 나눠 복사하면, 코드만 바뀌었을 때 라이브러리 설치 단계를 캐시에서 재사용한다.

## 컨테이너 FastAPI에서 0.0.0.0으로 바인딩하는 이유
컨테이너 안의 FastAPI는 `0.0.0.0:8000`에서 요청을 받도록 실행한다. `0.0.0.0`은 그 실행 환경의 모든 네트워크 인터페이스에서 요청을 받는다는 뜻이다.
- 컨테이너 안에서 `127.0.0.1`에만 바인딩하면 컨테이너 바깥에서 오는 요청을 받지 못한다.
- 브라우저에 입력하는 주소는 `0.0.0.0`이 아니라 호스트에 공개한 `http://localhost:8000`이다.

## .dockerignore로 빌드에서 제외할 파일
FastAPI 이미지 빌드에서 빼야 할 파일은 `.dockerignore`에 적는다.
```text
.venv
.env
.env.*
__pycache__
*.pyc
.git
compose*.yaml
compose-examples/
```
- `.venv`: 내 컴퓨터의 가상환경은 복사하지 않는다. 컨테이너용 라이브러리는 Dockerfile의 `RUN`으로 설치한다.
- `.env`: API 키가 든 파일은 이미지에 넣지 않고, 실행할 때 전달한다.
- `compose*.yaml`, `compose-examples/`: 컨테이너 안에서 실행할 코드가 아니므로 제외한다.

## Compose 실습 1단계: backend 서비스가 추가된 compose.yaml
기존 FastAPI 서버가 켜져 있으면 먼저 끈다. FastAPI는 시작할 때 DB에 연결해 테이블을 만들므로, DB 준비 확인 설정도 함께 넣어 `compose.yaml`을 교체한다. (비밀번호 `1234`는 강의 실습용 값)
```yaml
name: docker-practice
services:
  db:
    image: pgvector/pgvector:pg17-trixie
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: "1234"
      POSTGRES_DB: docker_prac
    ports:
      - "127.0.0.1:5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d docker_prac"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 10s
  backend:
    build: .
    env_file:
      - ./.env
    environment:
      DATABASE_URL: postgresql://postgres:1234@db:5432/docker_prac
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      db:
        condition: service_healthy
volumes:
  postgres_data:
```
(원문의 서비스 사이 빈 줄만 줄였다.)

## Compose build 설정과 빌드 컨텍스트
Compose의 `build: .`은 `compose.yaml`이 있는 폴더로 이미지를 만들라는 뜻이다. 이미지 빌드에 쓰는 이 폴더를 빌드 컨텍스트라고 한다.
- Docker는 이 폴더의 `Dockerfile`을 읽고, `COPY`에 적힌 파일도 이 폴더에서 찾는다.
- `db` 서비스의 `image`는 이미 준비된 이미지를 지정하고, `backend` 서비스의 `build`는 내 코드로 이미지를 만드는 방법을 지정한다.

## Compose healthcheck: PostgreSQL 준비 상태 확인
Compose의 `healthcheck`는 컨테이너 안에서 검사 명령을 반복 실행해 서비스 상태를 확인한다. PostgreSQL은 컨테이너가 뜬 뒤에도 초기화 시간이 필요해서, 실제 접속 가능 여부를 검사한다.
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres -d docker_prac"]
  interval: 5s
  timeout: 3s
  retries: 10
  start_period: 10s
```
- `test`: 검사 명령. `CMD-SHELL`은 뒤 명령을 컨테이너 셸에서 실행하라는 뜻이다.
- `pg_isready -U postgres -d docker_prac`: 해당 사용자·DB로 접속 준비가 됐는지 확인한다.
- `interval: 5s`: 검사가 끝난 뒤 다음 검사까지 5초
- `timeout: 3s`: 한 번의 검사가 3초 안에 안 끝나면 실패
- `retries: 10`: 연속 10번 실패하면 `unhealthy`. 컨테이너 재시작 횟수가 아니다.
- `start_period: 10s`: 시작 후 10초 동안은 실패를 세지 않는다. 그 사이에도 검사는 하며, 성공하면 바로 `healthy`가 되고 그때부터 실패를 센다.

## Compose depends_on: DB가 healthy가 된 뒤 FastAPI 시작
Compose의 `depends_on`은 서비스가 시작할 때 의존하는 서비스를 지정한다. `backend`에 아래처럼 쓰면 FastAPI 시작 전에 `db` 상태를 확인한다.
```yaml
depends_on:
  db:
    condition: service_healthy
```
- `db`: 기다릴 Compose 서비스 이름
- `condition: service_healthy`: `db`의 healthcheck가 성공해 `healthy`가 될 때까지 기다린다.
- 실행 순서: DB 시작 → DB 준비 검사 통과 → FastAPI 시작
- 시작 후에도 healthcheck는 계속되지만, 실행 중 DB 오류를 복구하거나 FastAPI를 자동 재시작해 주지는 않는다.

## Compose env_file과 environment로 환경변수 전달
Compose의 `env_file`은 환경변수를 읽어 올 파일을 지정한다. `./.env`의 API 키 등이 backend 컨테이너 환경변수로 들어간다. `environment`는 Compose 파일에 직접 환경변수를 적는다.
- 이 실습에서는 `environment`로 `.env`의 로컬용 `DATABASE_URL`을 컨테이너용 주소로 덮어쓴다. 두 곳에 모두 있으면 컨테이너는 `environment` 값을 쓴다.
- 로컬 FastAPI: `.env`의 `localhost:5433`
- 컨테이너 FastAPI: Compose `environment`의 `db:5432`
- 덕분에 로컬용 `.env`를 고치지 않아도 컨테이너는 DB 서비스 주소를 쓴다.
- Compose가 설정 파일의 `${변수}`를 채우려고 읽는 `.env`와, `env_file`로 컨테이너에 넘기는 환경변수는 역할이 다르다.

## Compose ports와 컨테이너 사이 네트워크 연결
backend의 `ports: "127.0.0.1:8000:8000"`은 `호스트 주소:호스트 포트:컨테이너 포트` 순서다. 내 컴퓨터의 `http://localhost:8000` 요청이 backend 컨테이너 8000번으로 전달되고, 앞의 `127.0.0.1`은 내 컴퓨터에서만 접속하도록 제한한다.
- Compose는 프로젝트 기본 네트워크(`docker-practice`)를 만들고 서비스를 연결한다. 같은 네트워크에서는 서비스 이름 `db`로 PostgreSQL에 접속한다.
- 흐름: 브라우저 → `localhost:8000` → backend 컨테이너(:8000) → `db:5432` → db 컨테이너 → 볼륨 `postgres_data`
- backend 컨테이너 안의 `localhost`는 backend 자신이지 DB 컨테이너가 아니다.
- 컨테이너끼리는 PostgreSQL 실제 포트 5432를 쓰고, 호스트에 공개한 5433은 내 컴퓨터에서 DB에 접속할 때 쓴다.

## Compose 실습 2단계: FastAPI 이미지 빌드와 실행
Compose 설정을 검사하고 FastAPI 이미지를 빌드해 컨테이너를 실행한다.
```bash
docker compose config -q
docker compose up -d --build
docker compose ps
docker compose logs backend
```
- `config -q`: 설정 유효성 검사. 아무것도 안 나오면 정상이다.
- `--build`: 서비스 이미지를 빌드한다. 처음엔 Python 이미지 다운로드와 라이브러리 설치가 진행된다.
- Docker Desktop에서 `docker-practice`를 펼치면 db와 backend 컨테이너가 함께 보인다.
- `http://localhost:8000/docs`에서 `/health`, `/notes`를 다시 호출한다. 호스트에서 `uv run` 없이 FastAPI를 쓸 수 있고, 같은 DB 볼륨을 쓰므로 저장했던 메모도 조회된다.

## Compose 실습 3단계: 컨테이너 FastAPI 검색 API 확인
컨테이너로 띄운 FastAPI의 API 문서(`/docs`)에서 `POST /search`에 아래 JSON을 보낸다.
```json
{"query": "여러 컨테이너의 실행 설정을 한 파일로 관리하려면?"}
```
- 응답의 `documents`에 저장된 텍스트가 나오는지 확인한다.

## Compose 실습 4단계: FastAPI 코드 수정 후 재빌드로 반영
FastAPI 코드를 수정하면 이미지를 다시 빌드해야 컨테이너에 반영된다. `main.py`의 앱 제목을 바꾼 뒤 backend만 재빌드한다.
```python
app = FastAPI(title="나의 Compose 실습", lifespan=lifespan)
```
```bash
docker compose up -d --build backend
```
- Swagger(`/docs`)의 제목이 바뀌었는지 확인한다.

## Bind mount란: 이름 있는 볼륨과 비교
Dockerfile의 `COPY`는 빌드할 때 코드를 복사하므로, 내 컴퓨터의 코드를 고쳐도 이미 만든 이미지 안의 코드는 그대로다. Bind mount는 내 컴퓨터의 파일·폴더를 컨테이너 내부 경로에 연결하는 기능이라, 개발 중 재빌드 없이 수정한 코드를 컨테이너에서 쓸 수 있다.
- 이름 있는 볼륨: Docker가 관리하는 저장 공간에 연결. 실습 용도는 PostgreSQL 데이터 유지.
- Bind mount: 내 컴퓨터에서 지정한 파일·폴더에 연결. 실습 용도는 수정한 소스 코드를 컨테이너에서 사용.

## Bind mount 실습 1단계: 개발용 compose.dev.yaml 작성
`compose.yaml`과 같은 폴더에 개발 전용 설정 `compose.dev.yaml`을 만든다. DB, 포트, 환경변수 같은 공통 설정은 `compose.yaml`에서 가져온다.
```yaml
services:
  backend:
    command: ["uv", "run", "--no-sync", "fastapi", "dev", "main.py", "--host", "0.0.0.0", "--port", "8000"]
    environment:
      WATCHFILES_FORCE_POLLING: "true"
    volumes:
      - ./main.py:/app/main.py
```
- `command`: Dockerfile의 `CMD`(`fastapi run`) 대신 `fastapi dev`로 실행. 코드 변경을 감지하면 서버를 자동 재시작한다.
- `WATCHFILES_FORCE_POLLING`: WatchFiles가 파일을 주기적으로 확인(polling)하게 해, Docker에서 변경 알림이 안 오는 경우에도 감지한다.
- `./main.py:/app/main.py`: `내 컴퓨터 경로:컨테이너 경로`. 이미지의 원래 파일은 마운트 동안 가려질 뿐 이미지가 바뀌지는 않는다.

## Bind mount 실습 2단계: 기본 설정과 개발용 설정으로 실행
Compose는 기본으로 `compose.yaml`만 읽고 `compose.dev.yaml`은 자동으로 읽지 않는다. 기본 설정은 Dockerfile `CMD`대로 `fastapi run`으로 실행한다.
```bash
docker compose up -d
```
- `-d`: 백그라운드 실행. 이미지 재빌드가 필요하면 `docker compose up -d --build`.

개발용 설정은 `-f`로 두 파일을 합쳐 적용한다.
```bash
docker compose -f compose.yaml -f compose.dev.yaml config -q
docker compose -f compose.yaml -f compose.dev.yaml up -d
```
- `-f`: 사용할 Compose 파일 지정. 공통 설정에 개발용 설정을 덮어쓴다.
- backend의 실행 명령과 마운트가 달라지므로 backend 컨테이너가 다시 만들어진다.

## Bind mount 실습 3단계: 재빌드 없이 FastAPI 코드 변경 확인
개발용 Compose 설정으로 실행 중일 때 `main.py`의 제목을 고치고 저장한다.
```python
app = FastAPI(title="Bind mount 개발 실습", lifespan=lifespan)
```
- `http://localhost:8000/docs`를 새로고침하면 바뀐 제목이 보인다. `docker compose up`이나 빌드는 다시 하지 않는다.
- 서버 자동 재시작과 브라우저 새로고침은 별개라 화면은 직접 새로고침한다.
- 자동 반영은 마운트한 `main.py`만 된다. Dockerfile, 의존성 파일, 마운트 안 한 소스를 고쳤다면 재빌드한다.
```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```
- 기본 설정으로 돌아가려면 `docker compose up -d`. 이미지 속 코드를 쓰므로 수정 내용을 넣으려면 `--build`를 붙인다.

## 도커에서 FastAPI 실행하기 복습 Q&A
- Q. Dockerfile에서 `RUN`과 `CMD`의 차이는?
  A. `RUN`은 이미지 빌드 중 실행되어 결과가 이미지에 담기고, `CMD`는 컨테이너가 시작될 때 실행할 기본 명령만 저장한다.
- Q. 컨테이너 안 FastAPI를 `--host 0.0.0.0`으로 실행하는 이유는?
  A. `127.0.0.1`에만 바인딩하면 컨테이너 밖의 요청을 받을 수 없기 때문이다.
- Q. Compose에서 FastAPI가 PostgreSQL 준비 후에 시작하게 하려면?
  A. db에 `healthcheck`(`pg_isready`)를 두고, backend에 `depends_on: db: condition: service_healthy`를 쓴다.
- Q. backend 컨테이너에서 DB 주소로 `localhost:5433`을 쓰면 안 되는 이유는?
  A. 컨테이너 안의 `localhost`는 backend 자신이다. 같은 Compose 네트워크의 서비스 이름과 실제 포트인 `db:5432`를 써야 한다.
- Q. Bind mount 개발 설정에서 재빌드가 필요한 경우는?
  A. Dockerfile, 의존성 파일, 마운트하지 않은 소스 파일을 수정했을 때다.
