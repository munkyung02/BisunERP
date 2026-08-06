from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from .base import PurchaseTemplate
from .helpers import aggregate_items, safe_filename


class SummaryOnlyPurchaseTemplate(PurchaseTemplate):
    """
    상품코드·상품명·옵션·수량만 필요한 공급처용 간단 양식입니다.
    """

    template_key = "summary_only"
    display_name = "상품 합산 간단 양식"

    def create_excel(
        self,
        *,
        output_directory: Path,
        supplier_name: str,
        purchase_round: str,
        items: list[dict[str, Any]],
    ) -> Path:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "발주서"

        sheet["A1"] = f"{supplier_name} 발주서"
        sheet["A1"].font = Font(size=16, bold=True)

        sheet.append([])
        sheet.append([
            "공급처 상품코드",
            "공급처 상품명",
            "옵션",
            "총 수량",
        ])

        for cell in sheet[3]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        for item in aggregate_items(items):
            sheet.append([
                item.get("supplier_product_code") or "",
                item.get("product_name") or "",
                item.get("option_name") or "",
                int(item.get("total_quantity") or 0),
            ])

        sheet.column_dimensions["A"].width = 20
        sheet.column_dimensions["B"].width = 36
        sheet.column_dimensions["C"].width = 30
        sheet.column_dimensions["D"].width = 12

        timestamp = datetime.now().strftime("%H%M%S")
        file_path = output_directory / (
            f"{safe_filename(supplier_name)}_"
            f"{safe_filename(purchase_round)}_"
            f"간단발주서_{timestamp}.xlsx"
        )
        workbook.save(file_path)
        return file_path
