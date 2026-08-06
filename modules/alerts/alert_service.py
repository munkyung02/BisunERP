from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class AlertService:
    """ERP 운영상 즉시 확인할 업무 항목을 통합 조회합니다."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(__file__).resolve().parents[2] / "data" / "bisun_erp.db"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_alerts(self, *, category: str = "전체", keyword: str = "", overdue_days: int = 3) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        with self._connect() as conn:
            if category in ("전체", "입금"):
                alerts.extend(self._payment_alerts(conn))
            if category in ("전체", "매핑"):
                alerts.extend(self._mapping_alerts(conn))
            if category in ("전체", "발주"):
                alerts.extend(self._purchase_alerts(conn))
            if category in ("전체", "송장"):
                alerts.extend(self._shipment_alerts(conn))
            if category in ("전체", "배송"):
                alerts.extend(self._delivery_alerts(conn, overdue_days))
            if category in ("전체", "클레임"):
                alerts.extend(self._claim_alerts(conn))

        term = keyword.strip().lower()
        if term:
            alerts = [a for a in alerts if term in " ".join(str(v or "") for v in a.values()).lower()]
        priority_order = {"긴급": 0, "높음": 1, "보통": 2}
        alerts.sort(key=lambda a: (priority_order.get(a["priority"], 9), a.get("sort_date", "")))
        return alerts

    def get_summary(self, overdue_days: int = 3) -> dict[str, int]:
        rows = self.get_alerts(overdue_days=overdue_days)
        summary = {"전체": len(rows), "긴급": 0, "높음": 0, "보통": 0}
        for row in rows:
            summary[row["priority"]] = summary.get(row["priority"], 0) + 1
        return summary

    @staticmethod
    def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        try:
            return list(conn.execute(sql, params))
        except sqlite3.OperationalError:
            return []

    def _payment_alerts(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = self._rows(conn, """
            SELECT o.id, o.order_number, o.receiver_name, o.receiver_phone, o.total_amount,
                   o.ordered_at, COALESCE(SUM(CASE WHEN p.payment_status != '입금취소' THEN p.payment_amount ELSE 0 END),0) paid
              FROM orders o LEFT JOIN payments p ON p.order_id=o.id
             WHERE o.payment_status NOT IN ('입금완료','결제완료')
             GROUP BY o.id HAVING paid < o.total_amount
        """)
        result=[]
        for r in rows:
            remain=max(int(r['total_amount'] or 0)-int(r['paid'] or 0),0)
            result.append(self._make("입금","높음",r,"미입금 주문",f"미입금 {remain:,}원",r['ordered_at'],"입금관리"))
        return result

    def _mapping_alerts(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows=self._rows(conn,"""
            SELECT o.id,o.order_number,o.receiver_name,o.receiver_phone,o.ordered_at,
                   COUNT(oi.id) cnt FROM orders o JOIN order_items oi ON oi.order_id=o.id
             WHERE COALESCE(oi.mapping_status,'미매핑')!='매핑완료'
             GROUP BY o.id
        """)
        return [self._make("매핑","높음",r,"미매핑 상품",f"미매핑 품목 {r['cnt']}건",r['ordered_at'],"상품매핑") for r in rows]

    def _purchase_alerts(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows=self._rows(conn,"""
            SELECT o.id,o.order_number,o.receiver_name,o.receiver_phone,o.ordered_at,
                   COUNT(po.id) cnt FROM orders o LEFT JOIN purchase_orders po ON po.order_id=o.id
             WHERE COALESCE(o.purchase_status,'발주대기') IN ('발주대기','발주준비')
             GROUP BY o.id
        """)
        return [self._make("발주","보통",r,"발주 대기",f"발주 대상 {max(int(r['cnt'] or 0),1)}건",r['ordered_at'],"발주관리") for r in rows]

    def _shipment_alerts(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows=self._rows(conn,"""
            SELECT o.id,o.order_number,o.receiver_name,o.receiver_phone,o.ordered_at
              FROM orders o
             WHERE COALESCE(o.shipment_status,'배송대기') IN ('배송대기','송장대기','배송준비')
               AND NOT EXISTS (SELECT 1 FROM shipments s WHERE s.order_id=o.id AND COALESCE(s.tracking_number,'')!='')
        """)
        return [self._make("송장","높음",r,"송장 미등록","등록된 송장번호 없음",r['ordered_at'],"송장관리") for r in rows]

    def _delivery_alerts(self, conn: sqlite3.Connection, days: int) -> list[dict[str, Any]]:
        cutoff=(datetime.now()-timedelta(days=max(days,1))).strftime('%Y-%m-%d %H:%M:%S')
        rows=self._rows(conn,"""
            SELECT o.id,o.order_number,o.receiver_name,o.receiver_phone,s.shipped_at,s.courier_name,s.tracking_number
              FROM shipments s JOIN orders o ON o.id=s.order_id
             WHERE s.shipment_status='배송중' AND COALESCE(s.shipped_at,s.created_at) < ?
        """,(cutoff,))
        return [self._make("배송","긴급",r,"장기 배송중",f"{r['courier_name'] or '-'} {r['tracking_number'] or '-'}",r['shipped_at'],"배송현황") for r in rows]

    def _claim_alerts(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows=self._rows(conn,"""
            SELECT c.id,o.order_number,o.receiver_name,o.receiver_phone,c.created_at,c.claim_type,c.reason
              FROM claims c LEFT JOIN orders o ON o.id=c.order_id
             WHERE c.status NOT IN ('완료','취소')
        """)
        return [self._make("클레임","긴급",r,f"{r['claim_type'] or '클레임'} 미처리",r['reason'] or '처리 내용 확인 필요',r['created_at'],"클레임관리") for r in rows]

    @staticmethod
    def _make(category: str, priority: str, row: sqlite3.Row, title: str, detail: str, date_value: Any, target: str) -> dict[str, Any]:
        return {
            "category": category,
            "priority": priority,
            "order_number": row["order_number"] if "order_number" in row.keys() else "",
            "customer": row["receiver_name"] if "receiver_name" in row.keys() else "",
            "phone": row["receiver_phone"] if "receiver_phone" in row.keys() else "",
            "title": title,
            "detail": detail,
            "date": str(date_value or "")[:16],
            "sort_date": str(date_value or ""),
            "target": target,
        }
