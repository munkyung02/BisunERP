# BisunERP v3.0 Full Build

## 복구 및 안정화

- `modules.purchases.templates` 잘못된 import를 `modules.templates`로 수정
- `modules.notion.*` 구형 import를 `modules.notion_sync.*`로 수정
- `MappingPage` 및 상품매핑 호환 구조 포함
- 쿠팡 주문 자동수집 모듈 포함
- 쿠팡 송장 API 전송 및 실패 재전송 구조 포함
- `main.py`에서 Notion 자동동기화가 두 번 생성되던 문제 제거
- 암호화된 주문 엑셀 처리를 위해 `msoffcrypto-tool`을 requirements에 추가

## 검증 결과

- 전체 Python 파일 문법검사 통과
- `app.main_window` 전체 import 통과
- BisunERP 사전점검: PASS 296 / WARN 2 / FAIL 0
- 가상 디스플레이에서 `python main.py` 실행 후 8초 이상 오류 없이 유지

## 주의

- WARN 2건은 최초 저장 전 환경설정 JSON과 백업설정 JSON이 없는 상태로 정상입니다.
- 쿠팡 운영 API는 실제 판매자 키와 실제 주문으로 1건씩 검증한 뒤 대량 사용하세요.
