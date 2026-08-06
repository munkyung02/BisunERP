from __future__ import annotations

import pandas as pd

from modules.oms_adapters.base import MarketplaceOrderAdapter


class OMSAdapterRegistry:
    """Ordered registry for marketplace order adapters."""

    def __init__(self) -> None:
        self._adapters: list[MarketplaceOrderAdapter] = []

    @property
    def adapters(self) -> tuple[MarketplaceOrderAdapter, ...]:
        return tuple(self._adapters)

    def register(self, adapter: MarketplaceOrderAdapter) -> None:
        if not isinstance(adapter, MarketplaceOrderAdapter):
            raise TypeError("MarketplaceOrderAdapter만 등록할 수 있습니다.")
        if any(existing.id == adapter.id for existing in self._adapters):
            raise ValueError(f"이미 등록된 OMS 어댑터 ID입니다: {adapter.id}")
        self._adapters.append(adapter)
        self._adapters.sort(key=lambda value: value.priority)

    def matching_adapters(
        self,
        dataframe: pd.DataFrame,
    ) -> list[MarketplaceOrderAdapter]:
        return [
            adapter
            for adapter in self._adapters
            if adapter.can_handle(dataframe)
        ]
