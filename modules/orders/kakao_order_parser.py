from __future__ import annotations

from typing import Any

import pandas as pd

from modules.orders.base_order_parser import BaseOrderExcelParser


class KakaoOrderExcelParser(BaseOrderExcelParser):
    """카카오 톡스토어 발주서 Excel을 ERP 공통 주문 형식으로 변환합니다."""

    platform_name = "Kakao"
    source_headers = (
        "결제번호", "배송지/수신자정보 입력일", "주문상태", "주문번호",
        "개인통관고유부호", "채널상품번호", "상품명", "옵션", "수량",
        "배송방법", "택배사코드", "송장번호", "수령인명", "수령인연락처1",
        "하이픈포함 수령인연락처1", "수령인연락처2",
        "하이픈포함 수령인연락처2", "배송지주소", "우편번호", "배송메세지",
        "타입", "발송예정일", "배송지연출고일", "주문일", "상품금액",
        "옵션금액", "판매자할인금액", "판매자쿠폰할인금액", "정산기준금액",
        "기본수수료", "노출추가수수료", "추천리워드수수료", "수수료할인금액",
        "채널", "브랜드", "모델명", "판매자상품번호", "옵션코드",
        "최초배송비번호", "배송비지불방법", "기본배송비 유형",
        "기본배송비 금액", "도서산간 주문 여부", "도서산간 추가 배송비 금액",
        "유입경로", "톡딜여부", "상품유형", "biz판매여부",
    )
    required_columns = set(source_headers)

    def find_header_row(self, dataframe: pd.DataFrame) -> int | None:
        expected = list(self.source_headers)
        max_rows = min(len(dataframe), self.header_search_rows)
        for row_index in range(max_rows):
            headers = [
                self._normalize_column_name(self._decode_text(value))
                for value in dataframe.iloc[row_index].tolist()
            ]
            while headers and not headers[-1]:
                headers.pop()
            if headers == expected:
                return row_index
        return None

    def prepare_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        header_row = self.find_header_row(dataframe)
        if header_row is None:
            raise ValueError("카카오 톡스토어 발주서 형식을 확인할 수 없습니다.")
        decoded = dataframe.apply(lambda column: column.map(self._decode_text))
        columns = self._make_unique_columns(decoded.iloc[header_row].tolist())
        prepared = decoded.iloc[header_row + 1 :].copy()
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
        working = working[working["주문번호"] != ""].copy()
        if working.empty:
            raise ValueError("카카오 톡스토어 발주서에서 주문을 찾지 못했습니다.")

        orders: list[dict[str, Any]] = []
        for order_number, group in working.groupby("주문번호", sort=False):
            first_row = group.iloc[0]
            items: list[dict[str, Any]] = []
            total_amount = 0

            for _, row in group.iterrows():
                product_name = self.clean_text(row.get("상품명"))
                if not product_name:
                    continue
                quantity = self.to_positive_int(row.get("수량"), default=1)
                line_total = self._customer_payment_amount(row)
                total_amount += line_total
                items.append({
                    "platform_product_name": product_name,
                    "option_name": self.clean_text(row.get("옵션")),
                    "quantity": quantity,
                    "unit_price": line_total // quantity,
                    "total_price": line_total,
                    "purchase_round": "",
                    "mapping_status": "미매핑",
                    "channel_metadata": {
                        "platform": self.platform_name,
                        "original_platform_name": "톡스토어",
                        "channel_order_number": self.clean_identifier(
                            row.get("주문번호")
                        ),
                        "channel_item_number": self.clean_identifier(
                            row.get("채널상품번호")
                        ),
                        "bundle_shipment_number": self.clean_identifier(
                            row.get("최초배송비번호")
                        ),
                        "option_id": self.clean_identifier(row.get("옵션코드")),
                        "seller_product_code": self.clean_identifier(
                            row.get("판매자상품번호")
                        ),
                        "vendor_item_id": "",
                        "shipment_box_id": "",
                        "external_order_id": self.clean_identifier(
                            row.get("결제번호")
                        ),
                        "delivery_method": self.clean_text(row.get("배송방법")),
                        "sales_channel": self.clean_text(row.get("채널")) or "톡스토어",
                        "product_identifier": self.clean_identifier(
                            row.get("채널상품번호")
                        ),
                        "raw_source_row": {
                            str(column).strip(): self.clean_text(value)
                            for column, value in row.to_dict().items()
                        },
                        "source_file": source_file,
                    },
                })

            if not items:
                continue
            orders.append({
                "platform": self.platform_name,
                "order_number": str(order_number),
                "ordered_at": self.clean_datetime(first_row.get("주문일")),
                "receiver_name": self.clean_text(first_row.get("수령인명")),
                "receiver_phone": self.clean_text(
                    first_row.get("수령인연락처1")
                ),
                "postal_code": self.clean_identifier(first_row.get("우편번호")),
                "address": self.clean_text(first_row.get("배송지주소")),
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
            raise ValueError("카카오 톡스토어 발주서에서 등록 가능한 주문이 없습니다.")
        return orders

    @classmethod
    def _customer_payment_amount(cls, row: pd.Series) -> int:
        settlement_base = cls.to_non_negative_int(row.get("정산기준금액"), default=0)
        basic_shipping = (
            cls.to_non_negative_int(row.get("기본배송비 금액"), default=0)
            if cls.clean_text(row.get("기본배송비 유형")) == "유료"
            else 0
        )
        remote_status = cls.clean_text(row.get("도서산간 주문 여부"))
        remote_shipping = (
            cls.to_non_negative_int(
                row.get("도서산간 추가 배송비 금액"), default=0
            )
            if "도서산간" in remote_status
            else 0
        )
        return settlement_base + basic_shipping + remote_shipping

    @staticmethod
    def _decode_text(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return value.encode("latin1").decode("cp949")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return value
