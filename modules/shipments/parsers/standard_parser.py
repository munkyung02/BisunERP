from __future__ import annotations

from pathlib import Path
from typing import Any

from .base_parser import BaseShipmentParser


class StandardShipmentParser(BaseShipmentParser):
    """주문번호·택배사·송장번호 형태의 비선ERP 기본 송장 파서입니다."""

    parser_key = "standard"
    display_name = "기본 송장양식"
    supplier_name = None

    HEADER_ALIASES = {
        "order_number": {
            "주문번호",
            "주문 번호",
            "order_number",
            "orderno",
            "상품주문번호",
        },
        "carrier": {
            "택배사",
            "배송사",
            "courier",
            "carrier",
        },
        "tracking_number": {
            "송장번호",
            "운송장번호",
            "송장 번호",
            "tracking_number",
            "invoice",
        },
    }

    def detect(self, file_path: str | Path) -> bool:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            columns = self._find_columns(worksheet)
            return all(
                key in columns
                for key in (
                    "order_number",
                    "carrier",
                    "tracking_number",
                )
            )
        finally:
            workbook.close()

    def parse(self, file_path: str | Path) -> dict[str, Any]:
        workbook, worksheet = self.open_first_sheet(file_path)
        try:
            columns = self._find_columns(worksheet)
            missing = [
                key
                for key in (
                    "order_number",
                    "carrier",
                    "tracking_number",
                )
                if key not in columns
            ]
            if missing:
                raise ValueError(
                    "기본 송장양식의 필수 열을 찾지 못했습니다.\n"
                    "필수 열: 주문번호, 택배사, 송장번호"
                )

            rows: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []

            for excel_row in range(2, worksheet.max_row + 1):
                order_number = self.clean_text(
                    worksheet.cell(
                        excel_row,
                        columns["order_number"],
                    ).value
                )
                carrier = self.normalize_carrier(
                    worksheet.cell(
                        excel_row,
                        columns["carrier"],
                    ).value
                )
                tracking = self.clean_tracking_number(
                    worksheet.cell(
                        excel_row,
                        columns["tracking_number"],
                    ).value
                )

                if not any((order_number, carrier, tracking)):
                    continue

                row = {
                    "excel_row": excel_row,
                    "order_number": order_number,
                    "carrier": carrier,
                    "tracking_number": tracking,
                }

                row_errors: list[str] = []
                if not order_number:
                    row_errors.append("주문번호 없음")
                if not carrier:
                    row_errors.append("택배사 없음")
                if not tracking:
                    row_errors.append("송장번호 없음")

                if row_errors:
                    row["error_message"] = ", ".join(row_errors)
                    errors.append(row)
                else:
                    rows.append(row)

            return {
                "source_type": self.display_name,
                "supplier_name": "",
                "file_path": str(Path(file_path)),
                "rows": rows,
                "errors": errors,
                "total_count": len(rows) + len(errors),
                "valid_count": len(rows),
                "error_count": len(errors),
            }
        finally:
            workbook.close()

    def _find_columns(self, worksheet: Any) -> dict[str, int]:
        header_map = self.build_header_map(worksheet, 1)
        normalized = {
            header.lower().replace(" ", ""): column
            for header, column in header_map.items()
        }

        columns: dict[str, int] = {}
        for key, aliases in self.HEADER_ALIASES.items():
            for alias in aliases:
                normalized_alias = alias.lower().replace(" ", "")
                if normalized_alias in normalized:
                    columns[key] = normalized[normalized_alias]
                    break
        return columns
