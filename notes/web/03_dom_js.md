---
part: web
lesson: DOM과 JavaScript
order: 3
source_type: web
tags: [dom, javascript, queryselector, textcontent, fetch, json, api]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1314/
note: 개인 학습용 요약. 외부 공유 금지.
---

# DOM과 JavaScript

## DOM과 JavaScript 요약
브라우저가 HTML을 DOM 트리로 만드는 원리를 보고, 개발자 도구 Console에서 JavaScript로 요소를 찾고 바꾸며, `fetch()`로 API JSON을 받아 화면에 표시하는 흐름을 익힌다.

## DOM(Document Object Model)이란
DOM은 브라우저가 HTML을 읽어 문서를 트리 구조의 객체로 표현한 것이다. JavaScript는 DOM을 통해 요소의 내용·속성·구조를 읽거나 바꾼다.

```html
<li id="post-1" class="post">
  <a class="title" href="#post-1">HTML 기초</a>
  <div class="details">
    <p class="body">HTML은 웹 페이지의 내용과 구조를 나타낸다.</p>
  </div>
</li>
```

```text
li#post-1.post
├── a.title
│   └── "HTML 기초"
└── div.details
    └── p.body
        └── "HTML은 웹 페이지의 내용과 구조를 나타낸다."
```
- 텍스트도 DOM 트리의 한 노드로 들어간다.

## 웹 페이지에서 JavaScript의 역할
웹 페이지에서 JavaScript는 세 가지 일을 한다.
- 버튼 클릭, 입력, 스크롤 같은 이벤트를 처리한다.
- DOM에 요소를 추가하거나 기존 요소의 내용·속성을 바꾼다.
- 서버에 데이터를 요청하고, 받은 내용을 화면에 반영한다.

## JavaScript 실습 1단계: 선택자로 DOM 요소 찾기
게시글 페이지를 열고 개발자 도구 Console에서 CSS 선택자로 DOM 요소를 찾는다.

```javascript
document.querySelector(".title");
document.querySelectorAll(".post").length;
document.querySelector("#post-1 .title").textContent;
```
- `document`: 현재 웹 문서 객체
- `querySelector()`: 선택자에 맞는 첫 요소. 없으면 `null`
- `querySelectorAll()`: 맞는 요소 전부. `.length`로 개수 확인, 없으면 빈 목록이라 `.length`는 0
- `textContent`: 요소 안 텍스트를 읽거나 바꾸는 속성
- 새로고침 직후 결과는 첫 제목 요소, `2`, `"HTML 기초"`이다.

## JavaScript 실습 2단계: textContent로 내용 변경
JavaScript로 DOM 요소의 `textContent`에 새 값을 대입하면 화면의 글자도 바로 바뀐다.

```javascript
document.querySelector("#post-1 .title").textContent = "JavaScript로 바꾼 제목";
```
- 첫 게시글 제목이 "JavaScript로 바꾼 제목"으로 바뀐다. 새로고침하면 원래대로 돌아온다(내 메모).

## JavaScript 실습 3단계: fetch로 API 요청과 JSON 응답 받기
JavaScript `fetch()`로 JSONPlaceholder 게시글 API에 GET 요청을 보내면 게시글 배열을 받는다. Console에서 한 줄씩 실행한다.

```javascript
const response = await fetch("https://jsonplaceholder.typicode.com/posts");
const posts = await response.json();
posts[0];
```
- `fetch()`: 지정한 주소로 요청을 보낸다.
- `await`: 작업이 끝날 때까지 기다렸다가 결과를 쓴다.
- `response.json()`: 응답 본문을 JavaScript 배열·객체로 읽는다.
- `posts[0]`: 첫 게시글. `id`, `userId`, `title`, `body`가 있다.

(원문 코드의 URL이 `<https://...>`처럼 꺾쇠로 감싸져 있는데 변환 흔적으로 보고 뺐다.)

## JavaScript 실습 4단계: API 응답을 화면에 표시하기
게시글 불러오기 버튼을 누르면 JavaScript가 API를 요청하고, 응답 배열의 앞 3개로 목록을 바꾼다. `title`은 제목, `body`는 본문 자리에 넣는다.

```text
게시글 불러오기 클릭
          ↓
GET https://jsonplaceholder.typicode.com/posts
          ↓
JSON 배열 응답
          ↓
JavaScript가 제목과 본문을 DOM에 추가
          ↓
게시글 목록 표시
```
- 개발자 도구 Network 탭에서 API 요청과 JSON 응답을 확인할 수 있다.
- 강의 본문에는 버튼 동작을 구현한 JavaScript 코드가 텍스트로 나오지 않는다(흐름도만 있음).

## DOM과 JavaScript 복습 Q&A
- Q. DOM이란 무엇인가?
  A. 브라우저가 HTML을 읽어 트리 구조 객체로 표현한 것으로, JavaScript가 이를 통해 요소를 읽고 바꾼다.
- Q. JavaScript `querySelector()`와 `querySelectorAll()`의 차이는?
  A. `querySelector()`는 첫 요소 하나(없으면 null), `querySelectorAll()`은 맞는 요소 전부(없으면 빈 목록)를 반환한다.
- Q. JavaScript로 요소 글자를 바꾸려면?
  A. 요소를 찾아 `textContent`에 새 문자열을 대입한다.
- Q. JavaScript `fetch()` 응답을 배열·객체로 바꾸는 코드는?
  A. `const posts = await response.json();`
