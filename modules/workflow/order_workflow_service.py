from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from modules.orders.order_repository import OrderRepository
from modules.purchases.purchase_service import PurchaseService
from modules.shipments.shipment_service import ShipmentService


@dataclass(frozen=True)
class WorkflowPreview:
    """주문 → 자동매핑 → 발주 생성 전 점검 결과입니다."""

    mapping_target_count: int
    mapping_mapped_count: int
    mapping_rule_mapped_count: int
    mapping_exact_mapped_count: int
    mapping_smart_mapped_count: int
    mapping_unmatched_count: int
    mapping_ambiguous_count: int

    purchase_candidate_count: int
    purchase_error_count: int
    purchase_warning_count: int
    purchase_errors: tuple[str, ...]
    purchase_warnings: tuple[str, ...]

    @property
    def can_create_purchase(self) -> bool:
        return (
            self.purchase_candidate_count > 0
            and self.purchase_error_count == 0
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["can_create_purchase"] = self.can_create_purchase
        return result


@dataclass(frozen=True)
class ShipmentWorkflowPreview:
    """Summary of a shipment file before registration."""

    source_type: str
    total_count: int
    valid_count: int
    error_count: int
    rows: tuple[dict[str, Any], ...]

    @property
    def can_register(self) -> bool:
        return self.valid_count > 0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["can_register"] = self.can_register
        return result


class OrderWorkflowService:
    """
    기존 주문·상품매핑·발주 모듈을 연결하는 업무 흐름 서비스입니다.

    처리 순서
    1. 미매핑 주문상품 자동매핑
    2. 발주 가능 후보 조회
    3. 발주 전 필수값 검사
    4. 사용자가 명시적으로 실행한 경우에만 공급처별 발주서 생성

    주의
    - preview()는 자동매핑을 실제 DB에 반영합니다.
      기존 OrderRepository.auto_map_order_items()의 정상 동작입니다.
    - 발주서 생성은 create_purchase_files=True일 때만 실행합니다.
    - 기본값은 안전을 위해 발주서 미생성입니다.
    """

    def __init__(
        self,
        *,
        database_path: str | Path | None = None,
        output_root: str | Path | None = None,
        order_repository: OrderRepository | None = None,
        purchase_service: PurchaseService | None = None,
        shipment_service: ShipmentService | None = None,
    ) -> None:
        self.order_repository = (
            order_repository
            or OrderRepository(database_path=database_path)
        )
        self.purchase_service = (
            purchase_service
            or PurchaseService(
                database_path=database_path,
                output_root=output_root,
            )
        )
        self.shipment_service = shipment_service or ShipmentService()

    def preview(
        self,
        *,
        order_id: int | None = None,
    ) -> WorkflowPreview:
        """
        자동매핑을 수행한 뒤 발주 가능한 데이터를 검사합니다.

        order_id가 지정되면 해당 주문만 자동매핑합니다.
        발주 후보 검사는 현재 ERP 전체 발주대기 후보를 대상으로 합니다.
        """

        mapping = self.order_repository.auto_map_order_items(
            order_id=order_id
        )

        candidates = self.purchase_service.get_purchase_candidates()

        if order_id is not None:
            candidates = [
                candidate
                for candidate in candidates
                if int(candidate.get("order_id") or 0) == int(order_id)
            ]

        validation = self.purchase_service.validate_purchase_candidates(
            candidates
        )

        return WorkflowPreview(
            mapping_target_count=int(
                mapping.get("target_count", 0) or 0
            ),
            mapping_mapped_count=int(
                mapping.get("mapped_count", 0) or 0
            ),
            mapping_rule_mapped_count=int(
                mapping.get("rule_mapped_count", 0) or 0
            ),
            mapping_exact_mapped_count=int(
                mapping.get("exact_mapped_count", 0) or 0
            ),
            mapping_smart_mapped_count=int(
                mapping.get("smart_mapped_count", 0) or 0
            ),
            mapping_unmatched_count=int(
                mapping.get("unmatched_count", 0) or 0
            ),
            mapping_ambiguous_count=int(
                mapping.get("ambiguous_count", 0) or 0
            ),
            purchase_candidate_count=len(candidates),
            purchase_error_count=int(
                validation.get("error_count", 0) or 0
            ),
            purchase_warning_count=int(
                validation.get("warning_count", 0) or 0
            ),
            purchase_errors=tuple(
                str(item)
                for item in validation.get("errors", [])
            ),
            purchase_warnings=tuple(
                str(item)
                for item in validation.get("warnings", [])
            ),
        )

    def execute(
        self,
        *,
        order_id: int | None = None,
        create_purchase_files: bool = False,
        allow_warnings: bool = False,
    ) -> dict[str, Any]:
        """
        주문 → 자동매핑 → 발주서 생성 흐름을 실행합니다.

        안전장치
        - create_purchase_files=False: 점검만 하고 발주서를 만들지 않음
        - 차단 오류가 있으면 발주 생성 중단
        - 주의사항이 있을 때 allow_warnings=False이면 발주 생성 중단
        """

        preview = self.preview(order_id=order_id)
        preview_dict = preview.to_dict()

        if not create_purchase_files:
            return {
                "executed": False,
                "purchase_created": False,
                "reason": "발주서 생성 옵션이 꺼져 있습니다.",
                "preview": preview_dict,
            }

        if preview.purchase_error_count > 0:
            return {
                "executed": False,
                "purchase_created": False,
                "reason": "발주 전 차단 오류가 있습니다.",
                "preview": preview_dict,
            }

        if (
            preview.purchase_warning_count > 0
            and not allow_warnings
        ):
            return {
                "executed": False,
                "purchase_created": False,
                "reason": (
                    "발주 전 주의사항이 있습니다. "
                    "확인 후 allow_warnings=True로 다시 실행하세요."
                ),
                "preview": preview_dict,
            }

        candidates = self.purchase_service.get_purchase_candidates()

        if order_id is not None:
            candidates = [
                candidate
                for candidate in candidates
                if int(candidate.get("order_id") or 0) == int(order_id)
            ]

        order_item_ids = [
            int(candidate["order_item_id"])
            for candidate in candidates
        ]

        purchase_result = self.purchase_service.create_purchase_files(
            order_item_ids=order_item_ids
        )

        return {
            "executed": True,
            "purchase_created": (
                int(purchase_result.get("created_count", 0) or 0) > 0
            ),
            "preview": preview_dict,
            "purchase": purchase_result,
        }

    def preview_shipments(
        self,
        file_path: str | Path,
    ) -> ShipmentWorkflowPreview:
        """Parse and match a shipment file without registering shipments."""

        result = self.shipment_service.preview_simple_shipment_file(
            file_path
        )
        rows = tuple(dict(row) for row in result.get("rows", []))

        return ShipmentWorkflowPreview(
            source_type=str(result.get("source_type") or ""),
            total_count=int(result.get("total_count", len(rows)) or 0),
            valid_count=int(result.get("valid_count", 0) or 0),
            error_count=int(result.get("error_count", 0) or 0),
            rows=rows,
        )

    def register_shipments(
        self,
        file_path: str | Path,
        *,
        allow_partial: bool = False,
    ) -> dict[str, Any]:
        """Preview and register valid rows from a shipment file."""

        preview = self.preview_shipments(file_path)
        preview_dict = preview.to_dict()

        if not preview.can_register:
            return {
                "executed": False,
                "shipment_registered": False,
                "reason": "No valid shipment rows were found.",
                "preview": preview_dict,
            }

        if preview.error_count > 0 and not allow_partial:
            return {
                "executed": False,
                "shipment_registered": False,
                "reason": (
                    "Shipment registration was blocked because the file "
                    "contains invalid or ambiguous rows."
                ),
                "preview": preview_dict,
            }

        shipment_result = self.shipment_service.save_simple_shipments(
            list(preview.rows)
        )
        registered_count = int(
            shipment_result.get("shipment_count", 0) or 0
        )

        return {
            "executed": True,
            "shipment_registered": registered_count > 0,
            "preview": preview_dict,
            "shipment": shipment_result,
        }
