from __future__ import annotations

from collections import Counter
from typing import Any

from .models import ValidationIssue

DEFAULT_MAX_QUANTITY = 100
NORMAL_MAPPING_STATUSES = {"자동매핑", "수동매핑", "매핑완료"}


def validate_order(order: dict[str, Any]) -> list[ValidationIssue]:
    """발주 전 반드시 확인할 실무 조건만 검사합니다."""
    items = list(order.get("items") or [])
    if not items:
        return [ValidationIssue(
            rule_code="ORDER_NO_ITEMS",
            level="FAIL",
            title="주문상품 없음",
            message="주문에 등록된 상품이 없습니다.",
        )]

    issues = _validate_duplicate_items(items)
    for item in items:
        issues.extend(_validate_item(item))
    return issues


def _validate_item(item: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    item_id = _to_optional_int(item.get("id") or item.get("order_item_id"))
    product_name = _text(item.get("platform_product_name") or item.get("product_name")) or "상품명 없음"
    product_id = _to_optional_int(item.get("product_id"))
    supplier_id = _to_optional_int(item.get("supplier_id"))
    mapping_status = _text(item.get("mapping_status"))
    option_name = _text(item.get("option_name"))
    quantity = _to_int(item.get("quantity"))

    if not product_id:
        issues.append(ValidationIssue(
            rule_code="PRODUCT_NOT_MAPPED",
            level="FAIL",
            title="상품 미매핑",
            message=f"'{product_name}' 상품이 ERP 상품과 연결되지 않았습니다.",
            order_item_id=item_id,
            field_name="product_id",
            current_value=item.get("product_id"),
        ))
    elif mapping_status not in NORMAL_MAPPING_STATUSES:
        issues.append(ValidationIssue(
            rule_code="MAPPING_STATUS_INVALID",
            level="FAIL",
            title="매핑 상태 오류",
            message=f"'{product_name}' 상품의 매핑 상태가 '{mapping_status or '없음'}'입니다.",
            order_item_id=item_id,
            field_name="mapping_status",
            current_value=mapping_status,
        ))

    if not supplier_id:
        issues.append(ValidationIssue(
            rule_code="SUPPLIER_NOT_CONNECTED",
            level="FAIL",
            title="공급처 미연결",
            message=f"'{product_name}' 상품에 공급처가 연결되지 않았습니다.",
            order_item_id=item_id,
            field_name="supplier_id",
            current_value=item.get("supplier_id"),
        ))

    if quantity <= 0:
        issues.append(ValidationIssue(
            rule_code="QUANTITY_INVALID",
            level="FAIL",
            title="수량 오류",
            message=f"'{product_name}' 주문수량은 1개 이상이어야 합니다.",
            order_item_id=item_id,
            field_name="quantity",
            current_value=item.get("quantity"),
        ))
    elif quantity > DEFAULT_MAX_QUANTITY:
        issues.append(ValidationIssue(
            rule_code="QUANTITY_HIGH",
            level="WARNING",
            title="수량 확인 필요",
            message=f"'{product_name}' 주문수량이 {quantity:,}개입니다. 실제 주문이 맞는지 확인하세요.",
            order_item_id=item_id,
            field_name="quantity",
            current_value=quantity,
        ))

    if not option_name:
        issues.append(ValidationIssue(
            rule_code="OPTION_EMPTY",
            level="WARNING",
            title="옵션 없음",
            message=f"'{product_name}' 상품의 옵션명이 비어 있습니다. 단일상품이면 그대로 진행할 수 있습니다.",
            order_item_id=item_id,
            field_name="option_name",
            current_value="",
        ))

    return issues


def _validate_duplicate_items(items: list[dict[str, Any]]) -> list[ValidationIssue]:
    keys = [(
        _normalize(item.get("platform_product_name")),
        _normalize(item.get("option_name")),
        _to_int(item.get("quantity")),
    ) for item in items]
    duplicates = {key for key, count in Counter(keys).items() if key[0] and count > 1}
    issues: list[ValidationIssue] = []
    for item, key in zip(items, keys):
        if key in duplicates:
            issues.append(ValidationIssue(
                rule_code="DUPLICATE_ITEM",
                level="WARNING",
                title="중복 상품 확인",
                message="같은 주문 안에 동일한 상품·옵션·수량이 두 번 이상 들어 있습니다.",
                order_item_id=_to_optional_int(item.get("id") or item.get("order_item_id")),
            ))
    return issues


def _normalize(value: Any) -> str:
    return "".join(_text(value).lower().split())


def _text(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _to_optional_int(value: Any) -> int | None:
    number = _to_int(value)
    return number if number > 0 else None
