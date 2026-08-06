from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IntegrityIssue:
    issue_key: str
    severity: str
    category: str
    record_id: int | None
    reference: str
    title: str
    detail: str
    fixable: bool = False


class IntegrityService:
    """ERP 데이터의 구조 및 업무 상태 일관성을 점검하고 안전한 항목을 복구합니다."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(__file__).resolve().parents[2] / "data" / "bisun_erp.db"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    def scan(self) -> list[IntegrityIssue]:
        issues: list[IntegrityIssue] = []
        with self._connect() as conn:
            issues.extend(self._check_foreign_keys(conn))
            issues.extend(self._check_order_totals(conn))
            issues.extend(self._check_order_statuses(conn))
            issues.extend(self._check_required_fields(conn))
            issues.extend(self._check_duplicates(conn))
        severity_order = {"긴급": 0, "주의": 1, "확인": 2}
        return sorted(issues, key=lambda x: (severity_order.get(x.severity, 9), x.category, x.reference))

    def get_summary(self, issues: list[IntegrityIssue] | None = None) -> dict[str, int]:
        rows = issues if issues is not None else self.scan()
        summary = {"전체": len(rows), "긴급": 0, "주의": 0, "확인": 0, "자동복구": 0}
        for row in rows:
            summary[row.severity] = summary.get(row.severity, 0) + 1
            if row.fixable:
                summary["자동복구"] += 1
        return summary

    def create_backup(self, backup_dir: str | Path | None = None) -> Path:
        target_dir = Path(backup_dir) if backup_dir else self.db_path.parent / "backups"
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = target_dir / f"bisun_erp_before_integrity_fix_{stamp}.db"
        shutil.copy2(self.db_path, target)
        return target

    def repair(self, issues: list[IntegrityIssue]) -> dict[str, Any]:
        fixable = [issue for issue in issues if issue.fixable]
        if not fixable:
            return {"fixed": 0, "backup": None, "failed": []}
        backup = self.create_backup()
        fixed = 0
        failed: list[str] = []
        with self._connect() as conn:
            for issue in fixable:
                try:
                    fixed += self._repair_one(conn, issue)
                except Exception as error:
                    failed.append(f"{issue.reference}: {error}")
            conn.commit()
        return {"fixed": fixed, "backup": backup, "failed": failed}

    def _repair_one(self, conn: sqlite3.Connection, issue: IntegrityIssue) -> int:
        if issue.record_id is None:
            return 0
        if issue.issue_key == "order_total":
            row = conn.execute(
                "SELECT COALESCE(SUM(total_price),0) total FROM order_items WHERE order_id=?",
                (issue.record_id,),
            ).fetchone()
            conn.execute(
                "UPDATE orders SET total_amount=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(row["total"] or 0), issue.record_id),
            )
            return 1
        if issue.issue_key == "mapping_status":
            count = conn.execute(
                "SELECT COUNT(*) FROM order_items WHERE order_id=? AND COALESCE(mapping_status,'미매핑')!='매핑완료'",
                (issue.record_id,),
            ).fetchone()[0]
            value = "매핑완료" if count == 0 else "미매핑"
            conn.execute("UPDATE orders SET mapping_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (value, issue.record_id))
            return 1
        if issue.issue_key == "purchase_status":
            rows = conn.execute("SELECT purchase_status FROM purchase_orders WHERE order_id=?", (issue.record_id,)).fetchall()
            if not rows:
                value = "발주대기"
            elif all((r[0] or "") in ("발주완료", "발주확정") for r in rows):
                value = "발주완료"
            else:
                value = "발주대기"
            conn.execute("UPDATE orders SET purchase_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (value, issue.record_id))
            return 1
        if issue.issue_key == "shipment_status":
            rows = conn.execute("SELECT shipment_status FROM shipments WHERE order_id=?", (issue.record_id,)).fetchall()
            if not rows:
                value = "배송대기"
            elif all((r[0] or "") == "배송완료" for r in rows):
                value = "배송완료"
            elif any((r[0] or "") == "배송중" for r in rows):
                value = "배송중"
            else:
                value = "배송준비"
            conn.execute("UPDATE orders SET shipment_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (value, issue.record_id))
            return 1
        return 0

    def _check_foreign_keys(self, conn: sqlite3.Connection) -> list[IntegrityIssue]:
        result = []
        for row in conn.execute("PRAGMA foreign_key_check"):
            result.append(IntegrityIssue(
                issue_key="foreign_key", severity="긴급", category="참조무결성",
                record_id=int(row[1]) if row[1] is not None else None,
                reference=f"{row[0]} #{row[1]}", title="연결 대상이 없는 데이터",
                detail=f"외래키 {row[3]} 참조가 유효하지 않습니다.", fixable=False,
            ))
        return result

    def _check_order_totals(self, conn: sqlite3.Connection) -> list[IntegrityIssue]:
        rows = conn.execute("""
            SELECT o.id,o.order_number,o.total_amount,COALESCE(SUM(oi.total_price),0) item_total
              FROM orders o LEFT JOIN order_items oi ON oi.order_id=o.id
             GROUP BY o.id
            HAVING COALESCE(o.total_amount,0) != COALESCE(SUM(oi.total_price),0)
        """).fetchall()
        return [IntegrityIssue(
            issue_key="order_total", severity="주의", category="주문금액", record_id=r["id"],
            reference=r["order_number"], title="주문금액 합계 불일치",
            detail=f"주문 {int(r['total_amount'] or 0):,}원 / 품목합계 {int(r['item_total'] or 0):,}원",
            fixable=True,
        ) for r in rows]

    def _check_order_statuses(self, conn: sqlite3.Connection) -> list[IntegrityIssue]:
        result: list[IntegrityIssue] = []
        rows = conn.execute("""
            SELECT o.id,o.order_number,o.mapping_status,
                   SUM(CASE WHEN COALESCE(oi.mapping_status,'미매핑')!='매핑완료' THEN 1 ELSE 0 END) pending
              FROM orders o JOIN order_items oi ON oi.order_id=o.id GROUP BY o.id
        """).fetchall()
        for r in rows:
            expected = "매핑완료" if int(r["pending"] or 0) == 0 else "미매핑"
            if (r["mapping_status"] or "미매핑") != expected:
                result.append(IntegrityIssue("mapping_status", "주의", "상태동기화", r["id"], r["order_number"],
                    "주문 매핑상태 불일치", f"현재 {r['mapping_status'] or '-'} / 예상 {expected}", True))

        rows = conn.execute("""
            SELECT o.id,o.order_number,o.purchase_status,
                   COUNT(po.id) cnt,
                   SUM(CASE WHEN COALESCE(po.purchase_status,'발주대기') NOT IN ('발주완료','발주확정') THEN 1 ELSE 0 END) pending
              FROM orders o LEFT JOIN purchase_orders po ON po.order_id=o.id GROUP BY o.id
        """).fetchall()
        for r in rows:
            expected = "발주대기" if int(r["cnt"] or 0) == 0 or int(r["pending"] or 0) > 0 else "발주완료"
            if (r["purchase_status"] or "발주대기") != expected:
                result.append(IntegrityIssue("purchase_status", "주의", "상태동기화", r["id"], r["order_number"],
                    "주문 발주상태 불일치", f"현재 {r['purchase_status'] or '-'} / 예상 {expected}", True))

        rows = conn.execute("""
            SELECT o.id,o.order_number,o.shipment_status,
                   COUNT(s.id) cnt,
                   SUM(CASE WHEN s.shipment_status='배송완료' THEN 1 ELSE 0 END) complete_cnt,
                   SUM(CASE WHEN s.shipment_status='배송중' THEN 1 ELSE 0 END) moving_cnt
              FROM orders o LEFT JOIN shipments s ON s.order_id=o.id GROUP BY o.id
        """).fetchall()
        for r in rows:
            cnt = int(r["cnt"] or 0)
            if cnt == 0: expected = "배송대기"
            elif int(r["complete_cnt"] or 0) == cnt: expected = "배송완료"
            elif int(r["moving_cnt"] or 0) > 0: expected = "배송중"
            else: expected = "배송준비"
            if (r["shipment_status"] or "배송대기") != expected:
                result.append(IntegrityIssue("shipment_status", "주의", "상태동기화", r["id"], r["order_number"],
                    "주문 배송상태 불일치", f"현재 {r['shipment_status'] or '-'} / 예상 {expected}", True))
        return result

    def _check_required_fields(self, conn: sqlite3.Connection) -> list[IntegrityIssue]:
        result: list[IntegrityIssue] = []
        for r in conn.execute("""
            SELECT id,order_number,receiver_name,receiver_phone,address
              FROM orders
             WHERE TRIM(COALESCE(receiver_name,''))='' OR TRIM(COALESCE(receiver_phone,''))=''
                OR TRIM(COALESCE(address,''))=''
        """):
            missing = []
            if not (r["receiver_name"] or "").strip(): missing.append("수취인")
            if not (r["receiver_phone"] or "").strip(): missing.append("연락처")
            if not (r["address"] or "").strip(): missing.append("주소")
            result.append(IntegrityIssue("required_order", "긴급", "필수정보", r["id"], r["order_number"],
                "주문 필수정보 누락", ", ".join(missing), False))
        for r in conn.execute("""
            SELECT s.id,o.order_number,s.courier_name,s.tracking_number FROM shipments s
              JOIN orders o ON o.id=s.order_id
             WHERE TRIM(COALESCE(s.tracking_number,''))='' AND s.shipment_status IN ('배송중','배송완료')
        """):
            result.append(IntegrityIssue("required_shipment", "긴급", "필수정보", r["id"], r["order_number"] or f"송장 #{r['id']}",
                "배송중 송장번호 누락", f"택배사: {r['courier_name'] or '-'}", False))
        return result

    def _check_duplicates(self, conn: sqlite3.Connection) -> list[IntegrityIssue]:
        result: list[IntegrityIssue] = []
        for r in conn.execute("""
            SELECT tracking_number,COUNT(*) cnt FROM shipments
             WHERE TRIM(COALESCE(tracking_number,''))!=''
             GROUP BY tracking_number HAVING COUNT(*)>1
        """):
            result.append(IntegrityIssue("duplicate_tracking", "확인", "중복데이터", None, r["tracking_number"],
                "송장번호 중복", f"동일 송장번호가 {r['cnt']}건 등록되어 있습니다.", False))
        for r in conn.execute("""
            SELECT product_code,COUNT(*) cnt FROM products
             WHERE TRIM(COALESCE(product_code,''))!=''
             GROUP BY product_code HAVING COUNT(*)>1
        """):
            result.append(IntegrityIssue("duplicate_product", "확인", "중복데이터", None, r["product_code"],
                "상품코드 중복", f"동일 상품코드가 {r['cnt']}건 등록되어 있습니다.", False))
        return result
