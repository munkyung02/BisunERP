from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"
PAYMENT_STATUSES = ("입금대기", "부분입금", "입금완료", "입금취소")


class ReceiptService:
    """주문별 계좌이체 입금 내역을 관리하고 주문 결제상태를 동기화합니다."""

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
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    customer_id INTEGER,
                    depositor_name TEXT,
                    payment_amount INTEGER NOT NULL DEFAULT 0,
                    payment_method TEXT NOT NULL DEFAULT '계좌이체',
                    payment_status TEXT NOT NULL DEFAULT '입금대기',
                    paid_at TEXT,
                    bank_message TEXT,
                    memo TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE SET NULL,
                    FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
                CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(payment_status);
                """
            )

    def get_rows(
        self,
        *,
        keyword: str | None = None,
        ordered_from: str | None = None,
        ordered_to: str | None = None,
        payment_status: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[Any] = []
        if keyword and keyword.strip():
            value = f"%{keyword.strip()}%"
            conditions.append(
                "(o.order_number LIKE ? OR o.receiver_name LIKE ? OR "
                "o.receiver_phone LIKE ? OR COALESCE(p.depositor_name, '') LIKE ? OR "
                "COALESCE(oi.item_summary, '') LIKE ?)"
            )
            parameters.extend([value] * 5)
        if ordered_from:
            conditions.append("DATE(o.ordered_at) >= DATE(?)")
            parameters.append(ordered_from)
        if ordered_to:
            conditions.append("DATE(o.ordered_at) <= DATE(?)")
            parameters.append(ordered_to)
        if payment_status and payment_status != "전체":
            conditions.append("COALESCE(p.payment_status, o.payment_status, '입금대기') = ?")
            parameters.append(payment_status)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT
                o.id AS order_id,
                o.order_number,
                o.ordered_at,
                o.platform,
                o.receiver_name,
                o.receiver_phone,
                COALESCE(o.total_amount, 0) AS order_amount,
                COALESCE(oi.item_summary, '-') AS item_summary,
                p.id AS payment_id,
                COALESCE(p.depositor_name, o.receiver_name, '') AS depositor_name,
                COALESCE(p.payment_amount, 0) AS payment_amount,
                COALESCE(p.payment_method, '계좌이체') AS payment_method,
                COALESCE(p.payment_status, o.payment_status, '입금대기') AS payment_status,
                p.paid_at,
                COALESCE(p.bank_message, '') AS bank_message,
                COALESCE(p.memo, '') AS memo,
                COALESCE(o.total_amount, 0) - COALESCE(p.payment_amount, 0) AS balance
            FROM orders AS o
            LEFT JOIN (
                SELECT payment.*
                FROM payments AS payment
                JOIN (
                    SELECT order_id, MAX(id) AS latest_id
                    FROM payments
                    WHERE order_id IS NOT NULL
                    GROUP BY order_id
                ) AS latest ON latest.latest_id = payment.id
            ) AS p ON p.order_id = o.id
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
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def save_payment(
        self,
        *,
        order_id: int,
        depositor_name: str,
        payment_amount: int,
        payment_method: str = "계좌이체",
        payment_status: str = "입금완료",
        paid_at: str | None = None,
        bank_message: str = "",
        memo: str = "",
    ) -> None:
        if order_id <= 0:
            raise ValueError("올바른 주문을 선택하세요.")
        if payment_amount < 0:
            raise ValueError("입금액은 0원 이상이어야 합니다.")
        if payment_status not in PAYMENT_STATUSES:
            raise ValueError("입금 상태가 올바르지 않습니다.")
        paid_at_value = self._normalize_datetime(paid_at)
        if payment_status == "입금완료" and not paid_at_value:
            paid_at_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if payment_status in {"입금대기", "입금취소"}:
            paid_at_value = None

        with self._connect() as connection:
            order = connection.execute(
                "SELECT id, customer_id, total_amount FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if order is None:
                raise ValueError("선택한 주문을 찾을 수 없습니다.")

            existing = connection.execute(
                "SELECT id FROM payments WHERE order_id = ? ORDER BY id DESC LIMIT 1", (order_id,)
            ).fetchone()
            values = (
                order_id,
                order["customer_id"],
                depositor_name.strip(),
                payment_amount,
                payment_method.strip() or "계좌이체",
                payment_status,
                paid_at_value,
                bank_message.strip(),
                memo.strip(),
            )
            if existing:
                connection.execute(
                    """
                    UPDATE payments
                    SET customer_id = ?, depositor_name = ?, payment_amount = ?,
                        payment_method = ?, payment_status = ?, paid_at = ?,
                        bank_message = ?, memo = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (values[1], values[2], values[3], values[4], values[5],
                     values[6], values[7], values[8], existing["id"]),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO payments (
                        order_id, customer_id, depositor_name, payment_amount,
                        payment_method, payment_status, paid_at, bank_message, memo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            connection.execute(
                "UPDATE orders SET payment_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (self._order_payment_status(payment_status), order_id),
            )

    def delete_payment(self, order_id: int) -> None:
        if order_id <= 0:
            raise ValueError("올바른 주문을 선택하세요.")
        with self._connect() as connection:
            connection.execute("DELETE FROM payments WHERE order_id = ?", (order_id,))
            connection.execute(
                "UPDATE orders SET payment_status = '입금대기', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (order_id,),
            )

    def get_summary(self) -> dict[str, int]:
        rows = self.get_rows()
        return {
            "total_count": len(rows),
            "waiting_count": sum(1 for row in rows if row["payment_status"] == "입금대기"),
            "partial_count": sum(1 for row in rows if row["payment_status"] == "부분입금"),
            "completed_count": sum(1 for row in rows if row["payment_status"] == "입금완료"),
            "expected_amount": sum(self._to_int(row["order_amount"]) for row in rows),
            "received_amount": sum(self._to_int(row["payment_amount"]) for row in rows),
            "balance_amount": sum(max(0, self._to_int(row["balance"])) for row in rows),
        }

    @staticmethod
    def _order_payment_status(status: str) -> str:
        return "결제완료" if status == "입금완료" else status

    @staticmethod
    def _normalize_datetime(value: str | None) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        raise ValueError("입금일시는 YYYY-MM-DD 또는 YYYY-MM-DD HH:MM 형식으로 입력하세요.")

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(str(value or 0).replace(",", "")))
        except (TypeError, ValueError):
            return 0
