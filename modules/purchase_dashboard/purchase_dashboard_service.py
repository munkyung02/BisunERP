from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from modules.purchase_dashboard.purchase_dashboard_repository import (
    PurchaseDashboardRepository,
)


class PurchaseDashboardService:
    """구매 통계 계산과 기간 처리를 담당합니다."""

    PERIODS = (
        "오늘",
        "이번주",
        "이번달",
        "최근 30일",
        "최근 90일",
        "올해",
        "직접입력",
    )

    def __init__(
        self,
        repository: PurchaseDashboardRepository | None = None,
        database_path: str | Path | None = None,
    ) -> None:
        self.repository = repository or PurchaseDashboardRepository(
            database_path=database_path
        )

    @staticmethod
    def parse_date(value: str) -> date:
        cleaned = str(value).strip()

        try:
            return datetime.strptime(
                cleaned,
                "%Y-%m-%d",
            ).date()
        except ValueError as error:
            raise ValueError(
                "날짜는 YYYY-MM-DD 형식으로 입력하세요."
            ) from error

    def resolve_period(
        self,
        period_name: str,
        *,
        custom_start: str | None = None,
        custom_end: str | None = None,
    ) -> tuple[str, str]:
        today = date.today()
        period = str(period_name).strip()

        if period == "오늘":
            start = end = today
        elif period == "이번주":
            start = today - timedelta(days=today.weekday())
            end = today
        elif period == "이번달":
            start = today.replace(day=1)
            end = today
        elif period == "최근 30일":
            start = today - timedelta(days=29)
            end = today
        elif period == "최근 90일":
            start = today - timedelta(days=89)
            end = today
        elif period == "올해":
            start = today.replace(month=1, day=1)
            end = today
        elif period == "직접입력":
            if not custom_start or not custom_end:
                raise ValueError("조회 시작일과 종료일을 입력하세요.")

            start = self.parse_date(custom_start)
            end = self.parse_date(custom_end)
        else:
            raise ValueError("올바르지 않은 조회 기간입니다.")

        if start > end:
            raise ValueError(
                "조회 시작일은 종료일보다 늦을 수 없습니다."
            )

        return start.isoformat(), end.isoformat()

    def get_dashboard_data(
        self,
        *,
        period_name: str,
        custom_start: str | None = None,
        custom_end: str | None = None,
    ) -> dict[str, Any]:
        start_date, end_date = self.resolve_period(
            period_name,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "summary": self.repository.get_kpi_summary(
                start_date=start_date,
                end_date=end_date,
            ),
            "today_summary": self.repository.get_today_summary(),
            "supplier_ranking": (
                self.repository.get_supplier_ranking(
                    start_date=start_date,
                    end_date=end_date,
                    limit=10,
                )
            ),
            "product_ranking": (
                self.repository.get_product_ranking(
                    start_date=start_date,
                    end_date=end_date,
                    limit=20,
                )
            ),
            "monthly_statistics": (
                self.repository.get_monthly_statistics(
                    months=12
                )
            ),
            "inactive_suppliers": (
                self.repository.get_inactive_suppliers(
                    inactive_days=90,
                    limit=20,
                )
            ),
        }

    @staticmethod
    def build_alerts(
        data: dict[str, Any],
    ) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []

        summary = data.get("summary") or {}

        pending_count = int(summary.get("pending_count") or 0)
        if pending_count > 0:
            alerts.append({
                "level": "주의",
                "title": "발주대기 존재",
                "message": (
                    f"아직 처리되지 않은 발주대기 "
                    f"{pending_count:,}건이 있습니다."
                ),
            })

        for supplier in data.get("inactive_suppliers") or []:
            supplier_name = (
                supplier.get("supplier_name")
                or "공급처 미지정"
            )
            last_date = supplier.get("last_purchase_date")

            if last_date:
                inactive_days = int(
                    supplier.get("inactive_days") or 0
                )
                message = (
                    f"최근 {inactive_days:,}일 동안 "
                    "발주가 없습니다."
                )
            else:
                message = "발주 이력이 없습니다."

            alerts.append({
                "level": "확인",
                "title": str(supplier_name),
                "message": message,
            })

        return alerts[:20]