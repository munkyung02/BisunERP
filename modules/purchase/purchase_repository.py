import sqlite3
from typing import Any

from core.database import Database


class PurchaseRepository:
    """발주 데이터를 조회하고 저장하는 저장소입니다."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def create_pending_purchases(self) -> dict[str, int]:
        """
        주문 상품을 purchase_orders 테이블에 발주대기로 생성합니다.

        이미 생성된 order_item_id는 UNIQUE 제약조건에 의해
        중복 저장되지 않습니다.
        """

        created_count = 0
        duplicate_count = 0
        failed_count = 0

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    o.id AS order_id,
                    o.order_number,
                    o.receiver_name,
                    o.receiver_phone,
                    o.postal_code,
                    o.address,
                    o.detail_address,
                    o.delivery_message,

                    oi.id AS order_item_id,
                    oi.supplier_id,
                    oi.platform_product_name,
                    oi.option_name,
                    oi.quantity,

                    s.supplier_name

                FROM order_items AS oi

                INNER JOIN orders AS o
                    ON o.id = oi.order_id

                LEFT JOIN suppliers AS s
                    ON s.id = oi.supplier_id

                ORDER BY
                    o.id ASC,
                    oi.id ASC
                """
            ).fetchall()

            for row in rows:
                full_address = self._build_full_address(
                    row["address"],
                    row["detail_address"],
                )

                try:
                    connection.execute(
                        """
                        INSERT INTO purchase_orders (
                            supplier_id,
                            order_id,
                            order_item_id,
                            supplier_name,
                            order_number,
                            product_name,
                            option_name,
                            quantity,
                            receiver_name,
                            receiver_phone,
                            postal_code,
                            address,
                            delivery_message,
                            purchase_status
                        )
                        VALUES (
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            '발주대기'
                        )
                        """,
                        (
                            row["supplier_id"],
                            row["order_id"],
                            row["order_item_id"],
                            row["supplier_name"] or "미지정",
                            row["order_number"],
                            row["platform_product_name"],
                            row["option_name"],
                            row["quantity"],
                            row["receiver_name"],
                            row["receiver_phone"],
                            row["postal_code"],
                            full_address,
                            row["delivery_message"],
                        ),
                    )

                    created_count += 1

                except sqlite3.IntegrityError:
                    duplicate_count += 1

                except sqlite3.Error:
                    failed_count += 1

            connection.commit()

        return {
            "total_items": len(rows),
            "created_count": created_count,
            "duplicate_count": duplicate_count,
            "failed_count": failed_count,
        }

    def get_purchase_orders(
        self,
        status: str | None = None,
        supplier_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """발주 목록을 조회합니다."""

        query = """
            SELECT
                id,
                supplier_id,
                order_id,
                order_item_id,
                supplier_name,
                order_number,
                product_name,
                option_name,
                quantity,
                receiver_name,
                receiver_phone,
                postal_code,
                address,
                delivery_message,
                purchase_status,
                purchase_file,
                purchased_at,
                created_at
            FROM purchase_orders
            WHERE 1 = 1
        """

        parameters: list[Any] = []

        if status:
            query += """
                AND purchase_status = ?
            """
            parameters.append(status)

        if supplier_name:
            query += """
                AND supplier_name = ?
            """
            parameters.append(supplier_name)

        query += """
            ORDER BY
                supplier_name ASC,
                created_at DESC,
                id DESC
        """

        with self.database.connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [dict(row) for row in rows]

    def get_status_counts(self) -> dict[str, int]:
        """발주 상태별 건수를 조회합니다."""

        result = {
            "전체": 0,
            "발주대기": 0,
            "발주완료": 0,
            "입고완료": 0,
        }

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    purchase_status,
                    COUNT(*) AS count
                FROM purchase_orders
                GROUP BY purchase_status
                """
            ).fetchall()

        for row in rows:
            status = row["purchase_status"]
            count = row["count"]

            result["전체"] += count
            result[status] = count

        return result

    def update_purchase_status(
        self,
        purchase_ids: list[int],
        status: str,
    ) -> int:
        """선택한 발주 건의 상태를 변경합니다."""

        allowed_statuses = {
            "발주대기",
            "발주완료",
            "입고완료",
        }

        if status not in allowed_statuses:
            raise ValueError(
                f"허용되지 않은 발주 상태입니다: {status}"
            )

        if not purchase_ids:
            return 0

        placeholders = ",".join(
            "?"
            for _ in purchase_ids
        )

        parameters: list[Any] = [
            status,
            *purchase_ids,
        ]

        with self.database.connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE purchase_orders
                SET
                    purchase_status = ?,
                    purchased_at = CASE
                        WHEN ? = '발주완료'
                        THEN CURRENT_TIMESTAMP
                        ELSE purchased_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """,
                [
                    status,
                    status,
                    *purchase_ids,
                ],
            )

            connection.commit()

        return cursor.rowcount

    @staticmethod
    def _build_full_address(
        address: str | None,
        detail_address: str | None,
    ) -> str:
        """기본 주소와 상세 주소를 하나로 합칩니다."""

        address_parts = [
            str(value).strip()
            for value in (
                address,
                detail_address,
            )
            if value and str(value).strip()
        ]

        return " ".join(address_parts)