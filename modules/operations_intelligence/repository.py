from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable

from modules.operations_intelligence.models import (
    ChannelSalesMix,
    ProductSalesMetrics,
    SalesWindowSummary,
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
