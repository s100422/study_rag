---
part: web
lesson: Crawling
order: 5
source_type: web
tags: [crawling, scraping, requests, beautifulsoup, playwright, robots-txt, rate-limit]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1317/
note: 개인 학습용 요약. 외부 공유 금지.
---

# Crawling

## 크롤링 레슨 요약
크롤링과 스크래핑의 차이, 데이터 위치에 따른 수집 방식(API, requests+BeautifulSoup, Playwright, AI 브라우저 제어) 선택, 수집 전 확인 사항(이용 조건, robots.txt, 요청 간격, 429 재시도)을 정리한다.

## 크롤링과 스크래핑의 차이
웹 데이터 수집은 페이지를 찾아 이동하는 과정과 값을 뽑는 과정으로 나눌 수 있다.
- 크롤링(Crawling): URL을 방문하고 링크를 따라 수집 대상을 탐색한다. 예: 게시글 목록의 다음 페이지를 차례로 방문
- 스크래핑(Scraping): 문서에서 필요한 항목을 추출해 구조화한다. 예: 각 게시글의 제목과 링크를 딕셔너리로 만들기

한 프로그램이 두 작업을 같이 할 수 있다. 게시글 목록 여러 페이지를 돌면서 각 페이지의 제목과 링크를 뽑는 경우가 그렇다.

## 크롤링 수집 방식 선택: API, requests, Playwright
크롤링 수집 방식은 데이터가 어디에 있는지로 고른다. 먼저 공식 API가 있는지 확인한다.
- 공식 API가 데이터를 준다 → API를 호출해 JSON 같은 구조화된 응답에서 값을 읽는다.
- 응답 HTML에 데이터가 있다 → requests로 HTML을 받고 BeautifulSoup으로 요소를 찾아 추출한다.
- 클릭·스크롤이나 JavaScript 실행 후에 데이터가 보인다 → Playwright로 브라우저를 제어하고, 내용이 표시된 뒤 현재 DOM에서 추출한다.

도구 특징:
- requests: HTTP 요청·응답만 처리하고 페이지의 JavaScript는 실행하지 않는다.
- BeautifulSoup: 받은 HTML을 분석해 CSS 선택자 등으로 요소를 찾는다.
- Playwright: 브라우저를 조작해 이동·클릭·입력을 하고 화면에 반영된 내용을 읽는다.

브라우저 화면에 보이는 데이터가 처음 받은 HTML에는 없을 수 있다. 그때는 데이터를 주는 API나 브라우저 기반 수집을 살펴본다.

## AI 브라우저 제어를 이용한 크롤링
AI에 브라우저 제어 도구(Browser Use, Playwright MCP 등)를 연결하면 AI가 페이지 이동, 클릭, 스크롤을 하며 데이터를 모을 수 있다.
- "월요일 웹툰 목록을 열고 제목과 링크를 수집해 줘"처럼 목표와 수집 항목을 전달한다.
- 일반 Playwright 코드는 미리 정한 동작 순서와 추출 규칙대로 실행되고, AI 브라우저 제어는 AI가 화면·페이지 구조를 보며 다음 동작을 정한다.
- 소규모 탐색에는 쓸 만하지만 AI 판단에 시간과 비용이 들고, 결과의 누락·오류를 검증해야 한다.
- 대량·반복 수집에는 검증된 코드나 공식 API가 더 적합하다.

## 크롤링 전에 확인할 사항
크롤링을 시작하기 전에 다음을 확인한다.
- 사이트 이용 조건과 robots.txt를 확인한다.
- 페이지를 열 수 있다고 해서 수집한 내용의 재사용·재배포까지 허용된 것은 아니다.
- 필요한 범위만 수집한다.

## robots.txt란: User-agent, Disallow, Allow
robots.txt는 사이트 운영자가 크롤러에게 접근 경로 규칙을 알리는 파일로, 사이트 최상위 경로 `/robots.txt`에 있다.
- `User-agent`: 규칙을 적용할 크롤러. 맞는 그룹이 없으면 `*` 그룹을 본다.
- `Disallow`: 접근을 제한하는 경로. `/`면 전체 제한
- `Allow`: 접근을 허용하는 경로. 제한 규칙과 겹치면 더 구체적인 경로 규칙이 적용된다.

(내 메모) 예시 형태:
```text
User-agent: *
Disallow: /admin/
Allow: /admin/public/
```
- 모든 크롤러에게 `/admin/`은 막고 그 안의 `/admin/public/`만 허용한다는 뜻이다.

## 크롤링 요청 간격과 429 재시도 처리
크롤링할 때는 서버에 부담을 주지 않도록 요청 사이에 대기 시간을 둔다. 간격은 사이트가 안내하는 호출 제한에 맞추고, 동시에 여러 요청을 보내면 동시 요청 수도 제한한다.
- `429 Too Many Requests`: 일정 시간 동안 요청이 너무 많았다는 응답이다. 잠시 멈추고 서버 안내를 확인한다.
- `Retry-After` 응답 헤더: 다음 요청까지 기다릴 시간. `Retry-After: 60`이면 최소 60초 기다린다. 초 대신 재요청 가능한 날짜·시각이 올 수도 있다.
- 429에 `Retry-After`가 없으면 대기 시간을 점점 늘린다. 재시도 횟수에 상한을 두고, 제한이 반복되면 수집을 멈춘다.

## 크롤링 재시도 예시 코드 (내 메모)
(내 메모) 강의에는 코드가 없다. 요청 간격과 429 처리 규칙을 requests로 옮겨 본 예시다.
```python
import time
import requests

def get_with_retry(url, max_retries=3, delay=1.0):
    wait = 5
    for _ in range(max_retries + 1):
        res = requests.get(url, timeout=10)
        if res.status_code != 429:
            time.sleep(delay)  # 다음 요청 전 간격
            return res
        ra = res.headers.get("Retry-After")
        # Retry-After가 날짜 형식이면 isdigit()이 False라 기본 대기 사용
        time.sleep(int(ra) if ra and ra.isdigit() else wait)
        wait *= 2  # Retry-After 없으면 대기 시간 늘리기
    raise RuntimeError("429가 반복되어 수집 중단")
```

## Crawling 복습 Q&A
- Q. 크롤링과 스크래핑의 차이는?
  A. 크롤링은 URL을 방문하고 링크를 따라 대상을 탐색하는 것, 스크래핑은 문서에서 필요한 값을 추출해 구조화하는 것이다.
- Q. 크롤링에서 requests+BeautifulSoup 대신 Playwright를 써야 하는 경우는?
  A. 클릭·스크롤이나 JavaScript 실행 후에야 데이터가 표시되는 경우다. requests는 JavaScript를 실행하지 않는다.
- Q. robots.txt에서 Disallow와 Allow 규칙이 겹치면?
  A. 더 구체적인 경로 규칙이 적용된다.
- Q. 크롤링 중 429 응답에 `Retry-After: 60`이 오면?
  A. 최소 60초 기다린 뒤 다시 요청한다. 헤더가 없으면 대기 시간을 늘리고, 재시도 횟수에 상한을 둔다.
- Q. 크롤링 방식을 고를 때 가장 먼저 확인할 것은?
  A. 필요한 데이터를 주는 공식 API가 있는지다.
