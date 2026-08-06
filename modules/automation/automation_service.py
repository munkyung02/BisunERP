from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from legacy_order_runner import main as run_legacy_order
from modules.orders.order_repository import OrderRepository


@dataclass(frozen=True)
class AutomationResult:
    step: str
    success: bool
    message: str
    processed_count: int = 0


class AutomationService:
    """기존 기능을 안전하게 묶는 자동화 실행 서비스입니다."""

    def __init__(
        self,
        order_repository: OrderRepository | None = None,
    ) -> None:
        self.order_repository = order_repository or OrderRepository()

    def collect_orders(self) -> AutomationResult:
        """기존 주문 엔진을 실행해 주문 수집·발주서 생성을 수행합니다."""
        run_legacy_order()
        return AutomationResult(
            step="주문 수집",
            success=True,
            message="기존 주문 엔진 실행이 완료되었습니다.",
        )

    def auto_map_orders(self) -> AutomationResult:
        """미매핑 주문상품에 자동매핑을 적용합니다."""
        method = getattr(
            self.order_repository,
            "auto_map_order_items",
            None,
        )
        if method is None:
            return AutomationResult(
                step="자동 상품매핑",
                success=False,
                message="현재 OrderRepository에 자동매핑 기능이 없습니다.",
            )

        result = method()
        count = self._extract_count(result)
        return AutomationResult(
            step="자동 상품매핑",
            success=True,
            message=f"자동매핑 처리가 완료되었습니다. ({count:,}건)",
            processed_count=count,
        )

    def prepare_purchase_orders(self) -> AutomationResult:
        """발주 생성 단계의 현재 지원 상태를 반환합니다."""
        return AutomationResult(
            step="발주 생성",
            success=True,
            message=(
                "주문 엔진에서 발주서 생성 단계가 함께 실행됩니다. "
                "발주관리 화면에서 결과를 확인하세요."
            ),
        )

    def import_shipments(self) -> AutomationResult:
        """송장 엑셀 자동등록은 공급처 파일 선택이 필요하므로 화면 연결 상태를 반환합니다."""
        return AutomationResult(
            step="송장 등록",
            success=True,
            message=(
                "송장관리를 열어 공급처와 엑셀 파일을 선택한 뒤 "
                "매칭 결과를 저장하세요."
            ),
        )

    def check_delivery(self) -> AutomationResult:
        """배송조회 API가 아직 연결되지 않았음을 명확하게 반환합니다."""
        return AutomationResult(
            step="배송 조회",
            success=False,
            message="택배사 배송조회 API 연결 전 단계입니다.",
        )

    def run_supported_pipeline(
        self,
        logger: Callable[[str], None] | None = None,
    ) -> list[AutomationResult]:
        """현재 실제 실행 가능한 단계만 순서대로 수행합니다."""
        results: list[AutomationResult] = []
        steps = (
            self.collect_orders,
            self.auto_map_orders,
            self.prepare_purchase_orders,
        )

        for function in steps:
            result = function()
            results.append(result)
            if logger is not None:
                logger(self.format_log(result))
            if not result.success:
                break

        return results

    @staticmethod
    def format_log(result: AutomationResult) -> str:
        status = "완료" if result.success else "확인 필요"
        current_time = datetime.now().strftime("%H:%M:%S")
        return f"[{current_time}] [{status}] {result.step} - {result.message}"

    @staticmethod
    def _extract_count(value: Any) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, dict):
            for key in (
                "updated_count",
                "mapped_count",
                "count",
                "processed_count",
            ):
                if key in value:
                    try:
                        return int(value[key] or 0)
                    except (TypeError, ValueError):
                        return 0
        if isinstance(value, (list, tuple, set)):
            return len(value)
        return 0
