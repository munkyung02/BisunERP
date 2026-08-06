from __future__ import annotations

from typing import Any


CATEGORY_KEYWORDS = {
    "홍게": [
        "홍게",
        "자숙 홍게",
        "자숙홍게",
        "붉은대게",
    ],
    "대게": [
        "대게",
        "박달대게",
    ],
    "민어": [
        "민어",
        "민어회",
    ],
    "장어": [
        "장어",
        "민물장어",
        "자포니카",
    ],
    "갑오징어": [
        "갑오징어",
        "갑오징어회",
    ],
    "오징어": [
        "오징어",
        "한치",
    ],
    "문어": [
        "문어",
        "자숙문어",
        "돌문어",
    ],
    "전복": [
        "전복",
        "활전복",
    ],
    "굴": [
        "굴",
        "바위굴",
        "석화",
        "각굴",
    ],
    "멸치": [
        "멸치",
        "생멸치",
        "횟감멸치",
    ],
    "한라봉": [
        "한라봉",
    ],
    "꽃게": [
        "꽃게",
        "암꽃게",
        "활꽃게",
    ],
    "굴비": [
        "굴비",
        "보리굴비",
        "참조기",
    ],
    "소라": [
        "소라",
        "뿔소라",
    ],
    "전어": [
        "전어",
        "세꼬시",
    ],
    "방어": [
        "방어",
        "대방어",
    ],
}


GRADE_KEYWORDS = [
    "왕특대",
    "초특대",
    "특대",
    "대과",
    "중과",
    "소과",
    "대",
    "중",
    "소",
]


ORIGIN_KEYWORDS = {
    "포항": [
        "포항",
        "구룡포",
    ],
    "영덕": [
        "영덕",
        "강구항",
    ],
    "통영": [
        "통영",
    ],
    "제주": [
        "제주",
        "제주도",
        "서귀포",
    ],
    "여수": [
        "여수",
    ],
    "완도": [
        "완도",
    ],
    "군산": [
        "군산",
    ],
    "영광": [
        "영광",
        "법성포",
    ],
    "태안": [
        "태안",
        "안면도",
    ],
    "연평도": [
        "연평도",
    ],
    "남해": [
        "남해",
        "남해안",
    ],
    "동해": [
        "동해",
        "동해안",
    ],
    "서해": [
        "서해",
        "서해안",
    ],
}


def classify_product(
    product: dict[str, Any],
) -> dict[str, Any]:
    text = " ".join(
        str(product.get(key, "") or "").strip()
        for key in [
            "product_name",
            "display_name",
            "origin",
            "category",
            "product_dna",
        ]
    )

    product_dna = str(product.get("product_dna") or "")

    strategy = ""

    if category == "갑각류":
        strategy = "수율"

    elif category == "장어":
        strategy = "보양"

    elif category == "과일":
        strategy = "당도"

    elif "자연산" in product_dna:
        strategy = "자연산"

    elif "당일조업" in product_dna:
        strategy = "당일조업"

    elif "제철" in product_dna:
        strategy = "제철"

    else:
        strategy = "품질"

    product["strategy"] = strategy

    category = ""
    grade = ""
    origin = ""

    for category_name, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            category = category_name
            break

    for grade_name in GRADE_KEYWORDS:
        if grade_name in text:
            grade = grade_name
            break

    for origin_name, aliases in ORIGIN_KEYWORDS.items():
        if any(alias in text for alias in aliases):
            origin = origin_name
            break

    return {
        "category": category,
        "grade": grade,
        "origin": origin,
    }