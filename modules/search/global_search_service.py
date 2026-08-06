from __future__ import annotations

from typing import Any

from modules.orders.order_repository import OrderRepository
from modules.purchases.purchase_repository import PurchaseRepository
from modules.shipments.shipment_repository import ShipmentRepository


class GlobalSearchService:
    """주문·발주·송장을 하나의 검색어로 조회합니다."""

    def __init__(self) -> None:
        self.order_repository = OrderRepository()
        self.purchase_repository = PurchaseRepository()
        self.shipment_repository = ShipmentRepository()

    def search(self, keyword: str) -> dict[str, Any]:
        cleaned = str(keyword or "").strip()
        if len(cleaned) < 2:
            raise ValueError("검색어를 두 글자 이상 입력해주세요.")

        errors: list[str] = []
        orders = self._safe(
            lambda: self.order_repository.get_orders(keyword=cleaned, limit=200),
            "주문 검색", errors,
        )
        purchases = self._safe(
            lambda: self.purchase_repository.get_purchase_orders(keyword=cleaned),
            "발주 검색", errors,
        )
        shipments = self._safe(
            lambda: self.shipment_repository.get_shipments(keyword=cleaned),
            "송장 검색", errors,
        )

        return {
            "keyword": cleaned,
            "orders": [self._order(row) for row in orders],
            "purchases": [self._purchase(row) for row in purchases],
            "shipments": [self._shipment(row) for row in shipments],
            "total_count": len(orders) + len(purchases) + len(shipments),
            "errors": errors,
        }

    @staticmethod
    def _safe(function: Any, label: str, errors: list[str]) -> list[dict[str, Any]]:
        try:
            return list(function() or [])
        except Exception as error:
            errors.append(f"{label}: {error}")
            return []

    @staticmethod
    def _order(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "order_number": row.get("order_number") or "-",
            "receiver_name": row.get("receiver_name") or "-",
            "receiver_phone": row.get("receiver_phone") or "-",
            "product_name": row.get("item_summary") or row.get("product_name") or "-",
            "amount": GlobalSearchService._number(row.get("total_amount")),
            "status": row.get("shipment_status") or row.get("purchase_status") or row.get("order_status") or "-",
        }

    @staticmethod
    def _purchase(row: dict[str, Any]) -> dict[str, Any]:
        product = str(row.get("product_name") or "-")
        option = str(row.get("option_name") or "").strip()
        if option: product = f"{product} / {option}"
        return {
            "order_number": row.get("order_number") or "-",
            "supplier_name": row.get("supplier_name") or "-",
            "receiver_name": row.get("receiver_name") or "-",
            "receiver_phone": row.get("receiver_phone") or "-",
            "product_name": product,
            "quantity": GlobalSearchService._number(row.get("quantity")),
            "status": row.get("purchase_status") or "-",
        }

    @staticmethod
    def _shipment(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "order_number": row.get("order_number") or "-",
            "receiver_name": row.get("receiver_name") or "-",
            "product_name": row.get("product_name") or "-",
            "courier_name": row.get("courier_name") or "-",
            "tracking_number": row.get("tracking_number") or "-",
            "status": row.get("shipment_status") or "-",
        }

    @staticmethod
    def _number(value: Any) -> int:
        try:
            return int(float(str(value or 0).replace(",", "")))
        except (TypeError, ValueError):
            return 0
