---
part: html
lesson: Playwright Crawling
order: 2
source_type: ipynb
tags: [crawling, playwright, chromium, locator, wait-for, headless, dom]
source: C:\Users\tnwls\aim-ai-agent\html\02-playwright-crawling.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Playwright Crawling

## Playwright Crawling 요약
Playwright로 Chromium 브라우저를 코드로 열어 네이버 웹툰 요일 목록 페이지에 접속하고, JavaScript가 그린 웹툰 제목이 나타날 때까지 기다린 뒤 제목을 수집한다. 노트북은 별도 실행 파일의 코드를 부분별로 설명한다.
```text
브라우저 실행 → 페이지 이동 → 제목 요소 대기 → 3초간 화면 확인 → 제목 수집 → 브라우저 종료
```

## Playwright란
Playwright는 브라우저를 코드로 제어하는 라이브러리다. `requests`+BeautifulSoup은 서버가 준 초기 HTML만 보지만, Playwright는 실제 브라우저에서 페이지를 열기 때문에 JavaScript 실행 결과가 반영된 DOM에서 데이터를 읽을 수 있다.

## Playwright 실습 준비: 설치와 실행 파일
Playwright 패키지와 Chromium 브라우저를 설치한다.
```bash
pip install playwright
python -m playwright install chromium
python html_crwaling/09-playwright-crawling.py
```
- 실행 코드는 `09-playwright-crawling.py`에 있고, 프로젝트 최상위 폴더에서 실행한다. (실행 경로의 폴더명이 `html_crwaling`으로 적혀 있는데, 실제 폴더명 오타일 수 있으니 확인 필요)
- 실행하면 브라우저가 열리고 제목이 나타난 뒤 3초간 화면을 보여 주고, 터미널에 웹툰 제목을 출력하고 종료한다.

## Playwright 실습 1단계: 브라우저 실행과 페이지 이동
Playwright 동기 API로 Chromium을 띄우고 `new_page()`로 탭을 만든 뒤 `page.goto()`로 이동한다.
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False)
    page = browser.new_page()
    URL = "https://comic.naver.com/webtoon?tab=mon"
    response = page.goto(URL, wait_until="domcontentloaded")
```
- `headless=False`: 브라우저 창을 띄운다. `True`면 창 없이 실행되어 화면 없는 서버에서 쓸 수 있다.
- `wait_until="domcontentloaded"`: 초기 HTML 문서가 준비될 때까지만 기다린다. JavaScript가 나중에 그리는 제목은 따로 기다려야 한다.
- 두 코드 조각을 하나로 이어 적었다(축약).

## Playwright Locator로 요소 지정하기
Playwright Locator는 페이지에서 특정 요소를 찾는 객체로, `page.locator()`에 CSS 선택자를 넘겨 만든다. 개발자 도구로 웹툰 제목을 검사해 클래스 이름을 확인한다.
```python
TITLE_SELECTOR = ".ContentTitle__title--e3qXt"
title_locator = page.locator(TITLE_SELECTOR)
```
- Locator를 만드는 것만으로는 요소가 나타날 때까지 기다리지 않는다. "무엇을 찾을지"만 정한다.
- 이런 해시가 붙은 클래스명은 사이트 배포 때 바뀔 수 있으므로, 구조가 바뀌면 현재 DOM에 맞게 선택자를 고친다.

## Playwright 요소 대기: wait_for
Playwright에서 페이지 이동이 끝났다고 데이터가 준비된 것은 아니다. 초기 HTML 뒤에 JavaScript가 서버에서 데이터를 받아 화면에 추가할 수 있어서, 바로 읽으면 빈 결과가 나올 수 있다. 그래서 수집할 요소가 보일 때까지 기다린다.
```python
title_locator.first.wait_for(state="visible", timeout=15000)
page.wait_for_timeout(3000)
```
- `first.wait_for(state="visible")`: 첫 번째 제목이 화면에 보일 때까지 기다린다.
- `timeout=15000`: 최대 15초(밀리초 단위). 먼저 나타나면 바로 진행하고, 시간 안에 안 나타나면 오류가 난다.
- `wait_for_timeout(3000)`: 수업 중 화면을 보려고 3초 더 멈추는 고정 대기. 수집 자체에는 필요 없다.

## Playwright 실습 2단계: 제목 수집과 브라우저 종료
Playwright에서 `all()`로 선택자에 맞는 Locator 목록을 얻고 `text_content()`로 텍스트를 읽는다.
```python
for title in title_locator.all():
    text = title.text_content()
    if text and text.strip():
        print(text.strip())

browser.close()
```
- `all()`은 기다리지 않고 현재 DOM에 있는 요소만 돌려준다. 첫 제목 대기 후에 호출해야 하고, 스크롤 등으로 추가 로딩되는 목록은 별도 대기 조건이 필요하다.
- 빈 텍스트는 건너뛴다.
- 실행 파일에서는 수집 코드를 `try`에 두고 `finally`에서 `browser.close()`를 호출해 오류가 나도 브라우저를 닫는다. `with` 블록이 끝나면 Playwright도 종료된다.

## Playwright 웹툰 제목 크롤링 전체 코드 (내 메모)
Playwright 웹툰 제목 크롤링의 조각들을 노트북 설명(try/finally로 종료)에 맞춰 한 파일로 이어 붙인 것이다(내 메모). 실제 `09-playwright-crawling.py` 원본은 노트북에 없다.
```python
from playwright.sync_api import sync_playwright

URL = "https://comic.naver.com/webtoon?tab=mon"
TITLE_SELECTOR = ".ContentTitle__title--e3qXt"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False)
    try:
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        title_locator = page.locator(TITLE_SELECTOR)
        title_locator.first.wait_for(state="visible", timeout=15000)
        page.wait_for_timeout(3000)
        for title in title_locator.all():
            text = title.text_content()
            if text and text.strip():
                print(text.strip())
    finally:
        browser.close()
```

## Playwright Crawling 복습 Q&A
- Q. requests+BeautifulSoup 대신 Playwright를 쓰는 경우는?
  A. 데이터가 JavaScript 실행 후에 화면에 나타나서 초기 HTML(`response.text`)에 없을 때다.
- Q. Playwright `goto(..., wait_until="domcontentloaded")` 후 바로 제목을 읽으면 안 되는 이유는?
  A. 초기 HTML만 준비된 상태라 JavaScript가 나중에 추가하는 제목이 아직 없을 수 있다. `wait_for`로 요소를 기다려야 한다.
- Q. Playwright `page.locator()`를 만들면 요소를 기다리나?
  A. 아니다. 찾을 대상만 지정한다. 대기는 `locator.first.wait_for(state="visible")` 같은 호출로 한다.
- Q. Playwright Locator의 `all()`은 요소가 나타날 때까지 기다리나?
  A. 아니다. 현재 DOM에 있는 요소만 반환하므로 먼저 대기한 뒤 호출한다.
- Q. Playwright `headless=True`와 `False`의 차이는?
  A. `False`는 브라우저 창을 띄우고, `True`는 창 없이 실행해 화면 없는 서버에서도 쓸 수 있다.
