from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class StatisticsService:
    """기간별 주문·매출·상품·고객 통계를 집계합니다."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or DATABASE_PATH)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def get_statistics(self, start_date: str, end_date: str) -> dict[str, Any]:
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        if start > end:
            raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")

        rows = self._read_rows(start.isoformat(), end.isoformat())
        total_sales = sum(self._int(row["total_amount"]) for row in rows)
        order_count = len({self._int(row["order_id"]) for row in rows})
        item_quantity = sum(self._int(row["quantity"]) for row in rows)
        customer_keys = {self._customer_key(row) for row in rows if self._customer_key(row)}

        return {
            "summary": {
                "order_count": order_count,
                "total_sales": total_sales,
                "average_order": int(total_sales / order_count) if order_count else 0,
                "item_quantity": item_quantity,
                "customer_count": len(customer_keys),
            },
            "daily": self._daily(rows, start, end),
            "products": self._products(rows),
            "platforms": self._platforms(rows),
            "customers": self._customers(rows),
            "statuses": self._statuses(rows),
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _read_rows(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        query = """
            SELECT o.id AS order_id, SUBSTR(o.ordered_at, 1, 10) AS order_date,
                   o.platform, o.order_status, o.payment_status, o.purchase_status,
                   o.shipment_status, o.receiver_name, o.receiver_phone,
                   COALESCE(o.total_amount, 0) AS total_amount,
                   oi.id AS item_id, COALESCE(oi.platform_product_name, '상품 미지정') AS product_name,
                   COALESCE(oi.option_name, '') AS option_name,
                   COALESCE(oi.quantity, 0) AS quantity,
                   COALESCE(oi.total_price, 0) AS item_sales
            FROM orders AS o
            LEFT JOIN order_items AS oi ON oi.order_id = o.id
            WHERE SUBSTR(o.ordered_at, 1, 10) BETWEEN ? AND ?
            ORDER BY o.ordered_at, o.id, oi.id
        """
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, (start_date, end_date)).fetchall()]

    def _daily(self, rows: list[dict[str, Any]], start: date, end: date) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"orders": set(), "sales": 0, "quantity": 0})
        seen_sales: set[int] = set()
        for row in rows:
            key = str(row.get("order_date") or "")
            order_id = self._int(row.get("order_id"))
            grouped[key]["orders"].add(order_id)
            grouped[key]["quantity"] += self._int(row.get("quantity"))
            if order_id not in seen_sales:
                grouped[key]["sales"] += self._int(row.get("total_amount"))
                seen_sales.add(order_id)
        result = []
        cursor = start
        while cursor <= end:
            key = cursor.isoformat()
            item = grouped[key]
            result.append({"date": key, "label": cursor.strftime("%m/%d"), "orders": len(item["orders"]), "sales": item["sales"], "quantity": item["quantity"]})
            cursor += timedelta(days=1)
        return result

    def _products(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"orders": set(), "quantity": 0, "sales": 0})
        for row in rows:
            name = str(row.get("product_name") or "상품 미지정")
            option = str(row.get("option_name") or "").strip()
            key = f"{name} / {option}" if option else name
            grouped[key]["orders"].add(self._int(row.get("order_id")))
            grouped[key]["quantity"] += self._int(row.get("quantity"))
            grouped[key]["sales"] += self._int(row.get("item_sales"))
        result = [{"product": key, "orders": len(value["orders"]), "quantity": value["quantity"], "sales": value["sales"]} for key, value in grouped.items()]
        return sorted(result, key=lambda row: (row["sales"], row["quantity"]), reverse=True)[:50]

    def _platforms(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"orders": set(), "sales": 0})
        seen: set[int] = set()
        for row in rows:
            key = str(row.get("platform") or "미지정")
            order_id = self._int(row.get("order_id"))
            grouped[key]["orders"].add(order_id)
            if order_id not in seen:
                grouped[key]["sales"] += self._int(row.get("total_amount"))
                seen.add(order_id)
        return sorted(({"platform": key, "orders": len(value["orders"]), "sales": value["sales"]} for key, value in grouped.items()), key=lambda row: row["sales"], reverse=True)

    def _customers(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"name": "-", "phone": "-", "orders": set(), "sales": 0})
        seen: set[int] = set()
        for row in rows:
            key = self._customer_key(row)
            if not key:
                continue
            grouped[key]["name"] = str(row.get("receiver_name") or "-")
            grouped[key]["phone"] = str(row.get("receiver_phone") or "-")
            order_id = self._int(row.get("order_id"))
            grouped[key]["orders"].add(order_id)
            if order_id not in seen:
                grouped[key]["sales"] += self._int(row.get("total_amount"))
                seen.add(order_id)
        result = [{"name": value["name"], "phone": value["phone"], "orders": len(value["orders"]), "sales": value["sales"]} for value in grouped.values()]
        return sorted(result, key=lambda row: (row["sales"], row["orders"]), reverse=True)[:50]

    def _statuses(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        orders: dict[int, dict[str, Any]] = {}
        for row in rows:
            orders.setdefault(self._int(row.get("order_id")), row)
        fields = (("payment_status", "결제"), ("purchase_status", "발주"), ("shipment_status", "배송"))
        result = []
        for field, category in fields:
            counts: dict[str, int] = defaultdict(int)
            for row in orders.values():
                counts[str(row.get(field) or "미지정")] += 1
            result.extend({"category": category, "status": status, "count": count} for status, count in sorted(counts.items()))
        return result

    @staticmethod
    def _customer_key(row: dict[str, Any]) -> str:
        phone = "".join(ch for ch in str(row.get("receiver_phone") or "") if ch.isdigit())
        return phone or str(row.get("receiver_name") or "").strip()

    @staticmethod
    def _parse_date(value: str) -> date:
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError as error:
            raise ValueError("날짜는 YYYY-MM-DD 형식으로 입력하세요.") from error

    @staticmethod
    def _int(value: Any) -> int:
        try:
            return int(float(str(value or 0).replace(",", "")))
        except (TypeError, ValueError):
            return 0
