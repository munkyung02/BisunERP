from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.database import Database


@dataclass(frozen=True)
class WorkTask:
    key: str
    title: str
    description: str
    count: int
    target: str
    priority: int


class WorkCenterService:
    """현재 DB 상태를 읽어 실제 처리할 작업을 집계합니다."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def get_summary(self) -> dict[str, int]:
        with self.database.connect() as connection:
            return {
                "products": self._scalar(connection, "SELECT COUNT(*) FROM products WHERE COALESCE(is_active, 1)=1"),
                "suppliers": self._scalar(connection, "SELECT COUNT(*) FROM suppliers WHERE COALESCE(is_active, 1)=1"),
                "orders_today": self._scalar(connection, "SELECT COUNT(*) FROM orders WHERE date(COALESCE(ordered_at, created_at))=date('now','localtime')"),
                "purchases_today": self._scalar(connection, "SELECT COUNT(*) FROM purchase_orders WHERE date(COALESCE(purchased_at, created_at))=date('now','localtime')"),
            }

    def get_tasks(self) -> list[WorkTask]:
        with self.database.connect() as connection:
            tasks = [
                WorkTask(
                    "unmapped_orders", "상품 미매핑 주문",
                    "상품 연결이 끝나지 않은 주문 품목입니다.",
                    self._scalar(connection, """
                        SELECT COUNT(*) FROM order_items
                        WHERE product_id IS NULL
                           OR COALESCE(mapping_status, '') NOT IN ('매핑완료','완료','MAPPED')
                    """),
                    "상품매핑", 1,
                ),
                WorkTask(
                    "purchase_waiting", "발주 대기",
                    "검수 후 아직 발주되지 않은 주문입니다.",
                    self._scalar(connection, """
                        SELECT COUNT(*) FROM orders
                        WHERE COALESCE(purchase_status, '') IN ('', '발주대기', '대기', '미발주')
                          AND COALESCE(order_status, '') NOT IN ('취소','주문취소')
                    """),
                    "발주관리", 2,
                ),
                WorkTask(
                    "shipment_waiting", "송장 미등록",
                    "발주되었지만 송장이 등록되지 않은 주문입니다.",
                    self._scalar(connection, """
                        SELECT COUNT(DISTINCT po.order_id)
                        FROM purchase_orders po
                        LEFT JOIN shipments s ON s.order_id = po.order_id
                        WHERE s.id IS NULL
                          AND COALESCE(po.purchase_status, '') NOT IN ('취소','발주취소')
                    """),
                    "송장관리", 3,
                ),
                WorkTask(
                    "supplier_missing", "공급처 없는 상품",
                    "기본 공급처 또는 공급처 연결이 없는 상품입니다.",
                    self._scalar(connection, """
                        SELECT COUNT(*) FROM products p
                        WHERE COALESCE(p.is_active, 1)=1
                          AND p.supplier_id IS NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM product_suppliers ps
                              WHERE ps.product_id=p.id AND COALESCE(ps.is_active,1)=1
                          )
                    """),
                    "상품관리", 4,
                ),
                WorkTask(
                    "purchase_price_missing", "매입가 미입력 상품",
                    "매입가가 비어 있거나 0원인 상품입니다.",
                    self._scalar(connection, """
                        SELECT COUNT(*) FROM products
                        WHERE COALESCE(is_active,1)=1 AND COALESCE(purchase_price,0)<=0
                    """),
                    "상품관리", 5,
                ),
                WorkTask(
                    "incomplete_products", "미완성 상품",
                    "상품명·옵션·발주차수 중 필요한 정보가 부족한 상품입니다.",
                    self._scalar(connection, """
                        SELECT COUNT(*) FROM products
                        WHERE COALESCE(is_active,1)=1 AND (
                            TRIM(COALESCE(product_name,''))=''
                            OR TRIM(COALESCE(option_name,''))=''
                            OR TRIM(COALESCE(purchase_round,''))=''
                        )
                    """),
                    "상품관리", 6,
                ),
            ]
        return tasks

    @staticmethod
    def _scalar(connection: Any, sql: str) -> int:
        try:
            row = connection.execute(sql).fetchone()
            return int(row[0] or 0) if row else 0
        except Exception:
            return 0
