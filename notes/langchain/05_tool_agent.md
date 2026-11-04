---
part: langchain
lesson: Tool and Basic Agent
order: 5
source_type: ipynb
tags: [tool, agent, bind-tools, tool-calls, toolmessage, function-calling, tmdb]
source: C:\Users\tnwls\aim-ai-agent\langchain_\05-tool-agent_answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Tool and Basic Agent

## Tool and Basic Agent 요약
LangChain `@tool`로 Python 함수를 Tool로 만들고 `bind_tools()`로 Gemini에 연결한 뒤, 모델 호출 → Tool 실행 → `ToolMessage` 전달을 반복하는 기본 Agent 루프를 직접 구현한다. 실습 문제는 TMDB API로 영화 목록·상세를 조회하는 세션별 Agent다.

## LangChain Tool이란
Tool은 LLM이 외부 세계와 상호작용하게 해 주는 함수다. LLM은 텍스트만 생성할 수 있지만 Tool을 통해 웹 검색, 계산, 외부 API 조회를 할 수 있다. LLM이 Tool이 필요하다고 판단하면 Tool 이름과 인자를 반환하고, 실제 실행은 개발자 코드가 한다.
- Tool 필요: LLM이 Tool 이름 + 인자 반환 → 개발자가 Tool 실행 → 결과를 LLM에 전달 → LLM이 자연어 최종 응답.
- Tool 불필요: LLM이 바로 텍스트로 응답.

예: "서울 날씨 알려줘"라는 질문에 LLM은 날씨를 모르므로 "날씨 검색 Tool을 city='서울'로 호출"을 요청하고, 개발자가 실행한 결과를 받아 답변을 정리한다.

## LangChain @tool 데코레이터와 parse_docstring
`@tool`은 Python 함수를 LangChain Tool 객체로 바꾸는 가장 간단한 방법이다. LLM은 Tool의 `name`, `description`(docstring), `args_schema`(타입 힌트)를 보고 어떤 Tool을 어떤 인자로 부를지 정하므로 docstring과 타입 힌트가 매우 중요하다.

`@tool(parse_docstring=True)`에 Google 스타일 `Args:` docstring을 쓰면 인자별 설명이 `args_schema`의 description에 자동으로 들어간다.
```python
from langchain_core.tools import tool

@tool(parse_docstring=True)
def search_weather(city: str) -> str:
    """주어진 도시의 현재 날씨를 검색한다.

    Args:
        city: 날씨를 검색할 도시 이름. 예: '서울', '부산'
    """
    weather_data = {"서울": "맑음, 22도, 습도 45%", "부산": "흐림, 19도, 습도 72%"}
    return weather_data.get(city, f"{city}의 날씨 정보를 찾을 수 없습니다.")

print(search_weather.name, search_weather.description)
print(search_weather.args_schema.model_json_schema())
print(search_weather.invoke({"city": "서울"}))  # 맑음, 22도, 습도 45%
```
- Tool이 된 함수는 `search_weather(city=...)`가 아니라 `.invoke({"city": ...})`로 호출한다.
- 원문 예시 데이터에는 제주도 있다(줄임).

## LangChain Tool 설계 원칙과 분리 기준
LangChain Tool을 잘 만들기 위한 원칙은 다음과 같다.
- 명확한 이름: `func1`보다 `search_weather`.
- 구체적인 설명: "데이터를 가져온다"보다 "주어진 도시의 현재 날씨 정보를 검색한다".
- 타입 힌트 필수: `city: str`처럼 넣을 값을 알려 준다.
- 예시 포함: docstring에 입력 예시를 넣으면 정확도가 오른다.
- 에러 메시지: 실행 실패 시 LLM이 이해할 수 있는 메시지를 반환한다.

Tool을 나누는 기준은 API 엔드포인트가 아니라 "LLM이 docstring만 보고 언제 쓸지 판단할 수 있는 단위"다. 용도가 다르면(검색 vs 상세 조회) 나누고, 파라미터 하나 차이면 합쳐도 된다. 너무 많으면 선택 정확도가 떨어지고, 너무 합치면 파라미터가 복잡해져 LLM이 헷갈린다.

## LangChain bind_tools로 Tool 바인딩
`bind_tools()`는 LLM에 사용 가능한 Tool 목록을 알려 준다. 바인딩된 모델은 질문을 보고 Tool 호출이 필요하면 `tool_calls`에 호출 정보를 담고(content는 비어 있을 수 있음), 필요 없으면 일반 텍스트를 content에 담는다. `bind_tools()`만으로는 Tool이 실행되지 않는다.
```python
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
llm_with_tools = llm.bind_tools([search_weather])

response = llm_with_tools.invoke("서울 날씨 알려줘")
print(response.content, response.tool_calls)

response2 = llm_with_tools.invoke("안녕하세요")
print(response2.tool_calls)  # []
```
```text
content: []
tool_calls: [{'name': 'search_weather', 'args': {'city': '서울'}, 'id': 'call_...', 'type': 'tool_call'}]
```
- 인사말에는 `tool_calls`가 빈 리스트이고 content에 일반 답변이 온다.

## Function Calling 비교: Google Gen AI SDK vs LangChain @tool
Function Calling을 Google Gen AI SDK로 직접 쓸 때와 LangChain `@tool`로 쓸 때의 차이는 다음과 같다.
- Tool 정의: SDK는 JSON 스키마를 직접 작성, LangChain은 Python 함수 + docstring.
- 파라미터: SDK는 properties를 수동 정의, LangChain은 타입 힌트에서 자동 추출.
- 결과 확인: SDK는 provider 고유 응답 구조, LangChain은 `AIMessage.tool_calls`로 표준화.
- 모델 교체: SDK는 API별 코드 재작성, LangChain은 ChatModel 한 줄만 변경.

## LangChain Tool 호출 루프로 기본 Agent 만들기
기본 Agent는 모델이 Tool을 요청하는 동안 "모델 호출 → Tool 실행 → `ToolMessage` 추가 → 모델 재호출"을 반복한다. 모델은 Tool을 직접 실행하지 않으므로 앱이 `tool_calls`를 읽어 실행한다.
```python
from langchain_core.messages import HumanMessage, ToolMessage

tools = [search_weather]
tool_map = {t.name: t for t in tools}
llm_with_tools = llm.bind_tools(tools)
MAX_ITERATIONS = 5

def run_agent(user_input: str) -> str:
    messages = [HumanMessage(content=user_input)]
    for _ in range(MAX_ITERATIONS):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        if not response.tool_calls:
            return response.content
        for tool_call in response.tool_calls:
            result = tool_map[tool_call["name"]].invoke(tool_call["args"])
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
    return "최대 반복 횟수를 초과했습니다."
```
- `tool_map`: 이름 → Tool 객체. `tool_call_id`: 어떤 요청의 결과인지 표시. `MAX_ITERATIONS`: 무한 호출 방지.

## LangChain 기본 Agent 실행 결과
기본 Agent `run_agent()`에 세 질문을 넣어 Tool 호출 동작을 확인한다.
```python
for q in ["서울 날씨 어때?", "서울이랑 부산 날씨 비교해줘", "안녕하세요!"]:
    print(run_agent(q))
```
```text
사용자: 서울이랑 부산 날씨 비교해줘
search_weather실행 - {'city': '서울'} - 맑음, 22도, 습도 45%
search_weather실행 - {'city': '부산'} - 흐림, 19도, 습도 72%
```
- 비교 질문에서는 모델이 한 번에 Tool 두 개를 요청한다. 인사에는 Tool 없이 답한다.
- 모델은 여러 Tool을 동시에 요청하거나 결과를 본 뒤 추가 Tool을 요청할 수 있으므로 반복 횟수 제한이 필요하다.
- 이 반복 구조는 이후 LangGraph에서 `ToolNode`와 `tools_condition`으로 구성한다.
- Gemini 3 응답의 `content`는 `[{'type': 'text', 'text': ..., 'extras': {'signature': ...}}]` 블록 리스트로 출력된다.

## Tool Agent 실습 문제: TMDB 영화 목록과 상세 조회 Agent
Tool Agent 실습 문제는 TMDB API와 LangChain Tool로 영화 목록을 조회하고, 후속 질문에서 특정 영화의 상세 정보를 조회하는 Agent를 만드는 것이다. API 키는 `.env`에 둔다.
- `get_movie_list`: 인기/현재 상영/개봉 예정 목록에서 영화 ID, 제목, 개봉일만 조회.
- `get_movie_detail`: 영화 ID로 줄거리, 장르, 러닝타임 등 상세 조회.

목록 Tool은 상세 정보를 주지 않으므로 후속 질문은 목록의 영화 ID로 상세 Tool을 불러야 한다. 같은 세션에서 다음 두 질문을 순서대로 실행한다.
```text
현재 상영 중인 영화 5개를 알려줘.
그중 첫 번째 영화의 줄거리와 러닝타임을 알려줘.
```
다른 세션에서 바로 "그중 첫 번째 영화의 줄거리를 알려줘."라고 하면 이전 목록을 모른다고 답하는지도 확인한다.

## TMDB 실습 풀이 1단계: Tool 없이 직접 호출해 보기
TMDB 실습 풀이는 먼저 LLM 없이 일반 함수로 흐름(목록 → 첫 영화 ID → 상세)을 확인한다. 인증은 환경 변수의 토큰을 Bearer 헤더로 보낸다.
```python
import os, requests
TMDB_TOKEN = os.getenv("TMDB_TOKEN")
HEADERS = {"authorization": f"Bearer {TMDB_TOKEN}"}

def get_movies(size: int = 10):
    r = requests.get("https://api.themoviedb.org/3/movie/now_playing", headers=HEADERS)
    data = r.json()
    return [{"id": m.get("id"), "title": m.get("title"),
             "release_date": m.get("release_date")} for m in data.get("results")][:size]

def get_movie_by_id(id: int):
    return requests.get(f"https://api.themoviedb.org/3/movie/{id}", headers=HEADERS).json()

first_id = get_movies(size=5)[0]["id"]
print(get_movie_by_id(first_id).get("overview"))
```
- 출력: 첫 영화 ID와 영어 줄거리 한 단락.
- 원문은 try/except와 함수별 헤더를 두었다(헤더 공통화·예외 생략으로 줄임).
- 문제 설명은 `TMDB_API_KEY`라 했지만 풀이 코드는 `TMDB_TOKEN` 환경 변수를 쓴다.

## TMDB 실습 풀이 2단계: @tool로 영화 Tool 정의
TMDB 실습 풀이 2단계는 두 함수를 `@tool(parse_docstring=True)`로 바꾸고, 목록 Tool에 `category` 인자를 추가해 상영 중/인기/순위/개봉 예정을 고르게 한다.
```python
@tool(parse_docstring=True)
def get_movies_tool(category: str, size: int = 10):
    """TMDB API를 활용해서 상영중인 영화의 목록을 가져오는 함수.

    Args:
        category: 어떤 영화의 목록을 가져올건지 정하는 파라미터. 예 : now_playing - 현재 상영중, popular - 인기있는, top_rated - 순위권인, upcoming - 개봉 예정인.
        size: 영화 목록의 사이즈. 예: 5, 3, 7
    """
    URL = f"https://api.themoviedb.org/3/movie/{category}"
    ...  # 1단계 get_movies와 같은 요청·변환, 예외 시 {} 반환

@tool(parse_docstring=True)
def get_movie_by_id_tool(id: int):
    """TMDB API를 활용해서 주어진 ID에 해당하는 영화의 상세 정보를 가져오는 함수.

    Args:
        id: TMDB API에서 활용되는 영화 id. 예 : 969681
    """
    ...  # 1단계 get_movie_by_id와 같음
```
- 스키마 확인 결과 `category`는 required, `size`는 default 10인 integer로 잡힌다.
- 원문 코드는 `response.raise_for_status`를 괄호 없이 써서 실제로 호출되지 않는다. `response.raise_for_status()`로 써야 HTTP 오류가 예외로 잡힌다. (내 메모)

## TMDB 실습 풀이 3단계: 영화 Agent 루프
TMDB 실습 풀이 3단계는 두 Tool을 바인딩해 기본 Agent 루프를 돌린다. 호출마다 새 메시지 리스트라 후속 질문에선 이전 목록을 모른다.
```python
tools = [get_movies_tool, get_movie_by_id_tool]
tool_map = {func.name: func for func in tools}
llm_with_movie_tool = ChatGoogleGenerativeAI(model=MODEL_NAME).bind_tools(tools)

def run_agent(request: str, max_attempt: int = 5):
    messages = [HumanMessage(content=request)]
    for _ in range(max_attempt):
        response = llm_with_movie_tool.invoke(messages)
        messages.append(response)
        if not response.tool_calls:
            return response.content
        for tool_call in response.tool_calls:
            result = tool_map.get(tool_call.get("name")).invoke(tool_call.get("args"))
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_call.get("id")))

run_agent("상영중인 영화 5개 가져와줘.")
```
- 모델이 `get_movies_tool`을 `{"category": "now_playing", "size": 5}`로 호출한다.
- 원문은 반환 전에 전체 messages를 `pprint`한다(생략).

## TMDB 실습 풀이 4단계: 세션별 메모리를 가진 영화 Agent
TMDB 실습 풀이 4단계는 사용자별 `InMemoryChatMessageHistory`에 Human/AI/Tool 메시지를 모두 저장해 후속 질문을 잇는다.
```python
memory = {"user-1": InMemoryChatMessageHistory(), "user-2": InMemoryChatMessageHistory()}

def run_agent(user_id: str, request: str, max_attempt: int = 5):
    user_memory = memory.get(user_id)
    user_memory.add_message(HumanMessage(content=request))
    for _ in range(max_attempt):
        response = llm_with_movie_tool.invoke(user_memory.messages)
        user_memory.add_message(response)
        if not response.tool_calls:
            return response.content
        for tc in response.tool_calls:
            result = tool_map[tc["name"]].invoke(tc["args"])
            user_memory.add_message(ToolMessage(content=str(result), tool_call_id=tc["id"]))

run_agent("user-1", "상영중인 영화 5개 가져와줘.")
run_agent("user-2", "첫번째 영화의 줄거리와 러닝타임 알려줘.")  # 목록을 모름
```
- 원문 변수명은 `momory`(오타), 변수명 줄임.
- 답안은 user-2 후속 질문만 실행한다. 같은 세션 확인은 user-1로 한 번 더 물으면 된다. (내 메모)

## Tool and Basic Agent 복습 Q&A
- Q. LangChain `bind_tools()`를 하면 Tool이 자동으로 실행되나?
  A. 아니다. 모델은 `tool_calls`로 호출을 요청할 뿐이고, 앱 코드가 Tool을 실행해 `ToolMessage`로 결과를 돌려줘야 한다.
- Q. `@tool(parse_docstring=True)`의 효과는?
  A. Google 스타일 `Args:` docstring에서 인자별 설명을 뽑아 `args_schema`의 description에 넣어 LLM이 인자 의미를 알게 한다.
- Q. 기본 Agent 루프에서 `ToolMessage`의 `tool_call_id`는 왜 필요한가?
  A. 어떤 tool_call 요청에 대한 결과인지 모델이 연결할 수 있게 하기 위해서다.
- Q. Agent 루프에 최대 반복 횟수를 두는 이유는?
  A. 모델이 Tool 결과를 보고 계속 추가 Tool을 요청해 무한 호출되는 것을 막기 위해서다.
- Q. TMDB 영화 Agent에서 "첫 번째 영화의 줄거리" 후속 질문에 답하려면?
  A. 세션별 히스토리에 이전 Human/AI/Tool 메시지를 모두 저장해 다음 호출에 넘겨야 모델이 목록의 영화 ID로 상세 Tool을 부를 수 있다.
