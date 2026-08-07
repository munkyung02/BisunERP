from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from modules.products.product_master_models import (
    MappingSummary,
    ProductMaster,
    SupplierSummary,
    UsageSummary,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ProductMasterRepository:
    """Read-only aggregation of the existing ERP product data."""

    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path).resolve()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"{self.database_path.as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def get_product_masters(
        self,
        product_ids: Iterable[int] | None = None,
    ) -> list[ProductMaster]:
        normalized_ids = sorted({int(value) for value in product_ids or []})
        if product_ids is not None and not normalized_ids:
            return []

        where_clause = ""
        parameters: list[int] = []
        if product_ids is not None:
            placeholders = ",".join("?" for _ in normalized_ids)
            where_clause = f"WHERE p.id IN ({placeholders})"
            parameters.extend(normalized_ids)

        query = f"""
            WITH supplier_totals AS (
                SELECT
                    ps.product_id,
                    COUNT(DISTINCT ps.supplier_id) AS supplier_count,
                    COUNT(DISTINCT CASE
                        WHEN ps.is_active = 1 AND s.is_active = 1
                        THEN ps.supplier_id
                    END) AS active_supplier_count,
                    COALESCE(MAX(CASE
                        WHEN ps.is_default = 1 THEN s.supplier_name
                    END), '') AS default_supplier
                FROM product_suppliers AS ps
                INNER JOIN suppliers AS s ON s.id = ps.supplier_id
                GROUP BY ps.product_id
            ),
            mapping_totals AS (
                SELECT
                    product_id,
                    COUNT(*) AS total_mapping_rules,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END)
                        AS confirmed_mapping_rules
                FROM product_mapping_rules
                GROUP BY product_id
            ),
            item_totals AS (
                SELECT
                    oi.product_id,
                    COUNT(*) AS mapped_order_items,
                    SUM(CASE
                        WHEN oi.mapping_status = '신규상품매핑' THEN 1 ELSE 0
                    END) AS new_product_mappings,
                    COALESCE(MAX(o.ordered_at), '') AS latest_order_date
                FROM order_items AS oi
                INNER JOIN orders AS o ON o.id = oi.order_id
                WHERE oi.product_id IS NOT NULL
                GROUP BY oi.product_id
            ),
            purchase_totals AS (
                SELECT
                    oi.product_id,
                    COUNT(*) AS purchase_history_count
                FROM purchase_orders AS po
                INNER JOIN order_items AS oi ON oi.id = po.order_item_id
                WHERE oi.product_id IS NOT NULL
                GROUP BY oi.product_id
            ),
            shipment_totals AS (
                SELECT
                    oi.product_id,
                    COUNT(*) AS shipment_history_count
                FROM shipments AS sh
                INNER JOIN order_items AS oi ON oi.id = sh.order_item_id
                WHERE oi.product_id IS NOT NULL
                GROUP BY oi.product_id
            )
            SELECT
                p.id,
                COALESCE(p.product_code, '') AS product_code,
                COALESCE(p.product_name, '') AS product_name,
                COALESCE(p.option_name, '') AS option_name,
                COALESCE(p.category, '') AS category,
                COALESCE(p.origin, '') AS origin,
                COALESCE(p.packaging_type, '') AS packaging_type,
                COALESCE(p.sale_unit, '') AS sale_unit,
                COALESCE(p.is_active, 0) AS is_active,
                COALESCE(st.supplier_count, 0) AS supplier_count,
                COALESCE(st.default_supplier, s.supplier_name, '')
                    AS default_supplier,
                COALESCE(st.active_supplier_count, 0)
                    AS active_supplier_count,
                COALESCE(mt.confirmed_mapping_rules, 0)
                    AS confirmed_mapping_rules,
                COALESCE(it.new_product_mappings, 0)
                    AS new_product_mappings,
                COALESCE(mt.total_mapping_rules, 0) AS total_mapping_rules,
                COALESCE(it.mapped_order_items, 0) AS mapped_order_items,
                COALESCE(pt.purchase_history_count, 0)
                    AS purchase_history_count,
                COALESCE(sht.shipment_history_count, 0)
                    AS shipment_history_count,
                COALESCE(it.latest_order_date, '') AS latest_order_date
            FROM products AS p
            LEFT JOIN suppliers AS s ON s.id = p.supplier_id
            LEFT JOIN supplier_totals AS st ON st.product_id = p.id
            LEFT JOIN mapping_totals AS mt ON mt.product_id = p.id
            LEFT JOIN item_totals AS it ON it.product_id = p.id
            LEFT JOIN purchase_totals AS pt ON pt.product_id = p.id
            LEFT JOIN shipment_totals AS sht ON sht.product_id = p.id
            {where_clause}
            ORDER BY p.is_active DESC, p.id DESC
        """

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._to_model(row) for row in rows]

    @staticmethod
    def _to_model(row: sqlite3.Row) -> ProductMaster:
        is_active = bool(int(row["is_active"] or 0))
        return ProductMaster(
            id=int(row["id"]),
            product_code=str(row["product_code"] or ""),
            product_name=str(row["product_name"] or ""),
            option_name=str(row["option_name"] or ""),
            category=str(row["category"] or ""),
            origin=str(row["origin"] or ""),
            packaging_type=str(row["packaging_type"] or ""),
            sale_unit=str(row["sale_unit"] or ""),
            is_active=is_active,
            status="사용" if is_active else "중지",
            supplier=SupplierSummary(
                supplier_count=int(row["supplier_count"] or 0),
                default_supplier=str(row["default_supplier"] or ""),
                active_supplier_count=int(row["active_supplier_count"] or 0),
            ),
            mapping=MappingSummary(
                confirmed_mapping_rules=int(
                    row["confirmed_mapping_rules"] or 0
                ),
                new_product_mappings=int(row["new_product_mappings"] or 0),
                total_mapping_rules=int(row["total_mapping_rules"] or 0),
            ),
            usage=UsageSummary(
                mapped_order_items=int(row["mapped_order_items"] or 0),
                purchase_history_count=int(row["purchase_history_count"] or 0),
                shipment_history_count=int(row["shipment_history_count"] or 0),
                latest_order_date=str(row["latest_order_date"] or ""),
            ),
        )
