import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ProductRepository:
    """상품 데이터 조회·등록·수정 Repository입니다."""

    def __init__(self, database_path: Path | None = None) -> None:
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
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """상품 목록과 연결된 공급처명을 조회합니다."""

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
                )
                """
            )

            parameters.extend([search_keyword] * 7)

        if active_only:
            conditions.append("p.is_active = 1")

        where_clause = ""

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

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
                p.created_at,
                p.updated_at
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

        return [dict(row) for row in rows]

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

            connection.commit()

            return int(cursor.lastrowid)

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

            connection.commit()

            return cursor.rowcount

    def set_product_active(
        self,
        product_id: int,
        is_active: bool,
    ) -> int:
        """상품의 활성·비활성 상태를 변경합니다."""

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
                    1 if is_active else 0,
                    product_id,
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