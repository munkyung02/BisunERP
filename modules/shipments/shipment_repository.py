import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ShipmentRepository:

    def __init__(self) -> None:
        self.database_path = DATABASE_PATH
        self._ensure_coupang_api_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.database_path
        )
        conn.row_factory = sqlite3.Row
        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        return conn

    def _ensure_coupang_api_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS coupang_shipment_api_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shipment_id INTEGER NOT NULL UNIQUE,
                    api_status TEXT NOT NULL DEFAULT '전송대기',
                    result_code TEXT NOT NULL DEFAULT '',
                    result_message TEXT NOT NULL DEFAULT '',
                    retry_required INTEGER NOT NULL DEFAULT 0,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    request_json TEXT NOT NULL DEFAULT '',
                    response_json TEXT NOT NULL DEFAULT '',
                    last_attempt_at TEXT,
                    sent_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(shipment_id)
                        REFERENCES shipments(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_coupang_shipment_api_status
                ON coupang_shipment_api_logs(api_status)
                """
            )
            conn.commit()

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
        shipment_status: str = "송장등록완료",
        purchase_order_id: int | None = None,
    ) -> int:
        """송장 저장과 관련 상태 변경을 하나의 트랜잭션으로 처리합니다."""

        cleaned_courier = str(courier_name or "").strip()
        cleaned_tracking = str(tracking_number or "").strip()

        if not cleaned_courier:
            raise ValueError("택배사를 입력해주세요.")

        if not cleaned_tracking:
            raise ValueError("송장번호를 입력해주세요.")

        with self._connect() as conn:
            duplicate_tracking = conn.execute(
                """
                SELECT
                    sh.id,
                    sh.order_item_id,
                    COALESCE(po.order_number, '') AS order_number
                FROM shipments AS sh
                LEFT JOIN purchase_orders AS po
                    ON po.order_item_id = sh.order_item_id
                WHERE TRIM(sh.tracking_number) = TRIM(?)
                LIMIT 1
                """,
                (cleaned_tracking,),
            ).fetchone()

            if duplicate_tracking is not None:
                registered_order = str(
                    duplicate_tracking["order_number"] or ""
                ).strip()
                detail = (
                    f" (기등록 주문번호: {registered_order})"
                    if registered_order
                    else ""
                )
                raise ValueError(
                    "같은 송장번호가 이미 다른 주문상품에 등록되어 있습니다."
                    + detail
                )

            duplicate_item = conn.execute(
                """
                SELECT id
                FROM shipments
                WHERE order_item_id = ?
                LIMIT 1
                """,
                (int(order_item_id),),
            ).fetchone()

            if duplicate_item is not None:
                raise ValueError(
                    "해당 주문상품에는 이미 송장이 등록되어 있습니다."
                )

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
                    ?, ?, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    int(order_id),
                    int(order_item_id),
                    supplier_id,
                    cleaned_courier,
                    cleaned_tracking,
                    shipment_status,
                ),
            )

            if purchase_order_id is not None:
                conn.execute(
                    """
                    UPDATE purchase_orders
                    SET purchase_status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        "송장등록완료",
                        int(purchase_order_id),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE purchase_orders
                    SET purchase_status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE order_item_id = ?
                    """,
                    (
                        "송장등록완료",
                        int(order_item_id),
                    ),
                )

            self._refresh_order_shipment_status(
                conn,
                int(order_id),
            )

            conn.commit()
            return int(cursor.lastrowid)

    def _refresh_order_shipment_status(
        self,
        conn: sqlite3.Connection,
        order_id: int,
    ) -> None:
        """주문상품 전체의 송장 등록 여부로 주문 상태를 갱신합니다."""

        row = conn.execute(
            """
            SELECT
                COUNT(oi.id) AS total_count,
                COUNT(sh.id) AS registered_count
            FROM order_items AS oi
            LEFT JOIN shipments AS sh
                ON sh.order_item_id = oi.id
            WHERE oi.order_id = ?
            """,
            (int(order_id),),
        ).fetchone()

        total_count = int(row["total_count"] or 0)
        registered_count = int(row["registered_count"] or 0)

        status = (
            "송장등록완료"
            if total_count > 0 and registered_count >= total_count
            else "송장대기"
        )

        conn.execute(
            """
            UPDATE orders
            SET shipment_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, int(order_id)),
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

                COALESCE(o.platform, '') AS platform,
                CASE
                    WHEN o.platform = '쿠팡'
                    THEN COALESCE(api.api_status, '전송대기')
                    ELSE '해당없음'
                END AS coupang_api_status,
                COALESCE(api.result_code, '') AS coupang_result_code,
                COALESCE(api.result_message, '') AS coupang_result_message,
                COALESCE(api.retry_count, 0) AS coupang_retry_count,
                api.last_attempt_at AS coupang_last_attempt_at,
                api.sent_at AS coupang_sent_at,

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

            LEFT JOIN orders AS o
                ON o.id = sh.order_id

            LEFT JOIN coupang_shipment_api_logs AS api
                ON api.shipment_id = sh.id

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

    def find_order_items_for_simple_shipment(self, order_number: str) -> list[dict]:
        """주문번호에 해당하는 아직 송장이 없는 발주상품을 조회합니다."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT po.id AS purchase_order_id, po.order_id, po.order_item_id,
                       po.supplier_id, po.order_number, po.product_name, po.option_name
                FROM purchase_orders AS po
                LEFT JOIN shipments AS sh ON sh.order_item_id = po.order_item_id
                WHERE TRIM(po.order_number) = TRIM(?) AND sh.id IS NULL
                ORDER BY po.id
                """, (order_number,)
            ).fetchall()
        return [dict(row) for row in rows]

    def simple_shipment_exists(self, order_number: str, tracking_number: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT sh.id FROM shipments sh
                   JOIN orders o ON o.id = sh.order_id
                   WHERE TRIM(o.order_number)=TRIM(?) AND TRIM(sh.tracking_number)=TRIM(?)
                   LIMIT 1""",
                (order_number, tracking_number),
            ).fetchone()
        return row is not None

    def update_order_shipment_status(
        self,
        order_id: int,
        status: str = "송장등록완료",
    ) -> None:
        """주문의 송장 상태만 변경합니다."""

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE orders
                SET shipment_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    int(order_id),
                ),
            )
            conn.commit()

    def get_shipment_waiting_count(self) -> int:
        """발주 생성 후 송장이 없는 주문상품 수를 반환합니다."""

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS waiting_count
                FROM purchase_orders AS po
                LEFT JOIN shipments AS sh
                    ON sh.order_item_id = po.order_item_id
                WHERE sh.id IS NULL
                  AND po.purchase_status NOT IN ('발주취소', '취소')
                """
            ).fetchone()

        return int(row["waiting_count"] or 0) if row else 0

    def get_shipment_summary(self) -> dict[str, int]:
        """송장 화면 KPI를 조회합니다."""

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    (
                        SELECT COUNT(*)
                        FROM purchase_orders AS po
                        LEFT JOIN shipments AS sh
                            ON sh.order_item_id = po.order_item_id
                        WHERE sh.id IS NULL
                          AND po.purchase_status NOT IN ('발주취소', '취소')
                    ) AS waiting_count,
                    (
                        SELECT COUNT(*)
                        FROM shipments
                        WHERE DATE(created_at) = DATE('now', 'localtime')
                    ) AS today_registered_count,
                    (
                        SELECT COUNT(*)
                        FROM shipments
                    ) AS total_registered_count
                """
            ).fetchone()

        return {
            "waiting_count": int(row["waiting_count"] or 0) if row else 0,
            "today_registered_count": int(row["today_registered_count"] or 0) if row else 0,
            "total_registered_count": int(row["total_registered_count"] or 0) if row else 0,
        }

    def get_coupang_api_summary(self) -> dict[str, int]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(
                        CASE
                            WHEN o.platform = '쿠팡'
                             AND COALESCE(api.api_status, '전송대기') = '전송대기'
                            THEN 1 ELSE 0
                        END
                    ) AS waiting_count,
                    SUM(
                        CASE
                            WHEN api.api_status = '전송완료'
                             AND DATE(api.sent_at) = DATE('now', 'localtime')
                            THEN 1 ELSE 0
                        END
                    ) AS today_success_count,
                    SUM(
                        CASE
                            WHEN api.api_status = '전송실패'
                            THEN 1 ELSE 0
                        END
                    ) AS failed_count
                FROM shipments AS sh
                INNER JOIN orders AS o
                    ON o.id = sh.order_id
                LEFT JOIN coupang_shipment_api_logs AS api
                    ON api.shipment_id = sh.id
                """
            ).fetchone()

        return {
            "waiting_count": int(row["waiting_count"] or 0),
            "today_success_count": int(row["today_success_count"] or 0),
            "failed_count": int(row["failed_count"] or 0),
        }

    def get_failed_coupang_shipment_ids(self) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT shipment_id
                FROM coupang_shipment_api_logs
                WHERE api_status = '전송실패'
                ORDER BY id
                """
            ).fetchall()
        return [int(row["shipment_id"]) for row in rows]

    def get_ready_shipments(self) -> list[dict]:
        """등록 완료된 송장 목록을 조회합니다."""

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

                WHERE sh.shipment_status IN (
                    '송장등록완료',
                    '배송중',
                    '배송완료'
                )

                ORDER BY sh.id
                """
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]