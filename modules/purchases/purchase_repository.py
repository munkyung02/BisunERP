import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class PurchaseRepository:
    """발주 데이터 조회·생성·수정 Repository입니다."""

    VALID_STATUSES = {
        "발주대기",
        "발주완료",
        "발주취소",
        "출고완료",
    }

    def __init__(
        self,
        database_path: Path | None = None,
    ) -> None:
        self.database_path = database_path or DATABASE_PATH

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    @staticmethod
    def _row_to_dict(
        row: sqlite3.Row | None,
    ) -> dict[str, Any] | None:
        if row is None:
            return None

        return dict(row)

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip()

        return cleaned or None

    @staticmethod
    def _validate_positive_id(
        value: int,
        field_name: str,
    ) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"{field_name}은 1 이상의 정수여야 합니다."
            )

    def _validate_status(
        self,
        purchase_status: str,
    ) -> str:
        cleaned_status = str(purchase_status).strip()

        if cleaned_status not in self.VALID_STATUSES:
            allowed = ", ".join(sorted(self.VALID_STATUSES))

            raise ValueError(
                f"올바르지 않은 발주 상태입니다. "
                f"사용 가능 상태: {allowed}"
            )

        return cleaned_status

    def get_purchase_orders(
        self,
        keyword: str | None = None,
        purchase_status: str | None = None,
        supplier_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """발주 목록을 검색 조건과 함께 조회합니다."""

        conditions: list[str] = []
        parameters: list[Any] = []

        if keyword and keyword.strip():
            search_keyword = f"%{keyword.strip()}%"

            conditions.append(
                """
                (
                    po.order_number LIKE ?
                    OR po.supplier_name LIKE ?
                    OR po.product_name LIKE ?
                    OR po.option_name LIKE ?
                    OR po.receiver_name LIKE ?
                    OR po.receiver_phone LIKE ?
                    OR po.postal_code LIKE ?
                    OR po.address LIKE ?
                )
                """
            )

            parameters.extend([search_keyword] * 8)

        if purchase_status and purchase_status.strip():
            conditions.append("po.purchase_status = ?")
            parameters.append(purchase_status.strip())

        if supplier_id is not None:
            self._validate_positive_id(
                supplier_id,
                "공급처 ID",
            )

            conditions.append("po.supplier_id = ?")
            parameters.append(supplier_id)

        where_clause = ""

        if conditions:
            where_clause = (
                "WHERE " + " AND ".join(conditions)
            )

        query = f"""
            SELECT
                po.id,
                po.supplier_id,
                po.order_id,
                po.order_item_id,
                po.supplier_name,
                po.order_number,
                po.product_name,
                po.option_name,
                po.quantity,
                po.receiver_name,
                po.receiver_phone,
                po.postal_code,
                po.address,
                po.delivery_message,
                po.purchase_status,
                po.purchase_file,
                po.purchased_at,
                po.created_at,
                po.updated_at,
                s.supplier_code,
                s.phone AS supplier_phone,
                s.email AS supplier_email,
                s.bank_name,
                s.bank_account,
                s.account_holder
            FROM purchase_orders AS po
            LEFT JOIN suppliers AS s
                ON s.id = po.supplier_id
            {where_clause}
            ORDER BY
                CASE po.purchase_status
                    WHEN '발주대기' THEN 1
                    WHEN '발주완료' THEN 2
                    WHEN '출고완료' THEN 3
                    WHEN '발주취소' THEN 4
                    ELSE 5
                END,
                po.id DESC
        """

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [dict(row) for row in rows]

    def get_purchase_by_id(
        self,
        purchase_id: int,
    ) -> dict[str, Any] | None:
        """발주 ID로 발주 한 건을 조회합니다."""

        self._validate_positive_id(
            purchase_id,
            "발주 ID",
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    po.id,
                    po.supplier_id,
                    po.order_id,
                    po.order_item_id,
                    po.supplier_name,
                    po.order_number,
                    po.product_name,
                    po.option_name,
                    po.quantity,
                    po.receiver_name,
                    po.receiver_phone,
                    po.postal_code,
                    po.address,
                    po.delivery_message,
                    po.purchase_status,
                    po.purchase_file,
                    po.purchased_at,
                    po.created_at,
                    po.updated_at,
                    s.supplier_code,
                    s.phone AS supplier_phone,
                    s.email AS supplier_email,
                    s.bank_name,
                    s.bank_account,
                    s.account_holder
                FROM purchase_orders AS po
                LEFT JOIN suppliers AS s
                    ON s.id = po.supplier_id
                WHERE po.id = ?
                """,
                (purchase_id,),
            ).fetchone()

        return self._row_to_dict(row)

    def get_purchase_by_order_item_id(
        self,
        order_item_id: int,
    ) -> dict[str, Any] | None:
        """주문 항목 ID로 연결된 발주를 조회합니다."""

        self._validate_positive_id(
            order_item_id,
            "주문 항목 ID",
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM purchase_orders
                WHERE order_item_id = ?
                """,
                (order_item_id,),
            ).fetchone()

        return self._row_to_dict(row)

    def get_purchase_status_counts(
        self,
    ) -> dict[str, int]:
        """발주 상태별 건수를 반환합니다."""

        counts = {
            "전체": 0,
            "발주대기": 0,
            "발주완료": 0,
            "출고완료": 0,
            "발주취소": 0,
        }

        with self._connect() as connection:
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
            count = int(row["count"])

            counts["전체"] += count
            counts[status] = count

        return counts

    def get_supplier_summary(
        self,
        purchase_status: str | None = None,
    ) -> list[dict[str, Any]]:
        """공급처별 발주 건수와 총수량을 조회합니다."""

        parameters: list[Any] = []
        where_clause = ""

        if purchase_status and purchase_status.strip():
            where_clause = "WHERE purchase_status = ?"
            parameters.append(purchase_status.strip())

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    supplier_id,
                    COALESCE(
                        supplier_name,
                        '공급처 미지정'
                    ) AS supplier_name,
                    COUNT(*) AS purchase_count,
                    COALESCE(
                        SUM(quantity),
                        0
                    ) AS total_quantity
                FROM purchase_orders
                {where_clause}
                GROUP BY
                    supplier_id,
                    supplier_name
                ORDER BY supplier_name
                """,
                parameters,
            ).fetchall()

        return [dict(row) for row in rows]

    def create_purchase(
        self,
        *,
        supplier_id: int | None,
        order_id: int,
        order_item_id: int,
        supplier_name: str | None,
        order_number: str,
        product_name: str,
        option_name: str | None = None,
        quantity: int = 1,
        receiver_name: str | None = None,
        receiver_phone: str | None = None,
        postal_code: str | None = None,
        address: str | None = None,
        delivery_message: str | None = None,
        purchase_status: str = "발주대기",
        purchase_file: str | None = None,
    ) -> int:
        """발주 데이터를 생성하고 발주 ID를 반환합니다."""

        self._validate_positive_id(
            order_id,
            "주문 ID",
        )
        self._validate_positive_id(
            order_item_id,
            "주문 항목 ID",
        )

        if supplier_id is not None:
            self._validate_positive_id(
                supplier_id,
                "공급처 ID",
            )

        cleaned_order_number = self._clean_text(
            order_number
        )
        cleaned_product_name = self._clean_text(
            product_name
        )

        if not cleaned_order_number:
            raise ValueError("주문번호는 필수입니다.")

        if not cleaned_product_name:
            raise ValueError("상품명은 필수입니다.")

        if quantity <= 0:
            raise ValueError(
                "발주 수량은 1개 이상이어야 합니다."
            )

        cleaned_status = self._validate_status(
            purchase_status
        )

        with self._connect() as connection:
            try:
                cursor = connection.execute(
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
                        purchase_status,
                        purchase_file,
                        purchased_at,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        CASE
                            WHEN ? = '발주완료'
                            THEN CURRENT_TIMESTAMP
                            ELSE NULL
                        END,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """,
                    (
                        supplier_id,
                        order_id,
                        order_item_id,
                        self._clean_text(supplier_name),
                        cleaned_order_number,
                        cleaned_product_name,
                        self._clean_text(option_name),
                        int(quantity),
                        self._clean_text(receiver_name),
                        self._clean_text(receiver_phone),
                        self._clean_text(postal_code),
                        self._clean_text(address),
                        self._clean_text(delivery_message),
                        cleaned_status,
                        self._clean_text(purchase_file),
                        cleaned_status,
                    ),
                )

                connection.commit()

                return int(cursor.lastrowid)

            except sqlite3.IntegrityError as error:
                if "order_item_id" in str(error):
                    raise ValueError(
                        "해당 주문 항목은 이미 발주 데이터가 "
                        "생성되어 있습니다."
                    ) from error

                raise

    def create_purchase_from_order_item(
        self,
        order_item_id: int,
    ) -> int:
        """주문 항목과 상품 매핑 정보를 이용해 발주를 생성합니다."""

        self._validate_positive_id(
            order_item_id,
            "주문 항목 ID",
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    oi.id AS order_item_id,
                    oi.order_id,
                    oi.product_id,
                    oi.supplier_id AS item_supplier_id,
                    oi.platform_product_name,
                    oi.option_name AS item_option_name,
                    oi.quantity,
                    o.order_number,
                    o.receiver_name,
                    o.receiver_phone,
                    o.postal_code,
                    o.address,
                    o.detail_address,
                    o.delivery_message,
                    p.product_name,
                    p.option_name AS product_option_name,
                    p.supplier_id AS product_supplier_id,
                    p.supplier_product_name,
                    s.supplier_name
                FROM order_items AS oi
                INNER JOIN orders AS o
                    ON o.id = oi.order_id
                LEFT JOIN products AS p
                    ON p.id = oi.product_id
                LEFT JOIN suppliers AS s
                    ON s.id = COALESCE(
                        oi.supplier_id,
                        p.supplier_id
                    )
                WHERE oi.id = ?
                """,
                (order_item_id,),
            ).fetchone()

            if row is None:
                raise ValueError(
                    "주문 항목을 찾을 수 없습니다."
                )

            supplier_id = (
                row["item_supplier_id"]
                or row["product_supplier_id"]
            )

            if supplier_id is None:
                raise ValueError(
                    "공급처가 지정되지 않은 주문 항목입니다."
                )

            product_name = (
                row["supplier_product_name"]
                or row["product_name"]
                or row["platform_product_name"]
            )

            option_name = (
                row["item_option_name"]
                or row["product_option_name"]
            )

            full_address = " ".join(
                value.strip()
                for value in (
                    row["address"],
                    row["detail_address"],
                )
                if value and value.strip()
            )

            try:
                cursor = connection.execute(
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
                        purchase_status,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, '발주대기',
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """,
                    (
                        supplier_id,
                        row["order_id"],
                        row["order_item_id"],
                        row["supplier_name"],
                        row["order_number"],
                        product_name,
                        option_name,
                        int(row["quantity"]),
                        row["receiver_name"],
                        row["receiver_phone"],
                        row["postal_code"],
                        full_address or None,
                        row["delivery_message"],
                    ),
                )

                connection.execute(
                    """
                    UPDATE order_items
                    SET
                        purchase_status = '발주대기',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (order_item_id,),
                )

                connection.commit()

                return int(cursor.lastrowid)

            except sqlite3.OperationalError as error:
                # 현재 order_items 테이블에 purchase_status가
                # 없는 구조도 지원합니다.
                if "purchase_status" not in str(error):
                    raise

                connection.rollback()

                try:
                    cursor = connection.execute(
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
                            purchase_status,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, '발주대기',
                            CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP
                        )
                        """,
                        (
                            supplier_id,
                            row["order_id"],
                            row["order_item_id"],
                            row["supplier_name"],
                            row["order_number"],
                            product_name,
                            option_name,
                            int(row["quantity"]),
                            row["receiver_name"],
                            row["receiver_phone"],
                            row["postal_code"],
                            full_address or None,
                            row["delivery_message"],
                        ),
                    )

                    connection.commit()

                    return int(cursor.lastrowid)

                except sqlite3.IntegrityError as retry_error:
                    raise ValueError(
                        "해당 주문 항목은 이미 발주 데이터가 "
                        "생성되어 있습니다."
                    ) from retry_error

            except sqlite3.IntegrityError as error:
                raise ValueError(
                    "해당 주문 항목은 이미 발주 데이터가 "
                    "생성되어 있습니다."
                ) from error

    def create_all_pending_purchases(
        self,
    ) -> dict[str, int]:
        """발주 가능한 주문 항목을 일괄 발주 데이터로 생성합니다."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    oi.id
                FROM order_items AS oi
                LEFT JOIN products AS p
                    ON p.id = oi.product_id
                LEFT JOIN purchase_orders AS po
                    ON po.order_item_id = oi.id
                WHERE po.id IS NULL
                  AND COALESCE(
                        oi.supplier_id,
                        p.supplier_id
                      ) IS NOT NULL
                ORDER BY oi.id
                """
            ).fetchall()

        result = {
            "target_count": len(rows),
            "created_count": 0,
            "failed_count": 0,
        }

        for row in rows:
            try:
                self.create_purchase_from_order_item(
                    int(row["id"])
                )
                result["created_count"] += 1

            except (ValueError, sqlite3.Error):
                result["failed_count"] += 1

        return result

    def update_purchase(
        self,
        purchase_id: int,
        *,
        supplier_id: int | None,
        supplier_name: str | None,
        product_name: str,
        option_name: str | None,
        quantity: int,
        receiver_name: str | None,
        receiver_phone: str | None,
        postal_code: str | None,
        address: str | None,
        delivery_message: str | None,
    ) -> int:
        """발주 내용을 수정합니다."""

        self._validate_positive_id(
            purchase_id,
            "발주 ID",
        )

        if supplier_id is not None:
            self._validate_positive_id(
                supplier_id,
                "공급처 ID",
            )

        cleaned_product_name = self._clean_text(
            product_name
        )

        if not cleaned_product_name:
            raise ValueError("상품명은 필수입니다.")

        if quantity <= 0:
            raise ValueError(
                "발주 수량은 1개 이상이어야 합니다."
            )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE purchase_orders
                SET
                    supplier_id = ?,
                    supplier_name = ?,
                    product_name = ?,
                    option_name = ?,
                    quantity = ?,
                    receiver_name = ?,
                    receiver_phone = ?,
                    postal_code = ?,
                    address = ?,
                    delivery_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    supplier_id,
                    self._clean_text(supplier_name),
                    cleaned_product_name,
                    self._clean_text(option_name),
                    int(quantity),
                    self._clean_text(receiver_name),
                    self._clean_text(receiver_phone),
                    self._clean_text(postal_code),
                    self._clean_text(address),
                    self._clean_text(delivery_message),
                    purchase_id,
                ),
            )

            connection.commit()

            return cursor.rowcount

    def update_purchase_status(
        self,
        purchase_id: int,
        purchase_status: str,
    ) -> int:
        """발주 상태를 변경합니다."""

        self._validate_positive_id(
            purchase_id,
            "발주 ID",
        )

        cleaned_status = self._validate_status(
            purchase_status
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE purchase_orders
                SET
                    purchase_status = ?,
                    purchased_at = CASE
                        WHEN ? = '발주완료'
                        THEN COALESCE(
                            purchased_at,
                            CURRENT_TIMESTAMP
                        )
                        WHEN ? = '발주대기'
                        THEN NULL
                        ELSE purchased_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    cleaned_status,
                    cleaned_status,
                    cleaned_status,
                    purchase_id,
                ),
            )

            connection.commit()

            return cursor.rowcount

    def update_purchase_file(
        self,
        purchase_id: int,
        purchase_file: str | None,
    ) -> int:
        """생성된 발주서 파일 경로를 저장합니다."""

        self._validate_positive_id(
            purchase_id,
            "발주 ID",
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE purchase_orders
                SET
                    purchase_file = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    self._clean_text(purchase_file),
                    purchase_id,
                ),
            )

            connection.commit()

            return cursor.rowcount

    def delete_purchase(
        self,
        purchase_id: int,
    ) -> int:
        """발주 한 건을 삭제합니다."""

        self._validate_positive_id(
            purchase_id,
            "발주 ID",
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM purchase_orders
                WHERE id = ?
                """,
                (purchase_id,),
            )

            connection.commit()

            return cursor.rowcount