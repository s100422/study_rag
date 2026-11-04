"""학습노트 검색 웹앱.  uv run streamlit run app.py"""
import streamlit as st
from google import genai

import rag

st.set_page_config(page_title="학습노트 검색", page_icon="📚", layout="wide")


@st.cache_resource
def get_client():
    return genai.Client()


def get_conn():
    # DB 컨테이너를 껐다 켜면 캐시된 연결이 끊기므로 닫힌 경우 다시 연결한다
    conn = st.session_state.get("conn")
    if conn is None or conn.closed:
        conn = st.session_state["conn"] = rag.connect()
    return conn


def show_source(label: str, row: tuple, expanded: bool = False):
    path, line, lesson, heading, content, score = row
    with st.expander(f"{label} {lesson} › {heading}", expanded=expanded):
        st.caption(f"`{path}:{line}`" + (f" · 유사도 {score:.3f}" if score is not None else ""))
        st.markdown(content)


with st.sidebar:
    st.title("📚 학습노트 검색")
    mode = st.radio("모드", ["답변 (ask)", "검색만 (search)"],
                    help="답변: 노트를 근거로 LLM이 출처를 달아 정리. 검색만: 비슷한 섹션 목록만 표시(LLM 호출 없음).")
    if mode.startswith("검색"):
        k = st.slider("결과 개수", 3, 20, 5)
        per_file = st.slider("노트당 최대 섹션", 1, 5, rag.PER_FILE,
                             help="1~2는 여러 노트를 고르게, 3 이상은 한 노트를 깊게 보여줍니다.")

if new_query := st.chat_input("궁금한 내용을 입력하세요 (예: N+1 문제 해결 방법)"):
    st.session_state["query"] = new_query
query = st.session_state.get("query")  # 모드·슬라이더를 바꿔도 마지막 질문으로 다시 보여준다
if not query:
    st.info("질문이나 키워드를 입력하세요. 노트에 없는 내용은 '찾을 수 없다'고 답합니다.")
    st.stop()

st.chat_message("user").write(query)
try:
    client, conn = get_client(), get_conn()
except Exception as e:  # DB 컨테이너가 꺼져 있는 경우가 대부분
    st.error(f"DB에 연결하지 못했어요. Docker Desktop과 컨테이너(`docker compose up -d db`)를 확인해 주세요.\n\n{e}")
    st.stop()

with st.chat_message("assistant"):
    try:
        if mode.startswith("검색"):
            rows = rag.retrieve(client, conn, query, k, per_file)
            for i, row in enumerate(rows, 1):
                show_source(f"[{i}]", row, expanded=i == 1)
        else:
            with st.spinner("노트에서 찾는 중..."):
                rows = rag.ask_context(client, conn, query)
            answer = st.write_stream(rag.answer_stream(client, rows, query))
            cited = rag.cited_rows(rows, answer)
            if cited:
                st.divider()
                st.caption("출처")
                for i, row in cited:
                    show_source(f"[{i}]", row)
    except Exception as e:
        st.error(f"요청에 실패했어요: {e}")
