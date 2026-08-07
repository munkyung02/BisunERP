from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .parser import ProductParser


@dataclass
class ScoreResult:
    score: int

    name_score: int

    weight_score: int

    quantity_score: int

    option_score: int

    similarity: float


class ProductScorer:

    NAME_SCORE = 60
    WEIGHT_SCORE = 20
    QUANTITY_SCORE = 10
    OPTION_SCORE = 10

    def __init__(self):

        self.parser = ProductParser()

    def score(self, source: str, target: str) -> ScoreResult:

        left = self.parser.parse(source)
        right = self.parser.parse(target)

        total = 0

        # --------------------------
        # 상품명
        # --------------------------

        similarity = SequenceMatcher(
            None,
            left.name,
            right.name
        ).ratio()

        name_score = int(
            similarity * self.NAME_SCORE
        )

        total += name_score

        # --------------------------
        # 중량
        # --------------------------

        weight_score = 0

        if (
            left.weight is not None
            and
            right.weight is not None
        ):

            if (
                left.weight == right.weight
                and left.weight_unit == right.weight_unit
            ):

                weight_score = self.WEIGHT_SCORE

        total += weight_score

        # --------------------------
        # 수량
        # --------------------------

        quantity_score = 0

        if (
            left.quantity is not None
            and
            right.quantity is not None
        ):

            if (
                left.quantity == right.quantity
                and left.quantity_unit == right.quantity_unit
            ):

                quantity_score = self.QUANTITY_SCORE

        total += quantity_score

        # --------------------------
        # 옵션
        # --------------------------

        option_score = 0

        if left.option and left.option.lower() == right.option.lower():

            option_score = self.OPTION_SCORE

        total += option_score

        return ScoreResult(

            score=total,

            name_score=name_score,

            weight_score=weight_score,

            quantity_score=quantity_score,

            option_score=option_score,

            similarity=similarity
        )
