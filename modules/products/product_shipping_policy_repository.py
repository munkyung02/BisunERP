import sqlite3
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ProductShippingPolicyRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or DATABASE_PATH

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def get_policy(self, policy_id: int) -> Optional[dict[str, Any]]:
        with self._connect() as c:
            row = c.execute("SELECT * FROM product_shipping_policies WHERE id=?", (int(policy_id),)).fetchone()
            return dict(row) if row is not None else None

    def get_shipping_fee(self, product_id: int, quantity: int) -> Optional[int]:
        """Return the shipping fee for given product_id and quantity.

        - Returns int shipping_fee when exactly one active matching policy exists.
        - Returns None when no matching policy.
        - Raises ValueError if multiple overlapping active policies exist.
        """
        # Support two shipping types:
        # - '구간형' (interval): match a single interval where min_quantity <= q <= max_quantity (or max_quantity IS NULL)
        # - '반복형' (repeating): use max_quantity as batch size and compute ceil(q / max_quantity) * shipping_fee
        # Fallback: if shipping_type column is missing, preserve previous interval-only behavior.
        with self._connect() as c:
            cols = {row[1] for row in c.execute("PRAGMA table_info(product_shipping_policies)").fetchall()}

            has_type = "shipping_type" in cols

            if has_type:
                # Check repeating policies for this product
                repeating = c.execute(
                    "SELECT id, shipping_fee, min_quantity, max_quantity FROM product_shipping_policies WHERE product_id=? AND is_active=1 AND shipping_type='반복형'",
                    (int(product_id),),
                ).fetchall()
                if repeating:
                    if len(repeating) > 1:
                        raise ValueError(
                            f"Multiple active repeating shipping policies for product_id={product_id}: {[int(r['id']) for r in repeating]}"
                        )
                    # If there are any active interval policies as well, treat as conflict
                    intervals_any = c.execute(
                        "SELECT 1 FROM product_shipping_policies WHERE product_id=? AND is_active=1 AND shipping_type='구간형' LIMIT 1",
                        (int(product_id),),
                    ).fetchone()
                    if intervals_any:
                        raise ValueError(
                            f"Conflicting shipping policies (반복형 and 구간형) for product_id={product_id}"
                        )
                    r = repeating[0]
                    max_q = r["max_quantity"]
                    fee = int(r["shipping_fee"] or 0)
                    if not max_q or int(max_q) <= 0:
                        raise ValueError(f"Invalid repeating policy max_quantity for policy id={int(r['id'])}")
                    from math import ceil

                    return int(ceil(int(quantity) / int(max_q)) * fee)

            # Interval lookup (구간형). If shipping_type exists, restrict to that type; otherwise keep previous behavior.
            if has_type:
                rows = c.execute(
                    """
                    SELECT id, shipping_fee, min_quantity, max_quantity
                    FROM product_shipping_policies
                    WHERE product_id = ?
                      AND is_active = 1
                      AND shipping_type = '구간형'
                      AND min_quantity <= ?
                      AND (max_quantity IS NULL OR max_quantity >= ?)
                    """,
                    (int(product_id), int(quantity), int(quantity)),
                ).fetchall()
            else:
                rows = c.execute(
                    """
                    SELECT id, shipping_fee, min_quantity, max_quantity
                    FROM product_shipping_policies
                    WHERE product_id = ?
                      AND is_active = 1
                      AND min_quantity <= ?
                      AND (max_quantity IS NULL OR max_quantity >= ?)
                    """,
                    (int(product_id), int(quantity), int(quantity)),
                ).fetchall()

            if not rows:
                return None
            if len(rows) > 1:
                # Data inconsistency: overlapping interval policies
                raise ValueError(
                    f"Multiple active shipping policies found for product_id={product_id} quantity={quantity}: {[int(r['id']) for r in rows]}"
                )
            return int(rows[0]["shipping_fee"] or 0)
