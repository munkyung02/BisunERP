from __future__ import annotations

from pathlib import Path
from typing import Any

from .base_parser import BaseShipmentParser


class FoodPresidentShipmentParser(BaseShipmentParser):
    """푸드대통령 고정 송장 회신 양식을 읽습니다."""

    parser_key = "foodpresident"
    display_name = "푸드대통령 송장 회신"
    supplier_name = "푸드대통령"

    REQUIRED_HEADERS = {
        "모델명",
        "상품주문번호",
        "상품명",
        "수량",
        "수령인",
        "수령인연락처1",
        "주소",
        "택배사",
        "송장번호",
    }

    COLUMN_HEADERS = {
        "supplier_product_code": "모델명",
        "supplier_order_number": "상품주문번호",
        "product_name": "상품명",
        "quantity": "수량",
        "receiver_name": "수령인",
        "receiver_phone": "수령인연락처1",
        "receiver_address": "주소",
        "delivery_message": "배송메모",
        "carrier": "택배사",
        "tracking_number": "송장번호",
    }

    def detect(self, file_path: str | Path) -> bool:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            self._prepare_dimensions(worksheet)
            header_map = self.build_header_map(worksheet, 1)
            return self.REQUIRED_HEADERS.issubset(header_map)
        finally:
            workbook.close()

    def parse(self, file_path: str | Path) -> dict[str, Any]:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            self._prepare_dimensions(worksheet)
            header_map = self.build_header_map(worksheet, 1)
            missing = sorted(self.REQUIRED_HEADERS.difference(header_map))
            if missing:
                raise ValueError(
                    "푸드대통령 송장 양식의 필수 열이 없습니다: "
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
        def cell_for(key: str) -> Any:
            column = header_map[self.COLUMN_HEADERS[key]]
            return worksheet.cell(excel_row, column)

        receiver_name = cell_for("receiver_name").value
        receiver_phone = cell_for("receiver_phone").value
        product_name = cell_for("product_name").value
        carrier_value = cell_for("carrier").value
        tracking_cell = cell_for("tracking_number")

        important = (
            receiver_name,
            receiver_phone,
            product_name,
            carrier_value,
            tracking_cell.value,
        )
        if all(self.clean_text(value) == "" for value in important):
            return None

        tracking_number = self._tracking_text(tracking_cell)
        carrier = self._normalize_foodpresident_carrier(carrier_value)

        return {
            "excel_row": excel_row,
            "supplier_name": self.supplier_name,
            "supplier_product_code": self.clean_text(
                cell_for("supplier_product_code").value
            ),
            "supplier_order_number": self.clean_text(
                cell_for("supplier_order_number").value
            ),
            "receiver_name": self.clean_text(receiver_name),
            "receiver_phone": self.normalize_phone(receiver_phone),
            "receiver_address": self.clean_text(
                cell_for("receiver_address").value
            ),
            "product_name": self.clean_text(product_name),
            "option_name": "",
            "quantity": self.normalize_quantity(
                cell_for("quantity").value
            ),
            "delivery_message": self.clean_text(
                cell_for("delivery_message").value
            ),
            "carrier": carrier,
            "tracking_numbers": [tracking_number] if tracking_number else [],
            "tracking_number": tracking_number,
        }

    @staticmethod
    def _prepare_dimensions(worksheet: Any) -> None:
        if worksheet.max_row == 1 and worksheet.max_column == 1:
            worksheet.reset_dimensions()
            worksheet.calculate_dimension(force=True)

    @classmethod
    def _normalize_foodpresident_carrier(cls, value: Any) -> str:
        original = cls.clean_text(value)
        compact = original.replace(" ", "").lower()
        if compact in {
            "롯데(현대)택배",
            "롯데현대택배",
            "롯데택배",
        }:
            return "롯데택배"
        return cls.normalize_carrier(original)

    @classmethod
    def _tracking_text(cls, cell: Any) -> str:
        value = cell.value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number_format = str(cell.number_format or "").strip()
            zero_mask = number_format.split(";")[0]
            if zero_mask and set(zero_mask) == {"0"}:
                return str(int(value)).zfill(len(zero_mask))
        return cls.clean_tracking_number(value)

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
