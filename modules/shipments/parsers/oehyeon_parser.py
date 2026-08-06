from __future__ import annotations

from pathlib import Path
from typing import Any

from .base_parser import BaseShipmentParser


class OehyeonShipmentParser(BaseShipmentParser):
    """
    외현농원 전용 파서 자리입니다.

    실제 회신 엑셀의 헤더와 송장 열 위치를 확인한 뒤 활성화합니다.
    잘못된 자동판별을 막기 위해 현재 detect()는 항상 False입니다.
    """

    parser_key = "oehyeon"
    display_name = "외현농원 회신 발주서"
    supplier_name = "외현농원"

    def detect(self, file_path: str | Path) -> bool:
        return False

    def parse(self, file_path: str | Path) -> dict[str, Any]:
        raise ValueError(
            "외현농원 송장양식은 아직 열 구성이 등록되지 않았습니다.\n"
            "외현농원에서 회신한 실제 엑셀 한 개가 필요합니다."
        )
