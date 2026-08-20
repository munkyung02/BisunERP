# BisunERP 개발 인수인계

## 1. 기준점

- 프로젝트: `C:\BisunERP_v2.8`
- 운영 브랜치: `feature/workflow`
- 이 문서 작성 직전 코드 기준점: `35d7480` (`fix: correct ESM purchase quantity semantics`)
- 이전 GO-LIVE 기준점: `7fa77da` (`feat: add Juyeong shipment parser and Mago purchase template`)
- BisunERP는 현재 GO-LIVE 실운영 단계다. 새 기능보다 기존 정상 운영 흐름과 데이터 보존을 우선한다.
- 운영 DB와 실제 고객 Excel은 Git 소스의 일부가 아니다. 운영 DB 기본 경로는 `data/bisun_erp.db`다.

## 2. 시스템 역할

- Notion은 공급처·상품·배송정책 등 Master의 Source of Truth다.
- ERP SQLite는 주문, 매핑, 발주, 송장, 채널 전송, 정산을 수행하는 실행 시스템이다.
- Notion 동기화는 Master를 ERP 실행 테이블에 반영한다. 주문·발주·송장 이력의 Source of Truth를 Notion으로 옮기지 않는다.
- 실제 발주, 송장 등록, 채널 Export/API는 외부 상태를 바꾸므로 사용자 승인 없이 실행하지 않는다.

## 3. GO-LIVE 운영 흐름

1. 판매채널 주문 Excel을 가져온다.
2. 채널을 자동 판별하고 신규/중복/오류를 미리 본다.
3. 신규 주문과 채널 원본 metadata를 저장한다.
4. 자동 상품매핑을 수행하고 미매핑은 Wizard에서 확정한다.
5. 취소 상태, 공급처, 원가, 발주마감, 배송정책을 기준으로 발주 후보를 계산한다.
6. 마감시간 또는 선택 공급처 단위로 발주서를 생성한다.
7. 공급처에 발주서를 전달하고 송장 회신을 받는다.
8. 전용 Parser, 기본 송장양식 또는 직접입력으로 송장을 등록한다.
9. 채널별 Excel Export 또는 쿠팡 API로 송장을 전달한다.
10. 채널에서 배송완료를 처리하고 ERP 배송현황/정산을 확인한다.

`modules/workflow/order_workflow_service.py`의 `OrderWorkflowService`가 매핑→발주와 송장 preview/register를 연결한다. 주의: `preview()`는 이름과 달리 자동매핑을 DB에 반영한다. 발주서 생성은 `execute(create_purchase_files=True)`에서만 수행한다.

## 4. 프로젝트 구조

- 진입점: `main.py` → 단일 인스턴스 mutex → `core.database.initialize_database()` → `app.main_window.MainWindow`
- DB 기본 스키마/점진 migration: `core/database.py`, `Database.initialize()`
- Dashboard: `modules/dashboard/dashboard_service.py`
- 주문 Import: `modules/orders/order_excel_parser.py`, `order_import_service.py`, `order_import_center.py`
- OMS adapter registry: `modules/oms_adapters/defaults.py`
- 주문관리/취소: `modules/orders/order_repository.py`, `order_page.py`
- 상품 Master: `modules/products/product_repository.py`, `product_master_repository.py`, `product_master_wizard.py`
- 상품매핑: `modules/mappings/`, `modules/mapping_engine/`, `OrderRepository.auto_map_order_items()`
- 공급처: `modules/suppliers/supplier_repository.py`
- Notion Live Sync: `modules/notion_sync/notion_live_service.py`
- 배송정책: `modules/products/product_shipping_policy_repository.py`
- 발주: `modules/purchases/purchase_service.py`, `purchase_repository.py`, `purchase_quantity_policy.py`
- 발주 Template: `modules/templates/registry.py`
- 송장: `modules/shipments/shipment_service.py`, `shipment_repository.py`, `parsers/registry.py`
- 채널 송장 Export: `modules/shipments/channel_shipment_export_service.py`, `channel_shipment_export_repository.py`
- 쿠팡 송장 API: `modules/coupang/coupang_shipment_service.py`
- 정산: `modules/settlements/settlement_service.py`
- Command Center: `modules/command_center/command_center_service.py`
- 운영 통계/지능: `modules/operations_intelligence/`

## 5. DB 핵심 구조

- `orders`: 채널 주문 단위. 구매/배송의 요약 상태를 가진다.
- `order_items`: 상품 단위 실행 기준. `cancellation_status`의 Source of Truth다.
- `channel_order_item_metadata`: 채널 원본 필드와 `raw_source_json`을 보존한다.
- `products`: ERP 상품 Master 및 기본 원가/공급처 연결.
- `suppliers`: 공급처 Master.
- `product_suppliers`: 상품-공급처별 원가/발주조건.
- `supplier_product_conditions`: 기본 공급처 조건과 Notion 동기화 정보.
- `product_shipping_policies`: 수량 구간 배송비 정책.
- `purchase_orders`: 실제 발주 snapshot. 과거 원가와 발주파일 경로를 보존한다.
- `shipments`: `order_item_id`에 연결된 송장/배송 상태.
- `channel_shipment_export_history`: 채널 송장 Export 중복 방지 이력.
- `coupang_shipment_api_logs`: 쿠팡 API 전송 상태/재시도 이력.
- `settlements`: 수동 확정 정산값. Dashboard는 주문 metadata와 발주 snapshot도 사용한다.

`core/database.py`의 migration은 기존 데이터를 보존하고 반복 실행 가능한 형태를 유지해야 한다. 일부 부가 테이블은 해당 모듈 서비스/Repository 초기화 시 생성되므로, 단순 조회 목적으로 운영 서비스 생성자를 호출할 때도 쓰기 가능성을 확인한다. 운영 조사에는 SQLite URI `mode=ro`를 우선한다.

2026-08-20 마감 READ ONLY 확인값:

- orders 35, order_items 35, purchase_orders 35, shipments 35
- products 31, suppliers 7
- 모든 order는 `발주완료/배송중`, 모든 PO는 `송장등록완료`, 모든 shipment는 `배송중`
- `foreign_key_check` 0건, `integrity_check` `ok`

## 6. Notion Master / Source of Truth

- Notion `📦 상품 DB`의 공식 원가 속성은 `원가`다.
- legacy 속성 `상품원가`는 2026-08-20 백업 후 삭제됐다.
- Live Sync 상품 파싱은 `NotionLiveSyncService._product_from_page()`에서 `_value(p, "원가", "매입단가")`를 사용한다. 즉 공식 우선순위는 `원가`, 호환 fallback은 `매입단가`다.
- ERP는 `상품원가`를 읽지 않는다.
- 원가는 다음 세 위치에 동기화된다.
  - `products.purchase_price`
  - `supplier_product_conditions.purchase_price`
  - `product_suppliers.purchase_price`
- 2026-08-20 동기화 후 Notion 상품 31개와 위 ERP 원가 저장 지점이 모두 일치함을 확인했다.
- Notion 주문DB의 `판매가`와 `원가` rollup은 상품DB의 `원가`를 가리킨다.

Notion sync/API를 조사할 때 token을 출력하거나 문서/로그에 기록하지 않는다.

## 7. 주문 Import

`modules/oms_adapters/defaults.py`의 production registry에 다음 Excel parser가 등록돼 있다.

- 쿠팡: `CoupangOrderExcelParser`
- 스마트스토어: `SmartStoreOrderExcelParser`
- Gmarket/Auction: `ESMOrderExcelParser`
- LotteOn: `LotteOnOrderExcelParser`
- Toss: `TossOrderExcelParser`
- Kakao: `KakaoOrderExcelParser`

`OrderImportService`는 parse → 신규/중복 preview → `OrderRepository.create_orders_bulk(skip_duplicates=True)` → 자동매핑 순서로 처리한다. 채널 원본은 metadata에 보존한다. 실제 고객 Excel을 fixture나 Git 파일로 재사용하지 않는다.

## 8. 상품매핑

- 자동매핑 진입점은 `OrderRepository.auto_map_order_items()`다.
- rule/exact/smart 결과와 미매핑/중복후보를 구분한다.
- 미매핑 Wizard에서 기존 상품 선택 또는 상품 생성 후 매핑할 수 있다.
- 발주 후보는 정상 cancellation 상태와 확정된 `product_id`/공급처를 요구한다.
- 채널 원본 상품/옵션과 ERP 상품명을 혼동하지 않는다. 원본은 metadata로 보존한다.

## 9. 발주 시스템

- 후보 조회/검증/발주서 생성: `PurchaseService`
- 직접 발주 및 DB persistence: `PurchaseRepository`
- 발주 snapshot에는 상품명, 옵션, 수량, 단가, 금액, 배송비, 공급처, 파일 경로를 저장한다.
- 발주 후보와 Repository 직접 생성 경로 모두 `purchase_quantity_policy.calculate_purchase_quantity()`를 사용한다.
- 취소된 item을 재발주하지 않는다.
- 과거 PO의 `unit_price`는 발주 당시 snapshot이므로 현재 Master 원가로 재계산하지 않는다.
- 발주서 생성은 실제 외부 업무이므로 복사 DB/임시 output 검증 후 명시 승인하에 실행한다.

## 10. 발주수량 정책

`modules/purchases/purchase_quantity_policy.py`가 공통 정책을 관리한다.

- Gmarket/Auction: `channel_total`
  - `purchase_quantity = order_items.quantity`
  - 옵션 끝 `/2개`, `/3개` 등을 다시 곱하지 않는다.
- 그 외 채널: `option_multiplier`
  - 주문수량 × 옵션의 `개/팩/봉/박스/세트` multiplier
  - 무게/용량 숫자는 수량으로 보지 않는다.

배경 사례: Gmarket 주문 `4480874991`은 원본 수량 2, 옵션 끝 `/2개`였다. 기존 계산은 2×2=4였고 수정 후 2다. 2026-08-20 운영 데이터 기준 ESM 15건에서 legacy 대비 14건은 동일하고 이 1건만 4→2였다. Auction 운영 데이터는 없었고 단위 테스트로 동일 정책을 검증했다. Coupang `4개 200g`과 Toss `2개` multiplier는 유지된다.

## 11. 공급처 Template

실제 registry는 `modules/templates/registry.py`와 `supplier_template_map.json`이다.

| 공급처 | template key | 구현 |
|---|---|---|
| 해담 | `haedam` | `HaedamPurchaseTemplate` |
| 푸드대통령 | `foodpresident` | `FoodPresidentPurchaseTemplate` |
| 주영씨푸드 | `juyeong` | `JuyeongSeafoodPurchaseTemplate` |
| 망고B2B | `mangob2b` | `MangoB2BPuchaseTemplate` |
| 와현농원 | `wahyun` | `WahyunFarmPurchaseTemplate` |
| (주)마스터 | `masteryutong` | `MasterYutongPurchaseTemplate` |
| 주식회사 마고 | `mago` | `MagoPurchaseTemplate` |

공통 `default`, `summary_only`도 등록돼 있다. 매핑되지 않은 공급처는 `DefaultPurchaseTemplate`을 쓴다. 마고 runtime asset은 `modules/templates/assets/mago_delivery_template.xlsx`이며 배포 패키지에 반드시 포함한다.

## 12. 송장 시스템

- 자동판별 registry: `modules/shipments/parsers/registry.py`
- 등록 Parser:
  - 푸드대통령 → `FoodPresidentShipmentParser`
  - 주영씨푸드 → `JuyeongShipmentParser`
  - 해담 → `HaedamShipmentParser`
  - 외현농원 → `OehyeonShipmentParser`
  - 공급처 무관 주문번호/택배사/송장번호 기본양식 → `StandardShipmentParser`
- registry에 없는 공급처는 기본양식 또는 직접입력을 사용한다.
- `ShipmentService.save_matched_shipments()`가 중복 송장을 차단하고 `ShipmentRepository.create_shipment()`을 호출한다.
- 정상 저장 결과는 shipment `배송중`, PO `송장등록완료`, order `배송중`이다.
- 현재 `order_item`당 실질적으로 shipment 한 건 정책이며 duplicate item을 차단한다.
- 망고B2B Shipment Parser는 미구현/중단 상태다.
- Template의 `와현농원`과 Parser의 `외현농원` 명칭 차이가 있으므로 새 작업에서 실제 공급처명/파일을 확인해야 한다.

Dashboard의 송장대기는 상태 문자열이 아니라 “취소되지 않은 PO 중 연결 shipment가 없는 item” 수다. 상태만 바꾸지 말고 shipment 존재 여부를 확인한다.

## 13. 채널 Export/API

| 채널 | Import | Dashboard 매출/정산 | Shipment 전달 | 특이 정책 |
|---|---|---|---|---|
| Coupang | Excel | 결제액의 88% | API (`CoupangShipmentService`) 및 export facade | API 로그/재시도 관리 |
| SmartStore | Excel | 정산예정금액+배송비 | 발송처리 Excel | 원본 metadata 필수 |
| Gmarket | ESM Excel | 정산예정금액+배송비 | ESM Excel | 발주수량 `channel_total` |
| Auction | ESM Excel | 정산예정금액+배송비 | ESM Excel | 발주수량 `channel_total` |
| Toss | Excel | 쿠폰/예상 수수료 반영 | 주문내역 Excel | 원본 header 보존 |
| Kakao | Excel | 수수료/배송비 기반 | 전용 Export 없음 | Import/정산만 확인됨 |
| LotteOn | Excel | 현재 일반 `total_price` fallback | 배송관리 Excel | 원본 header 보존 |

Export 후보는 `orders.shipment_status='배송중'`, 실제 tracking 존재, metadata 존재, 동일 플랫폼 export history 부재를 요구한다. Export 성공 시 `channel_shipment_export_history`를 기록한다. 이미 발송된 건을 history 없이 복구하면 신규 후보로 보일 수 있으므로 재전송 전에 반드시 운영 사실을 확인한다.

## 14. 취소 정책

Source of Truth는 `order_items.cancellation_status`다.

- `정상`: 정상 발주/송장/정산 흐름.
- `미발주취소`: 발주 후보에서 제외. 매출·매입·순익·판매수량·상품 주문수 통계에서 제외.
- `발주후취소요청`: 기존 발주/손익을 유지하며 취소 진행 상태로 표시.
- `발주후취소완료`: 매출·매입·순익·판매수량·상품 주문수 통계에서 완전 제외.

발주후 취소에서도 `purchase_orders` 원본은 감사 이력으로 보존한다. 관련 전이는 `OrderRepository`의 cancellation 메서드에서 기대 기존 상태를 조건으로 수행한다.

## 15. Settlement / Dashboard

- `SettlementService`는 주문 metadata의 채널별 원본 금액과 PO의 `item_amount`/`shipping_fee`를 결합한다.
- 취소 통계 제외 기준은 `미발주취소`, `발주후취소완료`다.
- Dashboard는 주문/발주/송장/정산과 `SalesIntelligenceService` read model을 조합한다.
- Operations Intelligence는 오늘/7/30/90일 매출, 상품/공급처 비교, 추세를 read-only Repository로 제공한다.
- Command Center는 Dashboard와 예외/활동 로그를 표시하며, `run_daily_operation()`은 Notion sync, 매핑, 발주/송장 관련 실제 작업을 포함할 수 있다. 조사 목적으로 실행하지 않는다.

## 16. 2026-08-20 운영 보정 이력

### ESM PO 수량 보정

- 대상: `purchase_order_id=41`, 주문 `4480874991`
- quantity 4→2
- unit_price 8,700 유지
- item_amount 34,800→17,400
- shipping_fee 4,000 유지
- 실제 발주서와 공급처 회신 수량 2를 근거로 백업 후 승인된 조건부 UPDATE를 수행했다.

### 확정 송장으로 복구

- `4478456031`: CJ대한통운 / `699617222296`
- `4480874991`: CJ대한통운 / `699740514313`
- `4481162039`: CJ대한통운 / `699740514324`

원본 파일의 수취인·전화·상품·수량을 교차검증하고 shipment를 복구했다. 마지막 주문은 ERP 부모 order_item 한 건에만 shipment를 연결했고 추가구성 행을 생성하지 않았다.

### 실제 발송 확인, 송장정보 유실

- `4478853267`
- `262037839`
- `4480881713`

사용자가 실제 발송을 확인했으나 송장정보가 유실됐다. schema의 NULL 허용을 확인한 뒤 다음 형태로 운영 정리했다.

- `courier_name = NULL`
- `tracking_number = NULL`
- `shipment_status = 배송중`
- memo: `실제 발송 완료 / 송장정보 유실 / 2026-08-20 수동 운영정리`

가짜 송장번호는 만들지 않았다. tracking이 없어 채널 Export 후보에서도 제외된다. 2026-08-20 마감 결과는 송장대기 0, 배송중 35다.

## 17. 현재 미해결 이슈

### A. ESM 추가구성

Gmarket 주문 `4481162039`의 본상품은 전어 회필렛250g ×1이고 원본 metadata에는 전어 구이용 500g ×1 추가구성이 있다. 현재 추가구성은 raw metadata에만 존재하며 별도 order_item, 상품 Master, purchase_order가 없다. 공급처는 전어필렛250g ×1과 전어구이500g ×1을 동일 송장 `699740514324`로 출고했다.

현재 결정은 미처리다. 장기 권장 설계는 `order_item` 하위 fulfillment component 모델이다.

### B. 망고B2B Shipment Parser

추가구성 데이터 모델이 결정될 때까지 구현 중단 상태다. 현재 회신 파일을 공통정책 변경으로 억지 매칭하지 않는다.

### C. 부분출고

현재는 item당 shipment 한 건 정책이다. component별 서로 다른 송장과 부분출고를 지원하지 않는다.

### D. 발주서 사후 수동수정 감지

`purchase_file` 경로는 저장하지만 파일 hash 또는 row snapshot hash 기반 변경 감지는 없다. DB snapshot과 실제 전달 파일이 달라질 수 있다.

### E. 소스 이력의 runtime 파일

과거 Git 이력에 운영 DB 백업과 고객 Excel 일부가 tracked 상태로 남아 있다. 신규 커밋/배포 ZIP에는 포함하지 말아야 하며, 이력 정리는 별도 승인과 보안 계획 없이 수행하지 않는다.

## 18. 개발 시 절대 보존할 원칙

- 기존 정상 운영 흐름 우선, 최소 수정.
- 운영 DB 직접 변경 최소화. 변경 전 정확한 대상 확인과 바이트 동일 백업.
- migration은 idempotent하고 기존 데이터를 보존.
- 발주/송장 중복 방지, 취소 주문 재발주 금지.
- 운영 DB, backup, 실제 고객 Excel, tmp/output/log를 Git에 포함하지 않음.
- Notion은 Master, ERP는 실행 시스템.
- 채널별 정상 로직을 무검증 공통화로 깨뜨리지 않음.
- 실전/복사 DB 검증 전 commit/push 금지.
- 사용자 승인 없는 실제 발주, shipment 등록, Export/API, Notion sync 금지.
- dirty working tree에서 reset/revert/stash/clean으로 사용자 변경을 덮지 않음.

## 19. 새 기능 개발 절차

1. `docs/ERP_HANDOFF.md`를 읽는다.
2. `git status`, branch, HEAD, stash를 확인한다.
3. 관련 코드와 registry를 READ ONLY로 조사한다.
4. 운영 DB가 필요하면 SQLite `mode=ro`로 조사한다.
5. 영향 범위와 데이터 변경 여부를 보고한다.
6. 최소 범위로 구현한다.
7. 복사 DB/fixture/tmp output에서 테스트한다.
8. 관련 채널과 공통 경로 회귀 테스트를 수행한다.
9. `py_compile`, 직접 테스트, `git diff --check`를 통과한다.
10. stage 파일을 명시하고 DB/Excel/secret 부재를 확인한다.
11. 사용자 승인 후 checkpoint commit한다.
12. non-force push하고 local/remote HEAD를 검증한다.

## 20. 다음 세션 시작 방법

새 세션에는 다음 정보를 제공한다.

- 프로젝트 경로 `C:\BisunERP_v2.8`
- branch `feature/workflow`
- 먼저 `docs/ERP_HANDOFF.md` 전체를 읽으라는 지시
- `git status --short`, `git log -5 --oneline` 확인
- 기존 untracked Excel/scripts/tmp를 삭제하거나 stage하지 말라는 지시
- 운영 DB는 명시 승인 전 READ ONLY라는 지시
- 새로 구현하려는 기능과 허용된 외부 작업 범위

새 세션은 HANDOFF 내용도 현재 코드/DB와 다시 대조해야 하며, 운영 상태가 변했으면 과거 마감 기록과 현재값을 구분해 보고한다.
