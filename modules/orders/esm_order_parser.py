from __future__ import annotations

from typing import Any

import pandas as pd

from modules.orders.base_order_parser import BaseOrderExcelParser


class ESMOrderExcelParser(BaseOrderExcelParser):
    """ESM Plus 발송관리 엑셀의 확인된 Gmarket 주문을 변환합니다."""

    platform_name = "ESM"
    normalized_platform = "Gmarket"
    required_columns = {
        "판매아이디",
        "주문번호",
        "주문상태",
        "상품번호",
        "상품명",
        "수량",
        "수령인명",
        "주소",
        "배송번호",
        "장바구니번호(결제번호)",
    }

    def parse(
        self,
        dataframe: pd.DataFrame,
        source_file: str,
    ) -> list[dict[str, Any]]:
        working = self.prepare_dataframe(dataframe)
        self.validate_columns(working)
        working["주문번호"] = working["주문번호"].apply(self.clean_identifier)
        working = working[working["주문번호"] != ""].copy()
        if working.empty:
            raise ValueError("ESM Plus 발송관리 엑셀에서 주문번호를 찾지 못했습니다.")

        self._validate_sales_accounts(working)

        orders: list[dict[str, Any]] = []
        for order_number, group in working.groupby(
            "주문번호",
            sort=False,
            dropna=False,
        ):
            first_row = group.iloc[0]
            items: list[dict[str, Any]] = []
            total_amount = 0

            for _, row in group.iterrows():
                product_name = self.clean_text(row.get("상품명"))
                if not product_name:
                    continue
                quantity = self.to_positive_int(row.get("수량"), default=1)
                unit_price = self.to_non_negative_int(
                    row.get("판매단가"),
                    default=0,
                )
                line_total = self.to_non_negative_int(
                    row.get("판매금액"),
                    default=unit_price * quantity,
                )
                if line_total <= 0 and unit_price > 0:
                    line_total = unit_price * quantity

                sales_account = self.clean_text(row.get("판매아이디"))
                items.append(
                    {
                        "platform_product_name": product_name,
                        "option_name": self.clean_text(row.get("옵션")),
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": line_total,
                        "purchase_round": "",
                        "mapping_status": "미매핑",
                        "channel_metadata": {
                            "platform": self.normalized_platform,
                            "original_platform_name": sales_account,
                            "channel_order_number": self.clean_identifier(
                                row.get("주문번호")
                            ),
                            "channel_item_number": "",
                            "bundle_shipment_number": self.clean_identifier(
                                row.get("배송번호")
                            ),
                            "option_id": "",
                            "seller_product_code": (
                                self.clean_identifier(row.get("판매자 관리코드"))
                                or self.clean_identifier(
                                    row.get("판매자 상세관리코드")
                                )
                            ),
                            "vendor_item_id": "",
                            "shipment_box_id": "",
                            "external_order_id": self.clean_identifier(
                                row.get("장바구니번호(결제번호)")
                            ),
                            "delivery_method": "",
                            "sales_channel": sales_account,
                            "product_identifier": self.clean_identifier(
                                row.get("상품번호")
                            ),
                            "raw_source_row": {
                                str(column): self.clean_text(value)
                                for column, value in row.to_dict().items()
                            },
                            "source_file": source_file,
                        },
                    }
                )
                total_amount += line_total

            if not items:
                continue

            receiver_phone = (
                self.clean_text(first_row.get("수령인 휴대폰"))
                or self.clean_text(first_row.get("수령인 전화번호"))
            )
            ordered_at = (
                self.clean_datetime(first_row.get("결제일"))
                or self.clean_datetime(first_row.get("주문일(결제확인전)"))
                or self.clean_datetime(first_row.get("주문일"))
            )
            orders.append(
                {
                    "platform": self.normalized_platform,
                    "order_number": str(order_number),
                    "ordered_at": ordered_at,
                    "receiver_name": self.clean_text(first_row.get("수령인명")),
                    "receiver_phone": receiver_phone,
                    "postal_code": self.clean_identifier(first_row.get("우편번호")),
                    "address": self.clean_text(first_row.get("주소")),
                    "detail_address": "",
                    "delivery_message": self.clean_text(
                        first_row.get("배송시 요구사항")
                    ),
                    "order_status": "주문접수",
                    "payment_status": "결제완료",
                    "mapping_status": "미매핑",
                    "purchase_status": "발주대기",
                    "shipment_status": "송장대기",
                    "total_amount": total_amount,
                    "source_file": source_file,
                    "items": items,
                }
            )

        if not orders:
            raise ValueError("ESM Plus 발송관리 엑셀에서 등록 가능한 주문을 찾지 못했습니다.")
        return orders

    def _validate_sales_accounts(self, dataframe: pd.DataFrame) -> None:
        for row_index, row in dataframe.iterrows():
            sales_account = self.clean_text(row.get("판매아이디"))
            if self._is_gmarket_account(sales_account):
                continue
            display_value = sales_account or "(비어 있음)"
            raise ValueError(
                f"ESM 주문서 {int(row_index) + 2}행의 판매아이디를 지원하지 않습니다: "
                f"{display_value}. 현재는 확인된 Gmarket(지마켓) 주문만 지원합니다."
            )

    @staticmethod
    def _is_gmarket_account(value: str) -> bool:
        normalized = "".join(str(value or "").casefold().split())
        return any(
            marker in normalized
            for marker in ("지마켓", "gmarket", "g마켓")
        )
