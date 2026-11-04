# 노트 묶음 설명

검색 시 노트를 고르는 데 쓰인다(rag.py index가 읽음). 형식:
`## 묶음 이름` 다음 줄에 설명, 그 아래 `- 경로`(notes/ 기준). 한 노트가 여러 묶음에 들어가도 된다.
노트를 추가하면 맞는 묶음에 경로를 넣고 `uv run rag.py index`를 다시 실행한다.

## FastAPI 기초
FastAPI로 API 서버를 처음 만드는 과정. 엔드포인트, CRUD 게시판, Pydantic 요청·응답 DTO, 쿼리 파라미터, 상태 코드, 유효성 검증.
- backend/01_fastapi_intro.md
- backend/02_simple_board.md
- backend/03_interactive_board.md
- backend/04_query_params_and_response.md
- backend/05_simple_validation.md

## 백엔드 구조 설계
관심사 분리와 Router·Service·Repository 레이어드 아키텍처, 공통 응답 형식과 예외 처리.
- backend/06_layered_architecture.md
- backend/07_layered_restful_api_practice.md
- backend/22_common_response_exception.md

## DB 연동과 SQLAlchemy ORM
FastAPI에 DB를 붙이는 방법. SQLAlchemy 엔진·세션·트랜잭션, ORM 조회와 수정, 더티 체킹, ORM 객체 상태.
- backend/08_board_with_db.md
- backend/09_sqlalchemy.md
- backend/19_session_orm_object_state.md

## 테이블 관계와 로딩 전략
SQLAlchemy 관계 매핑. 1:N, M:N 관계 설정과 cascade, association_proxy, 지연·즉시 로딩과 N+1 문제 해결.
- backend/10_one_to_many.md
- backend/11_one_to_many_practice.md
- backend/12_many_to_many.md
- backend/13_many_to_many_practice.md
- backend/14_n_plus_one_problem.md
- backend/17_posts_with_author.md

## 인증과 인가
로그인 기능 구현 과정. 쿠키·세션·토큰 개념, JWT 발급과 검증, 비밀번호 해싱, 회원가입·로그인, 작성자 권한 검사.
- backend/15_cookie_session_token.md
- backend/16_signup_login.md
- backend/17_posts_with_author.md
- backend/18_auth_practice.md

## 비동기 백엔드
async FastAPI와 비동기 SQLAlchemy. 초기 설정, Alembic 마이그레이션, 비동기 CRUD와 관계 로딩.
- backend/20_async_setup_alembic.md
- backend/21_async_crud.md

## 프론트엔드와 AI 서비스 연결
백엔드를 프론트엔드·AI 기능과 연결하기. CORS, React에서 API 호출, RAG Agent 스트리밍(SSE), 멀티턴 챗봇 저장 구조.
- backend/23_frontend_cors.md
- backend/24_rag_agent_streaming.md
- backend/25_multiturn_chatbot_checkpoint.md

## 도커와 컨테이너 DB
Docker 기본 개념, Compose로 PostgreSQL 실행, 로컬 서버와 컨테이너 DB 연결, 볼륨으로 데이터 유지, pgvector.
- docker/01_docker_basics.md
- docker/02_postgresql_in_docker.md
- docker/03_connect_local_server_to_docker_db.md
- docker/04_volumes.md
- docker/05_postgresql_vector_db.md

## 컨테이너화와 배포
FastAPI를 Dockerfile·Compose로 컨테이너화하고 AWS EC2·RDS·Nginx·HTTPS로 배포.
- docker/06_fastapi_in_docker.md
- docker/07_deployment.md

## 웹 크롤링
웹페이지에서 데이터를 수집하는 방법. requests+BeautifulSoup 정적 크롤링, Playwright 동적 크롤링, 크롤링 주의사항, 크롤링 데이터로 RAG 만들기.
- html/01_beautifulsoup_crawling.md
- html/02_playwright_crawling.md
- web/05_crawling.md
- langchain/33_crawling_parent_child_rag.md

## 웹 프론트엔드 기초
HTML 구조, CSS 선택자, DOM과 JavaScript, SPA·SSR 렌더링 방식.
- web/01_html.md
- web/02_css.md
- web/03_dom_js.md
- web/04_spa.md

## LLM 활용 기초
LLM을 코드로 다루는 기본기. 프롬프트 엔지니어링, LangChain 모델·프롬프트·LCEL, LangSmith 추적, 구조화 출력, Tool 호출.
- langchain/00_prompt_engineering.md
- langchain/01_langchain_basic.md
- langchain/02_langsmith.md
- langchain/04_structured_output.md
- langchain/05_tool_agent.md

## 대화 기억(메모리)
챗봇이 이전 대화를 이어가게 하는 방법. 대화 히스토리와 트리밍, LangGraph Checkpointer·Store, PostgreSQL 영속 저장, 멀티턴 챗봇.
- langchain/03_memory.md
- langchain/13_memory_state.md
- langchain/31_postgres_checkpointer.md
- backend/25_multiturn_chatbot_checkpoint.md

## RAG 기초와 파이프라인
RAG의 기본 흐름. 문서 로드, 청킹(텍스트 분할), 임베딩, 벡터 DB 저장과 검색, LCEL로 RAG 체인 구성, 출처 표시.
- langchain/06_rag_basic.md
- langchain/07_vector_db.md
- langchain/08_rag_pipeline.md
- docker/05_postgresql_vector_db.md

## 청킹과 문서 전처리
문서를 검색 단위로 나누고 정리하는 방법. Text Splitter 종류, Parent-Child 청킹, PDF 표·이미지 추출.
- langchain/06_rag_basic.md
- langchain/33_crawling_parent_child_rag.md
- langchain/34_pdf_table_image_extraction.md

## RAG 검색 고도화
검색 품질을 높이는 기법. MMR, BM25 키워드 검색, 하이브리드 검색, 메타데이터 필터, 리랭크, Agentic RAG의 문서 평가와 질문 재작성, Parent-Child 검색.
- langchain/09_rag_search_advanced.md
- langchain/23_agentic_rag.md
- langchain/33_crawling_parent_child_rag.md

## 평가
RAG와 Agent 성능을 측정하는 방법. Hit@k·MRR 같은 검색 지표, golden set 만들기, LLM-as-judge, LangSmith 실험.
- langchain/10_rag_evaluation.md
- langchain/10_rag_evaluation_practice.md
- langchain/35_rag_golden_set.md
- langchain/30_langgraph_evaluation.md

## LangGraph 기초와 단일 Agent
LangGraph의 State·Node·Edge 그래프, ReAct Agent, 검색 도구를 가진 RAG Agent. Agent를 만드는 기본 방법.
- langchain/11_langgraph_basic.md
- langchain/12_react_agent.md
- langchain/13_memory_state.md
- langchain/14_rag_agent.md

## 에이전트 워크플로 패턴
AI 에이전트(Agent)를 어떻게 구성할지 정하는 설계 패턴·아키텍처 종류. LLM 작업 흐름을 설계하는 대표 패턴. Router(분기), Reflection·Evaluator-Optimizer(자기 개선), Parallelization(병렬), Orchestrator-worker(동적 분배), Plan-and-Execute(계획 후 실행).
- langchain/15_router.md
- langchain/17_reflection.md
- langchain/18_parallelization.md
- langchain/19_orchestrator_worker.md
- langchain/20_plan_and_execute.md

## 멀티에이전트
여러 Agent를 나눠 협력시키는 구조. Subgraph로 그래프 분리, Supervisor가 하위 Agent 지휘, Handoff로 Agent 간 제어 넘기기.
- langchain/24_subgraph.md
- langchain/25_supervisor.md
- langchain/26_handoff.md

## Agent 실행 제어와 체크포인트 활용
Agent 실행을 멈추고, 되돌리고, 복구하는 방법. Human-in-the-Loop 승인, Time Travel(재실행·분기), 장애 허용과 재시도.
- langchain/21_human_in_the_loop.md
- langchain/22_time_travel.md
- langchain/27_fault_tolerance.md
- langchain/13_memory_state.md
- langchain/31_postgres_checkpointer.md

## Agent 안전과 운영
Agent를 안전하게 운영하는 방법. 입력·출력 Guardrail, Tool 실행 통제와 검증, 로깅.
- langchain/16_guardrails.md
- langchain/28_agent_tool_control.md
- langchain/29_langgraph_logging.md

## DB와 연결된 Agent
PostgreSQL을 쓰는 Agent. Checkpointer·Store 영속화, Text-to-SQL 조회 Agent.
- langchain/31_postgres_checkpointer.md
- langchain/32_postgres_agent.md

## LLM 확장과 실행 환경
외부 도구 연결 표준 MCP, 로컬 LLM(Ollama) 실행.
- langchain/36_mcp.md
- langchain/37_local_llm.md
