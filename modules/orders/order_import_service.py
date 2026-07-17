from pathlib import Path
from typing import Any

import pandas as pd

from modules.orders.order_repository import OrderRepository
from src.excel_reader import read_excel_file
from src.order_parser import parse_coupang_orders


class OrderImportService:
    """쿠팡 주문을 표준화하여 ERP 데이터베이스에 저장합니다."""

    def __init__(
        self,
        repository: OrderRepository | None = None,
    ) -> None:
        self.repository = repository or OrderRepository()

    def import_coupang_file(
        self,
        file_path: str | Path,
    ) -> dict[str, int]:
        """
        쿠팡 원본 주문 엑셀을 읽고 표준 주문으로 변환한 뒤 저장합니다.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"주문 파일을 찾을 수 없습니다: {path}"
            )

        original_orders = read_excel_file(path)
        standard_orders = parse_coupang_orders(original_orders)

        return self.import_standard_orders(
            orders=standard_orders,
            source_file=path.name,
        )

    def import_standard_file(
        self,
        file_path: str | Path,
    ) -> dict[str, int]:
        """
        이미 변환된 쿠팡_표준주문.xlsx 파일을 저장합니다.

        개발 테스트와 기존 출력 파일 재사용에 사용합니다.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"표준 주문 파일을 찾을 수 없습니다: {path}"
            )

        standard_orders = pd.read_excel(
            path,
            dtype={
                "주문번호": str,
                "채널상품ID": str,
                "채널옵션ID": str,
                "연락처": str,
                "우편번호": str,
                "원본고유키": str,
            },
        )

        return self.import_standard_orders(
            orders=standard_orders,
            source_file=path.name,
        )

    def import_standard_orders(
        self,
        orders: pd.DataFrame,
        source_file: str = "",
    ) -> dict[str, int]:
        """표준 주문 DataFrame을 주문번호별로 묶어서 저장합니다."""

        self._validate_columns(orders)

        result = {
            "total_rows": len(orders),
            "total_orders": 0,
            "saved_orders": 0,
            "saved_items": 0,
            "duplicate_orders": 0,
            "failed_orders": 0,
        }

        if orders.empty:
            return result

        prepared_orders = orders.copy()

        prepared_orders["판매채널"] = prepared_orders[
            "판매채널"
        ].apply(self._clean_text)

        prepared_orders["주문번호"] = prepared_orders[
            "주문번호"
        ].apply(self._clean_identifier)

        grouped_orders = prepared_orders.groupby(
            ["판매채널", "주문번호"],
            dropna=False,
            sort=False,
        )

        result["total_orders"] = grouped_orders.ngroups

        for (
            platform,
            order_number,
        ), order_group in grouped_orders:
            try:
                if not platform or not order_number:
                    result["failed_orders"] += 1
                    continue

                if self.repository.exists_order(
                    platform=platform,
                    order_number=order_number,
                ):
                    result["duplicate_orders"] += 1
                    continue

                first_row = order_group.iloc[0]

                total_amount = sum(
                    self._to_integer(value)
                    for value in order_group["결제금액"]
                )

                order_data = {
                    "platform": platform,
                    "order_number": order_number,
                    "ordered_at": "",
                    "receiver_name": self._clean_text(
                        first_row.get("수취인")
                    ),
                    "receiver_phone": self._clean_text(
                        first_row.get("연락처")
                    ),
                    "postal_code": self._clean_identifier(
                        first_row.get("우편번호")
                    ),
                    "address": self._clean_text(
                        first_row.get("주소")
                    ),
                    "detail_address": "",
                    "delivery_message": self._clean_text(
                        first_row.get("배송메모")
                    ),
                    "order_status": "주문접수",
                    "payment_status": "결제완료",
                    "mapping_status": "미매핑",
                    "purchase_status": "발주대기",
                    "shipment_status": "배송대기",
                    "total_amount": total_amount,
                    "source_file": source_file,
                }

                order_id, created = self.repository.save_order(
                    order_data
                )

                if not created:
                    result["duplicate_orders"] += 1
                    continue

                result["saved_orders"] += 1

                for _, item_row in order_group.iterrows():
                    quantity = self._to_integer(
                        item_row.get("주문수량"),
                        default=1,
                    )

                    if quantity < 1:
                        quantity = 1

                    total_price = self._to_integer(
                        item_row.get("결제금액")
                    )

                    unit_price = (
                        total_price // quantity
                        if quantity > 0
                        else total_price
                    )

                    item_data = {
                        "platform_product_name": self._clean_text(
                            item_row.get("채널상품명")
                        ),
                        "option_name": self._clean_text(
                            item_row.get("채널옵션명")
                        ),
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": total_price,
                        "purchase_round": "",
                        "mapping_status": "미매핑",
                    }

                    self.repository.save_order_item(
                        order_id=order_id,
                        item=item_data,
                    )

                    result["saved_items"] += 1

            except Exception as error:
                result["failed_orders"] += 1

                print(
                    "주문 저장 실패:",
                    platform,
                    order_number,
                    error,
                )

        return result

    @staticmethod
    def _validate_columns(orders: pd.DataFrame) -> None:
        required_columns = {
            "판매채널",
            "주문번호",
            "채널상품명",
            "채널옵션명",
            "주문수량",
            "결제금액",
            "수취인",
            "연락처",
            "우편번호",
            "주소",
            "배송메모",
        }

        missing_columns = required_columns.difference(
            orders.columns
        )

        if missing_columns:
            missing_text = ", ".join(
                sorted(missing_columns)
            )

            raise ValueError(
                "표준 주문에 필요한 컬럼이 없습니다: "
                f"{missing_text}"
            )

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""

        text = str(value).strip()

        if text.lower() in {
            "nan",
            "none",
            "nat",
        }:
            return ""

        return text

    @classmethod
    def _clean_identifier(cls, value: Any) -> str:
        text = cls._clean_text(value)

        if text.endswith(".0"):
            text = text[:-2]

        return text

    @staticmethod
    def _to_integer(
        value: Any,
        default: int = 0,
    ) -> int:
        if value is None:
            return default

        try:
            cleaned_value = (
                str(value)
                .replace(",", "")
                .strip()
            )

            if not cleaned_value:
                return default

            return int(float(cleaned_value))

        except (TypeError, ValueError):
            return default
        