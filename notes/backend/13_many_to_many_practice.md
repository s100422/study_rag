---
part: backend
lesson: M:N 관계 실습
order: 13
source_type: web
tags: [sqlalchemy, many_to_many, fastapi, collection, product, practice]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1450/
note: 개인 학습용 요약. 외부 공유 금지.
---

# M:N 관계 실습

## M:N 관계 실습 요약
`fastapi_ai/fastapi_prac`의 상품 관리 API에 기획전(Collection) 기능을 붙여, 상품과 기획전을 M:N 관계로 연결하는 과제이다. 강의 페이지는 요구사항만 주고 정답 코드는 없다.

## M:N 관계 실습 모델 요구사항: Collection과 ProductCollection
상품과 기획전은 연결 테이블 `product_collections`를 통해 M:N으로 이어진다.
- Collection 모델 (`collections` 테이블)
  - `id`: int, 자동 생성 기본키
  - `name`: str, 1~50자, 필수
- ProductCollection 모델 (`product_collections` 테이블)
  - `id`: int, 자동 생성 기본키
  - `product_id`: int, `products.id` 외래키, 필수
  - `collection_id`: int, `collections.id` 외래키, 필수
- `product_id`와 `collection_id`의 조합은 고유해야 한다 (예: `UniqueConstraint("product_id", "collection_id")`).

## M:N 관계 실습 API 요구사항: 기획전과 상품 연결
- `POST /collections`: 본문 `name`. 기획전 등록 후 id, name 반환 (201)
- `GET /collections`: 기획전 목록. 각 항목에 id, name (200)
- `GET /collections/{collection_id}`: 기획전 id, name과 `products` 목록. 상품별 id, name, final_price, category 포함 (200)
- `POST /collections/{collection_id}/products`: 본문 `product_id`. 기존 상품을 기획전에 연결하고 연결의 id, product_id, collection_id 반환 (201)
- `DELETE /collections/{collection_id}/products/{product_id}`: 연결만 해제. 상품 자체와 다른 기획전 연결은 유지, 응답 본문 없음 (204)

## M:N 관계 실습 오류 응답 요구사항
- 상품이나 기획전이 없을 때: 404
- 해제하려는 연결이 없을 때: 404
- 같은 기획전에 같은 상품을 다시 연결할 때: 400
- 기획전 이름이 1~50자 조건을 벗어날 때: 422 (Pydantic `Field(min_length=1, max_length=50)` 검증)
- 상품이 하나도 연결되지 않은 기획전의 `products`는 빈 목록이다.

## M:N 관계 실습 구현 방향 메모
과제 본문에는 구현 코드가 없으므로, 게시글-태그 M:N 예제와 같은 패턴을 적용하면 된다 (내 정리).
```python
class ProductCollection(Base):
    __tablename__ = "product_collections"
    __table_args__ = (
        UniqueConstraint("product_id", "collection_id",
                         name="uq_product_collection"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), nullable=False)
```
- Collection 쪽에 `relationship(..., cascade="all, delete-orphan")`과 `association_proxy`를 두면 연결 해제 시 연결 행만 지울 수 있다.
- 중복 연결은 EXISTS 조회로 먼저 검사해 400을 돌려준다.

## M:N 관계 실습 복습 Q&A
- Q. 상품-기획전 M:N 실습에서 연결 테이블 이름과 필수 컬럼은?
  A. `product_collections`이며 `product_id`(products.id FK)와 `collection_id`(collections.id FK)가 필수이다.
- Q. 같은 기획전에 같은 상품을 다시 연결하면 어떤 상태 코드를 반환해야 하나?
  A. 400을 반환한다.
- Q. 기획전-상품 연결을 해제할 때 상품 자체는 어떻게 되나?
  A. 연결만 지우고 상품과 다른 기획전의 연결은 유지한다. 응답은 204, 본문 없음이다.
- Q. 기획전 이름이 51자이면 어떤 응답이 나와야 하나?
  A. 1~50자 조건 위반이므로 422이다.
