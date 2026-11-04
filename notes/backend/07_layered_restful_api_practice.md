---
part: backend
lesson: 레이어드 아키텍쳐를 활용한 RESTful API 제작 실습
order: 7
source_type: web
tags: [fastapi, layered-architecture, router, service, repository, pydantic, restful-api, validation]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1441/
note: 개인 학습용 요약. 외부 공유 금지.
---

# 레이어드 아키텍쳐를 활용한 RESTful API 제작 실습

## 레이어드 아키텍쳐 RESTful API 실습 요약
레이어드 아키텍쳐 실습은 상품 관리 시스템의 등록·목록 조회·상세 조회·수정 API를 Router → Service → Repository 구조로 직접 만드는 과제이다. 데이터는 DB 없이 메모리의 리스트에 저장한다. (강의 페이지는 요구사항 명세만 제공하고 정답 코드는 없다.)

## 상품 관리 API 실습의 계층별 역할
상품 관리 API 실습에서 각 구성 요소가 맡는 일은 다음과 같다.
- Pydantic 모델: 요청·응답 필드와 타입을 정의하고, `Field`로 길이·범위·기본값을 건다.
- Router: 요청을 받아 Service를 호출하고, `response_model`과 상태 코드를 지정한다.
- Service: 할인 조건 검사, 상품 존재 여부 확인, 응답용 계산값(`final_price`, `is_sold_out`) 계산을 맡는다.
- Repository: 상품 ID를 부여하고, 리스트에 저장·조회·수정한다.

## 상품 관리 API 실습의 Product 데이터
상품 관리 API의 저장소가 다루는 Product 객체는 다음 필드를 가진다. `id`는 저장 시 서버(Repository)가 부여한다.
- `id: int`: 상품 고유 식별자
- `name: str`: 상품명
- `price: int`: 할인 전 가격
- `discount_price: int`: 가격에서 빼는 할인 금액
- `stock: int`: 재고 수량
- `category: str`: 카테고리

## 상품 관리 API 실습의 요청 모델 ProductCreate·ProductUpdate
상품 관리 API의 `ProductCreate`와 `ProductUpdate`는 같은 필드·조건을 가진다.
- `name: str`: 2~50자, 필수
- `price: int`: 100 이상, 필수
- `discount_price: int`: 0 이상, 기본값 0
- `stock: int`: 0 이상, 기본값 10
- `category: str`: 2자 이상, 필수

수정(PUT)은 상품 정보 전체를 교체하는 방식이다. 그래서 수정 요청에도 `name`, `price`, `category`를 꼭 넣어야 하고, `discount_price`와 `stock`을 빼면 기본값(0, 10)이 들어간다. 필드 조건 위반은 Pydantic이 자동으로 422를 돌려준다.

## 상품 관리 API 실습의 응답 모델
상품 관리 API는 목록용과 상세용 응답 모델을 따로 둔다.
- `ProductListResponse`: `id: int`, `name: str`, `final_price: int`, `category: str`
- `ProductDetailResponse`: 목록 응답 필드 전부 + `stock: int`, `is_sold_out: bool`

`final_price`와 `is_sold_out`은 저장된 값이 아니라 Service가 계산해서 응답 데이터에 넣는 값이다. 가격·할인·재고가 바뀌면 응답에도 바뀐 값으로 다시 계산되어야 한다.

## 상품 관리 API 실습의 Service 처리 규칙
상품 관리 API의 Service는 다음 규칙을 지킨다.
- 등록·수정 시 `discount_price`는 `price`보다 작아야 한다. 아니면 `HTTPException`으로 422를 낸다.
- 상세 조회·수정 시 대상 상품이 없으면 404를 낸다.
- `final_price = price - discount_price`
- `is_sold_out`은 `stock == 0`이면 `True`, 그 외 `False`
- 검증을 통과한 경우에만 저장·수정한다. 검증 실패 시 기존 데이터는 바뀌면 안 된다(검사를 먼저 하고 그다음 Repository를 호출).

## 상품 관리 API 실습의 엔드포인트 목록
상품 관리 API는 네 개의 엔드포인트를 가진다.
- `POST /products`: 요청 `ProductCreate`, 성공 201, 응답 `ProductDetailResponse`
- `GET /products`: 선택 쿼리 파라미터 `keyword`, 성공 200, 응답 `list[ProductListResponse]`
- `GET /products/{product_id}`: 경로 파라미터 `product_id: int`, 성공 200, 응답 `ProductDetailResponse`
- `PUT /products/{product_id}`: `product_id: int`와 `ProductUpdate`, 성공 200, 응답 `ProductDetailResponse`

## 상품 관리 API 실습의 목록 조회와 keyword 검색
상품 목록 조회 `GET /products`는 쿼리 파라미터 `keyword`로 상품명 검색을 지원한다.
```python
keyword: str | None = None
```
- `keyword`가 상품명에 포함된 상품만 돌려준다. 예: `GET /products?keyword=키보드`
- `keyword`를 생략하거나 빈 문자열이면 전체 목록을 돌려준다.
- 검색 결과가 없으면 빈 리스트 `[]`를 돌려준다.

## 상품 관리 API 실습 테스트 1: 정상 등록 데이터
상품 관리 API의 정상 등록을 확인하는 `POST /products` 요청 본문이다.
```json
{
  "name": "기계식 키보드",
  "price": 120000,
  "discount_price": 20000,
  "stock": 50,
  "category": "전자제품"
}
```
- 201 응답에서 `final_price`가 100000, `is_sold_out`이 `false`인지 확인한다.

## 상품 관리 API 실습 테스트 2: 기본값 확인 데이터
상품 관리 API에서 `discount_price`와 `stock`을 생략했을 때 기본값이 적용되는지 확인하는 등록 요청이다.
```json
{
  "name": "심플 에코백",
  "price": 15000,
  "category": "패션잡화"
}
```
- 할인 0, 재고 10이 적용되어 응답은 `final_price` 15000, `stock` 10, `is_sold_out` `false`여야 한다.

## 상품 관리 API 실습 테스트 3: 품절 상품 데이터
상품 관리 API는 재고가 0인 상품도 등록할 수 있어야 한다.
```json
{
  "name": "텀블러",
  "price": 25000,
  "discount_price": 2500,
  "stock": 0,
  "category": "생활용품"
}
```
- 응답의 `final_price`는 22500, `is_sold_out`은 `true`여야 한다.

## 상품 관리 API 실습 테스트 4: 검증 실패 확인
상품 관리 API의 검증은 정상 등록 데이터(기계식 키보드, price 120000)에서 값 하나씩만 바꿔 확인한다.
- `name`을 `"A"`로 등록 → 필드 검증 실패 422
- `price`를 99로 등록 → 필드 검증 실패 422
- `stock`을 -1로 등록 → 필드 검증 실패 422
- `discount_price`를 -1로 등록 → 필드 검증 실패 422
- `discount_price`를 120000으로 등록·수정 → Service 할인 조건 검사 실패 422
- 검증에 실패한 등록·수정 뒤 다시 조회 → 잘못된 데이터가 저장·반영되지 않아야 한다.

## 상품 관리 API 실습 테스트 5: 수정·목록·404 확인
상품 관리 API의 수정 요청은 생성 응답에서 받은 ID를 사용한다.
- 수정 요청에서 `stock`을 0으로 변경 → 200, `is_sold_out`이 `true`로 바뀐다.
- 수정 요청에서 `discount_price`를 10000으로 변경 → 200, `final_price`가 110000으로 바뀐다.
- 목록 조회 → 각 항목에 `id`, `name`, `final_price`, `category`만 있어야 한다.
- 없는 ID로 상세 조회, 또는 정상 데이터로 수정 → 404

## 레이어드 아키텍쳐 RESTful API 실습 복습 Q&A
- Q. 상품 관리 API에서 `final_price`와 `is_sold_out`은 어느 계층에서 만드나?
  A. Service가 `price - discount_price`, `stock == 0`으로 계산해 응답에 넣는다.
- Q. 상품 등록 시 `discount_price`가 `price` 이상이면 어떤 응답이 나와야 하나?
  A. Service가 `HTTPException`으로 422를 반환하고, 데이터는 저장되지 않아야 한다.
- Q. 상품 수정(PUT)에서 `stock`을 생략하면 어떻게 되나?
  A. 전체 교체 방식이므로 기본값 10이 적용된다.
- Q. 상품 목록 조회에서 `keyword`를 빈 문자열로 보내면?
  A. 전체 목록을 반환한다. 검색 결과가 없을 때는 빈 리스트를 반환한다.
- Q. 상품 ID는 누가 부여하나?
  A. Repository가 저장할 때 부여한다.
