import sqlite3
from pathlib import Path
from typing import Any


class CustomerRepository:
    """거래처 등록·조회·수정과 주문 요약을 처리합니다."""

    def __init__(self, db_path: str | Path = "data/bisun_erp.db") -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(customers)").fetchall()
            }
            if "is_active" not in columns:
                connection.execute(
                    "ALTER TABLE customers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_customers_business_number ON customers(business_number)"
            )
            connection.commit()

    def get_customers(
        self,
        keyword: str | None = None,
        customer_type: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                c.id, c.customer_type, c.business_name, c.customer_name,
                c.phone, c.email, c.postal_code, c.address, c.detail_address,
                c.business_number, c.representative_name, c.memo,
                c.is_active, c.created_at, c.updated_at,
                COUNT(DISTINCT o.id) AS order_count,
                COALESCE(SUM(o.total_amount), 0) AS total_order_amount,
                MAX(o.ordered_at) AS last_ordered_at
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if keyword and keyword.strip():
            value = f"%{keyword.strip()}%"
            query += """
                AND (
                    c.business_name LIKE ? OR c.customer_name LIKE ?
                    OR c.phone LIKE ? OR c.email LIKE ?
                    OR c.business_number LIKE ? OR c.representative_name LIKE ?
                    OR c.address LIKE ? OR c.detail_address LIKE ? OR c.memo LIKE ?
                )
            """
            params.extend([value] * 9)
        if customer_type and customer_type != "전체":
            query += " AND c.customer_type = ?"
            params.append(customer_type)
        if active_only:
            query += " AND c.is_active = 1"
        query += """
            GROUP BY c.id
            ORDER BY c.is_active DESC,
                     CASE WHEN c.customer_type = '사업자' THEN 0 ELSE 1 END,
                     COALESCE(c.business_name, c.customer_name, '') ASC,
                     c.id DESC
        """
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def get_customer_by_id(self, customer_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, customer_type, business_name, customer_name, phone,
                       email, postal_code, address, detail_address,
                       business_number, representative_name, memo, is_active,
                       created_at, updated_at
                FROM customers WHERE id = ?
                """,
                (customer_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_customer(self, **data: Any) -> int:
        cleaned = self._validate_and_clean(data)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO customers (
                    customer_type, business_name, customer_name, phone, email,
                    postal_code, address, detail_address, business_number,
                    representative_name, memo, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
                          CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                cleaned,
            )
            connection.commit()
            return int(cursor.lastrowid)

    def update_customer(self, customer_id: int, *, is_active: bool = True, **data: Any) -> int:
        cleaned = self._validate_and_clean(data)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE customers SET
                    customer_type = ?, business_name = ?, customer_name = ?,
                    phone = ?, email = ?, postal_code = ?, address = ?,
                    detail_address = ?, business_number = ?,
                    representative_name = ?, memo = ?, is_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*cleaned, 1 if is_active else 0, customer_id),
            )
            connection.commit()
            return cursor.rowcount

    def set_customer_active(self, customer_id: int, is_active: bool) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE customers SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (1 if is_active else 0, customer_id),
            )
            connection.commit()
            return cursor.rowcount

    def _validate_and_clean(self, data: dict[str, Any]) -> tuple[Any, ...]:
        customer_type = str(data.get("customer_type") or "소매").strip()
        if customer_type not in {"소매", "사업자"}:
            raise ValueError("거래처 유형은 소매 또는 사업자여야 합니다.")
        business_name = self._clean(data.get("business_name"))
        customer_name = self._clean(data.get("customer_name"))
        if customer_type == "사업자" and not business_name:
            raise ValueError("사업자 거래처는 상호명을 입력해야 합니다.")
        if not customer_name and not business_name:
            raise ValueError("고객명 또는 상호명 중 하나는 반드시 입력해야 합니다.")
        return (
            customer_type, business_name, customer_name,
            self._clean(data.get("phone")), self._clean(data.get("email")),
            self._clean(data.get("postal_code")), self._clean(data.get("address")),
            self._clean(data.get("detail_address")),
            self._clean(data.get("business_number")),
            self._clean(data.get("representative_name")), self._clean(data.get("memo")),
        )

    @staticmethod
    def _clean(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
