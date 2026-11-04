---
part: docker
lesson: 배포
order: 7
source_type: web
tags: [deploy, aws, ec2, rds, nginx, https, certbot, vercel]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1478/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 배포

## 배포 요약
FastAPI 백엔드를 AWS EC2의 Docker 컨테이너로 띄우고 RDS PostgreSQL(pgvector)에 연결한 뒤, Nginx와 Let's Encrypt로 HTTPS를 붙이고, React 프론트엔드를 Vercel에 배포해 연결하는 전체 과정이다.

## 배포란
배포는 개발한 프로그램을 서버에 올리고, 사용자가 네트워크로 쓸 수 있게 실행 환경과 접속 경로를 구성하는 작업이다. 코드 복사뿐 아니라 프로그램 실행, DB 연결, 외부 요청 허용, HTTPS 설정까지 필요하다.

## 배포에 쓰는 서비스: EC2, RDS, Nginx, Vercel
배포 실습에 쓰는 네 가지 서비스의 역할이다.
- EC2: AWS의 가상 컴퓨터 대여 서비스. 한 대를 인스턴스라 부르며 OS·CPU·메모리·저장 공간이 있고, 터미널로 접속해 프로그램을 설치·실행한다.
- RDS: AWS의 관리형 데이터베이스 서비스. 설치·패치·백업 같은 운영 작업을 지원하고, 사용자는 엔진·크기·계정·네트워크 접근 범위를 설정한다.
- Nginx: HTTP 요청을 받는 웹 서버이자 리버스 프록시. 리버스 프록시는 클라이언트 요청을 먼저 받아 내부 앱으로 전달하고 응답을 돌려준다.
- Vercel: GitHub 저장소를 연결하면 빌드해서 접속 가능한 웹 주소로 제공하는 배포 플랫폼.

## 배포 전체 구조
배포 실습의 요청 흐름은 다음과 같다.
- Vercel → 사용자 브라우저: React 정적 파일(HTML·JavaScript) 제공
- 브라우저 → EC2의 Nginx 컨테이너: HTTPS, 443번 포트
- Nginx → FastAPI 컨테이너: HTTP, 8000번 포트
- FastAPI → RDS PostgreSQL(pgvector): TLS, 5432번 포트
- 로컬 PC의 `ingest.py` → RDS: RAG용 데이터 적재

## AWS 리전, VPC, 보안 그룹, 포트
AWS 배포에서 알아야 할 네트워크 개념이다.
- 리전: 리소스를 만드는 지역. 실습은 아시아 태평양(서울).
- VPC: AWS 안의 가상 네트워크. EC2와 RDS를 같은 VPC에 두면 사설 네트워크로 연결하도록 구성할 수 있지만, 라우팅과 보안 그룹도 맞아야 한다.
- 보안 그룹: EC2·RDS의 통신을 제어하는 가상 방화벽. 인바운드 규칙은 들어오는 연결, 아웃바운드 규칙은 나가는 연결을 허용한다.
- 포트: IP가 컴퓨터 위치라면, 포트는 그 컴퓨터의 어떤 서비스인지 구분하는 번호다.

실습에서 쓰는 포트:
- 22: SSH로 EC2 터미널 접속
- 80: HTTP 요청, 인증서 발급·갱신 검증
- 443: HTTPS 요청
- 5432: PostgreSQL 접속
- 8000: 컨테이너 안 FastAPI

## AWS 실습 1단계: 리전 설정과 RDS PostgreSQL 생성
AWS 콘솔에서 우측 상단 리전을 아시아 태평양 서울로 바꾸고 RDS PostgreSQL을 만든다. (원문은 스크린샷으로 안내)
- RDS 검색 → 데이터베이스 생성, PostgreSQL · 전체 구성 · 샌드박스 선택
- 엔진 버전: 17.x
- DB 인스턴스 식별자: `database-{num}` (각자 받은 번호)
- 퍼블릭 액세스: 예
- VPC 보안 그룹: 새로 생성, 이름 `aim-agent-rds-{num}`
- 추가 구성 → 초기 데이터베이스 이름: `aim_agent`

## AWS 실습 2단계: EC2 인스턴스 생성
AWS 콘솔에서 EC2 → 인스턴스 시작으로 서버를 만든다. (원문은 스크린샷으로 안내)
- 이름 및 태그: `aim-agent-ec2-{num}`
- OS 이미지: Ubuntu
- 키 페어: 키 페어 없이 계속 진행
- 네트워크 설정 → 편집, 보안 그룹 이름 `aim-agent-ec2-{num}`
- 인바운드 규칙: 소스 유형 "사용자 지정", 원본은 `com. ~ .ec2-instance-connect`로 끝나는 항목 선택 (브라우저 접속용 SSH 허용으로 보임, 내 메모)

## AWS 실습 3단계: EC2 Instance Connect로 브라우저에서 접속
EC2 Instance Connect는 AWS 콘솔에서 임시 SSH 키로 EC2에 접속하게 해 주는 기능이다. 인스턴스 선택 → "연결" → "연결"을 누르면 브라우저에 터미널이 열리고, 이후 EC2 명령은 이 터미널에서 실행한다. (원문은 스크린샷으로 안내)

## AWS 실습 4단계: RDS 보안 그룹에 EC2 접속 허용
RDS 보안 그룹의 인바운드 규칙에 EC2 보안 그룹을 추가해 EC2에서 RDS로 접속할 수 있게 한다. (원문은 스크린샷으로 안내)
- RDS → 데이터베이스 → 내 DB 선택 → 보안 그룹 규칙의 인바운드 규칙 → 보안 그룹 ID 선택
- 인바운드 규칙 편집 → 규칙 추가: 유형 PostgreSQL, 소스 "사용자 지정", 내 EC2 보안 그룹 선택
- 이 규칙은 해당 EC2 보안 그룹에 속한 인스턴스에서 RDS 접속을 허용한다.

## EC2 Docker 설치 1단계: 필요한 도구 설치
EC2 터미널에서 Docker 설치 전에 패키지 목록을 갱신하고 기본 도구를 설치한다.
```bash
sudo apt update
sudo apt install -y ca-certificates curl git
```
- `sudo`: 관리자 권한으로 실행
- `apt update`: 설치 가능한 패키지 목록과 버전 정보 갱신
- `-y`: 설치 확인에 자동 동의
- `ca-certificates`: HTTPS 서버 인증서 검증용 CA 인증서 모음
- `curl`: URL 요청·파일 다운로드 도구
- `git`: GitHub 코드 가져오기와 버전 관리

## EC2 Docker 설치 2단계: Docker 공개 키 등록
EC2 터미널에서 Docker 저장소 서명을 검증할 공개 키를 받아 APT가 읽을 수 있게 둔다.
```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```
- `install -m 0755 -d`: 키 보관 폴더 생성. 0755는 소유자만 쓰기, 나머지는 읽기·접근 가능.
- `curl ... -o`: Docker 공개 키를 `docker.asc`로 저장(`-o`는 저장 경로).
- `chmod a+r`: 모든 사용자에게 읽기 권한 부여.
- Ubuntu의 패키지 관리 도구 APT는 신뢰하는 공개 키로 저장소 정보의 서명을 검증하고, 저장소 정보의 해시값과 받은 패키지의 해시값을 비교해 변조를 확인한다.

## EC2 Docker 설치 3단계: Docker APT 저장소 등록
EC2 터미널에서 APT가 Docker 패키지를 어디서 받고 어떤 공개 키로 검증할지 등록한다.
```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```
- `Suites`: 현재 Ubuntu 코드네임을 자동으로 채운다.
- `Signed-By`: 서명 검증에 쓸 공개 키 경로.

## EC2 Docker 설치 4단계: Docker와 Compose 설치 및 확인
EC2 터미널에서 Docker 엔진과 빌드·Compose 플러그인을 설치하고 동작을 확인한다.
```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
sudo docker compose version
```
- `apt update`: Docker 저장소를 포함해 목록 갱신
- `systemctl enable --now docker`: 지금 실행하고 부팅 시 자동 시작
- `docker run --rm hello-world`: 테스트 컨테이너 실행 후 삭제. `Hello from Docker!`가 나와야 한다.
- `docker compose version`: Compose 설치 여부와 버전 확인

## RDS 연결에서 TLS와 CA 인증서의 역할
RDS에 접속할 때 TLS로 SQL 요청과 결과를 보호한다. TLS는 데이터를 암호화하고 변조를 검출하는 통신 보안 기술이다.
- RDS는 연결할 때 서버 인증서를 제시하고, 클라이언트는 CA 인증서를 신뢰 기준으로 그 인증서를 검증한다. CA는 인증서를 발급·서명하는 인증 기관이다.
- `global-bundle.pem`: RDS 서버 인증서를 검증할 CA 인증서 모음.
- `sslmode=verify-full`: 암호화 연결 + 인증서 신뢰성 + 접속한 호스트 이름까지 확인.

## RDS 연결 1단계: EC2에 RDS CA 인증서 다운로드
EC2 터미널에서 RDS CA 인증서 모음을 받아 `/home/ubuntu/global-bundle.pem`에 저장한다.
```bash
curl -fsSL \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  -o /home/ubuntu/global-bundle.pem
```
- `-o`: 저장할 파일 경로

## RDS 연결 2단계: psql 컨테이너로 RDS 접속
RDS 콘솔에서 endpoint를 확인한 뒤(원문은 스크린샷으로 안내), EC2 터미널에서 PostgreSQL 17 임시 컨테이너의 psql로 RDS에 접속한다. 실행하면 비밀번호를 입력한다.
```bash
sudo docker run --rm -it \
  -v /home/ubuntu/global-bundle.pem:/certs/global-bundle.pem:ro \
  postgres:17-alpine \
  psql "host=<RDS_ENDPOINT> port=5432 dbname=aim_agent user=postgres sslmode=verify-full sslrootcert=/certs/global-bundle.pem"
```
- psql: 터미널에서 PostgreSQL에 접속해 SQL을 실행하는 클라이언트
- `-v ...:ro`: CA 인증서를 컨테이너에 읽기 전용으로 연결 (내 메모)
- `sslrootcert`: 서버 인증서 검증에 쓸 CA 파일 (내 메모)

## RDS 연결 3단계: pgvector 확장 활성화
RDS에 연결된 psql에서 pgvector 확장을 켜고 확인한다.
```sql
CREATE EXTENSION IF NOT EXISTS vector;

SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
```
- `CREATE EXTENSION IF NOT EXISTS vector`: 현재 DB에 벡터 저장·검색용 pgvector 활성화
- `SELECT ...`: `vector`와 버전이 나오면 활성화된 것
- 확인 후 `\q`로 psql 종료

## 백엔드 배포 1단계: 저장소 준비와 배포용 compose.yaml
로컬 PC에서 받은 backend 코드를 GitHub 저장소에 push한다. 로컬 백엔드 폴더의 `compose.yaml`은 배포용으로 아래처럼 쓴다.
```yaml
name: deploy-backend

services:
  backend:
    build: .
    env_file:
      - ./.env
    environment:
      PGSSLMODE: verify-full
      PGSSLROOTCERT: /certs/global-bundle.pem
    volumes:
      - /home/ubuntu/global-bundle.pem:/certs/global-bundle.pem:ro
    ports:
      - "127.0.0.1:8000:8000"
    restart: unless-stopped
```
- `PGSSLMODE`, `PGSSLROOTCERT`: PostgreSQL 클라이언트가 읽는 TLS 설정 환경변수 (내 메모)
- `volumes`: EC2의 CA 파일을 컨테이너에 읽기 전용으로 연결
- `restart: unless-stopped`: 직접 멈추지 않는 한 자동 재시작 (내 메모: Docker 표준 동작 설명)

## 백엔드 배포 2단계: EC2에 코드 가져오기와 .env 작성
EC2 터미널에서 GitHub 저장소를 clone하고 `.env`를 만든다.
```bash
cd /home/ubuntu
git clone "https://github.com/<GITHUB_OWNER>/<BACKEND_REPO>.git"
cd "/home/ubuntu/<BACKEND_REPO>"
nano .env
```
(원문의 clone 주소는 `"<https://github.com/><GITHUB_OWNER>/..."`처럼 링크 표기가 섞여 있어 정상 URL로 고쳐 적었다.)
```bash
DATABASE_URL=postgresql://postgres@<RDS_ENDPOINT>:5432/<DB_NAME>
PGPASSWORD='<DB_PASSWORD>'
GEMINI_API_KEY=<GEMINI_API_KEY>
CORS_ALLOWED_ORIGINS=
```
- nano: 터미널 텍스트 편집기. 파일이 없으면 새로 만든다.
- 저장은 `Ctrl+O` → `Enter`, 종료는 `Ctrl+X`.
- `CORS_ALLOWED_ORIGINS`는 프론트 배포 후 채운다.

## 백엔드 배포 3단계: EC2에서 빌드·실행과 health 확인
EC2의 백엔드 폴더에서 이미지를 빌드해 실행하고 로그를 본다.
```bash
sudo docker compose up -d --build backend
sudo docker compose ps
sudo docker compose logs --tail 50 backend
curl -i http://127.0.0.1:8000/health
```
- `logs --tail 50`: 마지막 50줄 로그로 서버 시작 확인
- `curl -i .../health`: `200 OK`와 `{"status":"ok"}`가 나오면 정상
- 이 단계에서는 포트를 `127.0.0.1`에만 열었으므로 EC2 내부에서만 API에 접근된다.

## RAG 데이터 적재 1단계: 로컬 PC에서 RDS 연결 확인
로컬 PC에서 RDS에 데이터를 넣으려면 5432 포트로 연결돼야 한다. RDS 퍼블릭 액세스가 켜져 있고 보안 그룹이 현재 PC의 공인 IP에 5432를 허용한다는 전제다. 로컬 백엔드 폴더 터미널에서 확인한다.
```powershell
Test-NetConnection -ComputerName "<RDS_ENDPOINT>" -Port 5432
```
```bash
# mac
nc -vz -G 5 "<RDS_ENDPOINT>" 5432
```
- `succeeded`가 나오면 TCP 연결 가능
- 이어서 로컬에도 CA 인증서 모음을 받는다.
```bash
curl -fsSL \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  -o global-bundle.pem
```

## RAG 데이터 적재 2단계: 로컬 .env 작성과 ingest.py 실행
로컬 백엔드 폴더의 `.env`에 Gemini API 키와 RDS 접속 정보를 넣는다.
```bash
GEMINI_API_KEY='<GEMINI_API_KEY>'

DATABASE_URL=postgresql://<DB_USER>@<RDS_ENDPOINT>:5432/<DB_NAME>
PGPASSWORD='<DB_PASSWORD>'
PGSSLMODE=verify-full
PGSSLROOTCERT=./global-bundle.pem
```
그다음 의존성을 맞추고 적재 스크립트를 실행한다. 예제 코드는 문서 6개를 저장한다.
```bash
uv sync --frozen
uv run --no-sync ingest.py
```

## RAG 데이터 적재 3단계: EC2에서 검색 API 확인
EC2 터미널에서 백엔드 검색 API를 호출해 RDS에 적재한 문서가 검색되는지 본다.
```bash
curl -i http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Docker Compose는 무엇인가요?"}'
```

## Nginx 리버스 프록시와 HTTP·HTTPS 구간
Nginx는 브라우저 요청을 받아 FastAPI로 넘기고 응답을 돌려주는 리버스 프록시로 쓴다. HTTPS는 HTTP를 TLS로 보호하는 방식으로, 암호화·변조 검출과 함께 클라이언트가 서버 인증서로 접속한 서버가 맞는지 확인한다.
- 브라우저 → Nginx: HTTPS. 인터넷을 지나는 요청·응답 보호
- Nginx → FastAPI: HTTP. 같은 EC2의 Docker 네트워크 안
- FastAPI → RDS: PostgreSQL 연결에 TLS 적용

## Nginx 실습 1단계: EC2 보안 그룹에 80·443 허용
AWS 콘솔에서 EC2 인스턴스의 보안 그룹에 들어가 인바운드 규칙을 추가한다. (원문은 스크린샷으로 안내)
- HTTP, 포트 80, 소스 `0.0.0.0/0`
- HTTPS, 포트 443, 소스 `0.0.0.0/0`

## Nginx 실습 2단계: HTTP용 nginx.conf 작성
로컬 백엔드 폴더에 `nginx.conf`를 만든다. EC2 콘솔에서 퍼블릭 IP를 확인해 `<EC2_PUBLIC_IP>`에 넣는다.
```nginx
server {
    listen 80;
    server_name <EC2_PUBLIC_IP>;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
        try_files $uri =404;
    }

    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
- `listen 80`, `server_name`: EC2 퍼블릭 IP의 80번으로 HTTP 수신
- `/.well-known/acme-challenge/`: 인증서 검증 파일 제공, 없으면 404
- `proxy_pass`: 나머지 요청을 `backend:8000`으로 전달
- `proxy_set_header`: 요청 주소, 클라이언트 IP, HTTP/HTTPS 여부 전달

## Nginx 실습 3단계: compose.yaml에 nginx 서비스 추가
배포용 `compose.yaml`에 nginx를 추가하고, backend에 `FORWARDED_ALLOW_IPS`를 넣는다. 수정한 두 파일(`nginx.conf`, `compose.yaml`)을 커밋·push한다. (backend 블록은 직전 단계와 같아 일부 줄을 `...`로 줄였다.)
```yaml
services:
  backend:
    # ... build, env_file, volumes, ports, restart 동일
    environment:
      PGSSLMODE: verify-full
      PGSSLROOTCERT: /certs/global-bundle.pem
      FORWARDED_ALLOW_IPS: "*"
  nginx:
    image: nginx:1.30.6-alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - /var/lib/letsencrypt:/var/www/certbot:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - backend
    restart: unless-stopped
```
- `FORWARDED_ALLOW_IPS`: 프록시가 보낸 `X-Forwarded-*` 헤더를 신뢰하게 하는 설정 (내 메모)
- `/var/lib/letsencrypt`: Certbot과 공유하는 검증 파일 폴더
- `/etc/letsencrypt`: 발급될 인증서 폴더

## Nginx 실습 4단계: EC2에 Nginx 적용과 HTTP 확인
EC2 백엔드 폴더에서 변경 내용을 받고, 인증서용 폴더를 만든 뒤 컨테이너를 띄운다.
```bash
git pull --ff-only
sudo mkdir -p /etc/letsencrypt /var/lib/letsencrypt/.well-known/acme-challenge
sudo docker compose up -d backend
sudo docker compose up -d nginx
curl -i http://127.0.0.1/health
```
- `mkdir -p`: 인증서·개인 키·검증 파일을 둘 폴더. 검증 파일은 이후 Certbot이 만든다.

로컬 터미널에서도 외부 접속을 확인한다. 두 요청 모두 `200 OK`, `{"status":"ok"}`면 된다.
```bash
curl -i "http://<EC2_PUBLIC_IP>/health"
```

## Let's Encrypt와 Certbot의 역할
HTTPS 인증서를 무료로 받으려고 Let's Encrypt와 Certbot을 쓴다.
- Let's Encrypt: 무료 인증 기관. 요청자가 그 도메인·IP의 서버를 제어하는지 확인한 뒤 인증서를 발급한다.
- Certbot: 발급·갱신 요청, 검증 파일 준비, 인증서 저장을 하는 클라이언트. EC2에서 컨테이너로 실행한다.
- Nginx: 검증 파일을 제공하고, 발급된 인증서로 HTTPS를 처리한다.
- Certbot이 받은 인증서를 Nginx가 읽도록 연결해야 HTTPS 요청을 받을 수 있다.

## Certbot webroot 방식의 인증 흐름
Certbot의 webroot 방식은 웹 서버가 파일을 제공하는 폴더(webroot)에 확인용 파일을 만들고 Nginx가 HTTP로 내보내게 하는 방식이다.
- Certbot이 Let's Encrypt에 IP 주소 인증서를 요청하면, Let's Encrypt가 확인에 필요한 값을 알려 준다.
- Certbot이 공유 폴더에 확인용 파일을 만든다.
- Let's Encrypt가 `http://<EC2_PUBLIC_IP>/.well-known/acme-challenge/...`로 80번 포트에 파일을 요청하고 Nginx가 응답한다.
- 내용이 맞으면 Let's Encrypt가 인증서를 발급한다.
- EC2의 `/var/lib/letsencrypt`를 Certbot과 Nginx가 함께 마운트하므로 Certbot이 만든 파일을 Nginx가 읽을 수 있다. 서버가 실행 중이어야 한다.

## HTTPS 실습 1단계: 인증 확인용 경로 검사
EC2 터미널에서 검증 폴더에 테스트 파일을 만든다.
```bash
echo ok | sudo tee /var/lib/letsencrypt/.well-known/acme-challenge/check
```
로컬 터미널에서 외부로 읽히는지 확인한다. `ok`가 나오면 검증 파일 경로가 정상이다.
```bash
curl "http://<EC2_PUBLIC_IP>/.well-known/acme-challenge/check"
```

## HTTPS 실습 2단계: Certbot으로 IP 주소 인증서 발급
EC2 터미널에서 Certbot webroot 방식으로 EC2 퍼블릭 IP용 인증서를 받는다. IP 인증서는 유효기간이 약 6일이라 자동 갱신 예약도 해야 한다. `<CERT_NAME>`은 임의 이름(수업에선 `ec2-prac`).
```bash
sudo docker run --rm -it --pull=always \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/lib/letsencrypt:/var/www/certbot \
  certbot/certbot:latest certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --preferred-profile shortlived \
  --ip-address "<EC2_PUBLIC_IP>" \
  --cert-name "<CERT_NAME>"
```
- 이메일 입력과 약관 확인 후, 성공하면 `Successfully received certificate.`가 출력된다.
- `--preferred-profile shortlived`: 단기 인증서 프로필 요청 (내 메모)

## HTTPS 서버 인증서와 개인 키
HTTPS용 서버 인증서는 도메인·IP와 공개 키를 묶어 인증 기관이 서명한 자료다. 브라우저는 인증 기관 신뢰 여부, 유효기간, 접속 주소와의 일치를 확인한다. 서버는 인증서와 짝인 개인 키로 TLS 연결에서 신원을 증명하며, 인증서는 클라이언트에 주고 개인 키는 서버가 보관한다.
- `fullchain.pem`: Nginx가 클라이언트에 제시하는 서버 인증서 + 중간 인증서
- `privkey.pem`: Nginx가 TLS 연결에 쓰는 서버 개인 키

## HTTPS 실습 3단계: HTTPS용 nginx.conf로 교체
인증서 발급 후 로컬 `nginx.conf`를 아래로 바꾸고, `<EC2_PUBLIC_IP>`, `<CERT_NAME>`을 실제 값으로 채운다. (80번 블록의 acme-challenge location은 HTTP 설정과 같아 한 줄로 줄였다.)
```nginx
server {
    listen 80;
    server_name <EC2_PUBLIC_IP>;
    location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; default_type text/plain; try_files $uri =404; }
    location / {
        return 308 https://<EC2_PUBLIC_IP>$request_uri;
    }
}
server {
    listen 443 ssl;
    server_name <EC2_PUBLIC_IP>;
    ssl_certificate /etc/letsencrypt/live/<CERT_NAME>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<CERT_NAME>/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
- 80번: 검증 파일만 HTTP로 주고 나머지는 308로 HTTPS 리다이렉트
- 443번: 인증서·개인 키로 HTTPS 수신, TLS 1.2·1.3 허용

## HTTPS 실습 4단계: Compose에 443 포트 추가와 적용
`compose.yaml`의 nginx 서비스 `ports`에 443을 추가하고, `nginx.conf`와 함께 커밋·push한다.
```yaml
    ports:
      - "80:80"
      - "443:443"
```
EC2 백엔드 폴더에서 받아서 설정을 검사하고 nginx만 다시 만든다.
```bash
git pull --ff-only
sudo docker compose run --rm --no-deps nginx nginx -t
sudo docker compose up -d --no-deps --force-recreate nginx
```
- `run --rm --no-deps nginx nginx -t`: 임시 Nginx 컨테이너로 설정 문법·참조 파일 검사, backend는 띄우지 않고 검사 후 삭제
- `--force-recreate nginx`: nginx 컨테이너만 새로 만들어 설정·포트 적용

로컬에서 인증서 오류 없이 `200 OK`, `{"status":"ok"}`가 나오는지 확인한다.
```bash
curl -i "https://<EC2_PUBLIC_IP>/health"
```

## 인증서 자동 갱신 원리: Certbot renew와 systemd 타이머
HTTPS 인증서는 유효기간이 지나면 브라우저가 쓸 수 없으므로 만료 전에 교체해야 한다.
- `certbot renew`: 저장된 인증서와 갱신 설정을 읽고 갱신 시점인지 판단한다. 시점이 아니면 건너뛰므로 주기적으로 돌려도 된다.
- `nginx -s reload`: 처리 중 요청은 마무리하면서 설정과 인증서를 다시 읽는다. 새 인증서가 저장된 뒤 필요하다.
- systemd: Ubuntu에서 서비스 실행·상태를 관리한다. 할 일은 서비스 파일(.service), 실행 시각은 타이머 파일(.timer)에 쓴다.
- 예약 시각에 EC2가 Certbot 컨테이너를 실행하고 끝나면 정리한다. 터미널을 닫아도 EC2가 켜져 있으면 동작한다.

## 인증서 자동 갱신 1단계: 갱신 과정 dry-run 시험
EC2 터미널에서 임시 Certbot 컨테이너로 갱신 절차를 실제 발급 없이 시험한다.
```bash
sudo docker run --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/lib/letsencrypt:/var/www/certbot \
  certbot/certbot:latest renew \
  --cert-name "<CERT_NAME>" \
  --dry-run \
  --non-interactive
```
- `--dry-run`: 갱신 절차만 시험
- `--non-interactive`: 입력 요청 없이 진행 (내 메모)

## 인증서 자동 갱신 2단계: systemd 서비스 파일 작성
EC2 터미널에서 `<BACKEND_REPO>`, `<CERT_NAME>`을 바꿔 블록 전체를 실행한다. 갱신 시점이 아니어도 Nginx 검사와 reload는 실행된다.
```bash
sudo tee /etc/systemd/system/ec2-api-renew.service > /dev/null <<'EOF'
[Unit]
Description=Renew EC2 API certificate and reload Nginx
Wants=network-online.target
Requires=docker.service
After=network-online.target docker.service

[Service]
Type=oneshot
WorkingDirectory=/home/ubuntu/<BACKEND_REPO>
TimeoutStartSec=30min
ExecStart=/usr/bin/docker run --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/lib/letsencrypt:/var/www/certbot \
  certbot/certbot:latest renew --cert-name <CERT_NAME> --non-interactive
ExecStart=/usr/bin/docker compose exec -T nginx nginx -t
ExecStart=/usr/bin/docker compose exec -T nginx nginx -s reload
EOF
```
- `Type=oneshot`: 한 번 실행하고 끝나는 작업, `ExecStart`가 순서대로 실행된다. (내 메모)

## 인증서 자동 갱신 3단계: systemd 타이머 파일 작성
EC2 터미널에서 갱신 작업의 실행 시각을 정하는 타이머 파일을 만든다.
```bash
sudo tee /etc/systemd/system/ec2-api-renew.timer > /dev/null <<'EOF'
[Unit]
Description=Check EC2 API certificate renewal twice daily

[Timer]
OnCalendar=*-*-* 03,15:00:00 Asia/Seoul
RandomizedDelaySec=30min
Persistent=true

[Install]
WantedBy=timers.target
EOF
```
- `OnCalendar`: 매일 서울 시간 03시·15시 (내 메모)
- `RandomizedDelaySec=30min`: 최대 30분 무작위 지연 (내 메모)
- `Persistent=true`: 꺼져 있어 놓친 실행을 다음 부팅 때 수행 (내 메모: systemd 표준 동작)

## 인증서 자동 갱신 4단계: 예약 활성화와 로그 확인
EC2 터미널에서 systemd 설정을 다시 읽고 갱신 작업을 한 번 직접 실행한다.
```bash
sudo systemctl daemon-reload
sudo systemctl start ec2-api-renew.service
```
오류 없이 끝나면 타이머를 켜고 예약·로그를 확인한다.
```bash
sudo systemctl enable --now ec2-api-renew.timer
sudo systemctl list-timers ec2-api-renew.timer --no-pager
sudo journalctl -u ec2-api-renew.service -n 30 --no-pager
```
- 타이머는 미래 실행을 예약하고, 서비스가 실제 작업을 한다.

## Vercel 프론트엔드 배포 1단계: GitHub 연결과 환경변수
로컬 PC에서 받은 프론트엔드 코드를 GitHub 저장소에 push하고 Vercel에 배포한다. (원문은 스크린샷으로 안내)
- `https://vercel.com/` 로그인 → 우측 상단 Create New → Project
- 좌측 하단에서 GitHub와 저장소 연결 → Import하면 배포 완료
- 프로젝트 Settings → Environment Variables → `VITE_API_URL`에 배포한 백엔드 주소 입력 (예: `https://<EC2_PUBLIC_IP>`, 내 메모)
- 환경변수 반영을 위해 재배포(Redeploy) 진행

## Vercel 프론트엔드 배포 2단계: 백엔드 CORS에 프론트 주소 허용
EC2 백엔드 폴더의 `.env`에서 `CORS_ALLOWED_ORIGINS`를 Vercel 프론트 주소로 바꾼다.
```bash
CORS_ALLOWED_ORIGINS=<FRONTEND_ORIGIN>
```
EC2 백엔드 폴더에서 이미지 재빌드 없이 backend를 다시 만들고 Nginx를 reload한다.
```bash
sudo docker compose up -d --no-build --force-recreate backend
sudo docker compose exec -T nginx nginx -s reload
```
로컬 터미널에서 Origin 헤더를 붙여 CORS 응답을 확인한다.
```bash
curl -i "https://<EC2_PUBLIC_IP>/health" \
  -H "Origin: <FRONTEND_ORIGIN>"
```
- 응답 헤더에 `Access-Control-Allow-Origin`이 프론트 주소로 오는지 보면 된다. (내 메모)

## Vercel 프론트엔드 배포 3단계: 브라우저 최종 확인
`<FRONTEND_ORIGIN>`을 브라우저로 열고 배포 전체가 연결됐는지 확인한다.
- 백엔드 상태 확인이 성공하는지
- 검색어를 넣었을 때 문서 검색 결과가 나오는지
- 개발자 도구 Network에서 요청 주소가 `https://<EC2_PUBLIC_IP>`로 시작하는지
- Console에 CORS 오류가 없는지

## 배포 복습 Q&A
- Q. 배포 구조에서 브라우저→Nginx, Nginx→FastAPI, FastAPI→RDS 구간은 각각 어떤 연결인가?
  A. HTTPS(443), 같은 Docker 네트워크 안의 HTTP(8000), TLS를 적용한 PostgreSQL(5432)이다.
- Q. RDS 접속에서 `sslmode=verify-full`과 `global-bundle.pem`의 역할은?
  A. `global-bundle.pem`은 RDS 서버 인증서를 검증할 CA 모음이고, `verify-full`은 암호화와 함께 인증서 신뢰성·호스트 이름까지 확인한다.
- Q. Certbot webroot 방식에서 Nginx가 80번 포트를 열어 두어야 하는 이유는?
  A. Let's Encrypt가 `/.well-known/acme-challenge/` 경로의 확인용 파일을 HTTP 80번으로 요청해 서버 제어 여부를 검증하기 때문이다.
- Q. EC2 IP 인증서에 자동 갱신 예약이 꼭 필요한 이유와 방법은?
  A. IP 인증서 유효기간이 약 6일로 짧기 때문이다. systemd 서비스(`certbot renew` → `nginx -t` → `nginx -s reload`)와 하루 두 번 도는 타이머로 예약한다.
- Q. Vercel 프론트에서 백엔드 호출 시 CORS 오류가 나면 무엇을 확인하나?
  A. EC2 `.env`의 `CORS_ALLOWED_ORIGINS`에 프론트 주소가 있는지, backend 컨테이너를 다시 만들었는지 확인한다.
