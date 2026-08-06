from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.orders.order_repository import OrderRepository
from modules.shipments.configurable_shipment_parser import (
    ConfigurableShipmentParser,
)
from modules.shipments.parsers import (
    detect_shipment_parser,
    get_supplier_parser,
    get_supported_supplier_names,
)
from modules.shipments.parsers.base_parser import BaseShipmentParser
from modules.shipments.shipment_repository import ShipmentRepository
from modules.suppliers.supplier_repository import SupplierRepository
from modules.coupang.coupang_shipment_service import CoupangShipmentService


class ShipmentService:
    """송장 엑셀 자동판별·매칭·저장 서비스입니다."""

    # 기존 ShipmentPage의 공급처 콤보박스 호환용입니다.
    SUPPLIER_PROFILES: dict[str, dict[str, Any]] = {
        name: {}
        for name in get_supported_supplier_names()
    }

    def __init__(self) -> None:
        self.shipment_repository = ShipmentRepository()
        self.order_repository = OrderRepository()
        self.supplier_repository = SupplierRepository(
            self.shipment_repository.database_path
        )
        self.coupang_shipment_service = CoupangShipmentService(
            database_path=self.shipment_repository.database_path
        )

    def _send_coupang_shipments(
        self,
        shipment_ids: list[int],
    ) -> dict[str, Any]:
        success_count = 0
        failed_count = 0
        skipped_count = 0
        skipped_messages: list[str] = []
        errors: list[dict[str, Any]] = []

        for shipment_id in shipment_ids:
            try:
                result = self.coupang_shipment_service.send_shipment(
                    int(shipment_id)
                )
                if result.get("skipped"):
                    skipped_count += 1
                    message = str(result.get("message") or "").strip()
                    if message and message not in skipped_messages:
                        skipped_messages.append(message)
                elif result.get("succeed"):
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as error:
                failed_count += 1
                errors.append(
                    {
                        "shipment_id": int(shipment_id),
                        "error": str(error),
                    }
                )

        return {
            "coupang_success_count": success_count,
            "coupang_failed_count": failed_count,
            "coupang_skipped_count": skipped_count,
            "coupang_skipped_messages": skipped_messages,
            "coupang_errors": errors,
        }

    def retry_failed_coupang_shipments(self) -> dict[str, Any]:
        return self.coupang_shipment_service.retry_failed()

    def match_shipment(
        self,
        shipment: dict[str, Any],
    ) -> dict[str, Any]:
        candidates = self.shipment_repository.find_match_candidates(
            supplier_name=shipment["supplier_name"],
            receiver_name=shipment["receiver_name"],
            receiver_phone=shipment["receiver_phone"],
            quantity=int(shipment["quantity"]),
        )

        if not candidates:
            return {
                "status": "unmatched",
                "shipment": shipment,
                "candidates": [],
            }

        if len(candidates) > 1:
            return {
                "status": "ambiguous",
                "shipment": shipment,
                "candidates": candidates,
            }

        return {
            "status": "matched",
            "shipment": shipment,
            "candidate": candidates[0],
            "candidates": candidates,
        }

    def read_supplier_shipment_file(
        self,
        file_path: str | Path,
        supplier_name: str,
    ) -> dict[str, Any]:
        supplier = next(
            (
                row
                for row in self.supplier_repository.get_suppliers()
                if str(row["supplier_name"]).strip()
                == str(supplier_name).strip()
            ),
            None,
        )
        mapping = None
        if supplier is not None:
            mapping = self.shipment_repository.get_supplier_shipment_format(
                int(supplier["id"])
            )

        if mapping is not None:
            parser = ConfigurableShipmentParser(
                supplier_name=str(supplier["supplier_name"]),
                header_row=int(mapping["header_row"]),
                order_number_column=int(mapping["order_number_column"]),
                carrier_column=int(mapping["carrier_column"]),
                tracking_number_column=int(
                    mapping["tracking_number_column"]
                ),
            )
        else:
            parser = get_supplier_parser(supplier_name)
        return parser.parse(file_path)

    def get_shipment_supplier_names(self) -> list[str]:
        names = [
            str(row["supplier_name"]).strip()
            for row in self.supplier_repository.get_suppliers(active_only=True)
            if str(row["supplier_name"]).strip()
        ]
        for name in get_supported_supplier_names():
            if name not in names:
                names.append(name)
        return names

    def preview_supplier_shipment_file(
        self,
        file_path: str | Path,
        supplier_name: str,
    ) -> dict[str, Any]:
        file_result = self.read_supplier_shipment_file(
            file_path=file_path,
            supplier_name=supplier_name,
        )

        if file_result.get("match_mode") == "order_number":
            return self._preview_configured_supplier_rows(file_result)

        match_results: list[dict[str, Any]] = []
        matched_count = 0
        unmatched_count = 0
        ambiguous_count = 0
        duplicate_count = 0

        for shipment in file_result["rows"]:
            for tracking_number in shipment.get(
                "tracking_numbers",
                [shipment.get("tracking_number", "")],
            ):
                row_shipment = dict(shipment)
                row_shipment["tracking_number"] = tracking_number
                row_shipment["tracking_numbers"] = [tracking_number]

                if self.shipment_repository.shipment_exists(
                    tracking_number
                ):
                    result = {
                        "status": "duplicate",
                        "shipment": row_shipment,
                        "candidates": [],
                    }
                    duplicate_count += 1
                else:
                    result = self.match_shipment(row_shipment)
                    if result["status"] == "matched":
                        matched_count += 1
                    elif result["status"] == "ambiguous":
                        ambiguous_count += 1
                    else:
                        unmatched_count += 1

                match_results.append(result)

        return {
            **file_result,
            "match_results": match_results,
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
            "ambiguous_count": ambiguous_count,
            "duplicate_count": duplicate_count,
        }

    def _preview_configured_supplier_rows(
        self,
        file_result: dict[str, Any],
    ) -> dict[str, Any]:
        simple_result = self._preview_standard_rows(file_result)
        match_results: list[dict[str, Any]] = []
        matched_count = 0
        unmatched_count = 0
        duplicate_count = 0
        invalid_count = 0

        for row in simple_result["rows"]:
            status = row["status"]
            if status == "valid":
                match_status = "matched"
                matched_count += 1
            elif status == "duplicate":
                match_status = "duplicate"
                duplicate_count += 1
            else:
                parser_error = any(
                    int(error.get("excel_row") or -1)
                    == int(row.get("excel_row") or -2)
                    for error in file_result.get("errors", [])
                )
                if parser_error:
                    match_status = "error"
                    invalid_count += 1
                else:
                    match_status = "unmatched"
                    unmatched_count += 1

            shipment = {
                "excel_row": row.get("excel_row"),
                "order_number": row.get("order_number", ""),
                "carrier": row.get("carrier", ""),
                "tracking_number": row.get("tracking_number", ""),
                "error_message": row.get("message", ""),
            }
            items = row.get("items", [])
            match_results.append(
                {
                    "status": match_status,
                    "shipment": shipment,
                    "candidate": items[0] if items else {},
                    "candidates": items,
                    "items": items,
                }
            )

        return {
            **file_result,
            "match_results": match_results,
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
            "ambiguous_count": 0,
            "duplicate_count": duplicate_count,
            "error_count": invalid_count,
            "errors": [],
        }

    def save_matched_shipments(
        self,
        match_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total_count = len(match_results)
        saved_count = 0
        skipped_count = 0
        error_count = 0
        errors: list[dict[str, Any]] = []
        created_shipment_ids: list[int] = []

        for result in match_results:
            if result.get("status") == "error":
                error_count += 1
                shipment = result.get("shipment", {})
                errors.append(
                    {
                        "excel_row": shipment.get("excel_row"),
                        "tracking_number": shipment.get(
                            "tracking_number", ""
                        ),
                        "error": shipment.get(
                            "error_message", "입력값을 확인하세요."
                        ),
                    }
                )
                continue
            if result.get("status") != "matched":
                skipped_count += 1
                continue

            shipment = result["shipment"]
            candidates = result.get("items") or [result["candidate"]]
            tracking_number = BaseShipmentParser.clean_tracking_number(
                shipment.get("tracking_number")
            )

            try:
                if self.shipment_repository.shipment_exists(
                    tracking_number
                ):
                    skipped_count += 1
                    continue

                for candidate in candidates:
                    shipment_id = self.shipment_repository.create_shipment(
                        order_id=int(candidate["order_id"]),
                        order_item_id=int(candidate["order_item_id"]),
                        supplier_id=(
                            int(candidate["supplier_id"])
                            if candidate.get("supplier_id") is not None
                            else None
                        ),
                        courier_name=shipment["carrier"],
                        tracking_number=tracking_number,
                        shipment_status="배송중",
                        purchase_order_id=int(
                            candidate["purchase_order_id"]
                        ),
                    )
                    created_shipment_ids.append(int(shipment_id))
                saved_count += 1
            except Exception as error:
                error_count += 1
                errors.append(
                    {
                        "excel_row": shipment.get("excel_row"),
                        "tracking_number": tracking_number,
                        "error": str(error),
                    }
                )

        coupang_result = self._send_coupang_shipments(
            created_shipment_ids
        )
        return {
            "total_count": total_count,
            "saved_count": saved_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "errors": errors,
            **coupang_result,
        }

    def preview_simple_shipment_file(
        self,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """
        공급처 선택 없이 엑셀 헤더를 분석해 파서를 자동 선택합니다.
        """

        parser = detect_shipment_parser(file_path)
        file_result = parser.parse(file_path)

        if parser.parser_key == "standard":
            return self._preview_standard_rows(file_result)

        return self._preview_supplier_rows(file_result)

    def _preview_standard_rows(
        self,
        file_result: dict[str, Any],
    ) -> dict[str, Any]:
        preview_rows: list[dict[str, Any]] = []
        valid_count = 0
        error_count = 0
        seen: set[tuple[str, str]] = set()

        for invalid in file_result["errors"]:
            preview_rows.append(
                {
                    "excel_row": invalid.get("excel_row", ""),
                    "order_number": invalid.get("order_number", ""),
                    "carrier": invalid.get("carrier", ""),
                    "tracking_number": invalid.get(
                        "tracking_number",
                        "",
                    ),
                    "status": "error",
                    "status_text": "오류",
                    "message": invalid.get(
                        "error_message",
                        "입력값을 확인하세요.",
                    ),
                    "items": [],
                    "item_count": 0,
                }
            )
            error_count += 1

        for row in file_result["rows"]:
            order_number = BaseShipmentParser.clean_text(
                row.get("order_number")
            )
            carrier = BaseShipmentParser.normalize_carrier(
                row.get("carrier")
            )
            tracking = BaseShipmentParser.clean_tracking_number(
                row.get("tracking_number")
            )

            duplicate_key = (order_number, tracking)
            status = "valid"
            status_text = "등록가능"
            message = ""
            items: list[dict[str, Any]] = []

            if (
                duplicate_key in seen
                or self.shipment_repository.simple_shipment_exists(
                    order_number,
                    tracking,
                )
                or self.shipment_repository.shipment_exists(
                    tracking
                )
            ):
                status = "duplicate"
                status_text = "기등록"
                message = "같은 송장번호가 이미 등록되어 있습니다."
            else:
                items = (
                    self.shipment_repository
                    .find_order_items_for_simple_shipment(
                        order_number
                    )
                )
                if not items:
                    status = "error"
                    status_text = "미매칭"
                    message = (
                        "발주완료 상태의 미등록 주문상품을 "
                        "찾지 못했습니다."
                    )

            seen.add(duplicate_key)

            if status == "valid":
                valid_count += 1
            else:
                error_count += 1

            preview_rows.append(
                {
                    "excel_row": row["excel_row"],
                    "order_number": order_number,
                    "carrier": carrier,
                    "tracking_number": tracking,
                    "status": status,
                    "status_text": status_text,
                    "message": message,
                    "items": items,
                    "item_count": len(items),
                }
            )

        preview_rows.sort(
            key=lambda row: (
                int(row.get("excel_row") or 0),
                str(row.get("tracking_number") or ""),
            )
        )

        return {
            "source_type": file_result["source_type"],
            "rows": preview_rows,
            "total_count": len(preview_rows),
            "valid_count": valid_count,
            "error_count": error_count,
        }

    def _preview_supplier_rows(
        self,
        file_result: dict[str, Any],
    ) -> dict[str, Any]:
        preview_rows: list[dict[str, Any]] = []
        valid_count = 0
        error_count = 0
        seen_tracking: set[str] = set()

        for invalid in file_result["errors"]:
            preview_rows.append(
                {
                    "excel_row": invalid.get("excel_row", ""),
                    "order_number": invalid.get("receiver_name", ""),
                    "carrier": invalid.get("carrier", ""),
                    "tracking_number": invalid.get(
                        "tracking_number",
                        "",
                    ),
                    "status": "error",
                    "status_text": "오류",
                    "message": invalid.get(
                        "error_message",
                        "입력값을 확인하세요.",
                    ),
                    "items": [],
                    "item_count": 0,
                }
            )
            error_count += 1

        for shipment in file_result["rows"]:
            for tracking in shipment.get(
                "tracking_numbers",
                [],
            ):
                row_shipment = dict(shipment)
                row_shipment["tracking_number"] = tracking
                row_shipment["tracking_numbers"] = [tracking]

                status = "valid"
                status_text = "등록가능"
                message = ""
                items: list[dict[str, Any]] = []
                display_reference = shipment.get(
                    "receiver_name",
                    "",
                )

                if (
                    tracking in seen_tracking
                    or self.shipment_repository.shipment_exists(
                        tracking
                    )
                ):
                    status = "duplicate"
                    status_text = "기등록"
                    message = "이미 등록된 송장번호입니다."
                else:
                    match_result = self.match_shipment(
                        row_shipment
                    )

                    if match_result["status"] == "matched":
                        candidate = match_result["candidate"]
                        items = [candidate]
                        display_reference = (
                            self._candidate_reference(
                                candidate,
                                display_reference,
                            )
                        )
                        message = (
                            f"{file_result['source_type']} 자동매칭 · "
                            f"{shipment.get('receiver_name', '')} · "
                            f"{shipment.get('product_name', '')}"
                        )
                    elif match_result["status"] == "ambiguous":
                        status = "error"
                        status_text = "중복후보"
                        message = (
                            f"일치 후보가 "
                            f"{len(match_result['candidates'])}건입니다. "
                            "수취인·전화번호·수량을 확인하세요."
                        )
                    else:
                        status = "error"
                        status_text = "미매칭"
                        message = (
                            "발주완료 상태의 주문을 찾지 못했습니다. "
                            "수취인·전화번호·수량을 확인하세요."
                        )

                seen_tracking.add(tracking)

                if status == "valid":
                    valid_count += 1
                else:
                    error_count += 1

                preview_rows.append(
                    {
                        "excel_row": shipment["excel_row"],
                        "order_number": display_reference,
                        "carrier": shipment["carrier"],
                        "tracking_number": tracking,
                        "status": status,
                        "status_text": status_text,
                        "message": message,
                        "items": items,
                        "item_count": len(items),
                    }
                )

        preview_rows.sort(
            key=lambda row: (
                int(row.get("excel_row") or 0),
                str(row.get("tracking_number") or ""),
            )
        )

        return {
            "source_type": file_result["source_type"],
            "rows": preview_rows,
            "total_count": len(preview_rows),
            "valid_count": valid_count,
            "error_count": error_count,
        }

    @staticmethod
    def _candidate_reference(
        candidate: dict[str, Any],
        fallback: str,
    ) -> str:
        for key in (
            "order_number",
            "external_order_number",
            "platform_order_number",
            "order_no",
        ):
            value = BaseShipmentParser.clean_text(
                candidate.get(key)
            )
            if value:
                return value
        return fallback

    def save_simple_shipments(
        self,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total_count = len(rows)
        success_count = 0
        shipment_count = 0
        skipped_count = 0
        error_count = 0
        errors: list[str] = []
        processed_orders: set[int] = set()
        created_shipment_ids: list[int] = []

        for row in rows:
            if row.get("status") == "duplicate":
                skipped_count += 1
                continue
            if row.get("status") != "valid":
                error_count += 1
                errors.append(
                    f"{row.get('excel_row', '?')}행: "
                    f"{row.get('message') or '등록할 수 없는 행입니다.'}"
                )
                continue

            tracking_number = (
                BaseShipmentParser.clean_tracking_number(
                    row.get("tracking_number")
                )
            )

            if (
                not tracking_number
                or self.shipment_repository.shipment_exists(
                    tracking_number
                )
            ):
                skipped_count += 1
                continue

            try:
                items = row.get("items", [])
                if not items:
                    raise ValueError("일치하는 주문상품이 없습니다.")

                for item in items:
                    shipment_id = self.shipment_repository.create_shipment(
                        order_id=int(item["order_id"]),
                        order_item_id=int(item["order_item_id"]),
                        supplier_id=(
                            int(item["supplier_id"])
                            if item.get("supplier_id") is not None
                            else None
                        ),
                        courier_name=row["carrier"],
                        tracking_number=tracking_number,
                        shipment_status="배송중",
                        purchase_order_id=int(
                            item["purchase_order_id"]
                        ),
                    )

                    created_shipment_ids.append(int(shipment_id))
                    shipment_count += 1
                    processed_orders.add(int(item["order_id"]))
                success_count += 1
            except Exception as exc:
                error_count += 1
                errors.append(
                    f"{row.get('excel_row', '?')}행: {exc}"
                )

        coupang_result = self._send_coupang_shipments(
            created_shipment_ids
        )
        return {
            "total_count": total_count,
            "success_count": success_count,
            "shipment_count": shipment_count,
            "order_count": len(processed_orders),
            "skipped_count": skipped_count,
            "error_count": error_count,
            "errors": errors,
            **coupang_result,
        }
