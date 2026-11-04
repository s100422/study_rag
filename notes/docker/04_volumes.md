---
part: docker
lesson: 볼륨으로 데이터 유지하기
order: 4
source_type: web
tags: [docker, volume, named-volume, compose, postgresql, persistence]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1474/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 볼륨으로 데이터 유지하기

## 볼륨으로 데이터 유지하기 요약
Docker 볼륨 설정 전과 후에 각각 PostgreSQL 컨테이너를 삭제·재생성해 보고, DB에 저장한 메모가 유지되는지 비교하는 실습이다.

## Docker 볼륨 실습 1단계: 볼륨 없이 메모 저장
`compose.yaml`에 `volumes` 설정이 없는 상태에서 시작한다. DB 컨테이너와 로컬 FastAPI가 실행 중일 때 `http://localhost:8000/docs`를 열고, `POST /notes`로 메모를 저장한 뒤 `GET /notes`에서 확인한다.
```json
{"text": "볼륨 설정 전 저장한 메모"}
```

## Docker 볼륨 실습 2단계: 볼륨 없이 컨테이너 삭제 후 재생성
볼륨이 없는 PostgreSQL 컨테이너를 삭제했다가 다시 만들어 데이터가 남는지 본다. 먼저 Ctrl+C로 FastAPI를 중지하고 컨테이너를 삭제한다.
```bash
docker compose down
```
DB 컨테이너를 다시 만들고 로그를 확인한다.
```bash
docker compose up -d
docker compose logs db
```
로그에 `database system is ready to accept connections`가 나오면 FastAPI를 다시 실행한다.
```bash
uv run fastapi dev main.py
```
`GET /notes`를 호출하면 저장했던 메모가 없고 빈 목록이 반환된다. 컨테이너 자체에 저장된 데이터는 컨테이너 삭제와 함께 사라지기 때문이다.

## Docker 이름 있는 볼륨(named volume)이란
Docker 이름 있는 볼륨은 컨테이너와 별도로 Docker가 관리하는 이름 붙은 저장 공간이다. 컨테이너 자체에 저장한 데이터는 컨테이너를 지우면 사라지지만, 볼륨에 저장하고 새 컨테이너에도 같은 볼륨을 연결하면 기존 데이터를 다시 쓸 수 있다. 그래서 DB 데이터를 컨테이너 재생성과 무관하게 유지하려면 볼륨이 필요하다.

## Docker 볼륨 실습 3단계: compose.yaml에 볼륨 추가
Ctrl+C로 로컬 FastAPI를 중지하고 DB 컨테이너를 종료한 뒤, PostgreSQL 데이터 경로에 이름 있는 볼륨을 연결하도록 `compose.yaml`을 바꾼다.
```yaml
name: docker-practice

services:
  db:
    image: postgres:17
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: "1234"
      POSTGRES_DB: docker_prac
    ports:
      - "127.0.0.1:5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```
- 최상위 `volumes`: 사용할 볼륨(`postgres_data`)을 정의한다.
- `db.volumes`: 그 볼륨을 컨테이너 경로에 연결한다.
- `/var/lib/postgresql/data`: PostgreSQL 17의 데이터 경로다.

새 이름의 볼륨을 처음 연결하면 빈 DB로 시작한다.

## Docker 볼륨 실습 4단계: 볼륨에 메모 저장
볼륨을 연결한 PostgreSQL 컨테이너를 실행하고 로그로 준비 완료를 확인한다.
```bash
docker compose up -d
docker compose logs db
```
FastAPI를 다시 실행(`uv run fastapi dev main.py`)한 뒤 `POST /notes`로 새 메모를 저장한다.
```json
{"text": "컨테이너를 다시 만들어도 남을 메모"}
```
`GET /notes`에서 저장한 메모의 `id`와 `text`를 확인해 둔다.

## Docker 볼륨 실습 5단계: 컨테이너 재생성 후 데이터 유지 확인
Ctrl+C로 FastAPI를 중지하고 볼륨이 연결된 DB 컨테이너를 삭제한 뒤 다시 만든다.
```bash
docker compose down
docker compose up -d
```
DB 준비 완료 로그를 확인하고 FastAPI를 다시 실행한 뒤 `GET /notes`를 호출하면, 삭제 전에 저장한 메모의 `id`와 `text`가 그대로 남아 있다. 새 컨테이너가 같은 `postgres_data` 볼륨을 연결하기 때문이다. Docker Desktop의 Volumes 화면에서도 `docker-practice_postgres_data` 볼륨을 확인할 수 있다(프로젝트 이름 + `_` + 볼륨 이름).

## 볼륨으로 데이터 유지하기 복습 Q&A
- Q. 볼륨 없이 PostgreSQL 컨테이너를 `docker compose down` 후 다시 만들면 메모는 어떻게 되나?
  A. 컨테이너와 함께 데이터가 사라져 `GET /notes`가 빈 목록을 반환한다.
- Q. compose.yaml에서 Docker 이름 있는 볼륨을 쓰려면 어디에 무엇을 적나?
  A. 최상위 `volumes:`에 볼륨 이름을 정의하고, 서비스의 `volumes:`에 `postgres_data:/var/lib/postgresql/data`처럼 연결한다.
- Q. PostgreSQL 17 컨테이너의 데이터 경로는?
  A. `/var/lib/postgresql/data`
- Q. Docker Desktop에서 이 실습의 볼륨은 어떤 이름으로 보이나?
  A. `docker-practice_postgres_data`
