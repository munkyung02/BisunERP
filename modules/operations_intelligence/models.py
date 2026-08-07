from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SalesWindowSummary:
    period: str
    start_date: str
    end_date: str
    order_count: int
    quantity_sold: int
    revenue: int
    average_order_value: int
    mapped_quantity: int
    unmapped_quantity: int


@dataclass(frozen=True)
class ProductSalesMetrics:
    product_id: int
    product_code: str
    product_name: str
    quantity_today: int
    quantity_7d: int
    quantity_30d: int
    quantity_90d: int
    revenue_today: int
    revenue_7d: int
    revenue_30d: int
    revenue_90d: int
    order_count: int
    latest_order_date: str


@dataclass(frozen=True)
class ChannelSalesMix:
    platform: str
    order_count: int
    quantity: int
    revenue: int
    order_ratio: float
    quantity_ratio: float
    revenue_ratio: float


@dataclass(frozen=True)
class ProductPurchaseMetrics:
    product_id: int
    product_code: str
    product_name: str
    purchase_count: int
    purchased_quantity: int | None
    total_purchase_amount: int | None
    average_unit_price: int | None
    price_coverage_count: int
    total_purchase_rows: int
    configured_default_supplier_id: int | None
    configured_default_supplier_name: str
    most_used_supplier_id: int | None
    most_used_supplier_name: str
    latest_supplier_id: int | None
    latest_supplier_name: str
    latest_purchase_date: str
    data_status: str


@dataclass(frozen=True)
class SupplierProductComparison:
    product_id: int
    supplier_id: int
    supplier_name: str
    configured_purchase_price: int
    historical_average_price: int | None
    purchase_count: int
    purchased_quantity: int | None
    purchase_amount: int | None
    usage_ratio: float
    latest_purchase_date: str
    supplier_active: bool
    product_supplier_active: bool
    is_default: bool
    price_source: str
    price_coverage_count: int
    data_status: str


@dataclass(frozen=True)
class SupplierComparisonRow:
    supplier_id: int
    supplier_name: str
    supplier_code: str
    configured_purchase_price: int | None
    historical_average_price: int | None
    historical_price_coverage_count: int
    purchase_count: int
    purchased_quantity: int | None
    purchase_amount: int | None
    usage_ratio: float | None
    latest_purchase_date: str
    supplier_active: bool
    product_supplier_active: bool
    is_default: bool
    supplier_product_code: str
    supplier_product_name: str
    minimum_order_quantity: int | None
    packaging_quantity: int | None
    packaging_unit: str
    shipping_fee: int | None
    cutoff_time: str
    condition_status: str
    data_status: str


@dataclass(frozen=True)
class SupplierComparisonResult:
    product_id: int
    product_code: str
    product_name: str
    suppliers: tuple[SupplierComparisonRow, ...]
    supplier_count: int
    active_supplier_count: int
    configured_default_supplier_id: int | None
    configured_default_supplier_name: str
    most_used_supplier_id: int | None
    most_used_supplier_name: str
    data_status: str
