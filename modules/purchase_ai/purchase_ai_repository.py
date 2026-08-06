"""Sprint 5.1.3 AI 발주 추천센터 데이터 접근 계층.

공급처 상품조건을 기준으로 매입단가, MOQ, 포장단위, 배송비를 비교해
주문상품별 최적 공급처를 추천하고 공급처별 발주계획을 생성한다.
"""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class PurchaseAIRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.db_path = Path(db_path) if db_path else project_root / "data" / "bisun_erp.db"
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}

    @classmethod
    def _add_column(cls, connection: sqlite3.Connection, table: str, definition: str) -> None:
        name = definition.split()[0]
        if name not in cls._columns(connection, table):
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

    def ensure_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS purchase_plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER,
                supplier_name TEXT NOT NULL DEFAULT '',
                order_count INTEGER NOT NULL DEFAULT 0,
                item_count INTEGER NOT NULL DEFAULT 0,
                total_quantity INTEGER NOT NULL DEFAULT 0,
                estimated_amount INTEGER NOT NULL DEFAULT 0,
                deadline_time TEXT,
                status TEXT NOT NULL DEFAULT '초안',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS purchase_plan_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                order_item_id INTEGER NOT NULL,
                order_number TEXT NOT NULL DEFAULT '',
                product_id INTEGER,
                product_code TEXT,
                product_name TEXT NOT NULL DEFAULT '',
                option_name TEXT,
                quantity INTEGER NOT NULL DEFAULT 0,
                purchase_price INTEGER NOT NULL DEFAULT 0,
                estimated_amount INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(plan_id, order_item_id),
                FOREIGN KEY (plan_id) REFERENCES purchase_plan(id) ON DELETE CASCADE,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS supplier_deadline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL UNIQUE,
                supplier_name TEXT NOT NULL DEFAULT '',
                deadline_time TEXT NOT NULL DEFAULT '14:00',
                delivery_days INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS supplier_score (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL UNIQUE,
                supplier_name TEXT NOT NULL DEFAULT '',
                delivery_score REAL NOT NULL DEFAULT 100,
                stock_score REAL NOT NULL DEFAULT 100,
                return_score REAL NOT NULL DEFAULT 100,
                delay_score REAL NOT NULL DEFAULT 100,
                total_score REAL NOT NULL DEFAULT 100,
                evaluated_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
            )
            """,
        ]
        with self.connect() as connection:
            for statement in statements:
                connection.execute(statement)
            plan_columns = [
                "recommended_reason TEXT NOT NULL DEFAULT ''",
                "priority INTEGER NOT NULL DEFAULT 3",
                "confirmed INTEGER NOT NULL DEFAULT 0",
                "product_amount INTEGER NOT NULL DEFAULT 0",
                "shipping_fee INTEGER NOT NULL DEFAULT 0",
                "savings_amount INTEGER NOT NULL DEFAULT 0",
                "optimization_mode TEXT NOT NULL DEFAULT '조건최적화'",
            ]
            item_columns = [
                "recommended_reason TEXT NOT NULL DEFAULT ''",
                "priority INTEGER NOT NULL DEFAULT 3",
                "excluded INTEGER NOT NULL DEFAULT 0",
                "confirmed INTEGER NOT NULL DEFAULT 0",
                "supplier_condition_id INTEGER",
                "ordered_quantity INTEGER NOT NULL DEFAULT 0",
                "purchase_quantity INTEGER NOT NULL DEFAULT 0",
                "waste_quantity INTEGER NOT NULL DEFAULT 0",
                "shipping_fee INTEGER NOT NULL DEFAULT 0",
                "candidate_count INTEGER NOT NULL DEFAULT 0",
                "savings_amount INTEGER NOT NULL DEFAULT 0",
                "package_unit INTEGER NOT NULL DEFAULT 1",
                "minimum_order_quantity INTEGER NOT NULL DEFAULT 1",
                "courier_name TEXT NOT NULL DEFAULT ''",
            ]
            for definition in plan_columns:
                self._add_column(connection, "purchase_plan", definition)
            for definition in item_columns:
                self._add_column(connection, "purchase_plan_item", definition)
            for statement in (
                "CREATE INDEX IF NOT EXISTS idx_purchase_plan_created_at ON purchase_plan(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_purchase_plan_supplier ON purchase_plan(supplier_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_purchase_plan_priority ON purchase_plan(priority, status)",
                "CREATE INDEX IF NOT EXISTS idx_purchase_plan_item_plan ON purchase_plan_item(plan_id)",
                "CREATE INDEX IF NOT EXISTS idx_purchase_plan_item_order_item ON purchase_plan_item(order_item_id)",
                "CREATE INDEX IF NOT EXISTS idx_spc_product_active ON supplier_product_conditions(product_id, is_active)",
            ):
                connection.execute(statement)
            self._seed_supplier_defaults(connection)
            connection.commit()

    @staticmethod
    def _seed_supplier_defaults(connection: sqlite3.Connection) -> None:
        connection.execute("""
            INSERT OR IGNORE INTO supplier_deadline
                (supplier_id, supplier_name, deadline_time, delivery_days, enabled)
            SELECT id, supplier_name, '14:00', 1, is_active FROM suppliers
        """)
        connection.execute("""
            INSERT OR IGNORE INTO supplier_score
                (supplier_id, supplier_name, delivery_score, stock_score,
                 return_score, delay_score, total_score, evaluated_at)
            SELECT id, supplier_name, 100, 100, 100, 100, 100, CURRENT_TIMESTAMP FROM suppliers
        """)

    def _eligible_rows(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute("""
            SELECT oi.id AS order_item_id, oi.order_id, o.order_number, o.ordered_at,
                   oi.product_id, COALESCE(p.product_code, '') AS product_code,
                   COALESCE(p.product_name, oi.platform_product_name) AS product_name,
                   COALESCE(oi.option_name, p.option_name, '') AS option_name,
                   oi.quantity AS ordered_quantity,
                   oi.supplier_id AS mapped_supplier_id,
                   p.supplier_id AS product_supplier_id,
                   COALESCE(p.purchase_price, 0) AS fallback_purchase_price
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            LEFT JOIN products p ON p.id = oi.product_id
            WHERE oi.product_id IS NOT NULL
              AND COALESCE(oi.mapping_status, '') NOT IN ('미매핑', '매핑실패')
              AND COALESCE(o.payment_status, '') IN ('결제완료', '입금완료')
              AND COALESCE(o.order_status, '') NOT IN ('주문취소', '취소완료', '반품완료')
              AND COALESCE(o.purchase_status, '발주대기') NOT IN ('발주완료', '발주취소')
              AND NOT EXISTS (
                  SELECT 1 FROM purchase_orders po
                  WHERE po.order_item_id = oi.id
                    AND COALESCE(po.purchase_status, '') NOT IN ('발주취소', '취소')
              )
            ORDER BY o.ordered_at, o.id, oi.id
        """).fetchall()

    @staticmethod
    def _purchase_quantity(order_qty: int, moq: int, package_unit: int) -> int:
        order_qty = max(1, int(order_qty or 1))
        moq = max(1, int(moq or 1))
        package_unit = max(1, int(package_unit or 1))
        required = max(order_qty, moq)
        return int(math.ceil(required / package_unit) * package_unit)

    def _condition_candidates(self, connection: sqlite3.Connection, row: sqlite3.Row) -> list[dict[str, Any]]:
        candidates = [dict(candidate) for candidate in connection.execute("""
            SELECT c.id AS condition_id, c.supplier_id, s.supplier_name,
                   c.purchase_price, c.minimum_order_quantity, c.package_unit,
                   c.shipping_fee, c.courier_name, c.order_deadline,
                   c.is_default, COALESCE(sc.total_score,100) AS supplier_score
            FROM supplier_product_conditions c
            JOIN suppliers s ON s.id=c.supplier_id AND s.is_active=1
            LEFT JOIN supplier_score sc ON sc.supplier_id=c.supplier_id
            WHERE c.product_id=? AND c.is_active=1
            ORDER BY c.is_default DESC, c.purchase_price ASC, c.shipping_fee ASC
        """, (row["product_id"],)).fetchall()]
        if candidates:
            return candidates
        supplier_id = row["mapped_supplier_id"] or row["product_supplier_id"]
        if supplier_id:
            supplier = connection.execute("""
                SELECT s.id AS supplier_id, s.supplier_name,
                       COALESCE(s.default_shipping_fee,0) AS shipping_fee,
                       COALESCE(s.default_courier,'') AS courier_name,
                       COALESCE(sc.total_score,100) AS supplier_score
                FROM suppliers s LEFT JOIN supplier_score sc ON sc.supplier_id=s.id
                WHERE s.id=? AND s.is_active=1
            """, (supplier_id,)).fetchone()
            if supplier:
                return [{
                    "condition_id": None,
                    "supplier_id": supplier["supplier_id"],
                    "supplier_name": supplier["supplier_name"],
                    "purchase_price": int(row["fallback_purchase_price"] or 0),
                    "minimum_order_quantity": 1,
                    "package_unit": 1,
                    "shipping_fee": int(supplier["shipping_fee"] or 0),
                    "courier_name": supplier["courier_name"] or "",
                    "order_deadline": "",
                    "is_default": 1,
                    "supplier_score": float(supplier["supplier_score"] or 100),
                }]
        return []

    def _select_best_candidate(self, row: sqlite3.Row, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        ordered_qty = int(row["ordered_quantity"] or 1)
        evaluated: list[dict[str, Any]] = []
        for candidate in candidates:
            purchase_qty = self._purchase_quantity(
                ordered_qty,
                int(candidate.get("minimum_order_quantity") or 1),
                int(candidate.get("package_unit") or 1),
            )
            product_amount = purchase_qty * int(candidate.get("purchase_price") or 0)
            shipping_fee = int(candidate.get("shipping_fee") or 0)
            total_cost = product_amount + shipping_fee
            score = float(candidate.get("supplier_score") or 100)
            # 동점일 때 공급처 성적과 기본공급처를 우선한다.
            ranking = (total_cost, -score, -int(candidate.get("is_default") or 0))
            evaluated.append({**candidate, "purchase_quantity": purchase_qty,
                              "product_amount": product_amount, "total_cost": total_cost,
                              "ranking": ranking})
        evaluated.sort(key=lambda item: item["ranking"])
        best = evaluated[0]
        second_cost = evaluated[1]["total_cost"] if len(evaluated) > 1 else best["total_cost"]
        best["savings_amount"] = max(0, int(second_cost - best["total_cost"]))
        best["candidate_count"] = len(evaluated)
        best["waste_quantity"] = max(0, int(best["purchase_quantity"] - ordered_qty))
        reason = [f"총비용 {best['total_cost']:,}원"]
        if best["candidate_count"] > 1:
            reason.append(f"{best['candidate_count']}개 공급조건 비교")
        if best["savings_amount"]:
            reason.append(f"차선 대비 {best['savings_amount']:,}원 절감")
        if best["waste_quantity"]:
            reason.append(f"MOQ/포장단위로 {best['waste_quantity']}개 추가")
        best["reason"] = " · ".join(reason)
        return best

    @staticmethod
    def _priority(deadline_time: str, oldest_ordered_at: str | None, order_count: int, item_count: int) -> tuple[int, str]:
        now = datetime.now()
        reasons: list[str] = []
        priority = 3
        try:
            deadline = datetime.strptime(f"{now:%Y-%m-%d} {deadline_time}", "%Y-%m-%d %H:%M")
            minutes = int((deadline - now).total_seconds() // 60)
            if minutes <= 0:
                priority = 1; reasons.append("발주 마감 경과")
            elif minutes <= 60:
                priority = 1; reasons.append(f"마감 {minutes}분 전")
            elif minutes <= 180:
                priority = min(priority, 2); reasons.append(f"마감 {minutes // 60}시간 전")
        except (TypeError, ValueError):
            pass
        if oldest_ordered_at:
            try:
                ordered = datetime.fromisoformat(str(oldest_ordered_at).replace("Z", "+00:00")).replace(tzinfo=None)
                age_hours = (now - ordered).total_seconds() / 3600
                if age_hours >= 24:
                    priority = 1; reasons.append("24시간 이상 미발주")
                elif age_hours >= 12:
                    priority = min(priority, 2); reasons.append("12시간 이상 미발주")
            except (TypeError, ValueError):
                pass
        if order_count >= 10:
            priority = min(priority, 2); reasons.append(f"주문 {order_count}건 집중")
        if item_count >= 10:
            reasons.append(f"상품 {item_count}건 합산")
        if not reasons:
            reasons.append("결제·매핑 완료 발주대상")
        return priority, " · ".join(reasons)

    def generate_supplier_groups(self) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            draft_ids = [r["id"] for r in connection.execute("""
                SELECT id FROM purchase_plan
                WHERE date(created_at) = date('now', 'localtime')
                  AND status IN ('초안', '발주대기', '긴급') AND confirmed = 0
            """).fetchall()]
            if draft_ids:
                marks = ",".join("?" for _ in draft_ids)
                connection.execute(f"DELETE FROM purchase_plan_item WHERE plan_id IN ({marks})", draft_ids)
                connection.execute(f"DELETE FROM purchase_plan WHERE id IN ({marks})", draft_ids)

            rows = self._eligible_rows(connection)
            selected: list[tuple[sqlite3.Row, dict[str, Any]]] = []
            excluded_count = 0
            total_savings = 0
            for row in rows:
                candidates = self._condition_candidates(connection, row)
                if not candidates:
                    excluded_count += 1
                    continue
                best = self._select_best_candidate(row, candidates)
                total_savings += int(best["savings_amount"] or 0)
                selected.append((row, best))

            grouped: dict[int, list[tuple[sqlite3.Row, dict[str, Any]]]] = {}
            for row, best in selected:
                grouped.setdefault(int(best["supplier_id"]), []).append((row, best))

            total_amount = 0
            urgent_count = 0
            for supplier_id, items in grouped.items():
                supplier_name = str(items[0][1]["supplier_name"])
                deadlines = [str(best.get("order_deadline") or "") for _, best in items if best.get("order_deadline")]
                fallback_deadline = connection.execute(
                    "SELECT deadline_time FROM supplier_deadline WHERE supplier_id=?", (supplier_id,)
                ).fetchone()
                deadline_time = min(deadlines) if deadlines else str((fallback_deadline[0] if fallback_deadline else "14:00") or "14:00")
                order_count = len({int(row["order_id"]) for row, _ in items})
                item_count = len(items)
                total_quantity = sum(int(best["purchase_quantity"] or 0) for _, best in items)
                product_amount = sum(int(best["product_amount"] or 0) for _, best in items)
                shipping_fee = max((int(best["shipping_fee"] or 0) for _, best in items), default=0)
                estimated_amount = product_amount + shipping_fee
                savings_amount = sum(int(best["savings_amount"] or 0) for _, best in items)
                oldest = min((str(row["ordered_at"]) for row, _ in items if row["ordered_at"]), default=None)
                priority, urgency_reason = self._priority(deadline_time, oldest, order_count, item_count)
                status = "긴급" if priority == 1 else "발주대기"
                urgent_count += int(priority == 1)
                total_amount += estimated_amount
                optimization_reason = f"조건 최적화 · 상품 {product_amount:,}원 + 배송비 {shipping_fee:,}원"
                if savings_amount:
                    optimization_reason += f" · 예상 절감 {savings_amount:,}원"
                reason = f"{urgency_reason} · {optimization_reason}"
                cursor = connection.execute("""
                    INSERT INTO purchase_plan
                        (supplier_id, supplier_name, order_count, item_count, total_quantity,
                         estimated_amount, product_amount, shipping_fee, savings_amount,
                         deadline_time, status, recommended_reason, priority,
                         optimization_mode, confirmed, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '조건최적화', 0,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (supplier_id, supplier_name, order_count, item_count, total_quantity,
                      estimated_amount, product_amount, shipping_fee, savings_amount,
                      deadline_time, status, reason, priority))
                plan_id = int(cursor.lastrowid)
                for row, best in items:
                    connection.execute("""
                        INSERT INTO purchase_plan_item
                            (plan_id, order_id, order_item_id, order_number, product_id,
                             product_code, product_name, option_name, quantity,
                             ordered_quantity, purchase_quantity, waste_quantity,
                             purchase_price, estimated_amount, shipping_fee,
                             supplier_condition_id, candidate_count, savings_amount,
                             package_unit, minimum_order_quantity, courier_name,
                             recommended_reason, priority, excluded, confirmed)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                    """, (
                        plan_id, int(row["order_id"]), int(row["order_item_id"]), row["order_number"],
                        row["product_id"], row["product_code"], row["product_name"], row["option_name"],
                        int(best["purchase_quantity"]), int(row["ordered_quantity"]), int(best["purchase_quantity"]),
                        int(best["waste_quantity"]), int(best["purchase_price"] or 0), int(best["product_amount"] or 0),
                        int(best["shipping_fee"] or 0), best.get("condition_id"), int(best["candidate_count"] or 0),
                        int(best["savings_amount"] or 0), int(best["package_unit"] or 1),
                        int(best["minimum_order_quantity"] or 1), str(best.get("courier_name") or ""),
                        str(best["reason"]), priority,
                    ))

            connection.commit()
        return {
            "plan_count": len(grouped), "item_count": len(selected), "supplier_count": len(grouped),
            "estimated_amount": total_amount, "excluded_count": excluded_count,
            "urgent_count": urgent_count, "savings_amount": total_savings,
        }

    def recalculate_recommendations(self) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT p.id, p.deadline_time, p.order_count, p.item_count,
                       MIN(o.ordered_at) AS oldest_ordered_at
                FROM purchase_plan p
                LEFT JOIN purchase_plan_item pi ON pi.plan_id = p.id AND pi.excluded = 0
                LEFT JOIN orders o ON o.id = pi.order_id
                WHERE p.confirmed = 0 AND p.status IN ('초안','발주대기','긴급')
                GROUP BY p.id
            """).fetchall()
            urgent = 0
            for row in rows:
                priority, urgency = self._priority(str(row["deadline_time"] or "14:00"), row["oldest_ordered_at"],
                                                   int(row["order_count"] or 0), int(row["item_count"] or 0))
                plan = connection.execute("SELECT product_amount,shipping_fee,savings_amount FROM purchase_plan WHERE id=?", (row["id"],)).fetchone()
                reason = f"{urgency} · 조건 최적화 · 상품 {int(plan['product_amount'] or 0):,}원 + 배송비 {int(plan['shipping_fee'] or 0):,}원"
                if int(plan["savings_amount"] or 0):
                    reason += f" · 예상 절감 {int(plan['savings_amount']):,}원"
                status = "긴급" if priority == 1 else "발주대기"
                urgent += int(priority == 1)
                connection.execute("UPDATE purchase_plan SET priority=?,recommended_reason=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                                   (priority, reason, status, int(row["id"])))
                connection.execute("UPDATE purchase_plan_item SET priority=? WHERE plan_id=? AND confirmed=0",
                                   (priority, int(row["id"])))
            connection.commit()
        return {"plan_count": len(rows), "urgent_count": urgent}

    def fetch_plan_items(self, plan_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT id, order_number, product_code, product_name, option_name,
                       quantity, ordered_quantity, purchase_quantity, waste_quantity,
                       purchase_price, estimated_amount, excluded, confirmed,
                       recommended_reason, priority, candidate_count, savings_amount,
                       package_unit, minimum_order_quantity, courier_name
                FROM purchase_plan_item
                WHERE plan_id = ?
                ORDER BY excluded, product_name, option_name, order_number
            """, (plan_id,)).fetchall()
        return [dict(row) for row in rows]

    def fetch_plan_preview(self, plan_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            plan = connection.execute("""
                SELECT p.*, COALESCE(s.total_score,100) AS supplier_score
                FROM purchase_plan p LEFT JOIN supplier_score s ON s.supplier_id=p.supplier_id
                WHERE p.id=?
            """, (plan_id,)).fetchone()
            if not plan:
                raise ValueError("발주계획을 찾을 수 없습니다.")
            items = connection.execute("""
                SELECT product_id, product_code, product_name, option_name,
                       COUNT(DISTINCT order_id) AS order_count,
                       SUM(ordered_quantity) AS ordered_quantity,
                       SUM(purchase_quantity) AS quantity,
                       SUM(waste_quantity) AS waste_quantity,
                       MAX(purchase_price) AS purchase_price,
                       SUM(estimated_amount) AS estimated_amount,
                       MAX(package_unit) AS package_unit,
                       MAX(minimum_order_quantity) AS minimum_order_quantity,
                       MAX(courier_name) AS courier_name
                FROM purchase_plan_item
                WHERE plan_id=? AND excluded=0
                GROUP BY product_id, product_code, product_name, option_name, purchase_price
                ORDER BY product_name, option_name
            """, (plan_id,)).fetchall()
        return {"plan": dict(plan), "items": [dict(row) for row in items]}

    def set_item_excluded(self, item_id: int, excluded: bool) -> None:
        with self.connect() as connection:
            row = connection.execute("SELECT plan_id FROM purchase_plan_item WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise ValueError("발주계획 상품을 찾을 수 없습니다.")
            connection.execute("UPDATE purchase_plan_item SET excluded=? WHERE id=?", (1 if excluded else 0, item_id))
            self._refresh_plan_totals(connection, int(row["plan_id"]))
            connection.commit()

    @staticmethod
    def _refresh_plan_totals(connection: sqlite3.Connection, plan_id: int) -> None:
        totals = connection.execute("""
            SELECT COUNT(*) AS item_count, COUNT(DISTINCT order_id) AS order_count,
                   COALESCE(SUM(purchase_quantity),0) AS total_quantity,
                   COALESCE(SUM(estimated_amount),0) AS product_amount,
                   COALESCE(MAX(shipping_fee),0) AS shipping_fee,
                   COALESCE(SUM(savings_amount),0) AS savings_amount
            FROM purchase_plan_item WHERE plan_id=? AND excluded=0
        """, (plan_id,)).fetchone()
        estimated = int(totals["product_amount"] or 0) + int(totals["shipping_fee"] or 0)
        connection.execute("""
            UPDATE purchase_plan SET item_count=?,order_count=?,total_quantity=?,product_amount=?,
                shipping_fee=?,estimated_amount=?,savings_amount=?,updated_at=CURRENT_TIMESTAMP WHERE id=?
        """, (totals["item_count"], totals["order_count"], totals["total_quantity"], totals["product_amount"],
              totals["shipping_fee"], estimated, totals["savings_amount"], plan_id))

    def confirm_plan(self, plan_id: int) -> dict[str, int]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            plan = connection.execute("SELECT * FROM purchase_plan WHERE id=?", (plan_id,)).fetchone()
            if not plan:
                raise ValueError("발주계획을 찾을 수 없습니다.")
            if int(plan["confirmed"] or 0):
                raise ValueError("이미 확정된 발주계획입니다.")
            items = connection.execute("""
                SELECT pi.*, o.receiver_name, o.receiver_phone, o.postal_code, o.address,
                       o.detail_address, o.delivery_message
                FROM purchase_plan_item pi JOIN orders o ON o.id=pi.order_id
                WHERE pi.plan_id=? AND pi.excluded=0 AND pi.confirmed=0
            """, (plan_id,)).fetchall()
            if not items:
                raise ValueError("확정할 발주상품이 없습니다.")
            inserted = 0
            for item in items:
                address = " ".join(filter(None, [item["address"], item["detail_address"]]))
                cursor = connection.execute("""
                    INSERT OR IGNORE INTO purchase_orders
                        (supplier_id, order_id, order_item_id, supplier_name, order_number,
                         product_name, option_name, quantity, receiver_name, receiver_phone,
                         postal_code, address, delivery_message, purchase_status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '발주확정', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (plan["supplier_id"], item["order_id"], item["order_item_id"], plan["supplier_name"],
                      item["order_number"], item["product_name"], item["option_name"], item["purchase_quantity"],
                      item["receiver_name"], item["receiver_phone"], item["postal_code"], address,
                      item["delivery_message"]))
                inserted += max(cursor.rowcount, 0)
                connection.execute("UPDATE order_items SET supplier_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                                   (plan["supplier_id"], item["order_item_id"]))
                connection.execute("UPDATE purchase_plan_item SET confirmed=1 WHERE id=?", (item["id"],))
            order_ids = {int(item["order_id"]) for item in items}
            for order_id in order_ids:
                total = connection.execute("SELECT COUNT(*) FROM order_items WHERE order_id=?", (order_id,)).fetchone()[0]
                confirmed = connection.execute("""
                    SELECT COUNT(*) FROM purchase_orders
                    WHERE order_id=? AND COALESCE(purchase_status,'') NOT IN ('발주취소','취소')
                """, (order_id,)).fetchone()[0]
                state = "발주완료" if total > 0 and confirmed >= total else "부분발주"
                connection.execute("UPDATE orders SET purchase_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (state, order_id))
            connection.execute("UPDATE purchase_plan SET status='발주확정',confirmed=1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (plan_id,))
            connection.commit()
        return {"inserted_count": inserted, "order_count": len(order_ids), "item_count": len(items)}

    def fetch_dashboard(self) -> dict[str, Any]:
        with self.connect() as connection:
            kpi = connection.execute("""
                SELECT COUNT(*) AS plan_count, COUNT(DISTINCT supplier_id) AS supplier_count,
                       COALESCE(SUM(CASE WHEN priority=1 AND confirmed=0 THEN 1 ELSE 0 END),0) AS urgent_count,
                       COALESCE(SUM(estimated_amount),0) AS estimated_amount,
                       COALESCE(SUM(savings_amount),0) AS savings_amount
                FROM purchase_plan WHERE date(created_at)=date('now','localtime')
            """).fetchone()
            pending = connection.execute("""
                SELECT COUNT(*) FROM order_items oi JOIN orders o ON o.id=oi.order_id
                WHERE COALESCE(o.payment_status,'') IN ('결제완료','입금완료')
                  AND COALESCE(o.purchase_status,'발주대기') NOT IN ('발주완료','발주취소')
                  AND NOT EXISTS (SELECT 1 FROM purchase_orders po WHERE po.order_item_id=oi.id
                                  AND COALESCE(po.purchase_status,'') NOT IN ('발주취소','취소'))
            """).fetchone()[0]
            plans = connection.execute("""
                SELECT p.id,p.supplier_id,p.supplier_name,p.order_count,p.item_count,p.total_quantity,
                       p.estimated_amount,p.product_amount,p.shipping_fee,p.savings_amount,
                       COALESCE(d.deadline_time,p.deadline_time,'-') AS deadline_time,
                       p.status,p.recommended_reason,p.priority,p.confirmed,p.created_at,
                       COALESCE(sc.total_score,100) AS supplier_score
                FROM purchase_plan p
                LEFT JOIN supplier_deadline d ON d.supplier_id=p.supplier_id
                LEFT JOIN supplier_score sc ON sc.supplier_id=p.supplier_id
                ORDER BY p.confirmed, p.priority, p.created_at DESC LIMIT 200
            """).fetchall()
            recent = connection.execute("""
                SELECT id,supplier_name,order_count,total_quantity,estimated_amount,status,created_at
                FROM purchase_plan ORDER BY created_at DESC LIMIT 20
            """).fetchall()
        return {"kpi": dict(kpi), "pending_item_count": int(pending or 0),
                "plans": [dict(r) for r in plans], "recent": [dict(r) for r in recent]}

    def get_schema_status(self) -> dict[str, int]:
        names = ("purchase_plan", "purchase_plan_item", "supplier_deadline", "supplier_score")
        with self.connect() as connection:
            return {name: int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] or 0) for name in names}
