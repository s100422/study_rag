---
part: web
lesson: SPA
order: 4
source_type: web
tags: [spa, mpa, ssr, csr, rendering, dynamic-page, dom]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1313/
note: 개인 학습용 요약. 외부 공유 금지.
---

# SPA

## SPA 레슨 요약
처음 받은 HTML과 JavaScript로 바뀐 DOM의 차이를 보고, MPA와 SPA, SSR과 CSR을 구분하는 기준과 동적 페이지에서 내용이 준비되는 시점을 익힌다.

## 동적 페이지: 처음 받은 HTML과 변경된 DOM
동적 페이지에서는 처음 받은 HTML과 현재 DOM이 다를 수 있다. 게시글 예제는 새로고침하면 HTML에 적힌 글 2개가 보이고, 게시글 불러오기 버튼을 누르면 JSONPlaceholder API 응답으로 목록이 바뀐다.

```text
처음 받은 HTML                  API 응답 후 DOM
ul#post-list                    ul#post-list
├── HTML 기초                   ├── API의 첫 번째 글
└── CSS 선택자                  ├── API의 두 번째 글
                                └── API의 세 번째 글
```
- 페이지 소스에는 처음의 글 2개, 개발자 도구 Elements에는 API로 받은 글 3개가 보인다.

## 웹 화면 전환의 두 가지 방식
게시글 목록에서 상세 화면으로 갈 때, 새 HTML 문서를 받아 통째로 바꾸거나 현재 문서를 유지하며 내용만 바꿀 수 있다.

```text
새 문서를 받는 이동
[게시글 목록 문서] → 상세 페이지 요청 → [게시글 상세 문서]

현재 문서 안에서의 이동
[문서: 게시글 목록 영역] → JavaScript 실행 → [같은 문서: 게시글 상세 영역]
```
- 앞쪽이 MPA 방식, 뒤쪽이 SPA 방식에 해당한다(내 메모).

## MPA(Multi-Page Application)란
MPA는 여러 HTML 문서로 이루어진 웹 애플리케이션이다. 보통 페이지를 이동하면 서버에 새 HTML 문서를 요청해 문서 전체를 교체한다. 개발자 도구 Network의 Doc 필터에서 새 문서 요청을 확인할 수 있다.

## SPA(Single-Page Application)란
SPA는 HTML 문서 하나를 기반으로 JavaScript가 내용을 갱신해 화면을 전환하는 웹 애플리케이션이다.
- 앱 안에서 화면을 옮길 때 매번 새 HTML 문서 전체를 받을 필요가 없다.
- 상세 화면 데이터는 API로 추가 요청하거나 이미 받은 데이터를 쓴다.
- 화면 전환에 맞춰 주소창 URL도 바꿀 수 있다.
- SPA여도 새로고침하거나 주소를 직접 입력하면 HTML 문서를 요청한다.

## 동적 페이지와 SPA의 관계
JavaScript로 일부 내용이 바뀐다고 모두 SPA인 것은 아니다.
- MPA도 검색 결과나 댓글 영역만 갱신할 수 있다.
- 강의 공통 예제는 한 화면에서 제목과 목록만 바뀌는 예제이고, 여러 화면을 전환하는 SPA를 구현한 것은 아니다.
- URL이 바뀌는지만으로는 SPA와 MPA를 구분할 수 없다. 화면 이동 때 새 문서가 요청되는지도 같이 본다.

## 렌더링과 API 응답 데이터
렌더링(Rendering)은 문서와 데이터를 화면에 표시할 형태로 만드는 과정이다. 예를 들어 `https://jsonplaceholder.typicode.com/posts/1`은 첫 게시글을 JSON으로 응답하며, `id`(글 번호), `userId`(작성자 번호), `title`(제목), `body`(본문)를 담는다. JavaScript는 이 데이터를 HTML 요소에 반영한다. 데이터를 반영한 HTML을 어디서 만드느냐에 따라 SSR과 CSR로 나뉜다.

## SSR(Server-Side Rendering)이란
SSR은 서버가 데이터를 반영한 HTML을 만들어 브라우저에 보내는 렌더링 방식이다. 게시글 조회 결과를 서버의 HTML 템플릿에 넣어 응답하는 경우가 해당한다.

```text
브라우저에서 페이지 요청
          ↓
서버에서 게시글 조회
          ↓
조회 결과를 반영한 HTML 생성
          ↓
브라우저가 HTML을 받아 화면에 표시
```
- 응답 HTML에 제목과 본문이 이미 들어 있다.
- 서버가 HTML을 만들어도 실제로 화면을 그리는 것은 브라우저다.
- 처음 받은 HTML에 내용이 있다고 늘 SSR은 아니다. 미리 작성된 HTML 파일을 그대로 줄 수도 있다.

## CSR(Client-Side Rendering)이란
CSR은 브라우저에서 JavaScript가 데이터를 화면 요소에 반영하는 렌더링 방식이다. API가 JSON을 응답하면 브라우저가 그 값으로 요소를 만들거나 내용을 바꾼다.

```text
브라우저가 HTML과 JavaScript를 받음
          ↓
JavaScript가 JSONPlaceholder의 /posts API 요청
          ↓
JSONPlaceholder가 게시글 배열 응답
          ↓
JavaScript가 JSON으로 DOM을 구성
          ↓
게시글 목록이 화면에 표시됨
```
- 데이터는 API 응답뿐 아니라 HTML에 미리 담긴 값을 쓸 수도 있다.
- 게시글 예제는 응답 배열 앞 3개의 제목·본문을 표시한다.
- JavaScript `fetch()`는 Python에서 HTTP 클라이언트로 API를 부르는 것과 역할이 비슷하다.

## SPA·MPA와 SSR·CSR 구분 기준
SPA·MPA와 SSR·CSR은 서로 다른 기준이다.
- MPA / SPA: 화면을 이동할 때 새 HTML 문서를 받는가, 기존 문서를 유지하는가
- SSR / CSR: 데이터를 반영한 HTML을 서버에서 만드는가, 브라우저에서 데이터를 DOM에 반영하는가

두 기준은 섞일 수 있다.
- 한 서비스가 초기 화면은 SSR, 이후 변경은 CSR로 처리할 수 있다.
- SPA라고 초기 HTML이 항상 비어 있는 것은 아니다.
- MPA도 JavaScript로 일부 영역을 갱신할 수 있다.

## 동적 페이지에서 내용이 준비되는 시점
동적 페이지는 HTML을 받은 시점과 필요한 데이터가 화면에 나타나는 시점이 다를 수 있다.
- 게시글 불러오기 버튼을 누르면 요청 중에는 "게시글을 불러오는 중입니다." 문구가 나오고 버튼이 비활성화된다.
- 응답 처리 후 API 게시글이 표시되고 문구가 "게시글 3개를 표시했습니다."로 바뀌면 갱신이 끝난 것이다.
- 실제 사이트는 스크롤하거나 더 보기 버튼을 눌러야 추가 내용이 나오기도 한다.
- 동적 페이지를 읽을 때는 어떤 동작 후, 어떤 요소가, 언제 나타나는지 확인한다.

## SPA 복습 Q&A
- Q. SPA와 MPA를 구분하는 기준은?
  A. 화면 이동 때 새 HTML 문서를 받으면 MPA, 기존 문서를 유지하고 JavaScript로 내용만 바꾸면 SPA다. URL 변경 여부만으로는 구분할 수 없다.
- Q. SSR과 CSR의 차이는?
  A. SSR은 서버가 데이터를 넣은 HTML을 만들어 보내고, CSR은 브라우저의 JavaScript가 받은 데이터로 DOM을 구성한다.
- Q. 동적 페이지에서 페이지 소스와 Elements 내용이 다른 이유는?
  A. 페이지 소스는 처음 받은 HTML이고, Elements는 JavaScript가 바꾼 현재 DOM이기 때문이다.
- Q. JavaScript로 내용이 바뀌면 SPA인가?
  A. 아니다. MPA도 일부 영역을 JavaScript로 갱신할 수 있다.
