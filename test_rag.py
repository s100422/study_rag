from rag import parse_note

note = """---
lesson: 테스트
tags: [a, b]
---

# 제목

## 첫 섹션
본문1
```python
## 코드 안 주석은 섹션이 아님
```

## 빈 섹션

## 둘째 섹션
본문2
"""
meta, secs = parse_note(note)
assert meta["lesson"] == "테스트" and meta["tags"] == ["a", "b"]
assert [s["heading"] for s in secs] == ["첫 섹션", "둘째 섹션"]
assert secs[0]["line"] == 8 and "코드 안 주석" in secs[0]["body"]
print("ok")
