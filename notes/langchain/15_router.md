---
part: langchain
lesson: Router
order: 15
source_type: ipynb
tags: [router, routing, langgraph, structured-output, semantic-routing, chroma, fallback, hierarchical]
source: C:\Users\tnwls\aim-ai-agent\langchain_\15-router.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# Router

## Router 요약
Router 패턴은 요청을 분류해서 알맞은 전문 노드로 보내는 구조다. 규칙(Deterministic), LLM, 임베딩 유사도(Semantic) 라우팅을 각각 만들고, LangGraph로 Hybrid 라우팅과 Hierarchical 라우팅 그래프를 구성한다.

## Router란
Router는 들어온 요청의 종류를 판단해 처리 경로를 고르는 노드다. 빠르고 확실하게 판단할 수 있으면 바로 전문 노드로 보내고, 애매하면 LLM이 판단하며, 그래도 모르면 fallback(되묻기 등)으로 보낸다.
```text
요청 → 빠르고 확실한 판단 → 전문 노드
              ↓ 애매함
           LLM 판단 → 전문 노드 또는 fallback
```

## Router 라우팅 방식 4가지 비교
- Deterministic: 형식·키워드처럼 확정 가능한 조건에 맞다. 빠르고 결과가 예측 가능하다.
- LLM: 맥락을 해석해야 하는 의도 분류에 맞다. 유연하지만 비용과 지연이 생긴다.
- Semantic: 대표 문장과 의미가 가까운 요청을 고른다. 빠르지만 예시 문장과 threshold에 민감하다.
- Hybrid: 확실한 요청과 애매한 요청이 섞인 환경에 맞다. 비용과 정확도의 균형을 잡기 쉽다.

## Router 실습 준비: 모델과 임베딩 설정
Router 실습은 Gemini 채팅 모델 두 개(일반/lite)와 Gemini 임베딩을 쓴다. API 키는 `.env`에 두고 `load_dotenv()`로 환경변수에 올린다(예: `os.environ["GOOGLE_API_KEY"]`).
```python
from typing import Literal, TypedDict
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
llm_lite = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")
embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
```
- `llm_lite`: 분류처럼 가벼운 판단에 쓰는 저렴한 모델이다.

## Deterministic Routing: 키워드 규칙으로 경로 결정
Deterministic Routing은 state 값을 명시적 규칙으로 검사해 경로를 정한다. 실서비스에선 요청 유형, 주문 상태, 권한, 입력 형식 같은 확실한 조건을 쓰고, 예제는 키워드로 단순화했다. 정확히 한 경로만 맞으면 그 경로, 여러 개거나 없으면 `uncertain`이다.
```python
Route = Literal["refund", "shipping", "general", "uncertain"]
ROUTE_KEYWORDS = {
    "refund": ("환불", "반품", "결제 취소"),
    "shipping": ("배송", "택배", "도착", "운송장"),
    "general": ("회원", "등급", "재질", "영업시간"),
}

def deterministic_route(query: str) -> Route:
    matched = [route for route, words in ROUTE_KEYWORDS.items()
               if any(word in query for word in words)]
    return matched[0] if len(matched) == 1 else "uncertain"
```
```text
상품을 환불하고 싶어요 → refund
반품 수거와 배송 일정을 알려주세요 → uncertain
회원 등급이 궁금해요 → general
```

## LLM Routing: Structured Output으로 목적지 제한
LLM Routing은 `with_structured_output`으로 출력 범주를 `Route` Literal로 묶는다. 어디에도 확실히 속하지 않는 요청을 위해 `uncertain`도 선택지에 넣는다.
```python
class Classification(BaseModel):
    category: Route = Field(description="refund, shipping, general 또는 uncertain")
    reason: str = Field(description="분류 근거 한 문장")

router_prompt = PromptTemplate.from_template(
    """고객 문의를 분류하세요.
refund: 환불·반품·결제 취소
shipping: 배송 조회·도착 일정·운송장
general: 그 밖의 일반 상담
uncertain: 여러 경로가 필요하거나 의도가 불명확함
문의: {query}"""
)
router_chain = router_prompt | llm_lite.with_structured_output(Classification)

def llm_route(query: str) -> Classification:
    return router_chain.invoke({"query": query})
```
- "물건을 돌려보냈는데 다음 절차가 궁금해요"처럼 키워드가 없어도 `refund`로 분류됐다.
- "반품 수거와 배송 일정을 알려주세요"는 LLM이 `refund`로 골랐다(규칙은 `uncertain`).

## LLM Routing에서 reason과 확률값 다루기
LLM Routing의 `reason` 필드는 관찰·디버깅용이고, 실제 분기는 값이 제한된 `category`로만 한다. LLM에게 확률(confidence)을 숫자로 내라고 해도 보정된 확률이 아니므로 그 값을 신뢰도처럼 그대로 쓰면 안 된다.

## Hybrid Routing 1단계: 분류 노드와 fallback
Hybrid Routing은 먼저 규칙으로 분류하고, 규칙이 `uncertain`일 때만 LLM을 부른다. LLM 호출이 실패하면 `uncertain`(되묻기 경로)으로 보낸다. `route_source`에 어떤 방식으로 분류됐는지 기록한다.
```python
class CustomerState(TypedDict, total=False):
    query: str
    category: Route
    route_source: str
    reason: str
    response: str

def classify_hybrid(state: CustomerState):
    category = deterministic_route(state["query"])
    if category != "uncertain":
        return {"category": category, "route_source": "rule", "reason": "단일 규칙 일치"}
    try:
        result = llm_route(state["query"])
        return {"category": result.category, "route_source": "llm", "reason": result.reason}
    except Exception:
        return {"category": "uncertain", "route_source": "fallback", "reason": "분류 호출 실패"}
```

## Hybrid Routing 2단계: 전문 처리 노드
Hybrid Routing 그래프의 처리 노드는 역할(상담원 종류)만 바꿔 같은 `answer` 함수를 호출한다. `uncertain`은 LLM 없이 되묻는 고정 문장을 돌려준다.
```python
def answer(state, role):
    result = llm.invoke(f"{role}로서 안내하세요.\n문의: {state['query']}")
    return {"response": result.text}

def handle_refund(state): return answer(state, "환불 전문 상담원")
def handle_shipping(state): return answer(state, "배송 전문 상담원")
def handle_general(state): return answer(state, "고객 상담원")
def ask_clarification(state):
    return {"response": "환불, 배송, 일반 문의 중 어느 내용인지 구체적으로 알려주세요."}
def route_by_category(state): return state["category"]
```

## Hybrid Routing 3단계: LangGraph 그래프 구성과 실행
Hybrid Routing 그래프는 `classify` 노드 뒤에 조건부 엣지로 네 경로를 연결하고, 각 경로는 END로 끝난다.
```python
ROUTES = ("refund", "shipping", "general", "uncertain")
builder = StateGraph(CustomerState)
builder.add_node("classify", classify_hybrid)
builder.add_node("refund", handle_refund)
builder.add_node("shipping", handle_shipping)
builder.add_node("general", handle_general)
builder.add_node("uncertain", ask_clarification)
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route_by_category, {n: n for n in ROUTES})
for node in ROUTES:
    builder.add_edge(node, END)
hybrid_graph = builder.compile()
```
(코드를 조금 줄임: 원본은 튜플을 두 번 직접 썼고, mermaid 그래프 이미지를 출력한다.)
- 실행 결과: "상품을 환불하고 싶어요"는 `refund rule`, "물건을 돌려보냈는데…"는 `refund llm`, "반품 수거와 새 상품 배송을 함께…"는 `shipping llm`으로 분류됐다.

## Semantic Routing 1단계: 대표 문장을 Chroma에 저장
Semantic Routing은 경로별 대표 문장을 벡터 DB(Chroma)에 넣고, metadata에 경로 이름을 붙여 둔다.
```python
ROUTE_EXAMPLES = {
    "refund": ["상품을 환불하고 싶어요", "결제를 취소하고 싶어요", "반품 방법을 알려주세요"],
    "shipping": ["택배가 언제 오나요", "배송 상태를 조회해 주세요", "운송장이 궁금해요"],
    "general": ["회원 등급이 궁금해요", "상품 재질을 알려주세요", "영업시간이 궁금해요"],
}
route_documents, route_ids = [], []
for route, texts in ROUTE_EXAMPLES.items():
    for index, text in enumerate(texts):
        route_documents.append(Document(page_content=text, metadata={"route": route}))
        route_ids.append(f"{route}-{index}")

route_store = Chroma.from_documents(
    documents=route_documents, embedding=embeddings,
    ids=route_ids, collection_name="semantic-router",
)
```

## Semantic Routing 2단계: threshold로 경로 판정
Semantic Routing은 가장 가까운 문서 1개의 relevance score가 threshold보다 낮으면 `uncertain`으로 본다. threshold와 대표 문장은 검증 데이터로 성공률/실패율을 보며 정하는 값이고, 숫자 자체를 정확하다고 믿으면 안 된다.
```python
SEMANTIC_THRESHOLD = 0.63

def semantic_route(query: str) -> tuple[Route, float]:
    document, score = route_store.similarity_search_with_relevance_scores(query, k=1)[0]
    if score < SEMANTIC_THRESHOLD:
        return "uncertain", score
    return document.metadata["route"], score
```
```text
결제한 돈을 돌려받고 싶어요 → refund (0.731)
내 물건이 어디 있나요? → shipping (0.646)
선물을 추천해 주세요 → uncertain (0.563)
```

## Semantic Routing 3단계: LLM fallback 결합
Semantic Routing이 `uncertain`이면 LLM Routing으로 넘기는 분류 노드다. Hybrid Routing 그래프에서 `classify_hybrid` 대신 이 함수를 `classify` 노드로 등록하면 Semantic + LLM fallback 라우터가 된다.
```python
def classify_semantic_llm(state: CustomerState):
    category, score = semantic_route(state["query"])
    if category != "uncertain":
        return {"category": category, "route_source": "semantic", "reason": f"similarity={score:.3f}"}
    try:
        result = llm_route(state["query"])
        return {"category": result.category, "route_source": "llm_fallback",
                "reason": f"similarity={score:.3f}; {result.reason}"}
    except Exception:
        return {"category": "uncertain", "route_source": "fallback", "reason": "LLM 호출 실패"}
```

## Flat Routing과 Hierarchical Routing 비교
Flat Routing은 Router 하나가 모든 목적지(환불, 배송, 계정, 상품…) 중 하나를 바로 고른다. Hierarchical Routing은 먼저 Domain Router가 큰 영역(예: Finance, Support, Engineering)을 고르고, 각 영역의 하위 Router가 세부 목적지(SQL, RAG, Refund, FAQ, GitHub, Logs 등)를 고른다.
- Flat: Router 호출이 보통 한 번이고, 목적지가 적을 때 맞다.
- Hierarchical: Router를 두 번 이상 거칠 수 있어 latency가 늘 수 있지만, 목적지가 많고 영역 경계가 분명하면 관리와 정확도에 유리하다.
- 목적지가 몇 개 안 되는 고객 문의 예제에는 Flat Router가 적합하다.

## Hierarchical Routing 1단계: 상위·하위 Router 함수
Hierarchical Routing 예제는 구조에 집중하려고 Router 판단을 간단한 키워드 규칙으로 만든다. 상위 Router는 domain(order/account/product)만 고르고, 하위 Router가 세부 목적지를 고른다.
```python
class HierarchicalState(TypedDict, total=False):
    query: str
    domain: Literal["order", "account", "product"]
    destination: str
    response: str

def classify_domain(state):
    q = state["query"]
    if any(w in q for w in ("환불", "배송", "주문")): return {"domain": "order"}
    if any(w in q for w in ("등급", "프로필", "계정")): return {"domain": "account"}
    return {"domain": "product"}

def classify_order(state):
    return {"destination": "refund" if "환불" in state["query"] else "shipping"}
def classify_account(state):
    return {"destination": "grade" if "등급" in state["query"] else "profile"}

```
(if 문을 한 줄로 줄여 적음.)

## Hierarchical Routing 2단계: 계층 그래프 구성
Hierarchical Routing 그래프는 domain_router → 하위 router → 세부 노드 → END로 조건부 엣지를 두 단계 건다.
```python
hb = StateGraph(HierarchicalState)
hb.add_node("domain_router", classify_domain)
hb.add_node("order_router", classify_order)
hb.add_node("account_router", classify_account)
hb.add_node("product", handle_product)
for d in ("refund", "shipping", "grade", "profile"):
    hb.add_node(d, complete)
hb.add_edge(START, "domain_router")
hb.add_conditional_edges("domain_router", route_domain,
    {"order": "order_router", "account": "account_router", "product": "product"})
hb.add_conditional_edges("order_router", route_destination,
    {"refund": "refund", "shipping": "shipping"})
hb.add_conditional_edges("account_router", route_destination,
    {"grade": "grade", "profile": "profile"})
for node in ("refund", "shipping", "grade", "profile", "product"):
    hb.add_edge(node, END)
hierarchical_graph = hb.compile()
```
(변수명 `hierarchy_builder`를 `hb`로 줄임.)

## Hierarchical Routing 3단계: 라우팅 헬퍼와 실행 결과
Hierarchical Routing 그래프에서 조건부 엣지가 쓰는 라우팅 함수와 말단 노드 함수다. 라우팅 함수는 State에 저장된 domain/destination 값을 그대로 돌려준다.
```python
def route_domain(state): return state["domain"]
def route_destination(state): return state["destination"]
def complete(state): return {"response": f"{state['destination']} 경로에서 처리합니다."}
def handle_product(state): return {"destination": "product", "response": "상품 경로에서 처리합니다."}
```
실행 결과(질문 → domain → destination):
```text
주문을 환불하고 싶어요 → order → refund
회원 등급이 궁금해요 → account → grade
상품 재질을 알려주세요 → product → product
```

## Router 평가 기준
Router 성능은 다음 지표로 본다.
- routing accuracy: 올바른 목적지를 고른 비율
- fallback rate: 자동 분류하지 않고 보류(되묻기)한 비율
- unsafe routing rate: 위험한 잘못된 경로로 보낸 비율
- latency: 최종 처리까지 걸린 시간
- token cost: Router와 처리 노드가 쓴 전체 토큰

## Router 복습 Q&A
- Q. Router에서 Hybrid Routing은 어떻게 동작하나?
  A. 먼저 키워드 규칙으로 분류하고, 규칙이 `uncertain`일 때만 LLM으로 분류한다. LLM 호출이 실패하면 되묻기(clarification) 경로로 보낸다.
- Q. LLM Routing 결과에서 분기에 써야 하는 필드는?
  A. Literal로 제한된 `category`다. `reason`은 디버깅용이고, LLM이 낸 확률값은 보정되지 않아 confidence로 쓰면 안 된다.
- Q. Semantic Routing의 threshold는 어떻게 정하나?
  A. 검증 데이터로 성공률/실패율을 보며 실험적으로 정한다. score가 threshold보다 낮으면 `uncertain`으로 보고 LLM fallback을 쓴다.
- Q. Hierarchical Routing은 언제 Flat Routing보다 낫나?
  A. 목적지가 많고 domain 경계가 명확할 때다. 대신 Router를 여러 번 거쳐 latency가 늘 수 있다.
- Q. Router 평가 지표 다섯 가지는?
  A. routing accuracy, fallback rate, unsafe routing rate, latency, token cost.
