from __future__ import annotations

from dataclasses import dataclass

from .dictionary import ProductDictionary
from .scorer import ProductScorer


@dataclass
class RecommendItem:
    product_id: int
    product_name: str
    score: int
    similarity: float


class SmartMappingEngine:
    AUTO_MAPPING_SCORE = 95

    def __init__(self) -> None:
        self.scorer = ProductScorer()
        self.dictionary = ProductDictionary()

    def recommend(
        self,
        platform_name: str,
        erp_products: list[dict],
    ) -> list[RecommendItem]:
        normalized_platform_name = self.dictionary.normalize(
            platform_name
        )

        if not normalized_platform_name:
            return []

        results: list[RecommendItem] = []

        for product in erp_products:
            product_id = product.get("id")
            product_name = str(
                product.get("name") or ""
            ).strip()

            if product_id is None or not product_name:
                continue

            normalized_product_name = self.dictionary.normalize(
                product_name
            )

            if not normalized_product_name:
                continue

            result = self.scorer.score(
                normalized_platform_name,
                normalized_product_name,
            )

            results.append(
                RecommendItem(
                    product_id=int(product_id),
                    product_name=product_name,
                    score=int(result.score),
                    similarity=float(result.similarity),
                )
            )

        results.sort(
            key=lambda item: (
                item.score,
                item.similarity,
                -item.product_id,
            ),
            reverse=True,
        )

        return results[:5]

    def auto_mapping(
        self,
        platform_name: str,
        erp_products: list[dict],
    ) -> RecommendItem | None:
        recommendations = self.recommend(
            platform_name,
            erp_products,
        )

        if not recommendations:
            return None

        best = recommendations[0]

        if best.score >= self.AUTO_MAPPING_SCORE:
            return best

        return None