from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class PurchaseTemplate(ABC):
    """공급처별 발주서 생성 플러그인의 공통 인터페이스입니다."""

    template_key = "base"
    display_name = "기본 인터페이스"

    @abstractmethod
    def create_excel(
        self,
        *,
        output_directory: Path,
        supplier_name: str,
        purchase_round: str,
        items: list[dict[str, Any]],
    ) -> Path:
        """발주 엑셀을 생성하고 저장 경로를 반환합니다."""
        raise NotImplementedError
