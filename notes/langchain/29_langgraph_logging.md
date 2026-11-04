---
part: langchain
lesson: LangGraph Logging
order: 29
source_type: ipynb
tags: [langgraph, logging, logger, handler, formatter, log-level, rotatingfilehandler, traceback]
source: C:\Users\tnwls\aim-ai-agent\langchain_\29-langgraph-logging.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# LangGraph Logging

## LangGraph Logging 요약
LangGraph Logging 레슨은 Python 기본 모듈 `logging`으로 로거·핸들러·포매터를 설정하고, 로그 레벨, 파일 저장과 로테이션, traceback 기록을 익힌 뒤 LangGraph 노드에 로그를 남긴다.

## Python 로깅이란
로그(log)는 프로그램 실행 중 일어난 일을 남긴 기록이고, 로깅(logging)은 그 기록을 남기는 작업이다. 로그에 시각, 실행 단계, 처리 결과를 남기면 실행 흐름과 오류 원인을 나중에 추적할 수 있다. Python의 `logging`은 기본 모듈이라 설치 없이 쓴다.

`print()`로도 실행 과정을 볼 수 있지만, 출력이 많아지면 필요한 기록만 골라 보기 어렵다. `logging`은 설정만 바꿔서 기록할 중요도, 출력 형식, 저장 위치(화면/파일)를 조절할 수 있다.

## Python logging의 로거, 핸들러, 포매터
Python `logging`은 세 가지 구성 요소로 이루어진다.
- 로거(Logger): `logger.info()`처럼 로그를 기록하는 객체. `logging.getLogger("이름")`으로 얻고, 같은 이름이면 같은 로거가 반환된다.
- 핸들러(Handler): 로그를 화면, 파일 등 목적지로 보낸다. 로거 하나에 핸들러 여러 개를 붙일 수 있다.
- 포매터(Formatter): 시각·레벨·메시지 등 표시 형식을 정한다. 핸들러에 연결한다.

`.py` 파일에서는 보통 `logging.getLogger(__name__)`으로 모듈 이름을 로거 이름으로 쓴다.

## Python logging 실습 1단계: 화면 출력 로거 설정
로거를 가져와 레벨을 정하고, 표준 출력 핸들러와 포매터를 연결한다.
```python
import logging, sys

logger = logging.getLogger("lesson.langgraph")
logger.setLevel(logging.INFO)
logger.propagate = False

for handler in logger.handlers[:]:  # 셀 재실행 시 중복 출력 방지
    logger.removeHandler(handler)
    handler.close()

console_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%H:%M:%S")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.info("로깅 준비 완료")
```
```text
14:18:02 | INFO | lesson.langgraph | 로깅 준비 완료
```
- `propagate = False`: 상위 로거로 전달하지 않고 직접 붙인 핸들러만 쓴다.
- `logger.handlers[:]`: 핸들러 목록의 복사본. 순회하며 제거·close한다.
- 포맷: `asctime` 시각, `levelname` 레벨, `name` 로거 이름, `message` 메시지.

## Python logging 로그 레벨로 중요도 나누기
Python 로그 레벨은 `DEBUG < INFO < WARNING < ERROR < CRITICAL` 순서이고, 설정한 레벨 이상만 기록된다.
- `DEBUG`: 검색 결과 개수 같은 자세한 진단 정보
- `INFO`: 노드 시작·완료, 선택한 경로
- `WARNING`: 검색 결과가 없어 안내 답변으로 전환 같은 상황
- `ERROR`: 외부 서비스 오류로 요청 처리 실패
- `CRITICAL`: 서비스 전체 운영이 어려운 심각한 문제

설정하지 않은 루트 로거의 기본 기준은 WARNING이다.
```python
logger.setLevel(logging.WARNING)
logger.info("이 INFO는 보이지 않는다")
logger.warning("이 WARNING은 보인다")
logger.setLevel(logging.DEBUG)
logger.debug("이제 DEBUG도 보인다")
logger.setLevel(logging.INFO)
```
- INFO 레벨에서 5개 레벨을 모두 호출하면 DEBUG만 빠지고 4줄이 나온다.

## Python logging 변수 값 함께 기록하기
Python 로그 메시지에는 f-string으로 변수 값을 넣을 수 있다. `key=value` 형태로 쓰면 나중에 검색하기 쉽다.
```python
node_name = "search"
document_count = 2
elapsed_ms = 12.345
logger.info(f"node={node_name} documents={document_count} elapsed_ms={elapsed_ms:.2f}")
```
```text
14:20:22 | INFO | lesson.langgraph | node=search documents=2 elapsed_ms=12.35
```

## Python logging 실습 2단계: 파일 핸들러 추가
화면을 닫은 뒤에도 볼 수 있도록 `FileHandler`를 추가해 `logs/29-langgraph.log`에 저장한다.
```python
from pathlib import Path

log_dir = Path.cwd() / "logs"
log_dir.mkdir(exist_ok=True)
log_path = log_dir / "29-langgraph.log"

for handler in logger.handlers[:]:
    if isinstance(handler, logging.FileHandler):
        logger.removeHandler(handler)
        handler.close()

file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info("화면과 파일에 함께 기록")
```
- `mode="a"`: 기존 기록 뒤에 이어서 추가한다.
- `encoding="utf-8"`: 한글을 깨지지 않게 저장한다.
- 기존 파일 핸들러를 먼저 제거해 셀 재실행 시 중복 저장을 막는다.

## Python logging 핸들러별 레벨: 화면은 간단히, 파일은 자세히
Python 로그는 로거의 레벨을 먼저 통과한 뒤, 각 핸들러의 레벨도 통과해야 출력된다. 로거가 INFO면 파일 핸들러만 DEBUG로 바꿔도 DEBUG 기록은 남지 않는다. 그래서 로거를 DEBUG로 열고 핸들러별로 거른다.
```python
logger.setLevel(logging.DEBUG)
console_handler.setLevel(logging.INFO)
file_handler.setLevel(logging.DEBUG)

logger.debug("파일에서만 보이는 상세 기록")
logger.info("화면과 파일에 모두 보이는 진행 기록")
file_handler.flush()
print(log_path.read_text(encoding="utf-8"))
```
- 화면에는 INFO 한 줄만 나오고, 파일 내용에는 DEBUG 줄까지 함께 들어 있다.

## Python logging RotatingFileHandler로 로그 파일 로테이션
`RotatingFileHandler`는 로그 파일이 정한 크기를 넘으면 새 파일로 전환하고, 이전 파일은 정해진 개수만 보관한다.
```python
from logging.handlers import RotatingFileHandler

logger.removeHandler(file_handler)
file_handler.close()
file_handler = RotatingFileHandler(log_path, maxBytes=1024, backupCount=2, encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

for index in range(40):
    logger.debug(f"파일 회전 확인: 반복 기록 {index}")
```
- `maxBytes`: 교체 기준 크기(바이트). 확인용으로 1024로 작게 잡았다.
- `backupCount`: 보관할 이전 파일 수(현재 파일 제외).
- 현재 기록은 `29-langgraph.log`, 이전 기록은 `.log.1`(더 최근), `.log.2`에 남고, 개수를 넘으면 가장 오래된 파일이 지워진다.

## Python logging logger.exception으로 traceback 기록
Python `logger.error()`는 메시지만 남기고, `except` 블록 안의 `logger.exception()`은 ERROR 레벨 메시지와 현재 예외의 traceback을 함께 남긴다. traceback은 어떤 함수·코드 줄을 거쳐 오류가 났는지 보여 준다.
```python
try:
    int("숫자가 아님")
except ValueError:
    logger.error("정수 변환 실패: 메시지만 기록")
    logger.exception("정수 변환 실패: traceback도 기록")
```
- 두 번째 로그 아래에 `Traceback (most recent call last): ... ValueError: invalid literal for int()...`가 이어서 출력된다.

기록과 오류 처리는 별개다. `logger.exception()`만으로 예외가 다시 발생하거나 재시도되지 않으므로, 호출한 곳에 실패를 알리려면 `raise`를 써야 한다.

## LangGraph 노드에 로그 남기기
LangGraph 노드도 Python 함수이므로 같은 로거를 그대로 쓴다. 질문 공백을 지우는 `prepare`와 답변을 만드는 `answer`를 `START → prepare → answer → END`로 연결하고 각 노드의 시작·완료를 기록한다.
```python
class LoggingState(TypedDict):
    question: str
    answer: str

def prepare(state: LoggingState):
    logger.info("prepare 시작")
    question = state["question"].strip()
    logger.info("prepare 완료")
    return {"question": question}

def answer(state: LoggingState):
    logger.info("answer 시작")
    try:
        if not state["question"]:
            raise ValueError("질문이 비어 있습니다.")
        response = f"질문을 받았습니다: {state['question']}"
    except ValueError:
        logger.exception("answer 실패")
        raise
    logger.info("answer 완료")
    return {"answer": response}
```
- 그래프 구성은 `StateGraph(LoggingState)`에 두 노드를 추가하고 `add_edge`로 순서대로 이은 뒤 `compile()`한다. (구성 코드는 생략)

## LangGraph 로깅 실행 결과: 정상과 오류
LangGraph 그래프를 정상 질문으로 실행하면 노드 순서대로 INFO 로그가 남는다.
```python
result = graph.invoke({"question": "  LangGraph가 무엇인가요?  "})
```
```text
INFO | prepare 시작 → prepare 완료 → answer 시작 → answer 완료
질문을 받았습니다: LangGraph가 무엇인가요?
```
(실제 출력은 한 줄씩 찍히며, 여기선 한 줄로 줄였다.)

공백만 입력하면 `answer`에서 `ValueError`가 난다.
```python
try:
    graph.invoke({"question": "   "})
except ValueError as error:
    print("실행 실패:", error)
```
- 로그에는 `answer 시작` 다음 `ERROR | answer 실패`와 traceback이 있고 `answer 완료`는 없다. 로그만 봐도 어느 노드에서 실패했는지 알 수 있다.
- `raise`로 예외가 호출자까지 전달되어 `실행 실패: 질문이 비어 있습니다.`가 출력된다.

## LangGraph Logging 복습 Q&A
- Q. Python logging에서 로거가 INFO인데 파일 핸들러만 DEBUG로 하면 DEBUG가 파일에 남나?
  A. 남지 않는다. 로그는 로거 레벨과 핸들러 레벨을 모두 통과해야 하므로 로거도 DEBUG로 낮춰야 한다.
- Q. `logger.error()`와 `logger.exception()`의 차이는?
  A. `error()`는 메시지만, `exception()`은 except 블록에서 ERROR 메시지와 traceback을 함께 남긴다.
- Q. `logger.exception()`을 호출하면 예외가 호출자에게 전달되나?
  A. 아니다. 기록만 하므로 실패를 알리려면 `raise`를 따로 써야 한다.
- Q. `RotatingFileHandler(maxBytes=1024, backupCount=2)`는 어떻게 동작하나?
  A. 파일이 1024바이트를 넘으면 새 파일로 바꾸고, 이전 파일은 `.1`, `.2` 두 개만 보관한다.
- Q. 노트북에서 로거 설정 셀을 다시 실행할 때 로그가 중복 출력되지 않게 하려면?
  A. `logger.handlers[:]`를 순회해 기존 핸들러를 제거하고 close한 뒤 새로 추가한다.
