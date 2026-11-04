---
part: langchain
lesson: Structured Output
order: 4
source_type: ipynb
tags: [structured-output, output-parser, pydantic, jsonoutputparser, with-structured-output, with-retry, with-fallbacks]
source: C:\Users\tnwls\aim-ai-agent\langchain_\04-structured-output.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Structured Output

## Structured Output 요약
Gemini 응답을 문자열, 리스트, dict, Pydantic 객체로 받는 Output Parser들과 `with_structured_output()`을 비교하고, 구조화 출력이 실패할 때 `include_raw` 진단, `with_retry()`, `with_fallbacks()`로 대응하는 방법을 `FakeListChatModel`로 재현한다.

## LangChain Output Parser란과 종류
Output Parser는 체인 끝에 붙여 LLM 응답을 필요한 Python 타입으로 바꾸는 구성 요소다.
- `StrOutputParser` → `str`: 일반 텍스트만 필요할 때.
- `CommaSeparatedListOutputParser` → `list[str]`: 단순 문자열 목록.
- `JsonOutputParser` → `dict`/`list`: 스키마 없는 유연한 JSON.
- `PydanticOutputParser` → Pydantic 객체: JSON 파싱 + 스키마 검증.
- `with_structured_output()` → Pydantic 객체 등: Gemini 네이티브 구조화 출력 사용.

Parser 방식은 `get_format_instructions()`로 만든 출력 규칙을 프롬프트에 넣는다. 이는 형식을 강제하는 게 아니라 자연어로 유도하는 것이라 모델이 설명을 덧붙이거나 필드를 빠뜨릴 수 있다. Parser는 응답을 변환하면서 위반을 검출하고, 실패하면 앱이 예외를 처리해야 한다. 지원 모델에서는 스키마를 API에 직접 넘기는 `with_structured_output()`이 보통 더 간결하고 안정적이지만 업무적으로 올바른 값까지 보장하진 않는다.

## 구조화 출력 검증 4단계
구조화 출력이 JSON으로 변환됐다고 해서 앱에서 쓸 수 있는 올바른 데이터라는 뜻은 아니다. 검증은 네 단계로 나눠 본다.
- JSON 문법: 올바른 JSON인가. 실패 예: 따옴표나 중괄호 누락.
- Schema: 필드와 타입이 맞는가. 실패 예: `intensity` 필드 누락.
- Domain: 업무 범위에 맞는 값인가. 실패 예: 감정 강도가 1~5를 벗어남.
- Policy: 서비스 정책상 허용되는가. 실패 예: 근거 없이 위험한 판단을 확정.

Output Parser와 Pydantic은 주로 JSON 문법과 schema를 검증한다. 업무 규칙과 정책은 별도 validator와 앱 로직으로 확인해야 한다.

## PromptTemplate.partial()로 format_instructions 미리 채우기
`PromptTemplate.partial()`은 프롬프트 변수 일부를 미리 채운 새 템플릿을 만든다. Parser의 출력 규칙처럼 고정된 값은 미리 넣고, 호출마다 바뀌는 사용자 입력만 `invoke()`로 넘기게 할 때 쓴다.
```python
prompt = PromptTemplate.from_template("입력: {text}\n{format_instructions}")
prompt = prompt.partial(format_instructions=parser.get_format_instructions())
prompt.invoke({"text": "분석할 문장"})  # text만 전달
```
- `.partial()`을 안 쓰면 `invoke()` 때 `text`와 `format_instructions`를 모두 넘겨야 한다.

## StrOutputParser와 CommaSeparatedListOutputParser 실습
`StrOutputParser`는 AIMessage에서 텍스트만 꺼내고, `CommaSeparatedListOutputParser`는 쉼표로 구분된 짧은 목록을 `list[str]`로 바꾼다. 리스트 파서는 태그·키워드 같은 단순 1차원 목록에 맞고, 항목에 쉼표가 들어가거나 구조가 복잡하면 `JsonOutputParser`를 쓴다.
```python
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

text_chain = ChatPromptTemplate.from_template(
    "{topic}을 처음 배우는 사람에게 두 문장으로 설명해 주세요."
) | llm | StrOutputParser()
text_result = text_chain.invoke({"topic": "LangChain"})

list_parser = CommaSeparatedListOutputParser()
list_prompt = PromptTemplate.from_template(
    "{topic}과 관련된 핵심 키워드 5개를 작성해 주세요.\n{format_instructions}"
).partial(format_instructions=list_parser.get_format_instructions())
list_result = (list_prompt | llm | list_parser).invoke({"topic": "생성형 AI"})
```
- `type(text_result).__name__`이 원문 출력에서 `str`이 아니라 `TextAccessor`로 찍혔다(설치된 버전 특성으로 보임, 문자열처럼 출력됨).
- 리스트 파서 셀은 결과를 print하지 않아 출력이 없다.

## JsonOutputParser로 dict 받기
`JsonOutputParser`는 고정 스키마까지는 필요 없지만 JSON을 Python `dict`로 받고 싶을 때 쓴다.
```python
json_parser = JsonOutputParser()
json_prompt = PromptTemplate.from_template(
    """다음 주제의 핵심 개념 3개를 JSON으로 정리해 주세요.
주제: {topic}
{format_instructions}"""
).partial(format_instructions=json_parser.get_format_instructions())

json_chain = json_prompt | llm | json_parser
json_result = json_chain.invoke({"topic": "RAG"})
print(type(json_result).__name__)  # dict
```
- 결과 예: `{'core_concepts': [{'name': '검색 (Retrieval)', 'description': ...}, ...]}`.
- 키 이름(`core_concepts`, `name`)은 모델이 정한 것이라 호출마다 달라질 수 있다. 스키마가 없기 때문이다. (내 메모)

## PydanticOutputParser로 스키마 검증
`PydanticOutputParser`는 LLM이 만든 JSON 텍스트를 파싱한 뒤 Pydantic 스키마로 검증한다. 필수 필드, 타입, 값 범위를 강제할 수 있다.
```python
class SentimentResult(BaseModel):
    sentiment: Literal["긍정", "부정", "중립"] = Field(description="문장에서 나타나는 감정")
    intensity: int = Field(ge=1, le=5, description="감정 강도")
    reason: str = Field(min_length=1, description="판단 근거")

pydantic_parser = PydanticOutputParser(pydantic_object=SentimentResult)
pydantic_prompt = PromptTemplate.from_template(
    """다음 문장의 감정을 분석해 주세요.
문장: {text}
{format_instructions}"""
).partial(format_instructions=pydantic_parser.get_format_instructions())

pydantic_chain = pydantic_prompt | llm | pydantic_parser
pydantic_chain.invoke({"text": "새 기능이 기대보다 훨씬 좋아서 정말 만족합니다."})
```
```text
SentimentResult
sentiment='긍정' intensity=5 reason="...정말 만족합니다'라는 직접적인 만족감 표현..."
```

## Pydantic Literal 타입으로 허용값 제한하기
Pydantic 필드의 `description`은 모델에게 원하는 값을 안내할 뿐 허용값을 제한하지 않는다. `sentiment: str`이면 "만족", "혼합", "알 수 없음"도 문자열이라 검증을 통과한다.

`Literal["긍정", "부정", "중립"]`처럼 허용값을 타입에 쓰면 그 밖의 값은 검증 단계에서 차단된다. 숫자는 `ge`, `le`, 문자열은 `min_length` 같은 제약을 함께 건다.
```python
sentiment: Literal["긍정", "부정", "중립"]
intensity: int = Field(ge=1, le=5)
reason: str = Field(min_length=1)
```

## Gemini with_structured_output 네이티브 구조화 출력
`with_structured_output()`은 Pydantic 스키마를 Gemini API에 직접 넘긴다. format instructions나 parser 없이 검증된 객체를 바로 받는다.
```python
structured_llm = llm.with_structured_output(SentimentResult)
result = structured_llm.invoke("배송은 빨랐지만 제품 포장이 찢어져 있어서 아쉬웠습니다.")
print(result)
```
```text
sentiment='부정' intensity=4 reason='배송은 빨랐지만 제품 포장이 찢어져 있어 아쉬움을 표현했기 때문입니다.'
```
- 반환 타입은 `SentimentResult` 객체다.

## with_structured_output vs PydanticOutputParser 선택
모델이 네이티브 구조화 출력을 안정적으로 지원하면 `with_structured_output()`을 먼저 고려한다. 다음 경우엔 `PydanticOutputParser`가 더 맞다.
- provider나 모델이 네이티브 structured output을 지원하지 않을 때.
- 여러 provider에서 같은 프롬프트·파싱 방식을 유지해야 할 때.
- 이미 저장된 JSON 문자열이나 외부 텍스트를 Pydantic 객체로 검증할 때.
- 원본 텍스트를 전처리해 직접 파싱하거나 실패 과정을 세밀히 제어할 때.
- `FakeListChatModel`처럼 문자열을 내는 테스트 모델로 성공/실패를 재현할 때.

차이: `with_structured_output()`은 스키마를 모델 API에 전달하고 지원 모델이 필요하며 간결하지만 provider 동작에 영향을 받는다. `PydanticOutputParser`는 format instructions를 프롬프트에 넣고 일반 텍스트 모델에서도 쓰며 응답을 받은 뒤 파싱·검증하므로 전처리·예외·재시도를 직접 구성할 수 있다. 다만 모델이 JSON을 안 지킬 수 있다.

## Structured Output 실패 원인 3가지와 include_raw 진단
구조화 출력 실패는 위치에 따라 세 가지로 나뉜다.
- Provider/API 실패: 모델이 지원하지 않거나 요청 자체가 실패. 원본 응답이 없어 예외가 난다.
- 파싱 실패: 응답은 왔지만 JSON 문법이나 구조가 틀림.
- 검증 실패: JSON은 맞지만 타입, 필수 필드, 범위 조건 위반.

`with_structured_output(..., include_raw=True)`는 `raw`, `parsed`, `parsing_error`를 함께 돌려줘 디버깅에 유용하다.
```python
diagnostic_llm = llm.with_structured_output(SentimentResult, include_raw=True)
r = diagnostic_llm.invoke("생각보다 나쁘지는 않았지만 다시 구매할지는 모르겠습니다.")
print(r["parsed"], r["parsing_error"], r["raw"])
```
- 결과: `parsed`는 `sentiment='중립' intensity=2 ...`, `parsing_error`는 `None`, `raw`는 JSON 문자열을 담은 AIMessage.
- 주의: `include_raw=True`면 파싱 실패가 예외가 아니라 `parsing_error` 값으로 온다. `.with_retry()`, `.with_fallbacks()`는 예외가 나야 동작하므로 진단 모드와 운영 복구 체인을 분리한다.

## Structured Output 재시도: with_retry와 FakeListChatModel
PydanticOutputParser 체인의 재시도는 `.with_retry()`로 건다. `FakeListChatModel`에 응답을 미리 넣어 첫 호출은 검증 실패(intensity=10), 두 번째는 성공하도록 재현한다.
```python
fake_retry_llm = FakeListChatModel(responses=[
    '{"sentiment": "긍정", "intensity": 10, "reason": "만족한다고 표현했습니다."}',  # 범위 위반
    '{"sentiment": "긍정", "intensity": 4, "reason": "만족한다고 표현했습니다."}',   # 통과
])
retry_demo_chain = (
    RunnableLambda(count_attempts)  # 시도 횟수를 세고 입력을 그대로 넘기는 함수
    | pydantic_prompt | fake_retry_llm | pydantic_parser
).with_retry(
    retry_if_exception_type=(OutputParserException,),
    stop_after_attempt=3,
)
retry_demo_chain.invoke({"text": "이 제품은 정말 좋습니다."})
```
```text
시도 1회
시도 2회
최종 결과: sentiment='긍정' intensity=4 reason='만족한다고 표현했습니다.'
```
- `.with_retry()`는 parser만 다시 돌리는 게 아니라 체인 전체를 다시 실행해 새 응답을 받는다.
- `retry_if_exception_type`으로 재시도할 오류를 좁히고 `stop_after_attempt`로 무한 반복을 막는다.

## Structured Output Fallback: with_fallbacks
`.with_fallbacks()`는 primary 체인이 예외를 던질 때만 같은 입력을 fallback 체인에 넘긴다. 예제는 "네이티브 구조화 출력 실패 → parser 방식 전환"을 `RuntimeError`로 재현한다.
```python
def raise_structured_output_error(_):
    raise RuntimeError("네이티브 structured output을 사용할 수 없습니다.")

fake_fallback_llm = FakeListChatModel(responses=[
    '{"sentiment": "중립", "intensity": 2, "reason": "장점과 단점이 함께 언급되었습니다."}'
])
primary_chain = RunnableLambda(raise_structured_output_error)
fallback_chain = pydantic_prompt | fake_fallback_llm | pydantic_parser
resilient_chain = primary_chain.with_fallbacks([fallback_chain])
resilient_chain.invoke({"text": "속도는 빨라졌지만 오류가 더 자주 발생합니다."})
```
- 결과: `sentiment='중립' intensity=2 ...`가 fallback에서 반환된다.
- 운영에서는 primary에 `llm.with_structured_output(Schema)`, fallback에 parser 체인이나 다른 모델을 둔다.
- 인증 오류·정책 위반처럼 전환해도 안 풀리는 오류까지 fallback하지 않게 대상 예외를 구분한다.

## Structured Output 실패별 처리와 파서 선택 기준
구조화 출력 실패를 모두 재시도하면 안 된다. 원인별로 처리한다.
- JSON 형식이 일시적으로 잘못됨 → 횟수 제한 재시도.
- 필수 입력 부족 → 사용자에게 추가 정보 요청.
- 허용 범위를 벗어난 값 → 오류를 알리고 중단하거나 다시 입력받기.
- 정책상 허용되지 않는 결과 → 재시도 없이 중단.
- 일시적 provider 장애 → 조건부 fallback 모델.

재시도에는 항상 최대 횟수를 둔다.

파서 선택 기준:
- 단순 텍스트: `StrOutputParser`
- 유연한 JSON: `JsonOutputParser`
- 프롬프트 기반 JSON + 엄격한 검증: `PydanticOutputParser`
- 모델이 지원하고 스키마가 명확함: `with_structured_output()`
- 운영에서는 예외 처리와 재시도(예: `chain.with_retry(stop_after_attempt=3)`)를 함께 구성한다.

## Structured Output 복습 Q&A
- Q. `get_format_instructions()`를 프롬프트에 넣으면 출력 형식이 보장되나?
  A. 아니다. 자연어로 유도할 뿐이라 모델이 어길 수 있고, parser가 위반을 검출하면 앱이 예외를 처리해야 한다.
- Q. Pydantic 스키마에서 감정 값을 "긍정/부정/중립"으로만 제한하려면?
  A. `description`이 아니라 `Literal["긍정", "부정", "중립"]` 타입으로 지정한다.
- Q. `with_structured_output(..., include_raw=True)`를 retry 체인에 그대로 쓰면 안 되는 이유는?
  A. 파싱 실패가 예외가 아니라 `parsing_error` 값으로 반환돼 `with_retry`/`with_fallbacks`가 동작하지 않을 수 있다.
- Q. LangChain `.with_retry()`는 파서만 다시 실행하나?
  A. 체인 전체를 다시 실행해 모델에서 새 응답을 받는다. `retry_if_exception_type`, `stop_after_attempt`로 범위와 횟수를 제한한다.
- Q. PydanticOutputParser를 with_structured_output 대신 쓰는 경우는?
  A. 모델이 네이티브 구조화 출력을 지원하지 않거나, 여러 provider를 같은 방식으로 다루거나, 저장된 JSON 문자열을 검증하거나, Fake 모델로 테스트할 때.
