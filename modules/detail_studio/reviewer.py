from __future__ import annotations

import re
from typing import Any

from .brand_voice import get_brand_voice


class DetailReviewer:
    def __init__(self) -> None:
        self.voice = get_brand_voice()

    def review_section(
        self,
        title: str,
        body: str,
        product: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        title = self.clean_text(title)
        body = self.clean_text(body)

        title, body = self.remove_avoid_words(title, body)
        body = self.remove_duplicate_lines(body)
        body = self.normalize_line_length(body)

        score = self.calculate_score(
            title=title,
            body=body,
            product=product,
        )

        return title, body, score

    def remove_avoid_words(
        self,
        title: str,
        body: str,
    ) -> tuple[str, str]:
        replacements = {
            "최고의": "좋은",
            "최상의": "좋은",
            "최상급": "품질 좋은",
            "무조건": "",
            "역대급": "",
            "인생상품": "",
            "압도적": "",
            "100%": "",
            "절대": "",
            "대박": "",
            "미친": "",
        }

        for old, new in replacements.items():
            title = title.replace(old, new)
            body = body.replace(old, new)

        for word in self.voice.get("avoid_words", []):
            title = title.replace(word, "")
            body = body.replace(word, "")

        return self.clean_text(title), self.clean_text(body)

    @staticmethod
    def remove_duplicate_lines(body: str) -> str:
        lines = body.splitlines()
        result: list[str] = []
        seen: set[str] = set()

        for line in lines:
            normalized = line.strip()

            if not normalized:
                if result and result[-1] != "":
                    result.append("")
                continue

            if normalized in seen:
                continue

            seen.add(normalized)
            result.append(normalized)

        return "\n".join(result).strip()

    @staticmethod
    def normalize_line_length(
        body: str,
        max_length: int = 38,
    ) -> str:
        result: list[str] = []

        for line in body.splitlines():
            line = line.strip()

            if not line:
                result.append("")
                continue

            if len(line) <= max_length:
                result.append(line)
                continue

            parts = re.split(r"(?<=[,.!?])\s+|\s+", line)
            current = ""

            for part in parts:
                candidate = f"{current} {part}".strip()

                if len(candidate) <= max_length:
                    current = candidate
                else:
                    if current:
                        result.append(current)
                    current = part

            if current:
                result.append(current)

        return "\n".join(result).strip()

    def calculate_score(
        self,
        title: str,
        body: str,
        product: dict[str, Any],
    ) -> dict[str, Any]:
        name = str(product.get("product_name") or "").strip()
        full_text = f"{title}\n{body}"

        avoid_count = sum(
            full_text.count(word)
            for word in self.voice.get("avoid_words", [])
        )

        brand_score = max(0, 100 - avoid_count * 20)

        if avoid_count:
            issues.append(
                f"금지어 {avoid_count}회 사용"
            )

        readability_score = 100

        for line in body.splitlines():
            if len(line) > 45:
                readability_score -= 5
                issues.append(
                f"긴 문장({len(line)}자)"
            )

        readability_score = max(0, readability_score)

        seo_score = 100 if not name or name in full_text else 70

        if name and name not in full_text:
            issues.append("상품명이 본문에 없음")

        issues: list[str] = []

        trust_words = [
            "선별",
            "확인",
            "상태",
            "품질",
            "신선도",
            "원물",
            "산지",
        ]

        trust_count = sum(
            1 for word in trust_words if word in full_text
        )

        trust_score = min(100, 70 + trust_count * 5)

        if trust_count < 3:
            issues.append(
            "신뢰 키워드 부족"
            )

        total_score = round(
            (
                brand_score
                + readability_score
                + seo_score
                + trust_score
            )
            / 4
        )

        return {
            "total": total_score,
            "brand": brand_score,
            "readability": readability_score,
            "seo": seo_score,
            "trust": trust_score,
            "issues": issues,
        }

    @staticmethod
    def clean_text(text: str) -> str:
        text = str(text or "")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()