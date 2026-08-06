from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from time import perf_counter
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

    def run_daily_operation(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Run the production daily workflow while isolating each failure."""
        from modules.notion_sync.notion_live_service import NotionLiveSyncService
        from modules.order_validation.service import OrderValidationService
        from modules.purchases.purchase_service import PurchaseService
        from modules.shipments.channel_shipment_export_service import (
            ChannelShipmentExportService,
        )
        from modules.shipments.shipment_repository import ShipmentRepository

        started_at = perf_counter()
        steps: list[dict[str, Any]] = []
        output_paths: list[dict[str, str]] = []

        def notify(name: str) -> None:
            if progress_callback is not None:
                progress_callback(name)

        def append_step(
            name: str,
            status: str,
            message: str,
            duration: float,
            details: dict[str, Any] | None = None,
        ) -> None:
            row = {
                "step": len(steps) + 1,
                "name": name,
                "status": status,
                "message": message,
                "elapsed_seconds": round(duration, 3),
                "details": details or {},
            }
            steps.append(row)
            self.activity_repository.append(
                action=f"오늘 업무 시작 · {name}",
                result_status={
                    "PASS": "성공",
                    "WARNING": "주의",
                    "FAILED": "실패",
                }[status],
                result_message=message,
                details=row,
            )

        # The production Notion service synchronizes suppliers and products in
        # one transaction. Call it once and expose two operator-facing results.
        notify("Notion Supplier Sync")
        notion_started = perf_counter()
        try:
            notion_result = NotionLiveSyncService().sync()
        except Exception as error:
            duration = perf_counter() - notion_started
            message = str(error)
            append_step("Notion Supplier Sync", "FAILED", message, duration)
            notify("Notion Product Sync")
            append_step("Notion Product Sync", "FAILED", message, duration)
        else:
            duration = perf_counter() - notion_started
            supplier_total = sum(
                int(notion_result.get(key, 0) or 0)
                for key in (
                    "supplier_created",
                    "supplier_updated",
                    "supplier_deactivated",
                )
            )
            supplier_status = "PASS" if supplier_total else "WARNING"
            append_step(
                "Notion Supplier Sync",
                supplier_status,
                (
                    f"생성 {int(notion_result.get('supplier_created', 0) or 0):,} · "
                    f"수정 {int(notion_result.get('supplier_updated', 0) or 0):,} · "
                    f"비활성 {int(notion_result.get('supplier_deactivated', 0) or 0):,}"
                ),
                duration,
                notion_result,
            )
            notify("Notion Product Sync")
            product_total = sum(
                int(notion_result.get(key, 0) or 0)
                for key in (
                    "product_created",
                    "product_updated",
                    "product_deactivated",
                    "condition_created",
                    "condition_updated",
                    "condition_deactivated",
                )
            )
            warning_count = len(notion_result.get("warnings") or [])
            product_status = (
                "WARNING" if warning_count or not product_total else "PASS"
            )
            append_step(
                "Notion Product Sync",
                product_status,
                (
                    f"상품 생성 {int(notion_result.get('product_created', 0) or 0):,} · "
                    f"수정 {int(notion_result.get('product_updated', 0) or 0):,} · "
                    f"주의 {warning_count:,}"
                ),
                duration,
                notion_result,
            )

        notify("Automatic Product Mapping")
        step_started = perf_counter()
        try:
            mapping_result = self.order_repository.auto_map_order_items()
            target_count = int(mapping_result.get("target_count", 0) or 0)
            mapped_count = int(mapping_result.get("mapped_count", 0) or 0)
            append_step(
                "Automatic Product Mapping",
                "PASS" if target_count else "WARNING",
                f"대상 {target_count:,} · 매핑완료 {mapped_count:,}",
                perf_counter() - step_started,
                mapping_result,
            )
        except Exception as error:
            append_step(
                "Automatic Product Mapping",
                "FAILED",
                str(error),
                perf_counter() - step_started,
            )

        notify("Order Validation")
        step_started = perf_counter()
        validation_summary: dict[str, Any] | None = None
        try:
            validation_summary = OrderValidationService(
                self.order_repository
            ).get_summary()
            total_count = int(validation_summary.get("total_count", 0) or 0)
            fail_count = int(validation_summary.get("fail_count", 0) or 0)
            warning_count = int(validation_summary.get("warning_count", 0) or 0)
            if not total_count:
                status = "WARNING"
            elif fail_count:
                status = "FAILED"
            elif warning_count:
                status = "WARNING"
            else:
                status = "PASS"
            append_step(
                "Order Validation",
                status,
                (
                    f"전체 {total_count:,} · 통과 "
                    f"{int(validation_summary.get('pass_count', 0) or 0):,} · "
                    f"주의 {warning_count:,} · 실패 {fail_count:,}"
                ),
                perf_counter() - step_started,
                {
                    key: value
                    for key, value in validation_summary.items()
                    if key != "results"
                },
            )
        except Exception as error:
            append_step(
                "Order Validation",
                "FAILED",
                str(error),
                perf_counter() - step_started,
            )

        notify("Purchase Generation")
        purchase_started = perf_counter()
        validation_failed = (
            validation_summary is None
            or int(validation_summary.get("fail_count", 0) or 0) > 0
        )
        if validation_failed:
            message = "주문 검수 실패로 발주 생성과 파일 출력을 건너뛰었습니다."
            duration = perf_counter() - purchase_started
            append_step("Purchase Generation", "WARNING", message, duration)
            notify("Purchase Export")
            append_step("Purchase Export", "WARNING", message, duration)
        else:
            try:
                purchase_service = PurchaseService()
                candidates = purchase_service.get_purchase_candidates()
                purchase_validation = purchase_service.validate_purchase_candidates(
                    candidates
                )
                if not candidates:
                    message = "발주 가능한 주문상품이 없습니다."
                    duration = perf_counter() - purchase_started
                    append_step("Purchase Generation", "WARNING", message, duration)
                    notify("Purchase Export")
                    append_step("Purchase Export", "WARNING", message, duration)
                elif purchase_validation.get("errors"):
                    message = (
                        "발주 필수정보 오류 "
                        f"{len(purchase_validation.get('errors') or []):,}건으로 건너뛰었습니다."
                    )
                    duration = perf_counter() - purchase_started
                    append_step(
                        "Purchase Generation",
                        "WARNING",
                        message,
                        duration,
                        purchase_validation,
                    )
                    notify("Purchase Export")
                    append_step(
                        "Purchase Export",
                        "WARNING",
                        message,
                        duration,
                        purchase_validation,
                    )
                else:
                    purchase_result = purchase_service.create_purchase_files()
                    duration = perf_counter() - purchase_started
                    created_count = int(
                        purchase_result.get("created_count", 0) or 0
                    )
                    files = [str(path) for path in purchase_result.get("files", [])]
                    generation_status = "PASS" if created_count else "WARNING"
                    export_status = "PASS" if files else "WARNING"
                    append_step(
                        "Purchase Generation",
                        generation_status,
                        (
                            f"발주상품 {created_count:,} · 공급처/차수 "
                            f"{int(purchase_result.get('supplier_count', 0) or 0):,}"
                        ),
                        duration,
                        purchase_result,
                    )
                    notify("Purchase Export")
                    append_step(
                        "Purchase Export",
                        export_status,
                        f"생성 파일 {len(files):,}개",
                        duration,
                        purchase_result,
                    )
                    output_directory = str(
                        purchase_result.get("output_directory") or ""
                    ).strip()
                    if output_directory:
                        output_paths.append(
                            {"label": "발주서 폴더 열기", "path": output_directory}
                        )
            except Exception as error:
                duration = perf_counter() - purchase_started
                message = str(error)
                append_step("Purchase Generation", "FAILED", message, duration)
                notify("Purchase Export")
                append_step("Purchase Export", "FAILED", message, duration)

        notify("Shipment Status Refresh")
        step_started = perf_counter()
        try:
            shipment_repository = ShipmentRepository()
            shipments = shipment_repository.get_shipments()
            order_ids = sorted(
                {
                    int(row["order_id"])
                    for row in shipments
                    if row.get("order_id") is not None
                }
            )
            refresh_errors: list[str] = []
            refreshed_count = 0
            for order_id in order_ids:
                try:
                    shipment_repository.update_order_shipment_status(
                        order_id,
                        "배송중",
                    )
                    refreshed_count += 1
                except Exception as error:
                    refresh_errors.append(f"주문 ID {order_id}: {error}")
            if refresh_errors:
                status = "FAILED"
            elif not order_ids:
                status = "WARNING"
            else:
                status = "PASS"
            append_step(
                "Shipment Status Refresh",
                status,
                (
                    f"송장 보유 주문 {len(order_ids):,} · 갱신 {refreshed_count:,} · "
                    f"실패 {len(refresh_errors):,}"
                ),
                perf_counter() - step_started,
                {"errors": refresh_errors},
            )
        except Exception as error:
            append_step(
                "Shipment Status Refresh",
                "FAILED",
                str(error),
                perf_counter() - step_started,
            )

        channel_service: ChannelShipmentExportService | None = None
        for name, exporter, folder_label in (
            (
                "Generate Coupang Shipment Upload",
                "export_coupang",
                "쿠팡 송장파일 폴더 열기",
            ),
            (
                "Generate SmartStore Shipment Upload",
                "export_smartstore",
                "스마트스토어 송장파일 폴더 열기",
            ),
        ):
            notify(name)
            step_started = perf_counter()
            try:
                if channel_service is None:
                    channel_service = ChannelShipmentExportService()
                exporter = getattr(channel_service, exporter)
                export_result = exporter()
                created = bool(export_result.get("created"))
                missing_count = int(
                    export_result.get("missing_metadata_count", 0) or 0
                )
                status = "PASS" if created and not missing_count else "WARNING"
                append_step(
                    name,
                    status,
                    str(export_result.get("message") or "생성 대상이 없습니다."),
                    perf_counter() - step_started,
                    export_result,
                )
                output_file = str(
                    export_result.get("output_file_path") or ""
                ).strip()
                if output_file:
                    output_paths.append(
                        {"label": folder_label, "path": str(Path(output_file).parent)}
                    )
            except Exception as error:
                append_step(
                    name,
                    "FAILED",
                    str(error),
                    perf_counter() - step_started,
                )

        notify("Final Summary")
        final_started = perf_counter()
        prior_failed = sum(row["status"] == "FAILED" for row in steps)
        prior_warning = sum(row["status"] == "WARNING" for row in steps)
        final_status = (
            "FAILED" if prior_failed else "WARNING" if prior_warning else "PASS"
        )
        append_step(
            "Final Summary",
            final_status,
            (
                f"PASS {sum(row['status'] == 'PASS' for row in steps):,} · "
                f"WARNING {prior_warning:,} · FAILED {prior_failed:,}"
            ),
            perf_counter() - final_started,
        )
        operational_steps = steps[:-1]
        return {
            "steps": steps,
            "output_paths": output_paths,
            "elapsed_seconds": round(perf_counter() - started_at, 3),
            "pass_count": sum(row["status"] == "PASS" for row in operational_steps),
            "warning_count": sum(
                row["status"] == "WARNING" for row in operational_steps
            ),
            "failed_count": sum(
                row["status"] == "FAILED" for row in operational_steps
            ),
        }

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
