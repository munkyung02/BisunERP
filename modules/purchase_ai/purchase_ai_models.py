"""스마트 발주센터에서 사용하는 데이터 모델."""

from dataclasses import dataclass


@dataclass(slots=True)
class PurchasePlanSummary:
    plan_id: int
    supplier_id: int | None
    supplier_name: str
    order_count: int
    item_count: int
    total_quantity: int
    estimated_amount: int
    deadline_time: str
    status: str
    created_at: str


@dataclass(slots=True)
class SupplierScoreSummary:
    supplier_id: int | None
    supplier_name: str
    delivery_score: float
    stock_score: float
    return_score: float
    delay_score: float
    total_score: float
