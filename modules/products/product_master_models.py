from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplierSummary:
    supplier_count: int
    default_supplier: str
    active_supplier_count: int


@dataclass(frozen=True)
class MappingSummary:
    confirmed_mapping_rules: int
    new_product_mappings: int
    total_mapping_rules: int


@dataclass(frozen=True)
class UsageSummary:
    mapped_order_items: int
    purchase_history_count: int
    shipment_history_count: int
    latest_order_date: str


@dataclass(frozen=True)
class ConfirmedChannelAlias:
    platform: str
    platform_product_name: str
    option_name: str
    is_active: bool


@dataclass(frozen=True)
class ObservedChannelAlias:
    platform: str
    platform_product_name: str
    option_name: str
    first_seen: str
    latest_seen: str
    observed_count: int


@dataclass(frozen=True)
class ObservedChannelIdentifier:
    platform: str
    identifier_type: str
    value: str
    observed_count: int
    is_conflict: bool


@dataclass(frozen=True)
class ChannelVisibilitySummary:
    confirmed_aliases: tuple[ConfirmedChannelAlias, ...]
    observed_aliases: tuple[ObservedChannelAlias, ...]
    observed_identifiers: tuple[ObservedChannelIdentifier, ...]
    conflict_status: str
    metadata_status: str


@dataclass(frozen=True)
class ProductMaster:
    id: int
    product_code: str
    product_name: str
    option_name: str
    category: str
    origin: str
    packaging_type: str
    sale_unit: str
    is_active: bool
    status: str
    supplier: SupplierSummary
    mapping: MappingSummary
    usage: UsageSummary
    channel: ChannelVisibilitySummary
