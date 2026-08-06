from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class MarketplaceOrderAdapter(ABC):
    """Contract for converting one marketplace source into ERP orders."""

    id: str
    platform: str
    display_name: str
    version: str
    priority: int
    source_type: str

    @abstractmethod
    def can_handle(self, dataframe: pd.DataFrame) -> bool:
        """Return whether this adapter accepts the supplied source data."""
        raise NotImplementedError

    @abstractmethod
    def parse(
        self,
        dataframe: pd.DataFrame,
        source_file: str,
    ) -> list[dict[str, Any]]:
        """Return orders using the existing ERP normalized dictionary shape."""
        raise NotImplementedError

    @abstractmethod
    def prepared_row_count(self, dataframe: pd.DataFrame) -> int:
        """Return the source data-row count after existing header preparation."""
        raise NotImplementedError
