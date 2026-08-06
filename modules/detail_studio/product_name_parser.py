from __future__ import annotations

import re
from typing import Any


OPTION_PATTERNS = [
    r"\b\d+(?:\.\d+)?\s*(?:kg|g|ml|l)\b",
    r"\b\d+\s*(?:미|마리|과|개|팩|봉|세트)\b",
    r"\b(?:소|중|대|특대|왕특대)\b",
]


def parse_product_name(product_name: str) -> dict[str, Any]:
    original = str(product_name or "").strip()
    clean_name = original
    options: list[str] = []

    for pattern in OPTION_PATTERNS:
        matches = re.findall(
            pattern,
            clean_name,
            flags=re.IGNORECASE,
        )

        for match in matches:
            value = str(match).strip()

            if value and value not in options:
                options.append(value)

        clean_name = re.sub(
            pattern,
            " ",
            clean_name,
            flags=re.IGNORECASE,
        )

    clean_name = re.sub(r"\s+", " ", clean_name).strip()
    option_text = " ".join(options)

    return {
        "original_name": original,
        "display_name": clean_name or original,
        "option_name": option_text,
    }