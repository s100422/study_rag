---
part: docker
lesson: 로컬 서버에서 도커 DB 연결하기
order: 3
source_type: web
tags: [docker, postgresql, fastapi, database-url, dotenv, port]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1477/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 로컬 서버에서 도커 DB 연결하기

## 로컬 서버에서 도커 DB 연결하기 요약
호스트(내 컴퓨터)에서 FastAPI를 실행하고, Docker 컨테이너로 띄운 PostgreSQL에 연결해 메모를 저장·조회하는 실습이다.

## 도커 DB 연결 실습 1단계: PostgreSQL 컨테이너 상태 확인
FastAPI를 띄우기 전에 Docker Compose의 PostgreSQL 컨테이너(`db` 서비스)가 실행 중인지 확인한다.
```bash
docker compose ps -a db
```
상태가 `Up`이면 실행 중이다. 컨테이너가 없거나 실행 중이 아닐 때만 다음 명령으로 시작한다.
```bash
docker compose up -d db
```
- `ps -a db`: 중지된 것까지 포함해 `db` 서비스 컨테이너 상태를 보여준다.
- `up -d db`: `db` 서비스만 백그라운드로 생성·실행한다.

## 도커 DB 연결 실습에서 제공되는 FastAPI 엔드포인트
강의에서 제공하는 FastAPI 백엔드는 시작할 때 `notes` 테이블을 준비하고, 데이터 저장·조회를 Docker의 PostgreSQL로 처리한다. 엔드포인트는 다음과 같다.
- `GET /health`: 앱과 DB 연결 상태 확인
- `POST /notes`: 메모 저장
- `GET /notes`: 최근 메모 최대 20개 조회
- `POST /search`: pgvector에 저장한 텍스트 검색

백엔드 소스 코드(`main.py`)는 강의 본문에 나오지 않고 제공 파일로만 쓰인다.

## 도커 DB 연결 실습 2단계: .env의 DATABASE_URL 확인
FastAPI 앱은 시작할 때 `load_dotenv()`로 `.env` 파일의 환경변수를 불러온다. Docker PostgreSQL에 연결하려면 `DATABASE_URL`이 호스트 포트 5433을 가리켜야 한다.
```bash
DATABASE_URL=postgresql://postgres:1234@localhost:5433/docker_prac
GEMINI_API_KEY=
```
- `postgres:1234`: compose.yaml에 설정한 실습용 사용자와 비밀번호.
- `localhost:5433`: 컨테이너 5432 포트에 연결된 호스트 포트.
- `docker_prac`: compose.yaml의 `POSTGRES_DB`로 만든 데이터베이스.
- `GEMINI_API_KEY`: 이 레슨에서는 비워 둔다. (내 메모: pgvector 검색 레슨에서 사용)

## 도커 DB 연결 실습 3단계: 로컬 FastAPI 실행
의존성을 맞춘 뒤 호스트에서 FastAPI 개발 서버를 실행한다.
```bash
uv sync
uv run fastapi dev main.py
```
연결 구조는 다음과 같다(강의의 흐름도를 문장으로 옮김).
- 브라우저 → `localhost:8000` → 로컬 FastAPI
- 로컬 FastAPI → `localhost:5433`(호스트 포트) → PostgreSQL 컨테이너의 5432

FastAPI는 호스트에서 실행되므로 `localhost`는 내 컴퓨터를 가리킨다. DB는 컨테이너 안에 있으므로 공개된 호스트 포트 5433을 거쳐 접속한다.

## 도커 DB 연결 실습 4단계: Swagger에서 메모 저장·조회
FastAPI 문서 페이지(`http://localhost:8000/docs`)에서 `GET /health`를 열고 Try it out → Execute를 누르면 다음 응답이 나온다.
```json
{"status": "ok"}
```
`POST /notes`에 다음 JSON을 넣어 실행한다.
```json
{"text": "Compose로 PostgreSQL 연결 성공"}
```
응답에는 생성된 `id`와 입력한 `text`가 들어 있다. 이어서 `GET /notes`를 실행해 같은 메모가 조회되는지 확인하면 Docker PostgreSQL 연결이 완료된 것이다.

## 로컬 서버에서 도커 DB 연결하기 복습 Q&A
- Q. 호스트에서 실행한 FastAPI가 Docker PostgreSQL에 접속할 때 왜 5432가 아니라 5433을 쓰나?
  A. compose.yaml에서 호스트 5433을 컨테이너 5432에 연결했고, 호스트 5432는 로컬 PostgreSQL이 쓰고 있기 때문이다.
- Q. 이 실습의 `DATABASE_URL`은?
  A. `postgresql://postgres:1234@localhost:5433/docker_prac`
- Q. FastAPI 앱은 `.env`의 값을 어떻게 읽나?
  A. 앱 시작 시 `load_dotenv()`가 `.env`의 환경변수를 불러온다.
- Q. Docker PostgreSQL 컨테이너가 실행 중인지 확인하는 명령은?
  A. `docker compose ps -a db` (상태가 `Up`이면 실행 중)
