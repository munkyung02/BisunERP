from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.shipments.parsers.base_parser import BaseShipmentParser


class ConfigurableShipmentParser(BaseShipmentParser):
    """저장된 열 번호로 공급처 회신 송장 파일을 읽습니다."""

    parser_key = "supplier_config"

    def __init__(
        self,
        *,
        supplier_name: str,
        header_row: int,
        order_number_column: int,
        carrier_column: int,
        tracking_number_column: int,
    ) -> None:
        self.supplier_name = supplier_name
        self.display_name = f"{supplier_name} 등록양식"
        self.header_row = int(header_row)
        self.columns = {
            "order_number": int(order_number_column),
            "carrier": int(carrier_column),
            "tracking_number": int(tracking_number_column),
        }

    def detect(self, file_path: str | Path) -> bool:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            return self._validate_coordinates(worksheet)
        finally:
            workbook.close()

    def parse(self, file_path: str | Path) -> dict[str, Any]:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            if not self._validate_coordinates(worksheet):
                raise ValueError(
                    "저장된 헤더 행 또는 열을 현재 파일에서 찾을 수 없습니다."
                )

            rows: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            start_row = self.header_row + 1

            for excel_row in range(start_row, worksheet.max_row + 1):
                order_number = self.clean_text(
                    worksheet.cell(
                        excel_row,
                        self.columns["order_number"],
                    ).value
                )
                carrier = self.normalize_carrier(
                    worksheet.cell(
                        excel_row,
                        self.columns["carrier"],
                    ).value
                )
                tracking_cell = worksheet.cell(
                    excel_row,
                    self.columns["tracking_number"],
                )
                tracking_number = self._tracking_text(tracking_cell)

                if not any((order_number, carrier, tracking_number)):
                    continue

                row = {
                    "excel_row": excel_row,
                    "order_number": order_number,
                    "carrier": carrier,
                    "tracking_number": tracking_number,
                }
                row_errors: list[str] = []
                if not order_number:
                    row_errors.append("주문번호 없음")
                if not carrier:
                    row_errors.append("택배사 없음")
                if not tracking_number:
                    row_errors.append("송장번호 없음")

                if row_errors:
                    row["error_message"] = ", ".join(row_errors)
                    errors.append(row)
                else:
                    rows.append(row)

            return {
                "source_type": self.display_name,
                "supplier_name": self.supplier_name,
                "match_mode": "order_number",
                "file_path": str(Path(file_path)),
                "rows": rows,
                "errors": errors,
                "total_count": len(rows) + len(errors),
                "valid_count": len(rows),
                "error_count": len(errors),
            }
        finally:
            workbook.close()

    def _validate_coordinates(self, worksheet: Any) -> bool:
        if self.header_row < 1 or self.header_row > worksheet.max_row:
            return False
        selected_columns = list(self.columns.values())
        if len(set(selected_columns)) != len(selected_columns):
            return False
        for column in selected_columns:
            if column < 1 or column > worksheet.max_column:
                return False
            if not self.clean_text(
                worksheet.cell(self.header_row, column).value
            ):
                return False
        return True

    @classmethod
    def _tracking_text(cls, cell: Any) -> str:
        value = cell.value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number_format = str(cell.number_format or "").strip()
            zero_mask = number_format.split(";")[0]
            if zero_mask and set(zero_mask) == {"0"}:
                return str(int(value)).zfill(len(zero_mask))
        return cls.clean_tracking_number(value)
