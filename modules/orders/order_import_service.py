from pathlib import Path
from typing import Any

import pandas as pd

from modules.orders.order_repository import OrderRepository


class OrderImportService:
    """쿠팡 주문 엑셀을 읽어 ERP 주문 DB에 저장합니다."""

    REQUIRED_COLUMNS = {
        "주문번호",
        "주문일",
        "등록상품명",
        "등록옵션명",
        "결제액",
        "구매수(수량)",
        "수취인이름",
        "수취인전화번호",
        "우편번호",
        "수취인 주소",
        "배송메세지",
    }

    def __init__(
        self,
        repository: OrderRepository | None = None,
    ) -> None:
        self.repository = repository or OrderRepository()

    def import_coupang_excel(
        self,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """쿠팡 주문 엑셀을 읽고 주문번호별로 묶어 저장합니다."""

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"파일을 찾을 수 없습니다.\n{path}"
            )

        if path.suffix.lower() not in {
            ".xlsx",
            ".xls",
        }:
            raise ValueError(
                "엑셀 파일만 불러올 수 있습니다."
            )

        dataframe = self._read_excel(path)
        self._validate_columns(dataframe)

        orders = self._convert_to_orders(
            dataframe=dataframe,
            source_file=path.name,
        )

        result = self.repository.create_orders_bulk(
            orders,
            skip_duplicates=True,
        )

        result["source_file"] = path.name
        result["excel_row_count"] = len(dataframe)
        result["parsed_order_count"] = len(orders)

        return result

    def preview_coupang_excel(
        self,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """DB에 저장하지 않고 엑셀 구조만 확인합니다."""

        path = Path(file_path)
        dataframe = self._read_excel(path)
        self._validate_columns(dataframe)

        orders = self._convert_to_orders(
            dataframe=dataframe,
            source_file=path.name,
        )

        return {
            "source_file": path.name,
            "excel_row_count": len(dataframe),
            "parsed_order_count": len(orders),
            "orders": orders,
        }

    def _read_excel(
        self,
        path: Path,
    ) -> pd.DataFrame:
        try:
            dataframe = pd.read_excel(
                path,
                dtype=str,
            )
        except ImportError as error:
            raise RuntimeError(
                "엑셀을 읽기 위한 패키지가 부족합니다.\n\n"
                "다음 명령을 실행해주세요.\n"
                "pip install pandas openpyxl"
            ) from error
        except Exception as error:
            raise RuntimeError(
                "엑셀 파일을 읽지 못했습니다.\n\n"
                f"{error}"
            ) from error

        dataframe.columns = [
            str(column).strip()
            for column in dataframe.columns
        ]

        dataframe = dataframe.dropna(
            how="all"
        ).reset_index(drop=True)

        return dataframe

    def _validate_columns(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        current_columns = {
            str(column).strip()
            for column in dataframe.columns
        }

        missing_columns = sorted(
            self.REQUIRED_COLUMNS
            - current_columns
        )

        if missing_columns:
            raise ValueError(
                "쿠팡 주문 엑셀에 필요한 컬럼이 없습니다.\n\n"
                "누락 컬럼:\n"
                + "\n".join(
                    f"• {column}"
                    for column in missing_columns
                )
            )

    def _convert_to_orders(
        self,
        dataframe: pd.DataFrame,
        source_file: str,
    ) -> list[dict[str, Any]]:
        working = dataframe.copy()

        working["주문번호"] = working[
            "주문번호"
        ].apply(self._clean_identifier)

        working = working[
            working["주문번호"] != ""
        ].copy()

        if working.empty:
            raise ValueError(
                "저장할 주문이 없습니다."
            )

        orders: list[dict[str, Any]] = []

        grouped = working.groupby(
            "주문번호",
            sort=False,
            dropna=False,
        )

        for order_number, group in grouped:
            first_row = group.iloc[0]

            items: list[dict[str, Any]] = []
            total_amount = 0

            for _, row in group.iterrows():
                product_name = self._clean_text(
                    row.get("등록상품명")
                )

                if not product_name:
                    continue

                quantity = self._to_positive_int(
                    row.get("구매수(수량)"),
                    default=1,
                )

                line_total = self._to_non_negative_int(
                    row.get("결제액"),
                    default=0,
                )

                unit_price = (
                    line_total // quantity
                    if quantity > 0
                    else line_total
                )

                items.append(
                    {
                        "platform_product_name": (
                            product_name
                        ),
                        "option_name": self._clean_text(
                            row.get("등록옵션명")
                        ),
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": line_total,
                        "purchase_round": "",
                        "mapping_status": "미매핑",
                    }
                )

                total_amount += line_total

            if not items:
                continue

            order = {
                "platform": "쿠팡",
                "order_number": str(order_number),
                "ordered_at": self._clean_datetime(
                    first_row.get("주문일")
                ),
                "receiver_name": self._clean_text(
                    first_row.get("수취인이름")
                ),
                "receiver_phone": self._clean_text(
                    first_row.get(
                        "수취인전화번호"
                    )
                ),
                "postal_code": self._clean_identifier(
                    first_row.get("우편번호")
                ),
                "address": self._clean_text(
                    first_row.get("수취인 주소")
                ),
                "detail_address": "",
                "delivery_message": self._clean_text(
                    first_row.get("배송메세지")
                ),
                "order_status": "주문접수",
                "payment_status": "결제완료",
                "mapping_status": "미매핑",
                "purchase_status": "발주대기",
                "shipment_status": "배송대기",
                "total_amount": total_amount,
                "source_file": source_file,
                "items": items,
            }

            orders.append(order)

        if not orders:
            raise ValueError(
                "엑셀에서 변환할 수 있는 주문이 없습니다."
            )

        return orders

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass

        text = str(value).strip()

        if text.lower() == "nan":
            return ""

        return text

    @classmethod
    def _clean_identifier(
        cls,
        value: Any,
    ) -> str:
        text = cls._clean_text(value)

        if not text:
            return ""

        if text.endswith(".0"):
            numeric_part = text[:-2]

            if numeric_part.isdigit():
                return numeric_part

        return text

    @classmethod
    def _clean_datetime(
        cls,
        value: Any,
    ) -> str:
        text = cls._clean_text(value)

        if not text:
            return ""

        try:
            converted = pd.to_datetime(
                value,
                errors="coerce",
            )

            if pd.isna(converted):
                return text

            return converted.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except Exception:
            return text

    @classmethod
    def _to_positive_int(
        cls,
        value: Any,
        default: int = 1,
    ) -> int:
        text = cls._clean_text(value)

        if not text:
            return default

        try:
            converted = int(
                float(
                    text.replace(",", "")
                )
            )
        except (TypeError, ValueError):
            return default

        if converted <= 0:
            return default

        return converted

    @classmethod
    def _to_non_negative_int(
        cls,
        value: Any,
        default: int = 0,
    ) -> int:
        text = cls._clean_text(value)

        if not text:
            return default

        try:
            converted = int(
                float(
                    text.replace(",", "")
                )
            )
        except (TypeError, ValueError):
            return default

        return max(converted, 0)