from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ProductDictionary:
    """
    상품명 비교 전에 동의어, 표현 차이, 불필요 문구를 정리합니다.

    주의:
    - 짧은 단어는 다른 단어 내부에서 오작동하지 않도록 토큰 단위로 처리합니다.
    - 실제 상품 구분에 필요한 중량, 수량, 규격 숫자는 제거하지 않습니다.
    """

    synonyms: dict[str, str] = field(
        default_factory=lambda: {
            # 원산지
            "국산": "국내산",
            "한국산": "국내산",

            # 보관·상태
            "활어": "생물",
            "활": "생물",
            "생": "생물",
            "냉장": "생물",
            "급냉": "냉동",
            "동결": "냉동",

            # 용도
            "횟감": "회용",
            "회감": "회용",
            "회용도": "회용",

            # 크기·규격
            "특대": "xl",
            "왕특대": "xxl",
            "초특대": "xxl",
            "대": "대자",
            "중": "중자",
            "소": "소자",

            # 손질
            "손질완료": "완전손질",
            "손질": "완전손질",
            "가공완료": "완전손질",

            # 포장·형태
            "필렛형": "필렛",
            "포장팩": "팩",
        }
    )

    removable_phrases: tuple[str, ...] = (
        "무료배송",
        "당일출고",
        "당일발송",
        "산지직송",
        "최상급",
        "프리미엄",
        "특가",
        "한정판매",
        "주문폭주",
        "인기상품",
        "추천상품",
        "초장증정",
        "초장 증정",
        "증정",
    )

    def normalize(self, value: str | None) -> str:
        text = str(value or "").strip().lower()

        if not text:
            return ""

        text = self._normalize_units(text)
        text = self._remove_noise(text)
        text = self._separate_tokens(text)
        text = self._apply_synonyms(text)
        text = self._cleanup(text)

        return text

    def _normalize_units(self, text: str) -> str:
        replacements = (
            (r"(\d+(?:\.\d+)?)\s*킬로그램", r"\1kg"),
            (r"(\d+(?:\.\d+)?)\s*키로", r"\1kg"),
            (r"(\d+(?:\.\d+)?)\s*kg", r"\1kg"),
            (r"(\d+(?:\.\d+)?)\s*그램", r"\1g"),
            (r"(\d+(?:\.\d+)?)\s*g", r"\1g"),
            (r"(\d+)\s*개입", r"\1개"),
            (r"(\d+)\s*마리", r"\1미"),
            (r"(\d+)\s*팩입", r"\1팩"),
        )

        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)

        return text

    def _remove_noise(self, text: str) -> str:
        for phrase in sorted(
            self.removable_phrases,
            key=len,
            reverse=True,
        ):
            text = text.replace(phrase.lower(), " ")

        text = re.sub(r"\b100\s*%\b", " ", text)
        return text

    def _separate_tokens(self, text: str) -> str:
        text = re.sub(r"([가-힣a-z])(\d)", r"\1 \2", text)
        text = re.sub(r"(\d)([가-힣a-z])", r"\1 \2", text)
        text = re.sub(r"[/|,+_\-·]", " ", text)
        text = re.sub(r"[()\[\]{}<>]", " ", text)
        return text

    def _apply_synonyms(self, text: str) -> str:
        tokens = text.split()
        normalized_tokens: list[str] = []

        for token in tokens:
            normalized_tokens.append(
                self.synonyms.get(token, token)
            )

        return " ".join(normalized_tokens)

    @staticmethod
    def _cleanup(text: str) -> str:
        text = re.sub(r"[^0-9a-z가-힣.%]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def add_synonym(
        self,
        source: str,
        target: str,
    ) -> None:
        source_key = self.normalize(source)
        target_value = self.normalize(target)

        if not source_key:
            raise ValueError("동의어 원문이 비어 있습니다.")

        if not target_value:
            raise ValueError("동의어 변환값이 비어 있습니다.")

        self.synonyms[source_key] = target_value