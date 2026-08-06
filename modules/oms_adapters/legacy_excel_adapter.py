from __future__ import annotations

from typing import Any

import pandas as pd

from modules.oms_adapters.base import MarketplaceOrderAdapter
from modules.orders.base_order_parser import BaseOrderExcelParser


class LegacyExcelOrderAdapter(MarketplaceOrderAdapter):
    """Adapter bridge that delegates to an existing production Excel parser."""

    source_type = "excel"

    def __init__(
        self,
        parser: BaseOrderExcelParser,
        *,
        adapter_id: str,
        display_name: str,
        version: str = "1.0",
        priority: int = 100,
    ) -> None:
        if not isinstance(parser, BaseOrderExcelParser):
            raise TypeError("BaseOrderExcelParser를 상속한 파서만 연결할 수 있습니다.")
        self.parser = parser
        self.id = str(adapter_id)
        self.platform = parser.platform_name
        self.display_name = str(display_name)
        self.version = str(version)
        self.priority = int(priority)

    def can_handle(self, dataframe: pd.DataFrame) -> bool:
        return self.parser.can_parse(dataframe)

    def parse(
        self,
        dataframe: pd.DataFrame,
        source_file: str,
    ) -> list[dict[str, Any]]:
        return self.parser.parse(dataframe=dataframe, source_file=source_file)

    def prepared_row_count(self, dataframe: pd.DataFrame) -> int:
        return len(self.parser.prepare_dataframe(dataframe))
