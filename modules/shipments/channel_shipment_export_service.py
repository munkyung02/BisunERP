from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import uuid4

from openpyxl import Workbook

from modules.shipments.channel_shipment_export_repository import (
    ChannelShipmentExportRepository,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output" / "channel_shipments"


class ChannelShipmentExportService:
    """Generates metadata-driven Coupang Delivery upload workbooks."""

    SHEET_NAME = "Delivery"
    REQUIRED_HEADERS = ("주문번호", "택배사", "운송장번호")

    def __init__(
        self,
        repository: ChannelShipmentExportRepository | None = None,
        output_root: str | Path = OUTPUT_ROOT,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository or ChannelShipmentExportRepository()
        self.output_root = Path(output_root)
        self.now_provider = now_provider or datetime.now

    def export_coupang(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
        reexport: bool = False,
    ) -> dict[str, Any]:
        if reexport and shipment_ids is None:
            raise ValueError("재출력할 송장을 선택해 주세요.")

        rows = self.repository.get_coupang_candidates(
            shipment_ids=shipment_ids,
            include_exported=reexport,
        )
        if not rows:
            message = (
                "선택한 송장 중 쿠팡 재출력 대상이 없습니다."
                if reexport
                else "새로 생성할 쿠팡 송장등록 대상이 없습니다."
            )
            return {"created": False, "message": message, "exported_count": 0}

        headers, output_rows = self._build_rows(rows)
        output_path, exported_at = self._build_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_workbook(output_path, headers, output_rows)

        batch_id = uuid4().hex
        self.repository.record_export(
            rows=rows,
            export_batch_id=batch_id,
            export_file=str(output_path),
            is_reexport=reexport,
        )
        return {
            "created": True,
            "message": f"쿠팡 송장등록 파일 {len(rows):,}건을 생성했습니다.",
            "output_file_path": str(output_path),
            "worksheet_name": self.SHEET_NAME,
            "header_count": len(headers),
            "exported_count": len(rows),
            "shipment_ids": [int(row["shipment_id"]) for row in rows],
            "export_batch_id": batch_id,
            "is_reexport": reexport,
            "exported_at": exported_at.isoformat(timespec="seconds"),
        }

    def _build_rows(
        self,
        candidates: list[dict[str, Any]],
    ) -> tuple[list[str], list[dict[str, str]]]:
        headers: list[str] = []
        parsed_rows: list[dict[str, str]] = []

        for candidate in candidates:
            raw = json.loads(str(candidate.get("raw_source_json") or "{}"))
            if not isinstance(raw, dict):
                raise ValueError("쿠팡 원본 주문 행 JSON 형식이 올바르지 않습니다.")
            normalized = {str(key): self._text(value) for key, value in raw.items()}
            if not headers:
                headers.extend(normalized.keys())
            else:
                headers.extend(key for key in normalized if key not in headers)
            parsed_rows.append(normalized)

        missing = [header for header in self.REQUIRED_HEADERS if header not in headers]
        if missing:
            raise ValueError("쿠팡 원본 주문 행에 필수 열이 없습니다: " + ", ".join(missing))

        for candidate, row in zip(candidates, parsed_rows):
            row["주문번호"] = self._text(candidate.get("channel_order_number"))
            row["택배사"] = self._text(candidate.get("courier_name"))
            row["운송장번호"] = self._text(candidate.get("tracking_number"))
        return headers, parsed_rows

    def _write_workbook(
        self,
        path: Path,
        headers: list[str],
        rows: list[dict[str, str]],
    ) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = self.SHEET_NAME
        for column, header in enumerate(headers, start=1):
            worksheet.cell(row=1, column=column, value=header)
        for row_number, row in enumerate(rows, start=2):
            for column, header in enumerate(headers, start=1):
                cell = worksheet.cell(row=row_number, column=column, value=row.get(header, ""))
                cell.number_format = "@"
        workbook.save(path)
        workbook.close()

    def _build_output_path(self) -> tuple[Path, datetime]:
        current = self.now_provider()
        while True:
            directory = self.output_root / current.strftime("%Y%m%d")
            path = directory / f"쿠팡_송장등록_{current.strftime('%Y%m%d_%H%M%S')}.xlsx"
            if not path.exists():
                return path, current
            current += timedelta(seconds=1)

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value).strip()
