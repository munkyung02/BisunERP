from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Callable

from modules.orders.order_repository import OrderRepository
from modules.purchases.purchase_repository import PurchaseRepository
from modules.shipments.shipment_repository import ShipmentRepository
from modules.settlements.settlement_service import SettlementService


class DashboardService:
    """기존 Repository 데이터를 대시보드 표시 형식으로 집계합니다."""

    def __init__(
        self,
        order_repository: OrderRepository | None = None,
        purchase_repository: PurchaseRepository | None = None,
        shipment_repository: ShipmentRepository | None = None,
    ) -> None:
        self.order_repository = order_repository or OrderRepository()
        self.purchase_repository = purchase_repository or PurchaseRepository()
        self.shipment_repository = shipment_repository or ShipmentRepository()
        self.settlement_service = SettlementService()

    def get_dashboard_data(self) -> dict[str, Any]:
        errors: list[str] = []
        order_counts = self._safe_call(
            self.order_repository.get_order_counts, {}, "주문 집계", errors
        )
        recent_orders = self._safe_call(
            lambda: self.order_repository.get_orders(limit=20), [], "최근 주문", errors
        )
        all_orders = self._safe_call(
            self.order_repository.get_orders, [], "전체 주문", errors
        )
        purchase_counts = self._safe_call(
            self.purchase_repository.get_purchase_status_counts,
            {},
            "발주 집계",
            errors,
        )
        supplier_summary = self._safe_call(
            self.purchase_repository.get_supplier_summary,
            [],
            "공급처 집계",
            errors,
        )
        shipments = self._safe_call(
            self.shipment_repository.get_shipments, [], "송장 집계", errors
        )

        today_text = date.today().isoformat()
        today_orders = [
            order for order in all_orders
            if self._date_text(order.get("ordered_at")) == today_text
        ]
        today_sales = sum(self._to_int(order.get("total_amount")) for order in today_orders)
        today_count = self._to_int(order_counts.get("today_count")) or len(today_orders)
        average_order = int(today_sales / today_count) if today_count else 0

        shipment_counts = self._count_shipments(shipments)
        unmapped = self._to_int(order_counts.get("unmapped_count"))
        purchase_waiting = self._to_int(
            purchase_counts.get(
                "발주대기", order_counts.get("purchase_waiting_count", 0)
            )
        )
        shipment_waiting = shipment_counts["배송대기"] + shipment_counts["배송준비"]
        shipping = shipment_counts["배송중"] or self._to_int(order_counts.get("shipping_count"))
        completed = shipment_counts["배송완료"]

        profit_summary = self._safe_call(
            self.settlement_service.get_dashboard_profit, {}, "정산 집계", errors
        )

        seven_days = self._build_seven_day_stats(all_orders)
        yesterday = seven_days[-2] if len(seven_days) >= 2 else {"order_count": 0, "sales": 0}
        order_change = today_count - self._to_int(yesterday.get("order_count"))
        sales_change = today_sales - self._to_int(yesterday.get("sales"))

        tasks = [
            self._task("unmapped", "상품 미매핑", unmapped, "상품 연결이 필요한 주문", 1),
            self._task("purchase_waiting", "발주 대기", purchase_waiting, "공급처 발주가 필요한 건", 2),
            self._task("shipment_waiting", "송장 대기", shipment_waiting, "송장 등록 또는 출고 확인", 3),
            self._task("shipping", "배송 조회", shipping, "배송상태 확인이 필요한 건", 4),
        ]
        alert_count = sum(1 for task in tasks if task["count"] > 0)
        urgent_count = sum(task["count"] for task in tasks[:3])

        return {
            "summary": {
                "today_orders": today_count,
                "today_sales": today_sales,
                "average_order": average_order,
                "total_orders": self._to_int(order_counts.get("total_count")) or len(all_orders),
                "unmapped": unmapped,
                "purchase_waiting": purchase_waiting,
                "shipment_waiting": shipment_waiting,
                "shipping": shipping,
                "completed": completed,
                "today_profit": self._to_int(profit_summary.get("today_profit")),
                "month_profit": self._to_int(profit_summary.get("month_profit")),
            },
            "comparisons": {
                "order_change": order_change,
                "sales_change": sales_change,
            },
            "tasks": tasks,
            "alert_count": alert_count,
            "urgent_count": urgent_count,
            "recent_orders": [self._normalize_order(order) for order in recent_orders],
            "supplier_summary": [
                {
                    "supplier_name": str(row.get("supplier_name") or "공급처 미지정"),
                    "purchase_count": self._to_int(row.get("purchase_count")),
                    "total_quantity": self._to_int(row.get("total_quantity")),
                }
                for row in supplier_summary
            ],
            "seven_day_stats": seven_days,
            "errors": errors,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @staticmethod
    def _safe_call(
        function: Callable[[], Any],
        default: Any,
        label: str,
        errors: list[str],
    ) -> Any:
        try:
            result = function()
            return default if result is None else result
        except Exception as error:
            errors.append(f"{label}: {error}")
            return default

    @staticmethod
    def _count_shipments(shipments: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"배송대기": 0, "배송준비": 0, "배송중": 0, "배송완료": 0, "배송취소": 0}
        for shipment in shipments:
            status = str(shipment.get("shipment_status") or "").strip()
            if status in counts:
                counts[status] += 1
        return counts

    def _build_seven_day_stats(self, orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
        totals: dict[str, dict[str, int]] = defaultdict(lambda: {"order_count": 0, "sales": 0})
        for order in orders:
            ordered_date = self._date_text(order.get("ordered_at"))
            if not ordered_date:
                continue
            totals[ordered_date]["order_count"] += 1
            totals[ordered_date]["sales"] += self._to_int(order.get("total_amount"))

        rows: list[dict[str, Any]] = []
        today = date.today()
        for offset in range(6, -1, -1):
            target = today - timedelta(days=offset)
            key = target.isoformat()
            rows.append({
                "date": key,
                "label": target.strftime("%m/%d"),
                "order_count": totals[key]["order_count"],
                "sales": totals[key]["sales"],
            })
        return rows

    @staticmethod
    def _task(key: str, title: str, count: int, description: str, priority: int) -> dict[str, Any]:
        return {
            "key": key,
            "title": title,
            "count": count,
            "description": description,
            "priority": priority,
            "active": count > 0,
        }

    @classmethod
    def _normalize_order(cls, order: dict[str, Any]) -> dict[str, Any]:
        shipment_status = str(order.get("shipment_status") or "").strip()
        purchase_status = str(order.get("purchase_status") or "").strip()
        mapping_status = str(order.get("mapping_status") or "").strip()
        order_status = str(order.get("order_status") or "").strip()
        if shipment_status and shipment_status != "배송대기":
            status = shipment_status
        elif purchase_status and purchase_status != "발주대기":
            status = purchase_status
        elif mapping_status and mapping_status != "매핑완료":
            status = mapping_status
        else:
            status = order_status or "주문접수"
        return {
            "ordered_at": str(order.get("ordered_at") or "-")[:16],
            "platform": str(order.get("platform") or "-"),
            "order_number": str(order.get("order_number") or "-"),
            "receiver_name": str(order.get("receiver_name") or "-"),
            "item_summary": str(order.get("item_summary") or "-"),
            "total_amount": cls._to_int(order.get("total_amount")),
            "status": status,
        }

    @staticmethod
    def _date_text(value: Any) -> str:
        text = str(value or "").strip()
        return text[:10] if len(text) >= 10 else ""

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return 0
