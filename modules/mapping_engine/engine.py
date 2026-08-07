from __future__ import annotations

from dataclasses import dataclass

from .normalizer import ProductNameNormalizer
from .parser import ParsedProduct, ProductParser
from .scorer import ProductScorer


@dataclass
class RecommendItem:
    product_id: int
    product_name: str
    score: int
    similarity: float


@dataclass(frozen=True)
class ProductSignature:
    normalized_product: str
    normalized_option: str
    normalized_combined: str
    parsed: ParsedProduct


class SmartMappingEngine:
    AUTO_MAPPING_SCORE = 95
    AUTO_MAPPING_MIN_GAP = 10

    DETERMINISTIC_PRODUCT_OPTION = 2
    DETERMINISTIC_PRODUCT_ONLY = 3

    def __init__(self) -> None:
        self.scorer = ProductScorer()
        self.normalizer = ProductNameNormalizer()
        self.parser = ProductParser()

    def build_signature(
        self,
        product_name: object,
        option_name: object = None,
    ) -> ProductSignature:
        product = self.normalizer.normalize_string(product_name)
        option = self.normalizer.normalize_string(option_name)
        combined = " ".join(part for part in (product, option) if part)
        return ProductSignature(
            normalized_product=self.normalizer.compact(product),
            normalized_option=self.normalizer.compact(option),
            normalized_combined=self.normalizer.compact(combined),
            parsed=self.parser.parse(combined),
        )

    def deterministic_rank(
        self,
        source_product: object,
        source_option: object,
        target_product: object,
        target_option: object,
    ) -> int | None:
        """Return the safe deterministic rank, or None when attributes conflict."""
        source = self.build_signature(source_product, source_option)
        target = self.build_signature(target_product, target_option)
        if not source.normalized_product or not target.normalized_product:
            return None
        if not self.signatures_compatible(source, target):
            return None

        has_specification = any((
            source.normalized_option,
            target.normalized_option,
            source.parsed.weight is not None,
            target.parsed.weight is not None,
            source.parsed.quantity is not None,
            target.parsed.quantity is not None,
            source.parsed.option,
            target.parsed.option,
            source.parsed.attributes,
            target.parsed.attributes,
        ))
        if (
            source.normalized_combined == target.normalized_combined
            and has_specification
        ):
            return self.DETERMINISTIC_PRODUCT_OPTION
        if source.normalized_product == target.normalized_product:
            return self.DETERMINISTIC_PRODUCT_ONLY
        return None

    @staticmethod
    def signatures_compatible(
        source: ProductSignature,
        target: ProductSignature,
    ) -> bool:
        left = source.parsed
        right = target.parsed

        if (left.weight is not None or right.weight is not None) and (
            left.weight != right.weight or left.weight_unit != right.weight_unit
        ):
            return False
        if (left.quantity is not None or right.quantity is not None) and (
            left.quantity != right.quantity
            or left.quantity_unit != right.quantity_unit
        ):
            return False
        if (source.normalized_option or target.normalized_option) and (
            source.normalized_option != target.normalized_option
        ):
            return False
        if (
            left.option or right.option
        ) and left.option.lower() != right.option.lower():
            return False
        if set(left.attributes) != set(right.attributes):
            return False
        return True

    def recommend(
        self,
        platform_name: str,
        erp_products: list[dict],
    ) -> list[RecommendItem]:
        normalized_platform_name = self.normalizer.normalize_string(
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

            normalized_product_name = self.normalizer.normalize_string(
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
