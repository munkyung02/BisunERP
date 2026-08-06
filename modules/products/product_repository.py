import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ProductRepository:
    """상품 데이터 조회·등록·수정 Repository입니다."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or DATABASE_PATH
        self._ensure_product_supplier_schema()
        self._ensure_notion_sync_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def _ensure_notion_sync_schema(self) -> None:
        """기존 DB를 보존하며 상품별 Notion 동기화 상태 컬럼을 준비합니다."""
        with self._connect() as connection:
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(products)")
            }
            additions = {
                "notion_page_id": "TEXT",
                "notion_last_edited_time": "TEXT",
                "notion_last_sync": "TEXT",
                "sync_status": "TEXT NOT NULL DEFAULT '미동기화'",
                "sync_message": "TEXT",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE products ADD COLUMN {name} {definition}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_products_notion_page_id "
                "ON products(notion_page_id)"
            )
            connection.commit()


    def _ensure_product_supplier_schema(self) -> None:
        """기존 기본 공급처를 보존하며 다중 공급처 테이블을 준비한다."""
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS product_suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    supplier_product_name TEXT,
                    supplier_product_code TEXT,
                    purchase_price INTEGER NOT NULL DEFAULT 0,
                    minimum_order_quantity INTEGER NOT NULL DEFAULT 1,
                    package_unit_qty INTEGER NOT NULL DEFAULT 1,
                    package_unit_name TEXT NOT NULL DEFAULT '개',
                    shipping_fee INTEGER NOT NULL DEFAULT 0,
                    carrier TEXT,
                    order_deadline TEXT NOT NULL DEFAULT '14:00',
                    is_default INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(product_id, supplier_id),
                    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
                    FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
                )
            """)
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(product_suppliers)")}
            if "supplier_product_code" not in columns:
                connection.execute("ALTER TABLE product_suppliers ADD COLUMN supplier_product_code TEXT")
            if "minimum_order_quantity" not in columns:
                connection.execute("ALTER TABLE product_suppliers ADD COLUMN minimum_order_quantity INTEGER NOT NULL DEFAULT 1")
            if "package_unit_qty" not in columns:
                connection.execute("ALTER TABLE product_suppliers ADD COLUMN package_unit_qty INTEGER NOT NULL DEFAULT 1")
            if "package_unit_name" not in columns:
                connection.execute("ALTER TABLE product_suppliers ADD COLUMN package_unit_name TEXT NOT NULL DEFAULT '개'")
            if "shipping_fee" not in columns:
                connection.execute("ALTER TABLE product_suppliers ADD COLUMN shipping_fee INTEGER NOT NULL DEFAULT 0")
            if "carrier" not in columns:
                connection.execute("ALTER TABLE product_suppliers ADD COLUMN carrier TEXT")
            if "order_deadline" not in columns:
                connection.execute("ALTER TABLE product_suppliers ADD COLUMN order_deadline TEXT NOT NULL DEFAULT '14:00'")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS "
                "idx_product_suppliers_product "
                "ON product_suppliers(product_id, is_active)"
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS product_mapping_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL DEFAULT '',
                    platform_product_name TEXT NOT NULL,
                    option_name TEXT NOT NULL DEFAULT '',
                    product_id INTEGER NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, platform_product_name, option_name),
                    FOREIGN KEY(product_id) REFERENCES products(id)
                )
                """
            )

            product_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(products)")}
            deadline_expression = "COALESCE(purchase_deadline,'14:00')" if "purchase_deadline" in product_columns else "'14:00'"
            supplier_name_expression = "supplier_product_name" if "supplier_product_name" in product_columns else "product_name"
            connection.execute(f"""
                INSERT OR IGNORE INTO product_suppliers
                    (product_id, supplier_id, supplier_product_name, supplier_product_code, purchase_price, minimum_order_quantity, package_unit_qty, package_unit_name, shipping_fee, carrier, order_deadline, is_default, is_active)
                SELECT id, supplier_id, {supplier_name_expression}, NULL, COALESCE(purchase_price,0), 1, 1, '개', 0, NULL, {deadline_expression}, 1, 1
                FROM products WHERE supplier_id IS NOT NULL
            """)
            connection.commit()

    def get_product_suppliers(self, product_id: int, active_only: bool = False) -> list[dict[str, Any]]:
        where = "AND ps.is_active = 1" if active_only else ""
        with self._connect() as connection:
            rows = connection.execute(f"""
                SELECT ps.*, s.supplier_name
                FROM product_suppliers ps
                JOIN suppliers s ON s.id = ps.supplier_id
                WHERE ps.product_id = ? {where}
                ORDER BY ps.is_default DESC, ps.id
            """, (int(product_id),)).fetchall()
        return [dict(row) for row in rows]

    def add_product_supplier(self, product_id: int, supplier_id: int, *, supplier_product_name: str | None = None, supplier_product_code: str | None = None, purchase_price: int = 0, minimum_order_quantity: int = 1, package_unit_qty: int = 1, package_unit_name: str = "개", shipping_fee: int = 0, carrier: str | None = None, order_deadline: str = "14:00") -> int:
        deadline = str(order_deadline or "14:00").strip()
        try:
            from datetime import datetime
            datetime.strptime(deadline, "%H:%M")
        except ValueError as exc:
            raise ValueError("발주마감시간은 14:00 형식으로 입력해 주세요.") from exc
        with self._connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM product_suppliers WHERE product_id=?", (int(product_id),)).fetchone()[0]
            cursor = connection.execute("""
                INSERT INTO product_suppliers
                    (product_id, supplier_id, supplier_product_name, supplier_product_code, purchase_price, minimum_order_quantity, package_unit_qty, package_unit_name, shipping_fee, carrier, order_deadline, is_default, is_active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(product_id, supplier_id) DO UPDATE SET
                    supplier_product_name=COALESCE(excluded.supplier_product_name, product_suppliers.supplier_product_name),
                    supplier_product_code=COALESCE(excluded.supplier_product_code, product_suppliers.supplier_product_code),
                    purchase_price=excluded.purchase_price, minimum_order_quantity=excluded.minimum_order_quantity,
                    package_unit_qty=excluded.package_unit_qty, package_unit_name=excluded.package_unit_name,
                    shipping_fee=excluded.shipping_fee, carrier=excluded.carrier, order_deadline=excluded.order_deadline,
                    is_active=1, updated_at=CURRENT_TIMESTAMP
            """, (int(product_id), int(supplier_id), self._clean_text(supplier_product_name), self._clean_text(supplier_product_code), max(0, int(purchase_price)), max(1, int(minimum_order_quantity)), max(1, int(package_unit_qty)), self._clean_text(package_unit_name) or "개", max(0, int(shipping_fee)), self._clean_text(carrier), deadline, 1 if count == 0 else 0))
            connection.commit()
            return int(cursor.lastrowid or 0)

    def set_default_product_supplier(self, product_id: int, link_id: int) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT supplier_id, supplier_product_name, purchase_price FROM product_suppliers WHERE id=? AND product_id=?", (int(link_id), int(product_id))).fetchone()
            if row is None:
                raise ValueError("선택한 공급처 연결을 찾을 수 없습니다.")
            connection.execute("UPDATE product_suppliers SET is_default=0, updated_at=CURRENT_TIMESTAMP WHERE product_id=?", (int(product_id),))
            connection.execute("UPDATE product_suppliers SET is_default=1, is_active=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(link_id),))
            connection.execute("""UPDATE products SET supplier_id=?, supplier_product_name=?, purchase_price=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                               (row["supplier_id"], row["supplier_product_name"], int(row["purchase_price"] or 0), int(product_id)))
            connection.commit()

    def delete_product_supplier(self, product_id: int, link_id: int) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT is_default FROM product_suppliers WHERE id=? AND product_id=?", (int(link_id), int(product_id))).fetchone()
            if row is None:
                return
            if int(row["is_default"] or 0):
                raise ValueError("기본 공급처는 삭제할 수 없습니다. 다른 공급처를 기본으로 지정한 뒤 삭제하세요.")
            connection.execute("DELETE FROM product_suppliers WHERE id=?", (int(link_id),))
            connection.commit()

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

    def _generate_product_code(
        self,
        connection: sqlite3.Connection,
    ) -> str:
        """PRD-000001 형식의 상품코드를 생성합니다."""

        rows = connection.execute(
            """
            SELECT product_code
            FROM products
            WHERE product_code LIKE 'PRD-%'
            """
        ).fetchall()

        max_number = 0

        for row in rows:
            product_code = row["product_code"]

            if not product_code:
                continue

            try:
                number = int(product_code.split("-")[-1])
                max_number = max(max_number, number)
            except (ValueError, IndexError):
                continue

        return f"PRD-{max_number + 1:06d}"

    def get_products(
        self,
        keyword: str | None = None,
        active_only: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        상품 목록과 기본 공급처, 공급처 수,
        매핑 규칙 수 및 실제 주문 매핑 수를 조회합니다.
        """

        conditions: list[str] = []
        parameters: list[Any] = []

        if keyword and keyword.strip():
            search_keyword = f"%{keyword.strip()}%"

            conditions.append(
                """
                (
                    p.product_code LIKE ?
                    OR p.product_name LIKE ?
                    OR p.platform_product_name LIKE ?
                    OR p.option_name LIKE ?
                    OR p.supplier_product_name LIKE ?
                    OR p.platform LIKE ?
                    OR s.supplier_name LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM product_suppliers AS ps_search
                        LEFT JOIN suppliers AS ss
                            ON ss.id = ps_search.supplier_id
                        WHERE ps_search.product_id = p.id
                          AND (
                              ps_search.supplier_product_name LIKE ?
                              OR ps_search.supplier_product_code LIKE ?
                              OR ss.supplier_name LIKE ?
                          )
                    )
                )
                """
            )

            parameters.extend(
                [search_keyword] * 10
            )

        if active_only is not None:
            conditions.append(
                "p.is_active = ?"
            )
            parameters.append(
                1 if active_only else 0
            )

        where_clause = (
            "WHERE " + " AND ".join(conditions)
            if conditions
            else ""
        )

        query = f"""
            SELECT
                p.id,
                p.product_code,
                p.platform,
                p.platform_product_name,
                p.product_name,
                p.option_name,
                p.supplier_id,
                s.supplier_name,
                p.supplier_product_name,
                p.purchase_price,
                p.sale_price,
                p.purchase_round,
                p.is_active,
                p.notion_page_id,
                p.notion_last_edited_time,
                p.notion_last_sync,
                p.sync_status,
                p.sync_message,
                p.created_at,
                p.updated_at,

                (
                    SELECT COUNT(*)
                    FROM product_suppliers AS ps
                    WHERE ps.product_id = p.id
                      AND ps.is_active = 1
                ) AS supplier_count,

                (
                    SELECT COUNT(*)
                    FROM product_mapping_rules AS pmr
                    WHERE pmr.product_id = p.id
                      AND pmr.is_active = 1
                ) AS mapping_rule_count,

                (
                    SELECT COUNT(*)
                    FROM order_items AS oi
                    WHERE oi.product_id = p.id
                ) AS mapped_order_item_count

            FROM products AS p

            LEFT JOIN suppliers AS s
                ON s.id = p.supplier_id

            {where_clause}

            ORDER BY
                p.is_active DESC,
                p.id DESC
        """

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        result: list[dict[str, Any]] = []

        for row in rows:
            item = dict(row)
            item["mapping_count"] = (
                int(item.get("mapping_rule_count") or 0)
                + int(item.get("mapped_order_item_count") or 0)
            )
            result.append(item)

        return result

    def get_product_by_id(
        self,
        product_id: int,
    ) -> dict[str, Any] | None:
        """상품 ID로 상품 한 건을 조회합니다."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    p.id,
                    p.product_code,
                    p.platform,
                    p.platform_product_name,
                    p.product_name,
                    p.option_name,
                    p.supplier_id,
                    s.supplier_name,
                    p.supplier_product_name,
                    p.purchase_price,
                    p.sale_price,
                    p.purchase_round,
                    p.is_active,
                    p.notion_page_id,
                    p.notion_last_edited_time,
                    p.notion_last_sync,
                    p.sync_status,
                    p.sync_message,
                    p.created_at,
                    p.updated_at
                FROM products AS p
                LEFT JOIN suppliers AS s
                    ON s.id = p.supplier_id
                WHERE p.id = ?
                """,
                (product_id,),
            ).fetchone()

        return self._row_to_dict(row)

    def _sync_default_supplier_link(
        self,
        connection: sqlite3.Connection,
        *,
        product_id: int,
        supplier_id: int | None,
        supplier_product_name: str | None,
        purchase_price: int,
    ) -> None:
        """상품 기본 공급처 정보를 다중 공급처 테이블과 동기화합니다."""

        if supplier_id is None:
            return

        connection.execute(
            """
            UPDATE product_suppliers
            SET is_default = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE product_id = ?
            """,
            (int(product_id),),
        )

        connection.execute(
            """
            INSERT INTO product_suppliers
            (
                product_id,
                supplier_id,
                supplier_product_name,
                purchase_price,
                is_default,
                is_active,
                updated_at
            )
            VALUES (?, ?, ?, ?, 1, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(product_id, supplier_id)
            DO UPDATE SET
                supplier_product_name = excluded.supplier_product_name,
                purchase_price = excluded.purchase_price,
                is_default = 1,
                is_active = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(product_id),
                int(supplier_id),
                self._clean_text(supplier_product_name),
                max(0, int(purchase_price)),
            ),
        )

    def get_supplier_id_by_name(
        self,
        supplier_name: str | None,
    ) -> int | None:
        """공급처명으로 활성 공급처 ID를 찾습니다."""

        cleaned_name = self._clean_text(
            supplier_name
        )

        if not cleaned_name:
            return None

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM suppliers
                WHERE REPLACE(TRIM(supplier_name), ' ', '')
                    = REPLACE(TRIM(?), ' ', '')
                ORDER BY is_active DESC, id
                LIMIT 1
                """,
                (cleaned_name,),
            ).fetchone()

        return int(row["id"]) if row else None

    def import_products(
        self,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        엑셀에서 읽은 상품을 일괄 등록합니다.

        product_code가 있으면 해당 코드 상품을 수정하고,
        없으면 새 상품으로 등록합니다.
        """

        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors: list[dict[str, Any]] = []

        for index, row in enumerate(rows, start=2):
            try:
                product_name = self._clean_text(
                    row.get("product_name")
                )

                if not product_name:
                    skipped_count += 1
                    errors.append({
                        "row": index,
                        "error": "내부 상품명이 없습니다.",
                    })
                    continue

                supplier_id = row.get("supplier_id")

                if supplier_id in (None, ""):
                    supplier_id = self.get_supplier_id_by_name(
                        row.get("supplier_name")
                    )

                product_code = self._clean_text(
                    row.get("product_code")
                )

                data = {
                    "product_name": product_name,
                    "platform": self._clean_text(row.get("platform")),
                    "platform_product_name": self._clean_text(
                        row.get("platform_product_name")
                    ),
                    "option_name": self._clean_text(row.get("option_name")),
                    "supplier_id": (
                        int(supplier_id)
                        if supplier_id not in (None, "")
                        else None
                    ),
                    "supplier_product_name": self._clean_text(
                        row.get("supplier_product_name")
                    ),
                    "purchase_price": max(
                        0,
                        int(row.get("purchase_price") or 0),
                    ),
                    "sale_price": max(
                        0,
                        int(row.get("sale_price") or 0),
                    ),
                    "purchase_round": self._clean_text(
                        row.get("purchase_round")
                    ),
                    "is_active": bool(
                        int(row.get("is_active", 1) or 0)
                    ),
                }

                existing_id: int | None = None

                if product_code:
                    with self._connect() as connection:
                        existing = connection.execute(
                            """
                            SELECT id
                            FROM products
                            WHERE TRIM(product_code) = TRIM(?)
                            LIMIT 1
                            """,
                            (product_code,),
                        ).fetchone()

                    if existing:
                        existing_id = int(existing["id"])

                if existing_id is not None:
                    self.update_product(
                        existing_id,
                        **data,
                    )
                    updated_count += 1
                else:
                    self.create_product(
                        **data,
                    )
                    created_count += 1

            except Exception as error:
                skipped_count += 1
                errors.append({
                    "row": index,
                    "error": str(error),
                })

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "errors": errors,
        }

    def create_product(
        self,
        *,
        product_name: str,
        platform: str | None = None,
        platform_product_name: str | None = None,
        option_name: str | None = None,
        supplier_id: int | None = None,
        supplier_product_name: str | None = None,
        purchase_price: int = 0,
        sale_price: int = 0,
        purchase_round: str | None = None,
        is_active: bool = True,
    ) -> int:
        """새 상품을 등록하고 상품 ID를 반환합니다."""

        cleaned_product_name = self._clean_text(product_name)

        if not cleaned_product_name:
            raise ValueError("상품명은 필수입니다.")

        if purchase_price < 0:
            raise ValueError("매입가는 0원 이상이어야 합니다.")

        if sale_price < 0:
            raise ValueError("판매가는 0원 이상이어야 합니다.")

        with self._connect() as connection:
            product_code = self._generate_product_code(
                connection
            )

            cursor = connection.execute(
                """
                INSERT INTO products (
                    product_code,
                    platform,
                    platform_product_name,
                    product_name,
                    option_name,
                    supplier_id,
                    supplier_product_name,
                    purchase_price,
                    sale_price,
                    purchase_round,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    product_code,
                    self._clean_text(platform),
                    self._clean_text(platform_product_name),
                    cleaned_product_name,
                    self._clean_text(option_name),
                    supplier_id,
                    self._clean_text(supplier_product_name),
                    int(purchase_price),
                    int(sale_price),
                    self._clean_text(purchase_round),
                    1 if is_active else 0,
                ),
            )

            product_id = int(
                cursor.lastrowid
            )

            self._sync_default_supplier_link(
                connection,
                product_id=product_id,
                supplier_id=supplier_id,
                supplier_product_name=supplier_product_name,
                purchase_price=int(purchase_price),
            )

            connection.commit()

            return product_id

    def update_product(
        self,
        product_id: int,
        *,
        product_name: str,
        platform: str | None = None,
        platform_product_name: str | None = None,
        option_name: str | None = None,
        supplier_id: int | None = None,
        supplier_product_name: str | None = None,
        purchase_price: int = 0,
        sale_price: int = 0,
        purchase_round: str | None = None,
        is_active: bool = True,
    ) -> int:
        """기존 상품을 수정하고 변경된 행 수를 반환합니다."""

        cleaned_product_name = self._clean_text(product_name)

        if not cleaned_product_name:
            raise ValueError("상품명은 필수입니다.")

        if purchase_price < 0:
            raise ValueError("매입가는 0원 이상이어야 합니다.")

        if sale_price < 0:
            raise ValueError("판매가는 0원 이상이어야 합니다.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE products
                SET
                    platform = ?,
                    platform_product_name = ?,
                    product_name = ?,
                    option_name = ?,
                    supplier_id = ?,
                    supplier_product_name = ?,
                    purchase_price = ?,
                    sale_price = ?,
                    purchase_round = ?,
                    is_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    self._clean_text(platform),
                    self._clean_text(platform_product_name),
                    cleaned_product_name,
                    self._clean_text(option_name),
                    supplier_id,
                    self._clean_text(supplier_product_name),
                    int(purchase_price),
                    int(sale_price),
                    self._clean_text(purchase_round),
                    1 if is_active else 0,
                    product_id,
                ),
            )

            self._sync_default_supplier_link(
                connection,
                product_id=int(product_id),
                supplier_id=supplier_id,
                supplier_product_name=supplier_product_name,
                purchase_price=int(purchase_price),
            )

            connection.commit()

            return cursor.rowcount

    def update_notion_sync_result(
        self,
        product_id: int,
        *,
        notion_page_id: str | None,
        notion_last_edited_time: str | None,
        sync_status: str,
        sync_message: str | None = None,
    ) -> int:
        """상품의 Notion 페이지 연결과 마지막 동기화 결과를 저장합니다."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE products
                SET notion_page_id = ?,
                    notion_last_edited_time = ?,
                    notion_last_sync = CURRENT_TIMESTAMP,
                    sync_status = ?,
                    sync_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    self._clean_text(notion_page_id),
                    self._clean_text(notion_last_edited_time),
                    self._clean_text(sync_status) or "미동기화",
                    self._clean_text(sync_message),
                    int(product_id),
                ),
            )
            connection.commit()
            return cursor.rowcount

    def set_product_active(
        self,
        product_id: int,
        is_active: bool,
    ) -> int:
        """상품의 사용 여부를 변경합니다."""

        if not isinstance(product_id, int):
            raise ValueError(
                "상품 ID는 정수여야 합니다."
            )

        if product_id <= 0:
            raise ValueError(
                "상품 ID는 1 이상이어야 합니다."
            )

        active_value = (
            1 if is_active else 0
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE products
                SET
                    is_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    active_value,
                    product_id,
                ),
            )

            connection.commit()

            return cursor.rowcount