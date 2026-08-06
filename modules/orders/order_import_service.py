from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from modules.orders.order_excel_parser import OrderExcelParser
from modules.orders.order_repository import OrderRepository


class OrderImportService:
    """
    판매채널 주문 엑셀 가져오기 흐름을 관리합니다.

    역할:
    - OrderExcelParser를 통한 채널 자동 판별 및 주문 변환
    - 신규·중복·오류 미리보기
    - 신규 주문 DB 저장
    - 저장 직후 자동 상품매핑

    실제 엑셀 읽기와 채널별 데이터 변환은
    order_excel_parser.py가 담당합니다.
    """

    def __init__(
        self,
        repository: OrderRepository | None = None,
        parser: OrderExcelParser | None = None,
    ) -> None:
        self.repository = repository or OrderRepository()
        self.parser = parser or OrderExcelParser()

    # =========================================================
    # 단일 파일 가져오기
    # =========================================================

    def import_excel(
        self,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """
        주문 엑셀 한 개를 자동 판별하여 바로 저장합니다.

        화면에서 미리보기 없이 즉시 저장해야 할 때 사용합니다.
        일반적인 사용자 흐름에서는 preview_excel() 실행 후
        import_preview_orders()를 호출하는 방식을 권장합니다.
        """
        parsed = self.parser.parse(file_path)
        orders = list(parsed.get("orders") or [])

        result = self.repository.create_orders_bulk(
            orders,
            skip_duplicates=True,
        )

        self._apply_auto_mapping(result)

        result.update(
            {
                "platform": parsed.get("platform", ""),
                "source_file": parsed.get("source_file", ""),
                "excel_row_count": parsed.get("excel_row_count", 0),
                "parsed_order_count": parsed.get("parsed_order_count", 0),
            }
        )

        return result

    def preview_excel(
        self,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """
        주문 엑셀 한 개를 분석하고 신규·중복·오류 주문을 구분합니다.
        """
        parsed = self.parser.parse(file_path)

        preview = self._build_preview(
            orders=list(parsed.get("orders") or []),
            platform=str(parsed.get("platform") or ""),
            source_file=str(parsed.get("source_file") or ""),
            excel_row_count=int(parsed.get("excel_row_count", 0) or 0),
            parsed_order_count=int(parsed.get("parsed_order_count", 0) or 0),
        )

        return preview

    # =========================================================
    # 여러 파일 가져오기
    # =========================================================

    def preview_multiple_excels(
        self,
        file_paths: Iterable[str | Path],
    ) -> dict[str, Any]:
        """
        여러 주문 엑셀을 한 번에 분석합니다.

        파일마다 판매채널을 자동 판별하고,
        모든 주문을 하나의 미리보기 목록으로 합칩니다.
        """
        normalized_paths = [
            Path(file_path)
            for file_path in file_paths
        ]

        if not normalized_paths:
            raise ValueError(
                "선택한 주문서 파일이 없습니다."
            )

        file_previews: list[dict[str, Any]] = []
        all_rows: list[dict[str, Any]] = []
        all_new_orders: list[dict[str, Any]] = []
        file_errors: list[dict[str, Any]] = []

        total_excel_row_count = 0
        total_parsed_order_count = 0
        total_new_count = 0
        total_duplicate_count = 0
        total_error_count = 0

        seen_in_current_batch: set[tuple[str, str]] = set()

        for path in normalized_paths:
            try:
                parsed = self.parser.parse(path)

                file_preview = self._build_preview(
                    orders=list(parsed.get("orders") or []),
                    platform=str(parsed.get("platform") or ""),
                    source_file=str(parsed.get("source_file") or path.name),
                    excel_row_count=int(parsed.get("excel_row_count", 0) or 0),
                    parsed_order_count=int(parsed.get("parsed_order_count", 0) or 0),
                    seen_in_current_batch=seen_in_current_batch,
                )

                file_previews.append(file_preview)
                all_rows.extend(file_preview["rows"])
                all_new_orders.extend(file_preview["new_orders"])

                total_excel_row_count += file_preview["excel_row_count"]
                total_parsed_order_count += file_preview["parsed_order_count"]
                total_new_count += file_preview["new_count"]
                total_duplicate_count += file_preview["duplicate_count"]
                total_error_count += file_preview["error_count"]

            except Exception as error:
                file_errors.append(
                    {
                        "file_path": str(path),
                        "source_file": path.name,
                        "error": str(error),
                    }
                )

        return {
            "file_count": len(normalized_paths),
            "success_file_count": len(file_previews),
            "failed_file_count": len(file_errors),
            "excel_row_count": total_excel_row_count,
            "parsed_order_count": total_parsed_order_count,
            "new_count": total_new_count,
            "duplicate_count": total_duplicate_count,
            "error_count": total_error_count,
            "orders": [
                row["order"]
                for row in all_rows
                if isinstance(row.get("order"), dict)
            ],
            "new_orders": all_new_orders,
            "rows": all_rows,
            "files": file_previews,
            "file_errors": file_errors,
            "source_file": (
                ", ".join(
                    preview["source_file"]
                    for preview in file_previews
                )
            ),
            "platform": "다중채널",
        }

    def import_preview_orders(
        self,
        preview: dict[str, Any],
    ) -> dict[str, Any]:
        """
        미리보기에서 신규로 판정된 주문만 저장합니다.
        """
        new_orders = list(
            preview.get("new_orders") or []
        )

        if not new_orders:
            return self._empty_import_result(preview)

        result = self.repository.create_orders_bulk(
            new_orders,
            skip_duplicates=True,
        )

        self._apply_auto_mapping(result)

        result.update(
            {
                "platform": preview.get("platform", ""),
                "source_file": preview.get("source_file", ""),
                "excel_row_count": preview.get("excel_row_count", 0),
                "parsed_order_count": preview.get("parsed_order_count", 0),
                "preview_new_count": preview.get("new_count", 0),
                "preview_duplicate_count": preview.get("duplicate_count", 0),
                "preview_error_count": preview.get("error_count", 0),
                "file_count": preview.get("file_count", 1),
                "success_file_count": preview.get("success_file_count", 1),
                "failed_file_count": preview.get("failed_file_count", 0),
                "file_errors": list(preview.get("file_errors") or []),
            }
        )

        return result

    # =========================================================
    # 기존 쿠팡 UI 호환 메서드
    # =========================================================

    def import_coupang_excel(
        self,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """
        기존 화면과의 호환을 위한 메서드입니다.

        내부적으로는 판매채널 자동 판별 기능을 사용하며,
        쿠팡이 아닌 파일이 들어오면 오류를 발생시킵니다.
        """
        parsed = self.parser.parse(file_path)
        platform = str(parsed.get("platform") or "")

        if platform != "쿠팡":
            raise ValueError(
                "선택한 파일은 쿠팡 주문서가 아닙니다.\n\n"
                f"자동 판별 채널: {platform or '알 수 없음'}"
            )

        result = self.repository.create_orders_bulk(
            list(parsed.get("orders") or []),
            skip_duplicates=True,
        )

        self._apply_auto_mapping(result)

        result.update(
            {
                "platform": platform,
                "source_file": parsed.get("source_file", ""),
                "excel_row_count": parsed.get("excel_row_count", 0),
                "parsed_order_count": parsed.get("parsed_order_count", 0),
            }
        )

        return result

    def preview_coupang_excel(
        self,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """
        기존 쿠팡 가져오기 창과의 호환을 위한 메서드입니다.
        """
        preview = self.preview_excel(file_path)

        if preview.get("platform") != "쿠팡":
            raise ValueError(
                "선택한 파일은 쿠팡 주문서가 아닙니다.\n\n"
                f"자동 판별 채널: {preview.get('platform') or '알 수 없음'}"
            )

        return preview

    # =========================================================
    # 미리보기 생성
    # =========================================================

    def _build_preview(
        self,
        *,
        orders: list[dict[str, Any]],
        platform: str,
        source_file: str,
        excel_row_count: int,
        parsed_order_count: int,
        seen_in_current_batch: set[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        preview_rows: list[dict[str, Any]] = []
        new_orders: list[dict[str, Any]] = []

        duplicate_count = 0
        error_count = 0

        batch_seen = (
            seen_in_current_batch
            if seen_in_current_batch is not None
            else set()
        )

        for order in orders:
            status = "error"
            status_text = "오류"
            message = ""

            try:
                order_platform = self._required_text(
                    order.get("platform"),
                    "플랫폼",
                )
                order_number = self._required_text(
                    order.get("order_number"),
                    "주문번호",
                )

                self._validate_order_for_preview(order)

                duplicate_key = (
                    order_platform,
                    order_number,
                )

                if duplicate_key in batch_seen:
                    status = "duplicate"
                    status_text = "중복"
                    message = (
                        "현재 선택한 파일 안에서 이미 확인된 "
                        "동일 주문번호입니다."
                    )
                    duplicate_count += 1

                elif self.repository.order_exists(
                    platform=order_platform,
                    order_number=order_number,
                ):
                    status = "duplicate"
                    status_text = "중복"
                    message = "이미 ERP에 등록된 주문번호입니다."
                    duplicate_count += 1
                    batch_seen.add(duplicate_key)

                else:
                    status = "new"
                    status_text = "신규"
                    message = "등록할 수 있는 신규 주문입니다."
                    new_orders.append(order)
                    batch_seen.add(duplicate_key)

            except Exception as error:
                status = "error"
                status_text = "오류"
                message = str(error)
                error_count += 1

            preview_rows.append(
                {
                    "status": status,
                    "status_text": status_text,
                    "message": message,
                    "platform": order.get("platform", platform),
                    "order_number": order.get("order_number", ""),
                    "ordered_at": order.get("ordered_at", ""),
                    "receiver_name": order.get("receiver_name", ""),
                    "receiver_phone": order.get("receiver_phone", ""),
                    "postal_code": order.get("postal_code", ""),
                    "address": order.get("address", ""),
                    "item_summary": self._build_order_item_summary(order),
                    "item_count": len(order.get("items") or []),
                    "total_quantity": self._calculate_total_quantity(order),
                    "total_amount": order.get("total_amount", 0),
                    "source_file": source_file,
                    "order": order,
                }
            )

        return {
            "platform": platform,
            "source_file": source_file,
            "excel_row_count": excel_row_count,
            "parsed_order_count": parsed_order_count,
            "new_count": len(new_orders),
            "duplicate_count": duplicate_count,
            "error_count": error_count,
            "orders": orders,
            "new_orders": new_orders,
            "rows": preview_rows,
        }

    @classmethod
    def _validate_order_for_preview(
        cls,
        order: dict[str, Any],
    ) -> None:
        """
        DB 저장 전에 사용자가 확인해야 할 필수 데이터를 검사합니다.
        """
        cls._required_text(
            order.get("platform"),
            "플랫폼",
        )
        cls._required_text(
            order.get("order_number"),
            "주문번호",
        )
        cls._required_text(
            order.get("receiver_name"),
            "수취인 이름",
        )
        cls._required_text(
            order.get("receiver_phone"),
            "수취인 연락처",
        )
        cls._required_text(
            order.get("address"),
            "수취인 주소",
        )

        items = order.get("items")

        if not isinstance(items, list) or not items:
            raise ValueError(
                "주문상품 정보가 없습니다."
            )

        valid_item_count = 0

        for item_index, item in enumerate(
            items,
            start=1,
        ):
            if not isinstance(item, dict):
                raise ValueError(
                    f"{item_index}번째 주문상품 형식이 올바르지 않습니다."
                )

            product_name = cls._clean_text(
                item.get("platform_product_name")
            )

            if not product_name:
                raise ValueError(
                    f"{item_index}번째 주문상품명이 없습니다."
                )

            quantity = cls._safe_int(
                item.get("quantity"),
                default=0,
            )

            if quantity <= 0:
                raise ValueError(
                    f"{item_index}번째 주문상품 수량이 올바르지 않습니다."
                )

            valid_item_count += 1

        if valid_item_count == 0:
            raise ValueError(
                "등록 가능한 주문상품이 없습니다."
            )

    # =========================================================
    # 자동매핑
    # =========================================================

    def _apply_auto_mapping(
        self,
        result: dict[str, Any],
    ) -> None:
        """
        이번에 생성된 주문만 자동 상품매핑합니다.
        """
        mapping_summary = {
            "target_count": 0,
            "rule_mapped_count": 0,
            "mapped_count": 0,
            "unmatched_count": 0,
            "ambiguous_count": 0,
        }

        for order_id in result.get(
            "created_order_ids",
            [],
        ):
            try:
                mapping_result = (
                    self.repository.auto_map_order_items(
                        order_id=int(order_id),
                    )
                )
            except Exception:
                continue

            for key in mapping_summary:
                mapping_summary[key] += int(
                    mapping_result.get(key, 0) or 0
                )

        result["mapping_target_count"] = (
            mapping_summary["target_count"]
        )
        result["mapping_saved_rule_count"] = (
            mapping_summary["rule_mapped_count"]
        )
        result["mapping_mapped_count"] = (
            mapping_summary["mapped_count"]
        )
        result["mapping_unmatched_count"] = (
            mapping_summary["unmatched_count"]
        )
        result["mapping_ambiguous_count"] = (
            mapping_summary["ambiguous_count"]
        )

    # =========================================================
    # 공통 함수
    # =========================================================

    @classmethod
    def _build_order_item_summary(
        cls,
        order: dict[str, Any],
    ) -> str:
        return " | ".join(
            cls._build_item_summary(item)
            for item in order.get("items") or []
            if isinstance(item, dict)
        )

    @classmethod
    def _build_item_summary(
        cls,
        item: dict[str, Any],
    ) -> str:
        product_name = cls._clean_text(
            item.get("platform_product_name")
        )
        option_name = cls._clean_text(
            item.get("option_name")
        )
        quantity = cls._safe_int(
            item.get("quantity"),
            default=0,
        )

        summary = product_name or "(상품명 없음)"

        if option_name:
            summary += f" / {option_name}"

        summary += f" × {quantity}"

        return summary

    @classmethod
    def _calculate_total_quantity(
        cls,
        order: dict[str, Any],
    ) -> int:
        return sum(
            cls._safe_int(
                item.get("quantity"),
                default=0,
            )
            for item in order.get("items") or []
            if isinstance(item, dict)
        )

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return str(value).strip()

    @classmethod
    def _required_text(
        cls,
        value: Any,
        field_name: str,
    ) -> str:
        text = cls._clean_text(value)

        if not text:
            raise ValueError(
                f"{field_name}이(가) 없습니다."
            )

        return text

    @staticmethod
    def _safe_int(
        value: Any,
        default: int = 0,
    ) -> int:
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _empty_import_result(
        preview: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "total_count": 0,
            "created_count": 0,
            "duplicate_count": 0,
            "failed_count": 0,
            "created_order_ids": [],
            "errors": [],
            "mapping_target_count": 0,
            "mapping_saved_rule_count": 0,
            "mapping_mapped_count": 0,
            "mapping_unmatched_count": 0,
            "mapping_ambiguous_count": 0,
            "platform": preview.get("platform", ""),
            "source_file": preview.get("source_file", ""),
            "excel_row_count": preview.get("excel_row_count", 0),
            "parsed_order_count": preview.get("parsed_order_count", 0),
            "preview_new_count": preview.get("new_count", 0),
            "preview_duplicate_count": preview.get("duplicate_count", 0),
            "preview_error_count": preview.get("error_count", 0),
            "file_count": preview.get("file_count", 1),
            "success_file_count": preview.get("success_file_count", 1),
            "failed_file_count": preview.get("failed_file_count", 0),
            "file_errors": list(preview.get("file_errors") or []),
        }