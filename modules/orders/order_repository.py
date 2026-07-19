import re
import sqlite3
import unicodedata

from pathlib import Path
from typing import Any, Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class OrderRepository:
    """비선상회 ERP 주문 및 주문상품 DB 처리 클래스입니다."""

    VALID_ORDER_STATUSES = {
        "주문접수",
        "주문확인",
        "처리중",
        "취소",
        "완료",
    }

    VALID_PAYMENT_STATUSES = {
        "입금대기",
        "결제대기",
        "결제완료",
        "입금완료",
        "부분입금",
        "환불",
    }

    VALID_MAPPING_STATUSES = {
        "미매핑",
        "자동매핑",
        "수동매핑",
        "매핑완료",
        "매핑오류",
    }

    VALID_PURCHASE_STATUSES = {
        "발주대기",
        "발주준비",
        "발주완료",
        "발주취소",
    }

    VALID_SHIPMENT_STATUSES = {
        "배송대기",
        "배송준비",
        "배송중",
        "배송완료",
        "배송취소",
    }

    def __init__(
        self,
        database_path: str | Path | None = None,
    ) -> None:
        self.database_path = Path(
            database_path or DATABASE_PATH
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =========================================================
    # DB 연결
    # =========================================================

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path
        )

        connection.row_factory = sqlite3.Row
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        return connection

    # =========================================================
    # 주문 목록 조회
    # =========================================================

    def get_orders(
        self,
        keyword: str | None = None,
        platform: str | None = None,
        order_status: str | None = None,
        payment_status: str | None = None,
        mapping_status: str | None = None,
        purchase_status: str | None = None,
        shipment_status: str | None = None,
        ordered_from: str | None = None,
        ordered_to: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """주문 목록과 주문상품 요약을 조회합니다."""

        conditions: list[str] = []
        parameters: list[Any] = []

        if keyword:
            cleaned_keyword = keyword.strip()

            if cleaned_keyword:
                search_value = (
                    f"%{cleaned_keyword}%"
                )

                conditions.append(
                    """
                    (
                        o.order_number LIKE ?
                        OR o.receiver_name LIKE ?
                        OR o.receiver_phone LIKE ?
                        OR o.address LIKE ?
                        OR EXISTS (
                            SELECT 1
                            FROM order_items AS search_item
                            WHERE search_item.order_id = o.id
                              AND (
                                  search_item.platform_product_name LIKE ?
                                  OR search_item.option_name LIKE ?
                              )
                        )
                    )
                    """
                )

                parameters.extend(
                    [
                        search_value,
                        search_value,
                        search_value,
                        search_value,
                        search_value,
                        search_value,
                    ]
                )

        if platform:
            conditions.append(
                "o.platform = ?"
            )
            parameters.append(platform.strip())

        if order_status:
            conditions.append(
                "o.order_status = ?"
            )
            parameters.append(order_status.strip())

        if payment_status:
            conditions.append(
                "o.payment_status = ?"
            )
            parameters.append(
                payment_status.strip()
            )

        if mapping_status:
            conditions.append(
                "o.mapping_status = ?"
            )
            parameters.append(
                mapping_status.strip()
            )

        if purchase_status:
            conditions.append(
                "o.purchase_status = ?"
            )
            parameters.append(
                purchase_status.strip()
            )

        if shipment_status:
            conditions.append(
                "o.shipment_status = ?"
            )
            parameters.append(
                shipment_status.strip()
            )

        if ordered_from:
            conditions.append(
                "DATE(o.ordered_at) >= DATE(?)"
            )
            parameters.append(ordered_from)

        if ordered_to:
            conditions.append(
                "DATE(o.ordered_at) <= DATE(?)"
            )
            parameters.append(ordered_to)

        where_clause = ""

        if conditions:
            where_clause = (
                "WHERE "
                + " AND ".join(conditions)
            )

        limit_clause = ""

        if limit is not None:
            safe_limit = self._validate_limit(
                limit
            )
            limit_clause = f"LIMIT {safe_limit}"

        query = f"""
            SELECT
                o.id,
                o.platform,
                o.order_number,
                o.ordered_at,
                o.customer_id,
                o.receiver_name,
                o.receiver_phone,
                o.postal_code,
                o.address,
                o.detail_address,
                o.delivery_message,
                o.order_status,
                o.payment_status,
                o.mapping_status,
                o.purchase_status,
                o.shipment_status,
                o.total_amount,
                o.source_file,
                o.created_at,
                o.updated_at,

                COUNT(oi.id) AS item_count,

                COALESCE(
                    SUM(oi.quantity),
                    0
                ) AS total_quantity,

                GROUP_CONCAT(
                    CASE
                        WHEN oi.option_name IS NOT NULL
                             AND TRIM(oi.option_name) != ''
                        THEN
                            oi.platform_product_name
                            || ' / '
                            || oi.option_name
                        ELSE
                            oi.platform_product_name
                    END,
                    ' | '
                ) AS item_summary

            FROM orders AS o

            LEFT JOIN order_items AS oi
                ON oi.order_id = o.id

            {where_clause}

            GROUP BY o.id

            ORDER BY
                CASE
                    WHEN o.ordered_at IS NULL
                    THEN 1
                    ELSE 0
                END,
                o.ordered_at DESC,
                o.id DESC

            {limit_clause}
        """

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # =========================================================
    # 주문상품 단위 목록 조회
    # =========================================================

    def get_order_items(
        self,
        order_id: int | None = None,
        keyword: str | None = None,
        mapping_status: str | None = None,
        unmapped_only: bool = False,
    ) -> list[dict[str, Any]]:
        """주문상품을 주문, 상품, 공급처 정보와 함께 조회합니다."""

        conditions: list[str] = []
        parameters: list[Any] = []

        if order_id is not None:
            valid_order_id = self._validate_id(
                order_id,
                "주문 ID",
            )

            conditions.append(
                "oi.order_id = ?"
            )
            parameters.append(valid_order_id)

        if keyword:
            cleaned_keyword = keyword.strip()

            if cleaned_keyword:
                search_value = (
                    f"%{cleaned_keyword}%"
                )

                conditions.append(
                    """
                    (
                        o.order_number LIKE ?
                        OR o.receiver_name LIKE ?
                        OR oi.platform_product_name LIKE ?
                        OR oi.option_name LIKE ?
                        OR p.product_name LIKE ?
                        OR s.supplier_name LIKE ?
                    )
                    """
                )

                parameters.extend(
                    [
                        search_value,
                        search_value,
                        search_value,
                        search_value,
                        search_value,
                        search_value,
                    ]
                )

        if mapping_status:
            conditions.append(
                "oi.mapping_status = ?"
            )
            parameters.append(
                mapping_status.strip()
            )

        if unmapped_only:
            conditions.append(
                """
                (
                    oi.product_id IS NULL
                    OR oi.mapping_status = '미매핑'
                )
                """
            )

        where_clause = ""

        if conditions:
            where_clause = (
                "WHERE "
                + " AND ".join(conditions)
            )

        query = f"""
            SELECT
                oi.id,
                oi.order_id,
                oi.product_id,
                oi.platform_product_name,
                oi.option_name,
                oi.quantity,
                oi.unit_price,
                oi.total_price,
                oi.supplier_id,
                oi.purchase_round,
                oi.mapping_status,
                oi.created_at,
                oi.updated_at,

                o.platform,
                o.order_number,
                o.ordered_at,
                o.receiver_name,
                o.receiver_phone,
                o.postal_code,
                o.address,
                o.detail_address,
                o.delivery_message,
                o.order_status,
                o.payment_status,
                o.purchase_status,
                o.shipment_status,

                p.product_code,
                p.product_name,
                p.supplier_product_name,
                p.purchase_price,
                p.sale_price,

                s.supplier_code,
                s.supplier_name

            FROM order_items AS oi

            INNER JOIN orders AS o
                ON o.id = oi.order_id

            LEFT JOIN products AS p
                ON p.id = oi.product_id

            LEFT JOIN suppliers AS s
                ON s.id = oi.supplier_id

            {where_clause}

            ORDER BY
                CASE
                    WHEN o.ordered_at IS NULL
                    THEN 1
                    ELSE 0
                END,
                o.ordered_at DESC,
                o.id DESC,
                oi.id ASC
        """

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # =========================================================
    # 주문 상세 조회
    # =========================================================

    def get_order_by_id(
        self,
        order_id: int,
    ) -> dict[str, Any] | None:
        """주문 한 건과 주문상품 목록을 조회합니다."""

        valid_order_id = self._validate_id(
            order_id,
            "주문 ID",
        )

        with self._connect() as connection:
            order_row = connection.execute(
                """
                SELECT
                    o.*
                FROM orders AS o
                WHERE o.id = ?
                """,
                (valid_order_id,),
            ).fetchone()

            if order_row is None:
                return None

            item_rows = connection.execute(
                """
                SELECT
                    oi.*,
                    p.product_code,
                    p.product_name,
                    p.supplier_product_name,
                    s.supplier_code,
                    s.supplier_name

                FROM order_items AS oi

                LEFT JOIN products AS p
                    ON p.id = oi.product_id

                LEFT JOIN suppliers AS s
                    ON s.id = oi.supplier_id

                WHERE oi.order_id = ?

                ORDER BY oi.id ASC
                """,
                (valid_order_id,),
            ).fetchall()

        result = dict(order_row)
        result["items"] = [
            dict(item)
            for item in item_rows
        ]

        return result

    def get_order_by_number(
        self,
        platform: str,
        order_number: str,
    ) -> dict[str, Any] | None:
        """플랫폼과 주문번호로 주문 한 건을 조회합니다."""

        valid_platform = self._required_text(
            platform,
            "플랫폼",
        )
        valid_order_number = self._required_text(
            order_number,
            "주문번호",
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM orders
                WHERE platform = ?
                  AND order_number = ?
                """,
                (
                    valid_platform,
                    valid_order_number,
                ),
            ).fetchone()

        if row is None:
            return None

        return dict(row)

    # =========================================================
    # 중복 확인
    # =========================================================

    def order_exists(
        self,
        platform: str,
        order_number: str,
    ) -> bool:
        """동일 플랫폼의 주문번호가 이미 존재하는지 확인합니다."""

        valid_platform = self._required_text(
            platform,
            "플랫폼",
        )
        valid_order_number = self._required_text(
            order_number,
            "주문번호",
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM orders
                WHERE platform = ?
                  AND order_number = ?
                LIMIT 1
                """,
                (
                    valid_platform,
                    valid_order_number,
                ),
            ).fetchone()

        return row is not None

    # =========================================================
    # 주문 저장
    # =========================================================

    def create_order(
        self,
        *,
        platform: str,
        order_number: str,
        items: Sequence[dict[str, Any]],
        ordered_at: str | None = None,
        customer_id: int | None = None,
        receiver_name: str | None = None,
        receiver_phone: str | None = None,
        postal_code: str | None = None,
        address: str | None = None,
        detail_address: str | None = None,
        delivery_message: str | None = None,
        order_status: str = "주문접수",
        payment_status: str = "결제완료",
        mapping_status: str = "미매핑",
        purchase_status: str = "발주대기",
        shipment_status: str = "배송대기",
        total_amount: int | None = None,
        source_file: str | None = None,
        skip_duplicate: bool = True,
    ) -> dict[str, Any]:
        """주문과 주문상품을 하나의 트랜잭션으로 저장합니다."""

        valid_platform = self._required_text(
            platform,
            "플랫폼",
        )
        valid_order_number = self._required_text(
            order_number,
            "주문번호",
        )

        valid_items = self._validate_items(
            items
        )

        valid_customer_id = self._optional_id(
            customer_id,
            "거래처 ID",
        )

        valid_order_status = self._validate_status(
            order_status,
            self.VALID_ORDER_STATUSES,
            "주문 상태",
        )

        valid_payment_status = self._validate_status(
            payment_status,
            self.VALID_PAYMENT_STATUSES,
            "결제 상태",
        )

        valid_mapping_status = self._validate_status(
            mapping_status,
            self.VALID_MAPPING_STATUSES,
            "매핑 상태",
        )

        valid_purchase_status = self._validate_status(
            purchase_status,
            self.VALID_PURCHASE_STATUSES,
            "발주 상태",
        )

        valid_shipment_status = self._validate_status(
            shipment_status,
            self.VALID_SHIPMENT_STATUSES,
            "배송 상태",
        )

        calculated_total = sum(
            item["total_price"]
            for item in valid_items
        )

        if total_amount is None:
            valid_total_amount = (
                calculated_total
            )
        else:
            valid_total_amount = (
                self._non_negative_int(
                    total_amount,
                    "총 결제금액",
                )
            )

        with self._connect() as connection:
            try:
                existing_row = connection.execute(
                    """
                    SELECT id
                    FROM orders
                    WHERE platform = ?
                      AND order_number = ?
                    """,
                    (
                        valid_platform,
                        valid_order_number,
                    ),
                ).fetchone()

                if existing_row is not None:
                    existing_order_id = int(
                        existing_row["id"]
                    )

                    if skip_duplicate:
                        return {
                            "created": False,
                            "duplicate": True,
                            "order_id": (
                                existing_order_id
                            ),
                            "item_count": 0,
                        }

                    raise ValueError(
                        "이미 등록된 주문입니다. "
                        f"[{valid_platform}] "
                        f"{valid_order_number}"
                    )

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
                        source_file,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """,
                    (
                        valid_platform,
                        valid_order_number,
                        self._optional_text(
                            ordered_at
                        ),
                        valid_customer_id,
                        self._optional_text(
                            receiver_name
                        ),
                        self._optional_text(
                            receiver_phone
                        ),
                        self._optional_text(
                            postal_code
                        ),
                        self._optional_text(
                            address
                        ),
                        self._optional_text(
                            detail_address
                        ),
                        self._optional_text(
                            delivery_message
                        ),
                        valid_order_status,
                        valid_payment_status,
                        valid_mapping_status,
                        valid_purchase_status,
                        valid_shipment_status,
                        valid_total_amount,
                        self._optional_text(
                            source_file
                        ),
                    ),
                )

                order_id = int(
                    cursor.lastrowid
                )

                for item in valid_items:
                    connection.execute(
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
                            mapping_status,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP
                        )
                        """,
                        (
                            order_id,
                            item["product_id"],
                            item[
                                "platform_product_name"
                            ],
                            item["option_name"],
                            item["quantity"],
                            item["unit_price"],
                            item["total_price"],
                            item["supplier_id"],
                            item["purchase_round"],
                            item["mapping_status"],
                        ),
                    )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        return {
            "created": True,
            "duplicate": False,
            "order_id": order_id,
            "item_count": len(valid_items),
        }

    # =========================================================
    # 여러 주문 일괄 저장
    # =========================================================

    def create_orders_bulk(
        self,
        orders: Iterable[dict[str, Any]],
        *,
        skip_duplicates: bool = True,
    ) -> dict[str, Any]:
        """여러 주문을 순차 저장하고 처리 결과를 반환합니다."""

        created_count = 0
        duplicate_count = 0
        failed_count = 0
        created_order_ids: list[int] = []
        errors: list[dict[str, Any]] = []

        for index, order_data in enumerate(
            orders,
            start=1,
        ):
            try:
                if not isinstance(
                    order_data,
                    dict,
                ):
                    raise ValueError(
                        "주문 데이터는 "
                        "dict 형식이어야 합니다."
                    )

                result = self.create_order(
                    platform=order_data.get(
                        "platform"
                    ),
                    order_number=order_data.get(
                        "order_number"
                    ),
                    ordered_at=order_data.get(
                        "ordered_at"
                    ),
                    customer_id=order_data.get(
                        "customer_id"
                    ),
                    receiver_name=order_data.get(
                        "receiver_name"
                    ),
                    receiver_phone=order_data.get(
                        "receiver_phone"
                    ),
                    postal_code=order_data.get(
                        "postal_code"
                    ),
                    address=order_data.get(
                        "address"
                    ),
                    detail_address=order_data.get(
                        "detail_address"
                    ),
                    delivery_message=order_data.get(
                        "delivery_message"
                    ),
                    order_status=order_data.get(
                        "order_status",
                        "주문접수",
                    ),
                    payment_status=order_data.get(
                        "payment_status",
                        "결제완료",
                    ),
                    mapping_status=order_data.get(
                        "mapping_status",
                        "미매핑",
                    ),
                    purchase_status=order_data.get(
                        "purchase_status",
                        "발주대기",
                    ),
                    shipment_status=order_data.get(
                        "shipment_status",
                        "배송대기",
                    ),
                    total_amount=order_data.get(
                        "total_amount"
                    ),
                    source_file=order_data.get(
                        "source_file"
                    ),
                    items=order_data.get(
                        "items",
                        [],
                    ),
                    skip_duplicate=(
                        skip_duplicates
                    ),
                )

                if result["created"]:
                    created_count += 1
                    created_order_ids.append(
                        int(result["order_id"])
                    )

                elif result["duplicate"]:
                    duplicate_count += 1

            except Exception as error:
                failed_count += 1

                errors.append(
                    {
                        "row": index,
                        "order_number": (
                            order_data.get(
                                "order_number"
                            )
                            if isinstance(
                                order_data,
                                dict,
                            )
                            else None
                        ),
                        "error": str(error),
                    }
                )

        return {
            "total_count": (
                created_count
                + duplicate_count
                + failed_count
            ),
            "created_count": created_count,
            "duplicate_count": duplicate_count,
            "failed_count": failed_count,
            "created_order_ids": (
                created_order_ids
            ),
            "errors": errors,
        }

    # =========================================================
    # 주문상품 자동 매핑
    # =========================================================

    # =========================================================
    # 상품명 정규화
    # =========================================================

    @staticmethod
    def _normalize_product_text(
        value: Any,
    ) -> str:
        """
        상품 비교에 사용할 표준 문자열을 만듭니다.

        예:
        해담_생참치회 500g
        생참치회500G
        해담 생참치회 500 g

        모두 비슷한 형태로 정리합니다.
        """

        if value is None:
            return ""

        text = unicodedata.normalize(
            "NFKC",
            str(value),
        )

        text = text.lower().strip()

        # 괄호 안의 상세 설명 제거
        text = re.sub(
            r"\([^)]*\)",
            " ",
            text,
        )
        text = re.sub(
            r"\[[^\]]*\]",
            " ",
            text,
        )
        text = re.sub(
            r"\{[^}]*\}",
            " ",
            text,
        )

        # 자주 붙는 공급처 및 브랜드 접두어 제거
        supplier_prefixes = [
            "해담",
            "외현농원",
            "주영씨푸드",
            "비선상회",
        ]

        for prefix in supplier_prefixes:
            text = re.sub(
                rf"^{re.escape(prefix)}[\s_\-]*",
                "",
                text,
            )

        # 상품 개수 관련 표현 제거
        text = re.sub(
            r"\b\d+\s*(개|팩|봉|박스|세트)\b",
            " ",
            text,
        )

        # 인분 표현 제거
        text = re.sub(
            r"\b\d+\s*[~\-]\s*\d+\s*인분\b",
            " ",
            text,
        )
        text = re.sub(
            r"\b\d+\s*인분\b",
            " ",
            text,
        )

        # 과수 표현 제거: 7~8과
        text = re.sub(
            r"\b\d+\s*[~\-]\s*\d+\s*과\b",
            " ",
            text,
        )

        # 비교에 불필요한 기호 제거
        text = re.sub(
            r"[/_,.\-+]",
            " ",
            text,
        )

        # 단위 앞뒤 공백 정리
        text = re.sub(
            r"(\d+)\s*(kg|g|ml|l)\b",
            r"\1\2",
            text,
        )

        # 모든 공백 제거
        text = re.sub(
            r"\s+",
            "",
            text,
        )

        return text

    @classmethod
    def _build_product_match_keys(
        cls,
        product_name: Any,
        option_name: Any = None,
    ) -> set[str]:
        """
        하나의 상품에서 비교 가능한 여러 키를 만듭니다.
        """

        product_text = cls._normalize_product_text(
            product_name
        )

        option_text = cls._normalize_product_text(
            option_name
        )

        keys: set[str] = set()

        if product_text:
            keys.add(product_text)

        if product_text and option_text:
            keys.add(
                product_text + option_text
            )

        return keys

    def auto_map_order_items(
        self,
        order_id: int | None = None,
    ) -> dict[str, int]:
        """
        판매처 상품명과 ERP 상품명을 정규화하여 자동 매핑합니다.

        매칭 대상:
        - 판매처 상품명
        - 내부 상품명
        - 공급처 상품명
        - 옵션명을 포함한 조합
        """

        parameters: list[Any] = []
        order_condition = ""

        if order_id is not None:
            valid_order_id = self._validate_id(
                order_id,
                "주문 ID",
            )

            order_condition = (
                "AND oi.order_id = ?"
            )
            parameters.append(valid_order_id)

        with self._connect() as connection:
            target_rows = connection.execute(
                f"""
                SELECT
                    oi.id,
                    oi.order_id,
                    oi.platform_product_name,
                    oi.option_name,
                    o.platform

                FROM order_items AS oi

                INNER JOIN orders AS o
                    ON o.id = oi.order_id

                WHERE (
                    oi.product_id IS NULL
                    OR oi.mapping_status = '미매핑'
                )

                {order_condition}

                ORDER BY oi.id ASC
                """,
                parameters,
            ).fetchall()

            product_rows = connection.execute(
                """
                SELECT
                    p.id,
                    p.platform,
                    p.platform_product_name,
                    p.product_name,
                    p.option_name,
                    p.supplier_product_name,
                    p.supplier_id,
                    p.purchase_round

                FROM products AS p

                WHERE p.is_active = 1

                ORDER BY p.id ASC
                """
            ).fetchall()

            mapped_count = 0
            unmatched_count = 0
            ambiguous_count = 0

            affected_order_ids: set[int] = set()

            try:
                for row in target_rows:
                    order_keys = (
                        self._build_product_match_keys(
                            row[
                                "platform_product_name"
                            ],
                            row["option_name"],
                        )
                    )

                    candidates = []

                    for product in product_rows:
                        product_platform = (
                            str(
                                product["platform"]
                                or ""
                            ).strip()
                        )

                        order_platform = str(
                            row["platform"]
                            or ""
                        ).strip()

                        # 상품에 플랫폼이 지정돼 있다면
                        # 주문 플랫폼과 같아야 함
                        if (
                            product_platform
                            and product_platform
                            != order_platform
                        ):
                            continue

                        product_keys: set[str] = set()

                        product_keys.update(
                            self._build_product_match_keys(
                                product[
                                    "platform_product_name"
                                ],
                                product[
                                    "option_name"
                                ],
                            )
                        )

                        product_keys.update(
                            self._build_product_match_keys(
                                product[
                                    "product_name"
                                ],
                                product[
                                    "option_name"
                                ],
                            )
                        )

                        product_keys.update(
                            self._build_product_match_keys(
                                product[
                                    "supplier_product_name"
                                ],
                                product[
                                    "option_name"
                                ],
                            )
                        )

                        if order_keys & product_keys:
                            candidates.append(
                                product
                            )

                    if len(candidates) == 1:
                        product = candidates[0]

                        connection.execute(
                            """
                            UPDATE order_items
                            SET
                                product_id = ?,
                                supplier_id = ?,
                                purchase_round = ?,
                                mapping_status = '자동매핑',
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """,
                            (
                                product["id"],
                                product["supplier_id"],
                                product[
                                    "purchase_round"
                                ],
                                row["id"],
                            ),
                        )

                        mapped_count += 1

                        affected_order_ids.add(
                            int(row["order_id"])
                        )

                    elif len(candidates) > 1:
                        ambiguous_count += 1

                    else:
                        unmatched_count += 1

                for affected_order_id in (
                    affected_order_ids
                ):
                    self._refresh_order_mapping_status(
                        connection,
                        affected_order_id,
                    )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        return {
            "target_count": len(
                target_rows
            ),
            "mapped_count": mapped_count,
            "unmatched_count": (
                unmatched_count
            ),
            "ambiguous_count": (
                ambiguous_count
            ),
        }

    # =========================================================
    # 주문상품 수동 매핑
    # =========================================================

    def map_order_item(
        self,
        order_item_id: int,
        product_id: int,
        mapping_status: str = "수동매핑",
    ) -> int:
        """주문상품을 등록 상품에 수동 연결합니다."""

        valid_order_item_id = (
            self._validate_id(
                order_item_id,
                "주문상품 ID",
            )
        )

        valid_product_id = self._validate_id(
            product_id,
            "상품 ID",
        )

        valid_mapping_status = (
            self._validate_status(
                mapping_status,
                self.VALID_MAPPING_STATUSES,
                "매핑 상태",
            )
        )

        with self._connect() as connection:
            product_row = connection.execute(
                """
                SELECT
                    id,
                    supplier_id,
                    purchase_round
                FROM products
                WHERE id = ?
                  AND is_active = 1
                """,
                (valid_product_id,),
            ).fetchone()

            if product_row is None:
                raise ValueError(
                    "사용 가능한 상품을 "
                    "찾을 수 없습니다."
                )

            order_item_row = connection.execute(
                """
                SELECT order_id
                FROM order_items
                WHERE id = ?
                """,
                (valid_order_item_id,),
            ).fetchone()

            if order_item_row is None:
                raise ValueError(
                    "주문상품을 찾을 수 없습니다."
                )

            cursor = connection.execute(
                """
                UPDATE order_items
                SET
                    product_id = ?,
                    supplier_id = ?,
                    purchase_round = ?,
                    mapping_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    valid_product_id,
                    product_row["supplier_id"],
                    product_row["purchase_round"],
                    valid_mapping_status,
                    valid_order_item_id,
                ),
            )

            self._refresh_order_mapping_status(
                connection,
                int(order_item_row["order_id"]),
            )

            connection.commit()

            return cursor.rowcount

    def unmap_order_item(
        self,
        order_item_id: int,
    ) -> int:
        """주문상품의 상품 및 공급처 연결을 해제합니다."""

        valid_order_item_id = (
            self._validate_id(
                order_item_id,
                "주문상품 ID",
            )
        )

        with self._connect() as connection:
            order_item_row = connection.execute(
                """
                SELECT order_id
                FROM order_items
                WHERE id = ?
                """,
                (valid_order_item_id,),
            ).fetchone()

            if order_item_row is None:
                return 0

            cursor = connection.execute(
                """
                UPDATE order_items
                SET
                    product_id = NULL,
                    supplier_id = NULL,
                    purchase_round = NULL,
                    mapping_status = '미매핑',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (valid_order_item_id,),
            )

            self._refresh_order_mapping_status(
                connection,
                int(order_item_row["order_id"]),
            )

            connection.commit()

            return cursor.rowcount

    # =========================================================
    # 주문 상태 변경
    # =========================================================

    def update_order_statuses(
        self,
        order_id: int,
        *,
        order_status: str | None = None,
        payment_status: str | None = None,
        mapping_status: str | None = None,
        purchase_status: str | None = None,
        shipment_status: str | None = None,
    ) -> int:
        """지정된 주문 상태만 선택적으로 변경합니다."""

        valid_order_id = self._validate_id(
            order_id,
            "주문 ID",
        )

        assignments: list[str] = []
        parameters: list[Any] = []

        if order_status is not None:
            assignments.append(
                "order_status = ?"
            )
            parameters.append(
                self._validate_status(
                    order_status,
                    self.VALID_ORDER_STATUSES,
                    "주문 상태",
                )
            )

        if payment_status is not None:
            assignments.append(
                "payment_status = ?"
            )
            parameters.append(
                self._validate_status(
                    payment_status,
                    self.VALID_PAYMENT_STATUSES,
                    "결제 상태",
                )
            )

        if mapping_status is not None:
            assignments.append(
                "mapping_status = ?"
            )
            parameters.append(
                self._validate_status(
                    mapping_status,
                    self.VALID_MAPPING_STATUSES,
                    "매핑 상태",
                )
            )

        if purchase_status is not None:
            assignments.append(
                "purchase_status = ?"
            )
            parameters.append(
                self._validate_status(
                    purchase_status,
                    self.VALID_PURCHASE_STATUSES,
                    "발주 상태",
                )
            )

        if shipment_status is not None:
            assignments.append(
                "shipment_status = ?"
            )
            parameters.append(
                self._validate_status(
                    shipment_status,
                    self.VALID_SHIPMENT_STATUSES,
                    "배송 상태",
                )
            )

        if not assignments:
            raise ValueError(
                "변경할 주문 상태가 없습니다."
            )

        assignments.append(
            "updated_at = CURRENT_TIMESTAMP"
        )
        parameters.append(valid_order_id)

        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE orders
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                parameters,
            )

            connection.commit()

            return cursor.rowcount

    # =========================================================
    # 주문 삭제
    # =========================================================

    def delete_order(
        self,
        order_id: int,
    ) -> int:
        """
        주문을 삭제합니다.

        order_items와 purchase_orders는 외래키 설정에 따라 함께 삭제됩니다.
        """

        valid_order_id = self._validate_id(
            order_id,
            "주문 ID",
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM orders
                WHERE id = ?
                """,
                (valid_order_id,),
            )

            connection.commit()

            return cursor.rowcount

    # =========================================================
    # 대시보드 및 통계
    # =========================================================

    def get_order_counts(
        self,
    ) -> dict[str, int]:
        """주문 상태별 주요 건수를 조회합니다."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_count,

                    SUM(
                        CASE
                            WHEN DATE(ordered_at)
                                 = DATE('now', 'localtime')
                            THEN 1
                            ELSE 0
                        END
                    ) AS today_count,

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
                            WHEN shipment_status IN (
                                '배송준비',
                                '배송중'
                            )
                            THEN 1
                            ELSE 0
                        END
                    ) AS shipping_count

                FROM orders
                """
            ).fetchone()

        if row is None:
            return {
                "total_count": 0,
                "today_count": 0,
                "unmapped_count": 0,
                "purchase_waiting_count": 0,
                "shipping_count": 0,
            }

        return {
            key: self._safe_int(row[key])
            for key in row.keys()
        }

    def get_platforms(
        self,
    ) -> list[str]:
        """현재 저장된 주문 플랫폼 목록을 조회합니다."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT platform
                FROM orders
                WHERE platform IS NOT NULL
                  AND TRIM(platform) != ''
                ORDER BY platform
                """
            ).fetchall()

        return [
            str(row["platform"])
            for row in rows
        ]

    # =========================================================
    # 내부 상태 갱신
    # =========================================================

    def _refresh_order_mapping_status(
        self,
        connection: sqlite3.Connection,
        order_id: int,
    ) -> None:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_count,

                SUM(
                    CASE
                        WHEN product_id IS NOT NULL
                             AND mapping_status != '미매핑'
                        THEN 1
                        ELSE 0
                    END
                ) AS mapped_count

            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,),
        ).fetchone()

        total_count = self._safe_int(
            row["total_count"]
        )
        mapped_count = self._safe_int(
            row["mapped_count"]
        )

        if total_count == 0:
            order_mapping_status = "미매핑"

        elif mapped_count == total_count:
            order_mapping_status = "매핑완료"

        elif mapped_count > 0:
            order_mapping_status = "자동매핑"

        else:
            order_mapping_status = "미매핑"

        connection.execute(
            """
            UPDATE orders
            SET
                mapping_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                order_mapping_status,
                order_id,
            ),
        )

    # =========================================================
    # 검증 함수
    # =========================================================

    def _validate_items(
        self,
        items: Sequence[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not items:
            raise ValueError(
                "주문상품이 한 개 이상 필요합니다."
            )

        valid_items: list[dict[str, Any]] = []

        for index, item in enumerate(
            items,
            start=1,
        ):
            if not isinstance(item, dict):
                raise ValueError(
                    f"{index}번째 주문상품 형식이 "
                    "올바르지 않습니다."
                )

            product_name = self._required_text(
                item.get(
                    "platform_product_name"
                ),
                f"{index}번째 판매처 상품명",
            )

            quantity = self._positive_int(
                item.get("quantity", 1),
                f"{index}번째 수량",
            )

            unit_price = self._non_negative_int(
                item.get("unit_price", 0),
                f"{index}번째 단가",
            )

            provided_total = item.get(
                "total_price"
            )

            if provided_total in (None, ""):
                total_price = (
                    quantity * unit_price
                )
            else:
                total_price = (
                    self._non_negative_int(
                        provided_total,
                        f"{index}번째 총금액",
                    )
                )

            product_id = self._optional_id(
                item.get("product_id"),
                f"{index}번째 상품 ID",
            )

            supplier_id = self._optional_id(
                item.get("supplier_id"),
                f"{index}번째 공급처 ID",
            )

            item_mapping_status = item.get(
                "mapping_status"
            )

            if not item_mapping_status:
                item_mapping_status = (
                    "수동매핑"
                    if product_id is not None
                    else "미매핑"
                )

            item_mapping_status = (
                self._validate_status(
                    item_mapping_status,
                    self.VALID_MAPPING_STATUSES,
                    f"{index}번째 매핑 상태",
                )
            )

            valid_items.append(
                {
                    "product_id": product_id,
                    "platform_product_name": (
                        product_name
                    ),
                    "option_name": (
                        self._optional_text(
                            item.get(
                                "option_name"
                            )
                        )
                    ),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "supplier_id": supplier_id,
                    "purchase_round": (
                        self._optional_text(
                            item.get(
                                "purchase_round"
                            )
                        )
                    ),
                    "mapping_status": (
                        item_mapping_status
                    ),
                }
            )

        return valid_items

    @staticmethod
    def _required_text(
        value: Any,
        field_name: str,
    ) -> str:
        if value is None:
            raise ValueError(
                f"{field_name}은(는) 필수입니다."
            )

        text = str(value).strip()

        if not text:
            raise ValueError(
                f"{field_name}은(는) 필수입니다."
            )

        return text

    @staticmethod
    def _optional_text(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        text = str(value).strip()

        return text or None

    @staticmethod
    def _validate_id(
        value: Any,
        field_name: str,
    ) -> int:
        try:
            converted = int(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name}는 정수여야 합니다."
            ) from None

        if converted <= 0:
            raise ValueError(
                f"{field_name}는 1 이상이어야 합니다."
            )

        return converted

    def _optional_id(
        self,
        value: Any,
        field_name: str,
    ) -> int | None:
        if value in (None, ""):
            return None

        return self._validate_id(
            value,
            field_name,
        )

    @staticmethod
    def _positive_int(
        value: Any,
        field_name: str,
    ) -> int:
        try:
            converted = int(
                float(str(value).replace(",", ""))
            )
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name}은(는) 숫자여야 합니다."
            ) from None

        if converted <= 0:
            raise ValueError(
                f"{field_name}은(는) "
                "1 이상이어야 합니다."
            )

        return converted

    @staticmethod
    def _non_negative_int(
        value: Any,
        field_name: str,
    ) -> int:
        if value in (None, ""):
            return 0

        try:
            converted = int(
                float(str(value).replace(",", ""))
            )
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name}은(는) 숫자여야 합니다."
            ) from None

        if converted < 0:
            raise ValueError(
                f"{field_name}은(는) "
                "0 이상이어야 합니다."
            )

        return converted

    @staticmethod
    def _validate_status(
        value: Any,
        valid_values: set[str],
        field_name: str,
    ) -> str:
        text = str(value).strip()

        if text not in valid_values:
            available = ", ".join(
                sorted(valid_values)
            )

            raise ValueError(
                f"{field_name} 값이 올바르지 않습니다.\n"
                f"사용 가능 값: {available}"
            )

        return text

    @staticmethod
    def _validate_limit(
        limit: Any,
    ) -> int:
        try:
            converted = int(limit)
        except (TypeError, ValueError):
            raise ValueError(
                "조회 제한 건수는 정수여야 합니다."
            ) from None

        if converted <= 0:
            raise ValueError(
                "조회 제한 건수는 "
                "1 이상이어야 합니다."
            )

        if converted > 100_000:
            raise ValueError(
                "조회 제한 건수는 "
                "100,000 이하이어야 합니다."
            )

        return converted

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int:
        if value in (None, ""):
            return 0

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0