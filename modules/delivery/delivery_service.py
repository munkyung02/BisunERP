from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class DeliveryService:
    """송장 등록 이후 배송 진행 상태를 조회하고 관리합니다."""

    STATUSES = ("전체", "배송준비", "배송중", "배송완료", "배송취소")
    UPDATE_STATUSES = ("배송준비", "배송중", "배송완료", "배송취소")

    CARRIER_URLS = {
        "CJ대한통운": "https://trace.cjlogistics.com/next/tracking.html?wblNo={tracking}",
        "CJ": "https://trace.cjlogistics.com/next/tracking.html?wblNo={tracking}",
        "대한통운": "https://trace.cjlogistics.com/next/tracking.html?wblNo={tracking}",
        "한진택배": "https://www.hanjin.com/kor/CMS/DeliveryMgr/WaybillResult.do?mession-val={tracking}",
        "한진": "https://www.hanjin.com/kor/CMS/DeliveryMgr/WaybillResult.do?mession-val={tracking}",
        "롯데택배": "https://www.lotteglogis.com/home/reservation/tracking/linkView?InvNo={tracking}",
        "롯데글로벌로지스": "https://www.lotteglogis.com/home/reservation/tracking/linkView?InvNo={tracking}",
        "우체국택배": "https://service.epost.go.kr/trace.RetrieveDomRigiTraceList.comm?sid1={tracking}",
        "우체국": "https://service.epost.go.kr/trace.RetrieveDomRigiTraceList.comm?sid1={tracking}",
        "로젠택배": "https://www.ilogen.com/web/personal/trace/{tracking}",
        "로젠": "https://www.ilogen.com/web/personal/trace/{tracking}",
    }

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path) if database_path else DATABASE_PATH
        self._ensure_indexes()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_indexes(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(shipment_status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_shipments_tracking ON shipments(tracking_number)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_shipments_shipped_at ON shipments(shipped_at)"
            )

    def get_summary(self, overdue_days: int = 3) -> dict[str, int]:
        overdue_days = max(1, int(overdue_days))
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN shipment_status = '배송준비' THEN 1 ELSE 0 END) AS ready,
                    SUM(CASE WHEN shipment_status = '배송중' THEN 1 ELSE 0 END) AS shipping,
                    SUM(CASE WHEN shipment_status = '배송완료' THEN 1 ELSE 0 END) AS delivered,
                    SUM(CASE WHEN shipment_status = '배송취소' THEN 1 ELSE 0 END) AS cancelled,
                    SUM(CASE
                        WHEN shipment_status = '배송중'
                         AND COALESCE(shipped_at, created_at) < datetime('now', ?)
                        THEN 1 ELSE 0 END
                    ) AS overdue
                FROM shipments
                """,
                (f"-{overdue_days} days",),
            ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}

    def search(
        self,
        *,
        keyword: str = "",
        status: str = "전체",
        overdue_only: bool = False,
        overdue_days: int = 3,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conditions = ["1 = 1"]
        params: list[Any] = []

        keyword = keyword.strip()
        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                """(
                    COALESCE(o.order_number, '') LIKE ? OR
                    COALESCE(o.receiver_name, '') LIKE ? OR
                    COALESCE(o.receiver_phone, '') LIKE ? OR
                    COALESCE(sh.courier_name, '') LIKE ? OR
                    COALESCE(sh.tracking_number, '') LIKE ? OR
                    COALESCE(po.product_name, '') LIKE ?
                )"""
            )
            params.extend([like] * 6)

        if status and status != "전체":
            conditions.append("sh.shipment_status = ?")
            params.append(status)

        if overdue_only:
            conditions.append(
                "sh.shipment_status = '배송중' AND COALESCE(sh.shipped_at, sh.created_at) < datetime('now', ?)"
            )
            params.append(f"-{max(1, int(overdue_days))} days")

        params.append(max(1, int(limit)))
        query = f"""
            SELECT
                sh.id,
                sh.order_id,
                sh.order_item_id,
                o.order_number,
                o.receiver_name,
                o.receiver_phone,
                po.product_name,
                po.option_name,
                po.quantity,
                sh.courier_name,
                sh.tracking_number,
                sh.shipment_status,
                sh.shipped_at,
                sh.delivered_at,
                sh.memo,
                CAST(julianday('now') - julianday(COALESCE(sh.shipped_at, sh.created_at)) AS INTEGER) AS elapsed_days
            FROM shipments AS sh
            JOIN orders AS o ON o.id = sh.order_id
            LEFT JOIN purchase_orders AS po ON po.order_item_id = sh.order_item_id
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE sh.shipment_status
                    WHEN '배송중' THEN 1
                    WHEN '배송준비' THEN 2
                    WHEN '배송취소' THEN 3
                    ELSE 4
                END,
                COALESCE(sh.shipped_at, sh.created_at) DESC,
                sh.id DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_status(
        self,
        shipment_ids: Iterable[int],
        status: str,
        memo: str | None = None,
    ) -> int:
        ids = sorted({int(value) for value in shipment_ids})
        if not ids:
            return 0
        if status not in self.UPDATE_STATUSES:
            raise ValueError(f"지원하지 않는 배송상태입니다: {status}")

        placeholders = ",".join("?" for _ in ids)
        delivered_sql = "CURRENT_TIMESTAMP" if status == "배송완료" else "NULL"
        shipped_sql = (
            "COALESCE(shipped_at, CURRENT_TIMESTAMP)"
            if status in {"배송중", "배송완료"}
            else "shipped_at"
        )
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                UPDATE shipments
                SET shipment_status = ?,
                    shipped_at = {shipped_sql},
                    delivered_at = {delivered_sql},
                    memo = CASE WHEN ? IS NULL OR TRIM(?) = '' THEN memo ELSE ? END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """,
                [status, memo, memo, memo, *ids],
            )
            order_rows = conn.execute(
                f"SELECT DISTINCT order_id FROM shipments WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
            for row in order_rows:
                self._sync_order_status(conn, int(row["order_id"]))
        return int(cursor.rowcount)

    def _sync_order_status(self, conn: sqlite3.Connection, order_id: int) -> None:
        rows = conn.execute(
            "SELECT shipment_status FROM shipments WHERE order_id = ?",
            (order_id,),
        ).fetchall()
        statuses = {str(row["shipment_status"]) for row in rows}
        if not statuses:
            return
        if statuses == {"배송완료"}:
            order_status = "배송완료"
        elif "배송중" in statuses or "배송완료" in statuses:
            order_status = "배송중"
        elif statuses == {"배송취소"}:
            order_status = "배송취소"
        else:
            order_status = "배송준비"
        conn.execute(
            "UPDATE orders SET shipment_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (order_status, order_id),
        )

    def get_tracking_url(self, carrier_name: str, tracking_number: str) -> str:
        carrier = (carrier_name or "").strip().replace(" ", "")
        tracking = (tracking_number or "").strip()
        if not tracking:
            raise ValueError("송장번호가 없습니다.")

        for name, template in self.CARRIER_URLS.items():
            if name.replace(" ", "") in carrier or carrier in name.replace(" ", ""):
                return template.format(tracking=quote(tracking))

        query = quote(f"{carrier_name} {tracking} 배송조회")
        return f"https://search.naver.com/search.naver?query={query}"

    @staticmethod
    def format_datetime(value: Any) -> str:
        if not value:
            return "-"
        text = str(value).replace("T", " ")
        try:
            return datetime.fromisoformat(text).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return text[:16]
