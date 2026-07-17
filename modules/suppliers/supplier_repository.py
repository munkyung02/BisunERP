import sqlite3
from pathlib import Path
from typing import Any


class SupplierRepository:
    """공급처 데이터베이스 처리 클래스입니다."""

    def __init__(
        self,
        db_path: str | Path = "data/bisun_erp.db",
    ) -> None:
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        """SQLite 연결을 생성합니다."""

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row

        return connection

    @staticmethod
    def _row_to_dict(
        row: sqlite3.Row | None,
    ) -> dict[str, Any] | None:
        """SQLite Row를 일반 딕셔너리로 변환합니다."""

        if row is None:
            return None

        return dict(row)

    def get_suppliers(
        self,
        keyword: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """공급처 목록을 조회합니다."""

        query = """
            SELECT
                id,
                supplier_code,
                supplier_name,
                contact_name,
                phone,
                email,
                bank_name,
                bank_account,
                account_holder,
                address,
                memo,
                is_active,
                created_at,
                updated_at
            FROM suppliers
            WHERE 1 = 1
        """

        params: list[Any] = []

        if keyword:
            search_keyword = f"%{keyword.strip()}%"

            query += """
                AND (
                    supplier_code LIKE ?
                    OR supplier_name LIKE ?
                    OR contact_name LIKE ?
                    OR phone LIKE ?
                    OR email LIKE ?
                    OR bank_name LIKE ?
                    OR bank_account LIKE ?
                    OR account_holder LIKE ?
                    OR address LIKE ?
                    OR memo LIKE ?
                )
            """

            params.extend(
                [search_keyword] * 10
            )

        if active_only:
            query += """
                AND is_active = 1
            """

        query += """
            ORDER BY
                is_active DESC,
                supplier_name ASC,
                id DESC
        """

        with self._connect() as connection:
            rows = connection.execute(
                query,
                params,
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def get_supplier_by_id(
        self,
        supplier_id: int,
    ) -> dict[str, Any] | None:
        """공급처 ID로 한 건을 조회합니다."""

        query = """
            SELECT
                id,
                supplier_code,
                supplier_name,
                contact_name,
                phone,
                email,
                bank_name,
                bank_account,
                account_holder,
                address,
                memo,
                is_active,
                created_at,
                updated_at
            FROM suppliers
            WHERE id = ?
        """

        with self._connect() as connection:
            row = connection.execute(
                query,
                (supplier_id,),
            ).fetchone()

        return self._row_to_dict(row)

    def create_supplier(
        self,
        *,
        supplier_name: str,
        manager_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        bank_name: str | None = None,
        account_number: str | None = None,
        account_holder: str | None = None,
        address: str | None = None,
        memo: str | None = None,
    ) -> int:
        """새 공급처를 등록하고 생성된 ID를 반환합니다."""

        supplier_name = supplier_name.strip()

        if not supplier_name:
            raise ValueError(
                "공급처명은 반드시 입력해야 합니다."
            )

        supplier_code = self._generate_supplier_code()

        query = """
            INSERT INTO suppliers (
                supplier_code,
                supplier_name,
                contact_name,
                phone,
                email,
                bank_name,
                bank_account,
                account_holder,
                address,
                memo,
                is_active,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
        """

        values = (
            supplier_code,
            supplier_name,
            self._clean_text(manager_name),
            self._clean_text(phone),
            self._clean_text(email),
            self._clean_text(bank_name),
            self._clean_text(account_number),
            self._clean_text(account_holder),
            self._clean_text(address),
            self._clean_text(memo),
        )

        with self._connect() as connection:
            cursor = connection.execute(
                query,
                values,
            )

            connection.commit()

            return int(cursor.lastrowid)

    def update_supplier(
        self,
        supplier_id: int,
        *,
        supplier_name: str,
        manager_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        bank_name: str | None = None,
        account_number: str | None = None,
        account_holder: str | None = None,
        address: str | None = None,
        memo: str | None = None,
        is_active: bool = True,
    ) -> int:
        """공급처 정보를 수정하고 변경된 행 수를 반환합니다."""

        supplier_name = supplier_name.strip()

        if not supplier_name:
            raise ValueError(
                "공급처명은 반드시 입력해야 합니다."
            )

        query = """
            UPDATE suppliers
            SET
                supplier_name = ?,
                contact_name = ?,
                phone = ?,
                email = ?,
                bank_name = ?,
                bank_account = ?,
                account_holder = ?,
                address = ?,
                memo = ?,
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """

        values = (
            supplier_name,
            self._clean_text(manager_name),
            self._clean_text(phone),
            self._clean_text(email),
            self._clean_text(bank_name),
            self._clean_text(account_number),
            self._clean_text(account_holder),
            self._clean_text(address),
            self._clean_text(memo),
            1 if is_active else 0,
            supplier_id,
        )

        with self._connect() as connection:
            cursor = connection.execute(
                query,
                values,
            )

            connection.commit()

            return cursor.rowcount

    def set_supplier_active(
        self,
        supplier_id: int,
        is_active: bool,
    ) -> int:
        """공급처의 활성·비활성 상태를 변경합니다."""

        query = """
            UPDATE suppliers
            SET
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """

        with self._connect() as connection:
            cursor = connection.execute(
                query,
                (
                    1 if is_active else 0,
                    supplier_id,
                ),
            )

            connection.commit()

            return cursor.rowcount

    def _generate_supplier_code(
        self,
    ) -> str:
        """새 공급처 코드를 생성합니다."""

        query = """
            SELECT COALESCE(MAX(id), 0) + 1
            FROM suppliers
        """

        with self._connect() as connection:
            next_number = connection.execute(
                query
            ).fetchone()[0]

        return f"SUP-{int(next_number):04d}"

    @staticmethod
    def _clean_text(
        value: str | None,
    ) -> str | None:
        """공백 문자열을 None으로 정리합니다."""

        if value is None:
            return None

        cleaned_value = value.strip()

        return cleaned_value or None