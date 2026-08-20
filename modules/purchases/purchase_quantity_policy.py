from __future__ import annotations

import re
from typing import Any


CHANNEL_TOTAL_PLATFORMS = frozenset({"gmarket", "auction"})


def quantity_semantics(platform: Any) -> str:
    normalized = str(platform or "").strip().casefold()
    if normalized in CHANNEL_TOTAL_PLATFORMS:
        return "channel_total"
    return "option_multiplier"


def option_unit_multiplier(option_name: Any) -> int:
    if option_name in (None, ""):
        return 1

    text = str(option_name).strip()
    if not text:
        return 1

    patterns = (
        r"(?<!\d)(\d+)\s*(?:개|팩|봉|박스|세트)\s*입\b",
        r"(?<!\d)(\d+)\s*(?:개|팩|봉|박스|세트)(?![가-힣])",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is not None:
            value = int(match.group(1))
            if value > 0:
                return value
    return 1


def calculate_purchase_quantity(
    order_quantity: Any,
    option_name: Any,
    *,
    platform: Any = None,
) -> int:
    try:
        base_quantity = int(order_quantity or 1)
    except (TypeError, ValueError):
        base_quantity = 1

    if base_quantity <= 0:
        base_quantity = 1

    if quantity_semantics(platform) == "channel_total":
        return base_quantity

    return base_quantity * option_unit_multiplier(option_name)
