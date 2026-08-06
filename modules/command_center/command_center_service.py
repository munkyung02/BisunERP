from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Callable

from modules.command_center.activity_log_repository import ActivityLogRepository
from modules.dashboard.dashboard_service import DashboardService
from modules.orders.order_repository import OrderRepository


class CommandCenterService:
    """기존 업무 서비스를 Command Center 표시·실행 형태로 연결합니다."""

    def __init__(self) -> None:
        self.dashboard_service = DashboardService()
        self.order_repository = OrderRepository()
        self.activity_repository = ActivityLogRepository()
        self.database_path = self.activity_repository.database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def get_data(self) -> dict[str, Any]:
        dashboard = self.dashboard_service.get_dashboard_data()
        summary = dashboard.get("summary", {})
        today = date.today().isoformat()

        with self._connect() as connection:
            purchase_amount = self._scalar(
                connection,
                """
                SELECT COALESCE(SUM(
                    COALESCE(p.purchase_price, 0) * COALESCE(po.quantity, 0)
                ), 0)
                FROM purchase_orders AS po
                LEFT JOIN order_items AS oi ON oi.id = po.order_item_id
                LEFT JOIN products AS p ON p.id = oi.product_id
                WHERE substr(COALESCE(po.purchased_at, po.created_at), 1, 10) = ?
                """,
                (today,),
            )
            exceptions = self._get_exceptions(connection)
            failed_jobs = self.activity_repository.get_failed_count()
            failed_jobs += self._optional_scalar(
                connection,
                """
                SELECT COUNT(*) FROM coupang_shipment_api_logs
                WHERE api_status = '전송실패'
                """,
            )

        cards = {
            "today_orders": int(summary.get("today_orders", 0) or 0),
            "unmapped": int(summary.get("unmapped", 0) or 0),
            "purchase_pending": int(summary.get("purchase_waiting", 0) or 0),
            "shipment_pending": int(summary.get("shipment_waiting", 0) or 0),
            "shipping": int(summary.get("shipping", 0) or 0),
            "failed_jobs": failed_jobs,
            "today_purchase_amount": purchase_amount,
            "today_sales_amount": int(summary.get("today_sales", 0) or 0),
        }
        return {
            "cards": cards,
            "exceptions": exceptions,
            "activity": self.activity_repository.get_recent(),
            "errors": list(dashboard.get("errors") or []),
        }

    def run_navigation_action(
        self,
        action: str,
        callback: Callable[[], None],
    ) -> dict[str, Any]:
        try:
            callback()
            message = f"{action} 화면을 열었습니다."
            self.activity_repository.append(
                action=action,
                result_status="성공",
                result_message=message,
            )
            return {"success": True, "message": message}
        except Exception as error:
            message = str(error)
            self.activity_repository.append(
                action=action,
                result_status="실패",
                result_message=message,
            )
            return {"success": False, "message": message}

    def run_auto_mapping(self) -> dict[str, Any]:
        try:
            result = self.order_repository.auto_map_order_items()
            processed_count = int(result.get("target_count", 0) or 0)
            mapped_count = int(result.get("mapped_count", 0) or 0)
            message = (
                "자동매핑 처리가 완료되었습니다. "
                f"(대상 {processed_count:,}건 · 완료 {mapped_count:,}건)"
            )
            self.activity_repository.append(
                action="자동매핑",
                result_status="성공",
                result_message=message,
                details=result,
            )
            return {
                "success": True,
                "message": message,
            }
        except Exception as error:
            message = str(error)
            self.activity_repository.append(
                action="자동매핑",
                result_status="실패",
                result_message=message,
            )
            return {"success": False, "message": message}

    def _get_exceptions(
        self,
        connection: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        definitions = (
            (
                "Unmapped Products",
                "SELECT COUNT(*) FROM order_items WHERE mapping_status = '미매핑'",
                "상품 연결이 필요한 주문상품",
            ),
            (
                "Missing Supplier",
                """
                SELECT COUNT(*) FROM order_items
                WHERE mapping_status != '미매핑' AND supplier_id IS NULL
                """,
                "매핑 완료 후 공급처가 없는 주문상품",
            ),
            (
                "Shipment Errors",
                """
                SELECT COUNT(*) FROM coupang_shipment_api_logs
                WHERE api_status = '전송실패'
                """,
                "송장 처리 또는 전송 실패",
            ),
            (
                "Duplicate Tracking Numbers",
                """
                SELECT COUNT(*) FROM (
                    SELECT tracking_number FROM shipments
                    WHERE TRIM(COALESCE(tracking_number, '')) != ''
                    GROUP BY tracking_number HAVING COUNT(*) > 1
                )
                """,
                "둘 이상의 송장에 저장된 동일 번호",
            ),
            (
                "Import Errors",
                """
                SELECT COUNT(*) FROM erp_activity_logs
                WHERE result_status = '실패' AND action = '주문 동기화'
                """,
                "Command Center 주문 동기화 실패",
            ),
        )
        return [
            {
                "category": category,
                "count": self._optional_scalar(connection, query),
                "detail": detail,
            }
            for category, query, detail in definitions
        ]

    @staticmethod
    def _scalar(
        connection: sqlite3.Connection,
        query: str,
        parameters: tuple[Any, ...] = (),
    ) -> int:
        row = connection.execute(query, parameters).fetchone()
        return int(row[0] or 0)

    @classmethod
    def _optional_scalar(
        cls,
        connection: sqlite3.Connection,
        query: str,
    ) -> int:
        try:
            return cls._scalar(connection, query)
        except sqlite3.Error:
            return 0
