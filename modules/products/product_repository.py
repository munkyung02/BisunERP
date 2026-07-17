from typing import Any

from core.database import Database


class ProductRepository:
    """상품 데이터를 조회하고 저장하는 저장소입니다."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def get_products(
        self,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        """상품 목록을 조회합니다."""

        query = """
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
            WHERE 1 = 1
        """

        parameters: list[Any] = []

        if keyword:
            query += """
                AND (
                    p.product_name LIKE ?
                    OR p.platform_product_name LIKE ?
                    OR p.supplier_product_name LIKE ?
                    OR s.supplier_name LIKE ?
                )
            """

            search_keyword = f"%{keyword.strip()}%"

            parameters.extend(
                [
                    search_keyword,
                    search_keyword,
                    search_keyword,
                    search_keyword,
                ]
            )

        query += """
            ORDER BY
                p.is_active DESC,
                p.product_name ASC,
                p.id DESC
        """

        with self.database.connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [dict(row) for row in rows]

    def get_product_by_id(
        self,
        product_id: int,
    ) -> dict[str, Any] | None:
        """상품 ID로 상품 1건을 조회합니다."""

        with self.database.connect() as connection:
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

        if row is None:
            return None

        return dict(row)

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
        product_code: str | None = None,
    ) -> int:
        """상품을 새로 등록합니다."""

        product_name = product_name.strip()

        if not product_name:
            raise ValueError("상품명은 반드시 입력해야 합니다.")

        purchase_price = self._normalize_price(
            purchase_price,
            "매입가",
        )
        sale_price = self._normalize_price(
            sale_price,
            "판매가",
        )

        with self.database.connect() as connection:
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
                    is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    self._clean_text(product_code),
                    self._clean_text(platform),
                    self._clean_text(platform_product_name),
                    product_name,
                    self._clean_text(option_name),
                    supplier_id,
                    self._clean_text(supplier_product_name),
                    purchase_price,
                    sale_price,
                    self._clean_text(purchase_round),
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
        product_code: str | None = None,
        is_active: bool = True,
    ) -> int:
        """기존 상품 정보를 수정합니다."""

        product_name = product_name.strip()

        if not product_name:
            raise ValueError("상품명은 반드시 입력해야 합니다.")

        purchase_price = self._normalize_price(
            purchase_price,
            "매입가",
        )
        sale_price = self._normalize_price(
            sale_price,
            "판매가",
        )

        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE products
                SET
                    product_code = ?,
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
                    self._clean_text(product_code),
                    self._clean_text(platform),
                    self._clean_text(platform_product_name),
                    product_name,
                    self._clean_text(option_name),
                    supplier_id,
                    self._clean_text(supplier_product_name),
                    purchase_price,
                    sale_price,
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
        """상품의 사용 여부를 변경합니다."""

        with self.database.connect() as connection:
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

    def delete_product(
        self,
        product_id: int,
    ) -> int:
        """
        상품을 완전히 삭제합니다.

        실제 운영에서는 삭제보다 set_product_active(False)를
        사용하는 것이 안전합니다.
        """

        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM products
                WHERE id = ?
                """,
                (product_id,),
            )

            connection.commit()

        return cursor.rowcount

    @staticmethod
    def _clean_text(
        value: str | None,
    ) -> str | None:
        """빈 문자열을 None으로 정리합니다."""

        if value is None:
            return None

        cleaned_value = str(value).strip()

        return cleaned_value or None

    @staticmethod
    def _normalize_price(
        value: int | str | None,
        field_name: str,
    ) -> int:
        """가격 값을 0 이상의 정수로 변환합니다."""

        if value in (
            None,
            "",
        ):
            return 0

        try:
            normalized_value = int(
                str(value)
                .replace(",", "")
                .strip()
            )
        except ValueError as error:
            raise ValueError(
                f"{field_name}는 숫자로 입력해야 합니다."
            ) from error

        if normalized_value < 0:
            raise ValueError(
                f"{field_name}는 0 이상이어야 합니다."
            )

        return normalized_value