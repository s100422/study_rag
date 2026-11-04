---
part: backend
lesson: 프론트엔드 연결과 CORS
order: 23
source_type: web
tags: [cors, fastapi, react, vite, jwt, sessionstorage, fetch, middleware]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1468/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 프론트엔드 연결과 CORS

## 프론트엔드 연결과 CORS 요약
React(Vite)로 만든 frontend 게시판 화면을 fastapi_agent 백엔드에 연결한다. 출처가 달라 생기는 CORS 제한을 CORSMiddleware로 풀고, 공통 응답 읽기·JWT 저장과 전송·글쓰기 폼 처리 흐름을 코드로 살펴본다.

## CORS란: 동일 출처 정책과 교차 출처 허용
CORS(Cross-Origin Resource Sharing)는 서버가 응답 헤더로 "이 출처는 응답을 읽어도 된다"고 알려 주어, 브라우저가 다른 출처의 응답을 JavaScript에서 쓸 수 있게 하는 방식이다.
- 브라우저는 기본적으로 동일 출처 정책(Same-Origin Policy)을 적용해, 한 출처의 JavaScript가 다른 출처의 응답을 마음대로 읽지 못하게 막는다.
- 목적은 악성 사이트가 사용자가 로그인한 다른 사이트의 데이터를 읽는 것을 막는 것이다.
- 프론트엔드와 백엔드의 출처가 다르면 이 제한이 걸리므로, 백엔드가 CORS 설정으로 프론트엔드 출처를 허용해야 화면에 API 응답을 표시할 수 있다.

## CORS 출처(Origin)를 구분하는 기준
CORS에서 출처(Origin)는 프로토콜 + 호스트 + 포트의 조합이며, 하나라도 다르면 다른 출처다.
- `http://127.0.0.1:5173`(프론트엔드)과 `http://127.0.0.1:8000`(백엔드)은 포트가 달라 다른 출처다.
- `http://localhost:5173`과 `http://127.0.0.1:5173`은 같은 컴퓨터를 가리켜도 호스트 표기가 달라 다른 출처다.
- `/posts`, `/auth/login` 같은 URL 경로는 출처 구분에 포함되지 않는다.

## 프론트엔드 연결 실습 1단계: 백엔드와 프론트엔드 실행
프론트엔드 연결 실습은 백엔드와 프론트엔드를 각각 다른 터미널에서 띄운다. 먼저 fastapi_agent 폴더에서 백엔드를 실행한다.
```bash
uv run fastapi dev
```
`frontend/.env`에 백엔드 주소를 적는다.
```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```
별도 터미널에서 프론트엔드를 실행하고 브라우저로 `http://127.0.0.1:5173`에 접속한다.
```bash
cd frontend
npm install
npm run dev
```

## 프론트엔드 연결 실습 2단계: FastAPI CORSMiddleware 설정
FastAPI에서 CORS는 미들웨어로 설정한다. 미들웨어는 요청이 Router에 닿기 전, 응답이 클라이언트로 가기 전에 공통 처리를 하는 구성 요소다. `CORSMiddleware`는 요청의 Origin을 보고 허용된 출처면 응답에 `Access-Control-Allow-Origin` 등의 헤더를 붙이고, 브라우저는 그 헤더로 JavaScript가 응답을 읽어도 되는지 판단한다.
```python
# fastapi_agent/src/fastapi_agent/main.py
from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI(...) 아래에 등록
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```
- `allow_origins`: 응답을 읽도록 허용할 프론트엔드 출처. (강의 코드에는 `"<http://127.0.0.1:5173>"`처럼 꺾쇠가 붙어 있는데, 표시 오류로 보이며 실제로는 꺾쇠 없이 써야 한다.)
- `allow_methods`: 허용할 HTTP 메서드.
- `allow_headers`: JSON 본문(`Content-Type`)과 토큰(`Authorization`) 전송용 헤더.

## CORS의 한계: 브라우저 정책일 뿐 보안 대책이 아니다
CORS는 브라우저가 적용하는 정책이라 curl이나 서버 간 요청에는 같은 제한이 걸리지 않는다. 따라서 CORS 설정이 API를 보호해 주지 않으며, 사용자 인증과 권한 검사는 백엔드에서 따로 구현해야 한다. 예를 들어 `allow_headers`의 `Authorization`은 그 헤더를 보내도 된다는 허용일 뿐이고, 토큰이 유효한지는 백엔드 인증 코드가 확인한다.

## React 프론트엔드 코드 구성 개념
React 프론트엔드에서 HTML은 구조, CSS는 스타일, JavaScript는 입력 처리와 API 호출을 맡는다. 이 프로젝트는 React로 화면을 만들고 Vite로 개발 서버를 띄운다.
- 컴포넌트: `PostListPage`, `AuthPage`처럼 화면을 나누는 단위.
- JSX: JavaScript 안에서 `<h1>{post.title}</h1>`처럼 화면을 표현하는 문법.
- props: `<PostListPage mine />`의 `mine`처럼 컴포넌트에 넘기는 값.
- `useState`: 게시글·입력값·로딩 여부 같은 상태 저장.
- `useEffect`: 화면 표시나 특정 값 변경 시 API 조회 같은 작업 실행.
- React Router: `/login`, `/posts/1` 같은 주소에 맞는 화면 표시.
- `onSubmit`은 폼 제출, `onChange`는 입력 변경 시 실행할 함수를 연결한다.

## 프론트엔드에서 FastAPI 공통 응답 읽기 (fetch)
프론트엔드의 API 요청 코드는 `frontend/src/api/client.js`에 모여 있다. 게시글 목록 조회의 기본 흐름은 다음과 같다.
```javascript
const response = await fetch(`${API_BASE_URL}/posts`)
const body = await response.json()
const posts = body.data
```
- `fetch()`: HTTP 요청을 보낸다. `await`로 결과를 기다린다.
- `response.json()`: JSON 응답을 JavaScript 값으로 읽는다.
- 실제 코드의 공통 함수 `request()`는 성공 시 `data`를 꺼내 반환하므로, `api.login()`·`api.post()`를 부른 화면에서 `.data`를 다시 꺼내지 않는다.
- 실패 응답이면 `error.message`를 읽어 오류로 던지고, 화면이 그 메시지를 표시한다.

## React 게시글 목록 화면을 API 응답으로 그리기
React의 `PostListPage.jsx`는 게시글 목록을 상태에 저장하고, 상태가 바뀌면 컴포넌트를 다시 실행해 화면을 갱신한다.
```javascript
const [data, setData] = useState({ items: [], total: 0 })
```
흐름: 목록 화면 표시 → `useEffect`에서 `api.posts()` 호출 → `GET /posts` 응답 → `setData(result)` → 목록 렌더링.

`/posts`는 전체 배열을 주고, `api.posts()`가 화면의 검색·정렬·페이지 조건에 맞춰 `{ items, total }`로 바꾼다.
```jsx
<ul>
  {data.items.map((post) => (
    <li key={post.id}>
      <Link to={`/posts/${post.id}`}>{post.title}</Link>
    </li>
  ))}
</ul>
```
- `{}`: JSX 안에 JavaScript 표현식을 넣는다.
- `map()`: 게시글마다 화면 요소로 변환. `key`는 React가 항목을 구분하는 값.
- `Link`: 클릭 시 상세 화면으로 이동.
- 요청 중엔 loading, 실패면 error, 성공이면 `data.items`로 화면을 표시한다.

## 프론트엔드 로그인 후 JWT 저장 (AuthContext)
프론트엔드 로그인 폼은 이메일·비밀번호를 JSON으로 `POST /auth/login`에 보내고, JWT는 응답의 `data.access_token`에 담겨 온다. `frontend/src/auth/AuthContext.jsx`에서 토큰과 사용자 정보를 저장한다.
```javascript
const result = await api.login(credentials)
const currentUser = await api.me(result.access_token)
sessionStorage.setItem(TOKEN_KEY, result.access_token)
setUser(currentUser)
setToken(result.access_token)
```
- `api.login()`이 `data`를 이미 꺼내 주므로 `result.access_token`으로 읽는다.
- 토큰으로 `GET /me`를 호출해 사용자 정보를 확인한 뒤 저장한다.
- sessionStorage: `access_token` 키로 JWT를 저장해 새로고침 후에도 쓴다.
- React 상태: `token`, `user`를 두고 API 요청과 화면 표시에 쓴다.
- `AuthProvider`가 Context로 로그인 상태를 공유하고, 각 화면은 `useAuth()`로 `user`, `token`, `logout()`을 가져온다. 상단 메뉴는 `user`에 따라 로그인 링크 또는 이메일·로그아웃 버튼을 보인다.

## 프론트엔드에서 JWT를 Authorization 헤더로 전달
프론트엔드 글쓰기 화면은 `useAuth()`로 토큰을 꺼내 API 함수에 넘긴다. sessionStorage에 저장했다고 자동으로 전송되지 않고, 요청 코드 `request()`가 `fetch()`의 Authorization 헤더에 직접 넣는다.
```javascript
const { token } = useAuth()
await api.createPost({ title, content }, token)
```
실제로 전송되는 요청 모양:
```http
POST /posts
Content-Type: application/json
Authorization: Bearer <JWT>

{"title": "제목", "content": "본문"}
```
백엔드의 `get_current_user()`는 헤더에서 토큰을 읽어 서명과 만료 시간을 검증하고, 토큰의 사용자 ID로 회원을 조회한다. 게시글 작성자는 이 사용자로 지정된다.

## 프론트엔드 JWT 새로고침·로그아웃·만료 처리
프론트엔드의 로그인 상태는 상황별로 다음처럼 처리된다.
- 새로고침: sessionStorage에서 토큰을 읽고 `/me`를 호출해 사용자 정보를 다시 불러온다.
- 로그아웃: 저장된 토큰을 지우고 React의 `token`, `user`를 비운다.
- 탭 닫기: 탭 세션이 끝나면 sessionStorage도 지워진다.
- 인증 실패: 현재 토큰으로 보낸 요청이 401을 받으면 로그인 상태를 지우고 재로그인 안내를 띄운다.

토큰 자동 갱신 기능은 없으므로 만료되면 다시 로그인해야 한다. 인증이 필요한 화면은 `RequireAuth`로 감싸져 있어, 로그인 상태가 없으면 로그인 화면으로 이동한다.

## React 글쓰기 폼 입력값 상태 관리 (NewPostPage)
React 글쓰기 화면 `frontend/src/pages/NewPostPage.jsx`는 제목과 내용을 각각 상태로 관리하고, 입력란과 버튼을 하나의 폼으로 묶는다.
```jsx
const [title, setTitle] = useState('')
const [content, setContent] = useState('')

<form onSubmit={submit}>
  <input value={title} onChange={(event) => setTitle(event.target.value)} />
  <textarea value={content} onChange={(event) => setContent(event.target.value)} />
  <button type="submit">등록</button>
</form>
```
- `value`: 입력란에 표시할 값.
- `onChange`: 입력할 때마다 `event.target.value`로 현재 값을 읽어 상태에 저장.
- 등록 버튼을 누르면 `onSubmit`의 `submit` 함수가 실행되고, `api.createPost()`에 넘긴 값을 공통 요청 코드가 JSON으로 바꿔 `POST /posts`로 보낸다.

## React 글쓰기 submit 함수: 요청 중·성공·실패 처리
React 글쓰기 화면은 `pending`(요청 중 여부), `error`(오류 메시지) 상태를 두고, `useAuth()`로 토큰, `useNavigate()`로 화면 이동 함수를 가져온다.
```javascript
const [pending, setPending] = useState(false)
const [error, setError] = useState('')
const { token } = useAuth()
const navigate = useNavigate()

async function submit(event) {
  event.preventDefault()
  if (pending) return
  setPending(true)
  setError('')
  try {
    const post = await api.createPost({ title, content }, token)
    navigate(`/posts/${post.id}`, { replace: true })
  } catch (reason) {
    setError(reason.message)
  } finally {
    setPending(false)
  }
}
```
- `event.preventDefault()`: 기본 폼 제출로 페이지가 새로 열리는 것을 막는다.
- 성공: 반환된 게시글 ID의 상세 화면으로 이동.
- 실패: `catch`에서 오류 메시지 저장. 입력값은 유지돼 다시 제출할 수 있다.
- `finally`: 결과와 관계없이 요청 중 상태 해제.

## React 글쓰기 버튼 비활성화와 오류 표시
React 글쓰기 화면은 `pending`, `error` 상태에 맞춰 버튼과 오류 문구를 바꿔 보여 준다.
```jsx
<button type="submit" disabled={pending}>
  {pending ? '등록 중…' : '등록'}
</button>
{error && <p role="alert">{error}</p>}
```
- `disabled={pending}`: 요청 중 버튼을 비활성화해 반복 제출을 막는다.
- 버튼 문구는 요청 중이면 "등록 중…", 아니면 "등록".
- 오류 메시지가 있으면 버튼 아래에 표시한다.
- 단, 인증 만료로 로그인 화면으로 이동하는 경우에는 입력값이 유지되지 않는다.

## 프론트엔드·백엔드 연결 확인 (개발자 도구)
프론트엔드와 FastAPI 연결은 회원가입 → 로그인 → 글쓰기 → 게시글 상세 → 댓글 작성 순서로 확인한다. 브라우저 개발자 도구에서 볼 것:
- Application → Session Storage: 로그인 후 `access_token`이 저장되는지.
- Network: `/auth/login` 응답의 `data.access_token`, `/me` 요청, 글쓰기 요청의 Authorization 헤더.
- Network: `/posts` 응답의 게시글이 화면 목록에 나오는지.
- Network → Payload: `POST /posts`에 입력한 title, content가 JSON으로 실리는지.
- 등록 후 응답의 게시글 ID 상세 화면으로 이동하는지.
- 새로고침 후 로그인 상태가 복원되고, 로그아웃 후 토큰이 지워지는지.

## 프론트엔드 연결과 CORS 복습 Q&A
- Q. CORS에서 출처(Origin)를 구분하는 세 요소는?
  A. 프로토콜, 호스트, 포트. 경로는 포함되지 않는다. 그래서 `127.0.0.1:5173`과 `127.0.0.1:8000`은 다른 출처다.
- Q. FastAPI에서 프론트엔드 출처를 허용하려면 무엇을 등록하나?
  A. `app.add_middleware(CORSMiddleware, allow_origins=[...], allow_methods=[...], allow_headers=[...])`.
- Q. CORS 설정만으로 API를 외부 요청에서 보호할 수 있나?
  A. 없다. CORS는 브라우저만 적용하는 정책이라 curl·서버 간 요청엔 효과가 없고, 인증·권한 검사를 따로 구현해야 한다.
- Q. 프론트엔드에서 JWT는 어디에 저장되고 어떻게 서버로 전달되나?
  A. sessionStorage(`access_token` 키)와 React 상태에 저장되고, 요청 코드가 `Authorization: Bearer <JWT>` 헤더에 직접 넣어 보낸다.
- Q. React 글쓰기 submit 함수에서 `finally`에 `setPending(false)`를 두는 이유는?
  A. 성공·실패와 관계없이 요청 중 상태를 풀어 버튼을 다시 활성화하기 위해서다.
