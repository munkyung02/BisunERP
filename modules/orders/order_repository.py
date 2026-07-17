import sqlite3
from typing import Any

from core.database import Database


class OrderRepository:
    """주문 데이터를 SQLite에서 조회하는 클래스입니다."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def get_orders(
        self,
        search_text: str = "",
    ) -> list[dict[str, Any]]:
        search_text = search_text.strip()

        query = """
            SELECT
                o.id AS order_id,
                o.platform,
                o.order_number,
                COALESCE(o.ordered_at, '') AS ordered_at,
                COALESCE(o.receiver_name, '') AS receiver_name,
                COALESCE(oi.platform_product_name, '') AS product_name,
                COALESCE(oi.option_name, '') AS option_name,
                COALESCE(oi.quantity, 0) AS quantity,
                COALESCE(oi.mapping_status, o.mapping_status) AS mapping_status,
                o.purchase_status,
                o.shipment_status
            FROM orders AS o
            LEFT JOIN order_items AS oi
                ON oi.order_id = o.id
        """

        parameters: list[Any] = []

        if search_text:
            query += """
                WHERE
                    o.order_number LIKE ?
                    OR o.receiver_name LIKE ?
                    OR oi.platform_product_name LIKE ?
                    OR oi.option_name LIKE ?
            """

            keyword = f"%{search_text}%"
            parameters.extend(
                [
                    keyword,
                    keyword,
                    keyword,
                    keyword,
                ]
            )

        query += """
            ORDER BY
                o.id DESC,
                oi.id ASC
        """

        with self.database.connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [dict(row) for row in rows]

    def get_order_count(self) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM orders
                """
            ).fetchone()

        return int(row["count"])

    def get_status_counts(self) -> dict[str, int]:
        result = {
            "all": 0,
            "unmapped": 0,
            "purchase_waiting": 0,
            "shipping": 0,
        }

        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS all_count,
                    SUM(
                        CASE
                            WHEN mapping_status = '미매핑'
                            THEN 1
                            ELSE 0
                        END
                    ) AS unmapped_count,
                    SUM(
                        CASE
                            WHEN purchase_status = '발주대기'
                            THEN 1
                            ELSE 0
                        END
                    ) AS purchase_waiting_count,
                    SUM(
                        CASE
                            WHEN shipment_status = '배송중'
                            THEN 1
                            ELSE 0
                        END
                    ) AS shipping_count
                FROM orders
                """
            ).fetchone()

        if row is None:
            return result

        result["all"] = int(row["all_count"] or 0)
        result["unmapped"] = int(row["unmapped_count"] or 0)
        result["purchase_waiting"] = int(
            row["purchase_waiting_count"] or 0
        )
        result["shipping"] = int(row["shipping_count"] or 0)

        return result
    