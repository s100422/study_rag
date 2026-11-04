---
part: langchain
lesson: PDF Table Image Extraction
order: 34
source_type: ipynb
tags: [pdf, pdfplumber, table-extraction, gemini, multimodal, chunking, rag, bbox]
source: C:\Users\tnwls\aim-ai-agent\langchain_\34-pdf-table-image-extraction.ipynb
note: 개인 학습용 요약. 외부 공유 금지.
---

# PDF Table Image Extraction

## PDF Table Image Extraction 요약
PDF 보도자료(태블릿 PC 품질비교시험)에서 표는 pdfplumber로 행·열 구조를 살려 Markdown 표로 바꾸고, 큰 이미지는 Gemini로 읽어 Markdown 텍스트로 만든다. 본문·표·이미지 내용을 블록으로 구분한 뒤 유형별로 RAG 청크를 만든다.
- 흐름: PDF 텍스트 추출 → 표·이미지 내용 정리 → 유형별 구분 → 청킹

## PDF 텍스트 추출의 한계와 PDF 저장 방식
PDF 텍스트 추출(`PyPDFLoader`)은 표의 글자는 꺼내지만 열 이름과 값의 대응, 병합 셀 구조는 잃는다. PDF는 "무엇을 어디에 어떻게 그릴지"만 저장하기 때문이다.
- 글자: 문자, 글꼴·크기, 배치 위치
- 선·도형: 시작/끝점, 위치·크기, 색상
- 이미지: 이미지 데이터와 배치 위치·크기

표처럼 보여도 셀 관계는 저장되지 않으므로, 글자 배치와 선 위치로 구조를 추정해야 한다. 스캔 PDF처럼 페이지 전체가 이미지면 OCR이나 비전 모델이 필요하다.

## pdfplumber가 표를 인식하는 원리
pdfplumber는 PDF 안 선과 글자의 좌표로 표의 행·열을 추정한다.
- 순서: 경계선 찾기 → 교차점 찾기 → 셀 구성 → 표로 묶기 → 글자 추출
- 가로·세로선과 사각형 테두리로 셀 경계를 잡고, 교차점으로 사각형 셀을 만든 뒤 연결된 셀을 하나의 표로 묶는다.
- 셀 안 글자를 행·열 순서로 정리한다.
- 선이 없는 표는 글자 정렬 위치로 추정할 수 있고, 이미지로만 된 표는 OCR/비전 모델이 필요하다.
- bounding box(bbox)는 `(왼쪽, 위쪽, 오른쪽, 아래쪽)` 좌표로, 영역을 잘라내거나 원래 위치를 찾는 데 쓴다.

## PDF 표 추출 실습 1단계: 표 후보 탐색과 시각화
PDF 표 추출은 먼저 전체 페이지에서 `find_tables()`로 표 후보와 bbox를 모은다. 테두리로 둘러싼 안내 박스도 후보로 잡히므로 확인 후 고른다.
```python
table_candidates = []
with pdfplumber.open(pdf_path) as pdf:
    for page_no, page in enumerate(pdf.pages, start=1):
        for table_no, table in enumerate(page.find_tables(), start=1):
            table_candidates.append({"page_no": page_no, "table_no": table_no,
                                     "bbox": table.bbox})
```
- 결과: 15페이지 PDF에서 표 후보 21개.
- `page.to_image(resolution=120).debug_tablefinder()`: 감지한 선(빨강), 교차점(원), 표 영역(파랑)을 페이지 이미지에 그려 보여준다.
- 1페이지 2번째 후보(하단 제품표)를 골라 `page.crop(bbox).to_image()`로 잘라 확인한다.
- `pip install pdfplumber==0.11.10`으로 설치한다.

## PDF 표 추출 실습 2단계: 빠진 경계 보완과 각주 추출
PDF 제품표는 양쪽 바깥 세로선이 없어서, 표 bbox의 좌우 좌표를 `explicit_vertical_lines`로 넣어 경계를 보완한다. 표 아래 `*`로 시작하는 각주 줄도 함께 가져온다.
```python
table_settings = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "explicit_vertical_lines": [table_bbox[0], table_bbox[2]],
}
region = page.crop(table_bbox)
corrected_rows = region.find_tables(table_settings)[0].extract()

footnote_lines = [
    line for line in page.extract_text_lines(return_chars=False)
    if line["top"] >= table_bbox[3] and line["text"].startswith("*")
]
footnotes = "\n".join(line["text"] for line in footnote_lines)
```
- `extract()`: 셀 내용을 행별 리스트로 준다. 병합 셀 자리는 `None`, 셀 안 줄바꿈은 `\n`으로 남는다.
- 표 bbox 하단을 마지막 각주 `bottom`까지 늘린 `table_with_footnotes_bbox`도 만든다(각주 없으면 기존 하단 유지).
- 표가 안 잡히면 ValueError를 내는 부분은 생략.

## PDF 표 추출 실습 3단계: 병합 셀 채우기와 Markdown 표 변환
PDF 표의 병합 셀 때문에 빈 `구분` 값은 직전 값(고가형/저가형)으로 채우고, 셀 줄바꿈·연속 공백은 한 칸으로 정리한다. 그 뒤 Markdown 표 문자열을 만든다.
```python
def normalize_cell(value):
    return " ".join((value or "").split())

headers = [normalize_cell(v) for v in corrected_rows[0]]
rows, current_category = [], ""
for extracted_row in corrected_rows[1:]:
    row = [normalize_cell(v) for v in extracted_row]
    if row[0]:
        current_category = row[0]
    else:
        row[0] = current_category
    rows.append(row)

def markdown_row(values):
    return "| " + " | ".join(v.replace("|", r"\|") for v in values) + " |"
```
- 표 = 헤더행 + `---` 구분행 + 데이터행. 각주의 `*`는 `\*`로 이스케이프해 강조로 해석되지 않게 한다.
- 결과: 7개 열, 4개 제품 행(구분·브랜드·제품명·화면크기·저장용량·본체가격·펜 가격) + 각주 2줄.

## PDF 표 추출 결과 보관 형식
PDF 표 추출 결과는 텍스트와 구조를 함께 dict로 보관한다. 나중에 행 단위 분할과 본문 위치 교체에 쓰기 위해서다.
```python
table_results = [{
    "page_no": TABLE_PAGE_NO,
    "bbox": table_with_footnotes_bbox,
    "content_type": "table",
    "table_id": f"page-{TABLE_PAGE_NO}-table-{TABLE_NO}",
    "text": table_content,          # Markdown 표 + 각주
    "headers": headers,
    "rows": rows,
    "footnotes": footnotes_markdown,
}]
```
- 표가 여러 개면 이 목록에 계속 추가한다.

## PDF 이미지 추출 실습 1단계: 면적 기준으로 이미지 선택
PDF 이미지(`page.images`)에는 로고·아이콘도 섞여 있으므로, 페이지 면적 대비 비율로 읽을 이미지를 고른다.
```python
for page_no, page in enumerate(pdf.pages, start=1):
    page_area = page.width * page.height
    for image_index, img in enumerate(page.images, start=1):
        bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        image_candidates.append({"page_no": page_no, "image_index": image_index,
                                 "bbox": bbox, "area_ratio": area / page_area})

selected_images = [i for i in image_candidates if i["area_ratio"] > 0.10]
```
- bbox를 표와 같은 좌표 순서로 맞춰 같은 교체 함수로 처리할 수 있게 한다.
- 결과: 전체 14개 중 1개(5페이지, 페이지 면적의 65%) 선택.
- 선택 영역을 `crop(...).to_image(resolution=180)`로 렌더링하고 `BytesIO`에 PNG로 저장해 `image_bytes`로 보관한다.

## PDF 이미지 추출 실습 2단계: Gemini 추출 지시문
PDF 이미지 내용을 Gemini로 읽을 때는 요약이 아니라 보존을 요청한다. 모델은 `ChatGoogleGenerativeAI(model="gemini-3.6-flash", timeout=90, max_retries=1)`이고, API 키는 `.env`에서 `load_dotenv`로 읽는다.

지시문의 핵심 규칙(내 말로 정리):
- 제목·본문을 읽기 순서대로, 요약·생략 없이 작성
- 표는 열 이름과 값 관계가 드러나는 Markdown 표로
- 수치·단위·제품명·각주 보존, 각주 번호와 수치 구분
- 그림 설명은 `[그림 설명]`, 읽을 수 없는 부분은 `[확인 불가]`로 표시하고 추측 금지
- 결과 전체를 코드 블록으로 감싸지 않기

## PDF 이미지 추출 실습 3단계: 이미지를 Gemini에 전달
PDF 이미지는 PNG 바이트를 Base64로 인코딩해 텍스트 지시문과 함께 하나의 `HumanMessage`에 담아 보낸다.
```python
message = HumanMessage(content=[
    {"type": "text", "text": extraction_prompt},
    {"type": "image",
     "base64": base64.b64encode(image_info["image_bytes"]).decode("ascii"),
     "mime_type": "image/png"},
])
image_text = parser.invoke(llm.invoke([message])).strip()
if not image_text:
    raise ValueError("추출 결과가 비어 있습니다.")
image_results.append({"page_no": ..., "image_index": ..., "bbox": image_info["bbox"],
                      "content_type": "image",
                      "image_id": f"page-{p}-image-{i}", "text": image_text})
```
- 빈 응답이면 기존 영역을 빈 내용으로 덮지 않도록 중단한다.
- bbox를 저장해 해석 결과를 원래 페이지 위치에 넣는다. (dict 값 일부는 `...`로 축약)
- 결과 Markdown은 원본 이미지와 비교해 숫자를 검증한다. AFC 관련 경고가 한 번 출력된다.

## PDF 청킹 전 본문·표·이미지를 구분하는 이유
PDF 추출 내용을 한꺼번에 길이 기준으로 청킹하면 표 중간이 잘려 열 이름, 데이터 행, 각주가 서로 다른 청크로 흩어진다. 그러면 청크 하나만 검색됐을 때 제품명·가격·단위 관계를 읽을 수 없다.

그래서 청킹 전에 본문 텍스트, 표, 이미지 해석 내용을 블록으로 구분한다. 본문과 이미지 해석 텍스트는 일반 청킹, 표는 크기에 따라 통째로 두거나 헤더·각주를 붙여 행 단위로 나눈다. 표·이미지 영역 안의 원래 글자는 빼고 그 자리에 정리된 결과를 넣어 중복 없이 원래 순서를 유지한다.
```text
PDF 페이지 → [본문 텍스트] [표] [본문 텍스트] [이미지 해석 결과]
```

## PDF 블록 구성 실습: build_page_blocks
PDF 페이지를 블록 목록으로 만드는 `build_page_blocks(page, regions)`는 글자 중심점이 표·이미지 bbox 안에 있으면 제외하고, 남은 본문 줄과 추출 결과를 위→왼쪽 순으로 정렬한다. (축약)
```python
def outside_regions(obj):
    if obj["object_type"] != "char":
        return True
    cx = (obj["x0"] + obj["x1"]) / 2
    cy = (obj["top"] + obj["bottom"]) / 2
    return not any(r["bbox"][0] <= cx <= r["bbox"][2] and
                   r["bbox"][1] <= cy <= r["bbox"][3] for r in regions)

body_page = page.filter(outside_regions)
blocks = [{"content_type": "text", "text": l["text"],
           "bbox": (l["x0"], l["top"], l["x1"], l["bottom"])}
          for l in body_page.extract_text_lines(return_chars=False)]
blocks.extend(dict(r) for r in regions)
blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
# 이어지는 text 블록끼리는 텍스트와 bbox를 합친다
```
- 원본 PDF는 바꾸지 않고 dict 목록만 반환한다.

## PDF 블록에 메타데이터 붙이기
PDF 전체 페이지를 돌며 표·이미지가 있는 페이지는 `build_page_blocks`로, 없는 페이지는 PyPDFLoader 본문 하나를 text 블록으로 둔다. 각 블록 메타데이터에는 출처와 유형을 담는다.
- `page_no`: 로더의 `page`(0부터)에 1을 더한 값
- `extraction_method`: `pdfplumber+gemini`(이미지 포함), `pdfplumber`(표만), `pypdf`(그 외)
- `content_type`, `block_id`(`page-N-block-M`), 해당 시 `table_id`/`image_id`
- `file_name`과 로더 기본 메타데이터도 유지

비교용으로 페이지별 블록 텍스트를 합친 `rag_documents`도 만든다. 결과: 1페이지는 text 670자 / table 511자 / text 5자, 5페이지는 image 1371자 블록이 생긴다.

## PDF 일반 청킹의 표 분할 문제
PDF 페이지 본문에 `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)`를 적용하면 15페이지에서 청크 23개가 나온다. 1페이지 제품표+각주(511자)는 우연히 한 청크에 들어가지만, 일반 청킹은 표 구조를 모르므로 기준이 작거나 표가 길면 잘린다.

같은 표를 `chunk_size=300, chunk_overlap=0`으로 나누면 255/141/112자 3조각이 되고, 열 이름은 첫 조각에만 남아 뒤 조각은 데이터 행이나 각주만 갖게 된다.

표를 통째로 보호하고 나머지만 일반 청킹하면 표가 잘리지 않지만, 표 청크가 511자로 기준 300자를 넘는다. 길이도 지키려면 행 구조를 써서 나눠야 한다.

## PDF 표 행 단위 분할 함수: split_table_rows
PDF 표의 `split_table_rows()`는 데이터 행 사이에서만 나누고, 모든 조각에 같은 헤더와 각주를 붙인다. 길이 계산에도 헤더·각주·줄바꿈을 포함한다.
```python
def split_table_rows(headers, rows, footnotes="", chunk_size=1000):
    if chunk_size <= 0:
        raise ValueError("chunk_size는 양수여야 합니다.")
    header_lines = [markdown_row(headers), markdown_row(["---"] * len(headers))]
    suffix = f"\n\n{footnotes.strip()}" if footnotes.strip() else ""

    def render_table(group):
        return "\n".join(header_lines + [markdown_row(r) for r in group]) + suffix

    parts, current = [], []
    for row in rows:
        if current and len(render_table(current + [row])) > chunk_size:
            parts.append(render_table(current))
            current = []
        current.append(row)  # 한 행은 자르지 않음(혼자 초과해도 허용)
    if current or not parts:
        parts.append(render_table(current))
    return parts
```
- 표가 기준 안이면 한 조각으로 그대로 유지된다.

## PDF 유형별 청킹 함수: split_document_blocks
PDF 블록용 `split_document_blocks()`는 표가 아니면 일반 청킹, 표면 `split_table_rows`를 쓴다.
```python
def split_document_blocks(blocks, chunk_size=1000, chunk_overlap=0):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size,
                                              chunk_overlap=chunk_overlap)
    chunks = []
    for block in blocks:
        if block["content_type"] != "table":
            doc = Document(page_content=block["text"], metadata=block["metadata"])
            chunks.extend(splitter.split_documents([doc]))
            continue
        parts = split_table_rows(block["headers"], block["rows"],
                                 footnotes=block["footnotes"], chunk_size=chunk_size)
        for part_no, text in enumerate(parts, start=1):
            chunks.append(Document(page_content=text,
                                   metadata={**block["metadata"], "table_part": part_no}))
    return chunks
```
- 표 조각마다 `table_part`(1부터) 순번을 남긴다.

## PDF 유형별 청킹 적용 시 주의점과 확장 방법
PDF 유형별 청킹(`split_document_blocks`)을 300자 기준으로 돌리면 제품표는 284~296자 4조각이 되고 각 조각에 헤더와 각주가 들어간다. PDF 전체에는 청크 63개가 생기며, 문서 순서대로 `chunk_index`를 붙인다. 행 단위 분할은 행·열 구조를 추출한 표(이 예제는 1페이지 제품표)에만 적용된다. 선택하지 않은 표와 이미지 해석 결과 안의 Markdown 표는 일반 청킹 대상이다. 300자는 관찰용 값이며, 1,000자로 늘리면 짧은 제품표는 한 청크로 유지된다.

이후 청크를 임베딩해 벡터 저장소에 넣고 검색한다. 출처 메타데이터 덕분에 검색 결과의 원문 페이지를 확인할 수 있다.
- Contextual Retrieval: LLM이 문서 전체와 청크를 보고 만든 짧은 문맥 설명을 청크 앞에 붙여 임베딩한다.
- 표 요약 기반 검색: 표 요약을 임베딩해 검색하고, 연결된 원본 표를 근거로 쓴다.
- 다른 도구: PyMuPDF(텍스트·이미지), Camelot(표), Tesseract·PaddleOCR(OCR).

## PDF Table Image Extraction 복습 Q&A
- Q. PyPDFLoader만으로 PDF 표를 RAG에 넣으면 어떤 문제가 있나?
  A. 글자는 나오지만 열 이름과 값의 대응, 병합 셀 구조가 사라져 표 의미를 읽기 어렵다.
- Q. pdfplumber 제품표 추출에서 `explicit_vertical_lines`를 쓴 이유는?
  A. 표의 바깥 세로선이 없어서, bbox 좌우 좌표를 명시적 세로 경계로 넣어 열을 제대로 잡기 위해서다.
- Q. PDF 이미지 중 Gemini로 읽을 대상은 어떻게 골랐나?
  A. 페이지 면적 대비 이미지 면적이 10%를 넘는 것만 골라 로고·아이콘을 걸렀다.
- Q. `split_table_rows()`가 일반 청킹보다 나은 점은?
  A. 행 중간을 자르지 않고 모든 조각에 헤더와 각주를 반복해, 조각 하나만 검색돼도 행 의미를 알 수 있다.
- Q. `build_page_blocks()`에서 표·이미지 영역의 원래 글자를 빼는 이유는?
  A. 정리한 표·이미지 결과와 내용이 중복되지 않게 하면서 원래 위치 순서는 유지하기 위해서다.
