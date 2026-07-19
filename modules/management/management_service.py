from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ManagementService:
    """대표가 확인할 매출·이익·고객·처리시간 지표를 집계합니다."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or DATABASE_PATH)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def get_management_data(self) -> dict[str, Any]:
        today = date.today()
        month_start = today.replace(day=1)
        previous_month_end = month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)

        errors: list[str] = []
        orders = self._read_orders(errors)
        settlements = self._read_settlements(errors)
        purchase_times = self._read_purchase_times(errors)

        settlement_by_order = {self._to_int(row.get("order_id")): row for row in settlements}
        normalized = [self._normalize_order(row, settlement_by_order) for row in orders]

        today_rows = [row for row in normalized if row["date"] == today.isoformat()]
        month_rows = [row for row in normalized if month_start.isoformat() <= row["date"] <= today.isoformat()]
        previous_rows = [
            row for row in normalized
            if previous_month_start.isoformat() <= row["date"] <= previous_month_end.isoformat()
        ]

        month_sales = sum(row["sales"] for row in month_rows)
        month_profit = sum(row["profit"] for row in month_rows)
        margin_rate = (month_profit / month_sales * 100) if month_sales else 0.0
        repeat_rate = self._repeat_customer_rate(month_rows)
        average_order = int(month_sales / len(month_rows)) if month_rows else 0
        average_purchase_minutes = self._average_minutes(purchase_times)

        previous_sales = sum(row["sales"] for row in previous_rows)
        previous_profit = sum(row["profit"] for row in previous_rows)

        return {
            "summary": {
                "today_sales": sum(row["sales"] for row in today_rows),
                "today_profit": sum(row["profit"] for row in today_rows),
                "month_sales": month_sales,
                "month_profit": month_profit,
                "margin_rate": margin_rate,
                "average_order": average_order,
                "repeat_rate": repeat_rate,
                "average_purchase_minutes": average_purchase_minutes,
                "month_order_count": len(month_rows),
                "unsettled_count": sum(1 for row in month_rows if not row["has_settlement"]),
            },
            "comparisons": {
                "sales_rate": self._change_rate(month_sales, previous_sales),
                "profit_rate": self._change_rate(month_profit, previous_profit),
            },
            "daily": self._daily_stats(normalized, days=30),
            "top_products": self._top_products(month_rows),
            "platforms": self._platform_stats(month_rows),
            "errors": errors,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _read_orders(self, errors: list[str]) -> list[dict[str, Any]]:
        query = """
            SELECT o.id, o.ordered_at, o.platform, o.receiver_name,
                   o.receiver_phone, COALESCE(o.total_amount, 0) AS total_amount,
                   COALESCE(oi.item_summary, '-') AS item_summary
            FROM orders AS o
            LEFT JOIN (
                SELECT order_id,
                       GROUP_CONCAT(
                           CASE WHEN option_name IS NOT NULL AND TRIM(option_name) != ''
                                THEN platform_product_name || ' / ' || option_name
                                ELSE platform_product_name END,
                           ' | '
                       ) AS item_summary
                FROM order_items
                GROUP BY order_id
            ) AS oi ON oi.order_id = o.id
            ORDER BY o.ordered_at DESC
        """
        try:
            with self._connect() as connection:
                return [dict(row) for row in connection.execute(query).fetchall()]
        except Exception as error:
            errors.append(f"주문 집계: {error}")
            return []

    def _read_settlements(self, errors: list[str]) -> list[dict[str, Any]]:
        query = """
            SELECT order_id, sales_amount, purchase_cost, shipping_fee,
                   platform_fee, other_cost, settlement_status
            FROM settlements
        """
        try:
            with self._connect() as connection:
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='settlements'"
                ).fetchone()
                if not exists:
                    return []
                return [dict(row) for row in connection.execute(query).fetchall()]
        except Exception as error:
            errors.append(f"정산 집계: {error}")
            return []

    def _read_purchase_times(self, errors: list[str]) -> list[float]:
        """스키마가 지원할 때 주문→발주 생성 시간을 분 단위로 계산합니다."""
        try:
            with self._connect() as connection:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(purchase_orders)").fetchall()
                }
                order_column = next((name for name in ("order_id",) if name in columns), None)
                created_column = next(
                    (name for name in ("created_at", "purchased_at", "ordered_at") if name in columns),
                    None,
                )
                if not order_column or not created_column:
                    return []
                query = f"""
                    SELECT (JULIANDAY(p.{created_column}) - JULIANDAY(o.ordered_at)) * 1440.0
                    FROM purchase_orders AS p
                    JOIN orders AS o ON o.id = p.{order_column}
                    WHERE p.{created_column} IS NOT NULL AND o.ordered_at IS NOT NULL
                """
                return [max(0.0, float(row[0])) for row in connection.execute(query).fetchall() if row[0] is not None]
        except Exception as error:
            errors.append(f"평균 발주시간: {error}")
            return []

    def _normalize_order(
        self,
        order: dict[str, Any],
        settlement_by_order: dict[int, dict[str, Any]],
    ) -> dict[str, Any]:
        order_id = self._to_int(order.get("id"))
        settlement = settlement_by_order.get(order_id)
        original_sales = self._to_int(order.get("total_amount"))
        if settlement:
            sales = self._to_int(settlement.get("sales_amount")) or original_sales
            costs = sum(
                self._to_int(settlement.get(key))
                for key in ("purchase_cost", "shipping_fee", "platform_fee", "other_cost")
            )
            profit = sales - costs
        else:
            sales = original_sales
            profit = sales
        return {
            "id": order_id,
            "date": str(order.get("ordered_at") or "")[:10],
            "platform": str(order.get("platform") or "미지정"),
            "customer": self._customer_key(order),
            "item_summary": str(order.get("item_summary") or "-").split(" | ")[0],
            "sales": sales,
            "profit": profit,
            "has_settlement": settlement is not None,
        }

    def _daily_stats(self, rows: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
        totals: dict[str, dict[str, int]] = defaultdict(lambda: {"sales": 0, "profit": 0, "orders": 0})
        for row in rows:
            key = row["date"]
            if key:
                totals[key]["sales"] += row["sales"]
                totals[key]["profit"] += row["profit"]
                totals[key]["orders"] += 1
        result = []
        today = date.today()
        for offset in range(days - 1, -1, -1):
            target = today - timedelta(days=offset)
            key = target.isoformat()
            result.append({"date": key, "label": target.strftime("%m/%d"), **totals[key]})
        return result

    @staticmethod
    def _top_products(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        totals: dict[str, dict[str, int]] = defaultdict(lambda: {"orders": 0, "sales": 0, "profit": 0})
        for row in rows:
            key = row["item_summary"] or "상품 미지정"
            totals[key]["orders"] += 1
            totals[key]["sales"] += row["sales"]
            totals[key]["profit"] += row["profit"]
        return [
            {"product": key, **value}
            for key, value in sorted(totals.items(), key=lambda item: item[1]["sales"], reverse=True)[:10]
        ]

    @staticmethod
    def _platform_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        totals: dict[str, dict[str, int]] = defaultdict(lambda: {"orders": 0, "sales": 0})
        for row in rows:
            totals[row["platform"]]["orders"] += 1
            totals[row["platform"]]["sales"] += row["sales"]
        return [
            {"platform": key, **value}
            for key, value in sorted(totals.items(), key=lambda item: item[1]["sales"], reverse=True)
        ]

    @staticmethod
    def _customer_key(order: dict[str, Any]) -> str:
        phone = "".join(character for character in str(order.get("receiver_phone") or "") if character.isdigit())
        return phone or str(order.get("receiver_name") or "").strip()

    @staticmethod
    def _repeat_customer_rate(rows: list[dict[str, Any]]) -> float:
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            if row["customer"]:
                counts[row["customer"]] += 1
        if not counts:
            return 0.0
        return sum(1 for count in counts.values() if count >= 2) / len(counts) * 100

    @staticmethod
    def _average_minutes(values: list[float]) -> int:
        return int(sum(values) / len(values)) if values else 0

    @staticmethod
    def _change_rate(current: int, previous: int) -> float | None:
        if previous == 0:
            return None if current else 0.0
        return (current - previous) / abs(previous) * 100

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(str(value or 0).replace(",", "")))
        except (TypeError, ValueError):
            return 0
