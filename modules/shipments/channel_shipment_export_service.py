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
    SMARTSTORE_SHEET_NAME = "발송처리"
    SMARTSTORE_HEADERS = (
        "상품주문번호", "주문번호", "배송속성", "풀필먼트사(주문 기준)",
        "택배사(주문 기준)", "배송방법(구매자 요청)", "배송방법", "택배사",
        "송장번호", "발송일", "판매채널", "구매자명", "구매자ID", "수취인명",
        "주문상태", "주문세부상태", "수량클레임 여부", "결제위치", "결제일",
        "상품번호", "상품명", "상품종류", "반품안심케어", "멤버십N배송",
        "옵션정보", "옵션관리코드", "수량", "옵션가격", "상품가격",
        "최종 상품별 할인액", "최초 상품별 할인액", "판매자 부담 할인액",
        "최종 상품별 총 주문금액", "최초 상품별 총 주문금액", "사은품",
        "발주확인일", "발송기한", "발송처리일", "송장출력일", "배송비 형태",
        "배송비 묶음번호", "배송비 유형", "배송비 합계", "제주/도서 추가배송비",
        "배송비 할인액", "판매자 상품코드", "판매자 내부코드1",
        "판매자 내부코드2", "수취인연락처1", "수취인연락처2", "통합배송지",
        "기본배송지", "상세배송지", "구매자연락처", "우편번호", "배송메세지",
        "출고지", "결제수단", "네이버페이 주문관리 수수료", "매출연동 수수료",
        "정산예정금액", "개인통관고유부호", "주문일시", "배송희망일",
        "구독신청회차", "구독진행회차", "구독배송희망일", "배송태그 유형",
        "출입방법 유형", "출입방법 내용", "수령위치 유형", "수령위치 내용",
    )

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

    def export_smartstore(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
        reexport: bool = False,
    ) -> dict[str, Any]:
        if reexport and shipment_ids is None:
            raise ValueError("재출력할 송장을 선택해 주세요.")

        missing_metadata_count = self.repository.count_smartstore_missing_metadata(
            shipment_ids=shipment_ids,
        )
        rows = self.repository.get_smartstore_candidates(
            shipment_ids=shipment_ids,
            include_exported=reexport,
        )
        if not rows:
            message = (
                "선택한 송장 중 스마트스토어 재출력 대상이 없습니다."
                if reexport
                else "새로 생성할 스마트스토어 발송처리 대상이 없습니다."
            )
            return {
                "created": False,
                "message": message,
                "exported_count": 0,
                "missing_metadata_count": missing_metadata_count,
            }

        output_rows = self._build_smartstore_rows(rows)
        output_path, exported_at = self._build_smartstore_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_workbook(
            output_path,
            list(self.SMARTSTORE_HEADERS),
            output_rows,
            worksheet_name=self.SMARTSTORE_SHEET_NAME,
        )

        batch_id = uuid4().hex
        self.repository.record_export(
            rows=rows,
            export_batch_id=batch_id,
            export_file=str(output_path),
            is_reexport=reexport,
        )
        return {
            "created": True,
            "message": f"스마트스토어 발송처리 파일 {len(rows):,}건을 생성했습니다.",
            "output_file_path": str(output_path),
            "worksheet_name": self.SMARTSTORE_SHEET_NAME,
            "header_count": len(self.SMARTSTORE_HEADERS),
            "exported_count": len(rows),
            "missing_metadata_count": missing_metadata_count,
            "shipment_ids": [int(row["shipment_id"]) for row in rows],
            "export_batch_id": batch_id,
            "is_reexport": reexport,
            "exported_at": exported_at.isoformat(timespec="seconds"),
        }

    def _build_smartstore_rows(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        output_rows: list[dict[str, str]] = []
        for candidate in candidates:
            raw = json.loads(str(candidate.get("raw_source_json") or "{}"))
            if not isinstance(raw, dict):
                raise ValueError("스마트스토어 원본 주문 행 JSON 형식이 올바르지 않습니다.")
            missing_headers = [
                header for header in self.SMARTSTORE_HEADERS if header not in raw
            ]
            if missing_headers:
                raise ValueError(
                    "스마트스토어 원본 주문 행에 필수 열이 없습니다: "
                    + ", ".join(missing_headers)
                )

            row = {
                header: self._text(raw.get(header))
                for header in self.SMARTSTORE_HEADERS
            }
            row["상품주문번호"] = self._text(candidate.get("channel_item_number"))
            row["배송방법"] = (
                self._text(candidate.get("delivery_method"))
                or self._text(raw.get("배송방법"))
            )
            row["택배사"] = self._text(candidate.get("courier_name"))
            row["송장번호"] = self._text(candidate.get("tracking_number"))

            missing_values = [
                header
                for header in ("상품주문번호", "배송방법", "택배사", "송장번호")
                if not row[header]
            ]
            if missing_values:
                raise ValueError(
                    "스마트스토어 발송처리 필수 값이 없습니다: "
                    + ", ".join(missing_values)
                )
            output_rows.append(row)
        return output_rows

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
        worksheet_name: str | None = None,
    ) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = worksheet_name or self.SHEET_NAME
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

    def _build_smartstore_output_path(self) -> tuple[Path, datetime]:
        current = self.now_provider()
        while True:
            directory = self.output_root / current.strftime("%Y%m%d")
            path = directory / f"네이버_발송처리_{current.strftime('%Y%m%d_%H%M%S')}.xlsx"
            if not path.exists():
                return path, current
            current += timedelta(seconds=1)

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value).strip()
