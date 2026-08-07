from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from modules.operations_intelligence.models import (
    ChannelSalesMix,
    ProductSalesMetrics,
    SalesWindowSummary,
)
from modules.operations_intelligence.repository import (
    DATABASE_PATH,
    SalesIntelligenceRepository,
)


class SalesIntelligenceService:
    """Date-bound facade for read-only sales aggregation."""

    def __init__(
        self,
        database_path: str | Path = DATABASE_PATH,
        *,
        today: date | None = None,
    ) -> None:
        self.repository = SalesIntelligenceRepository(database_path)
        self.today = today or date.today()

    def _starts(self) -> dict[str, date]:
        return {
            "today": self.today,
            "7d": self.today - timedelta(days=6),
            "30d": self.today - timedelta(days=29),
            "90d": self.today - timedelta(days=89),
        }

    def get_window_summaries(self) -> tuple[SalesWindowSummary, ...]:
        return self.repository.get_window_summaries(
            starts=self._starts(),
            end_date=self.today,
        )

    def get_product_metrics(
        self,
        product_ids: Iterable[int] | None = None,
    ) -> tuple[ProductSalesMetrics, ...]:
        return self.repository.get_product_metrics(
            starts=self._starts(),
            end_date=self.today,
            product_ids=product_ids,
        )

    def get_channel_mix(self, period: str = "30d") -> tuple[ChannelSalesMix, ...]:
        starts = self._starts()
        if period not in starts:
            raise ValueError(f"Unsupported sales period: {period}")
        return self.repository.get_channel_mix(
            start_date=starts[period],
            end_date=self.today,
        )

    def get_dashboard_read_model(self) -> dict[str, object]:
        summaries = {item.period: item for item in self.get_window_summaries()}
        return {
            "windows": {key: asdict(value) for key, value in summaries.items()},
            "channel_mix_30d": [asdict(item) for item in self.get_channel_mix("30d")],
        }
