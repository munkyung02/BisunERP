from __future__ import annotations

from modules.oms_adapters.legacy_excel_adapter import LegacyExcelOrderAdapter
from modules.oms_adapters.registry import OMSAdapterRegistry
from modules.orders.coupang_order_parser import CoupangOrderExcelParser
from modules.orders.smartstore_order_parser import SmartStoreOrderExcelParser


def create_default_adapter_registry() -> OMSAdapterRegistry:
    """Build the production registry in the established parser order."""
    registry = OMSAdapterRegistry()
    registry.register(
        LegacyExcelOrderAdapter(
            CoupangOrderExcelParser(),
            adapter_id="coupang.excel.orders",
            display_name="쿠팡 주문 Excel",
            version="1.0",
            priority=100,
        )
    )
    registry.register(
        LegacyExcelOrderAdapter(
            SmartStoreOrderExcelParser(),
            adapter_id="smartstore.excel.orders",
            display_name="스마트스토어 주문 Excel",
            version="1.0",
            priority=200,
        )
    )
    return registry
