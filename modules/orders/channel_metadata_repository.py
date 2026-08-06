from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ChannelMetadataRepository:
    """Persists original marketplace identifiers for an ERP order item."""

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
                CREATE TABLE IF NOT EXISTS channel_order_item_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    order_item_id INTEGER NOT NULL UNIQUE,
                    platform TEXT NOT NULL DEFAULT '',
                    original_platform_name TEXT NOT NULL DEFAULT '',
                    channel_order_number TEXT NOT NULL DEFAULT '',
                    channel_item_number TEXT NOT NULL DEFAULT '',
                    bundle_shipment_number TEXT NOT NULL DEFAULT '',
                    option_id TEXT NOT NULL DEFAULT '',
                    seller_product_code TEXT NOT NULL DEFAULT '',
                    vendor_item_id TEXT NOT NULL DEFAULT '',
                    shipment_box_id TEXT NOT NULL DEFAULT '',
                    external_order_id TEXT NOT NULL DEFAULT '',
                    delivery_method TEXT NOT NULL DEFAULT '',
                    sales_channel TEXT NOT NULL DEFAULT '',
                    product_identifier TEXT NOT NULL DEFAULT '',
                    raw_source_json TEXT NOT NULL DEFAULT '{}',
                    source_file TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
                    FOREIGN KEY(order_item_id) REFERENCES order_items(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_channel_metadata_order
                ON channel_order_item_metadata(order_id);

                CREATE INDEX IF NOT EXISTS idx_channel_metadata_channel_order
                ON channel_order_item_metadata(platform, channel_order_number);

                CREATE INDEX IF NOT EXISTS idx_channel_metadata_channel_item
                ON channel_order_item_metadata(platform, channel_item_number);
                """
            )
            connection.commit()

    def save_with_connection(
        self,
        connection: sqlite3.Connection,
        *,
        order_id: int,
        order_item_id: int,
        metadata: dict[str, Any],
    ) -> None:
        """Save metadata using the caller's order transaction."""
        if not isinstance(metadata, dict):
            raise TypeError("채널 메타데이터는 dict 형식이어야 합니다.")

        raw_source = metadata.get("raw_source_row", {})
        if not isinstance(raw_source, dict):
            raise TypeError("원본 주문 행은 dict 형식이어야 합니다.")
        raw_source_json = json.dumps(
            raw_source,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )

        connection.execute(
            """
            INSERT INTO channel_order_item_metadata (
                order_id, order_item_id, platform, original_platform_name,
                channel_order_number, channel_item_number,
                bundle_shipment_number, option_id, seller_product_code,
                vendor_item_id, shipment_box_id, external_order_id,
                delivery_method, sales_channel, product_identifier,
                raw_source_json, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(order_id),
                int(order_item_id),
                self._text(metadata.get("platform")),
                self._text(metadata.get("original_platform_name")),
                self._text(metadata.get("channel_order_number")),
                self._text(metadata.get("channel_item_number")),
                self._text(metadata.get("bundle_shipment_number")),
                self._text(metadata.get("option_id")),
                self._text(metadata.get("seller_product_code")),
                self._text(metadata.get("vendor_item_id")),
                self._text(metadata.get("shipment_box_id")),
                self._text(metadata.get("external_order_id")),
                self._text(metadata.get("delivery_method")),
                self._text(metadata.get("sales_channel")),
                self._text(metadata.get("product_identifier")),
                raw_source_json,
                self._text(metadata.get("source_file")),
            ),
        )

    def get_by_order_item_id(self, order_item_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM channel_order_item_metadata
                WHERE order_item_id = ?
                """,
                (int(order_item_id),),
            ).fetchone()
        return dict(row) if row is not None else None

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value).strip()
