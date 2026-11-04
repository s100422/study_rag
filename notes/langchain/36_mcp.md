---
part: langchain
lesson: MCP
order: 36
source_type: ipynb
tags: [mcp, langchain-mcp-adapters, fastmcp, json-rpc, tool-calling, claude-code, a2a, agent]
source: C:\Users\tnwls\aim-ai-agent\langchain_\36-mcp.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# MCP

## MCP 요약
MCP(Model Context Protocol)의 개념과 구성 요소를 정리하고, 가상 날씨 데이터를 주는 MCP 서버에 `langchain-mcp-adapters`로 연결해 LangChain Agent에서 Tool·Resource·Prompt를 쓴 뒤, 같은 서버를 Claude Code에도 등록해 본다. 마지막에 Smithery와 A2A 프로토콜을 소개한다.

## MCP(Model Context Protocol)란
MCP는 AI 애플리케이션이 외부 도구와 데이터를 쓰기 위한 표준 통신 규약이다. 앱마다 도구 연결 방식이 다르면 같은 기능도 앱별로 다시 연결해야 하지만, MCP로 표준화하면 하나의 서버 기능을 여러 MCP 지원 앱이 재사용할 수 있다. 각 앱은 서버의 Tool 목록과 입력 형식을 조회한 뒤 필요한 Tool을 호출한다.
```text
LangGraph Agent ──┐
                  ├── 날씨 MCP 서버 ── TOOL
Claude Code ──────┘
```

## Tool Calling과 MCP의 차이
Tool Calling은 LLM이 외부 도구를 쓰기 위한 기능이고, MCP는 앱과 도구·데이터 사이의 표준 통신 규약이다.
- LangChain `@tool`: Python 함수를 Tool로 등록하고 앱이 직접 그 함수를 호출한다. 함수나 패키지를 가져와 LangChain 앱 안에서 재사용한다. 앱에 필요한 함수·API를 바로 연결할 때 적합하다.
- MCP 서버 Tool: 서버 기능을 MCP Tool로 등록하고, 앱의 요청을 받아 서버가 실행한다. MCP 지원 앱이면 서버에 연결해 재사용한다. 여러 앱이 같은 도구를 공유하거나 기존 MCP 서버를 쓸 때 적합하다.

## MCP 구성 요소: Host, Client, Server
MCP 연결 구조에는 세 역할이 있다.
- Host: 모델·사용자 대화·도구 사용을 관리하는 AI 앱. 예: LangGraph Agent 앱, Claude Code
- Client: Host 안에서 MCP 서버와 통신하는 연결. 예: `MultiServerMCPClient`가 관리하는 연결
- Server: Tool·Resource·Prompt를 제공하는 프로그램. 예: `weather_server.py`

모델은 서버와 직접 통신하지 않는다. Host가 모델의 요청을 받아 Client를 통해 실행한다.

## MCP 서버 기능: Tool, Resource, Prompt
MCP 서버는 기능과 데이터를 세 형태로 제공할 수 있다.
- Tool: 실행 가능한 함수. 모델이 호출을 제안하고 앱이 실행한다. 예: 현재 날씨·예보 조회
- Resource: URI로 읽는 데이터. 앱이 골라서 사용한다. 예: 지원 도시 목록
- Prompt: 인자를 받아 만드는 메시지 템플릿. 사용자나 앱이 선택한다. 예: 도시별 날씨 요약 요청

서버가 셋을 다 구현할 필요는 없고 Client마다 지원 범위도 다르다. `get_tools()`는 Tool만 가져오므로 Resource와 Prompt는 따로 읽어 모델에 전달해야 하며, Prompt를 가져오는 것만으로 모델이 실행되지는 않는다.

## MCP 메시지 구조: JSON-RPC 2.0
MCP Client와 Server는 JSON-RPC 2.0 형식으로 통신한다. 초기화 후 Client는 `tools/list`로 도구 목록·입력 형식을 확인하고 `tools/call`로 실행한다. (요청·응답을 한 블록으로 합쳐 단순화)
```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
 "params": {"name": "get_current_weather", "arguments": {"city": "서울"}}}

{"jsonrpc": "2.0", "id": 1,
 "result": {"content": [{"type": "text", "text": "서울의 현재 기온은 22°C, 습도는 50%입니다."}]}}
```
- `jsonrpc`: JSON-RPC 버전(MCP 버전과 다름)
- `id`: 요청과 응답을 짝짓는 식별자
- `method`: MCP 작업 이름. `tools/call`은 도구 실행
- `params.name` / `params.arguments`: 실행할 도구 이름과 입력값
- `result.content`: 도구가 반환한 콘텐츠 목록

## MCP 실습 1단계: 패키지 설치와 날씨 서버 실행
MCP 실습에는 `mcp`(Python MCP SDK, `FastMCP`로 데코레이터 기반 서버 작성)와 `langchain-mcp-adapters`(MCP Tool을 LangChain Tool로 변환)를 설치한다.
```bash
pip install "mcp==1.30.0" "langchain-mcp-adapters==0.3.2"
python mcp_examples/weather_server.py
```
- 서버는 같은 Python 환경의 별도 터미널에서, 노트북 폴더 기준으로 실행한다.
- `http://127.0.0.1:8000/mcp`에서 요청을 받고, 끝나면 `Ctrl+C`로 종료한다.
- 서울·부산·제주의 실습용 가상 날씨를 반환하므로 외부 날씨 API나 키가 필요 없다.
- Tool 두 개: `get_current_weather(city)`(기온·습도), `get_weather_forecast(city)`(최저·최고 기온, 강수 확률).

## MCP 실습 2단계: MultiServerMCPClient로 Tool 목록 가져오기
MCP 서버 연결은 `MultiServerMCPClient`에 서버 이름별 연결 정보를 넘겨 만든다. `get_tools()`는 Tool 목록만 가져오며 아직 Tool이나 LLM을 호출하지 않는다.
```python
weather_client = MultiServerMCPClient({"weather": {
    "transport": "streamable_http",
    "url": "http://127.0.0.1:8000/mcp",
    "timeout": 10,
}})
weather_tools = await weather_client.get_tools()
weather_tool_map = {tool.name: tool for tool in weather_tools}
for tool in weather_tools:
    print(tool.name, tool.description, json.dumps(tool.args, ensure_ascii=False))
```
- `transport: "streamable_http"`: HTTP로 실행 중인 서버에 붙는 방식.
- 출력: 두 Tool의 이름·설명과 입력 스키마. `city`는 `enum: ["서울", "부산", "제주"]`인 string이다.
- 노트북 셀에서 top-level `await`를 쓴다.

## MCP 실습 3단계: LLM 없이 Tool 직접 호출
MCP Tool은 이름과 입력 형식을 알면 모델 없이 `ainvoke`로 직접 부를 수 있다. 연결 문제와 모델의 도구 선택 문제를 분리해 확인할 때 유용하다.
```python
current = await weather_tool_map["get_current_weather"].ainvoke({"city": "서울"})
forecast = await weather_tool_map["get_weather_forecast"].ainvoke({"city": "서울"})
```
- 어댑터 반환값은 텍스트이거나 콘텐츠 블록 목록일 수 있다. 이 예제는 `[{'type': 'text', 'text': '<JSON 문자열>', 'id': ...}]` 형태다.
- JSON 안에 도시, 값(현재 22°C·습도 50%, 예보 18~25°C·강수 20%), 단위(`units`)가 들어 있다.

## MCP 실습 4단계: create_agent에 MCP Tool 연결
MCP에서 가져온 Tool은 일반 LangChain Tool처럼 `create_agent`에 넘긴다. 어댑터 Tool은 비동기라서 Agent도 `await agent.ainvoke(...)`로 호출한다.
```python
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
weather_agent = create_agent(
    model=llm,
    tools=weather_tools,
    system_prompt="날씨는 반드시 도구로 조회하세요. 현재 값과 예보를 구분하고 단위를 포함해 "
                  "한국어로 답하세요. 조회에 실패하거나 값이 없으면 추측하지 말고 확인할 수 없다고 안내하세요.",
)
resp = await weather_agent.ainvoke(
    {"messages": [("user", "서울의 현재 날씨와 예보를 알려줘.")]},
    config={"recursion_limit": 12},
)
print(resp["messages"][-1].text)
```
- 모델이 `get_current_weather`와 `get_weather_forecast`를 한 번에 두 개 호출 요청하고, 답변은 현재(22°C, 50%)와 예보(18°C/25°C/20%)를 단위와 함께 나눠 보여준다.
- 메시지를 돌며 `tool_calls`가 있는 메시지와 `type == "tool"` 메시지를 출력하면 호출 과정을 볼 수 있다.

## MCP 날씨 서버 코드 구성(FastMCP)
MCP 날씨 서버 파일 `mcp_examples/weather_server.py`에서 확인할 FastMCP 요소다. (서버 소스 자체는 노트북에 없음)
- `FastMCP(...)`: MCP 서버 객체 생성
- `@mcp.tool()`: 함수를 Tool로 등록. 함수 이름과 docstring이 Tool 이름·설명이 된다.
- `@mcp.resource(...)`: 읽을 데이터를 Resource로 등록
- `@mcp.prompt()`: 메시지 템플릿을 Prompt로 등록
- `mcp.run(...)`: 서버 실행

## MCP 실습 5단계: Resource와 Prompt 읽어 Agent에 전달
MCP Resource와 Prompt는 Client에서 따로 읽은 뒤 문자열로 합쳐 Agent에 넘긴다.
```python
resources = await weather_client.get_resources("weather", uris="weather://cities")
cities_text = resources[0].as_string()

weather_messages = await weather_client.get_prompt(
    "weather", "weather_briefing", arguments={"city": "서울"}
)
prompt_text = weather_messages[0].text

request = f"지원 도시:\n{cities_text}\n\n{prompt_text}"
briefing = await weather_agent.ainvoke({"messages": [("user", request)]},
                                       config={"recursion_limit": 12})
```
- `get_resources()`는 목록을 반환하므로 첫 항목을 `as_string()`으로 꺼낸다.
- `get_prompt()`는 메시지 목록을 반환하며, 가져오기만 해서는 LLM이 호출되지 않는다.
- 노트북에는 이 세 셀의 출력이 저장되어 있지 않다.

## MCP를 Claude Code에 연결하기
MCP 서버는 Claude Code(MCP Host)에도 같은 주소로 붙일 수 있다. Claude Code는 자체 모델·인증을 쓰므로 LangGraph Agent나 Gemini API 키를 넘길 필요가 없다. 날씨 서버를 켜 둔 채 다른 터미널에서 등록한다.
```bash
claude mcp add --transport http --scope local weather http://127.0.0.1:8000/mcp
claude mcp list
claude mcp get weather
claude
```
- Claude Code 대화창에서 `/mcp`로 `weather` 연결 상태와 Tool을 확인한다.
- "weather의 두 도구로 서울 현재 날씨와 예보를 알려줘"처럼 요청하고, 실행 승인 때 Tool 이름과 인자를 확인한다.
- 핵심: 실행 중인 같은 MCP 서버를 LangGraph Agent와 Claude Code가 각각 호출했다.

## MCP 서버 찾기: Smithery
Smithery는 공개된 MCP 서버를 검색하고 AI 앱에 연결하도록 돕는 서비스다.
- 웹 검색, 개발 문서 조회, 브라우저 제어 등 필요한 기능의 서버를 찾는다.
- 서버 설명, 제공 Tool, 연결 방법을 확인한다.
- 필요한 서비스 계정을 연결하고 인증 정보를 관리한다.

MCP는 통신 규약이고 Smithery는 서버를 찾아 연결하는 서비스일 뿐이다. 서버에 직접 연결할 수 있으므로 MCP 사용에 Smithery가 필수는 아니다.

## A2A 프로토콜과 MCP 비교
A2A(Agent2Agent)는 독립적인 AI Agent끼리 업무를 요청하고 진행 상태와 결과를 주고받는 표준 통신 규약이다. 모델·프레임워크가 달라도 양쪽이 A2A를 지원하면 협업할 수 있다. 예: 여행 계획 Agent가 숙소 조사 Agent에 "부산에서 예산에 맞는 숙소 후보 비교"를 맡기고, 조사 Agent는 부족한 조건(날짜·예산)을 되물을 수 있다.
- MCP: 앱 ↔ 도구·데이터. 외부 기능 호출과 데이터 활용. 예: 숙소 검색 Tool에 지역·날짜 전달
- A2A: Agent ↔ Agent. 업무 위임, 상태·결과 교환. 예: 숙소 조사 Agent에 후보 비교 요청

둘은 함께 쓸 수 있다. Agent끼리는 A2A로 소통하고, 각 Agent 내부에서는 MCP로 도구를 쓴다.

## MCP 복습 Q&A
- Q. MCP 구조에서 모델은 MCP 서버와 직접 통신하나?
  A. 아니다. Host가 모델의 요청을 받아 Host 안의 Client를 통해 서버를 호출한다.
- Q. `MultiServerMCPClient.get_tools()`로 Resource와 Prompt도 가져와지나?
  A. 아니다. Tool만 가져온다. Resource는 `get_resources()`, Prompt는 `get_prompt()`로 따로 읽어 모델에 전달해야 한다.
- Q. MCP에서 도구 목록 조회와 도구 실행에 쓰는 JSON-RPC method는?
  A. 목록 조회는 `tools/list`, 실행은 `tools/call`이다.
- Q. MCP Agent를 `invoke`가 아닌 `ainvoke`로 호출하는 이유는?
  A. MCP 어댑터의 Tool이 비동기로 실행되기 때문이다.
- Q. MCP와 A2A의 차이는?
  A. MCP는 앱과 도구·데이터를 연결하고, A2A는 독립 Agent끼리 업무를 위임하고 상태·결과를 주고받는다.
