---
part: docker
lesson: 도커로 PostgreSQL 실행하기
order: 2
source_type: web
tags: [docker, compose, postgresql, compose-yaml, port, docker-compose-up]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1473/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 도커로 PostgreSQL 실행하기

## 도커로 PostgreSQL 실행하기 요약
`compose.yaml`에 PostgreSQL 서비스 하나를 정의하고, Docker Compose로 이미지 다운로드·포트 연결·컨테이너 실행·로그 확인·중지와 삭제까지 실습한다.

## Docker Compose 프로젝트와 서비스 기본 구조
Docker Compose 설정 파일 `compose.yaml`은 YAML 형식이며 들여쓰기로 구조를 구분하므로 탭 대신 2칸 공백을 쓴다. 가장 단순한 형태는 다음과 같다.
```yaml
name: docker-practice

services:
  db:
    image: postgres:17
```
- `name`: 프로젝트 이름. 관련 컨테이너·네트워크·볼륨을 구분하는 데 쓰인다.
- `services`: 실행할 서비스 목록을 정의한다.
- `db`: 직접 정한 서비스 이름이다.
- `image`: 서비스에 쓸 이미지다. `postgres`는 이미지 이름, `17`은 PostgreSQL 메이저 버전을 나타내는 태그다.

서비스가 하나여도 Compose를 쓸 수 있고, 서비스를 추가하면 한 프로젝트 안에서 함께 관리된다. 각 서비스는 별도의 컨테이너로 실행된다.

## PostgreSQL 실습 1단계: compose.yaml에 DB 서비스 설정
PostgreSQL 컨테이너용 `compose.yaml`에 환경변수와 포트를 추가한다.
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
```
- `POSTGRES_USER`: 처음 만들 DB 사용자.
- `POSTGRES_PASSWORD`: 그 사용자의 비밀번호. `"1234"`는 로컬 실습용 예제 값이다.
- `POSTGRES_DB`: 처음 만들 데이터베이스.
- `ports`: 호스트 포트를 컨테이너 포트에 연결한다.

이 환경변수들은 PostgreSQL 이미지가 빈 데이터 디렉터리를 처음 초기화할 때만 사용된다.

## Docker Compose 포트 매핑 읽는 법 (127.0.0.1:5433:5432)
Docker Compose의 `ports` 값 `"127.0.0.1:5433:5432"`는 앞에서부터 호스트 주소, 호스트 포트, 컨테이너 포트를 뜻한다.
```text
127.0.0.1 : 5433 : 5432
호스트 주소   호스트 포트   컨테이너 포트
```
호스트(내 컴퓨터)의 포트와 컨테이너 내부 포트는 서로 별개라서, 호스트에서 5432를 이미 쓰고 있어도 컨테이너 안에서는 5432를 쓸 수 있다. 이 실습은 로컬에 설치한 PostgreSQL이 호스트 5432를 쓰고 있으므로 호스트 5433을 컨테이너 5432에 연결한다.
- `localhost:5432`로 접속하면 기존 로컬 PostgreSQL에 연결된다.
- `localhost:5433`으로 접속하면 컨테이너의 PostgreSQL에 연결된다.

## PostgreSQL 실습 2단계: docker compose로 DB 실행과 로그 확인
`compose.yaml`이 있는 폴더에서 PostgreSQL 컨테이너를 실행하고 상태와 로그를 본다.
```bash
docker compose up -d
docker compose ps
docker compose logs db
```
- `up`: 설정대로 컨테이너를 만들고 실행한다. 이미지가 없으면 내려받는다.
- `-d`: 백그라운드로 실행하고 터미널을 돌려준다. (강의에는 `d`로 표기됨)
- `ps`: 이 프로젝트의 컨테이너 상태를 보여준다.
- `logs db`: `db` 서비스의 로그를 보여준다.

Docker Desktop의 Containers에서 `docker-practice`를 펼치고 db 컨테이너 로그에 `database system is ready to accept connections`가 나오면 접속 준비가 끝난 것이다. (강의 본문에 "로그에서"로 끊긴 문장이 있음)

## PostgreSQL 실습 3단계: VSCode에서 컨테이너 DB 접속
Docker로 실행한 PostgreSQL에는 기존에 쓰던 VSCode Database Client 확장으로 연결한다. 강의에는 접속 설정값이 따로 적혀 있지 않다. (내 메모: compose 설정 기준으로 host `localhost`, port `5433`, user `postgres`, password `1234`, database `docker_prac`을 넣으면 된다.)

## Docker Compose 컨테이너 중지와 삭제 명령
Docker Compose로 띄운 컨테이너를 멈추거나 지우는 명령은 다음과 같다.
```bash
docker compose stop          # 컨테이너를 남겨 두고 중지
docker compose start         # 중지된 컨테이너를 다시 시작
docker compose restart db    # DB 컨테이너 재시작
docker compose down          # 프로젝트의 컨테이너와 기본 네트워크 삭제
docker compose up -d         # 설정에 맞게 컨테이너를 생성하거나 실행
```
(강의의 명령표를 주석 달린 코드 블록으로 바꿈)
- 중지된 컨테이너가 남아 있는 것(`stop`)과 삭제 후 새 컨테이너를 만드는 것(`down` → `up`)은 다르다.
- 이 명령들로는 이미지가 삭제되지 않는다.

## 도커로 PostgreSQL 실행하기 복습 Q&A
- Q. Docker Compose의 `ports: "127.0.0.1:5433:5432"`에서 5433과 5432는 각각 무엇인가?
  A. 5433은 호스트(내 컴퓨터) 포트, 5432는 컨테이너 내부 PostgreSQL 포트다.
- Q. PostgreSQL 이미지의 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`는 언제 적용되나?
  A. 빈 데이터 디렉터리를 처음 초기화할 때 적용된다.
- Q. `docker compose stop`과 `docker compose down`의 차이는?
  A. `stop`은 컨테이너를 남겨 둔 채 중지하고, `down`은 프로젝트의 컨테이너와 기본 네트워크를 삭제한다.
- Q. Docker로 띄운 PostgreSQL이 접속 준비됐는지 어떻게 확인하나?
  A. `docker compose logs db`에서 `database system is ready to accept connections`를 확인한다.
