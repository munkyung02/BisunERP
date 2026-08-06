# BisunERP v2.4 — 상품관리 Notion 동기화 1단계

## 추가 기능

- 상품관리 화면에 `선택 상품 Notion`, `전체 상품 Notion` 버튼 추가
- ERP 상품을 Notion `상품 DB`에 신규 생성 또는 기존 페이지 갱신
- 상품별 Notion Page ID 저장
- 상품별 동기화 상태 표시: 미동기화 / 동기화완료 / 동기화실패
- 마지막 동기화 시각과 오류 메시지 저장
- 기존 DB에 필요한 컬럼 자동 추가
- Notion DB에 실제 존재하는 속성만 자동 매칭하여 전송

## 현재 동기화 방향

ERP → Notion 단방향입니다.
Notion에서 ERP로 가져오는 기능은 이번 단계에 포함하지 않았습니다.

## 사용 순서

1. Notion 연동 메뉴에서 토큰 저장 및 데이터베이스 검색
2. Notion Integration에 `상품 DB` 공유
3. 상품관리에서 상품 선택
4. `선택 상품 Notion` 또는 `전체 상품 Notion` 실행

## 안전 사항

- 상품·주문·발주·송장 업무 흐름은 변경하지 않았습니다.
- Notion에 없는 속성은 오류 없이 건너뜁니다.
- relation, formula, rollup 속성은 수정하지 않습니다.
