---
part: backend
lesson: 1:N 관계 실습
order: 11
source_type: web
tags: [sqlalchemy, one-to-many, relationship, foreignkey, cascade, fastapi, review]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1449/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 1:N 관계 실습

## 1:N 관계 실습 요약
1:N 관계 실습은 `fastapi_ai/fastapi_prac`의 상품 관리 API에 상품(1)–리뷰(N) 관계를 추가하는 과제이다. 리뷰 등록·수정·삭제 API를 만들고, 상품 상세 응답에 리뷰 목록을 넣고, 상품 삭제 시 리뷰도 함께 지운다. (강의 페이지는 요구사항 명세만 있고 정답 코드는 없다.)

## 1:N 관계 실습의 Review 모델(reviews 테이블)
1:N 관계 실습의 리뷰 모델은 `reviews` 테이블에 대응하며 다음 필드를 가진다.
- `id: int`: 리뷰 ID, 자동 생성되는 기본키
- `content: str`: 리뷰 내용, 1자 이상, 필수
- `rating: int`: 평점, 1~5, 필수
- `product_id: int`: 리뷰가 속한 상품 ID, `products.id`를 참조하는 외래키, 필수

상품–리뷰는 게시글–댓글과 같은 구조이므로, 리뷰 쪽에 `ForeignKey("products.id")` 컬럼과 상품 객체 관계 속성을, 상품 쪽에 리뷰 목록 `relationship()`을 두면 된다(게시글–댓글 예제 기준의 적용 방향).

## 1:N 관계 실습의 리뷰 API
1:N 관계 실습에서 리뷰 API는 상품 경로 아래에 둔다. 요청 본문은 `content`, `rating`이다.
- `POST /products/{product_id}/reviews`: 리뷰 등록, 리뷰의 `id`, `content`, `rating` 반환, 201
- `PUT /products/{product_id}/reviews/{review_id}`: 리뷰 내용·평점 수정, 같은 필드 반환, 200
- `DELETE /products/{product_id}/reviews/{review_id}`: 리뷰 삭제, 응답 본문 없음, 204

## 1:N 관계 실습의 상품 API 변경 사항
1:N 관계 실습에서는 기존 상품 API도 다음처럼 바뀐다.
- `GET /products/{product_id}`: 상품 상세 응답에 `reviews` 목록을 추가한다. 리뷰마다 `id`, `content`, `rating`을 담는다. 리뷰가 없는 상품은 `reviews: []`.
- `DELETE /products/{product_id}`: 상품과 그 상품의 리뷰를 함께 삭제한다. 응답 본문 없이 204.

## 1:N 관계 실습의 오류 처리 규칙
1:N 관계 실습의 상품·리뷰 API는 다음 경우 오류를 반환한다.
- 상품이 없거나, 리뷰가 없거나, 리뷰가 URL의 상품에 속하지 않으면 404
- 리뷰 내용(1자 이상)이나 평점(1~5) 조건을 어기면 422

리뷰 소속 검사는 리뷰를 ID로 찾은 뒤 `review is None or review.product_id != product_id`이면 404를 내는 방식으로 할 수 있다(게시글–댓글 예제의 `_get_verified_comment()`와 같은 패턴).

## 1:N 관계 실습 복습 Q&A
- Q. 1:N 관계 실습에서 리뷰 평점의 허용 범위는?
  A. 1~5이며, 벗어나면 422이다.
- Q. 상품 A의 리뷰 ID로 `PUT /products/{상품 B}/reviews/{review_id}`를 보내면?
  A. 리뷰가 URL의 상품에 속하지 않으므로 404이다.
- Q. 상품을 삭제하면 리뷰는 어떻게 되나?
  A. 함께 삭제되어야 한다. 상품 모델의 리뷰 관계에 delete가 포함된 cascade(예: `cascade="all"`)를 두면 된다.
- Q. 리뷰가 없는 상품의 상세 응답에서 `reviews`는?
  A. 빈 목록 `[]`이다.
- Q. 리뷰 삭제 API의 성공 상태 코드는?
  A. 204이고 응답 본문이 없다.
