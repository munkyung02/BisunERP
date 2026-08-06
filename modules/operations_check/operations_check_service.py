from __future__ import annotations

import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CheckItem:
    level: str
    category: str
    reference: str
    title: str
    detail: str
    target: str


class OperationsCheckService:
    """실무 시작 전 최소 점검과 안전한 테스트 주문 도구를 제공합니다."""

    TEST_PREFIX = "TEST-"

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(__file__).resolve().parents[2] / "data" / "bisun_erp.db"
        self.backup_dir = self.db_path.parent / "backups"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
        return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))

    def create_backup(self) -> Path:
        """현재 DB의 일관된 복사본을 backups 폴더에 생성합니다."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self.backup_dir / f"bisun_erp_before_live_{stamp}.db"
        with self._connect() as source, sqlite3.connect(target) as destination:
            source.backup(destination)
        return target

    def create_test_order(self) -> str:
        """활성 공급처가 연결된 첫 상품으로 TEST 주문 1건을 생성합니다."""
        with self._connect() as conn:
            product = conn.execute(
                """
                SELECT p.id, p.product_name, p.option_name, p.platform,
                       p.platform_product_name, p.sale_price, p.purchase_round,
                       p.supplier_id
                  FROM products p
                 WHERE COALESCE(p.is_active, 1)=1
                   AND p.supplier_id IS NOT NULL
                 ORDER BY p.id
                 LIMIT 1
                """
            ).fetchone()
            if product is None:
                raise ValueError("활성 상태이며 공급처가 연결된 상품이 없습니다. 상품·공급처를 먼저 등록하세요.")

            order_number = f"{self.TEST_PREFIX}{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            platform = (product["platform"] or "테스트").strip() or "테스트"
            unit_price = int(product["sale_price"] or 0)
            conn.execute(
                """
                INSERT INTO orders (
                    platform, order_number, ordered_at, receiver_name, receiver_phone,
                    postal_code, address, detail_address, delivery_message,
                    order_status, payment_status, mapping_status, purchase_status,
                    shipment_status, total_amount, source_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    platform, order_number, now, "테스트고객", "010-0000-0000",
                    "00000", "테스트 주소", "삭제 가능한 TEST 주문", "배송 전 연락",
                    "주문접수", "결제완료", "매핑완료", "발주대기",
                    "배송대기", unit_price, "ERP 실무점검 테스트 주문",
                ),
            )
            order_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """
                INSERT INTO order_items (
                    order_id, product_id, platform_product_name, option_name,
                    quantity, unit_price, total_price, supplier_id,
                    purchase_round, mapping_status
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, '매핑완료')
                """,
                (
                    order_id,
                    int(product["id"]),
                    product["platform_product_name"] or product["product_name"],
                    product["option_name"],
                    unit_price,
                    unit_price,
                    int(product["supplier_id"]),
                    product["purchase_round"],
                ),
            )
            conn.commit()
            return order_number

    def count_test_orders(self) -> int:
        with self._connect() as conn:
            return int(conn.execute(
                "SELECT COUNT(*) FROM orders WHERE order_number LIKE ?",
                (f"{self.TEST_PREFIX}%",),
            ).fetchone()[0] or 0)

    def delete_test_orders(self) -> int:
        """주문번호가 TEST-로 시작하는 주문만 삭제합니다."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM orders WHERE order_number LIKE ?",
                (f"{self.TEST_PREFIX}%",),
            ).fetchall()
            ids = [int(row[0]) for row in rows]
            if not ids:
                return 0
            placeholders = ",".join("?" for _ in ids)
            # 외래키가 없는 확장 테이블도 안전하게 먼저 정리합니다.
            for table in ("purchase_plan_item", "purchase_orders", "payments", "shipments"):
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    continue
                columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                if "order_id" in columns:
                    conn.execute(f"DELETE FROM {table} WHERE order_id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", ids)
            conn.commit()
            return len(ids)

    def get_summary(self) -> dict[str, int]:
        with self._connect() as conn:
            def count(sql: str, params: tuple[Any, ...] = ()) -> int:
                return int(conn.execute(sql, params).fetchone()[0] or 0)

            return {
                "활성 공급처": count("SELECT COUNT(*) FROM suppliers WHERE COALESCE(is_active,1)=1"),
                "활성 상품": count("SELECT COUNT(*) FROM products WHERE COALESCE(is_active,1)=1"),
                "미매핑": count("SELECT COUNT(*) FROM order_items WHERE COALESCE(mapping_status,'미매핑')!='매핑완료'"),
                "발주대기": count("SELECT COUNT(*) FROM orders WHERE COALESCE(payment_status,'')='결제완료' AND COALESCE(mapping_status,'')='매핑완료' AND COALESCE(purchase_status,'발주대기') NOT IN ('발주완료','발주확정')"),
                "송장대기": count("SELECT COUNT(*) FROM orders WHERE COALESCE(purchase_status,'') IN ('발주완료','발주확정') AND COALESCE(shipment_status,'배송대기') IN ('배송대기','배송준비')"),
            }

    def get_checks(self, category: str = "전체", keyword: str = "") -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows: list[CheckItem] = []
            rows.extend(self._master_data_checks(conn))
            rows.extend(self._order_checks(conn))
            rows.extend(self._work_checks(conn))

        text = keyword.strip().lower()
        result = []
        for row in rows:
            if category != "전체" and row.category != category:
                continue
            if text and text not in " ".join((row.reference, row.title, row.detail)).lower():
                continue
            result.append(asdict(row))
        level_order = {"긴급": 0, "확인": 1, "준비": 2}
        return sorted(result, key=lambda x: (level_order.get(x["level"], 9), x["category"], x["reference"]))

    def _master_data_checks(self, conn: sqlite3.Connection) -> list[CheckItem]:
        rows: list[CheckItem] = []
        supplier_count = int(conn.execute("SELECT COUNT(*) FROM suppliers WHERE COALESCE(is_active,1)=1").fetchone()[0] or 0)
        product_count = int(conn.execute("SELECT COUNT(*) FROM products WHERE COALESCE(is_active,1)=1").fetchone()[0] or 0)
        if supplier_count == 0:
            rows.append(CheckItem("긴급", "기초데이터", "공급처", "활성 공급처가 없습니다", "일괄등록 또는 공급처관리에서 실제 공급처를 등록하세요.", "일괄등록"))
        if product_count == 0:
            rows.append(CheckItem("긴급", "기초데이터", "상품", "활성 상품이 없습니다", "일괄등록 또는 상품관리에서 실제 판매상품을 등록하세요.", "일괄등록"))

        for r in conn.execute("""
            SELECT p.id,p.product_code,p.product_name,p.option_name
              FROM products p
             WHERE COALESCE(p.is_active,1)=1 AND p.supplier_id IS NULL
             ORDER BY p.id DESC LIMIT 300
        """):
            rows.append(CheckItem("긴급", "기초데이터", r["product_code"] or f"상품 #{r['id']}", "상품 공급처 누락", f"{r['product_name']} / {r['option_name'] or '-'}", "상품관리"))

        has_unit = self._has_column(conn, "products", "purchase_unit")
        has_deadline = self._has_column(conn, "products", "purchase_deadline")
        if has_unit:
            for r in conn.execute("""
                SELECT id,product_code,product_name,option_name FROM products
                 WHERE COALESCE(is_active,1)=1 AND TRIM(COALESCE(purchase_unit,''))=''
                 ORDER BY id DESC LIMIT 300
            """):
                rows.append(CheckItem("확인", "기초데이터", r["product_code"] or f"상품 #{r['id']}", "발주단위 미입력", f"{r['product_name']} / {r['option_name'] or '-'}", "상품관리"))
        if has_deadline:
            missing = int(conn.execute("SELECT COUNT(*) FROM products WHERE COALESCE(is_active,1)=1 AND TRIM(COALESCE(purchase_deadline,''))='' ").fetchone()[0] or 0)
            if missing:
                rows.append(CheckItem("준비", "기초데이터", "상품 마감시간", "마감시간 미입력 상품", f"{missing:,}개 상품은 마감시간이 비어 있습니다. 당장 필요한 상품부터 입력하면 됩니다.", "상품관리"))
        return rows

    def _order_checks(self, conn: sqlite3.Connection) -> list[CheckItem]:
        rows: list[CheckItem] = []
        for r in conn.execute("""
            SELECT id,order_number,receiver_name,receiver_phone,address
              FROM orders
             WHERE TRIM(COALESCE(receiver_name,''))='' OR TRIM(COALESCE(receiver_phone,''))='' OR TRIM(COALESCE(address,''))=''
             ORDER BY id DESC LIMIT 300
        """):
            missing=[]
            if not (r["receiver_name"] or "").strip(): missing.append("수취인")
            if not (r["receiver_phone"] or "").strip(): missing.append("연락처")
            if not (r["address"] or "").strip(): missing.append("주소")
            rows.append(CheckItem("긴급", "주문정보", r["order_number"], "배송 필수정보 누락", ", ".join(missing), "주문관리"))

        for r in conn.execute("""
            SELECT o.order_number,oi.platform_product_name,oi.option_name
              FROM order_items oi JOIN orders o ON o.id=oi.order_id
             WHERE COALESCE(oi.mapping_status,'미매핑')!='매핑완료'
             ORDER BY oi.id DESC LIMIT 300
        """):
            rows.append(CheckItem("긴급", "상품매핑", r["order_number"], "미매핑 주문상품", f"{r['platform_product_name']} / {r['option_name'] or '-'}", "상품매핑"))
        return rows

    def _work_checks(self, conn: sqlite3.Connection) -> list[CheckItem]:
        rows: list[CheckItem] = []
        for r in conn.execute("""
            SELECT order_number,receiver_name,ordered_at FROM orders
             WHERE COALESCE(payment_status,'')='결제완료'
               AND COALESCE(mapping_status,'')='매핑완료'
               AND COALESCE(purchase_status,'발주대기') NOT IN ('발주완료','발주확정')
             ORDER BY ordered_at,id LIMIT 300
        """):
            rows.append(CheckItem("확인", "발주", r["order_number"], "발주 가능한 주문", f"{r['receiver_name'] or '-'} · {str(r['ordered_at'] or '-')[:16]}", "AI 발주센터"))

        for r in conn.execute("""
            SELECT order_number,receiver_name,updated_at FROM orders
             WHERE COALESCE(purchase_status,'') IN ('발주완료','발주확정')
               AND COALESCE(shipment_status,'배송대기') IN ('배송대기','배송준비')
             ORDER BY updated_at,id LIMIT 300
        """):
            rows.append(CheckItem("확인", "송장", r["order_number"], "송장 등록 대기", f"{r['receiver_name'] or '-'} · {str(r['updated_at'] or '-')[:16]}", "송장관리"))
        return rows
