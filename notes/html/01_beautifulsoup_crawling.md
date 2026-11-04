---
part: html
lesson: BeautifulSoup Crawling
order: 1
source_type: ipynb
tags: [crawling, beautifulsoup, requests, css-selector, urljoin, csv, json]
source: C:\Users\tnwls\aim-ai-agent\html\01-beautifulsoup-crawling.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# BeautifulSoup Crawling

## BeautifulSoup Crawling 요약
`requests`로 Google 뉴스 HTML을 받아 BeautifulSoup의 CSS 선택자로 기사 제목과 링크를 뽑고, 상대 주소를 절대 주소로 바꾼 뒤 CSV와 JSON 파일로 저장한다.

## requests와 BeautifulSoup의 역할
BeautifulSoup 크롤링은 두 단계로 나뉜다. HTML을 요청하는 일과 HTML에서 필요한 요소를 찾는 일이다.
- `requests`: 서버에 HTTP 요청을 보내고 응답을 받는다.
- `BeautifulSoup`: 받은 HTML을 분석해 태그·속성·텍스트를 찾는다.
```text
URL → requests → HTML → BeautifulSoup → 기사 제목과 링크
```
BeautifulSoup은 전달받은 HTML만 분석하며, 직접 사이트에 접속하거나 JavaScript를 실행하지 않는다. 설치는 `pip install requests beautifulsoup4`.

## BeautifulSoup 크롤링 실습 1단계: HTML 요청과 파싱
BeautifulSoup 크롤링은 먼저 `requests.get()`으로 페이지를 받고, 응답 문자열을 BeautifulSoup에 넘겨 파싱한다. 파싱은 문자열을 다룰 수 있는 구조로 바꾸는 작업이다.
```python
URL = "https://news.google.com/topics/<토픽ID>?hl=ko&gl=KR&ceid=KR%3Ako"
response = requests.get(URL, timeout=15)
response.raise_for_status()
print("상태 코드:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")
print(soup.title)
```
- `timeout=15`: 연결·수신 대기 시간을 제한한다.
- `raise_for_status()`: HTTP 오류면 예외를 낸다.
- `response.text`: 응답 본문 문자열(이 페이지는 약 320만 자). `status_code`는 200.
- `"html.parser"`: Python 내장 HTML 파서.
- URL의 긴 토픽 ID는 `<토픽ID>`로 줄여 적었다.

## BeautifulSoup CSS 선택자로 요소 찾기
BeautifulSoup에서 찾을 요소는 브라우저에서 기사 제목을 우클릭 → 검사로 열어 태그, `class`, `href`를 확인한 뒤 CSS 선택자로 지정한다.
- `a`: 모든 a 태그
- `.gPFEn`: `gPFEn` 클래스를 가진 요소
- `a.gPFEn`: `gPFEn` 클래스를 가진 a 태그

```python
articles = soup.select("a.gPFEn")
if not articles:
    raise ValueError("기사를 찾지 못했습니다. 응답 HTML과 선택자를 확인하세요.")
first_article = soup.select_one("a.gPFEn")
```
- `select()`: 맞는 태그 전부를 리스트로. 없으면 빈 리스트.
- `select_one()`: 첫 번째 태그 하나. 없으면 `None`.
- 사이트 구조가 바뀌면 선택자도 현재 HTML에 맞게 고쳐야 한다.

## BeautifulSoup 태그에서 텍스트와 속성 읽기
BeautifulSoup으로 찾은 태그에서는 텍스트와 속성값을 꺼낸다.
```python
for article in articles:
    title = article.get_text(strip=True)
    link = article["href"]
    print(f"제목: {title}")
    print(f"링크: {link}")
```
- `get_text(strip=True)`: 태그 안 텍스트를 읽고 양끝 공백을 제거한다.
- `["href"]`: href 속성값. 속성이 없으면 KeyError.
- `get("href")`: 속성이 없으면 오류 대신 `None`.
- 출력: 기사 제목(뉴스 헤드라인)과 `./read/...` 형태의 상대 링크가 기사마다 출력된다.

## 상대 주소를 절대 주소로 바꾸기: urljoin
크롤링한 `./read/...` 링크는 기준 URL에 따라 완성되는 상대 주소다. 절대 주소는 `https://news.google.com/read/...`처럼 사이트 주소까지 포함한다.
```python
BASE_URL = urljoin(response.url, "/")      # https://news.google.com/
absolute_url = urljoin(BASE_URL, articles[0]["href"])
```
- `response.url`: 리다이렉트까지 반영된 최종 응답 주소.
- `urljoin(response.url, "/")`: 경로와 쿼리를 떼고 사이트 루트만 남긴다.
- `urljoin(BASE_URL, link)`: 상대 주소를 절대 주소로 바꾸고, 이미 절대 주소면 그대로 둔다.

## BeautifulSoup 크롤링 실습 2단계: 결과를 딕셔너리 리스트로 정리
BeautifulSoup 크롤링 결과는 기사마다 `title`, `url` 딕셔너리로 만들어 리스트에 담는다. 제목이나 링크가 비어 있는 요소는 건너뛴다.
```python
news_rows = []
for article in articles:
    title = article.get_text(strip=True)
    href = article.get("href")
    if not title or not href:
        continue
    news_rows.append({"title": title, "url": urljoin(BASE_URL, href)})
print("수집 개수:", len(news_rows))
```
- `get("href")`를 써서 href 없는 태그도 오류 없이 걸러낸다.
- 결과: 248개 수집. 각 항목은 제목과 `https://news.google.com/read/...` 절대 URL이다.

## BeautifulSoup 크롤링 실습 3단계: CSV와 JSON으로 저장
BeautifulSoup 크롤링 결과는 작업 폴더 아래 `crawling_output`에 CSV와 JSON으로 저장한다. 같은 이름 파일은 덮어쓴다.
```python
output_dir = Path.cwd() / "crawling_output"
output_dir.mkdir(exist_ok=True)

with (output_dir / "google_news.csv").open("w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=["title", "url"])
    writer.writeheader()
    writer.writerows(news_rows)

(output_dir / "google_news.json").write_text(
    json.dumps(news_rows, ensure_ascii=False, indent=2), encoding="utf-8")
```
- `DictWriter(fieldnames=...)`: 열 이름과 순서를 정한다.
- `utf-8-sig`: Excel에서 한글이 깨지지 않게 BOM을 붙인다.
- `ensure_ascii=False`: 한글을 그대로 기록. `indent=2`: 들여쓰기.
- 두 셀을 하나로 합쳐 적었다(축약).

## requests 응답 HTML과 브라우저 화면의 차이
requests로 받은 HTML에는 브라우저가 JavaScript를 실행한 뒤 바뀐 화면 내용이 들어 있지 않다. 브라우저에서는 보이는데 BeautifulSoup으로 못 찾는다면, 먼저 `response.text`에 그 데이터가 있는지 확인한다. JavaScript 실행 후에 나타나는 데이터는 Playwright로 브라우저를 제어해서 읽는다.

## BeautifulSoup Crawling 복습 Q&A
- Q. BeautifulSoup은 웹 페이지에 직접 접속하나?
  A. 아니다. `requests` 등이 받아 온 HTML 문자열을 분석만 하며 JavaScript도 실행하지 않는다.
- Q. BeautifulSoup의 `select()`와 `select_one()` 차이는?
  A. `select()`는 일치하는 모든 태그 리스트(없으면 빈 리스트), `select_one()`은 첫 태그 하나(없으면 None)를 반환한다.
- Q. 태그 속성을 읽을 때 `tag["href"]` 대신 `tag.get("href")`를 쓰는 이유는?
  A. 속성이 없을 때 오류 대신 `None`을 돌려줘 안전하게 걸러낼 수 있다.
- Q. 크롤링한 상대 주소 `./read/...`를 절대 주소로 바꾸는 방법은?
  A. `BASE_URL = urljoin(response.url, "/")`로 루트를 구하고 `urljoin(BASE_URL, link)`를 쓴다.
- Q. CSV 저장 시 `encoding="utf-8-sig"`를 쓰는 이유는?
  A. Excel에서 열 때 한글이 깨지지 않게 하기 위해서다.
