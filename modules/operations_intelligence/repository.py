from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable

from modules.operations_intelligence.models import (
    ChannelSalesMix,
    ProductPurchaseMetrics,
    ProductSalesMetrics,
    SalesWindowSummary,
    SupplierProductComparison,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class SalesIntelligenceRepository:
    """Read-only SQL aggregation over existing order data."""

    PERIODS = ("today", "7d", "30d", "90d")

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

    def get_window_summaries(
        self,
        *,
        starts: dict[str, date],
        end_date: date,
    ) -> tuple[SalesWindowSummary, ...]:
        cases = ",\n".join(
            f"COUNT(CASE WHEN DATE(ordered_at) BETWEEN ? AND ? "
            f"THEN 1 END) AS orders_{name}, "
            f"COALESCE(SUM(CASE WHEN DATE(ordered_at) BETWEEN ? AND ? "
            f"THEN total_amount ELSE 0 END), 0) AS revenue_{name}"
            for name in self.PERIODS
        )
        order_parameters = tuple(
            value
            for name in self.PERIODS
            for value in (
                starts[name].isoformat(), end_date.isoformat(),
                starts[name].isoformat(), end_date.isoformat(),
            )
        )
        item_cases = ",\n".join(
            f"COALESCE(SUM(CASE WHEN DATE(o.ordered_at) BETWEEN ? AND ? "
            f"THEN oi.quantity ELSE 0 END), 0) AS quantity_{name}, "
            f"COALESCE(SUM(CASE WHEN DATE(o.ordered_at) BETWEEN ? AND ? "
            f"AND oi.product_id IS NOT NULL THEN oi.quantity ELSE 0 END), 0) "
            f"AS mapped_{name}, "
            f"COALESCE(SUM(CASE WHEN DATE(o.ordered_at) BETWEEN ? AND ? "
            f"AND oi.product_id IS NULL THEN oi.quantity ELSE 0 END), 0) "
            f"AS unmapped_{name}"
            for name in self.PERIODS
        )
        item_parameters = tuple(
            value
            for name in self.PERIODS
            for value in (
                starts[name].isoformat(), end_date.isoformat(),
                starts[name].isoformat(), end_date.isoformat(),
                starts[name].isoformat(), end_date.isoformat(),
            )
        )

        with self._connect() as connection:
            order_row = connection.execute(
                f"SELECT {cases} FROM orders",
                order_parameters,
            ).fetchone()
            item_row = connection.execute(
                f"""
                SELECT {item_cases}
                FROM order_items AS oi
                INNER JOIN orders AS o ON o.id = oi.order_id
                """,
                item_parameters,
            ).fetchone()

        result: list[SalesWindowSummary] = []
        for name in self.PERIODS:
            order_count = int(order_row[f"orders_{name}"] or 0)
            revenue = int(order_row[f"revenue_{name}"] or 0)
            result.append(
                SalesWindowSummary(
                    period=name,
                    start_date=starts[name].isoformat(),
                    end_date=end_date.isoformat(),
                    order_count=order_count,
                    quantity_sold=int(item_row[f"quantity_{name}"] or 0),
                    revenue=revenue,
                    average_order_value=(
                        int(revenue / order_count) if order_count else 0
                    ),
                    mapped_quantity=int(item_row[f"mapped_{name}"] or 0),
                    unmapped_quantity=int(item_row[f"unmapped_{name}"] or 0),
                )
            )
        return tuple(result)

    def get_product_metrics(
        self,
        *,
        starts: dict[str, date],
        end_date: date,
        product_ids: Iterable[int] | None = None,
    ) -> tuple[ProductSalesMetrics, ...]:
        normalized_ids = sorted({int(value) for value in product_ids or []})
        if product_ids is not None and not normalized_ids:
            return ()
        where_clause = ""
        id_parameters: list[int] = []
        if product_ids is not None:
            placeholders = ",".join("?" for _ in normalized_ids)
            where_clause = f"WHERE p.id IN ({placeholders})"
            id_parameters.extend(normalized_ids)

        time_parameters: list[str] = []
        expressions: list[str] = []
        for name in self.PERIODS:
            start = starts[name].isoformat()
            expressions.extend(
                (
                    f"COALESCE(SUM(CASE WHEN DATE(o.ordered_at) BETWEEN ? AND ? "
                    f"THEN oi.quantity ELSE 0 END), 0) AS quantity_{name}",
                    f"COALESCE(SUM(CASE WHEN DATE(o.ordered_at) BETWEEN ? AND ? "
                    f"THEN oi.total_price ELSE 0 END), 0) AS revenue_{name}",
                )
            )
            end = end_date.isoformat()
            time_parameters.extend((start, end, start, end))

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT p.id, COALESCE(p.product_code, '') AS product_code,
                       p.product_name,
                       {', '.join(expressions)},
                       COUNT(DISTINCT CASE
                           WHEN DATE(o.ordered_at) <= ? THEN oi.order_id
                       END) AS order_count,
                       COALESCE(MAX(CASE
                           WHEN DATE(o.ordered_at) <= ? THEN o.ordered_at
                       END), '') AS latest_order_date
                FROM products AS p
                LEFT JOIN order_items AS oi ON oi.product_id = p.id
                LEFT JOIN orders AS o ON o.id = oi.order_id
                {where_clause}
                GROUP BY p.id, p.product_code, p.product_name
                ORDER BY p.id
                """,
                (
                    *time_parameters,
                    end_date.isoformat(),
                    end_date.isoformat(),
                    *id_parameters,
                ),
            ).fetchall()

        return tuple(
            ProductSalesMetrics(
                product_id=int(row["id"]),
                product_code=str(row["product_code"] or ""),
                product_name=str(row["product_name"] or ""),
                quantity_today=int(row["quantity_today"] or 0),
                quantity_7d=int(row["quantity_7d"] or 0),
                quantity_30d=int(row["quantity_30d"] or 0),
                quantity_90d=int(row["quantity_90d"] or 0),
                revenue_today=int(row["revenue_today"] or 0),
                revenue_7d=int(row["revenue_7d"] or 0),
                revenue_30d=int(row["revenue_30d"] or 0),
                revenue_90d=int(row["revenue_90d"] or 0),
                order_count=int(row["order_count"] or 0),
                latest_order_date=str(row["latest_order_date"] or ""),
            )
            for row in rows
        )

    def get_channel_mix(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[ChannelSalesMix, ...]:
        start = start_date.isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """
                WITH order_mix AS (
                    SELECT platform, COUNT(*) AS order_count,
                           COALESCE(SUM(total_amount), 0) AS revenue
                    FROM orders
                    WHERE DATE(ordered_at) BETWEEN ? AND ?
                    GROUP BY platform
                ),
                item_mix AS (
                    SELECT o.platform, COALESCE(SUM(oi.quantity), 0) AS quantity
                    FROM orders AS o
                    INNER JOIN order_items AS oi ON oi.order_id = o.id
                    WHERE DATE(o.ordered_at) BETWEEN ? AND ?
                    GROUP BY o.platform
                ),
                channels AS (
                    SELECT platform FROM order_mix
                    UNION
                    SELECT platform FROM item_mix
                ),
                combined AS (
                    SELECT c.platform,
                           COALESCE(om.order_count, 0) AS order_count,
                           COALESCE(im.quantity, 0) AS quantity,
                           COALESCE(om.revenue, 0) AS revenue
                    FROM channels AS c
                    LEFT JOIN order_mix AS om ON om.platform = c.platform
                    LEFT JOIN item_mix AS im ON im.platform = c.platform
                )
                SELECT platform, order_count, quantity, revenue,
                       CASE WHEN SUM(order_count) OVER () = 0 THEN 0.0
                            ELSE 1.0 * order_count / SUM(order_count) OVER () END
                            AS order_ratio,
                       CASE WHEN SUM(quantity) OVER () = 0 THEN 0.0
                            ELSE 1.0 * quantity / SUM(quantity) OVER () END
                            AS quantity_ratio,
                       CASE WHEN SUM(revenue) OVER () = 0 THEN 0.0
                            ELSE 1.0 * revenue / SUM(revenue) OVER () END
                            AS revenue_ratio
                FROM combined
                ORDER BY revenue DESC, platform
                """,
                (start, end_date.isoformat(), start, end_date.isoformat()),
            ).fetchall()
        return tuple(
            ChannelSalesMix(
                platform=str(row["platform"] or ""),
                order_count=int(row["order_count"] or 0),
                quantity=int(row["quantity"] or 0),
                revenue=int(row["revenue"] or 0),
                order_ratio=float(row["order_ratio"] or 0.0),
                quantity_ratio=float(row["quantity_ratio"] or 0.0),
                revenue_ratio=float(row["revenue_ratio"] or 0.0),
            )
            for row in rows
        )

    def get_purchase_schema_capabilities(self) -> dict[str, bool]:
        """Report available historical purchase fields without migrating."""
        with self._connect() as connection:
            tables = self._table_names(connection)
            columns = (
                self._table_columns(connection, "purchase_orders")
                if "purchase_orders" in tables
                else set()
            )
        names = (
            "quantity", "unit_price", "item_amount", "shipping_fee",
            "supplier_id", "purchased_at", "created_at", "order_item_id",
        )
        return {name: name in columns for name in names}

    def get_product_purchase_metrics(
        self,
        product_ids: Iterable[int] | None = None,
    ) -> tuple[ProductPurchaseMetrics, ...]:
        normalized_ids = self._normalize_product_ids(product_ids)
        if product_ids is not None and not normalized_ids:
            return ()
        with self._connect() as connection:
            tables = self._table_names(connection)
            purchase_columns = (
                self._table_columns(connection, "purchase_orders")
                if "purchase_orders" in tables
                else set()
            )
            products = self._fetch_products(connection, normalized_ids, product_ids)
            history = self._fetch_supplier_purchase_history(
                connection,
                normalized_ids,
                product_ids,
                purchase_columns,
            )
            defaults = self._fetch_configured_defaults(
                connection,
                normalized_ids,
                product_ids,
                tables,
            )
        history_by_product: dict[int, list[dict[str, object]]] = {}
        for row in history:
            history_by_product.setdefault(int(row["product_id"]), []).append(row)
        defaults_by_product: dict[int, list[dict[str, object]]] = {}
        for row in defaults:
            defaults_by_product.setdefault(int(row["product_id"]), []).append(row)
        return tuple(
            self._build_product_purchase_metric(
                product,
                history_by_product.get(int(product["id"]), []),
                defaults_by_product.get(int(product["id"]), []),
                purchase_columns,
            )
            for product in products
        )

    def get_supplier_product_comparisons(
        self,
        product_ids: Iterable[int] | None = None,
    ) -> tuple[SupplierProductComparison, ...]:
        normalized_ids = self._normalize_product_ids(product_ids)
        if product_ids is not None and not normalized_ids:
            return ()
        with self._connect() as connection:
            tables = self._table_names(connection)
            if "product_suppliers" not in tables:
                return ()
            purchase_columns = (
                self._table_columns(connection, "purchase_orders")
                if "purchase_orders" in tables
                else set()
            )
            history = self._fetch_supplier_purchase_history(
                connection,
                normalized_ids,
                product_ids,
                purchase_columns,
            )
            configured = self._fetch_product_suppliers(
                connection,
                normalized_ids,
                product_ids,
            )
        history_by_key = {
            (int(row["product_id"]), row["supplier_id"]): row
            for row in history
            if row["supplier_id"] is not None
        }
        totals: dict[int, int | None] = {}
        for row in history:
            product_id = int(row["product_id"])
            quantity = row["purchased_quantity"]
            if quantity is None:
                totals[product_id] = None
            elif product_id not in totals:
                totals[product_id] = int(quantity)
            elif totals[product_id] is not None:
                totals[product_id] = int(totals.get(product_id) or 0) + int(quantity)

        result: list[SupplierProductComparison] = []
        for row in configured:
            product_id = int(row["product_id"])
            supplier_id = int(row["supplier_id"])
            historical = history_by_key.get((product_id, supplier_id))
            result.append(
                self._build_supplier_comparison(
                    row,
                    historical,
                    totals.get(product_id),
                    purchase_columns,
                )
            )
        return tuple(result)

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    @staticmethod
    def _table_columns(
        connection: sqlite3.Connection,
        table: str,
    ) -> set[str]:
        if table != "purchase_orders":
            raise ValueError("Unsupported compatibility table")
        return {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(purchase_orders)")
        }

    @staticmethod
    def _normalize_product_ids(
        product_ids: Iterable[int] | None,
    ) -> list[int]:
        return sorted({int(value) for value in product_ids or []})

    @staticmethod
    def _product_filter(
        column: str,
        product_ids: list[int],
        supplied: Iterable[int] | None,
    ) -> tuple[str, list[int]]:
        if supplied is None:
            return "", []
        placeholders = ",".join("?" for _ in product_ids)
        return f" AND {column} IN ({placeholders})", list(product_ids)

    def _fetch_products(
        self,
        connection: sqlite3.Connection,
        product_ids: list[int],
        supplied: Iterable[int] | None,
    ) -> list[dict[str, object]]:
        extra, parameters = self._product_filter("p.id", product_ids, supplied)
        rows = connection.execute(
            f"""
            SELECT p.id, COALESCE(p.product_code, '') AS product_code,
                   p.product_name, p.supplier_id AS legacy_supplier_id,
                   COALESCE(s.supplier_name, '') AS legacy_supplier_name
            FROM products AS p
            LEFT JOIN suppliers AS s ON s.id = p.supplier_id
            WHERE 1 = 1 {extra}
            ORDER BY p.id
            """,
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]

    def _fetch_supplier_purchase_history(
        self,
        connection: sqlite3.Connection,
        product_ids: list[int],
        supplied: Iterable[int] | None,
        columns: set[str],
    ) -> list[dict[str, object]]:
        required = {"order_item_id"}
        if not required.issubset(columns):
            return []
        extra, parameters = self._product_filter(
            "oi.product_id", product_ids, supplied
        )
        status_filter = (
            "AND COALESCE(po.purchase_status, '') NOT IN ('발주취소', '취소')"
            if "purchase_status" in columns
            else ""
        )
        quantity = "po.quantity" if "quantity" in columns else "NULL"
        supplier_id = "po.supplier_id" if "supplier_id" in columns else "NULL"
        supplier_name = (
            "COALESCE(NULLIF(TRIM(po.supplier_name), ''), s.supplier_name, '')"
            if "supplier_name" in columns
            else "COALESCE(s.supplier_name, '')"
        )
        date_value = self._purchase_date_expression(columns)
        amount = self._historical_amount_expression(columns)
        amount_sum = f"SUM({amount})" if amount != "NULL" else "NULL"
        coverage = (
            f"SUM(CASE WHEN {amount} IS NOT NULL THEN 1 ELSE 0 END)"
            if amount != "NULL"
            else "0"
        )
        priced_quantity = (
            f"SUM(CASE WHEN {amount} IS NOT NULL THEN po.quantity ELSE 0 END)"
            if amount != "NULL" and "quantity" in columns
            else "NULL"
        )
        rows = connection.execute(
            f"""
            SELECT oi.product_id,
                   {supplier_id} AS supplier_id,
                   {supplier_name} AS supplier_name,
                   COUNT(*) AS purchase_count,
                   {f'SUM({quantity})' if quantity != 'NULL' else 'NULL'}
                       AS purchased_quantity,
                   {amount_sum} AS purchase_amount,
                   {priced_quantity} AS priced_quantity,
                   {coverage} AS price_coverage_count,
                   COUNT(*) AS total_purchase_rows,
                   {f'MAX({date_value})' if date_value != 'NULL' else 'NULL'}
                       AS latest_purchase_date
            FROM purchase_orders AS po
            INNER JOIN order_items AS oi ON oi.id = po.order_item_id
            LEFT JOIN suppliers AS s ON s.id = {supplier_id}
            WHERE oi.product_id IS NOT NULL {status_filter} {extra}
            GROUP BY oi.product_id, {supplier_id}, {supplier_name}
            ORDER BY oi.product_id, supplier_id
            """,
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _purchase_date_expression(columns: set[str]) -> str:
        if "purchased_at" in columns and "created_at" in columns:
            return "COALESCE(po.purchased_at, po.created_at)"
        if "purchased_at" in columns:
            return "po.purchased_at"
        if "created_at" in columns:
            return "po.created_at"
        return "NULL"

    @staticmethod
    def _historical_amount_expression(columns: set[str]) -> str:
        if "quantity" not in columns:
            return "NULL"
        alternatives: list[str] = []
        if "item_amount" in columns:
            alternatives.append(
                "CASE WHEN po.quantity > 0 AND po.item_amount > 0 "
                "THEN po.item_amount END"
            )
        if "unit_price" in columns:
            alternatives.append(
                "CASE WHEN po.quantity > 0 AND po.unit_price > 0 "
                "THEN po.unit_price * po.quantity END"
            )
        if not alternatives:
            return "NULL"
        return f"COALESCE({', '.join(alternatives)})"

    def _fetch_configured_defaults(
        self,
        connection: sqlite3.Connection,
        product_ids: list[int],
        supplied: Iterable[int] | None,
        tables: set[str],
    ) -> list[dict[str, object]]:
        if "product_suppliers" not in tables:
            return []
        extra, parameters = self._product_filter(
            "ps.product_id", product_ids, supplied
        )
        rows = connection.execute(
            f"""
            SELECT ps.product_id, ps.supplier_id,
                   COALESCE(s.supplier_name, '') AS supplier_name
            FROM product_suppliers AS ps
            LEFT JOIN suppliers AS s ON s.id = ps.supplier_id
            WHERE ps.is_default = 1 {extra}
            ORDER BY ps.product_id, ps.supplier_id
            """,
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]

    def _fetch_product_suppliers(
        self,
        connection: sqlite3.Connection,
        product_ids: list[int],
        supplied: Iterable[int] | None,
    ) -> list[dict[str, object]]:
        extra, parameters = self._product_filter(
            "ps.product_id", product_ids, supplied
        )
        rows = connection.execute(
            f"""
            SELECT ps.product_id, ps.supplier_id,
                   COALESCE(s.supplier_name, '') AS supplier_name,
                   COALESCE(ps.purchase_price, 0) AS purchase_price,
                   COALESCE(s.is_active, 0) AS supplier_active,
                   COALESCE(ps.is_active, 0) AS product_supplier_active,
                   COALESCE(ps.is_default, 0) AS is_default
            FROM product_suppliers AS ps
            LEFT JOIN suppliers AS s ON s.id = ps.supplier_id
            WHERE 1 = 1 {extra}
            ORDER BY ps.product_id, ps.is_default DESC, ps.supplier_id
            """,
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]

    def _build_product_purchase_metric(
        self,
        product: dict[str, object],
        history: list[dict[str, object]],
        defaults: list[dict[str, object]],
        columns: set[str],
    ) -> ProductPurchaseMetrics:
        statuses: list[str] = []
        purchase_count = sum(int(row["purchase_count"] or 0) for row in history)
        total_rows = sum(int(row["total_purchase_rows"] or 0) for row in history)
        quantity_available = "quantity" in columns
        purchased_quantity = (
            sum(int(row["purchased_quantity"] or 0) for row in history)
            if quantity_available
            else None
        )
        coverage = sum(int(row["price_coverage_count"] or 0) for row in history)
        amount = sum(int(row["purchase_amount"] or 0) for row in history)
        priced_quantity = sum(int(row["priced_quantity"] or 0) for row in history)
        total_amount = amount if coverage else None
        average_price = (
            int(amount / priced_quantity) if priced_quantity > 0 else None
        )
        if not history:
            statuses.append("No Purchase History")
        if not quantity_available:
            statuses.append("Purchase Quantity Unavailable")
        if total_rows and coverage == 0:
            statuses.append("Historical Price Unavailable")
        elif coverage < total_rows:
            statuses.append("Historical Price Partial")

        default_id: int | None = None
        default_name = ""
        if len(defaults) == 1:
            default_id = int(defaults[0]["supplier_id"])
            default_name = str(defaults[0]["supplier_name"] or "")
        elif len(defaults) > 1:
            statuses.append("Configured Default Ambiguous")
        elif product.get("legacy_supplier_id") is not None:
            default_id = int(product["legacy_supplier_id"])
            default_name = str(product.get("legacy_supplier_name") or "")
            statuses.append("Legacy Default Fallback")

        most_id, most_name, most_ambiguous = self._most_used_supplier(history)
        if most_ambiguous:
            statuses.append("Most Used Supplier Ambiguous")
        latest_id, latest_name, latest_date, latest_ambiguous = (
            self._latest_supplier(history)
        )
        if latest_ambiguous:
            statuses.append("Latest Supplier Ambiguous")
        if "order_item_id" not in columns:
            statuses.append("Purchase Link Unavailable")

        return ProductPurchaseMetrics(
            product_id=int(product["id"]),
            product_code=str(product["product_code"] or ""),
            product_name=str(product["product_name"] or ""),
            purchase_count=purchase_count,
            purchased_quantity=purchased_quantity,
            total_purchase_amount=total_amount,
            average_unit_price=average_price,
            price_coverage_count=coverage,
            total_purchase_rows=total_rows,
            configured_default_supplier_id=default_id,
            configured_default_supplier_name=default_name,
            most_used_supplier_id=most_id,
            most_used_supplier_name=most_name,
            latest_supplier_id=latest_id,
            latest_supplier_name=latest_name,
            latest_purchase_date=latest_date,
            data_status="; ".join(statuses) if statuses else "Available",
        )

    @staticmethod
    def _most_used_supplier(
        history: list[dict[str, object]],
    ) -> tuple[int | None, str, bool]:
        candidates = [
            row for row in history
            if row["supplier_id"] is not None
            and row["purchased_quantity"] is not None
        ]
        if not candidates:
            return None, "", False
        maximum = max(int(row["purchased_quantity"] or 0) for row in candidates)
        winners = [
            row for row in candidates
            if int(row["purchased_quantity"] or 0) == maximum
        ]
        if len(winners) != 1:
            return None, "", True
        return (
            int(winners[0]["supplier_id"]),
            str(winners[0]["supplier_name"] or ""),
            False,
        )

    @staticmethod
    def _latest_supplier(
        history: list[dict[str, object]],
    ) -> tuple[int | None, str, str, bool]:
        candidates = [
            row for row in history
            if row["supplier_id"] is not None
            and str(row["latest_purchase_date"] or "")
        ]
        if not candidates:
            return None, "", "", False
        latest = max(str(row["latest_purchase_date"]) for row in candidates)
        winners = [
            row for row in candidates
            if str(row["latest_purchase_date"]) == latest
        ]
        if len(winners) != 1:
            return None, "", latest, True
        return (
            int(winners[0]["supplier_id"]),
            str(winners[0]["supplier_name"] or ""),
            latest,
            False,
        )

    @staticmethod
    def _build_supplier_comparison(
        configured: dict[str, object],
        historical: dict[str, object] | None,
        total_quantity: int | None,
        columns: set[str],
    ) -> SupplierProductComparison:
        historical = historical or {}
        coverage = int(historical.get("price_coverage_count") or 0)
        amount = int(historical.get("purchase_amount") or 0)
        priced_quantity = int(historical.get("priced_quantity") or 0)
        average = int(amount / priced_quantity) if priced_quantity > 0 else None
        configured_price = int(configured["purchase_price"] or 0)
        if average is not None and configured_price > 0:
            price_source = "Configured + Historical"
        elif average is not None:
            price_source = "Historical Only"
        elif configured_price > 0:
            price_source = "Configured Only"
        else:
            price_source = "Unavailable"
        quantity = historical.get("purchased_quantity")
        statuses: list[str] = []
        if not historical:
            statuses.append("No Purchase History")
        if "quantity" not in columns:
            statuses.append("Purchase Quantity Unavailable")
            quantity = None
        if historical and coverage == 0:
            statuses.append("Historical Price Unavailable")
        elif historical and coverage < int(historical.get("total_purchase_rows") or 0):
            statuses.append("Historical Price Partial")
        usage_ratio = (
            float(int(quantity or 0) / total_quantity)
            if quantity is not None and total_quantity and total_quantity > 0
            else 0.0
        )
        return SupplierProductComparison(
            product_id=int(configured["product_id"]),
            supplier_id=int(configured["supplier_id"]),
            supplier_name=str(configured["supplier_name"] or ""),
            configured_purchase_price=configured_price,
            historical_average_price=average,
            purchase_count=int(historical.get("purchase_count") or 0),
            purchased_quantity=(int(quantity or 0) if quantity is not None else None),
            purchase_amount=(amount if coverage else None),
            usage_ratio=usage_ratio,
            latest_purchase_date=str(historical.get("latest_purchase_date") or ""),
            supplier_active=bool(int(configured["supplier_active"] or 0)),
            product_supplier_active=bool(
                int(configured["product_supplier_active"] or 0)
            ),
            is_default=bool(int(configured["is_default"] or 0)),
            price_source=price_source,
            price_coverage_count=coverage,
            data_status="; ".join(statuses) if statuses else "Available",
        )
