from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from modules.orders.order_repository import OrderRepository
from modules.settings.settings_service import SettingsService

from .coupang_api import CoupangAPIClient


KST = timezone(timedelta(hours=9))


class CoupangOrderService:
    """
    쿠팡 발주서를 ERP 주문 구조로 변환하고 저장합니다.

    중요한 설계:
    - 쿠팡 shipmentBoxId를 ERP 주문번호로 사용합니다.
      쿠팡은 한 orderId가 여러 배송묶음으로 나뉠 수 있기 때문입니다.
    - 원본 orderId, shipmentBoxId, vendorItemId는 별도 연결 테이블에
      보관하여 추후 송장 API에 그대로 사용할 수 있게 합니다.
    """

    PLATFORM = "쿠팡"
    DEFAULT_STATUSES = ("ACCEPT", "INSTRUCT")

    def __init__(
        self,
        *,
        settings_service: SettingsService | None = None,
        repository: OrderRepository | None = None,
    ) -> None:
        self.settings_service = settings_service or SettingsService()
        self.repository = repository or OrderRepository()
        self.database_path = Path(self.repository.database_path)
        self._ensure_schema()

    def collect_recent_orders(
        self,
        *,
        lookback_minutes: int = 1440,
        statuses: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        settings = self.settings_service.get_coupang_settings()

        client = CoupangAPIClient(
            vendor_id=settings["vendor_id"],
            access_key=settings["access_key"],
            secret_key=settings["secret_key"],
        )

        safe_lookback = max(1, min(int(lookback_minutes), 1439))
        now = datetime.now(KST)
        start = now - timedelta(minutes=safe_lookback)

        created_at_from = self._format_api_datetime(start)
        created_at_to = self._format_api_datetime(now)

        requested_statuses = tuple(
            str(value or "").strip().upper()
            for value in (statuses or self.DEFAULT_STATUSES)
            if str(value or "").strip()
        )

        raw_sheets: list[dict[str, Any]] = []
        api_counts: dict[str, int] = {}

        for status in requested_statuses:
            sheets = client.get_order_sheets(
                created_at_from=created_at_from,
                created_at_to=created_at_to,
                status=status,
            )
            api_counts[status] = len(sheets)
            raw_sheets.extend(sheets)

        unique_sheets: dict[str, dict[str, Any]] = {}
        for sheet in raw_sheets:
            shipment_box_id = self._text(
                sheet.get("shipmentBoxId")
            )
            order_id = self._text(sheet.get("orderId"))
            key = shipment_box_id or order_id
            if key:
                unique_sheets[key] = sheet

        created_count = 0
        duplicate_count = 0
        failed_count = 0
        created_order_ids: list[int] = []
        mapping_summary = {
            "target_count": 0,
            "mapped_count": 0,
            "rule_mapped_count": 0,
            "exact_mapped_count": 0,
            "smart_mapped_count": 0,
            "unmatched_count": 0,
            "ambiguous_count": 0,
        }
        errors: list[dict[str, Any]] = []

        for sheet in unique_sheets.values():
            try:
                order_data, item_links = self._convert_sheet(sheet)
                result = self.repository.create_order(
                    **order_data,
                    skip_duplicate=True,
                )

                if result["duplicate"]:
                    duplicate_count += 1
                    self._update_existing_link_metadata(
                        order_number=order_data["order_number"],
                        sheet=sheet,
                    )
                    continue

                erp_order_id = int(result["order_id"])
                created_count += 1
                created_order_ids.append(erp_order_id)

                self._save_links(
                    erp_order_id=erp_order_id,
                    sheet=sheet,
                    item_links=item_links,
                )

                mapping = self.repository.auto_map_order_items(
                    order_id=erp_order_id
                )
                for key in mapping_summary:
                    mapping_summary[key] += int(
                        mapping.get(key, 0) or 0
                    )

            except Exception as error:
                failed_count += 1
                errors.append(
                    {
                        "shipment_box_id": self._text(
                            sheet.get("shipmentBoxId")
                        ),
                        "order_id": self._text(
                            sheet.get("orderId")
                        ),
                        "error": str(error),
                    }
                )

        checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_message = (
            f"쿠팡 주문수집 완료: 신규 {created_count}건, "
            f"중복 {duplicate_count}건, 실패 {failed_count}건"
        )
        self.settings_service.save(
            {
                "coupang.last_order_sync_at": checked_at,
                "coupang.last_order_sync_status": (
                    "성공" if failed_count == 0 else "일부실패"
                ),
                "coupang.last_order_sync_message": summary_message,
                "coupang.last_order_sync_created": str(created_count),
                "coupang.last_order_sync_duplicate": str(duplicate_count),
                "coupang.last_order_sync_failed": str(failed_count),
            }
        )

        return {
            "created_at_from": created_at_from,
            "created_at_to": created_at_to,
            "requested_statuses": list(requested_statuses),
            "api_counts": api_counts,
            "received_count": len(unique_sheets),
            "created_count": created_count,
            "duplicate_count": duplicate_count,
            "failed_count": failed_count,
            "created_order_ids": created_order_ids,
            "errors": errors,
            **{
                f"mapping_{key}": value
                for key, value in mapping_summary.items()
            },
            "checked_at": checked_at,
            "message": summary_message,
        }

    def get_last_sync_summary(self) -> dict[str, str]:
        values = self.settings_service.get_all()
        return {
            "checked_at": str(
                values.get("coupang.last_order_sync_at", "") or ""
            ),
            "status": str(
                values.get("coupang.last_order_sync_status", "") or ""
            ),
            "message": str(
                values.get("coupang.last_order_sync_message", "") or ""
            ),
            "created": str(
                values.get("coupang.last_order_sync_created", "0") or "0"
            ),
            "duplicate": str(
                values.get("coupang.last_order_sync_duplicate", "0") or "0"
            ),
            "failed": str(
                values.get("coupang.last_order_sync_failed", "0") or "0"
            ),
        }

    def _convert_sheet(
        self,
        sheet: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        shipment_box_id = self._required_text(
            sheet.get("shipmentBoxId"),
            "shipmentBoxId",
        )
        coupang_order_id = self._required_text(
            sheet.get("orderId"),
            "orderId",
        )

        receiver = (
            sheet.get("receiver")
            if isinstance(sheet.get("receiver"), dict)
            else {}
        )
        orderer = (
            sheet.get("orderer")
            if isinstance(sheet.get("orderer"), dict)
            else {}
        )

        raw_items = sheet.get("orderItems")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("쿠팡 주문상품 정보가 없습니다.")

        items: list[dict[str, Any]] = []
        item_links: list[dict[str, Any]] = []

        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue

            shipping_count = self._safe_int(
                raw_item.get("shippingCount"),
                default=0,
            )
            cancel_count = self._safe_int(
                raw_item.get("cancelCount"),
                default=0,
            )
            hold_count = self._safe_int(
                raw_item.get("holdCountForCancel"),
                default=0,
            )
            available_quantity = max(
                0,
                shipping_count - cancel_count - hold_count,
            )

            if available_quantity <= 0:
                continue

            product_name = (
                self._text(raw_item.get("sellerProductName"))
                or self._text(raw_item.get("vendorItemName"))
            )
            option_name = (
                self._text(raw_item.get("sellerProductItemName"))
                or self._text(raw_item.get("firstSellerProductItemName"))
            )
            if not product_name:
                raise ValueError("쿠팡 판매상품명이 비어 있습니다.")

            unit_price = self._money_units(
                raw_item.get("salesPrice")
            )
            order_price = self._money_units(
                raw_item.get("orderPrice")
            )
            if order_price <= 0:
                order_price = unit_price * available_quantity

            items.append(
                {
                    "platform_product_name": product_name,
                    "option_name": option_name,
                    "quantity": available_quantity,
                    "unit_price": unit_price,
                    "total_price": order_price,
                    "mapping_status": "미매핑",
                }
            )
            item_links.append(
                {
                    "vendor_item_id": self._text(
                        raw_item.get("vendorItemId")
                    ),
                    "seller_product_id": self._text(
                        raw_item.get("sellerProductId")
                    ),
                    "external_vendor_sku": self._text(
                        raw_item.get("externalVendorSkuCode")
                    ),
                    "original_shipping_count": shipping_count,
                    "cancel_count": cancel_count,
                    "hold_count_for_cancel": hold_count,
                    "raw_status": self._text(sheet.get("status")),
                }
            )

        if not items:
            raise ValueError(
                "취소·환불대기 수량을 제외한 발주 가능 상품이 없습니다."
            )

        total_amount = sum(
            int(item["total_price"])
            for item in items
        )

        phone = (
            self._text(receiver.get("safeNumber"))
            or self._text(receiver.get("receiverNumber"))
            or self._text(orderer.get("safeNumber"))
        )

        order_data = {
            "platform": self.PLATFORM,
            "order_number": shipment_box_id,
            "ordered_at": self._text(sheet.get("orderedAt")),
            "receiver_name": self._text(receiver.get("name")),
            "receiver_phone": phone,
            "postal_code": self._text(receiver.get("postCode")),
            "address": self._text(receiver.get("addr1")),
            "detail_address": self._text(receiver.get("addr2")),
            "delivery_message": self._text(
                sheet.get("parcelPrintMessage")
            ),
            "order_status": "주문접수",
            "payment_status": "결제완료",
            "mapping_status": "미매핑",
            "purchase_status": "발주대기",
            "shipment_status": "송장대기",
            "total_amount": total_amount,
            "source_file": (
                f"Coupang Open API / orderId={coupang_order_id}"
            ),
            "items": items,
        }
        return order_data, item_links

    def _save_links(
        self,
        *,
        erp_order_id: int,
        sheet: dict[str, Any],
        item_links: list[dict[str, Any]],
    ) -> None:
        with self._connect() as connection:
            order_item_rows = connection.execute(
                """
                SELECT id
                FROM order_items
                WHERE order_id = ?
                ORDER BY id ASC
                """,
                (erp_order_id,),
            ).fetchall()

            if len(order_item_rows) != len(item_links):
                raise RuntimeError(
                    "ERP 주문상품 수와 쿠팡 상품 연결정보 수가 일치하지 않습니다."
                )

            connection.execute(
                """
                INSERT INTO coupang_order_links (
                    erp_order_id,
                    coupang_order_id,
                    shipment_box_id,
                    raw_status,
                    last_seen_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(shipment_box_id)
                DO UPDATE SET
                    erp_order_id = excluded.erp_order_id,
                    coupang_order_id = excluded.coupang_order_id,
                    raw_status = excluded.raw_status,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (
                    erp_order_id,
                    self._text(sheet.get("orderId")),
                    self._text(sheet.get("shipmentBoxId")),
                    self._text(sheet.get("status")),
                ),
            )

            for row, link in zip(order_item_rows, item_links):
                connection.execute(
                    """
                    INSERT INTO coupang_order_item_links (
                        erp_order_item_id,
                        erp_order_id,
                        shipment_box_id,
                        vendor_item_id,
                        seller_product_id,
                        external_vendor_sku,
                        original_shipping_count,
                        cancel_count,
                        hold_count_for_cancel,
                        raw_status,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(erp_order_item_id)
                    DO UPDATE SET
                        shipment_box_id = excluded.shipment_box_id,
                        vendor_item_id = excluded.vendor_item_id,
                        seller_product_id = excluded.seller_product_id,
                        external_vendor_sku = excluded.external_vendor_sku,
                        original_shipping_count = excluded.original_shipping_count,
                        cancel_count = excluded.cancel_count,
                        hold_count_for_cancel = excluded.hold_count_for_cancel,
                        raw_status = excluded.raw_status,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        int(row["id"]),
                        erp_order_id,
                        self._text(sheet.get("shipmentBoxId")),
                        link["vendor_item_id"],
                        link["seller_product_id"],
                        link["external_vendor_sku"],
                        link["original_shipping_count"],
                        link["cancel_count"],
                        link["hold_count_for_cancel"],
                        link["raw_status"],
                    ),
                )
            connection.commit()

    def _update_existing_link_metadata(
        self,
        *,
        order_number: str,
        sheet: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM orders
                WHERE platform = ?
                  AND order_number = ?
                """,
                (self.PLATFORM, order_number),
            ).fetchone()
            if row is None:
                return

            connection.execute(
                """
                INSERT INTO coupang_order_links (
                    erp_order_id,
                    coupang_order_id,
                    shipment_box_id,
                    raw_status,
                    last_seen_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(shipment_box_id)
                DO UPDATE SET
                    raw_status = excluded.raw_status,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (
                    int(row["id"]),
                    self._text(sheet.get("orderId")),
                    self._text(sheet.get("shipmentBoxId")),
                    self._text(sheet.get("status")),
                ),
            )
            connection.commit()

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS coupang_order_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    erp_order_id INTEGER NOT NULL,
                    coupang_order_id TEXT NOT NULL,
                    shipment_box_id TEXT NOT NULL UNIQUE,
                    raw_status TEXT NOT NULL DEFAULT '',
                    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(erp_order_id)
                        REFERENCES orders(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS
                    idx_coupang_order_links_order_id
                ON coupang_order_links(coupang_order_id);

                CREATE TABLE IF NOT EXISTS coupang_order_item_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    erp_order_item_id INTEGER NOT NULL UNIQUE,
                    erp_order_id INTEGER NOT NULL,
                    shipment_box_id TEXT NOT NULL,
                    vendor_item_id TEXT NOT NULL DEFAULT '',
                    seller_product_id TEXT NOT NULL DEFAULT '',
                    external_vendor_sku TEXT NOT NULL DEFAULT '',
                    original_shipping_count INTEGER NOT NULL DEFAULT 0,
                    cancel_count INTEGER NOT NULL DEFAULT 0,
                    hold_count_for_cancel INTEGER NOT NULL DEFAULT 0,
                    raw_status TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(erp_order_item_id)
                        REFERENCES order_items(id) ON DELETE CASCADE,
                    FOREIGN KEY(erp_order_id)
                        REFERENCES orders(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS
                    idx_coupang_item_links_shipment
                ON coupang_order_item_links(shipment_box_id);
                """
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _format_api_datetime(value: datetime) -> str:
        return value.astimezone(KST).isoformat(
            timespec="minutes"
        )

    @staticmethod
    def _money_units(value: Any) -> int:
        if isinstance(value, dict):
            return CoupangOrderService._safe_int(
                value.get("units"),
                default=0,
            )
        return CoupangOrderService._safe_int(
            value,
            default=0,
        )

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _required_text(
        cls,
        value: Any,
        field_name: str,
    ) -> str:
        text = cls._text(value)
        if not text:
            raise ValueError(
                f"쿠팡 응답의 {field_name} 값이 비어 있습니다."
            )
        return text

    @staticmethod
    def _safe_int(
        value: Any,
        *,
        default: int = 0,
    ) -> int:
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return default
