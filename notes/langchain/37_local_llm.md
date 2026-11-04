---
part: langchain
lesson: Local LLM
order: 37
source_type: ipynb
tags: [local-llm, ollama, chatollama, hugging-face, quantization, gguf, gemini]
source: C:\Users\tnwls\aim-ai-agent\langchain_\37-local-llm.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Local LLM

## Local LLM 요약
Ollama로 오픈소스 LLM(qwen3.5:0.8b)을 로컬에서 실행하고, Gemini API로 만든 LangChain 체인에서 모델 객체만 `ChatOllama`로 바꿔 같은 체인을 돌려 본다. Hugging Face와 양자화 개념, 로컬 모델과 API 모델의 차이도 정리한다.

## Ollama란
Ollama는 로컬 PC에서 LLM을 쉽게 실행해 주는 도구다(https://ollama.com). `ollama pull`로 모델을 받고 `ollama run`으로 실행한다.
- Llama(Meta), Qwen(Alibaba), Gemma(Google) 등 여러 오픈소스 모델을 지원한다.
- 로컬 API 서버를 띄워 주므로 LangChain 같은 외부 도구에서 쉽게 연동한다.
- 이미 양자화된 모델을 내려받아 실행할 수 있다.

양자화(quantization)는 모델 가중치를 더 낮은 정밀도로 표현해 모델 크기와 메모리 사용량을 줄이는 기법이다.

## Hugging Face와 Model Hub
Hugging Face(https://huggingface.co)는 오픈소스 AI 모델을 위한 GitHub 같은 플랫폼으로, LLM뿐 아니라 이미지·음성 모델도 공유된다.
- Models: 수십만 개의 사전학습 모델 검색·다운로드
- Datasets: 학습용 데이터셋 공유·다운로드
- Spaces: 모델을 웹에서 바로 체험하는 데모 공간

이렇게 모델을 모아 둔 플랫폼을 Model Hub라 부른다. Ollama 라이브러리에 없는 모델도 Hugging Face에서 GGUF 형식으로 받으면 Ollama로 실행할 수 있다.

## Local LLM 실습 1단계: Gemini API 체인 만들기
Local LLM 비교의 기준으로 Gemini API 체인을 먼저 만든다. API 키는 `.env`에 `GOOGLE_API_KEY`로 두고 `load_dotenv()`로 읽으면 `ChatGoogleGenerativeAI`가 사용한다.
```python
load_dotenv()
prompt = ChatPromptTemplate.from_messages([
    ("system", "너는 {role} 전문가야. 모든 답변은 한국어로 해줘."),
    ("human", "{question}"),
])
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
parser = StrOutputParser()
chain = prompt | llm | parser
print(chain.invoke({"role": "Python", "question": "for 문을 설명해줘"}))
```
- 결과: 파이썬 for 문(iterable 요소를 하나씩 꺼내 반복)을 기본 구조와 예시와 함께 한국어로 길게 설명한다.
- 첫 호출 때 Gemini SDK의 AFC 관련 경고 문구가 함께 출력된다.

## Local LLM 실습 2단계: Ollama 설치와 모델 다운로드
Ollama는 macOS에서 `brew install ollama` 또는 공식 설치 파일로, Windows는 공식 설치 파일로 설치한다. Ollama 앱이 이미 실행 중이 아니면 서버를 띄우고, 새 터미널에서 모델을 받는다.
```bash
ollama serve                 # 이 터미널은 열어 둔다
ollama pull qwen3.5:0.8b     # 새 터미널에서 실행
pip install langchain-ollama
```
- `0.8b`: 파라미터가 약 8억 개라는 뜻(`b` = billion, 10억). 파라미터는 학습 중 조정되는 모델 내부 수치다.
- 노트북 실습 동안 Ollama 서버를 계속 켜 둔다.

## Local LLM 실습 3단계: ChatOllama로 모델만 교체
Local LLM 연동은 기존 체인에서 LLM 객체만 `ChatOllama`로 바꾸면 된다. 프롬프트와 파서는 그대로 쓴다.
```python
from langchain_ollama import ChatOllama

local_llm = ChatOllama(model="qwen3.5:0.8b", reasoning=False)
chain = prompt | local_llm | parser
print(chain.invoke({"role": "Python", "question": "for 문을 설명해줘"}))
```
- `reasoning=False`: 모델의 추론(thinking) 출력을 끄는 옵션으로 보인다(내 메모).
- 노트북에서는 이 셀이 `KeyboardInterrupt`로 중단되어 출력이 없다. 응답이 오래 걸려 수동으로 멈춘 것으로 보인다(내 메모). 서버 실행·모델 다운로드 여부를 먼저 확인하자.

## 로컬 LLM과 Gemini API 비교
로컬 LLM(qwen3.5:0.8b)과 Gemini API(gemini-3.6-flash)의 차이다.
- 비용: 로컬은 API 호출 비용이 없지만 장비와 전력이 든다. API는 요금제와 사용량에 따라 달라진다.
- 인터넷: 로컬은 모델 다운로드 후 추론에는 필요 없다. API는 항상 필요하다.
- 사용 한계: 로컬은 PC 메모리와 연산 성능에 묶인다. API는 요청 수·토큰 수 같은 호출 한도가 있다.

## Local LLM 복습 Q&A
- Q. Gemini 체인을 로컬 LLM으로 바꾸려면 무엇을 바꾸나?
  A. LLM 객체만 `ChatOllama(model="qwen3.5:0.8b")`로 바꾸면 되고 프롬프트·파서·체인 구성은 그대로다.
- Q. Ollama 모델명 `qwen3.5:0.8b`의 `0.8b`는 무슨 뜻인가?
  A. 파라미터가 약 8억 개(0.8 billion)라는 뜻이다.
- Q. 양자화(quantization)란?
  A. 가중치를 낮은 정밀도로 표현해 모델 크기와 메모리 사용량을 줄이는 기법이다.
- Q. Ollama 라이브러리에 없는 모델을 Ollama로 실행하려면?
  A. Hugging Face에서 GGUF 형식으로 받아 Ollama로 실행한다.
- Q. 로컬 LLM이 Gemini API보다 유리한 점은?
  A. API 호출 비용이 없고 모델을 받은 뒤에는 인터넷 없이 추론할 수 있다. 대신 PC 메모리·연산 성능의 제약을 받는다.
