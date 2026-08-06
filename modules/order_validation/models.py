from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ValidationLevel = Literal["PASS", "WARNING", "FAIL"]


@dataclass(slots=True)
class ValidationIssue:
    rule_code: str
    level: ValidationLevel
    title: str
    message: str
    order_item_id: int | None = None
    field_name: str = ""
    current_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationResult:
    order_id: int
    order_number: str
    level: ValidationLevel
    summary: str
    issues: list[ValidationIssue] = field(default_factory=list)
    item_count: int = 0
    passed_count: int = 0
    warning_count: int = 0
    failed_count: int = 0

    @property
    def can_purchase(self) -> bool:
        return self.failed_count == 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["can_purchase"] = self.can_purchase
        return data
