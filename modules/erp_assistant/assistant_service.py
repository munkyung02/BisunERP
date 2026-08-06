from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modules.command_center.activity_log_repository import ActivityLogRepository
from modules.erp_assistant.assistant_repository import ReadOnlyAssistantRepository
from modules.erp_assistant.intent_parser import AssistantIntent, KoreanIntentParser


@dataclass
class AssistantAnswer:
    message: str
    columns: list[tuple[str, str, int]] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    supported: bool = True


class ERPAssistantService:
    """Execute deterministic intents without exposing mutating operations."""

    ORDER_COLUMNS = [
        ("order_number", "주문번호", 150), ("platform", "판매처", 90),
        ("ordered_at", "주문일시", 135), ("item_summary", "상품", 300),
        ("total_quantity", "수량", 60), ("mapping_status", "매핑", 90),
        ("purchase_status", "발주", 90), ("shipment_status", "배송", 90),
    ]

    def __init__(self) -> None:
        self.parser = KoreanIntentParser()
        self.repository = ReadOnlyAssistantRepository()
        self.activity_repository = ActivityLogRepository()

    def ask(self, question: str) -> AssistantAnswer:
        parsed = self.parser.parse(question)
        try:
            answer = self._execute(parsed.intent, parsed.search_term)
            self._log(question, parsed.intent, answer)
            return answer
        except Exception as error:
            message = "질문을 조회하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
            self.activity_repository.append(
                action="ERP 도우미 질문", result_status="실패", result_message=message,
                details={"question": question, "intent": parsed.intent.value, "error": str(error)},
            )
            return AssistantAnswer(message=message)

    def _execute(self, intent: AssistantIntent, term: str) -> AssistantAnswer:
        if intent is AssistantIntent.TODAY_ORDER_COUNT:
            return AssistantAnswer(message=f"오늘 주문은 {self.repository.get_today_order_count():,}건입니다.")
        if intent is AssistantIntent.UNMAPPED_ORDERS:
            return self._order_answer("미매핑 주문", *self.repository.get_unmapped_orders())
        if intent is AssistantIntent.PURCHASE_PENDING:
            return self._order_answer("발주 대기 주문", *self.repository.get_purchase_pending_orders())
        if intent is AssistantIntent.SHIPMENT_PENDING:
            return self._order_answer("송장 대기 주문", *self.repository.get_shipment_pending_orders())
        if intent is AssistantIntent.SHIPPING_ORDERS:
            return self._order_answer("배송중 주문", *self.repository.get_shipping_orders())
        if intent is AssistantIntent.MISSING_TRACKING:
            return self._order_answer("송장번호 없는 주문", *self.repository.get_orders_missing_tracking())
        if intent is AssistantIntent.PRODUCT_ORDER_SEARCH:
            return self._order_answer(f"상품명 ‘{term}’ 검색 결과", *self.repository.search_orders_by_product(term))
        if intent is AssistantIntent.ORDER_NUMBER_SEARCH:
            return self._order_answer(f"주문번호 ‘{term}’ 검색 결과", *self.repository.search_orders_by_number(term))
        if intent is AssistantIntent.SUPPLIER_PURCHASE_AMOUNT:
            return self._table_answer(
                "공급처별 발주 금액", *self.repository.get_supplier_purchase_amounts(),
                [("supplier_name", "공급처", 180), ("purchase_count", "발주건수", 90),
                 ("total_quantity", "수량", 80), ("purchase_amount", "발주금액", 120)],
            )
        if intent is AssistantIntent.TODAY_PURCHASES:
            return self._table_answer(
                "오늘 발주 내역", *self.repository.get_today_purchases(),
                [("order_number", "주문번호", 150), ("supplier_name", "공급처", 130),
                 ("product_name", "상품", 220), ("option_name", "옵션", 150),
                 ("quantity", "수량", 60), ("purchase_amount", "금액", 100),
                 ("purchase_status", "상태", 90), ("purchased_at", "발주일시", 140)],
            )
        return AssistantAnswer(
            message=("아직 지원하지 않는 질문입니다. 화면의 추천 질문 중 하나를 선택하거나 "
                     "‘상품명 사과 주문 검색’ 또는 ‘주문번호 12345 검색’처럼 질문해 주세요."),
            supported=False,
        )

    def _order_answer(self, label: str, rows: list[dict[str, Any]], truncated: bool) -> AssistantAnswer:
        return self._table_answer(label, rows, truncated, self.ORDER_COLUMNS)

    @staticmethod
    def _table_answer(
        label: str, rows: list[dict[str, Any]], truncated: bool,
        columns: list[tuple[str, str, int]],
    ) -> AssistantAnswer:
        suffix = " 최대 100건만 표시합니다." if truncated else ""
        return AssistantAnswer(
            message=f"{label}은(는) {len(rows):,}건입니다.{suffix}",
            columns=columns, rows=rows, truncated=truncated,
        )

    def _log(self, question: str, intent: AssistantIntent, answer: AssistantAnswer) -> None:
        self.activity_repository.append(
            action="ERP 도우미 질문",
            result_status="성공" if answer.supported else "지원안함",
            result_message=answer.message,
            details={"question": question, "intent": intent.value,
                     "result_count": len(answer.rows), "truncated": answer.truncated},
        )
