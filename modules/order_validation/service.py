from __future__ import annotations

from typing import Any, Iterable

from modules.orders.order_repository import OrderRepository

from .models import ValidationResult
from .rules import validate_order


class OrderValidationService:
    """DB를 변경하지 않고 발주 전 주문 검수 결과를 계산합니다."""

    def __init__(self, repository: OrderRepository | None = None) -> None:
        self.repository = repository or OrderRepository()

    def validate_order(self, order_id: int) -> ValidationResult:
        order = self.repository.get_order_by_id(int(order_id))
        if order is None:
            raise ValueError("주문을 찾을 수 없습니다.")

        issues = validate_order(order)
        failed_count = sum(issue.level == "FAIL" for issue in issues)
        warning_count = sum(issue.level == "WARNING" for issue in issues)
        item_count = len(order.get("items") or [])

        if failed_count:
            level = "FAIL"
            summary = "상품매핑 또는 공급처 연결을 먼저 완료해야 합니다."
        elif warning_count:
            level = "WARNING"
            summary = "발주 전 확인이 필요한 항목이 있습니다."
        else:
            level = "PASS"
            summary = "검수 완료. 발주할 수 있습니다."

        affected_ids = {issue.order_item_id for issue in issues if issue.order_item_id is not None}
        return ValidationResult(
            order_id=int(order.get("id") or order_id),
            order_number=str(order.get("order_number") or ""),
            level=level,
            summary=summary,
            issues=issues,
            item_count=item_count,
            passed_count=max(0, item_count - len(affected_ids)),
            warning_count=int(warning_count),
            failed_count=int(failed_count),
        )

    def validate_orders(self, order_ids: Iterable[int]) -> list[ValidationResult]:
        return [self.validate_order(order_id) for order_id in order_ids]

    def validate_pending_orders(self, limit: int = 1000) -> list[ValidationResult]:
        orders = self.repository.get_orders(limit=limit)
        results: list[ValidationResult] = []
        for order in orders:
            order_id = order.get("id") or order.get("order_id")
            if not order_id:
                continue
            purchase_status = str(order.get("purchase_status") or "").strip()
            if purchase_status not in {"", "발주대기", "발주준비"}:
                continue
            results.append(self.validate_order(int(order_id)))
        return results

    def get_summary(self, limit: int = 1000) -> dict[str, Any]:
        results = self.validate_pending_orders(limit=limit)
        return {
            "total_count": len(results),
            "pass_count": sum(row.level == "PASS" for row in results),
            "warning_count": sum(row.level == "WARNING" for row in results),
            "fail_count": sum(row.level == "FAIL" for row in results),
            "results": results,
        }
