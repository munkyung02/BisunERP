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
