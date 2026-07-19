from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class SettlementService:
    """주문 매출과 비용을 결합해 정산·순이익을 계산합니다."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or DATABASE_PATH)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_tables()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize_tables(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settlements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL UNIQUE,
                    sales_amount INTEGER NOT NULL DEFAULT 0,
                    purchase_cost INTEGER NOT NULL DEFAULT 0,
                    shipping_fee INTEGER NOT NULL DEFAULT 0,
                    platform_fee INTEGER NOT NULL DEFAULT 0,
                    other_cost INTEGER NOT NULL DEFAULT 0,
                    memo TEXT,
                    settlement_status TEXT NOT NULL DEFAULT '미정산',
                    settled_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_settlements_status
                ON settlements(settlement_status);
                """
            )

    def get_rows(
        self,
        keyword: str | None = None,
        ordered_from: str | None = None,
        ordered_to: str | None = None,
        settlement_status: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[Any] = []

        if keyword and keyword.strip():
            value = f"%{keyword.strip()}%"
            conditions.append(
                "(o.order_number LIKE ? OR o.receiver_name LIKE ? "
                "OR o.receiver_phone LIKE ? OR oi.item_summary LIKE ?)"
            )
            parameters.extend([value, value, value, value])
        if ordered_from:
            conditions.append("DATE(o.ordered_at) >= DATE(?)")
            parameters.append(ordered_from)
        if ordered_to:
            conditions.append("DATE(o.ordered_at) <= DATE(?)")
            parameters.append(ordered_to)
        if settlement_status and settlement_status != "전체":
            conditions.append("COALESCE(s.settlement_status, '미정산') = ?")
            parameters.append(settlement_status)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT
                o.id AS order_id,
                o.order_number,
                o.ordered_at,
                o.platform,
                o.receiver_name,
                o.receiver_phone,
                COALESCE(o.total_amount, 0) AS order_sales_amount,
                COALESCE(oi.item_summary, '-') AS item_summary,
                COALESCE(s.sales_amount, o.total_amount, 0) AS sales_amount,
                COALESCE(s.purchase_cost, 0) AS purchase_cost,
                COALESCE(s.shipping_fee, 0) AS shipping_fee,
                COALESCE(s.platform_fee, 0) AS platform_fee,
                COALESCE(s.other_cost, 0) AS other_cost,
                COALESCE(s.memo, '') AS memo,
                COALESCE(s.settlement_status, '미정산') AS settlement_status,
                s.settled_at,
                (
                    COALESCE(s.sales_amount, o.total_amount, 0)
                    - COALESCE(s.purchase_cost, 0)
                    - COALESCE(s.shipping_fee, 0)
                    - COALESCE(s.platform_fee, 0)
                    - COALESCE(s.other_cost, 0)
                ) AS net_profit
            FROM orders AS o
            LEFT JOIN settlements AS s ON s.order_id = o.id
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
            {where}
            ORDER BY o.ordered_at DESC, o.id DESC
        """
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def save_settlement(
        self,
        *,
        order_id: int,
        sales_amount: int,
        purchase_cost: int,
        shipping_fee: int,
        platform_fee: int,
        other_cost: int,
        memo: str = "",
        settlement_status: str = "미정산",
    ) -> None:
        if order_id <= 0:
            raise ValueError("올바른 주문을 선택하세요.")
        values = [sales_amount, purchase_cost, shipping_fee, platform_fee, other_cost]
        if any(value < 0 for value in values):
            raise ValueError("금액은 0원 이상이어야 합니다.")
        if settlement_status not in {"미정산", "정산완료"}:
            raise ValueError("정산 상태가 올바르지 않습니다.")

        settled_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if settlement_status == "정산완료" else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO settlements (
                    order_id, sales_amount, purchase_cost, shipping_fee,
                    platform_fee, other_cost, memo, settlement_status,
                    settled_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(order_id) DO UPDATE SET
                    sales_amount = excluded.sales_amount,
                    purchase_cost = excluded.purchase_cost,
                    shipping_fee = excluded.shipping_fee,
                    platform_fee = excluded.platform_fee,
                    other_cost = excluded.other_cost,
                    memo = excluded.memo,
                    settlement_status = excluded.settlement_status,
                    settled_at = excluded.settled_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (order_id, sales_amount, purchase_cost, shipping_fee,
                 platform_fee, other_cost, memo.strip(), settlement_status, settled_at),
            )

    def delete_settlement(self, order_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM settlements WHERE order_id = ?", (order_id,))

    def get_summary(self, ordered_from: str | None = None, ordered_to: str | None = None) -> dict[str, int]:
        rows = self.get_rows(ordered_from=ordered_from, ordered_to=ordered_to)
        sales = sum(self._to_int(row.get("sales_amount")) for row in rows)
        purchase = sum(self._to_int(row.get("purchase_cost")) for row in rows)
        shipping = sum(self._to_int(row.get("shipping_fee")) for row in rows)
        platform = sum(self._to_int(row.get("platform_fee")) for row in rows)
        other = sum(self._to_int(row.get("other_cost")) for row in rows)
        completed = sum(1 for row in rows if row.get("settlement_status") == "정산완료")
        return {
            "order_count": len(rows), "sales": sales, "purchase_cost": purchase,
            "shipping_fee": shipping, "platform_fee": platform,
            "other_cost": other, "total_cost": purchase + shipping + platform + other,
            "net_profit": sales - purchase - shipping - platform - other,
            "completed_count": completed, "waiting_count": len(rows) - completed,
        }

    def get_dashboard_profit(self) -> dict[str, int]:
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        today_text = today.isoformat()
        return {
            "today_profit": self.get_summary(today_text, today_text)["net_profit"],
            "month_profit": self.get_summary(month_start, today_text)["net_profit"],
        }

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(str(value or 0).replace(",", "")))
        except (TypeError, ValueError):
            return 0
