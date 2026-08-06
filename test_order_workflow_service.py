from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from modules.workflow.order_workflow_service import OrderWorkflowService


class FakeShipmentService:
    def __init__(self, preview: dict[str, Any]) -> None:
        self.preview = preview
        self.saved_rows: list[dict[str, Any]] | None = None

    def preview_simple_shipment_file(
        self,
        file_path: str | Path,
    ) -> dict[str, Any]:
        return self.preview

    def save_simple_shipments(
        self,
        rows: list[dict[str, Any]],
    ) -> dict[str, int]:
        self.saved_rows = rows
        return {
            "shipment_count": len(rows),
            "order_count": len(rows),
            "skipped_count": 0,
        }


class OrderWorkflowShipmentTests(unittest.TestCase):
    @staticmethod
    def make_service(
        shipment_service: FakeShipmentService,
    ) -> OrderWorkflowService:
        return OrderWorkflowService(
            order_repository=object(),
            purchase_service=object(),
            shipment_service=shipment_service,
        )

    def test_preview_uses_production_shipment_preview_contract(self) -> None:
        shipment_service = FakeShipmentService(
            {
                "source_type": "standard",
                "total_count": 1,
                "valid_count": 1,
                "error_count": 0,
                "rows": [{"status": "valid", "tracking_number": "123"}],
            }
        )

        preview = self.make_service(shipment_service).preview_shipments(
            "shipments.xlsx"
        )

        self.assertTrue(preview.can_register)
        self.assertEqual(preview.valid_count, 1)
        self.assertEqual(preview.rows[0]["tracking_number"], "123")

    def test_registration_is_blocked_when_preview_has_errors(self) -> None:
        shipment_service = FakeShipmentService(
            {
                "source_type": "standard",
                "total_count": 2,
                "valid_count": 1,
                "error_count": 1,
                "rows": [
                    {"status": "valid", "tracking_number": "123"},
                    {"status": "error", "tracking_number": ""},
                ],
            }
        )

        result = self.make_service(shipment_service).register_shipments(
            "shipments.xlsx"
        )

        self.assertFalse(result["executed"])
        self.assertFalse(result["shipment_registered"])
        self.assertIsNone(shipment_service.saved_rows)

    def test_partial_registration_reuses_validated_preview_rows(self) -> None:
        rows = [
            {"status": "valid", "tracking_number": "123"},
            {"status": "error", "tracking_number": ""},
        ]
        shipment_service = FakeShipmentService(
            {
                "source_type": "standard",
                "total_count": 2,
                "valid_count": 1,
                "error_count": 1,
                "rows": rows,
            }
        )

        result = self.make_service(shipment_service).register_shipments(
            "shipments.xlsx",
            allow_partial=True,
        )

        self.assertTrue(result["executed"])
        self.assertTrue(result["shipment_registered"])
        self.assertEqual(shipment_service.saved_rows, rows)

    def test_registration_is_not_attempted_without_valid_rows(self) -> None:
        shipment_service = FakeShipmentService(
            {
                "source_type": "standard",
                "total_count": 1,
                "valid_count": 0,
                "error_count": 1,
                "rows": [{"status": "error", "tracking_number": ""}],
            }
        )

        result = self.make_service(shipment_service).register_shipments(
            "shipments.xlsx"
        )

        self.assertFalse(result["executed"])
        self.assertIsNone(shipment_service.saved_rows)


if __name__ == "__main__":
    unittest.main()
