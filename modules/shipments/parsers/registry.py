from __future__ import annotations

from pathlib import Path

from .base_parser import BaseShipmentParser
from .foodpresident_parser import FoodPresidentShipmentParser
from .haedam_parser import HaedamShipmentParser
from .juyeong_parser import JuyeongShipmentParser
from .oehyeon_parser import OehyeonShipmentParser
from .standard_parser import StandardShipmentParser


PARSER_CLASSES: list[type[BaseShipmentParser]] = [
    FoodPresidentShipmentParser,
    JuyeongShipmentParser,
    StandardShipmentParser,
    HaedamShipmentParser,
    OehyeonShipmentParser,
]


def detect_shipment_parser(
    file_path: str | Path,
) -> BaseShipmentParser:
    """엑셀 헤더를 분석해 사용할 파서를 자동으로 선택합니다."""

    detection_errors: list[str] = []

    for parser_class in PARSER_CLASSES:
        parser = parser_class()
        try:
            if parser.detect(file_path):
                return parser
        except Exception as error:
            detection_errors.append(
                f"{parser.display_name}: {error}"
            )

    detail = ""
    if detection_errors:
        detail = "\n\n판별 중 확인사항:\n" + "\n".join(
            detection_errors
        )

    raise ValueError(
        "지원하는 송장 양식을 자동으로 찾지 못했습니다.\n\n"
        "지원 양식\n"
        "1. 주문번호·택배사·송장번호 기본양식\n"
        "2. 해담 회신 발주서"
        + detail
    )


def get_supplier_parser(
    supplier_name: str,
) -> BaseShipmentParser:
    """공급처명으로 전용 파서를 반환합니다."""

    normalized = str(supplier_name or "").strip()

    for parser_class in PARSER_CLASSES:
        parser = parser_class()
        if parser.supplier_name == normalized:
            return parser

    raise ValueError(
        f"등록되지 않은 공급처 송장양식입니다: {normalized}"
    )


def get_supported_supplier_names() -> list[str]:
    """UI 공급처 선택 목록에 표시할 공급처명을 반환합니다."""

    names: list[str] = []
    for parser_class in PARSER_CLASSES:
        parser = parser_class()
        if parser.supplier_name:
            names.append(parser.supplier_name)
    return names
