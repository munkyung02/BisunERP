import sqlite3
from typing import Any, Mapping

from core.database import Database


class OrderRepository:
    """주문 데이터를 SQLite에 저장하고 조회합니다."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def exists_order(
        self,
        platform: str,
        order_number: str,
    ) -> bool:
        """동일한 판매채널과 주문번호가 이미 저장됐는지 확인합니다."""

        platform = str(platform).strip()
        order_number = str(order_number).strip()

        if not platform or not order_number:
            return False

        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM orders
                WHERE platform = ?
                  AND order_number = ?
                LIMIT 1
                """,
                (platform, order_number),
            ).fetchone()

        return row is not None

    def save_order(
        self,
        order: Mapping[str, Any],
    ) -> tuple[int, bool]:
        """
        주문 기본정보를 저장합니다.

        반환값:
            (DB 주문 ID, 신규 저장 여부)

        예:
            (15, True)  -> 새 주문 저장
            (15, False) -> 기존 주문이라 저장하지 않음
        """

        platform = str(order.get("platform", "")).strip()
        order_number = str(order.get("order_number", "")).strip()

        if not platform:
            raise ValueError("판매채널(platform)이 없습니다.")

        if not order_number:
            raise ValueError("주문번호(order_number)가 없습니다.")

        with self.database.connect() as connection:
            existing_row = connection.execute(
                """
                SELECT id
                FROM orders
                WHERE platform = ?
                  AND order_number = ?
                LIMIT 1
                """,
                (platform, order_number),
            ).fetchone()

            if existing_row is not None:
                return int(existing_row["id"]), False

            cursor = connection.execute(
                """
                INSERT INTO orders (
                    platform,
                    order_number,
                    ordered_at,
                    customer_id,
                    receiver_name,
                    receiver_phone,
                    postal_code,
                    address,
                    detail_address,
                    delivery_message,
                    order_status,
                    payment_status,
                    mapping_status,
                    purchase_status,
                    shipment_status,
                    total_amount,
                    source_file
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    platform,
                    order_number,
                    self._clean_text(order.get("ordered_at")),
                    order.get("customer_id"),
                    self._clean_text(order.get("receiver_name")),
                    self._clean_text(order.get("receiver_phone")),
                    self._clean_text(order.get("postal_code")),
                    self._clean_text(order.get("address")),
                    self._clean_text(order.get("detail_address")),
                    self._clean_text(order.get("delivery_message")),
                    self._clean_text(
                        order.get("order_status")
                    ) or "주문접수",
                    self._clean_text(
                        order.get("payment_status")
                    ) or "결제완료",
                    self._clean_text(
                        order.get("mapping_status")
                    ) or "미매핑",
                    self._clean_text(
                        order.get("purchase_status")
                    ) or "발주대기",
                    self._clean_text(
                        order.get("shipment_status")
                    ) or "배송대기",
                    self._to_integer(order.get("total_amount")),
                    self._clean_text(order.get("source_file")),
                ),
            )

            connection.commit()

            if cursor.lastrowid is None:
                raise RuntimeError("주문 저장 후 DB ID를 확인하지 못했습니다.")

            return int(cursor.lastrowid), True

    def save_order_item(
        self,
        order_id: int,
        item: Mapping[str, Any],
    ) -> int:
        """주문에 포함된 상품 한 건을 저장합니다."""

        product_name = self._clean_text(
            item.get("platform_product_name")
        )

        if not product_name:
            raise ValueError(
                "주문상품명(platform_product_name)이 없습니다."
            )

        quantity = self._to_integer(
            item.get("quantity"),
            default=1,
        )

        if quantity < 1:
            quantity = 1

        unit_price = self._to_integer(item.get("unit_price"))

        total_price = self._to_integer(
            item.get("total_price"),
            default=unit_price * quantity,
        )

        with self.database.connect() as connection:
            order_exists = connection.execute(
                """
                SELECT 1
                FROM orders
                WHERE id = ?
                LIMIT 1
                """,
                (order_id,),
            ).fetchone()

            if order_exists is None:
                raise ValueError(
                    f"DB에서 주문 ID {order_id}을 찾을 수 없습니다."
                )

            cursor = connection.execute(
                """
                INSERT INTO order_items (
                    order_id,
                    product_id,
                    platform_product_name,
                    option_name,
                    quantity,
                    unit_price,
                    total_price,
                    supplier_id,
                    purchase_round,
                    mapping_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    item.get("product_id"),
                    product_name,
                    self._clean_text(item.get("option_name")),
                    quantity,
                    unit_price,
                    total_price,
                    item.get("supplier_id"),
                    self._clean_text(item.get("purchase_round")),
                    self._clean_text(
                        item.get("mapping_status")
                    ) or "미매핑",
                ),
            )

            connection.commit()

            if cursor.lastrowid is None:
                raise RuntimeError(
                    "주문상품 저장 후 DB ID를 확인하지 못했습니다."
                )

            return int(cursor.lastrowid)

    def get_orders(
        self,
        search_text: str = "",
    ) -> list[dict[str, Any]]:
        """주문관리 화면에 표시할 주문 목록을 조회합니다."""

        search_text = search_text.strip()

        query = """
            SELECT
                o.id AS order_id,
                o.platform,
                o.order_number,
                COALESCE(o.ordered_at, '') AS ordered_at,
                COALESCE(o.receiver_name, '') AS receiver_name,
                COALESCE(
                    oi.platform_product_name,
                    ''
                ) AS product_name,
                COALESCE(oi.option_name, '') AS option_name,
                COALESCE(oi.quantity, 0) AS quantity,
                COALESCE(
                    oi.mapping_status,
                    o.mapping_status
                ) AS mapping_status,
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
        """DB에 저장된 전체 주문 수를 반환합니다."""

        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM orders
                """
            ).fetchone()

        return int(row["count"] or 0)

    def get_status_counts(self) -> dict[str, int]:
        """주문 상태별 집계 데이터를 반환합니다."""

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

    @staticmethod
    def _clean_text(value: Any) -> str:
        """None이나 NaN 값을 빈 문자열로 정리합니다."""

        if value is None:
            return ""

        text = str(value).strip()

        if text.lower() in {"nan", "none", "nat"}:
            return ""

        return text

    @staticmethod
    def _to_integer(
        value: Any,
        default: int = 0,
    ) -> int:
        """문자열이나 실수 형태의 숫자를 정수로 변환합니다."""

        if value is None:
            return default

        try:
            cleaned_value = str(value).replace(",", "").strip()

            if not cleaned_value:
                return default

            return int(float(cleaned_value))

        except (TypeError, ValueError):
            return default