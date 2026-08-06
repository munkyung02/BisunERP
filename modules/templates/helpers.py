from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def safe_filename(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "미지정"


def full_address(address: Any, detail_address: Any) -> str:
    return " ".join(
        str(value).strip()
        for value in (address, detail_address)
        if value is not None and str(value).strip()
    )


def aggregate_items(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    같은 공급처 상품코드·상품명·옵션·단가를 한 줄로 합산합니다.
    """

    grouped: dict[
        tuple[str, str, str, int],
        dict[str, Any],
    ] = {}

    for item in items:
        product_code = str(
            item.get("supplier_product_code")
            or item.get("product_code")
            or ""
        ).strip()

        product_name = str(
            item.get("supplier_product_name")
            or item.get("product_name")
            or item.get("platform_product_name")
            or ""
        ).strip()

        option_name = str(
            item.get("option_name") or ""
        ).strip()

        unit_price = int(
            item.get("unit_price") or 0
        )

        quantity = int(
            item.get(
                "purchase_quantity",
                item.get("quantity") or 0,
            )
            or 0
        )

        key = (
            product_code,
            product_name,
            option_name,
            unit_price,
        )

        bucket = grouped.setdefault(
            key,
            {
                "supplier_product_code": product_code,
                "product_name": product_name,
                "option_name": option_name,
                "unit_price": unit_price,
                "order_count": 0,
                "total_quantity": 0,
                "total_amount": 0,
            },
        )

        bucket["order_count"] += 1
        bucket["total_quantity"] += quantity
        bucket["total_amount"] += (
            unit_price * quantity
        )

    return sorted(
        grouped.values(),
        key=lambda item: (
            str(item.get("supplier_product_code") or ""),
            str(item.get("product_name") or ""),
            str(item.get("option_name") or ""),
            int(item.get("unit_price") or 0),
        ),
    )
