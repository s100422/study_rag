---
part: web
lesson: HTML
order: 1
source_type: web
tags: [html, frontend, element, attribute, semantic-tag, form, devtools]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1316/
note: 개인 학습용 요약. 외부 공유 금지.
---

# HTML

## HTML 레슨 요약
프론트엔드를 구성하는 HTML·CSS·JavaScript의 역할과 웹 페이지가 표시되는 과정을 보고, HTML의 요소·속성·문서 구조·주요 태그와 브라우저 개발자 도구 사용법을 익힌다.

## 프론트엔드와 HTML·CSS·JavaScript의 역할
프론트엔드는 사용자가 브라우저에서 보고 조작하는 웹 애플리케이션 영역이다. 화면은 세 가지 언어가 나눠 맡는다.
- HTML: 제목, 이미지, 링크, 입력창 같은 내용과 구조
- CSS: 글자 색·크기, 여백, 배치 같은 스타일
- JavaScript: 클릭·입력 같은 동작 처리와 화면 내용 변경

```text
게시글 목록 화면
├── HTML       : 버튼, 게시글 목록
├── CSS        : 글자 색상, 게시글 사이의 간격, 목록의 배치
└── JavaScript : 버튼을 눌렀을 때 API에서 게시글 불러오기
```

## 웹 페이지 동작: 브라우저와 서버, 화면 표시 과정
브라우저는 웹 문서와 데이터를 받아 화면에 그리고 사용자 동작을 처리하는 프로그램이고, 서버는 요청을 받아 HTML·CSS·JavaScript·이미지·데이터를 응답한다. 둘은 주로 HTTP/HTTPS로 요청과 응답을 주고받는다.

화면 표시 순서는 다음과 같다.
- 브라우저가 HTML을 읽어 문서 구조를 만든다.
- CSS를 적용해 요소 모양과 배치를 정하고 화면에 그린다.
- JavaScript가 실행되면 문서 내용을 바꾸거나 추가 데이터를 요청할 수 있다.
- 파일 로딩과 코드 실행은 일부 겹쳐 진행될 수 있다.

## HTML이란: 하이퍼텍스트와 마크업 언어
HTML(HyperText Markup Language)에서 하이퍼텍스트는 링크로 다른 문서와 연결되는 텍스트이고, 마크업 언어는 태그로 문서의 내용과 구조를 표현하는 언어이다.

```html
<a href="https://www.python.org/">Python 공식 사이트</a>
```
- `<a>`: 링크 요소
- `href`: 이동할 주소
- `Python 공식 사이트`: 화면에 보이는 텍스트

(원문 코드의 URL이 `<https://...>`처럼 꺾쇠로 감싸져 있는데 페이지 변환 흔적으로 보여 꺾쇠를 뺐다.)

## HTML 요소(Element)의 구조
HTML 요소는 문서를 이루는 기본 단위로, 보통 시작 태그 + 내용 + 종료 태그로 되어 있고 시작 태그에 속성을 붙일 수 있다.

```html
<p class="title">HTML 기초</p>
```
- 태그: `<p>`, `</p>`가 단락의 시작과 끝
- 속성: `class="title"`로 title 클래스를 지정
- 내용: `HTML 기초`
- `<img>`, `<input>`, `<br>`처럼 종료 태그가 없는 요소도 있다.

## HTML 속성(Attribute)의 역할
HTML 속성은 요소에 추가 정보를 주거나 동작을 설정한다(링크 주소, 이미지 위치, 입력창 종류 등). 시작 태그 안에 `이름="값"`으로 쓰고, 여러 개면 공백으로 구분한다.

```html
<a href="https://www.python.org/" id="python-link">Python 공식 사이트</a>
```
- `href`: 속성 이름, `https://www.python.org/`: 속성 값. 클릭하면 이 주소로 이동한다.
- `id="python-link"`: 요소에 이름을 붙여 CSS·JavaScript에서 찾을 수 있게 한다.
- 같은 `<a>`라도 `href` 값이 다르면 이동 주소가 달라진다.

## HTML 문서 기본 구조
HTML 문서는 DOCTYPE 선언, `<html>`, `<head>`, `<body>`로 이루어진다.

```html
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>게시글 목록</title>
  </head>
  <body>
    <h1>게시글 목록</h1>
    <p>게시글을 확인하세요.</p>
  </body>
</html>
```
- `<!DOCTYPE html>`: 표준 모드로 해석하라는 선언
- `<html lang="ko">`: 루트 요소, 문서 언어는 한국어
- `<head>`: 인코딩, 제목, 스타일 연결 등 문서 정보
- `<meta charset="UTF-8">`: 문자 인코딩
- `<meta name="viewport" ...>`: 모바일 화면 너비와 초기 배율
- `<title>`: 브라우저 탭 제목
- `<body>`: 화면에 표시할 내용

## HTML 텍스트·영역 태그 (h1~h6, p, div, span, ul, li)
HTML의 기본 텍스트·영역 태그는 다음과 같다.
- `<h1>`~`<h6>`: 제목 계층. `<h1>`이 가장 높다.
- `<p>`: 단락
- `<div>`: 여러 요소를 한 영역으로 묶음
- `<span>`: 문장 일부를 묶음
- `<ul>`: 순서 없는 목록, `<li>`: 목록 항목
- 태그의 의미와 화면 모양은 별개다. 제목 글자 크기도 CSS로 바꿀 수 있다.

```html
<div class="post">
  <h2>HTML 기초</h2>
  <p>작성자 : <span class="author">학습자</span></p>
  <ul>
    <li>태그와 요소</li>
    <li>문서 구조</li>
  </ul>
</div>
```

## HTML 시맨틱 태그
HTML 시맨틱 태그는 영역의 의미를 드러내는 태그다.
- `<header>`: 페이지나 영역의 머리말
- `<nav>`: 메뉴·탐색 링크
- `<main>`: 주요 내용
- `<article>`: 독립적인 글·콘텐츠
- `<footer>`: 바닥글

```html
<header><h1>웹 학습 노트</h1></header>
<nav><a href="#html-note">HTML 기초</a></nav>
<main>
  <article id="html-note">
    <h2>HTML 기초</h2>
    <p>HTML은 웹 페이지의 내용과 구조를 나타낸다.</p>
  </article>
</main>
<footer>웹 기초 수업</footer>
```

## HTML 링크와 이미지 (a, img, href, src, alt)
HTML에서 `<a>`는 다른 페이지나 문서 내 위치로 가는 링크, `<img>`는 이미지 표시 태그다.
- `href`: 링크 목적지, `src`: 불러올 파일 주소, `alt`: 이미지 의미를 전하는 대체 텍스트

```html
<a href="https://www.python.org/about/">Python 소개</a>
<img src="https://www.python.org/static/img/python-logo.png" alt="Python 로고">
```

절대 주소는 `https://www.python.org/about/`처럼 전체 주소를 쓴다. 상대 주소는 기준 경로에 따라 달라진다. 기준 문서가 `https://example.com/docs/page.html`일 때:
- `/about/`: 사이트 최상위 기준 → `https://example.com/about/`
- `about/`: 현재 문서 경로 기준 → `https://example.com/docs/about/`

(원문 코드 URL의 꺾쇠 `<...>`는 변환 흔적으로 보고 뺐다.)

## HTML 입력창과 버튼 (form, input, label, button)
HTML 폼은 입력값을 서버로 보내는 구조다.
- `<form>`: 입력값을 `action` 주소로 전송
- `<input>`: 사용자 입력, `placeholder`는 비어 있을 때 안내 문구
- `<label>`: 입력 요소 이름. `for` 값을 입력 요소 `id`와 맞춰 연결
- `<button>`: 클릭 버튼

```html
<form action="https://www.python.org/search/" method="get">
  <label for="search">검색어</label>
  <input id="search" name="q" type="text" placeholder="검색어를 입력하세요">
  <button type="submit">검색</button>
</form>
```
- `name="q"`: 서버로 보낼 데이터의 키
- `method="get"`: 입력값을 URL에 붙여 보냄. `python`을 검색하면 `https://www.python.org/search/?q=python`으로 요청한다.

## HTML id 속성과 class 속성
HTML `id` 속성은 요소에 고유 식별자를 준다. 한 문서 안에서 중복되면 안 되며 CSS·JavaScript에서 특정 요소를 찾을 때 쓴다.

```html
<h1 id="page-title">게시글 목록</h1>
```

HTML `class` 속성은 여러 요소에 공통 이름을 준다. 같은 클래스를 여러 요소에 줄 수 있고, 한 요소에 여러 클래스를 공백으로 구분해 줄 수 있다.

```html
<p class="title">HTML 기초</p>
<p class="title featured">CSS 선택자</p>
```
- 두 요소 모두 `title` 클래스, 두 번째는 `featured`도 가진다.
- 클래스 이름만으로 모양이 바뀌지 않는다. 그 클래스에 적용할 CSS가 있어야 한다.

## HTML 요소 중첩: 부모·자식·형제·자손
HTML 요소 안에 요소를 넣어 구조를 만든다. 바로 바깥은 부모, 바로 안쪽은 자식, 같은 부모를 둔 요소끼리는 형제, 안쪽의 모든 단계 요소는 자손이다.

```html
<ul id="post-list">
  <li id="post-1" class="post">
    <a class="title featured" href="#post-1">HTML 기초</a>
    <div class="details">
      <p class="body">HTML은 웹 페이지의 내용과 구조를 나타낸다.</p>
    </div>
  </li>
  <li id="post-2" class="post">
    <a class="title" href="#post-2">CSS 선택자</a>
    <div class="details">
      <p class="body">CSS 선택자로 스타일을 적용할 요소를 찾는다.</p>
    </div>
  </li>
</ul>
```
- `<ul>`의 자식은 `<li>` 두 개, 각 `<li>`의 자식은 `<a>`와 `<div>`
- `<p>`는 `<div>`의 자식이자 `<li>`의 자손
- 반복 게시글은 같은 구조·클래스에 제목과 본문만 다르다.
- `href="#post-1"`: 같은 문서의 `id="post-1"` 위치로 이동

## HTML 주석
HTML 주석은 `<!-- 내용 -->` 형태로 쓴다. 화면에는 안 보이지만 HTML 소스와 개발자 도구에서는 보인다.

```html
<!-- 게시글 목록 영역 -->
<ul id="post-list"></ul>
```

## 브라우저 개발자 도구 (Elements, Console)
브라우저 개발자 도구는 페이지의 HTML, 스타일, 네트워크 등을 분석하는 브라우저 내장 도구다. `F12` 또는 `Ctrl + Shift + I`로 연다.
- Elements(요소) 메뉴: HTML 구조와 CSS를 실시간으로 보고 수정한다. 왼쪽 위의 요소 선택 버튼으로 화면의 특정 요소를 고를 수 있다. (이 부분 설명은 강의에서 이미지로만 보여 줘서 화면 모습은 노트에 없다.)
- Console(콘솔) 메뉴: JavaScript 코드를 실행해 결과를 보고, 오류·경고를 확인해 버그를 추적한다.

## HTML 복습 Q&A
- Q. 프론트엔드에서 HTML, CSS, JavaScript는 각각 무엇을 맡나?
  A. HTML은 내용과 구조, CSS는 스타일, JavaScript는 동작 처리와 화면 내용 변경이다.
- Q. HTML의 id와 class 속성의 차이는?
  A. id는 문서 안에서 하나뿐인 고유 식별자이고, class는 여러 요소에 공통으로 붙이며 한 요소에 여러 개 줄 수 있다.
- Q. 기준 문서가 `https://example.com/docs/page.html`일 때 HTML 상대 주소 `about/`은 어디로 해석되나?
  A. `https://example.com/docs/about/`이다. `/about/`이면 `https://example.com/about/`이다.
- Q. HTML 폼에서 `method="get"`과 `name="q"`는 어떤 역할을 하나?
  A. 입력값을 URL 쿼리에 붙여 보내며, `q`가 그 값의 키가 된다(예: `?q=python`).
- Q. 브라우저 개발자 도구를 여는 단축키는?
  A. `F12` 또는 `Ctrl + Shift + I`이다.
