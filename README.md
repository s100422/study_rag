# study_rag

강의 학습노트(`notes/`)를 pgvector에 넣고, 질문하면 관련 노트를 찾아 답해 주는 개인용 RAG 검색 앱입니다.

- **임베딩 / LLM:** Google Gemini (`google-genai`)
- **벡터 DB:** PostgreSQL + pgvector (Docker)
- **UI:** Streamlit

## 구성

| 경로 | 설명 |
|------|------|
| `notes/` | 학습노트 (backend 25, docker 7, html 2, langchain 39, web 5) |
| `groups.md` | 노트 묶음 설명. 검색 시 관련 노트를 고르는 힌트로 쓰임 |
| `rag.py` | 인덱싱 / 검색 / 답변 CLI |
| `app.py` | Streamlit 웹 앱 |
| `eval.py`, `golden.jsonl` | 골든셋 기반 검색 품질 측정 |
| `test_rag.py` | 테스트 |
| `compose.yaml` | pgvector DB 컨테이너 (`127.0.0.1:5434`) |
| `start.bat` | Docker → DB → 앱 한 번에 실행 (Windows) |

## 실행

필요: Python 3.13+, [uv](https://docs.astral.sh/uv/), Docker, Gemini API 키

### 빠른 실행 (Windows)

`.env`에 키를 넣고(아래 1번) 인덱싱을 한 번 한 뒤(아래 3번), `start.bat`을 더블클릭하거나 실행합니다.

```bat
start.bat
```

Docker Desktop이 꺼져 있으면 켜고, DB 컨테이너를 띄운 다음 Streamlit 앱을 브라우저로 엽니다. 창을 닫으면 앱이 종료됩니다.

### 단계별 실행

1. `.env` 파일에 키를 넣습니다.

   ```
   GOOGLE_API_KEY=...
   ```

2. DB를 띄웁니다.

   ```bash
   docker compose up -d db
   ```

3. 노트를 인덱싱합니다. 바뀐 파일만 다시 처리합니다.

   ```bash
   uv run rag.py index
   ```

4. 검색하거나 질문합니다.

   ```bash
   uv run rag.py search "N+1 문제" -k 5
   uv run rag.py ask "N+1 문제 해결 방법"
   ```

5. 웹 앱으로 쓰려면 다음을 실행합니다. (Windows에서는 `start.bat`이 2~5번 중 DB 실행과 앱 실행을 대신합니다)

   ```bash
   uv run streamlit run app.py
   ```

## 아키텍처

```
[인덱싱]  notes/*.md ──parse_note──▶ ## 섹션 단위 청크 ──Gemini 임베딩──▶ chunks 테이블 (pgvector)
          groups.md + 노트 요약 ─────────────Gemini 임베딩──────────────▶ notes  테이블 (pgvector)

[질문]    질문 ─▶ 임베딩 ─▶ 벡터 검색(chunks + notes) ─▶ 발췌 N개 ─▶ Gemini LLM ─▶ 인용 번호가 붙은 답 + 출처
```

### 인덱싱 (`rag.py index`)

- 노트를 `## ` 제목 기준 섹션으로 쪼개 청크로 저장합니다. 코드 블록 안의 `## `는 제목으로 보지 않고, 파일 맨 위 frontmatter(`lesson`, `part`, `tags`)는 메타데이터로 씁니다.
- 파일 해시(sha256)가 같으면 건너뛰고, 바뀐 파일만 한 트랜잭션 안에서 교체합니다. 삭제된 파일의 청크는 지웁니다.
- 청크와 별도로 **노트 단위 임베딩**(제목·태그·`groups.md` 묶음 설명·첫 섹션 요약)을 `notes` 테이블에 저장합니다.

### 검색

- 점수 = `(1-w) × 섹션 유사도 + w × 노트 유사도` (코사인). 파일당 최대 N개 섹션만 남겨 결과가 한 노트에 몰리지 않게 합니다.
- 노트 유사도를 섞으면 "에이전트 구성방법"처럼 섹션 단어와 겹치지 않는 질문에서도 관련 노트가 올라옵니다.
- `search` 모드는 w=0(순위 정확도 우선), `ask` 모드는 w=0.7(노트 다양성 우선)을 씁니다.
- 키워드 검색(pg_trgm)을 섞어 봤지만 `golden.jsonl` 기준으로 벡터 단독보다 낮아 쓰지 않습니다.

### 답변 (`ask`)

1. 깊게(상위 10개, 파일당 3개) + 넓게(상위 20개, 파일당 1개) 두 번 검색해 합칩니다. 평균 약 26개 섹션입니다.
2. 발췌에 번호를 붙여 LLM에 넘기고, 시스템 프롬프트로 "발췌에 있는 내용만 쓰기 / 문장마다 `[번호]` 인용 / 근거 없으면 '노트에서 찾을 수 없습니다'"를 강제합니다.
3. 스트리밍으로 답을 출력한 뒤, 답변에 실제로 인용된 발췌만 출처(`파일:줄`)로 보여 줍니다.

### AI 에이전트가 아니라 고정 파이프라인

이 프로젝트에는 에이전트 루프(도구 호출, 계획, 반복)가 **없습니다**. 질문 하나에 `임베딩 → 검색 → LLM 1회 호출`이 항상 같은 순서로 실행되는 RAG 파이프라인입니다. LLM은 최종 답을 쓰는 단계에서만 붙어 있고, 무엇을 검색할지는 LLM이 정하지 않습니다. `notes/langchain`의 에이전트 관련 노트(ReAct, 에이전틱 RAG, 슈퍼바이저 등)는 이 앱이 검색하는 **학습 자료**입니다.

### 앱 연결 (`app.py`)

Streamlit이 `rag.py`의 `retrieve`(검색 모드), `ask_context` → `answer_stream` → `cited_rows`(답변 모드)를 그대로 호출합니다. DB가 꺼져 있으면 안내 메시지를 보여 줍니다.

## 설정 (환경변수, 선택)

| 변수 | 기본값 |
|------|--------|
| `DATABASE_URL` | `postgresql://postgres:1234@127.0.0.1:5434/study_rag` |
| `EMBEDDING_MODEL` | `gemini-embedding-2` |
| `LLM_MODEL` | `gemini-3.6-flash` |

> `compose.yaml`과 기본 `DATABASE_URL`의 비밀번호 `1234`는 로컬 연습용입니다. DB 포트는 `127.0.0.1`에만 열려 있습니다. 서버에 배포할 때는 반드시 바꾸세요.

## 검색 품질 측정

```bash
uv run eval.py -k 5 --per-file 1 2 3
```

`golden.jsonl`의 질문으로 Hit@k, MRR, 개요형 질문의 Note Recall을 계산합니다.

## 새 노트 추가

`notes/`에 파일을 추가하고 `groups.md`에 알맞은 묶음으로 경로를 넣은 뒤 `uv run rag.py index`를 다시 실행합니다.
