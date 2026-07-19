import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ShipmentRepository:

    def __init__(self) -> None:
        self.database_path = DATABASE_PATH

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.database_path
        )
        conn.row_factory = sqlite3.Row
        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        return conn

    def shipment_exists(
        self,
        tracking_number: str,
    ) -> bool:
        """같은 송장번호가 이미 등록되어 있는지 확인합니다."""

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM shipments
                WHERE tracking_number = ?
                LIMIT 1
                """,
                (
                    tracking_number.strip(),
                ),
            ).fetchone()

        return row is not None

    def find_match_candidates(
        self,
        *,
        supplier_name: str,
        receiver_name: str,
        receiver_phone: str,
        quantity: int,
    ) -> list[dict]:
        """
        공급처 송장정보와 발주내역을 단계적으로 매칭합니다.

        1단계: 공급처 + 수취인 + 전화번호 + 수량
        2단계: 공급처 + 수취인 + 수량
        3단계: 수취인 + 전화번호 + 수량
        4단계: 수취인 + 수량

        여러 건이 검색되면 ShipmentService에서 '중복후보'로 처리합니다.
        """

        normalized_supplier = (
            supplier_name
            .strip()
            .replace(" ", "")
        )

        normalized_receiver = (
            receiver_name.strip()
        )

        normalized_phone = "".join(
            character
            for character in str(receiver_phone)
            if character.isdigit()
        )

        base_select = """
            SELECT
                po.id AS purchase_order_id,
                po.order_id,
                po.order_item_id,
                po.supplier_id,
                po.supplier_name,
                po.order_number,
                po.product_name,
                po.option_name,
                po.quantity,
                po.receiver_name,
                po.receiver_phone,
                po.purchase_status

            FROM purchase_orders AS po

            LEFT JOIN shipments AS sh
                ON sh.order_item_id = po.order_item_id

            WHERE sh.id IS NULL
        """

        with self._connect() as conn:

            # 1단계: 모든 조건 정확히 일치
            rows = conn.execute(
                base_select
                + """
                    AND REPLACE(
                        TRIM(po.supplier_name),
                        ' ',
                        ''
                        ) = ?
                    AND TRIM(po.receiver_name) = ?
                    AND REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    po.receiver_phone,
                                    '-',
                                    ''
                                ),
                                ' ',
                                ''
                            ),
                            '.',
                            ''
                        ),
                        '+82',
                        '0'
                        ) = ?
                    AND po.quantity = ?

                ORDER BY po.id
                """,
                (
                    normalized_supplier,
                    normalized_receiver,
                    normalized_phone,
                    quantity,
                ),
            ).fetchall()

            if rows:
                return [
                    dict(row)
                    for row in rows
                ]

            # 2단계: 전화번호를 제외하고 매칭
            rows = conn.execute(
                base_select
                + """
                    AND REPLACE(
                        TRIM(po.supplier_name),
                        ' ',
                        ''
                        ) = ?
                    AND TRIM(po.receiver_name) = ?
                    AND po.quantity = ?

                ORDER BY po.id
                """,
                (
                    normalized_supplier,
                    normalized_receiver,
                    quantity,
                ),
            ).fetchall()

            if rows:
                return [
                    dict(row)
                    for row in rows
                ]

            # 3단계: 공급처명을 제외하고 전화번호로 매칭
            rows = conn.execute(
                base_select
                + """
                    AND TRIM(po.receiver_name) = ?
                    AND REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    po.receiver_phone,
                                    '-',
                                    ''
                                ),
                                ' ',
                                ''
                            ),
                            '.',
                            ''
                        ),
                        '+82',
                        '0'
                        ) = ?
                    AND po.quantity = ?

                ORDER BY po.id
                """,
                (
                    normalized_receiver,
                    normalized_phone,
                    quantity,
                ),
            ).fetchall()

            if rows:
                return [
                    dict(row)
                    for row in rows
                ]

            # 4단계: 최종적으로 수취인명과 수량만 비교
            rows = conn.execute(
                base_select
                + """
                    AND TRIM(po.receiver_name) = ?
                    AND po.quantity = ?

                ORDER BY po.id
                """,
                (
                    normalized_receiver,
                    quantity,
                ),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def create_shipment(
        self,
        *,
        order_id: int,
        order_item_id: int,
        supplier_id: int | None,
        courier_name: str,
        tracking_number: str,
        shipment_status: str = "배송중",
    ) -> int:
        """송장정보를 저장합니다."""

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO shipments
                (
                    order_id,
                    order_item_id,
                    supplier_id,
                    courier_name,
                    tracking_number,
                    shipment_status,
                    shipped_at,
                    created_at,
                    updated_at
                )
                VALUES
                (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    order_id,
                    order_item_id,
                    supplier_id,
                    courier_name.strip(),
                    tracking_number.strip(),
                    shipment_status,
                ),
            )

            conn.commit()

            return int(
                cursor.lastrowid
            )

    def update_purchase_order_status(
        self,
        purchase_order_id: int,
        purchase_status: str,
    ) -> int:
        """발주내역 상태를 변경합니다."""

        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE purchase_orders
                SET purchase_status = ?
                WHERE id = ?
                """,
                (
                    purchase_status,
                    purchase_order_id,
                ),
            )

            conn.commit()

            return cursor.rowcount

    def get_shipments(
        self,
        keyword: str | None = None,
    ) -> list[dict]:
        """저장된 송장 목록을 조회합니다."""

        conditions: list[str] = []
        parameters: list[str] = []

        if keyword and keyword.strip():
            search_keyword = (
                f"%{keyword.strip()}%"
            )

            conditions.append(
                """
                (
                    sh.tracking_number LIKE ?
                    OR sh.courier_name LIKE ?
                    OR po.order_number LIKE ?
                    OR po.receiver_name LIKE ?
                    OR po.product_name LIKE ?
                    OR po.supplier_name LIKE ?
                )
                """
            )

            parameters.extend(
                [search_keyword] * 6
            )

        where_clause = ""

        if conditions:
            where_clause = (
                "WHERE "
                + " AND ".join(conditions)
            )

        query = f"""
            SELECT
                sh.id,
                sh.order_id,
                sh.order_item_id,
                sh.supplier_id,
                sh.courier_name,
                sh.tracking_number,
                sh.shipment_status,
                sh.shipped_at,
                sh.created_at,

                po.order_number,
                po.supplier_name,
                po.receiver_name,
                po.receiver_phone,
                po.product_name,
                po.option_name,
                po.quantity

            FROM shipments AS sh

            LEFT JOIN purchase_orders AS po
                ON po.order_item_id = sh.order_item_id

            {where_clause}

            ORDER BY sh.id DESC
        """

        with self._connect() as conn:
            rows = conn.execute(
                query,
                parameters,
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]
    def get_ready_shipments(self) -> list[dict]:
        """배송중 상태의 송장 목록을 조회합니다."""

        with self._connect() as conn:

            rows = conn.execute(
                """
                SELECT

                    po.order_number,

                    sh.courier_name,

                    sh.tracking_number

                FROM shipments AS sh

                INNER JOIN purchase_orders AS po
                    ON po.order_item_id = sh.order_item_id

                WHERE sh.shipment_status='배송중'

                ORDER BY sh.id
                """
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]