from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .base_parser import BaseShipmentParser


class JuyeongShipmentParser(BaseShipmentParser):
    """주영씨푸드 발주서 회신 파일의 송장 정보를 읽습니다."""

    parser_key = "juyeong"
    display_name = "주영씨푸드 송장 회신"
    supplier_name = "주영씨푸드"

    REQUIRED_HEADERS = {
        "받는분성명",
        "전화번호",
        "받는분주소",
        "품목명",
        "박스수량",
        "택배사",
        "운송장번호",
    }

    def detect(self, file_path: str | Path) -> bool:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            header_map = self.build_header_map(worksheet, 1)
            return self.REQUIRED_HEADERS.issubset(header_map)
        finally:
            workbook.close()

    def parse(self, file_path: str | Path) -> dict[str, Any]:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            header_map = self.build_header_map(worksheet, 1)
            missing = sorted(self.REQUIRED_HEADERS.difference(header_map))
            if missing:
                raise ValueError(
                    "주영씨푸드 송장 양식의 필수 열이 없습니다: "
                    + ", ".join(missing)
                )

            rows: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            for excel_row in range(2, worksheet.max_row + 1):
                row = self._parse_row(worksheet, excel_row, header_map)
                if row is None:
                    continue
                row_errors = self._validate(row)
                row["error_message"] = ", ".join(row_errors)
                if row_errors:
                    errors.append(row)
                else:
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
        def value(header: str) -> Any:
            return worksheet.cell(excel_row, header_map[header]).value

        receiver_name = value("받는분성명")
        receiver_phone = value("전화번호")
        product_value = value("품목명")
        carrier_value = value("택배사")
        tracking_value = value("운송장번호")
        important = (
            receiver_name,
            receiver_phone,
            product_value,
            carrier_value,
            tracking_value,
        )
        if all(self.clean_text(item) == "" for item in important):
            return None

        product_text = self.clean_text(product_value)
        product_name, quantity = self._product_and_quantity(
            product_text,
            value("박스수량"),
        )
        tracking_numbers = self.split_tracking_numbers(tracking_value)
        return {
            "excel_row": excel_row,
            "supplier_name": self.supplier_name,
            "receiver_name": self.clean_text(receiver_name),
            "receiver_phone": self.normalize_phone(receiver_phone),
            "receiver_address": self.clean_text(value("받는분주소")),
            "product_name": product_name,
            "option_name": "",
            "quantity": quantity,
            "delivery_message": self.clean_text(value("배송메세지1"))
            if "배송메세지1" in header_map
            else "",
            "carrier": self.normalize_carrier(carrier_value),
            "tracking_numbers": tracking_numbers,
            "tracking_number": "/".join(tracking_numbers),
        }

    @classmethod
    def _product_and_quantity(
        cls,
        product_text: str,
        box_quantity: Any,
    ) -> tuple[str, int]:
        match = re.search(r"\s+x\s*(\d+)\s*$", product_text, re.IGNORECASE)
        if match is None:
            return product_text, cls.normalize_quantity(box_quantity)
        return product_text[:match.start()].strip(), int(match.group(1))

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
            errors.append("운송장번호 없음")
        return errors
