from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.database import Database


class ClaimService:
    """주문 클레임의 등록, 조회, 처리 상태 동기화를 담당합니다."""

    CLAIM_TYPES = ("주문취소", "반품", "교환", "환불", "배송사고", "상품불량", "기타")
    CLAIM_STATUSES = ("접수", "처리중", "완료", "보류")
    REFUND_STATUSES = ("해당없음", "환불대기", "부분환불", "환불완료")

    def __init__(self, database_path: Path | None = None) -> None:
        self.database = Database(database_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    claim_type TEXT NOT NULL DEFAULT '주문취소',
                    claim_status TEXT NOT NULL DEFAULT '접수',
                    reason TEXT,
                    refund_amount INTEGER NOT NULL DEFAULT 0,
                    refund_status TEXT NOT NULL DEFAULT '해당없음',
                    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    manager_name TEXT,
                    memo TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_claims_order_id ON claims(order_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(claim_status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_claims_requested_at ON claims(requested_at)")
            connection.commit()

    def search_orders(self, keyword: str = "", limit: int = 100) -> list[dict[str, Any]]:
        keyword = keyword.strip()
        params: list[Any] = []
        where = ""
        if keyword:
            token = f"%{keyword}%"
            where = """
                WHERE o.order_number LIKE ? OR o.receiver_name LIKE ?
                   OR o.receiver_phone LIKE ? OR oi.platform_product_name LIKE ?
            """
            params.extend([token, token, token, token])
        params.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT o.id, o.order_number, o.platform, o.ordered_at,
                       o.receiver_name, o.receiver_phone, o.total_amount,
                       o.order_status, o.payment_status, o.shipment_status,
                       GROUP_CONCAT(DISTINCT oi.platform_product_name) AS products
                FROM orders o
                LEFT JOIN order_items oi ON oi.order_id = o.id
                {where}
                GROUP BY o.id
                ORDER BY COALESCE(o.ordered_at, o.created_at) DESC, o.id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_claims(
        self,
        keyword: str = "",
        claim_status: str = "전체",
        claim_type: str = "전체",
        date_from: str = "",
        date_to: str = "",
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if keyword.strip():
            token = f"%{keyword.strip()}%"
            conditions.append(
                "(o.order_number LIKE ? OR o.receiver_name LIKE ? OR o.receiver_phone LIKE ? "
                "OR c.reason LIKE ? OR c.memo LIKE ?)"
            )
            params.extend([token] * 5)
        if claim_status != "전체":
            conditions.append("c.claim_status = ?")
            params.append(claim_status)
        if claim_type != "전체":
            conditions.append("c.claim_type = ?")
            params.append(claim_type)
        if date_from:
            conditions.append("date(c.requested_at) >= date(?)")
            params.append(date_from)
        if date_to:
            conditions.append("date(c.requested_at) <= date(?)")
            params.append(date_to)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT c.*, o.order_number, o.platform, o.receiver_name,
                       o.receiver_phone, o.total_amount, o.order_status,
                       o.payment_status, o.shipment_status
                FROM claims c
                JOIN orders o ON o.id = c.order_id
                {where}
                ORDER BY CASE c.claim_status WHEN '접수' THEN 0 WHEN '처리중' THEN 1
                         WHEN '보류' THEN 2 ELSE 3 END,
                         datetime(c.requested_at) DESC, c.id DESC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_claim(self, claim_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT c.*, o.order_number, o.receiver_name, o.receiver_phone,
                       o.total_amount, o.order_status, o.payment_status, o.shipment_status
                FROM claims c JOIN orders o ON o.id = c.order_id
                WHERE c.id = ?
                """,
                (claim_id,),
            ).fetchone()
        return dict(row) if row else None

    def save_claim(self, data: dict[str, Any], claim_id: int | None = None) -> int:
        order_id = int(data["order_id"])
        claim_type = str(data.get("claim_type") or "주문취소")
        claim_status = str(data.get("claim_status") or "접수")
        refund_status = str(data.get("refund_status") or "해당없음")
        refund_amount = max(0, int(data.get("refund_amount") or 0))
        completed_at = data.get("completed_at") or None
        if claim_status == "완료" and not completed_at:
            completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif claim_status != "완료":
            completed_at = None

        with self.database.connect() as connection:
            if claim_id is None:
                cursor = connection.execute(
                    """
                    INSERT INTO claims (
                        order_id, claim_type, claim_status, reason, refund_amount,
                        refund_status, requested_at, completed_at, manager_name, memo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id, claim_type, claim_status, data.get("reason", ""),
                        refund_amount, refund_status,
                        data.get("requested_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        completed_at, data.get("manager_name", ""), data.get("memo", ""),
                    ),
                )
                claim_id = int(cursor.lastrowid)
            else:
                connection.execute(
                    """
                    UPDATE claims SET order_id=?, claim_type=?, claim_status=?, reason=?,
                        refund_amount=?, refund_status=?, requested_at=?, completed_at=?,
                        manager_name=?, memo=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        order_id, claim_type, claim_status, data.get("reason", ""),
                        refund_amount, refund_status, data.get("requested_at"), completed_at,
                        data.get("manager_name", ""), data.get("memo", ""), claim_id,
                    ),
                )
            self._sync_order_status(connection, order_id)
            connection.commit()
        return claim_id

    def delete_claim(self, claim_id: int) -> None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT order_id FROM claims WHERE id=?", (claim_id,)).fetchone()
            if not row:
                return
            order_id = int(row["order_id"])
            connection.execute("DELETE FROM claims WHERE id=?", (claim_id,))
            self._sync_order_status(connection, order_id)
            connection.commit()

    def mark_status(self, claim_ids: list[int], status: str) -> None:
        if status not in self.CLAIM_STATUSES or not claim_ids:
            return
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "완료" else None
        placeholders = ",".join("?" for _ in claim_ids)
        with self.database.connect() as connection:
            order_rows = connection.execute(
                f"SELECT DISTINCT order_id FROM claims WHERE id IN ({placeholders})", claim_ids
            ).fetchall()
            connection.execute(
                f"UPDATE claims SET claim_status=?, completed_at=?, updated_at=CURRENT_TIMESTAMP "
                f"WHERE id IN ({placeholders})",
                [status, completed_at, *claim_ids],
            )
            for row in order_rows:
                self._sync_order_status(connection, int(row["order_id"]))
            connection.commit()

    def get_summary(self) -> dict[str, int]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN claim_status='접수' THEN 1 ELSE 0 END) AS received,
                       SUM(CASE WHEN claim_status='처리중' THEN 1 ELSE 0 END) AS processing,
                       SUM(CASE WHEN claim_status='보류' THEN 1 ELSE 0 END) AS hold,
                       SUM(CASE WHEN claim_status='완료' THEN 1 ELSE 0 END) AS completed,
                       COALESCE(SUM(CASE WHEN refund_status IN ('환불대기','부분환불')
                                         THEN refund_amount ELSE 0 END), 0) AS pending_refund
                FROM claims
                """
            ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}

    def get_open_count(self) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM claims WHERE claim_status <> '완료'"
            ).fetchone()
        return int(row["count"] or 0)

    @staticmethod
    def _sync_order_status(connection: Any, order_id: int) -> None:
        rows = connection.execute(
            "SELECT claim_type, claim_status FROM claims WHERE order_id=? ORDER BY id DESC",
            (order_id,),
        ).fetchall()
        active = [row for row in rows if row["claim_status"] != "완료"]
        if not active:
            return
        claim_types = {row["claim_type"] for row in active}
        if "주문취소" in claim_types:
            status = "취소요청"
        elif "반품" in claim_types or "환불" in claim_types:
            status = "반품/환불요청"
        elif "교환" in claim_types:
            status = "교환요청"
        else:
            status = "클레임접수"
        connection.execute(
            "UPDATE orders SET order_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, order_id),
        )
