from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ChannelShipmentExportRepository:
    """Reads export candidates and records successful channel exports."""

    COUPANG = "쿠팡"
    SMARTSTORE = "스마트스토어"
    GMARKET = "Gmarket"

    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS channel_shipment_export_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shipment_id INTEGER NOT NULL,
                    order_item_id INTEGER NOT NULL,
                    metadata_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    export_batch_id TEXT NOT NULL,
                    export_file TEXT NOT NULL,
                    is_reexport INTEGER NOT NULL DEFAULT 0,
                    exported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
                    FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE,
                    FOREIGN KEY (metadata_id)
                        REFERENCES channel_order_item_metadata(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_channel_export_shipment_platform
                ON channel_shipment_export_history(shipment_id, platform);

                CREATE INDEX IF NOT EXISTS idx_channel_export_batch
                ON channel_shipment_export_history(export_batch_id);
                """
            )
            connection.commit()

    def get_coupang_candidates(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
        include_exported: bool = False,
    ) -> list[dict[str, Any]]:
        conditions = [
            "m.platform = ?",
            "o.shipment_status = ?",
            "TRIM(COALESCE(sh.tracking_number, '')) != ''",
        ]
        parameters: list[Any] = [self.COUPANG, "배송중"]

        normalized_ids = sorted({int(value) for value in shipment_ids or []})
        if shipment_ids is not None:
            if not normalized_ids:
                return []
            placeholders = ",".join("?" for _ in normalized_ids)
            conditions.append(f"sh.id IN ({placeholders})")
            parameters.extend(normalized_ids)

        if not include_exported:
            conditions.append(
                """
                NOT EXISTS (
                    SELECT 1
                    FROM channel_shipment_export_history h
                    WHERE h.shipment_id = sh.id
                      AND h.platform = m.platform
                )
                """
            )

        query = f"""
            SELECT
                sh.id AS shipment_id,
                sh.order_id,
                sh.order_item_id,
                sh.courier_name,
                sh.tracking_number,
                m.id AS metadata_id,
                m.platform,
                m.channel_order_number,
                m.raw_source_json
            FROM shipments sh
            INNER JOIN orders o ON o.id = sh.order_id
            INNER JOIN channel_order_item_metadata m
                ON m.order_item_id = sh.order_item_id
            WHERE {' AND '.join(conditions)}
            ORDER BY sh.id
        """

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def get_smartstore_candidates(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
        include_exported: bool = False,
    ) -> list[dict[str, Any]]:
        conditions = [
            "m.platform = ?",
            "o.shipment_status = ?",
            "TRIM(COALESCE(sh.tracking_number, '')) != ''",
        ]
        parameters: list[Any] = [self.SMARTSTORE, "배송중"]
        self._add_shipment_id_condition(
            conditions,
            parameters,
            shipment_ids,
        )
        if shipment_ids is not None and not parameters[2:]:
            return []

        if not include_exported:
            conditions.append(
                """
                NOT EXISTS (
                    SELECT 1
                    FROM channel_shipment_export_history h
                    WHERE h.shipment_id = sh.id
                      AND h.platform = m.platform
                )
                """
            )

        query = f"""
            SELECT
                sh.id AS shipment_id,
                sh.order_id,
                sh.order_item_id,
                sh.courier_name,
                sh.tracking_number,
                m.id AS metadata_id,
                m.platform,
                m.channel_order_number,
                m.channel_item_number,
                m.delivery_method,
                m.raw_source_json
            FROM shipments sh
            INNER JOIN orders o ON o.id = sh.order_id
            INNER JOIN channel_order_item_metadata m
                ON m.order_item_id = sh.order_item_id
            WHERE {' AND '.join(conditions)}
            ORDER BY sh.id
        """

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def count_smartstore_missing_metadata(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
    ) -> int:
        conditions = [
            "o.platform = ?",
            "o.shipment_status = ?",
            "TRIM(COALESCE(sh.tracking_number, '')) != ''",
            "m.id IS NULL",
        ]
        parameters: list[Any] = [self.SMARTSTORE, "배송중"]
        self._add_shipment_id_condition(
            conditions,
            parameters,
            shipment_ids,
        )
        if shipment_ids is not None and not parameters[2:]:
            return 0

        query = f"""
            SELECT COUNT(*)
            FROM shipments sh
            INNER JOIN orders o ON o.id = sh.order_id
            LEFT JOIN channel_order_item_metadata m
                ON m.order_item_id = sh.order_item_id
            WHERE {' AND '.join(conditions)}
        """
        with self._connect() as connection:
            return int(connection.execute(query, parameters).fetchone()[0])

    def get_gmarket_candidates(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
        include_exported: bool = False,
    ) -> list[dict[str, Any]]:
        conditions = [
            "m.platform = ?",
            "o.shipment_status = ?",
            "TRIM(COALESCE(sh.courier_name, '')) != ''",
            "TRIM(COALESCE(sh.tracking_number, '')) != ''",
        ]
        parameters: list[Any] = [self.GMARKET, "배송중"]
        self._add_shipment_id_condition(
            conditions,
            parameters,
            shipment_ids,
        )
        if shipment_ids is not None and not parameters[2:]:
            return []

        if not include_exported:
            conditions.append(
                """
                NOT EXISTS (
                    SELECT 1
                    FROM channel_shipment_export_history h
                    WHERE h.shipment_id = sh.id
                      AND h.platform = m.platform
                )
                """
            )

        query = f"""
            SELECT
                sh.id AS shipment_id,
                sh.order_id,
                sh.order_item_id,
                sh.courier_name,
                sh.tracking_number,
                m.id AS metadata_id,
                m.platform,
                m.original_platform_name,
                m.sales_channel,
                m.channel_order_number,
                m.bundle_shipment_number,
                m.external_order_id,
                m.product_identifier,
                m.raw_source_json
            FROM shipments sh
            INNER JOIN orders o ON o.id = sh.order_id
            INNER JOIN channel_order_item_metadata m
                ON m.order_item_id = sh.order_item_id
            WHERE {' AND '.join(conditions)}
            ORDER BY sh.id
        """

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def count_gmarket_missing_metadata(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
    ) -> int:
        conditions = [
            "o.platform = ?",
            "o.shipment_status = ?",
            "TRIM(COALESCE(sh.courier_name, '')) != ''",
            "TRIM(COALESCE(sh.tracking_number, '')) != ''",
            "m.id IS NULL",
        ]
        parameters: list[Any] = [self.GMARKET, self.GMARKET, "배송중"]
        self._add_shipment_id_condition(
            conditions,
            parameters,
            shipment_ids,
        )
        if shipment_ids is not None and not parameters[3:]:
            return 0

        query = f"""
            SELECT COUNT(*)
            FROM shipments sh
            INNER JOIN orders o ON o.id = sh.order_id
            LEFT JOIN channel_order_item_metadata m
                ON m.order_item_id = sh.order_item_id
               AND m.platform = ?
            WHERE {' AND '.join(conditions)}
        """
        with self._connect() as connection:
            return int(connection.execute(query, parameters).fetchone()[0])

    @staticmethod
    def _add_shipment_id_condition(
        conditions: list[str],
        parameters: list[Any],
        shipment_ids: Iterable[int] | None,
    ) -> None:
        if shipment_ids is None:
            return
        normalized_ids = sorted({int(value) for value in shipment_ids})
        if not normalized_ids:
            return
        placeholders = ",".join("?" for _ in normalized_ids)
        conditions.append(f"sh.id IN ({placeholders})")
        parameters.extend(normalized_ids)

    def record_export(
        self,
        *,
        rows: list[dict[str, Any]],
        export_batch_id: str,
        export_file: str,
        is_reexport: bool,
    ) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO channel_shipment_export_history (
                    shipment_id, order_item_id, metadata_id, platform,
                    export_batch_id, export_file, is_reexport
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        int(row["shipment_id"]),
                        int(row["order_item_id"]),
                        int(row["metadata_id"]),
                        str(row["platform"]),
                        str(export_batch_id),
                        str(export_file),
                        1 if is_reexport else 0,
                    )
                    for row in rows
                ],
            )
            connection.commit()

    def get_history_for_shipment(self, shipment_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM channel_shipment_export_history
                WHERE shipment_id = ?
                ORDER BY id
                """,
                (int(shipment_id),),
            ).fetchall()
        return [dict(row) for row in rows]
