from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import uuid4

from openpyxl import Workbook

from modules.orders.lotteon_order_parser import LotteOnOrderExcelParser
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
    ESM_GMARKET_SHEET_NAME = "Sheet 1"
    ESM_GMARKET_HEADERS = (
        "판매아이디", "주문번호", "주문상태", "상품번호", "상품명", "발송마감일",
        "택배사명(발송방법)", "송장번호", "발송정책", "주문일(결제확인전)",
        "수령인명", "구매자명", "선물주문여부", "선물수락일시", "설치주문여부",
        "설치예정일", "수량", "옵션", "추가구성", "사은품", "사은품 관리코드",
        "덤", "덤 관리코드", "판매단가", "판매금액", "판매자 관리코드",
        "판매자 상세관리코드", "수령인 휴대폰", "수령인 전화번호",
        "배송지변경 여부", "우편번호", "주소", "배송시 요구사항",
        "배송비 결제방법", "배송비 금액", "배송번호", "배송지연사유",
        "수령인 통관정보", "SKU번호 및 수량", "구매자아이디", "구매자 휴대폰",
        "구매자 전화번호", "판매방식", "주문종류", "장바구니번호(결제번호)",
        "결제일", "주문일", "발송예정일", "정산예정금액", "서비스이용료",
        "판매자쿠폰할인", "구매쿠폰적용금액", "우수회원할인", "복수구매할인",
        "스마일캐시적립", "제휴사명", "배송라벨출력일", "SSG 상품번호",
        "SSG 원주문번호",
    )
    ESM_HEADERS = ESM_GMARKET_HEADERS
    ESM_AUCTION_SHEET_NAME = ESM_GMARKET_SHEET_NAME
    LOTTEON_SHEET_NAME = "sheet1"
    LOTTEON_HEADERS = LotteOnOrderExcelParser.source_headers

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

    def export_gmarket(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
        reexport: bool = False,
    ) -> dict[str, Any]:
        if reexport and shipment_ids is None:
            raise ValueError("재출력할 송장을 선택해 주세요.")

        missing_metadata_count = self.repository.count_gmarket_missing_metadata(
            shipment_ids=shipment_ids,
        )
        candidates = self.repository.get_gmarket_candidates(
            shipment_ids=shipment_ids,
            include_exported=reexport,
        )
        (
            output_rows,
            export_rows,
            incomplete_raw_count,
            missing_required_count,
        ) = self._build_gmarket_rows(candidates)

        if not export_rows:
            message = (
                "선택한 송장 중 Gmarket 재출력 대상이 없습니다."
                if reexport
                else "새로 생성할 Gmarket 발송정보 대상이 없습니다."
            )
            return {
                "created": False,
                "message": message,
                "exported_count": 0,
                "missing_metadata_count": missing_metadata_count,
                "incomplete_raw_count": incomplete_raw_count,
                "missing_required_count": missing_required_count,
            }

        output_path, exported_at = self._build_gmarket_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_workbook(
            output_path,
            list(self.ESM_GMARKET_HEADERS),
            output_rows,
            worksheet_name=self.ESM_GMARKET_SHEET_NAME,
        )

        batch_id = uuid4().hex
        self.repository.record_export(
            rows=export_rows,
            export_batch_id=batch_id,
            export_file=str(output_path),
            is_reexport=reexport,
        )
        return {
            "created": True,
            "message": f"Gmarket 발송정보 파일 {len(export_rows):,}건을 생성했습니다.",
            "output_file_path": str(output_path),
            "worksheet_name": self.ESM_GMARKET_SHEET_NAME,
            "header_count": len(self.ESM_GMARKET_HEADERS),
            "exported_count": len(export_rows),
            "missing_metadata_count": missing_metadata_count,
            "incomplete_raw_count": incomplete_raw_count,
            "missing_required_count": missing_required_count,
            "shipment_ids": [int(row["shipment_id"]) for row in export_rows],
            "export_batch_id": batch_id,
            "is_reexport": reexport,
            "exported_at": exported_at.isoformat(timespec="seconds"),
        }

    def export_auction(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
        reexport: bool = False,
    ) -> dict[str, Any]:
        if reexport and shipment_ids is None:
            raise ValueError("재출력할 송장을 선택해 주세요.")

        missing_metadata_count = self.repository.count_auction_missing_metadata(
            shipment_ids=shipment_ids,
        )
        candidates = self.repository.get_auction_candidates(
            shipment_ids=shipment_ids,
            include_exported=reexport,
        )
        (
            output_rows,
            export_rows,
            incomplete_raw_count,
            missing_required_count,
        ) = self._build_gmarket_rows(candidates)

        if not export_rows:
            message = (
                "선택한 송장 중 Auction 재출력 대상이 없습니다."
                if reexport
                else "새로 생성할 Auction 발송정보 대상이 없습니다."
            )
            return {
                "created": False,
                "message": message,
                "exported_count": 0,
                "missing_metadata_count": missing_metadata_count,
                "incomplete_raw_count": incomplete_raw_count,
                "missing_required_count": missing_required_count,
            }

        output_path, exported_at = self._build_auction_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_workbook(
            output_path,
            list(self.ESM_HEADERS),
            output_rows,
            worksheet_name=self.ESM_AUCTION_SHEET_NAME,
        )

        batch_id = uuid4().hex
        self.repository.record_export(
            rows=export_rows,
            export_batch_id=batch_id,
            export_file=str(output_path),
            is_reexport=reexport,
        )
        return {
            "created": True,
            "message": f"Auction 발송정보 파일 {len(export_rows):,}건을 생성했습니다.",
            "output_file_path": str(output_path),
            "worksheet_name": self.ESM_AUCTION_SHEET_NAME,
            "header_count": len(self.ESM_HEADERS),
            "exported_count": len(export_rows),
            "missing_metadata_count": missing_metadata_count,
            "incomplete_raw_count": incomplete_raw_count,
            "missing_required_count": missing_required_count,
            "shipment_ids": [int(row["shipment_id"]) for row in export_rows],
            "export_batch_id": batch_id,
            "is_reexport": reexport,
            "exported_at": exported_at.isoformat(timespec="seconds"),
        }

    def export_lotteon(
        self,
        *,
        shipment_ids: Iterable[int] | None = None,
        reexport: bool = False,
    ) -> dict[str, Any]:
        if reexport and shipment_ids is None:
            raise ValueError("재출력할 송장을 선택해 주세요.")

        missing_metadata_count = self.repository.count_lotteon_missing_metadata(
            shipment_ids=shipment_ids,
        )
        candidates = self.repository.get_lotteon_candidates(
            shipment_ids=shipment_ids,
            include_exported=reexport,
        )
        (
            output_rows,
            export_rows,
            incomplete_raw_count,
            missing_required_count,
            unsupported_carrier_count,
        ) = self._build_lotteon_rows(candidates)

        if not export_rows:
            message = (
                "선택한 송장 중 롯데ON 재출력 대상이 없습니다."
                if reexport
                else "새로 생성할 롯데ON 송장번호일괄등록 대상이 없습니다."
            )
            return {
                "created": False,
                "message": message,
                "exported_count": 0,
                "missing_metadata_count": missing_metadata_count,
                "incomplete_raw_count": incomplete_raw_count,
                "missing_required_count": missing_required_count,
                "unsupported_carrier_count": unsupported_carrier_count,
            }

        output_path, exported_at = self._build_lotteon_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_workbook(
            output_path,
            list(self.LOTTEON_HEADERS),
            output_rows,
            worksheet_name=self.LOTTEON_SHEET_NAME,
        )

        batch_id = uuid4().hex
        self.repository.record_export(
            rows=export_rows,
            export_batch_id=batch_id,
            export_file=str(output_path),
            is_reexport=reexport,
        )
        return {
            "created": True,
            "message": f"롯데ON 송장번호일괄등록 파일 {len(export_rows):,}건을 생성했습니다.",
            "output_file_path": str(output_path),
            "worksheet_name": self.LOTTEON_SHEET_NAME,
            "header_count": len(self.LOTTEON_HEADERS),
            "exported_count": len(export_rows),
            "missing_metadata_count": missing_metadata_count,
            "incomplete_raw_count": incomplete_raw_count,
            "missing_required_count": missing_required_count,
            "unsupported_carrier_count": unsupported_carrier_count,
            "shipment_ids": [int(row["shipment_id"]) for row in export_rows],
            "export_batch_id": batch_id,
            "is_reexport": reexport,
            "exported_at": exported_at.isoformat(timespec="seconds"),
        }

    def _build_lotteon_rows(
        self,
        candidates: list[dict[str, Any]],
    ) -> tuple[
        list[dict[str, str]],
        list[dict[str, Any]],
        int,
        int,
        int,
    ]:
        output_rows: list[dict[str, str]] = []
        export_rows: list[dict[str, Any]] = []
        incomplete_raw_count = 0
        missing_required_count = 0
        unsupported_carrier_count = 0

        for candidate in candidates:
            try:
                raw = json.loads(str(candidate.get("raw_source_json") or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                incomplete_raw_count += 1
                continue
            if not isinstance(raw, dict) or any(
                header not in raw for header in self.LOTTEON_HEADERS
            ):
                incomplete_raw_count += 1
                continue

            channel_order_number = self._text(
                candidate.get("channel_order_number")
            )
            channel_item_number = self._text(
                candidate.get("channel_item_number")
            )
            delivery_method = (
                self._text(candidate.get("delivery_method"))
                or self._text(raw.get("배송수단"))
            )
            courier_name = self._text(candidate.get("courier_name"))
            tracking_number = self._text(candidate.get("tracking_number"))
            verified_source_carrier = self._text(raw.get("배송사"))

            if any(
                not value
                for value in (
                    channel_order_number,
                    channel_item_number,
                    delivery_method,
                    tracking_number,
                )
            ):
                missing_required_count += 1
                continue
            if not verified_source_carrier or courier_name != verified_source_carrier:
                unsupported_carrier_count += 1
                continue

            row = {
                header: self._text(raw.get(header))
                for header in self.LOTTEON_HEADERS
            }
            row["주문번호"] = channel_order_number
            row["주문순번"] = channel_item_number
            row["배송수단"] = delivery_method
            row["배송사"] = courier_name
            row["송장번호"] = tracking_number
            output_rows.append(row)
            export_rows.append(candidate)

        return (
            output_rows,
            export_rows,
            incomplete_raw_count,
            missing_required_count,
            unsupported_carrier_count,
        )

    def _build_gmarket_rows(
        self,
        candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]], int, int]:
        output_rows: list[dict[str, str]] = []
        export_rows: list[dict[str, Any]] = []
        incomplete_raw_count = 0
        missing_required_count = 0

        for candidate in candidates:
            try:
                raw = json.loads(str(candidate.get("raw_source_json") or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                incomplete_raw_count += 1
                continue
            if not isinstance(raw, dict) or any(
                header not in raw for header in self.ESM_GMARKET_HEADERS
            ):
                incomplete_raw_count += 1
                continue

            row = {
                header: self._text(raw.get(header))
                for header in self.ESM_GMARKET_HEADERS
            }
            row["판매아이디"] = (
                self._text(candidate.get("original_platform_name"))
                or self._text(candidate.get("sales_channel"))
                or self._text(raw.get("판매아이디"))
            )
            row["주문번호"] = self._text(candidate.get("channel_order_number"))
            row["택배사명(발송방법)"] = self._text(candidate.get("courier_name"))
            row["송장번호"] = self._text(candidate.get("tracking_number"))

            if any(
                not row[header]
                for header in (
                    "판매아이디",
                    "주문번호",
                    "택배사명(발송방법)",
                    "송장번호",
                )
            ):
                missing_required_count += 1
                continue

            output_rows.append(row)
            export_rows.append(candidate)

        return (
            output_rows,
            export_rows,
            incomplete_raw_count,
            missing_required_count,
        )

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

    def _build_gmarket_output_path(self) -> tuple[Path, datetime]:
        current = self.now_provider()
        while True:
            directory = self.output_root / current.strftime("%Y%m%d")
            path = directory / (
                "ESM_Gmarket_발송정보일괄등록_"
                f"{current.strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            if not path.exists():
                return path, current
            current += timedelta(seconds=1)

    def _build_auction_output_path(self) -> tuple[Path, datetime]:
        current = self.now_provider()
        while True:
            directory = self.output_root / current.strftime("%Y%m%d")
            path = directory / (
                "ESM_Auction_발송정보일괄등록_"
                f"{current.strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            if not path.exists():
                return path, current
            current += timedelta(seconds=1)

    def _build_lotteon_output_path(self) -> tuple[Path, datetime]:
        current = self.now_provider()
        while True:
            directory = self.output_root / current.strftime("%Y%m%d")
            path = directory / (
                "롯데ON_송장번호일괄등록_"
                f"{current.strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            if not path.exists():
                return path, current
            current += timedelta(seconds=1)

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value).strip()
