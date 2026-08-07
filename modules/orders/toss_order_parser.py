from __future__ import annotations

from typing import Any

import pandas as pd

from modules.orders.base_order_parser import BaseOrderExcelParser


class TossOrderExcelParser(BaseOrderExcelParser):
    """토스쇼핑 주문배송관리 Excel을 ERP 공통 주문 형식으로 변환합니다."""

    platform_name = "Toss"
    source_headers = (
        "주문번호", "주문상품번호", "주문상태", "발송기한", "배송속성",
        "받은 혜택", "물류사", "택배사", "송장번호", "상품명", "옵션명",
        "주문건수", "상품ID", "상품 관리 코드", "옵션 ID", "옵션 관리 코드",
        "구매자명", "구매자 연락처", "수령인명", "수령인 연락처", "우편번호",
        "배송지", "주문요청사항", "주문일시", "구매확정일", "희망배송일",
        "발송처리일시", "배송완료일시", "주문금액", "배송비 묶음 번호",
        "배송비 합계",
    )
    required_columns = set(source_headers)
    helper_values = tuple(
        "수정 가능" if index in {2, 7, 8} else "수정 불가"
        for index in range(len(source_headers))
    )
    instruction_markers = (
        "엑셀 일괄발송",
        "입력 및 수정 가능 항목",
    )

    def find_header_row(self, dataframe: pd.DataFrame) -> int | None:
        """Accept only the verified instruction/header/helper layout."""
        expected_headers = list(self.source_headers)
        expected_helper = list(self.helper_values)
        max_rows = min(len(dataframe), self.header_search_rows)
        for row_index in range(1, max_rows - 1):
            headers = self._trimmed_row(dataframe.iloc[row_index].tolist())
            if headers != expected_headers:
                continue
            helper = self._trimmed_row(dataframe.iloc[row_index + 1].tolist())
            if helper != expected_helper:
                continue
            instruction = [
                self.clean_text(value)
                for value in dataframe.iloc[row_index - 1].tolist()
            ]
            if not all(
                any(marker in value for value in instruction)
                for marker in self.instruction_markers
            ):
                continue
            return row_index
        return None

    def prepare_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        header_row = self.find_header_row(dataframe)
        if header_row is None:
            raise ValueError("토스쇼핑 주문배송관리 Excel 형식을 확인할 수 없습니다.")
        columns = self._make_unique_columns(dataframe.iloc[header_row].tolist())
        prepared = dataframe.iloc[header_row + 2 :].copy()
        prepared.columns = columns
        return prepared.dropna(how="all").reset_index(drop=True)

    def parse(
        self,
        dataframe: pd.DataFrame,
        source_file: str,
    ) -> list[dict[str, Any]]:
        working = self.prepare_dataframe(dataframe)
        self.validate_columns(working)
        working["주문번호"] = working["주문번호"].apply(self.clean_identifier)
        working["주문상품번호"] = working["주문상품번호"].apply(
            self.clean_identifier
        )
        working = working[
            (working["주문번호"] != "")
            & (working["주문상품번호"] != "")
        ].copy()
        if working.empty:
            raise ValueError("토스쇼핑 주문배송관리 Excel에서 주문을 찾지 못했습니다.")

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
                quantity = self.to_positive_int(row.get("주문건수"), default=1)
                line_total = self.to_non_negative_int(
                    row.get("주문금액"),
                    default=0,
                )
                unit_price = line_total // quantity if quantity > 0 else line_total
                seller_product_code = (
                    self.clean_identifier(row.get("옵션 관리 코드"))
                    or self.clean_identifier(row.get("상품 관리 코드"))
                )
                items.append(
                    {
                        "platform_product_name": product_name,
                        "option_name": self.clean_text(row.get("옵션명")),
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": line_total,
                        "purchase_round": "",
                        "mapping_status": "미매핑",
                        "channel_metadata": {
                            "platform": self.platform_name,
                            "original_platform_name": "토스쇼핑",
                            "channel_order_number": self.clean_identifier(
                                row.get("주문번호")
                            ),
                            "channel_item_number": self.clean_identifier(
                                row.get("주문상품번호")
                            ),
                            "bundle_shipment_number": self.clean_identifier(
                                row.get("배송비 묶음 번호")
                            ),
                            "option_id": self.clean_identifier(row.get("옵션 ID")),
                            "seller_product_code": seller_product_code,
                            "vendor_item_id": "",
                            "shipment_box_id": "",
                            "external_order_id": "",
                            "delivery_method": self.clean_text(row.get("배송속성")),
                            "sales_channel": "토스쇼핑",
                            "product_identifier": self.clean_identifier(
                                row.get("상품ID")
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
                    "ordered_at": self.clean_datetime(first_row.get("주문일시")),
                    "receiver_name": self.clean_text(first_row.get("수령인명")),
                    "receiver_phone": self.clean_text(
                        first_row.get("수령인 연락처")
                    ),
                    "postal_code": self.clean_identifier(first_row.get("우편번호")),
                    "address": self.clean_text(first_row.get("배송지")),
                    "detail_address": "",
                    "delivery_message": self.clean_text(
                        first_row.get("주문요청사항")
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
            raise ValueError("토스쇼핑 주문배송관리 Excel에서 등록 가능한 주문이 없습니다.")
        return orders

    @classmethod
    def _trimmed_row(cls, values: list[Any]) -> list[str]:
        normalized = [cls._normalize_column_name(value) for value in values]
        while normalized and not normalized[-1]:
            normalized.pop()
        return normalized
