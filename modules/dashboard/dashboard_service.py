from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Callable

from modules.operations_intelligence.service import SalesIntelligenceService
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
        sales_intelligence_service: SalesIntelligenceService | None = None,
    ) -> None:
        self.order_repository = order_repository or OrderRepository()
        self.purchase_repository = purchase_repository or PurchaseRepository()
        self.shipment_repository = shipment_repository or ShipmentRepository()
        self.sales_intelligence_service = (
            sales_intelligence_service or SalesIntelligenceService()
        )
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
        supplier_summary = self._safe_call(
            self.purchase_repository.get_supplier_summary,
            [],
            "공급처 집계",
            errors,
        )
        shipments = self._safe_call(
            self.shipment_repository.get_shipments, [], "송장 집계", errors
        )

        shipment_waiting_count = self._safe_call(
            self.shipment_repository.get_shipment_waiting_count,
            0,
            "송장 대기 집계",
            errors,
        )   

        today_text = date.today().isoformat()
        today_orders = [
            order for order in all_orders
            if self._date_text(order.get("ordered_at")) == today_text
        ]
        today_sales = sum(self._to_int(order.get("total_amount")) for order in today_orders)
        today_count = self._to_int(order_counts.get("today_count")) or len(today_orders)
        shipment_counts = self._count_shipments(
            shipments
        )

        unmapped = self._to_int(
            order_counts.get("unmapped_count")
        )

        purchase_waiting = self._to_int(
            order_counts.get("purchase_waiting_count", 0)
        )

        shipment_waiting = self._to_int(
            shipment_waiting_count
        )

        shipping = (
            shipment_counts["배송중"]
            or self._to_int(
                order_counts.get("shipping_count")
            )
        )

        completed = shipment_counts["배송완료"]
        profit_summary = self._safe_call(
            self.settlement_service.get_dashboard_profit, {}, "정산 집계", errors
        )
        today_sales = self._to_int(profit_summary.get("today_sales", today_sales))
        intelligence, sales_intelligence = self._get_operations_intelligence(errors)

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
        next_work = self._next_work(tasks)

        return {
            "summary": {
                "today_orders": today_count,
                "today_sales": today_sales,
                "today_purchase": self._to_int(
                    profit_summary.get("today_purchase")
                ),
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
            "next_work": next_work,
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
            "sales_intelligence": sales_intelligence,
            "operations_intelligence": intelligence,
            "errors": errors,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _get_operations_intelligence(
        self,
        errors: list[str],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        unavailable = {"status": "Unavailable", "detail": "조회할 수 없습니다."}
        sales_read_model = self._safe_call(
            self.sales_intelligence_service.get_dashboard_read_model,
            None,
            "Sales Overview",
            errors,
        )
        product_metrics = self._safe_call(
            self.sales_intelligence_service.get_product_metrics,
            None,
            "Top Selling Products",
            errors,
        )
        purchase_metrics = self._safe_call(
            self.sales_intelligence_service.get_purchase_metrics,
            None,
            "Purchase Intelligence",
            errors,
        )
        supplier_comparisons = self._safe_call(
            self.sales_intelligence_service.get_supplier_comparison,
            None,
            "Supplier Health",
            errors,
        )
        trend_read_model = self._safe_call(
            self.sales_intelligence_service.get_trend_read_model,
            None,
            "Product Trend",
            errors,
        )

        sales_overview: dict[str, Any] = dict(unavailable)
        if sales_read_model is not None:
            by_period = sales_read_model.get("windows", {})
            today = by_period.get("today", {})
            day7 = by_period.get("7d", {})
            day30 = by_period.get("30d", {})
            sales_overview = {
                "status": "Available",
                "today_revenue": today.get("revenue"),
                "today_quantity": today.get("quantity_sold"),
                "revenue_7d": day7.get("revenue"),
                "revenue_30d": day30.get("revenue"),
                "aov_30d": day30.get("average_order_value"),
                "mapped_quantity": day30.get("mapped_quantity"),
                "unmapped_quantity": day30.get("unmapped_quantity"),
            }

        top_products: dict[str, Any] = dict(unavailable)
        if product_metrics is not None:
            ranked = sorted(
                product_metrics,
                key=lambda item: (-item.quantity_30d, -item.revenue_30d, item.product_id),
            )[:10]
            top_products = {
                "status": "Available",
                "rows": [
                    {
                        "product_name": item.product_name,
                        "quantity_30d": item.quantity_30d,
                        "revenue_30d": item.revenue_30d,
                        "order_count": item.order_count,
                        "latest_order_date": item.latest_order_date,
                    }
                    for item in ranked
                    if item.quantity_30d > 0
                ],
                "unmapped_quantity": sales_overview.get("unmapped_quantity"),
            }

        trend_section: dict[str, Any] = dict(unavailable)
        if trend_read_model is not None:
            trends, summary = trend_read_model
            significant = sorted(
                (
                    item for item in trends
                    if item.trend_status in {"Increasing", "Decreasing", "New"}
                ),
                key=lambda item: (-item.quantity_30d, item.product_id),
            )[:10]
            trend_section = {
                "status": "Available",
                "summary": {
                    "Increasing": summary.increasing_products,
                    "Decreasing": summary.decreasing_products,
                    "Stable": summary.stable_products,
                    "New": summary.new_products,
                    "Inactive": summary.inactive_products,
                    "Insufficient History": summary.insufficient_history_products,
                },
                "rows": [
                    {
                        "product_name": item.product_name,
                        "trend_status": item.trend_status,
                        "quantity_30d": item.quantity_30d,
                        "latest_order_date": item.latest_order_date,
                        "data_status": item.data_status,
                    }
                    for item in significant
                ],
            }

        channel_section: dict[str, Any] = dict(unavailable)
        if sales_read_model is not None:
            channel_section = {
                "status": "Available",
                "rows": [
                    {
                        "platform": item.get("platform", ""),
                        "order_count": item.get("order_count"),
                        "quantity": item.get("quantity"),
                        "revenue": item.get("revenue"),
                        "revenue_ratio": item.get("revenue_ratio"),
                    }
                    for item in sales_read_model.get("channel_mix_30d", [])
                ],
            }

        purchase_section: dict[str, Any] = dict(unavailable)
        if purchase_metrics is not None:
            with_history = [item for item in purchase_metrics if item.purchase_count > 0]
            covered = sum(item.price_coverage_count for item in with_history)
            total_rows = sum(item.total_purchase_rows for item in with_history)
            purchase_section = {
                "status": "Available" if covered == total_rows else "Partial",
                "products_with_history": len(with_history),
                "price_coverage_count": covered,
                "total_purchase_rows": total_rows,
                "missing_price_products": sum(
                    1 for item in with_history
                    if item.price_coverage_count < item.total_purchase_rows
                ),
                "default_mismatch_count": sum(
                    1 for item in with_history
                    if item.configured_default_supplier_id is not None
                    and item.most_used_supplier_id is not None
                    and item.configured_default_supplier_id != item.most_used_supplier_id
                ),
            }

        supplier_section: dict[str, Any] = dict(unavailable)
        if supplier_comparisons is not None:
            supplier_rows = [
                row for result in supplier_comparisons for row in result.suppliers
            ]
            supplier_section = {
                "status": "Available",
                "price_conflict": sum(
                    row.condition_status == "Price Conflict" for row in supplier_rows
                ),
                "missing_product_suppliers": sum(
                    row.condition_status == "Missing in Product Suppliers"
                    for row in supplier_rows
                ),
                "missing_notion_conditions": sum(
                    row.condition_status == "Missing in Notion Conditions"
                    for row in supplier_rows
                ),
                "ambiguous_usage": sum(
                    "Ambiguous" in result.data_status
                    for result in supplier_comparisons
                ),
            }

        intelligence = {
            "sales_overview": sales_overview,
            "top_products": top_products,
            "trends": trend_section,
            "channel_mix": channel_section,
            "purchase": purchase_section,
            "supplier_health": supplier_section,
        }
        return intelligence, (
            sales_read_model
            if sales_read_model is not None
            else {"windows": {}, "channel_mix_30d": []}
        )


    @staticmethod
    def _next_work(tasks: list[dict[str, Any]]) -> dict[str, Any]:
        """남은 업무 중 가장 먼저 처리해야 할 단계를 반환합니다."""
        active_tasks = [
            task for task in sorted(tasks, key=lambda row: int(row.get("priority", 999)))
            if int(task.get("count", 0) or 0) > 0
        ]

        if not active_tasks:
            return {
                "key": "complete",
                "title": "오늘 필수 업무 완료",
                "message": "미매핑·발주대기·송장대기 업무가 없습니다.",
                "count": 0,
            }

        task = active_tasks[0]
        messages = {
            "unmapped": "상품 매핑을 먼저 완료해야 발주로 넘어갈 수 있습니다.",
            "purchase_waiting": "매핑이 끝난 주문의 공급처 발주를 진행하세요.",
            "shipment_waiting": "발주완료 주문의 공급처 송장을 등록하세요.",
            "shipping": "등록된 송장의 배송상태를 확인하세요.",
        }
        key = str(task.get("key") or "")
        return {
            "key": key,
            "title": str(task.get("title") or "다음 업무"),
            "message": messages.get(key, str(task.get("description") or "업무를 확인하세요.")),
            "count": int(task.get("count", 0) or 0),
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
