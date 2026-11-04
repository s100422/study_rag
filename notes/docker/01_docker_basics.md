---
part: docker
lesson: 도커 기초
order: 1
source_type: web
tags: [docker, image, container, volume, docker-desktop, docker-hub, dockerfile, compose]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1472/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 도커 기초

## 도커 기초 요약
Docker가 해결하는 문제(실행 환경 차이)를 이해하고, 이미지·컨테이너·볼륨의 관계와 Docker Engine, Docker Hub, Dockerfile, Compose 같은 구성 요소를 살펴본 뒤 Docker Desktop을 설치하는 레슨이다.

## Docker란
Docker는 애플리케이션과 그 실행에 필요한 파일을 이미지로 묶고, 그 이미지로 컨테이너를 만들어 실행·관리하는 플랫폼이다. 소스 코드만 넘기면 받는 쪽이 Python과 라이브러리를 직접 준비해야 하지만, Docker 이미지에는 Python 실행 파일, 라이브러리, 소스 코드를 함께 담아 전달할 수 있다. 이미지를 받은 컴퓨터에서 Docker가 만드는 실행 환경을 컨테이너라고 한다.

## Docker가 필요한 이유: 실행 환경 차이 문제
Docker가 필요한 이유는 같은 코드라도 실행 환경이 다르면 결과가 달라질 수 있기 때문이다. FastAPI 코드도 Python, FastAPI, 관련 라이브러리, 때로는 운영체제의 프로그램에 의존한다. 환경 차이로 생기는 대표적인 문제는 다음과 같다.
- 개발자마다 Python 버전이 다르면 쓸 수 있는 문법이나 라이브러리가 달라진다.
- 라이브러리 버전이 다르면 함수 사용법이나 실행 결과가 달라진다.
- 한 컴퓨터에서 여러 프로젝트를 하면 프로젝트마다 요구하는 프로그램·버전이 다르다.
- 다른 컴퓨터에 개발 환경을 새로 준비할 때 설치 항목이나 설정을 빠뜨릴 수 있다.

Docker는 필요한 파일을 이미지로 준비해 프로젝트별 컨테이너에서 쓰게 하므로, 같은 이미지를 공유하면 컴퓨터마다 환경을 맞추는 일이 줄어든다. 예를 들어 PostgreSQL을 컨테이너로 실행하면 내 컴퓨터에 PostgreSQL 서버를 직접 설치하지 않아도 된다.

## Docker 컨테이너란
Docker 컨테이너는 프로그램을 격리된 환경에서 실행하는 단위다. 컨테이너마다 실행에 필요한 파일과 라이브러리를 따로 쓰므로, 같은 컴퓨터에서도 서로 다른 실행 환경을 유지할 수 있다. 예를 들어 한 컨테이너는 Python 3.11, 다른 컨테이너는 Python 3.12를 쓸 수 있고, 각 컨테이너에 설치한 라이브러리도 서로 영향을 주지 않는다.

## Docker 컨테이너와 Python 가상환경(.venv)의 차이
Python 가상환경 `.venv`는 프로젝트별 Python 패키지만 분리하고, Docker 컨테이너는 Python 실행 파일·시스템 라이브러리·애플리케이션 파일까지 함께 준비하며 프로세스 실행 환경도 격리한다.
- 주요 목적: 가상환경은 프로젝트별 Python 패키지 관리, 컨테이너는 애플리케이션 실행 환경 구성과 격리.
- 파일·프로세스·네트워크: 가상환경은 호스트 환경을 그대로 쓰고, 컨테이너는 격리된 환경을 쓴다.
- PostgreSQL 같은 별도 프로그램: 가상환경으로는 설치·격리하지 않지만, 컨테이너는 해당 프로그램의 이미지로 실행할 수 있다.

둘은 함께 쓸 수도 있다. 컨테이너 안에서 Python 가상환경을 만들어 패키지를 관리하면 된다.

## Docker 이미지란
Docker 이미지는 컨테이너를 만들 때 쓰는 실행 파일과 설정의 묶음이다. FastAPI 애플리케이션용 이미지라면 다음을 담을 수 있다.
- Python 실행 파일
- FastAPI 등 필요한 라이브러리
- 애플리케이션 소스 코드
- 필요한 시스템 라이브러리
- 컨테이너 시작 시 실행할 기본 명령

이미지로 컨테이너를 만들고, 컨테이너를 시작하면 그 안에서 프로그램이 실행된다.

## Docker 컨테이너의 데이터 저장과 볼륨
Docker 컨테이너 자체의 저장 공간에 만든 파일은 컨테이너를 중지했다가 다시 시작해도 남지만, 컨테이너를 삭제하면 그 변경분도 사라진다. DB 데이터처럼 컨테이너를 새로 만들어도 유지해야 하는 내용은 Docker가 컨테이너와 별도로 관리하는 저장 공간인 볼륨에 둔다.
- 이미지: 프로그램을 준비하는 데 쓴다.
- 볼륨: 실행 중 생기는 데이터를 보존하는 데 쓴다. 같은 볼륨을 새 컨테이너에 연결하면 저장한 데이터를 다시 쓸 수 있다.

## Docker Engine, Docker CLI, Docker Desktop
Docker Engine은 이미지·컨테이너·네트워크·볼륨을 관리하는 실행 엔진으로, 요청을 받아 컨테이너를 만들고 프로그램을 실행·중지한다.
- Docker CLI: 터미널에서 쓰는 `docker` 명령줄 도구. 요청을 Engine에 전달하고 결과를 보여준다.
- Docker Desktop: 로컬 컴퓨터에서 Docker를 쓰도록 실행 환경과 관리 화면을 제공하는 앱. Engine, CLI, Compose 등을 함께 구성한다.

CLI와 Desktop 화면 모두 Engine에 요청을 보내고, Engine이 이미지·컨테이너·네트워크·볼륨을 다룬다(강의의 흐름도를 문장으로 옮김). CLI가 설치되어 있어도 Engine이 실행 중이 아니면 컨테이너를 실행할 수 없다.

## Docker Hub와 이미지 태그
Docker Hub는 이미지를 저장·배포하는 서버인 이미지 레지스트리 중 널리 쓰이는 서비스다. PostgreSQL, Python처럼 미리 준비된 이미지를 Docker Hub에서 내려받아 Docker Engine에서 컨테이너로 실행할 수 있다.

태그는 이미지에 붙인 이름표다(예: `postgres:17`의 `17`). 같은 태그가 업데이트된 이미지를 가리킬 수 있으므로, 태그가 같다고 이미지 내용이 영원히 같은 것은 아니다.

## Dockerfile과 Docker Compose의 차이
Dockerfile은 이미지를 만드는 방법을 적은 파일로, 기본 이미지·설치할 라이브러리·넣을 코드를 정의한다. 이 파일로 이미지를 만드는 과정을 빌드라고 한다. Docker Compose는 여러 컨테이너의 실행 설정(이미지, 환경변수, 네트워크, 데이터 저장 공간)을 `compose.yaml`에 정의해 함께 관리하는 도구다.
- Dockerfile: 이미지에 어떤 프로그램과 파일을 담을지 정의한다.
- Compose 파일: 어떤 컨테이너를 어떤 설정으로 실행하고 연결할지 정의한다.

FastAPI와 PostgreSQL을 함께 쓰면 두 컨테이너를 따로 두고 Compose로 함께 관리할 수 있다. Compose를 쓴다고 여러 컨테이너가 이미지 하나로 합쳐지지는 않는다.

## Docker Desktop 설치: Windows
Docker Desktop에는 Docker CLI와 Compose가 포함되어 있다. Windows에서는 공식 Docker Desktop Windows 설치 안내에 따라 CPU 종류에 맞는 설치 파일을 받고 시스템 요구 사항을 확인한다. 설치가 진행되지 않으면 WSL을 설치해야 한다. PowerShell을 관리자 권한으로 열고 실행한 뒤 Docker Desktop을 재설치한다.
```powershell
wsl --install
```
Docker Desktop 실행 후 안내가 나오면 다음 명령을 실행한다.
```powershell
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
```
- `wsl --install`: Windows용 리눅스 하위 시스템(WSL)을 설치한다.
- `Enable-WindowsOptionalFeature ... VirtualMachinePlatform`: 가상 머신 플랫폼 기능을 켠다. (내 메모: Docker Desktop의 WSL 2 백엔드에 필요한 기능)

## Docker Desktop 설치: macOS와 실행 확인
macOS에서 Homebrew가 설치되어 있다면 터미널에서 다음 명령으로 Docker Desktop을 설치한다.
```bash
brew install --cask docker-desktop
```
설치가 끝나면 Docker Desktop을 실행하고 Docker Engine이 완전히 시작될 때까지 기다린다. Engine이 실행 중이어야 컨테이너를 실행할 수 있다.

## 도커 기초 복습 Q&A
- Q. Docker 이미지와 Docker 컨테이너의 관계는?
  A. 이미지는 실행 파일과 설정의 묶음이고, 컨테이너는 그 이미지로 만든 격리된 실행 환경이다.
- Q. Docker 컨테이너를 삭제하면 컨테이너 안에 만든 파일은 어떻게 되나? 유지하려면?
  A. 삭제와 함께 사라진다. 유지하려면 볼륨에 저장하고 새 컨테이너에 같은 볼륨을 연결한다.
- Q. Python 가상환경과 Docker 컨테이너의 가장 큰 차이는?
  A. 가상환경은 Python 패키지만 분리하고, 컨테이너는 실행 파일·시스템 라이브러리까지 포함해 프로세스 실행 환경을 격리한다.
- Q. Dockerfile과 Docker Compose 파일은 각각 무엇을 정의하나?
  A. Dockerfile은 이미지에 담을 내용, Compose 파일은 어떤 컨테이너를 어떤 설정으로 실행·연결할지를 정의한다.
- Q. Docker CLI가 설치되어 있는데 컨테이너가 실행되지 않는다면 무엇을 확인하나?
  A. Docker Engine(Docker Desktop)이 실행 중인지 확인한다.
