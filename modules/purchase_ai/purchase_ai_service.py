"""AI 발주 추천센터 비즈니스 계층."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .purchase_ai_repository import PurchaseAIRepository
from .purchase_export_service import PurchaseExportService


class PurchaseAIService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.repository = PurchaseAIRepository(db_path)
        self.exporter = PurchaseExportService(db_path)

    def get_dashboard_data(self) -> dict[str, Any]:
        return self.repository.fetch_dashboard()

    def generate_supplier_groups(self) -> dict[str, Any]:
        return self.repository.generate_supplier_groups()

    def recalculate_recommendations(self) -> dict[str, int]:
        return self.repository.recalculate_recommendations()

    def get_plan_items(self, plan_id: int) -> list[dict[str, Any]]:
        return self.repository.fetch_plan_items(plan_id)

    def get_plan_preview(self, plan_id: int) -> dict[str, Any]:
        return self.repository.fetch_plan_preview(plan_id)

    def set_item_excluded(self, item_id: int, excluded: bool) -> None:
        self.repository.set_item_excluded(item_id, excluded)

    def confirm_plan(self, plan_id: int) -> dict[str, int]:
        return self.repository.confirm_plan(plan_id)

    def get_schema_status(self) -> dict[str, int]:
        return self.repository.get_schema_status()

    def build_purchase_message(self, plan_id: int, include_delivery: bool = False) -> str:
        return self.exporter.build_message_text(plan_id, include_delivery=include_delivery)

    def export_purchase_excel(self, plan_id: int, output_path: str | Path) -> Path:
        return self.exporter.export_excel(plan_id, output_path)
