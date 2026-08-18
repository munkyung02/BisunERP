from __future__ import annotations

from typing import Any

import pandas as pd

from modules.orders.base_order_parser import BaseOrderExcelParser


class LotteOnOrderExcelParser(BaseOrderExcelParser):
    """롯데ON 배송관리 Excel을 ERP 공통 주문 형식으로 변환합니다."""

    platform_name = "LotteOn"
    source_headers = (
        "주문번호", "주문순번", "주문상태", "발송예정일", "도착예정일",
        "발송지연여부", "배송희망일/배송예약일", "발송약속일", "합배송그룹번호",
        "합배송가능여부", "배송상품유형", "배송예약구분", "판매유형", "상품명",
        "상품번호", "옵션명", "단품번호", "판매단가", "수량", "입력형추가옵션",
        "배송메세지", "판매자 내부 상품번호", "판매자 내부 단품번호", "선물여부",
        "선물포장요청여부", "명절상품여부", "해외배송여부", "개인통관번호",
        "배송수단", "배송사", "송장번호", "운송장규칙 위배사유", "송장개수",
        "주문접수일시", "출고지시일시", "상품준비일시", "발송완료일시",
        "배송완료일시", "기배송", "우편번호", "우편번호순번", "수취인 배송지",
        "수취인명", "수취인 휴대폰번호", "주문자명", "주문자 휴대폰번호",
        "주문자ID", "판매가", "롯데온부담 할인금액", "판매자부담 할인금액",
        "판매자부담 지원할인 프로그램 할인금액", "상품별 총 할인금액",
        "실 결제금액", "배송비", "도서산간 추가여부", "제주지역 추가여부",
        "하위거래처",
    )
    required_columns = set(source_headers)

    def find_header_row(self, dataframe: pd.DataFrame) -> int | None:
        """Accept the verified 57- and 58-column 배송관리 header sequences."""
        legacy_headers = list(self.source_headers)
        extended_headers = list(legacy_headers)
        customs_index = extended_headers.index("개인통관번호") + 1
        extended_headers.insert(customs_index, "해외배송인증번호")
        accepted_headers = (legacy_headers, extended_headers)
        max_rows = min(len(dataframe), self.header_search_rows)
        for row_index in range(max_rows):
            values = [
                self._normalize_column_name(value)
                for value in dataframe.iloc[row_index].tolist()
            ]
            while values and not values[-1]:
                values.pop()
            if values in accepted_headers:
                return row_index
        return None

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
            raise ValueError("롯데ON 배송관리 엑셀에서 주문번호를 찾지 못했습니다.")

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
                line_total = self.to_non_negative_int(
                    row.get("실 결제금액"),
                    default=0,
                )
                unit_price = line_total // quantity if quantity > 0 else line_total
                option_name = self._combine_option(
                    row.get("옵션명"),
                    row.get("입력형추가옵션"),
                )
                seller_product_code = (
                    self.clean_identifier(row.get("판매자 내부 단품번호"))
                    or self.clean_identifier(row.get("판매자 내부 상품번호"))
                )
                sales_channel = (
                    self.clean_text(row.get("하위거래처")) or "롯데ON"
                )

                items.append(
                    {
                        "platform_product_name": product_name,
                        "option_name": option_name,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": line_total,
                        "purchase_round": "",
                        "mapping_status": "미매핑",
                        "channel_metadata": {
                            "platform": self.platform_name,
                            "original_platform_name": "롯데ON",
                            "channel_order_number": self.clean_identifier(
                                row.get("주문번호")
                            ),
                            "channel_item_number": self.clean_identifier(
                                row.get("주문순번")
                            ),
                            "bundle_shipment_number": self.clean_identifier(
                                row.get("합배송그룹번호")
                            ),
                            "option_id": self.clean_identifier(row.get("단품번호")),
                            "seller_product_code": seller_product_code,
                            "vendor_item_id": "",
                            "shipment_box_id": "",
                            "external_order_id": "",
                            "delivery_method": self.clean_text(row.get("배송수단")),
                            "sales_channel": sales_channel,
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

            orders.append(
                {
                    "platform": self.platform_name,
                    "order_number": str(order_number),
                    "ordered_at": self.clean_datetime(
                        first_row.get("주문접수일시")
                    ),
                    "receiver_name": self.clean_text(first_row.get("수취인명")),
                    "receiver_phone": self.clean_text(
                        first_row.get("수취인 휴대폰번호")
                    ),
                    "postal_code": self.clean_identifier(first_row.get("우편번호")),
                    "address": self.clean_text(first_row.get("수취인 배송지")),
                    "detail_address": "",
                    "delivery_message": self.clean_text(
                        first_row.get("배송메세지")
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
            raise ValueError("롯데ON 배송관리 엑셀에서 등록 가능한 주문을 찾지 못했습니다.")
        return orders

    @classmethod
    def _combine_option(cls, option: Any, additional_option: Any) -> str:
        values = [cls.clean_text(option), cls.clean_text(additional_option)]
        return " / ".join(value for value in values if value)
