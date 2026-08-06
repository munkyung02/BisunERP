from __future__ import annotations

from typing import Any

import pandas as pd

from modules.orders.base_order_parser import BaseOrderExcelParser


class CoupangOrderExcelParser(BaseOrderExcelParser):
    """쿠팡 주문 엑셀을 ERP 공통 주문 형식으로 변환합니다."""

    platform_name = "쿠팡"
    required_columns = {
        "주문번호", "주문일", "등록상품명", "등록옵션명", "결제액",
        "구매수(수량)", "수취인이름", "수취인전화번호", "우편번호",
        "수취인 주소", "배송메세지",
    }

    def parse(self, dataframe: pd.DataFrame, source_file: str) -> list[dict[str, Any]]:
        working = self.prepare_dataframe(dataframe)
        self.validate_columns(working)
        working["주문번호"] = working["주문번호"].apply(self.clean_identifier)
        working = working[working["주문번호"] != ""].copy()
        if working.empty:
            raise ValueError("저장할 주문이 없습니다.")

        orders: list[dict[str, Any]] = []
        for order_number, group in working.groupby("주문번호", sort=False, dropna=False):
            first_row = group.iloc[0]
            items: list[dict[str, Any]] = []
            total_amount = 0

            for _, row in group.iterrows():
                product_name = self.clean_text(row.get("등록상품명"))
                if not product_name:
                    continue
                quantity = self.to_positive_int(row.get("구매수(수량)"), default=1)
                line_total = self.to_non_negative_int(row.get("결제액"), default=0)
                unit_price = line_total // quantity if quantity > 0 else line_total
                items.append({
                    "platform_product_name": product_name,
                    "option_name": self.clean_text(row.get("등록옵션명")),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": line_total,
                    "purchase_round": "",
                    "mapping_status": "미매핑",
                    "channel_metadata": {
                        "platform": self.platform_name,
                        "original_platform_name": (
                            self.clean_text(row.get("판매채널")) or self.platform_name
                        ),
                        "channel_order_number": self.clean_identifier(row.get("주문번호")),
                        "channel_item_number": "",
                        "bundle_shipment_number": self.clean_identifier(
                            row.get("묶음배송번호")
                        ),
                        "option_id": self.clean_identifier(row.get("옵션ID")),
                        "seller_product_code": (
                            self.clean_identifier(row.get("판매자상품코드"))
                            or self.clean_identifier(row.get("업체상품코드"))
                        ),
                        "vendor_item_id": self.clean_identifier(row.get("vendorItemId")),
                        "shipment_box_id": self.clean_identifier(row.get("shipmentBoxId")),
                        "external_order_id": self.clean_identifier(row.get("orderId")),
                        "delivery_method": "",
                        "sales_channel": self.clean_text(row.get("판매채널")),
                        "product_identifier": self.clean_identifier(
                            row.get("노출상품ID")
                        ),
                        "raw_source_row": {
                            str(column): self.clean_text(value)
                            for column, value in row.to_dict().items()
                        },
                        "source_file": source_file,
                    },
                })
                total_amount += line_total

            if not items:
                continue

            orders.append({
                "platform": self.platform_name,
                "order_number": str(order_number),
                "ordered_at": self.clean_datetime(first_row.get("주문일")),
                "receiver_name": self.clean_text(first_row.get("수취인이름")),
                "receiver_phone": self.clean_text(first_row.get("수취인전화번호")),
                "postal_code": self.clean_identifier(first_row.get("우편번호")),
                "address": self.clean_text(first_row.get("수취인 주소")),
                "detail_address": "",
                "delivery_message": self.clean_text(first_row.get("배송메세지")),
                "order_status": "주문접수",
                "payment_status": "결제완료",
                "mapping_status": "미매핑",
                "purchase_status": "발주대기",
                "shipment_status": "송장대기",
                "total_amount": total_amount,
                "source_file": source_file,
                "items": items,
            })

        if not orders:
            raise ValueError("엑셀에서 변환할 수 있는 주문이 없습니다.")
        return orders
