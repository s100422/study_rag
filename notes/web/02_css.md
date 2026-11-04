---
part: web
lesson: CSS
order: 2
source_type: web
tags: [css, selector, box-model, descendant-selector, stylesheet, css-diner]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1315/
note: 개인 학습용 요약. 외부 공유 금지.
---

# CSS

## CSS 레슨 요약
CSS의 기본 문법, 색상·여백과 박스 모델, 태그·클래스·아이디·속성 선택자, 자손·자식 선택자, HTML에 CSS를 적용하는 세 가지 방법을 익히고 CSS Diner로 선택자를 연습한다.

## CSS란
CSS(Cascading Style Sheets)는 HTML 요소의 색상, 글자 크기, 여백, 배치를 지정하는 스타일 언어다. 선택자로 대상 요소를 고르고, 속성과 값으로 스타일을 정한다.

## CSS 기본 문법: 선택자, 속성, 값
CSS 규칙은 `선택자 { 속성: 값; }` 형태다.

```css
.body {
  color: blue;
  font-size: 20px;
}
```
- `.body`: 선택자. `body` 클래스를 가진 요소를 고른다.
- `{ }`: 그 요소에 적용할 스타일을 쓴다.
- `color`, `font-size`는 속성, `blue`, `20px`는 값이다.
- 속성과 값은 `:`로 나누고, 선언마다 `;`로 끝낸다.
- HTML의 `class="body"`는 HTML 속성이고, `color`·`font-size`는 CSS 속성이다.

## CSS 색상과 여백, 박스 모델
CSS로 배경색, 테두리, 안쪽·바깥쪽 여백을 지정할 수 있다.

```css
.post {
  background-color: #f5f5f5;
  border: 1px solid #cccccc;
  padding: 16px;
  margin: 12px;
}
```
- `background-color`: 배경색
- `border`: 테두리
- `padding`: 내용과 테두리 사이 안쪽 여백
- `margin`: 테두리 바깥 여백
- 요소 영역을 내용 → 안쪽 여백 → 테두리 → 바깥 여백으로 나눠 보는 방식을 박스 모델(Box Model)이라 한다.

## CSS 기본 선택자: 태그·클래스·아이디·속성
CSS 기본 선택자는 네 가지다.
- 태그 선택자: `a`는 모든 `<a>`
- 클래스 선택자: `.body`는 body 클래스 요소
- 아이디 선택자: `#post-list`는 그 id를 가진 요소
- 속성 선택자: `button[type="button"]`은 type이 button인 `<button>`

```css
a {
  color: navy;
}

.body {
  font-weight: bold;
}

#post-list {
  padding: 16px;
}

button[type="button"] {
  border: 1px solid gray;
}

.title.featured {
  color: #b42318;
}
```
- `.title.featured`: 클래스 선택자를 공백 없이 이어 쓰면 두 클래스를 모두 가진 요소를 고른다.

(내 메모: 원문에서는 `.title.featured` 예시가 별도 코드 블록이었는데 한 블록으로 합쳤다.)

## CSS 자손 선택자와 자식 선택자
CSS 자손 선택자는 공백으로 이어 안쪽 모든 단계에서 고르고, 자식 선택자는 `>`로 이어 바로 아래 단계에서만 고른다. 게시글 하나의 구조는 다음과 같다.

```html
<li id="post-1" class="post">
  <a class="title" href="#post-1">HTML 기초</a>
  <div class="details">
    <p class="body">HTML은 웹 페이지의 내용과 구조를 나타낸다.</p>
  </div>
</li>
```

```text
li.post
├── a.title
└── div.details
    └── p.body
```

```css
.post .body {
  color: blue;
}

.post > .title {
  font-weight: bold;
}
```
- `.post .body`: 게시글 안의 본문을 고른다(`.details` 안에 있어도 됨).
- `.post > .title`: 게시글 바로 아래 제목 링크를 고른다.
- `.post > .body`는 아무것도 고르지 못한다. 본문이 `.details` 안에 있어 직계 자식이 아니기 때문이다.

## CSS 적용 방법: 인라인, 내부, 외부 스타일
HTML에 CSS를 적용하는 방법은 세 가지다.

인라인 스타일: 요소의 `style` 속성에 직접 쓴다.
```html
<p style="color: blue;">HTML은 웹 페이지의 내용과 구조를 나타낸다.</p>
```

내부 스타일: `<head>` 안의 `<style>`에 쓴다.
```html
<style>
  .body {
    color: blue;
  }
</style>
```

외부 스타일: 별도 CSS 파일을 `<head>` 안의 `<link>`로 연결한다.
```html
<link rel="stylesheet" href="posts.css">
```
- 강의 공통 예제는 외부 스타일을 써서 `posts.html`이 `posts.css`를 연결한다.

## CSS 선택자 실습: CSS Diner
CSS Diner는 접시와 음식을 고르며 CSS 선택자를 연습하는 웹 게임이다.
- 문제가 요구하는 대상과 HTML Viewer의 HTML 구조를 확인한다.
- CSS Editor에 선택자를 입력하고 Enter로 결과를 확인한다.
- 선택자가 기억나지 않으면 오른쪽 설명과 예제를 참고한다.
- (강의 본문에 CSS Diner 주소는 텍스트로 나오지 않는다. 링크로만 걸려 있었을 수 있다.)

## CSS 복습 Q&A
- Q. CSS 박스 모델에서 padding과 margin의 차이는?
  A. padding은 내용과 테두리 사이의 안쪽 여백, margin은 테두리 바깥의 여백이다.
- Q. CSS 선택자 `.post .body`와 `.post > .body`는 어떻게 다른가?
  A. 공백은 모든 단계의 자손을, `>`는 바로 아래 자식만 고른다. 본문이 `.details` 안에 있으면 `.post > .body`는 아무것도 고르지 못한다.
- Q. CSS 선택자 `.title.featured`는 어떤 요소를 고르나?
  A. title과 featured 클래스를 모두 가진 요소다.
- Q. HTML에 외부 CSS 파일을 연결하는 코드는?
  A. `<head>` 안에 `<link rel="stylesheet" href="posts.css">`를 쓴다.
