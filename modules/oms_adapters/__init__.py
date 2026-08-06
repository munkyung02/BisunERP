"""Marketplace order adapter abstractions used by the OMS import facade."""

from modules.oms_adapters.base import MarketplaceOrderAdapter
from modules.oms_adapters.defaults import create_default_adapter_registry
from modules.oms_adapters.legacy_excel_adapter import LegacyExcelOrderAdapter
from modules.oms_adapters.registry import OMSAdapterRegistry

__all__ = [
    "LegacyExcelOrderAdapter",
    "MarketplaceOrderAdapter",
    "OMSAdapterRegistry",
    "create_default_adapter_registry",
]
