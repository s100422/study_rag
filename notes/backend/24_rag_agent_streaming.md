---
part: backend
lesson: RAG Agent 연결과 스트리밍
order: 24
source_type: web
tags: [rag, langgraph, sse, streamingresponse, astream, chroma, fastapi, react]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1470/
note: 개인 학습용 요약. 외부 공유 금지.
---

# RAG Agent 연결과 스트리밍

## RAG Agent 연결과 스트리밍 요약
검색(retrieve) → 답변 생성(generate) 순서로 도는 LangGraph RAG 그래프를 FastAPI chat 도메인에 연결한다. Service가 그래프를 `astream()`으로 실행하고, Router가 결과를 SSE(Server-Sent Events)로 흘려보내며, React 화면은 생성 중인 답변·참고 문서·실행 시간을 실시간으로 보여 준다.

## RAG 스트리밍 API 전체 실행 흐름
RAG 스트리밍 API는 다음 순서로 동작한다.
- 브라우저가 `POST /chat/rag/stream`을 보낸다.
- Chat Router가 JWT 인증과 요청 검증을 한 뒤 `RagChatService.stream_rag(agent, question)`을 호출한다.
- Service는 RAG 그래프를 `astream(question)`으로 실행한다.
- 검색 문서가 나오면 `sources` 이벤트, 답변 조각이 나올 때마다 `token` 이벤트를 Router를 통해 SSE로 보낸다.
- 그래프가 끝나면 최종 답변과 실행 시간을 담은 `done` 이벤트를 보낸다.

## RAG 실습 1단계: Chroma에 문서 적재 (rag-ingest)
RAG가 질문과 의미가 비슷한 문서를 찾으려면 문서를 임베딩 벡터로 바꿔 Chroma에 저장해 두어야 한다. fastapi_agent 디렉터리의 `.env`에 `GEMINI_API_KEY`를 설정하고 실행한다.
```bash
uv run rag-ingest
```
- PDF를 읽어 청크로 나누고, 각 청크를 임베딩해 `./chroma_db`의 `spri_ai_brief` 컬렉션에 저장한다.
- 그래프 생성 시 이 컬렉션에 연결하므로 서버 실행 전에 적재를 끝내야 한다.
- 다시 실행하면 기존 컬렉션을 지우고 새로 적재한다.

## RAG 그래프 create_rag_agent의 구조와 상태
`agents.rag`의 `create_rag_agent()`는 검색기와 Gemini 모델을 연결한 LangGraph 그래프를 반환한다. START → retrieve → generate → END로 도는 고정 RAG 워크플로라서, 검색 여부와 순서가 코드로 정해져 있고 모든 질문에 검색과 생성을 차례로 수행한다.

그래프 상태:
- `question`: 사용자 질문
- `documents`: 검색된 Document 목록
- `answer`: 문서를 근거로 생성한 답변

Service는 질문을 넣고 검색 결과와 생성 중인 답변을 읽기만 하며, HTTP 응답 형식은 Router가 만든다.

## SSE 스트리밍 응답과 일반 JSON 응답 비교
LLM 답변 생성은 시간이 걸리므로, 생성된 내용을 바로바로 보내는 스트리밍을 쓰면 사용자가 진행 과정을 보며 답변을 읽기 시작할 수 있다.
- 일반 JSON 응답: Content-Type `application/json`, 완성된 JSON 하나를 생성이 끝난 뒤 전송. 프론트는 `response.json()`으로 한 번에 읽고 표시.
- SSE 응답: Content-Type `text/event-stream`, 연결을 유지한 채 텍스트 이벤트를 순서대로 여러 번 전송. 프론트는 `response.body` 스트림을 읽으며 이벤트마다 화면 갱신.

SSE(Server-Sent Events)는 서버가 클라이언트로 이벤트를 보내는 형식으로, 한 질문의 답변 조각과 진행 상태를 같은 HTTP 응답으로 계속 보낼 수 있다.

## SSE 이벤트 텍스트 형식 (event, data, 빈 줄)
SSE 이벤트는 `event:` 줄과 `data:` 줄로 이루어지고, 빈 줄(`\n\n`)로 이벤트가 끝난다.
```text
event: token
data: {"content":"AI 산업에서는 "}

event: token
data: {"content":"인프라 투자가 확대되고 있습니다."}
```
- `event`: 클라이언트가 구분할 이벤트 이름.
- `data`: 전달할 데이터. 이 API는 JSON 문자열을 쓴다.
- `\n\n`: 이벤트 하나의 끝.
- data를 JSON으로 직렬화하면 답변 속 줄바꿈이 문자열 내부 `\n`으로 표현돼 이벤트 경계와 헷갈리지 않는다.

## RAG SSE 이벤트 종류: status, sources, token, done, error
RAG 스트리밍 API는 화면 처리 방식이 다른 정보를 이벤트 이름으로 구분하며, 이름과 데이터 형식은 서버·프론트가 미리 약속한다.
- `status`: `{"message": "문서를 검색하고 있습니다."}` → 진행 상태 표시.
- `sources`: `{"sources": [{"id": 1, "source": "보고서.pdf", "page_number": 3}]}` → 참고 문서 표시.
- `token`: `{"content": "답변 조각"}` → 현재 답변 뒤에 덧붙임. 한 조각에 여러 글자가 들어 있을 수 있다.
- `done`: `{"answer": "최종 답변", "sources": [], "elapsed_ms": 1320}` → 최종 결과 반영 후 수신 종료.
- `error`: `{"message": "답변 생성 중 오류가 발생했습니다."}` → 오류 표시 후 수신 종료.

`sources`의 `id`는 답변 속 인용 번호 `[1]`, `[2]`와 대응한다.

## 파이썬 비동기 제너레이터: async def + yield와 async for
이벤트를 차례로 내보내기 위해 비동기 제너레이터를 쓴다. `async def` 안에서 `yield`를 쓰면 비동기 제너레이터가 되고, 호출자는 `async for`로 값을 하나씩 받는다.
```python
async def events():
    yield "검색 시작"
    yield "답변 생성"
    yield "완료"

async for event in events():
    print(event)
```
- `events()`를 호출하면 제너레이터 객체만 만들어진다.
- `async for`가 다음 값을 요청하면 실행되어 `yield`에서 값을 넘기고 멈추며, 다음 요청 때 멈춘 곳부터 이어 간다.
- `await`는 비동기 작업 결과 하나를 기다리고, `async for`는 비동기 반복자가 만드는 값을 차례로 받는다.
- FastAPI `StreamingResponse`에 제너레이터를 넘기면 FastAPI가 이 반복을 돌며 값을 응답 본문으로 보낸다.

## LangChain/LangGraph 동기·비동기 호출: invoke, ainvoke, stream, astream
LangChain 모델과 LangGraph 그래프는 동기·비동기 호출을 모두 제공하며, 비동기 코드에서는 `ainvoke()`, `astream()`을 쓴다.
- 최종 결과 한 번 받기: 동기 `invoke()`, 비동기 `await ainvoke()`.
- 실행 중 값을 차례로 받기: 동기 `for ... in stream(...)`, 비동기 `async for ... in astream(...)`.

비동기 실행과 스트리밍은 다른 개념이다. `ainvoke()`는 비동기로 돌지만 완성된 결과만 돌려주고, `astream()`은 비동기로 돌면서 중간 결과를 계속 넘긴다. 이 API에서는 노드 안에서 `await model.ainvoke(...)`로 모델을 부르고, Service에서 `agent.astream(...)`으로 그래프 스트림을 읽는다.

## LangGraph astream stream_mode: messages와 updates
LangGraph `astream()`에 `stream_mode=["messages", "updates"]`를 주면 생성 중인 답변과 노드 결과를 함께 받는다.
- `messages`: 모델이 생성하는 동안 (메시지 조각, 메타데이터)를 받는다 → 답변 조각 즉시 표시용.
- `updates`: 노드가 끝날 때마다 그 노드가 반환한 상태 변경을 받는다 → 검색 문서·최종 답변 확인용.
```python
async for mode, data in agent.astream(
    {"question": question},
    stream_mode=["messages", "updates"],
):
    if mode == "messages":
        chunk, metadata = data
        if metadata["langgraph_node"] == "generate" and chunk.text:
            print(chunk.text, end="", flush=True)
    elif mode == "updates":
        print(data)
```
- 두 모드를 함께 쓰면 매번 `(mode, data)` 튜플을 받는다.
- `metadata["langgraph_node"]`: 조각을 만든 노드 이름. generate 것만 골라 출력.
- updates 예: `{"retrieve": {"documents": [...]}}`, `{"generate": {"answer": "최종 답변"}}`.

## LangGraph 노드 안 invoke로도 토큰 스트리밍이 되는 이유
LangGraph에서는 노드 내부에서 `model.invoke()`/`await model.ainvoke()`를 써도, 그래프를 바깥에서 `stream_mode="messages"`로 실행하면 생성 중인 토큰 조각을 받을 수 있다. 노드 안에서 `model.stream()`/`model.astream()`을 직접 돌릴 필요가 없다.
- `invoke()`/`ainvoke()`는 노드에는 완성된 응답을 돌려준다.
- 그 응답을 기다리는 동안 LangGraph가 모델의 토큰 생성 이벤트를 받아 그래프 바깥의 messages 스트림으로 흘려보낸다.
- 조건: 스트리밍을 지원하는 LangChain 채팅 모델을 쓰고, 모델 스트리밍을 끄지 않았을 것.
- `stream_mode`에 `"messages"`가 있어야 토큰이 오며, `"updates"`만 주면 노드 완료 후 상태 변경만 받는다.

## FastAPI chat 도메인 파일 구성과 질문 요청 모델
FastAPI의 `fastapi_agent/src/fastapi_agent/domains/chat`은 세 파일로 나뉜다.
- `schemas.py`: 질문 요청 형식 정의.
- `rag_service.py`: RAG 그래프 출력을 (이벤트 이름, 데이터)로 변환.
- `router.py`: 이벤트를 SSE 본문으로 직렬화해 전송.

질문은 빈 문자열을 허용하지 않는 모델로 받는다.
```python
# src/fastapi_agent/domains/chat/schemas.py
from pydantic import BaseModel, Field

class RagChatRequest(BaseModel):
    question: str = Field(min_length=1)
```
요청 본문 예:
```json
{"question": "AI 산업의 주요 동향을 알려줘."}
```

## FastAPI lifespan에서 RAG 그래프 생성해 app.state에 공유
FastAPI에서 검색기·모델 클라이언트·그래프를 요청마다 만들지 않도록, 앱 시작 시 lifespan에서 한 번 만들어 `app.state.rag_agent`에 보관한다. `app.state`는 앱의 요청들이 공유할 객체를 두는 공간이다.
```python
# src/fastapi_agent/main.py (발췌)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agents import create_rag_agent
from fastapi_agent.core.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.rag_agent = create_rag_agent()
        yield
    finally:
        await engine.dispose()
```
- `FastAPI(lifespan=lifespan, ...)`로 연결한다.
- 그래프는 서버 프로세스마다 한 번 생성되며, 프로세스가 여러 개면 각자 자기 그래프를 가진다.

## FastAPI Router에서 request.app.state로 공유 그래프 꺼내기
FastAPI Router 함수에 `request: Request`를 선언하면 현재 요청 객체가 주입되고, 이를 통해 저장해 둔 그래프에 접근한다.
- `request`: 현재 HTTP 요청 객체.
- `request.app`: 요청을 처리하는 FastAPI 앱 객체.
- `request.app.state`: 앱 공유 객체 보관 공간.
- `request.app.state.rag_agent`: 앱 시작 시 만든 RAG 그래프.

Router는 이 그래프와 질문을 Service에 넘긴다. 공유되는 것은 실행 가능한 그래프 객체뿐이고, 질문·검색 문서·답변은 각 `astream()` 호출의 상태로 따로 관리되므로 요청끼리 섞이지 않는다.

## RagChatService stream_rag: 그래프 출력과 이벤트 대응
RagChatService의 `stream_rag()`는 (이벤트 이름, 데이터)를 차례로 내보내는 비동기 제너레이터이며, LangGraph 출력을 다음처럼 이벤트로 바꾼다.
- 실행 시작 → "검색 중" `status`.
- updates의 retrieve → 문서 메타데이터로 출처 목록을 만들어 `sources`, 이어서 "생성 중" `status`.
- messages의 generate → 답변 조각을 `token`.
- updates의 generate → 최종 답변을 `answer` 변수에 보관.
- 그래프 반복 종료 → 최종 답변·출처·경과 시간을 담은 `done` 한 번.

## RagChatService 실습 코드 1: 시작 status와 token 이벤트
RagChatService는 시작 시간을 재고 검색 상태를 알린 뒤, 그래프 스트림에서 generate 노드의 조각을 `token`으로 내보낸다. (`rag_service.py` 앞부분 발췌)
```python
# src/fastapi_agent/domains/chat/rag_service.py (앞부분)
from time import perf_counter
from langgraph.graph.state import CompiledStateGraph

class RagChatService:
    async def stream_rag(self, agent: CompiledStateGraph, question: str):
        started = perf_counter()
        answer = ""
        sources = []

        yield "status", {"message": "문서를 검색하고 있습니다."}

        async for mode, data in agent.astream(
            {"question": question},
            stream_mode=["messages", "updates"],
        ):
            if mode == "messages":
                chunk, metadata = data
                if metadata["langgraph_node"] == "generate" and chunk.text:
                    yield "token", {"content": chunk.text}
            elif mode == "updates":
                ...  # retrieve/generate 결과 처리
```
- `perf_counter()`: 경과 시간 측정 시작점.
- `token`은 받는 즉시 전달한다.

## RagChatService 실습 코드 2: retrieve 결과로 sources 이벤트 만들기
RagChatService `stream_rag()`의 `elif mode == "updates":` 분기는 retrieve 결과를 출처 목록으로 바꿔 `sources`를 보내고, generate 결과에서 최종 답변을 보관한다.
```python
elif mode == "updates":
    if "retrieve" in data:
        documents = data["retrieve"]["documents"]
        sources = [
            {"id": index,
             "source": document.metadata["source"],
             "page_number": document.metadata["page_number"]}
            for index, document in enumerate(documents, start=1)
        ]
        yield "sources", {"sources": sources}
        yield "status", {"message": "답변을 생성하고 있습니다."}
    if "generate" in data:
        answer = data["generate"]["answer"]
```
- `enumerate(..., start=1)`: generate 노드와 같은 순서로 1부터 번호를 매겨 `id`가 답변의 `[1]`, `[2]`와 맞는다.
- `source`, `page_number`: 적재 때 넣은 메타데이터(파일명·페이지). 사용자가 답변 근거를 확인하는 데 쓴다.

## RagChatService 실습 코드 3: 스트림 종료 후 done 이벤트
RagChatService `stream_rag()`는 `async for`로 그래프 스트림을 끝까지 읽은 뒤(반복문 바깥에서) `done`을 한 번 보낸다. 화면은 이 이벤트로 최종 결과를 반영하고 수신을 마친다.
```python
        yield "done", {
            "answer": answer,
            "sources": sources,
            "elapsed_ms": round((perf_counter() - started) * 1000),
        }

rag_chat_service = RagChatService()
```
- `answer`: updates의 generate에서 보관한 최종 답변(token 조각을 이어 붙인 것이 아니다).
- `elapsed_ms`: `perf_counter()`로 잰 Service 시작부터 그래프 완료까지의 시간(ms).
- `rag_chat_service`: Router가 가져다 쓰는 모듈 수준 인스턴스.

## FastAPI chat Router 설정과 format_sse 함수
FastAPI chat Router는 라우터 전체에 JWT 인증을 걸고, 이벤트를 SSE 텍스트로 바꾸는 `format_sse()`를 둔다.
```python
# src/fastapi_agent/domains/chat/router.py (앞부분)
import json
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi_agent.core.dependencies import get_current_user
from fastapi_agent.core.responses import error_responses
from fastapi_agent.domains.chat.rag_service import rag_chat_service
from fastapi_agent.domains.chat.schemas import RagChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(get_current_user)],
    responses=error_responses(401, 422),
)

def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```
- `dependencies=[Depends(get_current_user)]`: 스트리밍 시작 전에 JWT를 검사해 로그인 사용자만 호출하게 한다.
- `ensure_ascii=False`: 한글을 이스케이프하지 않고 그대로 담는다.

## FastAPI StreamingResponse로 RAG SSE 엔드포인트 만들기
FastAPI `POST /chat/rag/stream`은 비동기 제너레이터 `events()`를 `StreamingResponse`에 넘겨 이벤트를 즉시 보낸다.
```python
@router.post(
    "/rag/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_rag(data: RagChatRequest, request: Request):
    agent = request.app.state.rag_agent

    async def events():
        try:
            async for event, payload in rag_chat_service.stream_rag(agent, data.question):
                yield format_sse(event, payload)
        except Exception:
            logger.exception("RAG 스트리밍 실행 실패")
            yield format_sse("error", {"message": "답변 생성 중 오류가 발생했습니다."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```
- 그래프 예외는 본문 전송 중에 나므로 `events()` 안에서 잡는다.
- `media_type`: 실제 Content-Type(데코레이터 `responses`는 문서용).
- `no-cache`: 재검증 요구. `X-Accel-Buffering: no`: Nginx 버퍼링 해제.

## FastAPI main.py에 chat Router 등록
FastAPI 앱에서 RAG 스트리밍 엔드포인트를 쓰려면 `main.py`에 chat Router를 등록한다.
```python
from fastapi_agent.domains.chat.router import router as chat_router

app.include_router(chat_router)
```

## RAG 스트리밍 오류 처리: 응답 시작 전과 시작 후
RAG 스트리밍 API의 오류는 발생 시점에 따라 전달 방식이 다르다.
- 스트리밍 시작 전 인증 실패: 401과 공통 JSON 오류 응답.
- 스트리밍 시작 전 요청 검증 실패: 422와 공통 JSON 오류 응답.
- 스트리밍 시작 후 그래프 실행 실패: 서버 로그를 남기고 SSE `error` 이벤트 전송.

응답 헤더가 나가면 HTTP 상태 코드(200)가 이미 확정되므로, 그 뒤의 실패는 상태 코드로 알릴 수 없다. 그래서 Router의 비동기 제너레이터에서 예외를 잡고, 연결이 살아 있으면 `error` 이벤트로 알린다.

## 프론트엔드 RAG 스트림 요청: 인증된 POST fetch
프론트엔드는 질문을 POST 본문에 담고 JWT를 헤더로 보내면서 응답 스트림을 읽어야 하므로 `fetch()`를 쓴다.
```javascript
const response = await fetch(`${API_BASE_URL}/chat/rag/stream`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify({ question }),
})
```
- `fetch()`는 응답 헤더를 받으면 바로 반환되고, 이후 `response.body`에서 이벤트를 계속 읽는다.

## 프론트엔드 SSE 파싱 consumeSSE: 청크를 줄로 나누기
프론트엔드에서 SSE 이벤트는 여러 청크로 쪼개지거나 한 청크에 여럿 들어오고, 한글 UTF-8 바이트도 잘릴 수 있다. `frontend/src/api/stream.js`의 `consumeSSE()`는 바이트 → 문자열 → 줄 → 이벤트 순으로 읽는다(줄 분리 부분 발췌, `line()`은 줄 처리 함수).
```javascript
const reader = body.getReader()
const decoder = new TextDecoder()
let buffer = ''
while (true) {
  const { value, done } = await reader.read()
  buffer += decoder.decode(value, { stream: !done })
  let match
  while ((match = /[\r\n]/.exec(buffer))) {
    const index = match.index
    if (!done && buffer[index] === '\r' && index === buffer.length - 1) break
    const width = buffer[index] === '\r' && buffer[index + 1] === '\n' ? 2 : 1
    const content = buffer.slice(0, index)
    buffer = buffer.slice(index + width)
    if (line(content)) return
  }
  if (done) return
}
```
- `TextDecoder`의 `stream: true`: 미완성 문자 바이트를 다음 호출까지 보관. 마지막엔 `stream: false`로 남은 바이트 처리.
- 바깥 while은 청크 수신, 안쪽 while은 버퍼의 완성된 줄을 모두 꺼낸다. 미완성 줄은 버퍼에 남는다.
- 줄바꿈은 `\n`, `\r`, `\r\n` 가능. 버퍼 끝이 `\r`이면 다음 `\n`을 기다리고, `width`는 1 또는 2.

## 프론트엔드 SSE 파싱 line(): 줄을 이벤트로 모으기
프론트엔드 `consumeSSE()`의 내부 함수 `line()`은 줄을 받아 다음 규칙으로 SSE 이벤트를 조립한다.
- `event: token` 줄: 현재 이벤트 이름을 token으로 저장.
- `data: {...}` 줄: `data:` 뒤 문자열을 배열에 추가.
- 빈 줄: 모은 data를 줄바꿈으로 합쳐 `{ event, data }`를 콜백에 넘기고 다음 이벤트 준비.
- `:`로 시작하는 줄: SSE 주석으로 무시.

콜백이 `true`를 반환하면 `line()`도 `true`를 반환해 읽기 반복을 끝낸다. 함수의 `finally`에서 `reader.cancel()`과 `reader.releaseLock()`으로 수신을 정리한다.

## 프론트엔드 streamRequest: onEvent 콜백과 done 결과 반환
프론트엔드 `streamRequest()`는 인증된 요청을 보내고, `consumeSSE()`가 넘긴 data를 `JSON.parse()`해 화면의 `onEvent(event, data)` 콜백에 전달한다. `await`로 완료를 기다리는 동안에도 콜백은 이벤트마다 실행된다.
```javascript
import { streamRequest } from '../api/stream.js'

const result = await streamRequest('/chat/rag/stream', {
  body: { question },
  token,
  onEvent(event, data) {
    if (event === 'token') console.log(data.content)
  },
})
console.log(result.answer)
```
내부에서 콜백 호출과 완료 판정은 다음과 같다.
```javascript
onEvent?.(event, payload)
if (event === 'done') { result = payload; return true }
return false
```
- `onEvent?.()`: 콜백이 있을 때만 실행.
- `done`이면 결과를 보관하고 `true`로 `consumeSSE()`를 끝낸 뒤 `result`를 반환한다.
- `reader.read()`의 `done`은 본문을 끝까지 읽음, SSE `done` 이벤트는 서버가 생성을 마침. 본문이 끝났는데 `result`가 비어 있으면 미완료 응답으로 처리한다.

## 프론트엔드 streamRequest 오류 처리와 시간 초과
프론트엔드 `streamRequest()`는 실패 원인별로 예외를 던져 화면이 알맞은 안내를 보이게 한다.
- HTTP 오류 응답: JSON 오류 본문을 읽어 `ApiError` 발생.
- SSE `error` 이벤트: 이벤트의 안내 문구로 `ApiError` 발생.
- `done` 없이 연결 종료: 답변 완료 전에 끊겼다는 오류.
- 요청 시작 후 120초 경과: 내부 `AbortController`로 수신을 취소하고 시간 초과 오류.

요청이 끝나면 `finally`에서 제한 시간 타이머와 취소 이벤트 리스너를 정리한다.

## 프론트엔드 ai.ask(): RAG 호출 함수
프론트엔드 `frontend/src/api/ai.js`의 `ai.ask()`는 화면에서 질문과 이벤트 처리 함수를 받아 RAG 스트리밍 요청을 보내고 최종 결과를 반환한다.
```javascript
ask: async (question, token, signal, onEvent) => {
  const data = await streamRequest('/chat/rag/stream', {
    body: { question }, token, signal, onEvent,
  })
  if (typeof data?.answer !== 'string') throw new ApiError('답변을 읽을 수 없습니다.', 0)
  return data
},
```
- `token`: JWT 인증. `signal`: 요청 취소. `onEvent`: 중간 결과 전달.
- 반환값은 `done` 이벤트에 담긴 최종 결과(answer, sources, elapsed_ms).

## React RagPage 실습 1: import와 상태 선언
React `frontend/src/pages/RagPage.jsx`는 질문·답변·출처·진행 상태·실행 시간·로딩·오류를 상태로 두고, 취소용 AbortController를 `useRef`에 보관한다.
```jsx
import { useEffect, useRef, useState } from 'react'
import { ai } from '../api/ai.js'
import { useAuth } from '../auth/AuthContext'

export function RagPage() {
  const { token } = useAuth()
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState([])
  const [status, setStatus] = useState('')
  const [elapsed, setElapsed] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const requestRef = useRef(null)

  useEffect(() => () => requestRef.current?.abort(), [])
  // submit 함수와 화면 JSX가 이어진다
```
- `useRef`: 렌더링 사이에도 유지되는 보관 공간. 현재 요청의 AbortController를 둔다.
- `useEffect(...)`: 컴포넌트가 사라질 때 진행 중인 요청을 취소한다.

## React RagPage 실습 2: submit에서 ai.ask 호출과 토큰 누적
React RagPage `submit`은 `ai.ask()` 콜백으로 상태를 갱신한다.
```jsx
async function submit(event) {
  event.preventDefault()
  if (loading || !question.trim()) return
  const controller = new AbortController()
  requestRef.current = controller
  setLoading(true); setAnswer(''); setSources([]); setError(''); setElapsed(null)
  setStatus('요청하고 있습니다.')
  try {
    const result = await ai.ask(question.trim(), token, controller.signal,
      (event, data) => {
        if (event === 'status') setStatus(data.message)
        if (event === 'sources') setSources(data.sources)
        if (event === 'token') setAnswer(current => current + data.content)
      })
    if (!controller.signal.aborted) {
      setAnswer(result.answer); setSources(result.sources)
      setElapsed(result.elapsed_ms); setStatus('완료')
    }
  } catch (reason) {
    if (!controller.signal.aborted) { setError(reason.message); setStatus('응답 중단') }
  } finally {
    if (!controller.signal.aborted) setLoading(false)
  }
}
```

## React RagPage 토큰 누적과 최종 답변 교체 원리
React RagPage에서 `status`, `sources` 이벤트는 상태를 통째로 교체하고, `token` 이벤트는 `setAnswer(current => current + data.content)`로 이어 붙인다.
- 함수형 갱신의 `current`에는 React가 처리 중인 최신 상태가 들어오므로, 조각이 연달아 와도 순서대로 누적된다.
- token으로 쌓은 텍스트는 "생성 중" 표시용이다. `await ai.ask(...)`가 끝나면 `done`의 최종 답변으로 교체하고 출처·실행 시간을 반영한다.
- 완료 전에 오류가 나면 부분 답변은 그대로 두고 오류 안내를 함께 보인다.
- `controller.signal.aborted`를 확인해 취소된 요청이면 결과 반영과 오류 표시를 건너뛴다.

## React RagPage 실습 3: 질문 폼과 답변·출처 화면
React RagPage의 렌더링 부분은 질문 폼, 진행 상태, 오류, 누적 답변, 출처 목록, 실행 시간을 보여 준다.
```jsx
<section>
  <h1>문서에 질문하기</h1>
  <form onSubmit={submit}>
    <label htmlFor="rag-question">질문</label>
    <textarea id="rag-question" value={question}
      onChange={event => setQuestion(event.target.value)}
      disabled={loading} required />
    <button disabled={loading || !question.trim()}>
      {loading ? '답변 생성 중' : '질문 보내기'}
    </button>
  </form>
  <p role="status">{status}</p>
  {error && <p role="alert">{error}</p>}
  <div style={{ whiteSpace: 'pre-wrap' }}>{answer}</div>
  <ul>
    {sources.map(source => (
      <li key={source.id}>[{source.id}] {source.source} · {source.page_number}쪽</li>
    ))}
  </ul>
  {elapsed !== null && <p>실행 시간: {(elapsed / 1000).toFixed(1)}초</p>}
</section>
```
- `whiteSpace: 'pre-wrap'`: 답변의 줄바꿈을 그대로 표시.
- 출처는 `[번호] 파일명 · 페이지쪽` 형태로, 답변 인용 번호와 대조할 수 있다.

## React RagPage 화면을 떠날 때 스트림 수신 취소
React RagPage는 `useRef`로 렌더링 사이에도 유지되는 보관 공간에 현재 요청의 AbortController를 저장해 두고, 컴포넌트가 사라질 때 요청을 취소한다. 예제의 `useEffect(() => () => requestRef.current?.abort(), [])`를 풀어 쓰면 다음과 같다.
```jsx
useEffect(() => {
  return () => {
    requestRef.current?.abort()
  }
}, [])
```
- `useEffect`가 반환한 함수는 컴포넌트 제거 시 실행되는 정리 함수다.
- `abort()`를 부르면 `controller.signal`을 받은 수신 작업이 취소된다.
- 이후 `controller.signal.aborted`로 취소 여부를 보고 결과 반영·오류 표시를 건너뛴다.

## RAG 스트리밍 프론트엔드 실행과 동작 확인
RAG 스트리밍 화면은 프론트엔드 `.env`에 `VITE_API_BASE_URL=http://127.0.0.1:8000`을 두고 `npm run dev`로 실행한다. 백엔드 CORS 설정에서 프론트엔드 출처와 `Authorization`, `Content-Type` 헤더를 허용해야 한다.

확인할 것:
- 로그인 후 질문을 보내면 검색 상태와 출처가 표시된다.
- 답변 생성 중 텍스트가 점점 늘어난다.
- `done`을 받으면 최종 답변과 실행 시간이 나오고 전송 버튼이 다시 활성화된다.
- 답변의 인용 번호와 참고 문서 목록을 대조할 수 있다.
- 인증 오류, 생성 실패, 연결 중단 시 오류 안내가 표시된다.

## RAG Agent 연결과 스트리밍 복습 Q&A
- Q. RAG 스트리밍 API에서 SSE 응답의 Content-Type과 이벤트 구분 방식은?
  A. `text/event-stream`. 각 이벤트는 `event:`·`data:` 줄로 쓰고 빈 줄(`\n\n`)로 끝난다.
- Q. LangGraph `astream()`에서 `messages`와 `updates` 모드는 각각 무엇을 주나?
  A. `messages`는 생성 중인 (메시지 조각, 메타데이터), `updates`는 노드가 끝날 때 그 노드의 상태 변경을 준다.
- Q. RAG 그래프를 요청마다 만들지 않고 어디에 두나?
  A. lifespan에서 한 번 만들어 `app.state.rag_agent`에 두고, Router에서 `request.app.state.rag_agent`로 꺼낸다.
- Q. 스트리밍이 시작된 뒤 그래프 실행이 실패하면 왜 HTTP 500을 못 보내나?
  A. 응답 헤더가 이미 나가 상태 코드가 확정됐기 때문이다. 그래서 로그를 남기고 SSE `error` 이벤트로 알린다.
- Q. React RagPage에서 token 조각을 `setAnswer(current => current + data.content)`로 누적하는 이유는?
  A. 함수형 갱신은 항상 최신 상태를 받으므로 조각이 연달아 도착해도 순서대로 빠짐없이 이어 붙는다.
