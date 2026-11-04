---
part: backend
lesson: AUTH 실습
order: 18
source_type: web
tags: [fastapi, auth, jwt, argon2, wishlist, signup, login]
source: https://ucanlabs.kr/classroom/aicampus-agent-python/lesson/1456/
note: 개인 학습용 요약. 외부 공유 금지.
---

# AUTH 실습

## AUTH 실습 요약
AUTH 실습은 fastapi_ai/fastapi_prac의 상품 관리 API에 회원가입·로그인과 사용자별 상품 위시리스트를 추가하는 과제이다. 강의 페이지는 요구사항 명세만 제공하고 정답 코드는 없다.

## AUTH 실습 User 모델(users 테이블) 요구사항
AUTH 실습의 User 모델은 users 테이블에 다음 필드를 가진다.
- `id`(int): 자동 생성되는 기본키.
- `email`(str): 최대 254자, 중복 불가, 필수.
- `hashed_password`(str): 비밀번호 해시값, 필수.
- `created_at`(datetime): 가입 시각, DB가 자동 생성.

이메일은 유효한 형식인지 검증하고 소문자로 바꿔 저장·조회한다. 회원가입 비밀번호는 15~128자이고 Argon2id로 해싱해 저장한다. 응답에는 비밀번호와 해시를 넣지 않는다.

## AUTH 실습 인증 API 명세
AUTH 실습의 인증 API는 세 개이다.
- `POST /auth/signup`: 본문 email, password. 가입 후 id, email, created_at 반환. 201.
- `POST /auth/login`: 본문 email, password. `access_token`과 `token_type: "bearer"` 반환. 200.
- `GET /me`: 인증된 사용자의 id, email, created_at 반환. 200.

로그인 비밀번호는 1~128자를 받는다. JWT 페이로드에는 사용자 ID를 문자열로 넣은 `sub`, 발급 시각 `iat`, 만료 시각 `exp`를 담는다. 인증이 필요한 요청은 `Authorization: Bearer <access_token>` 헤더를 보낸다.

## AUTH 실습 인증 API 오류 응답 규칙
AUTH 실습의 회원가입·로그인·`/me`는 상황별로 다음 상태 코드를 반환한다.
- 이미 있는 이메일로 회원가입: 409.
- 가입되지 않은 이메일이나 틀린 비밀번호로 로그인: 401.
- 요청 값이 조건(이메일 형식, 비밀번호 길이 등)에 맞지 않음: 422.
- `/me`에서 토큰이 없거나, 유효하지 않거나, 토큰의 사용자가 없음: 401.

## AUTH 실습 WishlistItem 모델(wishlist_items 테이블) 요구사항
AUTH 실습의 위시리스트는 로그인한 사용자가 기존 상품을 담는 기능이며, WishlistItem 모델은 다음 필드를 가진다.
- `id`(int): 자동 생성되는 기본키.
- `user_id`(int): `users.id`를 참조하는 외래키, 필수.
- `product_id`(int): `products.id`를 참조하는 외래키, 필수.

`user_id`와 `product_id` 조합은 고유해야 하지만, 서로 다른 사용자는 같은 상품을 담을 수 있다. `user_id`는 요청 본문으로 받지 않고 인증된 사용자 ID로 넣는다. 상품을 삭제하면 그 상품에 연결된 위시리스트 항목도 함께 삭제되어야 한다.

## AUTH 실습 위시리스트 API 명세
AUTH 실습의 위시리스트 API는 모두 인증이 필요하다.
- `POST /me/wishlist`: 본문 `product_id`. 담은 항목의 id, user_id, product_id 반환. 201.
- `GET /me/wishlist`: 본인 항목 목록. 항목마다 id와 product(id, name, final_price, category) 포함. 담은 것이 없으면 빈 목록. 200.
- `DELETE /me/wishlist/{wishlist_item_id}`: 본인 항목만 삭제. 상품 자체와 다른 사용자의 항목은 유지. 본문 없음. 204.

## AUTH 실습 위시리스트 API 오류 응답 규칙
AUTH 실습의 위시리스트 API는 상황별로 다음 상태 코드를 반환한다.
- 토큰이 없거나, 유효하지 않거나, 토큰의 사용자가 없음: 401.
- 삭제하려는 항목이 다른 사용자의 것: 403.
- 담을 상품이나 삭제할 항목이 없음: 404.
- 본인 위시리스트에 같은 상품을 다시 담음: 400.
- `product_id`가 양의 정수가 아님: 422.

## AUTH 실습 복습 Q&A
- Q. AUTH 실습에서 비밀번호는 어떻게 저장하나?
  A. Argon2id로 해싱한 값만 `hashed_password`에 저장하고, 응답에는 포함하지 않는다.
- Q. AUTH 실습의 JWT에는 어떤 클레임이 들어가나?
  A. 사용자 ID 문자열 `sub`, 발급 시각 `iat`, 만료 시각 `exp`.
- Q. AUTH 실습에서 중복 이메일 가입과 위시리스트 중복 담기의 응답 코드는?
  A. 중복 이메일 가입은 409, 같은 상품 중복 담기는 400이다.
- Q. 위시리스트 항목의 user_id는 어디서 가져오나?
  A. 요청 본문이 아니라 토큰으로 인증된 사용자의 ID를 쓴다.
- Q. 상품을 삭제하면 위시리스트 항목은 어떻게 되나?
  A. 그 상품에 연결된 위시리스트 항목도 함께 삭제된다.
