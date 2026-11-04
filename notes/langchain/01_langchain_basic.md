---
part: langchain
lesson: LangChain Basic
order: 1
source_type: ipynb
tags: [langchain, chatmodel, prompttemplate, lcel, runnable, runnablepassthrough, batch, stream]
source: C:\Users\tnwls\aim-ai-agent\langchain_\01-langchain-basic_answer.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# LangChain Basic

## LangChain Basic 요약
LangChain의 기본 구성 요소(ChatModel, PromptTemplate, OutputParser)를 LCEL `|` 파이프라인으로 연결하고, Runnable 인터페이스(RunnableLambda, RunnablePassthrough, batch/stream), 토큰 사용량, 에러 처리, 캐싱을 Gemini 모델로 실습한다. 마지막에 용도별 체인 실습 문제 4개와 풀이가 있다.

## LangChain이란
LangChain은 LLM 애플리케이션을 쉽게 만들도록 돕는 Python 프레임워크다. 여러 LLM 제공자를 같은 인터페이스로 쓸 수 있고, 프롬프트 관리, 체인 구성, 메모리, Tool 사용 같은 기능을 제공한다.

LLM 앱 개발은 보통 이 순서로 발전하며, LangChain은 2~5단계를 쉽게 해 준다.
- 1단계 단순 API 호출: LLM API를 직접 호출해 챗봇을 만든다.
- 2단계 체인 구성: 프롬프트 + 모델 + 파서를 연결한다.
- 3단계 메모리/Tool: 대화 기억과 외부 도구(검색, DB)를 붙인다.
- 4단계 RAG: 자체 문서를 검색해 LLM에 맥락으로 준다.
- 5단계 Agent: LLM이 스스로 판단해 도구를 조합한다.

## LangChain 생태계 패키지 구성
LangChain은 여러 패키지로 된 생태계다.
- `langchain-core`: 기본 인터페이스, LCEL, 메시지 타입 등 핵심.
- `langchain`: 체인, 메모리, 에이전트 등 고수준 기능.
- `langchain-google-genai`: `ChatGoogleGenerativeAI` 등 Gemini 연동.
- `langchain-community`: 서드파티 Tool, 벡터 DB 등 커뮤니티 통합.
- `langgraph`: 상태 기반 Agent 프레임워크.

```bash
pip install google-genai langchain langchain-google-genai langchain-community
```
- API 키는 프로젝트 루트 `.env`에 `GEMINI_API_KEY=...` 형태로 두고 `load_dotenv()`로 읽는다. Gemini SDK와 `ChatGoogleGenerativeAI`가 이 환경 변수를 자동으로 사용한다.

## LangChain을 사용하는 이유: 직접 구현과 비교
Gemini API를 직접 호출해도 앱을 만들 수 있지만 기능이 늘수록 직접 구현할 것이 많아진다. LangChain이 대신해 주는 부분은 다음과 같다.
- 프롬프트 템플릿: 문자열 포맷팅 대신 `ChatPromptTemplate`.
- 모델 교체: API별 코드 재작성 대신 모델 이름 한 줄 변경.
- 대화 메모리: 히스토리 리스트 직접 관리 대신 `RunnableWithMessageHistory`.
- Tool 사용: JSON 스키마 작성·파싱 대신 `@tool` 데코레이터.
- RAG: 임베딩/검색/주입 직접 구현 대신 `Retriever` + 체인.
- 체인 연결: 함수 호출 순서 관리 대신 `|` 파이프라인.

단순한 1회 호출은 직접 호출이 더 간단하고, 기능이 많아질수록 LangChain의 가치가 커진다.

## Gemini 직접 호출과 LangChain 호출 비교
같은 Gemini 모델을 Gemini SDK(Interactions API)와 LangChain으로 각각 호출해 번역을 시킨다. 노트북은 `MODEL_NAME = "gemini-3.6-flash"`를 공통으로 쓴다.
```python
from google import genai
client = genai.Client()  # GEMINI_API_KEY 환경 변수를 자동으로 읽음
interaction = client.interactions.create(
    model=MODEL_NAME,
    system_instruction="너는 친절한 한국어 번역가야. 다음 문장을 번역해줘: ",
    input="Hello, how are you?",
)
print(interaction.output_text)

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
llm = ChatGoogleGenerativeAI(model=MODEL_NAME)
response = llm.invoke([
    SystemMessage(content="너는 친절한 한국어 번역가야. 다음 문장을 번역해줘: "),
    HumanMessage(content="Hello, how are you?"),
])
print(response.content)
```
- 직접 호출은 Gemini 최신 기능을 바로 쓸 때, LangChain은 여러 구성 요소를 연결할 때 편하다.
- `invoke()`는 모든 LangChain 구성 요소(Runnable)의 기본 실행 메서드다. 무언가를 실행할 땐 `invoke()`를 쓴다.

## LangChain ChatModel과 메시지 타입
ChatModel은 메시지 리스트를 받아 AI 응답 메시지를 돌려주는 LangChain의 LLM 객체다. 메시지 타입은 세 가지다.
- `SystemMessage`(system): LLM의 역할과 행동 설정.
- `HumanMessage`(user): 사용자 입력.
- `AIMessage`(assistant): LLM의 응답.

```python
llm = ChatGoogleGenerativeAI(model=MODEL_NAME)
messages = [
    SystemMessage(content="너는 Python 전문가야."),
    HumanMessage(content="리스트 컴프리헨션이 뭐야?"),
]
response = llm.invoke(messages)
pprint(response.content)
pprint(response.usage_metadata)
pprint(response.tool_calls)
```
- 같은 `llm` 변수에 `ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")`처럼 다른 모델을 넣어도 `invoke()` 방식은 그대로다.

## LangChain AIMessage 응답 객체의 속성
ChatModel의 `llm.invoke(messages)`는 문자열이 아니라 `AIMessage` 객체를 반환한다. 주요 속성은 다음과 같다.
- `response.content`: 모델이 생성한 실제 답변.
- `response.usage_metadata`: 입력·출력·전체 토큰 사용량.
- `response.response_metadata`: 모델명, 종료 이유 등 제공자별 정보.
- `response.tool_calls`: 모델이 요청한 도구 호출 목록. 도구를 안 쓰면 빈 리스트.
- `response.id`: 응답 식별자.

답변 텍스트만 필요하면 `response.content`를, 토큰이나 Tool 호출까지 다루면 객체 전체를 쓴다.

## LangChain PromptTemplate과 ChatPromptTemplate
PromptTemplate은 프롬프트에서 바뀌는 값을 `{변수}`로 분리해 재사용하게 해 준다. `invoke()`로 값을 넣는다.
```python
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate

prompt = PromptTemplate.from_template(
    "너는 {role} 전문가야. 다음 질문에 한국어로 답해줘.\n\n질문: {question}"
)
print(prompt.invoke({"role": "Python", "question": "데코레이터가 뭐야?"}).text)

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "너는 {role} 전문가야. 모든 답변은 한국어로 해줘."),
    ("human", "{question}"),
])
print(chat_prompt.invoke({"role": "Python", "question": "데코레이터가 뭐야?"}).messages)
```
- `PromptTemplate`: 역할 구분 없는 단일 문자열. `StringPromptValue`를 반환한다.
- `ChatPromptTemplate`: system/human/ai 역할을 나눈 채팅 프롬프트. `ChatPromptValue`(메시지 리스트)를 반환한다.

## f-string과 LangChain PromptTemplate 비교
f-string은 짧은 일회성 프롬프트에 적합하고, PromptTemplate은 여러 체인에서 재사용하거나 메시지 역할을 나눌 때 쓴다.
- 결과: f-string은 일반 문자열, PromptTemplate은 `PromptValue`.
- 변수: f-string은 현재 Python 변수를 바로 참조, PromptTemplate은 `input_variables`로 관리.
- 재사용: f-string은 생성 코드를 다시 실행, PromptTemplate은 템플릿 객체를 재사용.
- 체인 연결: PromptTemplate은 `prompt | llm | parser`로 바로 연결된다.
- 추적: PromptTemplate은 LangSmith에서 프롬프트 단계가 따로 보인다.

## LangChain OutputParser: StrOutputParser
OutputParser는 LLM 응답을 원하는 형태로 바꾸는 구성 요소다. `StrOutputParser`는 `AIMessage`에서 `content` 문자열만 꺼낸다.
```python
from langchain_core.output_parsers import StrOutputParser
parser = StrOutputParser()
result = parser.invoke(response)  # response: AIMessage
print(result)                      # 답변 문자열만 출력
```

## LCEL 파이프라인이란 (LangChain Expression Language)
LCEL은 `|` 연산자로 프롬프트, 모델, 파서를 연결해 체인을 만드는 문법이다. 데이터는 왼쪽에서 오른쪽으로 흐른다(입력 → PromptTemplate → ChatModel → OutputParser → 출력).
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "너는 {role} 전문가야."),
    ("human", "{question}"),
])
llm = ChatGoogleGenerativeAI(model=MODEL_NAME)
parser = StrOutputParser()
chain = prompt | llm | parser
result = chain.invoke({"role": "Python", "question": "리스트와 튜플의 차이가 뭐야?"})

# 위 체인과 같은 과정을 단계별로 실행
r1 = prompt.invoke({"role": "Python", "question": "리스트와 튜플의 차이가 뭐야?"})
r2 = llm.invoke(r1)
r3 = parser.invoke(r2)
```
- `prompt`: 변수를 받아 메시지 리스트를 만든다.
- `llm`: 메시지를 받아 AI 응답을 만든다.
- `parser`: 응답에서 문자열만 꺼낸다.

## LangChain Runnable 공통 인터페이스
Runnable은 LangChain 구성 요소가 따르는 공통 실행 인터페이스다. PromptTemplate, ChatModel, OutputParser와 이를 연결한 체인이 모두 Runnable이라 `invoke()`로 실행하고 `|`로 연결할 수 있다. 연결할 때는 앞 단계의 출력 타입이 다음 단계의 입력 타입과 맞아야 한다.
```python
from langchain_core.runnables import Runnable
components = {"prompt": prompt, "llm": llm, "parser": parser, "chain": chain}
for name, component in components.items():
    print(f"{name:>6}: {isinstance(component, Runnable)} ({type(component).__name__})")
```
- 네 객체 모두 `True`가 나온다. 클래스는 서로 달라도(`ChatPromptTemplate`, `ChatGoogleGenerativeAI`, `StrOutputParser`, `RunnableSequence`) 같은 인터페이스를 따른다. (클래스명은 내 메모)

## LangChain RunnableLambda: 함수를 Runnable로 변환
RunnableLambda는 lambda나 `def` 함수 같은 callable을 Runnable로 감싸 LCEL 파이프라인의 한 단계로 쓰게 한다. 주로 앞 단계 출력을 다음 단계가 원하는 형태로 바꾸는 어댑터로 쓴다.
```python
from langchain_core.runnables import RunnableLambda

def to_upper_text(text: str) -> str:
    return text.upper()

to_upper = RunnableLambda(to_upper_text)
add_label = RunnableLambda(lambda text: f"결과: {text}")
text_chain = to_upper | add_label
print(text_chain.invoke("hello langchain"))
```
```text
결과: HELLO LANGCHAIN
```
- 흐름: `"hello langchain"` → to_upper → `"HELLO LANGCHAIN"` → add_label → `"결과: HELLO LANGCHAIN"`.

## LangChain Prompt Chaining 패턴과 RunnableLambda 어댑터
Prompt Chaining은 한 체인의 출력을 다음 체인 입력으로 잇는 패턴이고, LCEL `|`가 곧 이 패턴이다. `chain1` 출력은 `str`인데 `chain2`는 `{"text": ..., "target": ...}` dict를 기대하므로 `chain1 | chain2`는 바로 연결되지 않는다. 중간에 RunnableLambda로 타입을 바꿔 준다.
```python
prompt1 = ChatPromptTemplate.from_messages([
    ("system", "너는 기술 블로거야. 주어진 주제에 대해 간단히 설명해줘."),
    ("human", "{topic}"),
])
prompt2 = ChatPromptTemplate.from_messages([
    ("system", "너는 초보자를 위한 튜터야. 다음 설명을 {target}도 이해할 수 있게 바꿔줘."),
    ("human", "{text}"),
])
chain1 = prompt1 | llm | parser
chain2 = prompt2 | llm | parser

combined_chain = chain1 | RunnableLambda(lambda x: {"text": x, "target": "초등학생"}) | chain2
print(combined_chain.invoke({"topic": "REST API"}))
```

## LangChain RunnablePassthrough와 assign
RunnablePassthrough는 입력을 그대로 넘기거나 입력에 새 키를 추가하는 Runnable이다.
- `RunnablePassthrough()`: 입력을 바꾸지 않고 전달.
- `RunnablePassthrough.assign(key=fn)`: 입력 dict를 유지하면서 `fn(입력)` 결과를 새 키로 추가.

RAG에서는 호출자가 질문만 넘기고 체인 안에서 검색 결과를 `context`로 붙인다.
```python
from langchain_core.runnables import RunnablePassthrough

knowledge_base = {
    "Python": "Python은 귀도 반 로섬이 개발한 범용 프로그래밍 언어입니다.",
    "LangChain": "LangChain은 언어 모델을 활용한 애플리케이션 개발을 돕는 프레임워크입니다.",
}
prompt = ChatPromptTemplate.from_messages([
    ("system", "다음 context를 참고하여 질문에 답해줘. context가 비어 있으면 모른다고 답해.\n\nContext: {context}"),
    ("human", "{question}"),
])
add_context = RunnablePassthrough.assign(
    context=lambda inputs: knowledge_base.get(inputs["question"], "")
)
chain = add_context | prompt | llm | parser
print(chain.invoke({"question": "Python"}))
```
- 원문은 `retrieve_context()` 함수로 분리했고 Java 항목도 있다(짧게 줄임). 없는 키("spring")를 넣으면 context가 비어 "모른다"고 답하게 된다.

## LangChain 토큰 사용량 모니터링
LLM API는 토큰 단위로 과금되며 실제 비용은 모델과 입력/출력 단가에 따라 다르다. Gemini 응답의 `usage_metadata`에서 토큰 수를 본다.
```python
response = llm.invoke("Python 클래스가 뭐야?")
usage = response.usage_metadata or {}
print(f"입력 토큰: {usage.get('input_tokens', 0)}")
print(f"출력 토큰: {usage.get('output_tokens', 0)}")
print(f"전체 토큰: {usage.get('total_tokens', 0)}")
```
- `usage_metadata`가 없을 수 있으므로 `or {}`와 `.get(..., 0)`으로 안전하게 읽는다.

## LangChain LLM API 에러 종류와 대응
LLM API 호출은 네트워크 요청이라 여러 이유로 실패할 수 있다.
- 429 Rate Limit: 짧은 시간에 요청이 너무 많음 → `max_retries`로 자동 재시도, 잠시 후 재실행.
- 408/504 Timeout: 응답이 너무 느림 → `timeout` 설정.
- 500 Server Error: Gemini 서버 장애 → 재시도 또는 fallback 모델.
- 401 Auth Error: API 키 오류 → `.env`의 키 확인.

에러 처리는 3단계로 구성한다: 일시적 오류는 재시도 → 계속 실패하면 fallback 모델 → 최종 실패는 `try/except`로 잡아 사용자에게 안전한 메시지를 보여 준다. 재시도 대기 시간은 1초 → 2초 → 4초처럼 늘어나는 exponential backoff 방식이다. 빠르게 무한 재시도하면 rate limit이 더 심해지기 때문이다.

## LangChain 에러 핸들링 코드: max_retries, timeout, with_fallbacks
LangChain에서는 모델 생성 시 재시도/타임아웃을 주고, `with_fallbacks()`로 백업 모델을 연결한다.
```python
llm = ChatGoogleGenerativeAI(model=MODEL_NAME, max_retries=3, timeout=30)

llm_main = ChatGoogleGenerativeAI(model=MODEL_NAME)
llm_backup = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")
llm_safe = llm_main.with_fallbacks([llm_backup])

try:
    result = llm_safe.invoke("안녕하세요")
    print(result.content)
except Exception as error:
    print(f"LLM 호출 실패: {error}")  # 개발자용 로그
    print("현재 답변을 생성할 수 없습니다. 잠시 후 다시 시도해주세요.")  # 사용자용
```
- 실무에서는 비싼 모델을 메인, 저렴한 모델을 백업으로 두는 경우가 많다.
- 실서비스에서는 `Exception` 하나로 뭉치지 말고 인증, Rate Limit, Timeout을 구분하고, 상세 오류나 API 키 같은 민감 정보는 사용자 화면이 아니라 서버 로그에만 남긴다.

## LangChain LLM 응답 캐싱: InMemoryCache
개발 중 같은 프롬프트를 반복 실행할 때 매번 API를 부르면 비용이 낭비된다. `InMemoryCache`를 켜면 동일 입력은 캐시된 응답을 즉시 돌려준다.
```python
from time import perf_counter
from langchain_core.caches import InMemoryCache
from langchain_core.globals import set_llm_cache

set_llm_cache(InMemoryCache())

start = perf_counter()
llm.invoke("Python이 뭐야?")        # API 호출 발생
print(f"첫 번째 호출: {perf_counter() - start:.2f}초")

start = perf_counter()
llm.invoke("Python이 뭐야?")        # 캐시에서 즉시 반환
print(f"두 번째 호출: {perf_counter() - start:.2f}초 (캐시)")

set_llm_cache(None)  # 실습 후 캐시 끄기
```

## LangChain Runnable 실행 메서드: invoke, batch, stream
모든 Runnable은 목적별 실행 메서드를 제공한다.
- 입력 하나: `invoke()` / 비동기 `ainvoke()`
- 입력 여러 개: `batch()` / 비동기 `abatch()`
- 스트리밍: `stream()` / 비동기 `astream()`

FastAPI처럼 이미 비동기로 도는 환경에서는 비동기 메서드를 쓴다.

`batch()`는 입력마다 별도 모델 호출을 만들고 LangChain이 이를 동시에 실행해 대기 시간을 줄인다. 하나의 HTTP 요청으로 묶어 보내는 기능이 아니다. 결과는 입력 순서대로 리스트로 온다. `max_concurrency`로 동시 요청 수를 제한해 rate limit을 피한다.
```python
chain = prompt | llm | StrOutputParser()  # prompt: system "한 문장으로 답해줘." + human "{question}"
results = chain.batch(
    [{"question": "Go가 뭐야?"}, {"question": "Swift가 뭐야?"},
     {"question": "Kotlin이 뭐야?"}, {"question": "C++이 뭐야?"}],
    config={"max_concurrency": 2},
)
```

## LangChain stream으로 응답 스트리밍
`stream()`은 응답이 다 만들어질 때까지 기다리지 않고 생성되는 chunk를 순서대로 돌려준다.
```python
chain = prompt | llm | StrOutputParser()
for chunk in chain.stream({"question": "Python의 장점 3가지를 알려줘"}):
    print(chunk, end="", flush=True)
print()
```
- 모델은 `AIMessageChunk`를 내고 `StrOutputParser`가 텍스트만 뽑으므로 반복문에서 바로 문자열을 쓴다(ChatGoogleGenerativeAI → AIMessageChunk → StrOutputParser → str).
- Gemini Interactions API를 직접 스트리밍하면 `event.event_type == "step.delta"`인지 확인하고 `event.delta.text`를 꺼내야 하는데, LangChain은 그 처리가 필요 없다.
- chunk는 한 토큰일 수도, 여러 토큰이나 문자 일부일 수도 있다. `end=""`로 이어 붙여 출력한다.

## LangChain batch/abatch와 asyncio.gather 비교
여러 비동기 호출을 동시에 돌리는 것만 목적이면 `asyncio.gather()`도 된다. LangChain의 기본 `abatch()`도 내부적으로 여러 `ainvoke()`를 병렬 실행한다. 차이는 어떤 추상화에서 실행을 관리하느냐다.
- 일반 동기 코드에서 같은 체인에 여러 입력: `batch()` (await 불필요).
- 비동기 코드에서 같은 체인에 여러 입력: `abatch()` (config, callback, tracing, 동시성 설정을 LangChain 방식으로 관리).
- 서로 다른 비동기 작업 조합: `asyncio.gather()`.

```python
import asyncio
gather_results = await asyncio.gather(*(chain.ainvoke(item) for item in inputs))
batch_results = await chain.abatch(inputs, config={"max_concurrency": 2})
```
- 노트북(Jupyter)에서는 최상위 `await`가 바로 동작한다.

## LangChain ChatGoogleGenerativeAI와 Gemini API 연동 방식
노트북에는 두 가지 Gemini 호출 방식이 나온다.
- `client.interactions.create(...)`: Gemini Interactions API. Gemini 최신 직접 호출 방식.
- `ChatGoogleGenerativeAI(...).invoke(...)`: 내부적으로 generateContent API(`models.generate_content()`, `models.generate_content_stream()`)를 쓰며 Runnable·LCEL 인터페이스를 제공한다.

Gemini 3.x 모델은 `temperature`, `top_p`, `top_k` 같은 샘플링 값을 직접 지정하지 말고 모델 기본값을 쓰는 것이 권장된다. (원문은 "결과 일관성이 필요하면 다음 방법을 우선 사용한다"로 끝나고 그 방법 목록이 빠져 있다.)

## LangChain 실습 문제 1: 말투 변환기 체인
LangChain 실습 문제 1은 같은 문장 "이 기능은 다음 주까지 구현이 어려울 것 같습니다."를 "해적", "조선시대 임금", "츤데레 애니메이션 캐릭터" 말투로 바꾸는 체인을 만드는 것이다. 예상 출력은 말투별로 변환된 문장 한 줄씩이다.

풀이: `{tone}`과 `{user_input}` 두 변수를 가진 프롬프트를 만들고 반복문 또는 `batch()`로 실행한다.
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "주어진 입력에 대해서 말투를 변경해줘. "
     "- 설명은 제외하고 변경된 문장만 출력해"
     "- {tone}의 특징을 최대한 잘 살려서 진행해."),
    ("human", "{user_input}"),
])
llm = ChatGoogleGenerativeAI(model=MODEL_NAME, max_retries=3)
chain = prompt | llm | StrOutputParser()
tones = ["해적", "조선시대 임금", "츤데레 애니메이션 캐릭터"]
text = "이 기능은 다음 주까지 구현이 어려울 것 같습니다."

for tone in tones:
    print(chain.invoke({"tone": tone, "user_input": text}))

results = chain.batch([{"tone": t, "user_input": text} for t in tones])
```
- 문자열이 줄바꿈 없이 이어 붙으므로 규칙 사이에 `\n`을 넣으면 더 읽기 좋다. (내 메모)

## LangChain 실습 문제 2: few-shot 감정분석기 체인
LangChain 실습 문제 2는 few-shot 예시로 출력 형식을 고정한 감정분석 체인이다. 출력 형식은 "감정(긍정/부정/중립), 강도(강함/약함), 근거(문장 속 표현)" 3줄이다.

풀이: few-shot 예시를 human/ai 메시지 쌍으로 넣는다. (답안 노트북에서는 예시 3쌍이 주석 처리되어 system 지시만으로 실행된다. 아래는 주석을 풀고 1쌍만 남겨 줄인 형태)
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "주어진 텍스트에 대해 감정 분석을 해라."),
    ("human", "이 제품 정말 최악이에요. 다시는 안 살 겁니다."),
    ("ai", """- 감정: 부정
- 강도: 강함
- 근거: "최악", "다시는 안 살 겁니다"와 같은 강한 부정 표현 사용"""),
    # 중립("괜찮은 것 같아요...")·긍정("완전 대박!...") 예시도 같은 형식으로 추가
    ("human", "{input_text}"),
])
chain = prompt | ChatGoogleGenerativeAI(model=MODEL_NAME, max_retries=3) | StrOutputParser()
for text in ["무난합니다", "이런 제품은 처음 봤습니다!", "이런 제품은 처음 봤습니다;;"]:
    print(chain.invoke({"input_text": text}))
```
- "처음 봤습니다!"와 ";;"처럼 같은 문장도 부호에 따라 감정이 달라지는 경계 사례를 테스트한다.

## LangChain 실습 문제 3: 언어 지정 번역기 체인
LangChain 실습 문제 3은 원본 언어와 대상 언어를 변수로 받는 번역 체인이다. 같은 체인으로 한→영, 영→일 등 여러 언어 쌍을 처리해야 한다.

풀이: `{original}`, `{target}`, `{user_input}` 변수를 두고, 입력이 원본 언어가 아니면 번역하지 않게 규칙을 넣는다.
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "{original}을 {target}으로 번역해줘."
     "- 추가적인 설명 말고 번역만 진행해."
     "- {user_input}이 {original}언어가 아니면 번역을 하지 마"),
    ("human", "{user_input}"),
])
chain = prompt | ChatGoogleGenerativeAI(model=MODEL_NAME, max_retries=3) | StrOutputParser()
result = chain.invoke({
    "original": "일본어",
    "target": "한국어",
    "user_input": "The weather is really nice today. I want to go for a walk.",
})
```
- 답안은 일부러 영어 문장을 "일본어→한국어"로 넣어 번역 거부 규칙을 테스트한다.
- 답안 주석: 규칙에 `user_input`을 변수가 아닌 글자로 쓰면 이 테스트가 실패해서 `{user_input}`으로 바꿨다고 적혀 있다.

## LangChain 실습 문제 4: RunnablePassthrough QA 체인
LangChain 실습 문제 4는 `{"question": "..."}`만 넘기면 dict에서 문서를 찾아 `context`로 붙이는 QA 체인이다.

풀이: 검색 함수(입력 dict를 받음)를 `RunnablePassthrough().assign(context=함수)`로 앞에 붙인다.
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "입력받은 <context>를 활용하여 <question>에 대해서 설명을 해줘. <context>가 비어있으면 답변하지 마."),
    ("human", "<context>{context}</context>\n\n<question>{question}</question>"),
])
knowledge_base = {
    "FastAPI": "FastAPI는 Python 기반의 고성능 웹 프레임워크이며, Starlette과 Pydantic을 기반으로 합니다.",
    "Django": "Django는 Python 기반의 풀스택 웹 프레임워크...",
}
def get_knowledge(input_dict):
    return knowledge_base.get(input_dict.get("question", ""), "")

add_context = RunnablePassthrough().assign(context=get_knowledge)
chain = add_context | prompt | ChatGoogleGenerativeAI(model=MODEL_NAME, max_retries=3) | StrOutputParser()
print(chain.invoke({"question": "FastAPI"}))
```
- 출력: FastAPI가 Starlette·Pydantic 기반 고성능 프레임워크라는 설명.
- 답안은 dict를 함수 안에 뒀다(코드 줄임).

## LangChain Basic 복습 Q&A
- Q. LCEL 체인 `prompt | llm | parser`에서 각 단계는 무엇을 하나?
  A. prompt는 변수로 메시지를 만들고, llm은 AIMessage를 생성하고, parser(StrOutputParser)는 그중 content 문자열만 꺼낸다.
- Q. LangChain에서 앞 체인의 str 출력을 dict 입력 체인에 연결하려면?
  A. `RunnableLambda(lambda x: {"text": x})` 같은 어댑터를 중간에 넣는다.
- Q. `RunnablePassthrough.assign()`은 RAG 체인에서 왜 쓰나?
  A. 입력 dict를 유지한 채 검색 결과를 `context` 키로 추가해, 호출자는 질문만 넘기면 되게 하려고.
- Q. LangChain `batch()`는 입력을 하나의 요청으로 묶어 보내나?
  A. 아니다. 입력마다 별도 호출을 동시에 실행하며, `max_concurrency`로 동시 수를 제한한다.
- Q. LangChain에서 LLM 호출 실패에 대비하는 3단계는?
  A. `max_retries`(exponential backoff 재시도) → `with_fallbacks()`로 백업 모델 → `try/except`로 사용자에게 안전한 메시지.
