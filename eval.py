"""golden.jsonl로 검색 품질 측정.

- 단일 정답형 {"q", "path", "heading"}: File/Section Hit@k, Section MRR
- 개요형 {"q", "paths"}: Note Recall@max(k,10) (정답 노트 중 상위 결과에 나온 비율)

uv run eval.py [-k 5] [--per-file 3 1 2 99] [--note-weight 0 0.3] [-v]
"""
import argparse
import json
import sys

from google import genai

from rag import NOTE_WEIGHT, PER_FILE, connect, embed, np, SEARCH_SQL

OVERVIEW_K = 10  # 개요형은 정답 노트가 3~5개라 k=5로는 다 담을 수 없다. -k가 더 크면 -k를 쓴다

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("-k", type=int, default=5)
ap.add_argument("--per-file", type=int, nargs="+", default=[PER_FILE], help="여러 값을 주면 비교")
ap.add_argument("--note-weight", type=float, nargs="+", default=[NOTE_WEIGHT], help="여러 값을 주면 비교")
ap.add_argument("-v", action="store_true", help="틀린 문항 출력")
a = ap.parse_args()
ok = max(a.k, OVERVIEW_K)

golden = [json.loads(l) for l in open("golden.jsonl", encoding="utf-8") if l.strip()]
lookup = [g for g in golden if "paths" not in g]
overview = [g for g in golden if "paths" in g]
client, conn = genai.Client(), connect()
embs = {g["q"]: np.array(embed(client, [g["q"]], "RETRIEVAL_QUERY")[0]) for g in golden}  # 설정별 재호출 방지


def run(q, k, per_file):
    return conn.execute(SEARCH_SQL, {"e": embs[q], "k": k, "per_file": per_file, "w": w}).fetchall()


for w, pf in [(w, pf) for w in a.note_weight for pf in a.per_file]:
    file_hit = sec_hit = rr = 0.0
    for g in lookup:
        rows = run(g["q"], a.k, pf)
        secs = [(r[0], r[3]) for r in rows]
        target = (g["path"], g["heading"])
        rank = secs.index(target) + 1 if target in secs else 0
        file_hit += g["path"] in [r[0] for r in rows]
        sec_hit += rank > 0
        rr += 1 / rank if rank else 0
        if a.v and rank != 1:
            got = f"{rows[0][0]} › {rows[0][3]}" if rows else "(결과 없음)"
            print(f"[{'rank ' + str(rank) if rank else 'MISS'}] {g['q']}\n   기대: {g['path']} › {g['heading']}\n   1위: {got}")

    recall = 0.0
    for g in overview:
        found = {r[0] for r in run(g["q"], ok, pf)} & set(g["paths"])
        recall += len(found) / len(g["paths"])
        if a.v and len(found) < len(g["paths"]):
            print(f"[누락 {len(found)}/{len(g['paths'])}] {g['q']}: {sorted(set(g['paths']) - found)}")

    n, m = len(lookup), len(overview)
    print(f"w={w:<4} per_file={pf:<3} 단일 {n}문항 File Hit@{a.k} {file_hit / n:.2f}  Section Hit@{a.k} {sec_hit / n:.2f}"
          f"  MRR {rr / n:.2f}  |  개요 {m}문항 Note Recall@{ok} {recall / m:.2f}")
