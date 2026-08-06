from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class NormalizedText:
    """상품명 정규화 결과."""

    original: str
    normalized: str
    compact: str
    tokens: tuple[str, ...]
    removed_words: tuple[str, ...] = field(default_factory=tuple)


class ProductNameNormalizer:
    """판매처 상품명과 ERP 상품명을 비교하기 위한 정규화 도구."""

    DEFAULT_STOP_WORDS = {
        "국내산",
        "수입산",
        "자연산",
        "양식",
        "산지직송",
        "당일배송",
        "당일발송",
        "당일출고",
        "프리미엄",
        "최고급",
        "고급",
        "특품",
        "상품",
        "정품",
        "신선",
        "싱싱한",
        "급냉",
        "냉동",
        "냉장",
        "생물",
        "횟감용",
        "횟감",
        "회용",
        "구이용",
        "찜용",
        "탕용",
        "손질완료",
        "완전손질",
        "손질",
        "무료배송",
        "초장증정",
        "초장포함",
        "증정",
        "포함",
        "한정판매",
        "특가",
        "할인",
        "추천",
    }

    SYNONYM_MAP = {
        "그램": "g",
        "그람": "g",
        "킬로그램": "kg",
        "킬로": "kg",
        "미리리터": "ml",
        "리터": "l",
        "팩입": "팩",
        "개입": "개",
        "마리": "미",
    }

    UNIT_PATTERN = re.compile(
        r"(?P<number>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>kg|kgs|킬로그램|킬로|g|그램|그람|"
        r"ml|미리리터|l|리터)",
        flags=re.IGNORECASE,
    )

    COUNT_PATTERN = re.compile(
        r"(?P<number>\d+)\s*"
        r"(?P<unit>팩|봉|세트|개|미|마리|입|박스|box)",
        flags=re.IGNORECASE,
    )

    MULTIPLY_PATTERN = re.compile(
        r"(?P<left>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>kg|g|ml|l)?\s*"
        r"[x×*]\s*"
        r"(?P<count>\d+)",
        flags=re.IGNORECASE,
    )

    SPECIAL_CHARACTER_PATTERN = re.compile(
        r"[\[\]{}()<>\-_+/\\|,:;!?~`'\"“”‘’·ㆍ★☆♥♡※]"
    )

    SPACE_PATTERN = re.compile(r"\s+")

    def __init__(
        self,
        stop_words: Iterable[str] | None = None,
        synonym_map: dict[str, str] | None = None,
    ) -> None:
        self.stop_words = set(self.DEFAULT_STOP_WORDS)

        if stop_words:
            self.stop_words.update(
                str(word).strip().lower()
                for word in stop_words
                if str(word).strip()
            )

        self.synonym_map = dict(self.SYNONYM_MAP)

        if synonym_map:
            self.synonym_map.update(
                {
                    str(source).strip().lower(): str(target).strip().lower()
                    for source, target in synonym_map.items()
                    if str(source).strip() and str(target).strip()
                }
            )

        self._stop_words_sorted = sorted(
            self.stop_words,
            key=len,
            reverse=True,
        )

    def normalize(self, value: object) -> NormalizedText:
        """상품명을 비교 가능한 형태로 변환한다."""

        original = "" if value is None else str(value).strip()

        if not original:
            return NormalizedText(
                original=original,
                normalized="",
                compact="",
                tokens=(),
                removed_words=(),
            )

        text = unicodedata.normalize("NFKC", original)
        text = text.lower()

        text = self._normalize_multiply_expression(text)
        text = self._normalize_units(text)
        text = self._normalize_count_units(text)
        text = self._replace_synonyms(text)

        text = self.SPECIAL_CHARACTER_PATTERN.sub(" ", text)
        text = self.SPACE_PATTERN.sub(" ", text).strip()

        text, removed_words = self._remove_stop_words(text)

        text = self._join_number_and_unit(text)
        text = self.SPACE_PATTERN.sub(" ", text).strip()

        tokens = tuple(
            token
            for token in text.split()
            if token
        )

        compact = re.sub(r"\s+", "", text)

        return NormalizedText(
            original=original,
            normalized=text,
            compact=compact,
            tokens=tokens,
            removed_words=tuple(removed_words),
        )

    def normalize_string(self, value: object) -> str:
        """정규화된 문자열만 반환한다."""

        return self.normalize(value).normalized

    def compact(self, value: object) -> str:
        """공백까지 제거된 비교용 문자열을 반환한다."""

        return self.normalize(value).compact

    def are_exact_match(
        self,
        left: object,
        right: object,
    ) -> bool:
        """두 상품명이 정규화 후 완전히 같은지 확인한다."""

        left_value = self.compact(left)
        right_value = self.compact(right)

        return bool(
            left_value
            and right_value
            and left_value == right_value
        )

    def _normalize_multiply_expression(self, text: str) -> str:
        """300g x 2와 같은 표현을 300g 2개 형태로 보존한다."""

        def replace(match: re.Match[str]) -> str:
            left = match.group("left")
            unit = (match.group("unit") or "").lower()
            count = match.group("count")

            normalized_unit = self.synonym_map.get(unit, unit)

            return f"{left}{normalized_unit} {count}개"

        return self.MULTIPLY_PATTERN.sub(replace, text)

    def _normalize_units(self, text: str) -> str:
        """중량과 용량 단위를 통일한다."""

        def replace(match: re.Match[str]) -> str:
            number_text = match.group("number")
            unit_text = match.group("unit").lower()

            unit_text = self.synonym_map.get(
                unit_text,
                unit_text,
            )

            try:
                number = float(number_text)
            except (TypeError, ValueError):
                return match.group(0)

            if unit_text in {"kg", "kgs"}:
                grams = number * 1000

                if grams.is_integer():
                    return f"{int(grams)}g"

                return f"{grams:g}g"

            if unit_text == "g":
                if number.is_integer():
                    return f"{int(number)}g"

                return f"{number:g}g"

            if unit_text == "l":
                milliliters = number * 1000

                if milliliters.is_integer():
                    return f"{int(milliliters)}ml"

                return f"{milliliters:g}ml"

            if unit_text == "ml":
                if number.is_integer():
                    return f"{int(number)}ml"

                return f"{number:g}ml"

            return f"{number_text}{unit_text}"

        return self.UNIT_PATTERN.sub(replace, text)

    def _normalize_count_units(self, text: str) -> str:
        """수량 표현을 비교하기 쉬운 형태로 통일한다."""

        unit_map = {
            "마리": "미",
            "입": "개",
            "box": "박스",
        }

        def replace(match: re.Match[str]) -> str:
            number = match.group("number")
            unit = match.group("unit").lower()
            unit = unit_map.get(unit, unit)

            return f"{number}{unit}"

        return self.COUNT_PATTERN.sub(replace, text)

    def _replace_synonyms(self, text: str) -> str:
        """기본 단위 및 표현 사전을 적용한다."""

        for source, target in sorted(
            self.synonym_map.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if not source:
                continue

            text = text.replace(source, target)

        return text

    def _remove_stop_words(
        self,
        text: str,
    ) -> tuple[str, list[str]]:
        """비교에 불필요한 홍보 문구를 제거한다."""

        removed_words: list[str] = []

        for word in self._stop_words_sorted:
            if not word:
                continue

            if word in text:
                text = text.replace(word, " ")
                removed_words.append(word)

        text = self.SPACE_PATTERN.sub(" ", text).strip()

        return text, removed_words

    @staticmethod
    def _join_number_and_unit(text: str) -> str:
        """300 g처럼 분리된 숫자와 단위를 300g으로 붙인다."""

        text = re.sub(
            r"(\d+(?:\.\d+)?)\s+(g|kg|ml|l)\b",
            r"\1\2",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"(\d+)\s+(팩|봉|세트|개|미|박스)\b",
            r"\1\2",
            text,
        )

        return text


_default_normalizer = ProductNameNormalizer()


def normalize_product_name(value: object) -> str:
    """기본 설정으로 상품명을 정규화한다."""

    return _default_normalizer.normalize_string(value)


def compact_product_name(value: object) -> str:
    """기본 설정으로 상품명의 공백까지 제거한다."""

    return _default_normalizer.compact(value)