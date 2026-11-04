"""notes/ 학습자료 검색 RAG.

uv run rag.py index            # notes/ 를 pgvector에 인덱싱 (바뀐 파일만)
uv run rag.py search "질문" [-k 5] [--per-file 3]
uv run rag.py ask "질문"   # 노트 근거로 LLM이 출처 번호를 달아 답변
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import psycopg
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pgvector.psycopg import register_vector

load_dotenv()
NOTES = Path(__file__).parent / "notes"
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1234@127.0.0.1:5434/study_rag")
MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.6-flash")
DIM = 768

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
    id serial PRIMARY KEY,
    path text NOT NULL,
    line int NOT NULL,
    part text, lesson text, heading text,
    tags text[],
    content text NOT NULL,
    file_hash text NOT NULL,
    embedding vector({DIM}) NOT NULL
);
-- 노트 단위 임베딩(제목·태그·묶음 설명·요약). 질문과 관련된 노트를 고르는 데 쓴다.
CREATE TABLE IF NOT EXISTS notes (
    path text PRIMARY KEY,
    text_hash text NOT NULL,
    embedding vector({DIM}) NOT NULL
);
"""
GROUPS = Path(__file__).parent / "groups.md"


def parse_groups(text: str) -> dict[str, list[str]]:
    """groups.md → {notes/경로: ["묶음 이름: 설명", ...]}"""
    out, name, desc = {}, None, []
    for ln in text.splitlines():
        if ln.startswith("## "):
            name, desc = ln[3:].strip(), []
        elif name and ln.startswith("- "):
            out.setdefault("notes/" + ln[2:].strip(), []).append(f"{name}: {' '.join(desc)}")
        elif name and ln.strip():
            desc.append(ln.strip())
    return out


def parse_note(text: str) -> tuple[dict, list[dict]]:
    """frontmatter와 `## ` 섹션 목록(제목, 시작 줄 번호, 본문)을 돌려준다."""
    lines = text.splitlines()
    meta, start = {}, 0
    if lines and lines[0].strip() == "---":
        end = lines.index("---", 1)
        for ln in lines[1:end]:
            key, _, val = ln.partition(":")
            meta[key.strip()] = val.strip()
        start = end + 1
    meta["tags"] = [t.strip() for t in meta.get("tags", "").strip("[]").split(",") if t.strip()]

    sections, cur, in_code = [], None, False
    for i in range(start, len(lines)):
        ln = lines[i]
        if ln.startswith("```"):
            in_code = not in_code
        if not in_code and ln.startswith("## "):
            cur = {"heading": ln[3:].strip(), "line": i + 1, "body": []}
            sections.append(cur)
        elif cur:
            cur["body"].append(ln)
    for s in sections:
        s["body"] = "\n".join(s["body"]).strip()
    return meta, [s for s in sections if s["body"]]


def embed(client, texts: list[str], task: str) -> list[list[float]]:
    out = []
    for i in range(0, len(texts), 100):  # API 배치 한도 100
        batch = [types.Content(parts=[types.Part(text=t)]) for t in texts[i:i + 100]]
        res = client.models.embed_content(
            model=MODEL, contents=batch,
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=DIM))
        assert len(res.embeddings) == len(batch), "임베딩 개수가 입력과 다름"
        out += [e.values for e in res.embeddings]
    return out


def connect():
    conn = psycopg.connect(DB_URL, autocommit=True)
    conn.execute(SCHEMA)
    register_vector(conn)
    return conn


def index():
    client, conn = genai.Client(), connect()
    files = sorted(NOTES.rglob("*.md"))
    rel = [p.relative_to(NOTES.parent).as_posix() for p in files]
    known = dict(conn.execute("SELECT DISTINCT path, file_hash FROM chunks").fetchall())

    gone = set(known) - set(rel)
    if gone:
        conn.execute("DELETE FROM chunks WHERE path = ANY(%s)", (list(gone),))
    changed = 0
    for p, path in zip(files, rel):
        text = p.read_text(encoding="utf-8")
        h = hashlib.sha256(text.encode()).hexdigest()
        if known.get(path) == h:
            continue
        meta, secs = parse_note(text)
        lesson = meta.get("lesson", p.stem)
        docs = [f"{lesson} > {s['heading']}\n{s['body']}" for s in secs]
        vecs = embed(client, docs, "RETRIEVAL_DOCUMENT")
        with conn.transaction():  # 파일 단위로 교체해서 중간 실패 시 반쪽 데이터가 남지 않게
            conn.execute("DELETE FROM chunks WHERE path = %s", (path,))
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks (path, line, part, lesson, heading, tags, content, file_hash, embedding)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    [(path, s["line"], meta.get("part"), lesson, s["heading"], meta["tags"],
                      s["body"], h, v) for s, v in zip(secs, vecs)])
        changed += 1
        print(f"indexed {path} ({len(secs)} sections)")
    total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    print(f"done: {changed} files updated, {len(gone)} removed, {total} chunks total")
    index_notes(client, conn, files, rel)


def index_notes(client, conn, files, rel):
    groups = parse_groups(GROUPS.read_text(encoding="utf-8"))
    for path in sorted(set(groups) - set(rel)):
        print(f"warning: groups.md에 없는 노트 경로 {path}")
    for path in rel:
        if path not in groups:
            print(f"warning: 묶음이 없는 노트 {path}")
    known = dict(conn.execute("SELECT path, text_hash FROM notes").fetchall())
    conn.execute("DELETE FROM notes WHERE NOT path = ANY(%s)", (rel,))
    todo = []
    for p, path in zip(files, rel):
        meta, secs = parse_note(p.read_text(encoding="utf-8"))
        summary = secs[0]["body"] if secs else ""  # 노트 첫 섹션은 보통 "~ 요약"
        text = "\n".join([f"{meta.get('lesson', p.stem)} [{', '.join(meta['tags'])}]",
                          *groups.get(path, []), summary])
        h = hashlib.sha256(text.encode()).hexdigest()
        if known.get(path) != h:
            todo.append((path, h, text))
    if todo:
        vecs = embed(client, [t for _, _, t in todo], "RETRIEVAL_DOCUMENT")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO notes VALUES (%s,%s,%s) ON CONFLICT (path) DO UPDATE"
                " SET text_hash = EXCLUDED.text_hash, embedding = EXCLUDED.embedding",
                [(path, h, v) for (path, h, _), v in zip(todo, vecs)])
    print(f"notes: {len(todo)} note summaries updated")


# 벡터 검색만 쓴다. pg_trgm 키워드 검색을 RRF로 섞어 봤지만 golden.jsonl 기준으로
# 가중치 0.25~1, 식별자 전용 모두 벡터 단독보다 낮았다(MRR 0.69~0.74 vs 0.76).
# 파일당 최대 per_file개만 남겨 결과가 한 노트에 몰리지 않게 한다.
# 점수 = (1-w)·섹션 유사도 + w·노트 유사도. 노트 유사도(groups.md 묶음 설명 포함)가
# "에이전트 구성방법"처럼 섹션 단어와 겹치지 않는 질문에서 관련 노트를 끌어올린다.
SEARCH_SQL = """
SELECT path, line, lesson, heading, content, score FROM (
    SELECT c.*, (1 - %(w)s) * (1 - (c.embedding <=> %(e)s)) + %(w)s * (1 - (n.embedding <=> %(e)s)) AS score,
           row_number() OVER (PARTITION BY c.path ORDER BY c.embedding <=> %(e)s) AS rn
    FROM chunks c JOIN notes n USING (path)) x
WHERE rn <= %(per_file)s ORDER BY score DESC LIMIT %(k)s
"""
# search는 사람이 순위를 보므로 MRR이 가장 높은 w=0(노트 점수 미사용).
# ask는 LLM이 결과를 다 읽으므로 순위보다 노트 다양성이 중요: w=0 → 0.7로 올리면
# 단일 Section Hit은 그대로, 개요형 Note Recall이 오른다(k=10·파일당 2개에서 0.75 → 0.85).
NOTE_WEIGHT = 0.0
ASK_NOTE_WEIGHT = 0.7
# golden.jsonl(섹션 하나 찾기) 기준 MRR: 1개 0.64, 2개 0.73, 3개 0.75, 제한 없음 0.76.
# 3개면 정확한 검색 손해가 거의 없다. 개요형 질문은 --per-file 1~2가 더 다양하게 나온다.
PER_FILE = 3


def retrieve(client, conn, query: str, k: int, per_file: int = PER_FILE,
             note_weight: float = NOTE_WEIGHT) -> list[tuple]:
    """(path, line, lesson, heading, content, 점수) 목록."""
    e = embed(client, [query], "RETRIEVAL_QUERY")[0]
    return conn.execute(SEARCH_SQL, {"e": np.array(e), "k": k, "per_file": per_file,
                                     "w": note_weight}).fetchall()


def search(query: str, k: int, per_file: int):
    rows = retrieve(genai.Client(), connect(), query, k, per_file)
    for i, (path, line, lesson, heading, content, score) in enumerate(rows, 1):
        snippet = " ".join(content.split())[:240]
        print(f"[{i}] {path}:{line}  ({score:.4f})\n    {lesson} › {heading}\n    {snippet}…\n")


ANSWER_RULES = """너는 사용자의 학습 노트만 근거로 답하는 학습 도우미다.
규칙:
1. 아래 [노트 발췌]에 있는 내용만 써라. 발췌에 없는 내용은 지어내지 마라.
2. 문장이나 항목마다 근거 발췌 번호를 [1], [2] 형태로 붙여라.
3. 발췌로 답할 수 없으면 "노트에서 찾을 수 없습니다."라고만 답하고, 일부만 답할 수 있으면 답할 수 있는 부분만 답한 뒤 빠진 부분을 밝혀라.
4. "어떤 게 있어?" 같은 질문은 발췌에 나온 항목을 빠짐없이 모아 목록으로 정리하라.
5. 한국어로 간결하게 답하라."""


def ask_context(client, conn, query: str) -> list[tuple]:
    """깊게(상위 10개, 파일당 3개) + 넓게(상위 20개, 파일당 1개)를 합친다. 평균 약 26개 섹션.
    한 가지만 쓰면 둘 중 하나를 놓쳤다: 20개·파일당 3개는 넓은 질문("ai agent 구성방법")에서
    워크플로 패턴 노트를 2/5만, 20개·파일당 1개는 단일 정답 섹션을 0.65만 찾았다.
    합치면 단일 Section Hit 0.95, 개요 Recall 1.00, 넓은 질문 워크플로 노트 5/5."""
    e = np.array(embed(client, [query], "RETRIEVAL_QUERY")[0])
    rows, seen = [], set()
    for k, pf in [(10, 3), (20, 1)]:
        for r in conn.execute(SEARCH_SQL, {"e": e, "k": k, "per_file": pf, "w": ASK_NOTE_WEIGHT}):
            if (r[0], r[1]) not in seen:
                seen.add((r[0], r[1]))
                rows.append(r)
    return rows


def answer_stream(client, rows: list[tuple], query: str):
    """검색된 섹션을 근거로 답변 텍스트 조각을 차례로 내보낸다."""
    context = "\n\n".join(f"[{i}] {lesson} › {heading}\n{content}"
                          for i, (_, _, lesson, heading, content, _) in enumerate(rows, 1))
    for chunk in client.models.generate_content_stream(
            model=LLM_MODEL, contents=f"[노트 발췌]\n{context}\n\n[질문]\n{query}",
            config=types.GenerateContentConfig(system_instruction=ANSWER_RULES)):
        yield chunk.text or ""


def cited_rows(rows: list[tuple], answer: str) -> list[tuple[int, tuple]]:
    """답변에서 실제로 인용한 발췌만 (번호, 행)으로 돌려준다."""
    return [(i, r) for i, r in enumerate(rows, 1) if f"[{i}]" in answer]


def ask(query: str):
    client = genai.Client()
    rows = ask_context(client, connect(), query)
    answer = ""
    for text in answer_stream(client, rows, query):
        print(text, end="", flush=True)
        answer += text
    cited = cited_rows(rows, answer)
    print("\n\n출처:" if cited else "")
    for i, (path, line, lesson, heading, _, _) in cited:
        print(f"  [{i}] {path}:{line}  {lesson} › {heading}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 한글 출력
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index")
    sp = sub.add_parser("search")
    sp.add_argument("query")
    sp.add_argument("-k", type=int, default=5)
    sp.add_argument("--per-file", type=int, default=PER_FILE, help="한 노트에서 가져올 최대 섹션 수")
    aq = sub.add_parser("ask")
    aq.add_argument("query")
    a = ap.parse_args()
    if a.cmd == "index":
        index()
    elif a.cmd == "search":
        search(a.query, a.k, a.per_file)
    else:
        ask(a.query)
