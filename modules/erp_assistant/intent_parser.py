from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class AssistantIntent(str, Enum):
    TODAY_ORDER_COUNT = "TODAY_ORDER_COUNT"
    UNMAPPED_ORDERS = "UNMAPPED_ORDERS"
    PURCHASE_PENDING = "PURCHASE_PENDING"
    SHIPMENT_PENDING = "SHIPMENT_PENDING"
    SHIPPING_ORDERS = "SHIPPING_ORDERS"
    SUPPLIER_PURCHASE_AMOUNT = "SUPPLIER_PURCHASE_AMOUNT"
    TODAY_PURCHASES = "TODAY_PURCHASES"
    MISSING_TRACKING = "MISSING_TRACKING"
    PRODUCT_ORDER_SEARCH = "PRODUCT_ORDER_SEARCH"
    ORDER_NUMBER_SEARCH = "ORDER_NUMBER_SEARCH"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class ParsedQuestion:
    intent: AssistantIntent
    search_term: str = ""


class KoreanIntentParser:
    """Deterministic parser for supported Korean operational questions."""

    _TRAILING_WORDS = re.compile(
        r"(?:주문)?\s*(?:검색|조회|찾아줘|찾아|보여줘|보여\s*줘|알려줘|알려\s*줘)\s*[?.!]*$"
    )

    def parse(self, question: str) -> ParsedQuestion:
        text = re.sub(r"\s+", " ", str(question or "").strip())
        if not text:
            return ParsedQuestion(AssistantIntent.UNSUPPORTED)
        if "오늘" in text and "주문" in text and any(
            token in text for token in ("몇 건", "몇건", "건수")
        ):
            return ParsedQuestion(AssistantIntent.TODAY_ORDER_COUNT)
        if "미매핑" in text:
            return ParsedQuestion(AssistantIntent.UNMAPPED_ORDERS)
        if "발주 대기" in text or "발주대기" in text:
            return ParsedQuestion(AssistantIntent.PURCHASE_PENDING)
        if "송장 대기" in text or "송장대기" in text:
            return ParsedQuestion(AssistantIntent.SHIPMENT_PENDING)
        if "배송중" in text and "주문" in text:
            return ParsedQuestion(AssistantIntent.SHIPPING_ORDERS)
        if "공급처별" in text and "발주" in text and "금액" in text:
            return ParsedQuestion(AssistantIntent.SUPPLIER_PURCHASE_AMOUNT)
        if "오늘" in text and "발주" in text and "내역" in text:
            return ParsedQuestion(AssistantIntent.TODAY_PURCHASES)
        if "송장번호" in text and any(token in text for token in ("없는", "없음", "미등록")):
            return ParsedQuestion(AssistantIntent.MISSING_TRACKING)

        term = self._extract_after(text, "주문번호")
        if term:
            return ParsedQuestion(AssistantIntent.ORDER_NUMBER_SEARCH, term)
        term = self._extract_after(text, "상품명") or self._extract_before(text, "상품 주문")
        if term:
            return ParsedQuestion(AssistantIntent.PRODUCT_ORDER_SEARCH, term)
        return ParsedQuestion(AssistantIntent.UNSUPPORTED)

    def _extract_after(self, text: str, label: str) -> str:
        match = re.search(rf"{re.escape(label)}\s*[:：]?\s*(.+)$", text)
        return self._clean(match.group(1)) if match else ""

    def _extract_before(self, text: str, label: str) -> str:
        match = re.search(rf"^(.+?)\s*{re.escape(label)}", text)
        return self._clean(match.group(1)) if match else ""

    def _clean(self, value: str) -> str:
        return self._TRAILING_WORDS.sub("", value).strip(" \t?.!\"'")
