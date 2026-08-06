from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class PurchaseDashboardRepository:
    """구매 통계 화면에서 사용하는 읽기 전용 Repository입니다."""

    def __init__(
        self,
        database_path: str | Path | None = None,
    ) -> None:
        self.database_path = Path(database_path or DATABASE_PATH)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _purchase_columns(self) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "PRAGMA table_info(purchase_orders)"
            ).fetchall()

        return {str(row["name"]) for row in rows}

    def get_kpi_summary(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        columns = self._purchase_columns()
        item_amount_sql = (
            "COALESCE(item_amount, 0)"
            if "item_amount" in columns
            else "0"
        )
        shipping_fee_sql = (
            "COALESCE(shipping_fee, 0)"
            if "shipping_fee" in columns
            else "0"
        )
        unit_price_sql = (
            "COALESCE(unit_price, 0)"
            if "unit_price" in columns
            else "0"
        )

        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS purchase_count,
                    COALESCE(SUM(quantity), 0) AS total_quantity,
                    COALESCE(SUM({item_amount_sql}), 0)
                        AS total_item_amount,
                    COALESCE(SUM({shipping_fee_sql}), 0)
                        AS total_shipping_fee,
                    COALESCE(
                        SUM({item_amount_sql} + {shipping_fee_sql}),
                        0
                    ) AS grand_total,
                    COUNT(DISTINCT supplier_id)
                        AS supplier_count,
                    COALESCE(
                        AVG(NULLIF({unit_price_sql}, 0)),
                        0
                    ) AS average_unit_price
                FROM purchase_orders
                WHERE purchase_status = '발주완료'
                  AND DATE(
                        COALESCE(purchased_at, created_at),
                        'localtime'
                      )
                      BETWEEN DATE(?) AND DATE(?)
                """,
                (start_date, end_date),
            ).fetchone()

            pending_row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM purchase_orders
                WHERE purchase_status = '발주대기'
                """
            ).fetchone()

        result = dict(row)
        result["pending_count"] = int(pending_row["count"] or 0)
        return result

    def get_today_summary(self) -> dict[str, Any]:
        today = date.today().isoformat()
        return self.get_kpi_summary(
            start_date=today,
            end_date=today,
        )

    def get_supplier_ranking(
        self,
        *,
        start_date: str,
        end_date: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        columns = self._purchase_columns()
        item_amount_sql = (
            "COALESCE(item_amount, 0)"
            if "item_amount" in columns
            else "0"
        )
        shipping_fee_sql = (
            "COALESCE(shipping_fee, 0)"
            if "shipping_fee" in columns
            else "0"
        )

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    supplier_id,
                    COALESCE(
                        NULLIF(TRIM(supplier_name), ''),
                        '공급처 미지정'
                    ) AS supplier_name,
                    COUNT(*) AS purchase_count,
                    COALESCE(SUM(quantity), 0) AS total_quantity,
                    COALESCE(SUM({item_amount_sql}), 0)
                        AS total_item_amount,
                    COALESCE(SUM({shipping_fee_sql}), 0)
                        AS total_shipping_fee,
                    COALESCE(
                        SUM({item_amount_sql} + {shipping_fee_sql}),
                        0
                    ) AS grand_total
                FROM purchase_orders
                WHERE purchase_status = '발주완료'
                  AND DATE(
                        COALESCE(purchased_at, created_at),
                        'localtime'
                      )
                      BETWEEN DATE(?) AND DATE(?)
                GROUP BY supplier_id, supplier_name
                ORDER BY
                    grand_total DESC,
                    total_quantity DESC,
                    supplier_name
                LIMIT ?
                """,
                (start_date, end_date, int(limit)),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_product_ranking(
        self,
        *,
        start_date: str,
        end_date: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        columns = self._purchase_columns()
        item_amount_sql = (
            "COALESCE(item_amount, 0)"
            if "item_amount" in columns
            else "0"
        )
        unit_price_sql = (
            "COALESCE(unit_price, 0)"
            if "unit_price" in columns
            else "0"
        )
        product_code_select = (
            "supplier_product_code"
            if "supplier_product_code" in columns
            else "NULL"
        )

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    {product_code_select} AS supplier_product_code,
                    COALESCE(
                        NULLIF(TRIM(product_name), ''),
                        '상품명 미지정'
                    ) AS product_name,
                    COUNT(*) AS purchase_count,
                    COALESCE(SUM(quantity), 0) AS total_quantity,
                    COALESCE(
                        AVG(NULLIF({unit_price_sql}, 0)),
                        0
                    ) AS average_unit_price,
                    COALESCE(SUM({item_amount_sql}), 0)
                        AS total_item_amount
                FROM purchase_orders
                WHERE purchase_status = '발주완료'
                  AND DATE(
                        COALESCE(purchased_at, created_at),
                        'localtime'
                      )
                      BETWEEN DATE(?) AND DATE(?)
                GROUP BY
                    {product_code_select},
                    product_name
                ORDER BY
                    total_item_amount DESC,
                    total_quantity DESC,
                    product_name
                LIMIT ?
                """,
                (start_date, end_date, int(limit)),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_monthly_statistics(
        self,
        *,
        months: int = 12,
    ) -> list[dict[str, Any]]:
        columns = self._purchase_columns()
        item_amount_sql = (
            "COALESCE(item_amount, 0)"
            if "item_amount" in columns
            else "0"
        )
        shipping_fee_sql = (
            "COALESCE(shipping_fee, 0)"
            if "shipping_fee" in columns
            else "0"
        )

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    STRFTIME(
                        '%Y-%m',
                        COALESCE(purchased_at, created_at),
                        'localtime'
                    ) AS month,
                    COUNT(*) AS purchase_count,
                    COALESCE(SUM(quantity), 0) AS total_quantity,
                    COUNT(DISTINCT supplier_id)
                        AS supplier_count,
                    COALESCE(SUM({item_amount_sql}), 0)
                        AS total_item_amount,
                    COALESCE(SUM({shipping_fee_sql}), 0)
                        AS total_shipping_fee,
                    COALESCE(
                        SUM({item_amount_sql} + {shipping_fee_sql}),
                        0
                    ) AS grand_total
                FROM purchase_orders
                WHERE purchase_status = '발주완료'
                  AND DATE(
                        COALESCE(purchased_at, created_at),
                        'localtime'
                      )
                      >= DATE(
                            'now',
                            'start of month',
                            ?,
                            'localtime'
                      )
                GROUP BY month
                ORDER BY month
                """,
                (f"-{max(0, int(months) - 1)} months",),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_inactive_suppliers(
        self,
        *,
        inactive_days: int = 90,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    s.id AS supplier_id,
                    s.supplier_name,
                    MAX(
                        DATE(
                            COALESCE(
                                po.purchased_at,
                                po.created_at
                            ),
                            'localtime'
                        )
                    ) AS last_purchase_date,
                    CAST(
                        JULIANDAY('now', 'localtime')
                        - JULIANDAY(
                            MAX(
                                DATE(
                                    COALESCE(
                                        po.purchased_at,
                                        po.created_at
                                    ),
                                    'localtime'
                                )
                            )
                        )
                        AS INTEGER
                    ) AS inactive_days
                FROM suppliers AS s
                LEFT JOIN purchase_orders AS po
                    ON po.supplier_id = s.id
                   AND po.purchase_status = '발주완료'
                WHERE COALESCE(s.is_active, 1) = 1
                GROUP BY s.id, s.supplier_name
                HAVING
                    last_purchase_date IS NULL
                    OR inactive_days >= ?
                ORDER BY
                    CASE
                        WHEN last_purchase_date IS NULL THEN 0
                        ELSE 1
                    END,
                    inactive_days DESC,
                    s.supplier_name
                LIMIT ?
                """,
                (int(inactive_days), int(limit)),
            ).fetchall()

        return [dict(row) for row in rows]