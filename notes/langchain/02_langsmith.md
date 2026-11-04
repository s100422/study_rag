---
part: langchain
lesson: LangSmith
order: 2
source_type: ipynb
tags: [langsmith, tracing, observability, run-name, metadata, tracing-context]
source: C:\Users\tnwls\aim-ai-agent\langchain_\02-langsmith.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# LangSmith

## LangSmith 요약
LangSmith 환경 변수를 설정해 Gemini 기반 LCEL 체인의 실행을 자동으로 추적하고, `config`로 run 이름·태그·메타데이터를 붙이며, `tracing_context`로 특정 구간만 추적하는 방법을 익힌다.

## LangSmith란
LangSmith는 LangChain 애플리케이션의 실행 과정을 기록하고 분석하는 관측성(observability) 플랫폼이다. LangChain Runnable(체인, 모델, 프롬프트)을 실행하면 별도 콜백 코드 없이 각 단계의 입력·출력, 토큰 수, 소요 시간이 트레이스로 기록된다.

## LangSmith 실습 1단계: 설치와 환경 변수 설정
LangSmith 추적은 `langsmith` 패키지를 설치하고 `.env`에 환경 변수를 넣으면 켜진다.
```bash
pip install langsmith
```
```dotenv
GEMINI_API_KEY=...
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=langchain-gemini-prac
```
- `LANGSMITH_TRACING=true`: 추적을 켠다.
- `LANGSMITH_PROJECT`: 트레이스가 쌓일 프로젝트 이름. 없으면 `default`.
- API 키가 여러 워크스페이스에 연결돼 있으면 `LANGSMITH_WORKSPACE_ID`도 설정한다.

```python
from dotenv import load_dotenv
import os
load_dotenv()
print("LangSmith tracing:", os.getenv("LANGSMITH_TRACING"))
print("LangSmith project:", os.getenv("LANGSMITH_PROJECT", "default"))
```
- 환경 변수를 바꿨는데 반영되지 않으면 설정 셀을 다시 실행하고 커널을 재시작한다.

## LangSmith 실습 2단계: 추적할 Gemini 체인 실행
LangSmith 추적 대상으로 Python 튜터 체인을 만들고 실행한다. 환경 변수만 설정돼 있으면 `invoke()` 한 번으로 트레이스가 기록된다.
```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_messages([
    ("system", "너는 초보자를 가르치는 Python 튜터야. 핵심만 한국어로 설명해줘."),
    ("human", "{question}"),
])
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
chain = prompt | llm | StrOutputParser()

result = chain.invoke({"question": "Python 데코레이터가 뭐야?"})
print(result)
```
- 출력: 데코레이터를 "스마트폰 케이스" 비유와 예제 코드로 설명하는 긴 마크다운 답변. 앞에 Gemini SDK의 AFC 경고 문구가 함께 찍힌다.

## LangSmith 실습 3단계: run_name, 태그, 메타데이터 추가
LangSmith에서 실행을 찾고 필터링하기 쉽게 `invoke()`의 `config`에 이름, 태그, 메타데이터를 넘긴다.
```python
result = chain.invoke(
    {"question": "리스트와 튜플의 차이는 뭐야?"},
    config={
        "run_name": "python-basic-question",
        "tags": ["gemini", "basic", "class-demo"],
        "metadata": {"lesson": "01-1", "model_family": "gemini"},
    },
)
```
- `run_name`: 트레이스 목록에 표시될 실행 이름.
- `tags`: 실행 목적·실험 버전별 필터링용 라벨 목록.
- `metadata`: 레슨 번호, 모델 계열 같은 키-값 정보.
- 출력: 리스트(가변)와 튜플(불변)의 차이를 정리한 답변. (원문 출력 끝에 내용 없는 `[에러] :` 표시가 붙어 있으나 결과는 정상)

## LangSmith 화면에서 확인할 항목
LangSmith 웹(smith.langchain.com)에서 `LANGSMITH_PROJECT`로 지정한 프로젝트를 열면 다음을 확인할 수 있다.
- 프롬프트 → Gemini 모델 → 출력 파서 순의 실행 단계
- 템플릿 변수가 채워진 최종 프롬프트
- 입력·출력 토큰 수와 단계별 소요 시간
- `run_name`, 태그, 메타데이터
- 실패한 실행이 있으면 오류가 난 단계

## LangSmith 선택적 추적: tracing_context
LangSmith에서 모든 실행을 항상 기록하지 않고 특정 구간만 추적하려면 `langsmith.tracing_context`를 with 블록으로 쓴다. 블록 안에서만 추적이 켜지고 다른 프로젝트로 보낼 수도 있다.
```python
import langsmith as ls

with ls.tracing_context(enabled=True, project_name="langchain-gemini-selective"):
    result = chain.invoke({"question": "Python 제너레이터가 뭐야?"})
print(result)
```
- `enabled=True`: 이 블록 안의 실행을 추적한다.
- `project_name`: 이 구간의 트레이스를 별도 프로젝트에 기록한다.
- 전역 추적을 끄고(`LANGSMITH_TRACING` 미설정) 필요한 곳만 켜는 용도로 쓸 수 있다. (내 메모)

## LangSmith 복습 Q&A
- Q. LangChain 체인 실행을 LangSmith에 기록하려면 코드에 콜백을 넣어야 하나?
  A. 아니다. `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` 환경 변수만 설정하면 Runnable 실행이 자동 기록된다.
- Q. LangSmith에서 실행을 필터링하기 쉽게 하려면?
  A. `invoke(..., config={"run_name": ..., "tags": [...], "metadata": {...}})`로 이름, 태그, 메타데이터를 붙인다.
- Q. LangSmith에서 특정 코드 구간만 추적하려면?
  A. `with langsmith.tracing_context(enabled=True, project_name=...):` 블록 안에서 체인을 실행한다.
- Q. LangSmith 트레이스에서 볼 수 있는 정보는?
  A. 단계별 실행 순서, 최종 프롬프트, 토큰 수, 소요 시간, 태그·메타데이터, 오류 발생 단계.
