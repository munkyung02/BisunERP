from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class SettlementService:
    """주문 매출과 비용을 결합해 정산·순이익을 계산합니다."""

    TOSS_EXPECTED_COUPON_DISCOUNT = 500
    TOSS_EXPECTED_FEE_RATE = 0.11

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
        today_summary = self.get_dashboard_period_summary(today_text, today_text)
        return {
            "today_sales": today_summary["sales"],
            "today_purchase": today_summary["purchase"],
            "today_profit": today_summary["profit"],
            "month_profit": self._get_confirmed_profit(month_start, today_text),
        }

    def get_dashboard_period_summary(
        self,
        ordered_from: str,
        ordered_to: str,
    ) -> dict[str, int]:
        """Dashboard와 동일한 기준으로 주문일 범위의 손익을 집계합니다."""
        return {
            "sales": self._get_dashboard_sales(ordered_from, ordered_to),
            "purchase": self._get_confirmed_purchase_cost(ordered_from, ordered_to),
            "profit": self._get_confirmed_profit(ordered_from, ordered_to),
        }

    def get_product_profit_summary(
        self,
        ordered_from: str,
        ordered_to: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """기존 Dashboard 손익 기준을 상품별로 합산합니다."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    oi.product_id,
                    p.product_name,
                    oi.order_id,
                    oi.quantity,
                    oi.total_price,
                    o.platform,
                    po.id AS purchase_order_id,
                    po.unit_price,
                    po.item_amount,
                    po.shipping_fee,
                    metadata.raw_source_json
                FROM order_items AS oi
                JOIN orders AS o ON o.id = oi.order_id
                JOIN products AS p ON p.id = oi.product_id
                LEFT JOIN purchase_orders AS po ON po.order_item_id = oi.id
                LEFT JOIN channel_order_item_metadata AS metadata
                  ON metadata.order_item_id = oi.id
                WHERE DATE(o.ordered_at) >= DATE(?)
                  AND DATE(o.ordered_at) <= DATE(?)
                  AND COALESCE(oi.cancellation_status, '정상') NOT IN (
                      '미발주취소', '발주후취소완료'
                  )
                """,
                (ordered_from, ordered_to),
            ).fetchall()

        products: dict[int, dict[str, Any]] = {}
        for row in rows:
            product_id = int(row["product_id"])
            item = products.setdefault(product_id, {
                "product_id": product_id,
                "product_name": str(row["product_name"] or ""),
                "order_ids": set(),
                "total_quantity": 0,
                "sales": 0,
                "purchase": 0,
                "profit": 0,
                "confirmed_count": 0,
                "unconfirmed_count": 0,
            })
            item["order_ids"].add(int(row["order_id"]))
            item["total_quantity"] += self._to_int(row["quantity"])

            sales_amount = self._dashboard_sales_amount(row)
            snapshot_is_valid = (
                row["purchase_order_id"] is not None
                and self._to_int(row["unit_price"]) > 0
                and self._to_int(row["item_amount"]) > 0
            )
            if (
                sales_amount is None
                or not snapshot_is_valid
                or str(row["platform"] or "").strip() == "LotteOn"
            ):
                item["unconfirmed_count"] += 1
                continue

            item["confirmed_count"] += 1
            item["sales"] += sales_amount
            item["purchase"] += (
                self._to_int(row["item_amount"])
                + self._to_int(row["shipping_fee"])
            )
            item["profit"] += (
                sales_amount
                - self._to_int(row["item_amount"])
                - self._to_int(row["shipping_fee"])
            )

        result: list[dict[str, Any]] = []
        for item in products.values():
            confirmed = int(item["confirmed_count"]) > 0
            sales = int(item["sales"])
            profit = int(item["profit"])
            result.append({
                "product_id": item["product_id"],
                "product_name": item["product_name"],
                "order_count": len(item["order_ids"]),
                "total_quantity": int(item["total_quantity"]),
                "sales": sales,
                "purchase": int(item["purchase"]),
                "profit": profit if confirmed else None,
                "margin_rate": (
                    profit / sales * 100
                    if confirmed and sales > 0
                    else None
                ),
                "is_confirmed": confirmed and sales > 0,
                "confirmed_count": int(item["confirmed_count"]),
                "unconfirmed_count": int(item["unconfirmed_count"]),
            })

        result.sort(key=lambda item: (
            -int(item["purchase"]),
            -int(item["total_quantity"]),
            str(item["product_name"]),
        ))
        return result[:max(0, int(limit))]

    def _get_confirmed_purchase_cost(self, ordered_from: str, ordered_to: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(
                    SUM(po.item_amount + po.shipping_fee),
                    0
                ) AS confirmed_purchase_cost
                FROM purchase_orders AS po
                JOIN order_items AS oi
                  ON oi.id = po.order_item_id
                JOIN orders AS o
                  ON o.id = oi.order_id
                WHERE DATE(o.ordered_at) >= DATE(?)
                  AND DATE(o.ordered_at) <= DATE(?)
                  AND COALESCE(oi.cancellation_status, '정상') NOT IN (
                      '미발주취소', '발주후취소완료'
                  )
                  AND po.unit_price > 0
                  AND po.item_amount > 0
                """,
                (ordered_from, ordered_to),
            ).fetchone()
        return self._to_int(row["confirmed_purchase_cost"] if row is not None else 0)

    def _get_confirmed_profit(self, ordered_from: str, ordered_to: str) -> int:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    o.platform,
                    oi.total_price,
                    po.item_amount,
                    po.shipping_fee,
                    metadata.raw_source_json
                FROM order_items AS oi
                JOIN orders AS o
                  ON o.id = oi.order_id
                JOIN purchase_orders AS po
                  ON po.order_item_id = oi.id
                LEFT JOIN channel_order_item_metadata AS metadata
                  ON metadata.order_item_id = oi.id
                WHERE DATE(o.ordered_at) >= DATE(?)
                  AND DATE(o.ordered_at) <= DATE(?)
                  AND COALESCE(oi.cancellation_status, '정상') NOT IN (
                      '미발주취소', '발주후취소완료'
                  )
                  AND o.platform != 'LotteOn'
                  AND po.unit_price > 0
                  AND po.item_amount > 0
                """,
                (ordered_from, ordered_to),
            ).fetchall()

        confirmed_profit = 0
        for row in rows:
            sales_amount = self._dashboard_sales_amount(row)
            if sales_amount is None:
                continue
            confirmed_profit += (
                sales_amount
                - self._to_int(row["item_amount"])
                - self._to_int(row["shipping_fee"])
            )
        return confirmed_profit

    def _get_dashboard_sales(self, ordered_from: str, ordered_to: str) -> int:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    o.platform,
                    oi.total_price,
                    metadata.raw_source_json
                FROM order_items AS oi
                JOIN orders AS o
                  ON o.id = oi.order_id
                LEFT JOIN channel_order_item_metadata AS metadata
                  ON metadata.order_item_id = oi.id
                WHERE DATE(o.ordered_at) >= DATE(?)
                  AND DATE(o.ordered_at) <= DATE(?)
                  AND COALESCE(oi.cancellation_status, '정상') NOT IN (
                      '미발주취소', '발주후취소완료'
                  )
                """,
                (ordered_from, ordered_to),
            ).fetchall()

        return sum(
            sales_amount
            for row in rows
            if (sales_amount := self._dashboard_sales_amount(row)) is not None
        )

    @classmethod
    def _dashboard_sales_amount(cls, row: sqlite3.Row) -> int | None:
        platform = str(row["platform"] or "").strip()
        if platform not in {
            "쿠팡", "스마트스토어", "Gmarket", "Auction", "Toss", "Kakao"
        }:
            return cls._to_int(row["total_price"])

        try:
            raw_source = json.loads(str(row["raw_source_json"] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

        if platform == "쿠팡":
            payment_amount = cls._parse_source_amount(raw_source.get("결제액"))
            if payment_amount is None:
                return None
            return cls._to_int(payment_amount * 0.88)

        if platform == "스마트스토어":
            settlement_amount = cls._parse_source_amount(
                raw_source.get("정산예정금액")
            )
            if settlement_amount is None:
                return None
            shipping_fee = cls._parse_source_amount(
                raw_source.get("배송비 합계")
            )
            remote_shipping_fee = cls._parse_source_amount(
                raw_source.get("제주/도서 추가배송비")
            )
            return (
                settlement_amount
                + (shipping_fee or 0)
                + (remote_shipping_fee or 0)
            )

        if platform == "Toss":
            order_amount = cls._parse_source_amount(raw_source.get("주문금액"))
            if order_amount is None:
                return None
            shipping_fee = cls._parse_source_amount(raw_source.get("배송비 합계"))
            fee_base = order_amount - cls.TOSS_EXPECTED_COUPON_DISCOUNT
            return (
                cls._to_int(fee_base * (1 - cls.TOSS_EXPECTED_FEE_RATE))
                + (shipping_fee or 0)
            )

        if platform == "Kakao":
            settlement_base = cls._parse_source_amount(
                raw_source.get("정산기준금액")
            )
            if settlement_base is None:
                return None
            product_settlement = (
                settlement_base
                - (cls._parse_source_amount(raw_source.get("기본수수료")) or 0)
                - (
                    cls._parse_source_amount(raw_source.get("노출추가수수료"))
                    or 0
                )
                - (
                    cls._parse_source_amount(raw_source.get("추천리워드수수료"))
                    or 0
                )
                + (
                    cls._parse_source_amount(raw_source.get("수수료할인금액"))
                    or 0
                )
            )
            basic_shipping = 0
            if str(raw_source.get("기본배송비 유형") or "").strip() == "유료":
                basic_shipping = (
                    cls._parse_source_amount(raw_source.get("기본배송비 금액"))
                    or 0
                )
            remote_shipping = 0
            remote_status = str(
                raw_source.get("도서산간 주문 여부") or ""
            ).strip()
            if "도서산간" in remote_status:
                remote_shipping = (
                    cls._parse_source_amount(
                        raw_source.get("도서산간 추가 배송비 금액")
                    )
                    or 0
                )
            return product_settlement + basic_shipping + remote_shipping

        settlement_amount = cls._parse_source_amount(raw_source.get("정산예정금액"))
        if settlement_amount is None:
            return None
        customer_shipping_fee = cls._parse_source_amount(raw_source.get("배송비 금액"))
        return settlement_amount + (customer_shipping_fee or 0)

    @staticmethod
    def _parse_source_amount(value: Any) -> int | None:
        text = str(value or "").strip()
        if not text:
            return None
        normalized = re.sub(r"[^0-9.-]", "", text)
        if not normalized:
            return None
        try:
            return int(float(normalized))
        except ValueError:
            return None

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(str(value or 0).replace(",", "")))
        except (TypeError, ValueError):
            return 0
