from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


QA_STATUSES = {"PASS", "WARNING", "FAILED"}


@dataclass
class QACheckResult:
    check_id: str
    name: str
    status: str
    summary: str
    detail: str = ""
    elapsed_seconds: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in QA_STATUSES:
            raise ValueError(f"지원하지 않는 QA 상태입니다: {self.status}")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QAReport:
    metadata: dict[str, str]
    results: list[QACheckResult]
    elapsed_seconds: float
    execution_type: str = "full"

    @property
    def pass_count(self) -> int:
        return sum(row.status == "PASS" for row in self.results)

    @property
    def warning_count(self) -> int:
        return sum(row.status == "WARNING" for row in self.results)

    @property
    def failed_count(self) -> int:
        return sum(row.status == "FAILED" for row in self.results)

    def as_dict(self) -> dict[str, Any]:
        return {
            "metadata": dict(self.metadata),
            "results": [row.as_dict() for row in self.results],
            "elapsed_seconds": self.elapsed_seconds,
            "execution_type": self.execution_type,
            "pass_count": self.pass_count,
            "warning_count": self.warning_count,
            "failed_count": self.failed_count,
        }
