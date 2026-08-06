from __future__ import annotations

import hashlib
from typing import Any


PLAYBOOK_LIBRARY: dict[str, dict[str, list[str]]] = {
    "품질": {
        "hooks": [
            "좋은 {name}은 첫입부터 다릅니다.",
            "판매보다 선별을 먼저 생각한 {name}",
            "기본부터 제대로 준비한 {name}",
        ],
        "usps": [
            "상태와 선별 기준을 먼저 확인했습니다.",
            "판매보다 상품의 기본 품질을 먼저 살폈습니다.",
            "좋은 상태의 상품만 소개합니다.",
        ],
        "ctas": [
            "좋은 상품은 결국 다시 찾게 됩니다.",
            "제대로 고른 {name}을 만나보세요.",
            "오늘 식탁에 좋은 {name}을 준비해 보세요.",
        ],
    },
    "희소성": {
        "hooks": [
            "지금 아니면 만나기 어려운 {name}",
            "쉽게 만날 수 없는 {name}",
            "준비된 수량만 소개하는 {name}",
        ],
        "usps": [
            "쉽게 만날 수 없는 상품입니다.",
            "좋은 상태로 준비되는 시기와 수량이 한정적입니다.",
            "희소성과 상품 상태를 함께 확인해 선별했습니다.",
        ],
        "ctas": [
            "준비된 수량만 판매합니다.",
            "좋은 상태로 준비됐을 때 만나보세요.",
            "지금 준비된 {name}을 확인해 보세요.",
        ],
    },
    "제철": {
        "hooks": [
            "가장 맛있는 지금, {name}",
            "제철의 맛이 살아 있는 {name}",
            "좋은 시기를 놓치지 않은 {name}",
        ],
        "usps": [
            "가장 맛있는 시기에 맞춰 준비했습니다.",
            "제철의 맛과 식감을 제대로 즐길 수 있습니다.",
            "좋은 시기와 좋은 상태를 함께 확인했습니다.",
        ],
        "ctas": [
            "제철은 기다려주지 않습니다.",
            "가장 맛있는 지금 만나보세요.",
            "제철의 {name}을 오늘 식탁에 준비해 보세요.",
        ],
    },
    "신선도": {
        "hooks": [
            "오늘 준비한 {name}",
            "신선함부터 다른 {name}",
            "좋은 상태로 빠르게 보내드리는 {name}",
        ],
        "usps": [
            "입고와 출고 흐름을 확인해 신선하게 준비합니다.",
            "상품 상태를 확인한 뒤 빠르게 출고합니다.",
            "신선도 유지를 고려해 포장하고 출고합니다.",
        ],
        "ctas": [
            "가장 신선할 때 받아보세요.",
            "좋은 상태의 {name}을 만나보세요.",
            "신선함이 살아 있을 때 즐겨보세요.",
        ],
    },
    "프리미엄": {
        "hooks": [
            "한 단계 더 꼼꼼하게 고른 {name}",
            "선별 기준부터 다른 {name}",
            "좋은 날을 위한 {name}",
        ],
        "usps": [
            "상품 상태와 구성 기준을 꼼꼼하게 확인했습니다.",
            "선물과 특별한 식탁에 어울리도록 엄선했습니다.",
            "가격보다 만족도를 먼저 생각해 선별했습니다.",
        ],
        "ctas": [
            "좋은 선택이 필요한 날 준비해 보세요.",
            "정성껏 고른 {name}을 만나보세요.",
            "특별한 식탁을 위한 {name}을 선택해 보세요.",
        ],
    },
    "수율": {
        "hooks": [
            "살이 꽉 찬 {name}",
            "수율부터 다른 {name}",
            "껍데기보다 속이 중요한 {name}",
            "먹을 것이 제대로 들어찬 {name}",
        ],
        "usps": [
            "몸통과 다리의 실제 먹을 수 있는 살을 기준으로 확인합니다.",
            "실제 먹을 수 있는 살의 만족도를 먼저 생각했습니다.",
            "살이 부족한 상품은 선별 단계에서 제외합니다.",
            "크기보다 속살의 만족도를 먼저 확인합니다.",
        ],
        "ctas": [
            "수율 좋은 {name}을 경험해 보세요.",
            "속이 제대로 찬 {name}을 만나보세요.",
            "껍데기보다 먹을 것이 많은 상품을 선택하세요.",
            "준비된 좋은 수율의 {name}을 만나보세요.",
        ],
    },
    "알배기": {
        "hooks": [
            "알이 꽉 찬 {name}",
            "제철 알의 고소함을 담은 {name}",
            "속까지 제대로 확인한 {name}",
        ],
        "usps": [
            "알 상태와 상품 컨디션을 함께 확인해 선별합니다.",
            "알의 상태와 살의 만족도를 함께 살폈습니다.",
            "좋은 시기에 준비된 상품을 엄선합니다.",
        ],
        "ctas": [
            "지금이 가장 맛있는 시기입니다.",
            "알이 좋은 시기에 만나보세요.",
            "제철의 진한 맛을 즐겨보세요.",
        ],
    },
    "보양": {
        "hooks": [
            "기력 채우는 {name}",
            "든든한 한 끼를 위한 {name}",
            "맛과 든든함을 함께 챙긴 {name}",
        ],
        "usps": [
            "든든한 한 끼로 즐기기 좋은 상품입니다.",
            "손질과 조리가 편하도록 상품 정보를 꼼꼼히 안내합니다.",
            "가족 식사와 보양식으로 활용하기 좋습니다.",
        ],
        "ctas": [
            "오늘 든든한 한 끼를 준비하세요.",
            "가족을 위한 {name}을 준비해 보세요.",
            "맛있고 든든한 식탁을 완성해 보세요.",
        ],
    },
    "자연산": {
        "hooks": [
            "자연 그대로의 {name}",
            "자연산의 풍미를 담은 {name}",
            "바다와 산지가 키운 {name}",
        ],
        "usps": [
            "자연산 특유의 식감과 풍미를 즐길 수 있습니다.",
            "채취와 조업 환경에 따라 달라지는 자연의 맛을 담았습니다.",
            "자연물 특성을 고려해 상태를 확인하고 선별합니다.",
        ],
        "ctas": [
            "자연산의 차이를 느껴보세요.",
            "자연이 만든 맛을 식탁에서 만나보세요.",
            "좋은 상태로 준비된 {name}을 만나보세요.",
        ],
    },
    "당일조업": {
        "hooks": [
            "오늘 조업한 {name}",
            "조업의 신선함을 담은 {name}",
            "산지에서 빠르게 준비한 {name}",
        ],
        "usps": [
            "조업과 입고 흐름을 확인해 빠르게 출고합니다.",
            "산지에서 준비된 상품을 신선도에 맞춰 포장합니다.",
            "좋은 상태를 유지할 수 있도록 출고 과정을 관리합니다.",
        ],
        "ctas": [
            "신선할 때 받아보세요.",
            "산지의 신선함을 빠르게 만나보세요.",
            "오늘 준비된 {name}을 확인해 보세요.",
        ],
    },
    "당도": {
        "hooks": [
            "한입에 퍼지는 달콤함, {name}",
            "당도와 향이 좋은 {name}",
            "기분 좋은 단맛을 담은 {name}",
        ],
        "usps": [
            "맛과 향, 과육 상태를 함께 확인해 선별합니다.",
            "기분 좋은 단맛을 즐길 수 있는 과일을 엄선합니다.",
            "크기보다 실제 맛의 만족도를 먼저 생각합니다.",
        ],
        "ctas": [
            "달콤한 제철 과일을 만나보세요.",
            "한입 가득 좋은 단맛을 즐겨보세요.",
            "오늘 가장 맛있는 {name}을 준비해 보세요.",
        ],
    },
}


class PlaybookEngine:
    DEFAULT_SECTION_PRIORITY = [
        "brand_intro", "hero", "why_now", "usp", "origin",
        "selection", "taste", "how_to", "prep", "option",
        "packing", "notice", "cs", "quality", "cta",
    ]

    STRATEGY_SECTIONS = {
        "수율": [
            "brand_intro", "hero", "usp", "selection", "taste",
            "origin", "how_to", "prep", "option", "packing",
            "notice", "cs", "quality", "cta",
        ],
        "알배기": [
            "brand_intro", "hero", "why_now", "taste", "usp",
            "selection", "origin", "how_to", "prep", "option",
            "packing", "notice", "cs", "quality", "cta",
        ],
        "보양": [
            "brand_intro", "hero", "usp", "how_to", "taste",
            "origin", "selection", "prep", "option", "packing",
            "notice", "cs", "quality", "cta",
        ],
        "당일조업": [
            "brand_intro", "hero", "origin", "packing", "taste",
            "usp", "selection", "how_to", "prep", "option",
            "notice", "cs", "quality", "cta",
        ],
        "당도": [
            "brand_intro", "hero", "taste", "selection", "origin",
            "why_now", "usp", "how_to", "prep", "option",
            "packing", "notice", "cs", "quality", "cta",
        ],
    }

    @staticmethod
    def stable_choice(items: list[str], key: str) -> str:
        if not items:
            return ""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % len(items)
        return items[index]

    @staticmethod
    def _value(data: dict[str, Any], key: str) -> str:
        return str(data.get(key) or "").strip()

    def _detect_strategy(
        self,
        product: dict[str, Any],
        interview: dict[str, Any],
    ) -> str:
        name = (
            self._value(product, "display_name")
            or self._value(product, "product_name")
        )

        dna = self._value(product, "product_dna")

        axis = str(
            interview.get("main_sales_axis")
            or product.get("sales_axis")
            or product.get("main_sales_axis")
            or ""
        ).strip()

        axis_map = {
            "맛·식감": "품질",
            "가격·가성비": "품질",
            "희소성": "희소성",
            "제철성": "제철",
            "선물·고급감": "프리미엄",
        }
        if axis in axis_map:
            return axis_map[axis]

        strategy_rules = [
            ("수율", ["홍게", "대게"]),
            ("알배기", ["꽃게"]),
            ("보양", ["장어"]),
            ("자연산", ["굴", "고동", "소라", "전복"]),
            ("당일조업", ["멸치", "방어", "오징어"]),
            ("당도", ["사과", "복숭아", "배", "포도", "한라봉", "감귤"]),
        ]
        for strategy, keywords in strategy_rules:
            if any(keyword in name for keyword in keywords):
                return strategy

        dna_rules = [
            ("자연산", "자연산"),
            ("제철", "제철"),
            ("당일조업", "당일조업"),
            ("당일", "신선도"),
            ("프리미엄", "프리미엄"),
            ("희소", "희소성"),
            ("고당도", "당도"),
            ("당도", "당도"),
        ]
        for keyword, strategy in dna_rules:
            if keyword in dna:
                return strategy

        return "품질"

def build(
    self,
    product: dict[str, Any],
    interview: dict[str, Any] | None = None,
    brand: dict[str, Any] | None = None,
) -> dict[str, Any]:
    interview = interview or {}
    brand = brand or {}

    name = (
        self._value(product, "display_name")
        or self._value(product, "product_name")
        or "상품"
    )

    dna = self._value(product, "product_dna")

    strategy = (
        self._value(product, "strategy")
        or self._value(product, "sales_strategy")
        or self._detect_strategy(product, interview)
    )

    library = PLAYBOOK_LIBRARY.get(strategy)
    if library is None:
        library = PLAYBOOK_LIBRARY["품질"]

    selection_key = " | ".join([
        name,
        dna,
        self._value(product, "origin"),
        self._value(product, "key_point"),
        self._value(product, "taste_texture"),
        strategy,
    ])

    hook = self.stable_choice(
        library["hooks"],
        selection_key + "|hook",
    ).format(name=name)

    usp = self.stable_choice(
        library["usps"],
        selection_key + "|usp",
    ).format(name=name)

    cta = self.stable_choice(
        library["ctas"],
        selection_key + "|cta",
    ).format(name=name)

    section_priority = self.STRATEGY_SECTIONS.get(
        strategy,
        list(self.DEFAULT_SECTION_PRIORITY),
    )

    checks = {
        "origin": "원산지",
        "key_point": "핵심 장점",
        "taste_texture": "맛·식감",
        "usage_text": "먹는 방법",
        "shipping_text": "배송 안내",
        "customer_worries": "고객 불안 요소",
    }

    missing = [
        label
        for field, label in checks.items()
        if not self._value(product, field)
    ]

    weights = {
        "origin": 8,
        "key_point": 12,
        "taste_texture": 10,
        "production_story": 10,
        "usage_text": 8,
        "customer_worries": 10,
        "shipping_text": 8,
        "option_text": 6,
        "prep_text": 6,
        "caution_text": 5,
    }

    score = 100
    improvements: list[str] = []

    for field, weight in weights.items():
        if not self._value(product, field):
            score -= weight
            improvements.append(field)

    score = max(score, 0)

    if score >= 95:
        grade = "S"
    elif score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    else:
        grade = "D"

    diagnosis = {
        "trust": 100,
        "purchase": 100,
        "scarcity": 100,
        "seo": 40,
        "conversion": 100,
    }

    trust_fields = {
        "origin": 25,
        "production_story": 25,
        "shipping_text": 20,
        "caution_text": 15,
        "option_text": 15,
    }

    purchase_fields = {
        "key_point": 25,
        "taste_texture": 25,
        "usage_text": 20,
        "why_now": 15,
        "cta_text": 15,
    }

    conversion_fields = {
        "customer_worries": 25,
        "key_point": 20,
        "option_text": 20,
        "shipping_text": 20,
        "cta_text": 15,
    }

    for field, weight in trust_fields.items():
        if not self._value(product, field):
            diagnosis["trust"] -= weight

    for field, weight in purchase_fields.items():
        if not self._value(product, field):
            diagnosis["purchase"] -= weight

    for field, weight in conversion_fields.items():
        if not self._value(product, field):
            diagnosis["conversion"] -= weight

    scarcity_keywords = [
        "제철",
        "자연산",
        "당일",
        "한정",
        "희소",
        "산지",
        "조업",
        "알배기",
    ]

    scarcity_text = " ".join([
        name,
        dna,
        self._value(product, "why_now"),
        self._value(product, "production_story"),
        self._value(product, "key_point"),
    ])

    matched_scarcity = sum(
        1
        for keyword in scarcity_keywords
        if keyword in scarcity_text
    )

    diagnosis["scarcity"] = min(
        100,
        40 + matched_scarcity * 12,
    )

    seo_fields = [
        "product_name",
        "category",
        "origin",
        "key_point",
        "taste_texture",
        "usage_text",
    ]

    for field in seo_fields:
        if self._value(product, field):
            diagnosis["seo"] += 10

    for key in diagnosis:
        diagnosis[key] = max(
            0,
            min(100, diagnosis[key]),
        )

    feedback: list[str] = []

    if diagnosis["trust"] < 80:
        feedback.append(
            "원산지, 생산과정, 배송 안내를 구체적인 사실 중심으로 보강하세요."
        )

    if diagnosis["purchase"] < 80:
        feedback.append(
            "맛과 식감, 핵심 장점을 더 구체적으로 작성하세요."
        )

    if diagnosis["scarcity"] < 80:
        feedback.append(
            "제철, 자연산, 한정수량, 당일조업 등 실제 희소성 근거를 추가하세요."
        )

    if diagnosis["seo"] < 80:
        feedback.append(
            "상품명, 원산지, 핵심 키워드를 충분히 입력하세요."
        )

    if diagnosis["conversion"] < 80:
        feedback.append(
            "고객이 망설이는 이유와 구매 근거를 보강하세요."
        )

    if not feedback:
        feedback.append(
            "현재 상품 정보가 판매 콘텐츠 생성에 충분합니다."
        )

    return {
        "strategy": strategy,
        "hook": hook,
        "usp": usp,
        "cta": cta,
        "section_priority": section_priority,
        "missing": missing,
        "score": score,
        "improvements": improvements,
        "grade": grade,
        "diagnosis": diagnosis,
        "feedback": feedback,
        "brand_name": str(
            brand.get("brand_name") or "비선상회"
        ),
    }