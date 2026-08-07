from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from modules.products.product_master_models import (
    ChannelVisibilitySummary,
    ConfirmedChannelAlias,
    MappingSummary,
    ObservedChannelAlias,
    ObservedChannelIdentifier,
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
            result_ids = [int(row["id"]) for row in rows]
            channel_by_product = self._get_channel_visibility(
                connection,
                result_ids,
            )
        return [
            self._to_model(
                row,
                channel_by_product.get(
                    int(row["id"]),
                    self._empty_channel_visibility(),
                ),
            )
            for row in rows
        ]

    def get_channel_visibility(
        self,
        product_ids: Iterable[int],
    ) -> dict[int, ChannelVisibilitySummary]:
        """Return channel visibility in one read-only batch."""
        normalized_ids = sorted({int(value) for value in product_ids})
        if not normalized_ids:
            return {}
        with self._connect() as connection:
            return self._get_channel_visibility(connection, normalized_ids)

    def _get_channel_visibility(
        self,
        connection: sqlite3.Connection,
        product_ids: list[int],
    ) -> dict[int, ChannelVisibilitySummary]:
        if not product_ids:
            return {}

        placeholders = ",".join("?" for _ in product_ids)
        parameters = list(product_ids)
        confirmed_rows = connection.execute(
            f"""
            SELECT product_id, platform, platform_product_name,
                   option_name, is_active
            FROM product_mapping_rules
            WHERE product_id IN ({placeholders})
            ORDER BY product_id, platform, platform_product_name, option_name
            """,
            parameters,
        ).fetchall()

        metadata_exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'channel_order_item_metadata'
            """
        ).fetchone() is not None
        if not metadata_exists:
            return self._assemble_channel_visibility(
                product_ids,
                confirmed_rows,
                [],
                [],
                [],
            )

        observed_rows = connection.execute(
            f"""
            SELECT
                oi.product_id,
                COALESCE(NULLIF(m.platform, ''), o.platform, '') AS platform,
                oi.platform_product_name,
                COALESCE(oi.option_name, '') AS option_name,
                COALESCE(MIN(o.ordered_at), '') AS first_seen,
                COALESCE(MAX(o.ordered_at), '') AS latest_seen,
                COUNT(*) AS observed_count
            FROM order_items AS oi
            INNER JOIN orders AS o ON o.id = oi.order_id
            LEFT JOIN channel_order_item_metadata AS m
                ON m.order_item_id = oi.id
            WHERE oi.product_id IN ({placeholders})
            GROUP BY oi.product_id,
                     COALESCE(NULLIF(m.platform, ''), o.platform, ''),
                     oi.platform_product_name,
                     COALESCE(oi.option_name, '')
            ORDER BY oi.product_id, platform,
                     oi.platform_product_name, option_name
            """,
            parameters,
        ).fetchall()

        identifier_rows = connection.execute(
            f"""
            WITH identifiers AS (
                SELECT oi.product_id, m.platform, 'vendor_item_id' AS kind,
                       m.vendor_item_id AS value
                FROM channel_order_item_metadata AS m
                INNER JOIN order_items AS oi ON oi.id = m.order_item_id
                WHERE m.vendor_item_id != ''
                UNION ALL
                SELECT oi.product_id, m.platform, 'seller_product_code',
                       m.seller_product_code
                FROM channel_order_item_metadata AS m
                INNER JOIN order_items AS oi ON oi.id = m.order_item_id
                WHERE m.seller_product_code != ''
                UNION ALL
                SELECT oi.product_id, m.platform, 'product_identifier',
                       m.product_identifier
                FROM channel_order_item_metadata AS m
                INNER JOIN order_items AS oi ON oi.id = m.order_item_id
                WHERE m.product_identifier != ''
                UNION ALL
                SELECT oi.product_id, m.platform, 'option_id', m.option_id
                FROM channel_order_item_metadata AS m
                INNER JOIN order_items AS oi ON oi.id = m.order_item_id
                WHERE m.option_id != ''
            ), grouped AS (
                SELECT product_id, platform, kind, value, COUNT(*) AS seen
                FROM identifiers
                GROUP BY product_id, platform, kind, value
            ), conflicts AS (
                SELECT platform, kind, value
                FROM identifiers
                GROUP BY platform, kind, value
                HAVING COUNT(DISTINCT product_id) > 1
            )
            SELECT g.product_id, g.platform, g.kind, g.value, g.seen,
                   CASE WHEN c.value IS NULL THEN 0 ELSE 1 END AS is_conflict
            FROM grouped AS g
            LEFT JOIN conflicts AS c
              ON c.platform = g.platform
             AND c.kind = g.kind
             AND c.value = g.value
            WHERE g.product_id IN ({placeholders})
            ORDER BY g.product_id, g.platform, g.kind, g.value
            """,
            parameters,
        ).fetchall()

        metadata_rows = connection.execute(
            f"""
            SELECT oi.product_id,
                   COUNT(*) AS mapped_count,
                   COUNT(m.id) AS metadata_count
            FROM order_items AS oi
            LEFT JOIN channel_order_item_metadata AS m
                ON m.order_item_id = oi.id
            WHERE oi.product_id IN ({placeholders})
            GROUP BY oi.product_id
            """,
            parameters,
        ).fetchall()
        return self._assemble_channel_visibility(
            product_ids,
            confirmed_rows,
            observed_rows,
            identifier_rows,
            metadata_rows,
        )

    @classmethod
    def _assemble_channel_visibility(
        cls,
        product_ids: list[int],
        confirmed_rows: list[sqlite3.Row],
        observed_rows: list[sqlite3.Row],
        identifier_rows: list[sqlite3.Row],
        metadata_rows: list[sqlite3.Row],
    ) -> dict[int, ChannelVisibilitySummary]:
        confirmed: dict[int, list[ConfirmedChannelAlias]] = {}
        observed: dict[int, list[ObservedChannelAlias]] = {}
        identifiers: dict[int, list[ObservedChannelIdentifier]] = {}
        metadata_counts = {
            int(row["product_id"]): (
                int(row["mapped_count"] or 0),
                int(row["metadata_count"] or 0),
            )
            for row in metadata_rows
        }
        for row in confirmed_rows:
            confirmed.setdefault(int(row["product_id"]), []).append(
                ConfirmedChannelAlias(
                    platform=str(row["platform"] or ""),
                    platform_product_name=str(
                        row["platform_product_name"] or ""
                    ),
                    option_name=str(row["option_name"] or ""),
                    is_active=bool(int(row["is_active"] or 0)),
                )
            )
        for row in observed_rows:
            observed.setdefault(int(row["product_id"]), []).append(
                ObservedChannelAlias(
                    platform=str(row["platform"] or ""),
                    platform_product_name=str(
                        row["platform_product_name"] or ""
                    ),
                    option_name=str(row["option_name"] or ""),
                    first_seen=str(row["first_seen"] or ""),
                    latest_seen=str(row["latest_seen"] or ""),
                    observed_count=int(row["observed_count"] or 0),
                )
            )
        for row in identifier_rows:
            identifiers.setdefault(int(row["product_id"]), []).append(
                ObservedChannelIdentifier(
                    platform=str(row["platform"] or ""),
                    identifier_type=str(row["kind"] or ""),
                    value=str(row["value"] or ""),
                    observed_count=int(row["seen"] or 0),
                    is_conflict=bool(int(row["is_conflict"] or 0)),
                )
            )

        result: dict[int, ChannelVisibilitySummary] = {}
        for product_id in product_ids:
            product_identifiers = tuple(identifiers.get(product_id, []))
            mapped_count, metadata_count = metadata_counts.get(
                product_id, (0, 0)
            )
            if metadata_count == 0:
                metadata_status = "Unavailable"
            elif metadata_count < mapped_count:
                metadata_status = "Partial"
            else:
                metadata_status = "Available"
            result[product_id] = ChannelVisibilitySummary(
                confirmed_aliases=tuple(confirmed.get(product_id, [])),
                observed_aliases=tuple(observed.get(product_id, [])),
                observed_identifiers=product_identifiers,
                conflict_status=(
                    "Conflict"
                    if any(item.is_conflict for item in product_identifiers)
                    else "No Conflict"
                ),
                metadata_status=metadata_status,
            )
        return result

    @staticmethod
    def _empty_channel_visibility() -> ChannelVisibilitySummary:
        return ChannelVisibilitySummary(
            confirmed_aliases=(),
            observed_aliases=(),
            observed_identifiers=(),
            conflict_status="No Conflict",
            metadata_status="Unavailable",
        )

    @staticmethod
    def _to_model(
        row: sqlite3.Row,
        channel: ChannelVisibilitySummary,
    ) -> ProductMaster:
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
            channel=channel,
        )
