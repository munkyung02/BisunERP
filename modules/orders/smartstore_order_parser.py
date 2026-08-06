from __future__ import annotations

from typing import Any

import pandas as pd

from modules.orders.base_order_parser import BaseOrderExcelParser


class SmartStoreOrderExcelParser(BaseOrderExcelParser):
    """네이버 스마트스토어 전체주문 발주·발송관리 엑셀 파서입니다."""

    platform_name = "스마트스토어"
    required_columns = {
        "상품주문번호", "주문번호", "판매채널", "결제일", "상품명",
        "옵션정보", "수량", "최종 상품별 총 주문금액", "수취인명",
        "수취인연락처1", "통합배송지",
    }

    def parse(self, dataframe: pd.DataFrame, source_file: str) -> list[dict[str, Any]]:
        working = self.prepare_dataframe(dataframe)
        self.validate_columns(working)
        working["주문번호"] = working["주문번호"].apply(self.clean_identifier)
        working["상품주문번호"] = working["상품주문번호"].apply(self.clean_identifier)
        working = working[working["주문번호"] != ""].copy()

        if working.empty:
            raise ValueError("스마트스토어 엑셀에서 주문번호를 찾지 못했습니다.")

        orders: list[dict[str, Any]] = []
        for order_number, group in working.groupby("주문번호", sort=False, dropna=False):
            first_row = group.iloc[0]
            items: list[dict[str, Any]] = []
            total_amount = 0

            for _, row in group.iterrows():
                if self._is_cancelled_or_returned(row):
                    continue
                product_name = self.clean_text(row.get("상품명"))
                if not product_name:
                    continue
                quantity = self.to_positive_int(row.get("수량"), default=1)
                line_total = self.to_non_negative_int(
                    row.get("최종 상품별 총 주문금액"), default=0
                )
                if line_total <= 0:
                    product_price = self.to_non_negative_int(row.get("상품가격"), 0)
                    option_price = self.to_non_negative_int(row.get("옵션가격"), 0)
                    line_total = (product_price + option_price) * quantity
                unit_price = line_total // quantity if quantity > 0 else line_total
                items.append({
                    "platform_product_name": product_name,
                    "option_name": self.clean_text(row.get("옵션정보")),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": line_total,
                    "purchase_round": "",
                    "mapping_status": "미매핑",
                    "channel_metadata": {
                        "platform": self.platform_name,
                        "original_platform_name": self.clean_text(row.get("판매채널")),
                        "channel_order_number": self.clean_identifier(row.get("주문번호")),
                        "channel_item_number": self.clean_identifier(
                            row.get("상품주문번호")
                        ),
                        "bundle_shipment_number": "",
                        "option_id": (
                            self.clean_identifier(row.get("옵션ID"))
                            or self.clean_identifier(row.get("옵션번호"))
                        ),
                        "seller_product_code": "",
                        "vendor_item_id": "",
                        "shipment_box_id": "",
                        "external_order_id": "",
                        "delivery_method": (
                            self.clean_text(row.get("배송방법"))
                            or self.clean_text(row.get("배송방식"))
                            or self.clean_text(row.get("배송유형"))
                        ),
                        "sales_channel": self.clean_text(row.get("판매채널")),
                        "product_identifier": (
                            self.clean_identifier(row.get("상품번호"))
                            or self.clean_identifier(row.get("상품ID"))
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

            receiver_phone = (
                self.clean_text(first_row.get("수취인연락처1"))
                or self.clean_text(first_row.get("수취인연락처2"))
            )
            orders.append({
                "platform": self.platform_name,
                "order_number": str(order_number),
                "ordered_at": self.clean_datetime(first_row.get("결제일")),
                "receiver_name": self.clean_text(first_row.get("수취인명")),
                "receiver_phone": receiver_phone,
                "postal_code": "",
                "address": self.clean_text(first_row.get("통합배송지")),
                "detail_address": "",
                "delivery_message": "",
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
            raise ValueError("스마트스토어 엑셀에서 등록 가능한 주문을 찾지 못했습니다.")
        return orders

    @classmethod
    def _is_cancelled_or_returned(cls, row: pd.Series) -> bool:
        status_text = " ".join([
            cls.clean_text(row.get("주문상태")),
            cls.clean_text(row.get("주문세부상태")),
        ])
        excluded_keywords = {"취소완료", "반품완료", "구매확정 후 취소"}
        return any(keyword in status_text for keyword in excluded_keywords)
