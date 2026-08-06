from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ReadOnlyAssistantRepository:
    """Assistant SELECT queries through a query-only SQLite connection."""

    MAX_ROWS = 100

    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path).resolve()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"{self.database_path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def _select(self, query: str, parameters: Sequence[Any] = ()) -> tuple[list[dict[str, Any]], bool]:
        with self._connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchmany(self.MAX_ROWS + 1)
        return [dict(row) for row in rows[: self.MAX_ROWS]], len(rows) > self.MAX_ROWS

    def get_today_order_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM orders "
                "WHERE DATE(ordered_at)=DATE('now','localtime')"
            ).fetchone()
        return int(row["count"] or 0)

    def get_unmapped_orders(self) -> tuple[list[dict[str, Any]], bool]:
        return self._select(
            self._order_query(
                "o.mapping_status != ? OR EXISTS (SELECT 1 FROM order_items x "
                "WHERE x.order_id=o.id AND (x.product_id IS NULL OR x.mapping_status != ?))"
            ),
            ("매핑완료", "매핑완료"),
        )

    def get_purchase_pending_orders(self) -> tuple[list[dict[str, Any]], bool]:
        return self._select(self._order_query("o.purchase_status = ?"), ("발주대기",))

    def get_shipment_pending_orders(self) -> tuple[list[dict[str, Any]], bool]:
        return self._select(
            """
            SELECT o.order_number, o.platform, o.ordered_at,
                   po.product_name AS item_summary, po.quantity AS total_quantity,
                   o.mapping_status, po.purchase_status, o.shipment_status
            FROM purchase_orders po JOIN orders o ON o.id=po.order_id
            LEFT JOIN shipments sh ON sh.order_item_id=po.order_item_id
            WHERE sh.id IS NULL AND po.purchase_status NOT IN (?, ?)
            ORDER BY COALESCE(po.purchased_at,po.created_at) DESC, po.id DESC
            """,
            ("발주취소", "취소"),
        )

    def get_shipping_orders(self) -> tuple[list[dict[str, Any]], bool]:
        return self._select(self._order_query("o.shipment_status = ?"), ("배송중",))

    def get_supplier_purchase_amounts(self) -> tuple[list[dict[str, Any]], bool]:
        return self._select(
            """
            SELECT COALESCE(NULLIF(TRIM(po.supplier_name),''),s.supplier_name,'공급처 미지정') AS supplier_name,
                   COUNT(*) AS purchase_count, SUM(COALESCE(po.quantity,0)) AS total_quantity,
                   SUM(COALESCE(po.item_amount,COALESCE(po.unit_price,p.purchase_price,0)*COALESCE(po.quantity,0))) AS purchase_amount
            FROM purchase_orders po LEFT JOIN suppliers s ON s.id=po.supplier_id
            LEFT JOIN order_items oi ON oi.id=po.order_item_id
            LEFT JOIN products p ON p.id=oi.product_id
            WHERE po.purchase_status NOT IN (?, ?)
            GROUP BY po.supplier_id, COALESCE(NULLIF(TRIM(po.supplier_name),''),s.supplier_name,'공급처 미지정')
            ORDER BY purchase_amount DESC, supplier_name
            """,
            ("발주취소", "취소"),
        )

    def get_today_purchases(self) -> tuple[list[dict[str, Any]], bool]:
        return self._select(
            """
            SELECT po.order_number,po.supplier_name,po.product_name,po.option_name,po.quantity,
                   COALESCE(po.item_amount,COALESCE(po.unit_price,p.purchase_price,0)*COALESCE(po.quantity,0)) AS purchase_amount,
                   po.purchase_status,COALESCE(po.purchased_at,po.created_at) AS purchased_at
            FROM purchase_orders po LEFT JOIN order_items oi ON oi.id=po.order_item_id
            LEFT JOIN products p ON p.id=oi.product_id
            WHERE DATE(COALESCE(po.purchased_at,po.created_at))=DATE('now','localtime')
            ORDER BY COALESCE(po.purchased_at,po.created_at) DESC,po.id DESC
            """
        )

    def get_orders_missing_tracking(self) -> tuple[list[dict[str, Any]], bool]:
        return self._select(
            """
            SELECT o.order_number,o.platform,o.ordered_at,po.product_name AS item_summary,
                   po.quantity AS total_quantity,o.mapping_status,po.purchase_status,o.shipment_status
            FROM purchase_orders po JOIN orders o ON o.id=po.order_id
            LEFT JOIN shipments sh ON sh.order_item_id=po.order_item_id
            WHERE po.purchase_status NOT IN (?, ?)
              AND (sh.id IS NULL OR TRIM(COALESCE(sh.tracking_number,''))='')
            ORDER BY o.ordered_at DESC,o.id DESC,po.id DESC
            """,
            ("발주취소", "취소"),
        )

    def search_orders_by_product(self, term: str) -> tuple[list[dict[str, Any]], bool]:
        value = f"%{term}%"
        return self._select(
            self._order_query(
                "EXISTS (SELECT 1 FROM order_items x WHERE x.order_id=o.id "
                "AND (x.platform_product_name LIKE ? OR x.option_name LIKE ?))"
            ),
            (value, value),
        )

    def search_orders_by_number(self, term: str) -> tuple[list[dict[str, Any]], bool]:
        return self._select(self._order_query("TRIM(o.order_number)=TRIM(?)"), (term,))

    @staticmethod
    def _order_query(where_clause: str) -> str:
        return f"""
            SELECT o.order_number,o.platform,o.ordered_at,
                   GROUP_CONCAT(CASE WHEN TRIM(COALESCE(oi.option_name,''))!=''
                       THEN oi.platform_product_name||' / '||oi.option_name
                       ELSE oi.platform_product_name END,' | ') AS item_summary,
                   COALESCE(SUM(oi.quantity),0) AS total_quantity,
                   o.mapping_status,o.purchase_status,o.shipment_status
            FROM orders o LEFT JOIN order_items oi ON oi.order_id=o.id
            WHERE {where_clause}
            GROUP BY o.id ORDER BY o.ordered_at DESC,o.id DESC
        """
