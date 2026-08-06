from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .normalizer import ProductNameNormalizer


@dataclass
class ParsedProduct:

    original: str

    normalized: str

    name: str

    weight: Optional[int]

    weight_unit: str

    quantity: Optional[int]

    quantity_unit: str

    option: str


class ProductParser:

    WEIGHT_PATTERN = re.compile(
        r'(\d+(?:\.\d+)?)\s*(g|kg|ml|l)',
        re.IGNORECASE
    )

    COUNT_PATTERN = re.compile(
        r'(\d+)\s*(팩|세트|봉|개|미|박스)',
        re.IGNORECASE
    )

    OPTION_PATTERN = re.compile(
        r'(특대|대|중|소|L|M|S|XL|XXL)',
        re.IGNORECASE
    )

    def __init__(self):

        self.normalizer = ProductNameNormalizer()

    def parse(self, product_name: str) -> ParsedProduct:

        normalized = self.normalizer.normalize_string(product_name)

        weight = None
        weight_unit = ""

        quantity = None
        quantity_unit = ""

        option = ""

        name = normalized

        m = self.WEIGHT_PATTERN.search(normalized)

        if m:

            value = float(m.group(1))
            unit = m.group(2).lower()

            if unit == "kg":
                value *= 1000
                unit = "g"

            elif unit == "l":
                value *= 1000
                unit = "ml"

            weight = int(value)
            weight_unit = unit

            name = name.replace(m.group(0), "")

        c = self.COUNT_PATTERN.search(normalized)

        if c:

            quantity = int(c.group(1))
            quantity_unit = c.group(2)

            name = name.replace(c.group(0), "")

        o = self.OPTION_PATTERN.search(normalized)

        if o:

            option = o.group(1)

            name = name.replace(option, "")

        name = re.sub(r"\s+", " ", name).strip()

        return ParsedProduct(

            original=product_name,

            normalized=normalized,

            name=name,

            weight=weight,

            weight_unit=weight_unit,

            quantity=quantity,

            quantity_unit=quantity_unit,

            option=option,
        )