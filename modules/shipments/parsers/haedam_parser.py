from __future__ import annotations

from pathlib import Path
from typing import Any

from .base_parser import BaseShipmentParser


class HaedamShipmentParser(BaseShipmentParser):
    """해담 회신 발주서의 J열 택배사·K열 송장번호를 읽습니다."""

    parser_key = "haedam"
    display_name = "해담 회신 발주서"
    supplier_name = "해담"

    REQUIRED_HEADERS = {
        "받는분성명",
        "받는분전화번호",
        "품목",
        "수량",
    }

    COLUMN_HEADERS = {
        "receiver_name": "받는분성명",
        "receiver_phone": "받는분전화번호",
        "receiver_address": "받는분주소(전체, 분할)",
        "product_name": "품목",
        "quantity": "수량",
        "delivery_message": "배송메세지",
    }

    CARRIER_COLUMN = 10
    TRACKING_COLUMN = 11

    def detect(self, file_path: str | Path) -> bool:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            header_map = self.build_header_map(worksheet, 1)
            return (
                self.REQUIRED_HEADERS.issubset(set(header_map))
                and worksheet.max_column >= self.TRACKING_COLUMN
            )
        finally:
            workbook.close()

    def parse(self, file_path: str | Path) -> dict[str, Any]:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            header_map = self.build_header_map(worksheet, 1)
            missing = sorted(
                self.REQUIRED_HEADERS.difference(set(header_map))
            )
            if missing:
                raise ValueError(
                    "해담 양식의 필수 열이 없습니다: "
                    + ", ".join(missing)
                )

            rows: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []

            for excel_row in range(2, worksheet.max_row + 1):
                row = self._parse_row(
                    worksheet,
                    excel_row,
                    header_map,
                )
                if row is None:
                    continue

                row_errors = self._validate(row)
                if row_errors:
                    row["error_message"] = ", ".join(row_errors)
                    errors.append(row)
                else:
                    row["error_message"] = ""
                    rows.append(row)

            return {
                "source_type": self.display_name,
                "supplier_name": self.supplier_name,
                "file_path": str(Path(file_path)),
                "rows": rows,
                "errors": errors,
                "total_count": len(rows) + len(errors),
                "valid_count": len(rows),
                "error_count": len(errors),
            }
        finally:
            workbook.close()

    def _parse_row(
        self,
        worksheet: Any,
        excel_row: int,
        header_map: dict[str, int],
    ) -> dict[str, Any] | None:
        def by_header(name: str) -> Any:
            column = header_map.get(name)
            if column is None:
                return None
            return worksheet.cell(excel_row, column).value

        receiver_name = by_header(
            self.COLUMN_HEADERS["receiver_name"]
        )
        receiver_phone = by_header(
            self.COLUMN_HEADERS["receiver_phone"]
        )
        receiver_address = by_header(
            self.COLUMN_HEADERS["receiver_address"]
        )
        product_name = by_header(
            self.COLUMN_HEADERS["product_name"]
        )
        quantity = by_header(
            self.COLUMN_HEADERS["quantity"]
        )
        delivery_message = by_header(
            self.COLUMN_HEADERS["delivery_message"]
        )
        carrier = worksheet.cell(
            excel_row,
            self.CARRIER_COLUMN,
        ).value
        tracking_value = worksheet.cell(
            excel_row,
            self.TRACKING_COLUMN,
        ).value

        important = [
            receiver_name,
            receiver_phone,
            product_name,
            carrier,
            tracking_value,
        ]
        if all(self.clean_text(value) == "" for value in important):
            return None

        tracking_numbers = self.split_tracking_numbers(
            tracking_value
        )

        return {
            "excel_row": excel_row,
            "supplier_name": self.supplier_name,
            "receiver_name": self.clean_text(receiver_name),
            "receiver_phone": self.normalize_phone(receiver_phone),
            "receiver_address": self.clean_text(receiver_address),
            "product_name": self.clean_text(product_name),
            "quantity": self.normalize_quantity(quantity),
            "delivery_message": self.clean_text(delivery_message),
            "carrier": self.normalize_carrier(carrier),
            "tracking_numbers": tracking_numbers,
            "tracking_number": "/".join(tracking_numbers),
        }

    @staticmethod
    def _validate(row: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not row["receiver_name"]:
            errors.append("수취인명 없음")
        if not row["receiver_phone"]:
            errors.append("전화번호 없음")
        if not row["product_name"]:
            errors.append("상품명 없음")
        if int(row["quantity"] or 0) <= 0:
            errors.append("수량 오류")
        if not row["carrier"]:
            errors.append("택배사 없음")
        if not row["tracking_numbers"]:
            errors.append("송장번호 없음")
        return errors
