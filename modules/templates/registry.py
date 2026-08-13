from __future__ import annotations

import json
from pathlib import Path

from .base import PurchaseTemplate
from .default_template import DefaultPurchaseTemplate
from .summary_only_template import SummaryOnlyPurchaseTemplate
from .haedam_template import HaedamPurchaseTemplate


TEMPLATE_CLASSES: dict[str, type[PurchaseTemplate]] = {
    DefaultPurchaseTemplate.template_key: DefaultPurchaseTemplate,
    SummaryOnlyPurchaseTemplate.template_key: SummaryOnlyPurchaseTemplate,
    HaedamPurchaseTemplate.template_key: HaedamPurchaseTemplate,
}

CONFIG_PATH = Path(__file__).with_name(
    "supplier_template_map.json"
)


def _load_supplier_template_map() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        return {}

    try:
        data = json.loads(
            CONFIG_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    return {
        str(supplier_name).strip(): str(template_key).strip()
        for supplier_name, template_key in data.items()
        if str(supplier_name).strip()
        and str(template_key).strip()
    }


def get_purchase_template(
    supplier_name: str,
) -> PurchaseTemplate:
    """
    공급처명에 연결된 양식을 반환합니다.

    supplier_template_map.json에 등록되지 않은 공급처는
    항상 기본 발주서를 사용합니다.
    """

    supplier_map = _load_supplier_template_map()
    template_key = supplier_map.get(
        str(supplier_name or "").strip(),
        "default",
    )

    template_class = TEMPLATE_CLASSES.get(
        template_key,
        DefaultPurchaseTemplate,
    )

    return template_class()
