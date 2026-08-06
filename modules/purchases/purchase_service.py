import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from modules.templates import get_purchase_template


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"
OUTPUT_ROOT = PROJECT_ROOT / "output" / "발주서"


class PurchaseService:
    """매핑 완료 주문을 공급처별 발주서로 생성합니다."""

    def __init__(
        self,
        database_path: str | Path | None = None,
        output_root: str | Path | None = None,
    ) -> None:
        self.database_path = Path(
            database_path or DATABASE_PATH
        )

        self.output_root = Path(
            output_root or OUTPUT_ROOT
        )

    # =========================================================
    # DB 연결
    # =========================================================

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path
        )

        connection.row_factory = sqlite3.Row
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        return connection

    # =========================================================
    # 발주 가능 상품 조회
    # =========================================================

    def get_purchase_candidates(
        self,
    ) -> list[dict[str, Any]]:
        """
        다음 조건을 만족하는 주문상품만 조회합니다.

        1. 상품 매핑 완료
        2. 공급처 연결 완료
        3. 아직 purchase_orders에 생성되지 않음
        4. 주문 발주 상태가 발주대기 또는 발주준비
        """

        query = """
            SELECT
                oi.id AS order_item_id,
                oi.order_id,
                oi.product_id,
                oi.supplier_id,
                oi.platform_product_name,
                oi.option_name,
                oi.quantity,
                oi.purchase_round,
                oi.mapping_status,

                o.platform,
                o.order_number,
                o.ordered_at,
                o.receiver_name,
                o.receiver_phone,
                o.postal_code,
                o.address,
                o.detail_address,
                o.delivery_message,
                o.purchase_status,

                p.product_code AS supplier_product_code,
                p.product_name,
                p.supplier_product_name,
                COALESCE(p.purchase_price, 0) AS unit_price,

                s.supplier_code,
                s.supplier_name,
                s.contact_name,
                s.phone AS supplier_phone,
                COALESCE(s.default_shipping_fee, 0) AS shipping_fee,
                COALESCE(s.default_courier, '') AS carrier

            FROM order_items AS oi

            INNER JOIN orders AS o
                ON o.id = oi.order_id

            INNER JOIN products AS p
                ON p.id = oi.product_id

            INNER JOIN suppliers AS s
                ON s.id = oi.supplier_id

            LEFT JOIN purchase_orders AS po
                ON po.order_item_id = oi.id

            WHERE oi.product_id IS NOT NULL
              AND oi.supplier_id IS NOT NULL
              AND oi.mapping_status != '미매핑'
              AND o.purchase_status IN (
                    '발주대기',
                    '발주준비'
              )
              AND po.id IS NULL
              AND p.is_active = 1
              AND s.is_active = 1

            ORDER BY
                s.supplier_name,
                oi.purchase_round,
                o.ordered_at,
                o.id,
                oi.id
        """

        with self._connect() as connection:
            rows = connection.execute(
                query
            ).fetchall()

        candidates: list[dict[str, Any]] = []

        for row in rows:
            item = dict(row)
            item["purchase_quantity"] = (
                self._purchase_quantity(
                    item.get("quantity"),
                    item.get("option_name"),
                )
            )
            item["item_amount"] = (
                int(item.get("unit_price") or 0)
                * int(item.get("purchase_quantity") or 0)
            )
            candidates.append(item)

        return candidates


    # =========================================================
    # 발주 전 안전검사
    # =========================================================

    def validate_purchase_candidates(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """발주서 생성 전에 누락·이상 데이터를 검사합니다.

        차단 오류는 발주를 중단하고, 주의사항은 사용자가 확인 후 진행할 수 있습니다.
        """
        errors: list[str] = []
        warnings: list[str] = []
        seen_item_ids: set[int] = set()

        for index, item in enumerate(candidates, start=1):
            order_number = str(item.get("order_number") or "").strip() or f"{index}번째 주문"
            product_name = str(
                item.get("supplier_product_name")
                or item.get("product_name")
                or item.get("platform_product_name")
                or ""
            ).strip()
            label = f"{order_number} / {product_name or '상품명 없음'}"

            try:
                item_id = int(item.get("order_item_id") or 0)
            except (TypeError, ValueError):
                item_id = 0

            if item_id <= 0:
                errors.append(f"{label}: 주문상품 ID가 없습니다.")
            elif item_id in seen_item_ids:
                errors.append(f"{label}: 동일 주문상품이 중복 선택되었습니다.")
            else:
                seen_item_ids.add(item_id)

            if not item.get("supplier_id") or not str(item.get("supplier_name") or "").strip():
                errors.append(f"{label}: 공급처가 연결되지 않았습니다.")

            if not item.get("product_id"):
                errors.append(f"{label}: ERP 상품이 매핑되지 않았습니다.")

            quantity = self._safe_positive_int(item.get("purchase_quantity"), default=0)
            if quantity <= 0:
                errors.append(f"{label}: 발주수량이 0이거나 올바르지 않습니다.")

            receiver_name = str(item.get("receiver_name") or "").strip()
            receiver_phone = str(item.get("receiver_phone") or "").strip()
            address = self._full_address(item.get("address"), item.get("detail_address"))

            if not receiver_name:
                errors.append(f"{label}: 수령인 이름이 없습니다.")
            if not receiver_phone:
                errors.append(f"{label}: 수령인 연락처가 없습니다.")
            if not address:
                errors.append(f"{label}: 배송 주소가 없습니다.")

            if not str(item.get("postal_code") or "").strip():
                warnings.append(f"{label}: 우편번호가 비어 있습니다.")
            if not str(item.get("supplier_product_code") or "").strip():
                warnings.append(f"{label}: 공급처 상품코드가 비어 있습니다.")
            if int(item.get("unit_price") or 0) <= 0:
                warnings.append(f"{label}: 매입단가가 0원입니다.")

        return {
            "ok": not errors,
            "candidate_count": len(candidates),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
        }

    @staticmethod
    def _safe_positive_int(value: Any, default: int = 1) -> int:
        try:
            converted = int(value)
        except (TypeError, ValueError):
            return default
        return converted if converted > 0 else default

    # =========================================================
    # 발주 생성
    # =========================================================

    def create_purchase_files(
        self,
        order_item_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        candidates = self.get_purchase_candidates()

        # 선택 발주일 경우 선택한 주문상품만 남깁니다.
        if order_item_ids is not None:
            selected_ids = {
                int(item_id)
                for item_id in order_item_ids
            }

            candidates = [
                candidate
                for candidate in candidates
                if int(candidate["order_item_id"])
                in selected_ids
            ]

        if not candidates:
            return {
                "candidate_count": 0,
                "created_count": 0,
                "supplier_count": 0,
                "files": [],
                "message": (
                    "발주 가능한 주문상품이 없습니다."
                ),
            }

        grouped: dict[
            tuple[int, str, str],
            list[dict[str, Any]],
        ] = defaultdict(list)

        for item in candidates:
            supplier_id = int(
                item["supplier_id"]
            )

            supplier_name = str(
                item["supplier_name"]
            ).strip()

            purchase_round = str(
                item.get("purchase_round") or "기본"
            ).strip()

            grouped[
                (
                    supplier_id,
                    supplier_name,
                    purchase_round,
                )
            ].append(item)

        date_folder = datetime.now().strftime(
            "%Y-%m-%d"
        )

        output_directory = (
            self.output_root / date_folder
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        created_files: list[str] = []
        created_order_item_ids: list[int] = []

        with self._connect() as connection:
            try:
                for (
                    supplier_id,
                    supplier_name,
                    purchase_round,
                ), items in grouped.items():
                    purchase_template = get_purchase_template(
                        supplier_name
                    )

                    file_path = purchase_template.create_excel(
                        output_directory=output_directory,
                        supplier_name=supplier_name,
                        purchase_round=purchase_round,
                        items=items,
                    )

                    created_files.append(
                        str(file_path)
                    )

                    for item in items:
                        order_item_id = int(
                            item["order_item_id"]
                        )

                        full_address = self._full_address(
                            item.get("address"),
                            item.get(
                                "detail_address"
                            ),
                        )

                        connection.execute(
                            """
                            INSERT INTO purchase_orders (
                                supplier_id,
                                order_id,
                                order_item_id,
                                supplier_name,
                                order_number,
                                product_name,
                                option_name,
                                quantity,
                                receiver_name,
                                receiver_phone,
                                postal_code,
                                address,
                                delivery_message,
                                purchase_status,
                                purchase_file,
                                purchased_at,
                                created_at,
                                updated_at,
                                supplier_product_code,
                                unit_price,
                                item_amount,
                                shipping_fee,
                                carrier,
                                purchase_round
                            )
                            VALUES (
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                ?, ?, ?,
                                '발주완료',
                                ?,
                                CURRENT_TIMESTAMP,
                                CURRENT_TIMESTAMP,
                                CURRENT_TIMESTAMP,
                                ?, ?, ?, ?, ?, ?
                            )
                            """,
                            (
                                supplier_id,
                                item["order_id"],
                                order_item_id,
                                supplier_name,
                                item["order_number"],
                                (
                                    item.get(
                                        "supplier_product_name"
                                    )
                                    or item.get(
                                        "product_name"
                                    )
                                    or item.get(
                                        "platform_product_name"
                                    )
                                ),
                                item.get("option_name"),
                                item.get(
                                    "purchase_quantity",
                                    item.get("quantity", 1),
                                ),
                                item.get("receiver_name"),
                                item.get("receiver_phone"),
                                item.get("postal_code"),
                                full_address,
                                item.get(
                                    "delivery_message"
                                ),
                                str(file_path),
                                item.get("supplier_product_code") or item.get("product_code") or "",
                                int(item.get("unit_price") or 0),
                                int(item.get("item_amount") or 0),
                                int(item.get("shipping_fee") or 0),
                                item.get("carrier") or "",
                                item.get("purchase_round") or "기본",
                            ),
                        )

                        created_order_item_ids.append(
                            order_item_id
                        )

                affected_order_ids = {
                    int(item["order_id"])
                    for item in candidates
                }

                for order_id in affected_order_ids:
                    remaining_row = connection.execute(
                        """
                        SELECT COUNT(*) AS remaining_count

                        FROM order_items AS oi

                        LEFT JOIN purchase_orders AS po
                            ON po.order_item_id = oi.id

                        WHERE oi.order_id = ?
                          AND po.id IS NULL
                        """,
                        (order_id,),
                    ).fetchone()

                    remaining_count = int(
                        remaining_row[
                            "remaining_count"
                        ]
                        or 0
                    )

                    next_status = (
                        "발주완료"
                        if remaining_count == 0
                        else "발주준비"
                    )

                    connection.execute(
                        """
                        UPDATE orders
                        SET
                            purchase_status = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            next_status,
                            order_id,
                        ),
                    )

                connection.commit()

            except Exception:
                connection.rollback()

                for created_file in created_files:
                    path = Path(created_file)

                    if path.exists():
                        try:
                            path.unlink()
                        except OSError:
                            pass

                raise

        return {
            "candidate_count": len(candidates),
            "created_count": len(
                created_order_item_ids
            ),
            "supplier_count": len(grouped),
            "files": created_files,
            "output_directory": str(
                output_directory
            ),
            "message": "발주서 생성 완료",
        }

    # =========================================================
    # 엑셀 생성
    # =========================================================

    def _create_supplier_excel(
        self,
        *,
        output_directory: Path,
        supplier_name: str,
        purchase_round: str,
        items: list[dict[str, Any]],
    ) -> Path:
        """
        공급처별 발주 엑셀을 생성합니다.

        시트 구성
        1. 발주요약: 같은 상품·옵션·단가를 한 줄로 합산
        2. 배송목록: 주문별 수령인·주소를 기존처럼 개별 표시

        DB의 purchase_orders에는 주문상품별 발주 기록을 그대로 저장하므로
        송장등록 및 주문 추적 구조는 변경되지 않습니다.
        """

        workbook = Workbook()

        summary_sheet = workbook.active
        summary_sheet.title = "발주요약"
        summary_sheet.sheet_view.showGridLines = False
        summary_sheet.freeze_panes = "A5"

        detail_sheet = workbook.create_sheet("배송목록")
        detail_sheet.sheet_view.showGridLines = False
        detail_sheet.freeze_panes = "A5"

        thin_border = Border(
            left=Side(style="thin", color="B7B7B7"),
            right=Side(style="thin", color="B7B7B7"),
            top=Side(style="thin", color="B7B7B7"),
            bottom=Side(style="thin", color="B7B7B7"),
        )
        header_fill = PatternFill(
            fill_type="solid",
            fgColor="D9EAD3",
        )

        aggregated_items = self._aggregate_purchase_items(items)

        # -----------------------------------------------------
        # 1. 발주요약 시트
        # -----------------------------------------------------
        summary_sheet.merge_cells("A1:H1")
        summary_sheet["A1"] = "비선상회 공급처 발주요약"
        summary_sheet["A1"].font = Font(size=18, bold=True)
        summary_sheet["A1"].alignment = Alignment(
            horizontal="center",
            vertical="center",
        )
        summary_sheet.row_dimensions[1].height = 32

        summary_sheet["A2"] = "공급처"
        summary_sheet["B2"] = supplier_name
        summary_sheet["D2"] = "발주차수"
        summary_sheet["E2"] = purchase_round
        summary_sheet["G2"] = "생성일시"
        summary_sheet["H2"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        total_quantity = sum(
            int(item.get("total_quantity") or 0)
            for item in aggregated_items
        )
        total_amount = sum(
            int(item.get("total_amount") or 0)
            for item in aggregated_items
        )

        summary_sheet["A3"] = "상품 종류"
        summary_sheet["B3"] = len(aggregated_items)
        summary_sheet["C3"] = "주문상품 건수"
        summary_sheet["D3"] = len(items)
        summary_sheet["E3"] = "총 수량"
        summary_sheet["F3"] = total_quantity
        summary_sheet["G3"] = "총 상품금액"
        summary_sheet["H3"] = total_amount
        summary_sheet["H3"].number_format = '#,##0"원"'

        summary_headers = [
            "번호",
            "공급처 상품코드",
            "공급처 상품명",
            "옵션",
            "주문건수",
            "총 수량",
            "매입단가",
            "총 상품금액",
        ]

        for column_index, header in enumerate(
            summary_headers,
            start=1,
        ):
            cell = summary_sheet.cell(
                row=4,
                column=column_index,
                value=header,
            )
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

        for row_index, item in enumerate(
            aggregated_items,
            start=1,
        ):
            excel_row = 4 + row_index

            values = [
                row_index,
                item.get("supplier_product_code") or "",
                item.get("product_name") or "",
                item.get("option_name") or "",
                int(item.get("order_count") or 0),
                int(item.get("total_quantity") or 0),
                int(item.get("unit_price") or 0),
                int(item.get("total_amount") or 0),
            ]

            for column_index, value in enumerate(
                values,
                start=1,
            ):
                cell = summary_sheet.cell(
                    row=excel_row,
                    column=column_index,
                    value=value,
                )
                cell.border = thin_border
                cell.alignment = Alignment(
                    horizontal=(
                        "left"
                        if column_index in {2, 3, 4}
                        else "center"
                    ),
                    vertical="center",
                    wrap_text=True,
                )

                if column_index in {7, 8}:
                    cell.number_format = '#,##0"원"'

            summary_sheet.row_dimensions[excel_row].height = 32

        summary_widths = {
            1: 7,
            2: 18,
            3: 34,
            4: 28,
            5: 11,
            6: 11,
            7: 14,
            8: 16,
        }

        for column_index, width in summary_widths.items():
            summary_sheet.column_dimensions[
                get_column_letter(column_index)
            ].width = width

        if aggregated_items:
            summary_sheet.auto_filter.ref = (
                f"A4:H{4 + len(aggregated_items)}"
            )

        # -----------------------------------------------------
        # 2. 배송목록 시트
        # -----------------------------------------------------
        detail_sheet.merge_cells("A1:K1")
        detail_sheet["A1"] = "비선상회 주문별 배송목록"
        detail_sheet["A1"].font = Font(size=18, bold=True)
        detail_sheet["A1"].alignment = Alignment(
            horizontal="center",
            vertical="center",
        )
        detail_sheet.row_dimensions[1].height = 32

        detail_sheet["A2"] = "공급처"
        detail_sheet["B2"] = supplier_name
        detail_sheet["D2"] = "발주차수"
        detail_sheet["E2"] = purchase_round
        detail_sheet["G2"] = "생성일시"
        detail_sheet["H2"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        detail_sheet["A3"] = "총 주문상품"
        detail_sheet["B3"] = len(items)
        detail_sheet["D3"] = "총 수량"
        detail_sheet["E3"] = sum(
            int(
                item.get(
                    "purchase_quantity",
                    item.get("quantity") or 0,
                )
            )
            for item in items
        )

        detail_headers = [
            "번호",
            "주문번호",
            "공급처 상품명",
            "옵션",
            "수량",
            "수령인",
            "연락처",
            "우편번호",
            "주소",
            "배송메시지",
            "주문일시",
        ]

        for column_index, header in enumerate(
            detail_headers,
            start=1,
        ):
            cell = detail_sheet.cell(
                row=4,
                column=column_index,
                value=header,
            )
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

        for row_index, item in enumerate(
            items,
            start=1,
        ):
            excel_row = 4 + row_index

            product_name = (
                item.get("supplier_product_name")
                or item.get("product_name")
                or item.get("platform_product_name")
                or ""
            )

            full_address = self._full_address(
                item.get("address"),
                item.get("detail_address"),
            )

            values = [
                row_index,
                item.get("order_number"),
                product_name,
                item.get("option_name"),
                item.get(
                    "purchase_quantity",
                    item.get("quantity"),
                ),
                item.get("receiver_name"),
                item.get("receiver_phone"),
                item.get("postal_code"),
                full_address,
                item.get("delivery_message"),
                item.get("ordered_at"),
            ]

            for column_index, value in enumerate(
                values,
                start=1,
            ):
                cell = detail_sheet.cell(
                    row=excel_row,
                    column=column_index,
                    value=value or "",
                )
                cell.border = thin_border
                cell.alignment = Alignment(
                    horizontal=(
                        "center"
                        if column_index in {
                            1,
                            2,
                            5,
                            6,
                            7,
                            8,
                            11,
                        }
                        else "left"
                    ),
                    vertical="center",
                    wrap_text=True,
                )

            detail_sheet.row_dimensions[excel_row].height = 38

        detail_widths = {
            1: 7,
            2: 18,
            3: 28,
            4: 28,
            5: 8,
            6: 11,
            7: 16,
            8: 10,
            9: 48,
            10: 38,
            11: 19,
        }

        for column_index, width in detail_widths.items():
            detail_sheet.column_dimensions[
                get_column_letter(column_index)
            ].width = width

        if items:
            detail_sheet.auto_filter.ref = (
                f"A4:K{4 + len(items)}"
            )

        safe_supplier_name = self._safe_filename(
            supplier_name
        )
        safe_purchase_round = self._safe_filename(
            purchase_round
        )
        timestamp = datetime.now().strftime(
            "%H%M%S"
        )

        file_name = (
            f"{safe_supplier_name}_"
            f"{safe_purchase_round}_"
            f"발주서_{timestamp}.xlsx"
        )
        file_path = output_directory / file_name

        workbook.active = 0
        workbook.save(file_path)

        return file_path

    @staticmethod
    def _aggregate_purchase_items(
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        같은 공급처 상품코드·상품명·옵션·단가를 하나로 합산합니다.

        배송지는 주문마다 다르므로 배송목록 시트에서는 합치지 않고,
        발주요약 시트에서만 상품 수량을 합산합니다.
        """

        grouped: dict[
            tuple[str, str, str, int],
            dict[str, Any],
        ] = {}

        for item in items:
            product_code = str(
                item.get("supplier_product_code")
                or item.get("product_code")
                or ""
            ).strip()

            product_name = str(
                item.get("supplier_product_name")
                or item.get("product_name")
                or item.get("platform_product_name")
                or ""
            ).strip()

            option_name = str(
                item.get("option_name") or ""
            ).strip()

            unit_price = int(
                item.get("unit_price") or 0
            )

            quantity = int(
                item.get(
                    "purchase_quantity",
                    item.get("quantity") or 0,
                )
                or 0
            )

            key = (
                product_code,
                product_name,
                option_name,
                unit_price,
            )

            bucket = grouped.setdefault(
                key,
                {
                    "supplier_product_code": product_code,
                    "product_name": product_name,
                    "option_name": option_name,
                    "unit_price": unit_price,
                    "order_count": 0,
                    "total_quantity": 0,
                    "total_amount": 0,
                },
            )

            bucket["order_count"] += 1
            bucket["total_quantity"] += quantity
            bucket["total_amount"] += (
                unit_price * quantity
            )

        return sorted(
            grouped.values(),
            key=lambda item: (
                str(item.get("supplier_product_code") or ""),
                str(item.get("product_name") or ""),
                str(item.get("option_name") or ""),
                int(item.get("unit_price") or 0),
            ),
        )

    def get_supplier_purchase_summary(self) -> list[dict[str, Any]]:
        """공급처별 발주대기·오늘 발주·누적 발주 현황을 반환합니다."""
        candidates = self.get_purchase_candidates()
        grouped: dict[int, dict[str, Any]] = {}

        for item in candidates:
            supplier_id = int(item["supplier_id"])
            bucket = grouped.setdefault(
                supplier_id,
                {
                    "supplier_id": supplier_id,
                    "supplier_name": str(item.get("supplier_name") or "공급처 미지정"),
                    "pending_count": 0,
                    "pending_quantity": 0,
                    "pending_amount": 0,
                    "today_count": 0,
                    "total_count": 0,
                    "purchase_rounds": set(),
                },
            )
            bucket["pending_count"] += 1
            bucket["pending_quantity"] += int(
                item.get("purchase_quantity") or item.get("quantity") or 0
            )
            bucket["pending_amount"] += int(item.get("item_amount") or 0)
            bucket["purchase_rounds"].add(
                str(item.get("purchase_round") or "기본")
            )

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    po.supplier_id,
                    COALESCE(NULLIF(TRIM(po.supplier_name), ''), s.supplier_name, '공급처 미지정') AS supplier_name,
                    COUNT(*) AS total_count,
                    SUM(
                        CASE
                            WHEN DATE(COALESCE(po.purchased_at, po.created_at)) = DATE('now', 'localtime')
                            THEN 1 ELSE 0
                        END
                    ) AS today_count
                FROM purchase_orders AS po
                LEFT JOIN suppliers AS s ON s.id = po.supplier_id
                WHERE po.purchase_status != '발주취소'
                GROUP BY po.supplier_id, COALESCE(NULLIF(TRIM(po.supplier_name), ''), s.supplier_name, '공급처 미지정')
                """
            ).fetchall()

        for row in rows:
            supplier_id = int(row["supplier_id"] or 0)
            bucket = grouped.setdefault(
                supplier_id,
                {
                    "supplier_id": supplier_id,
                    "supplier_name": str(row["supplier_name"] or "공급처 미지정"),
                    "pending_count": 0,
                    "pending_quantity": 0,
                    "pending_amount": 0,
                    "today_count": 0,
                    "total_count": 0,
                    "purchase_rounds": set(),
                },
            )
            bucket["today_count"] = int(row["today_count"] or 0)
            bucket["total_count"] = int(row["total_count"] or 0)

        result: list[dict[str, Any]] = []
        for bucket in grouped.values():
            bucket["purchase_rounds"] = ", ".join(
                sorted(bucket["purchase_rounds"])
            )
            result.append(bucket)

        return sorted(result, key=lambda row: str(row["supplier_name"]))

    # =========================================================
    # 대시보드 요약
    # =========================================================

    def get_dashboard_summary(self) -> dict[str, int]:
        """발주관리 상단 KPI에 사용할 집계값을 반환합니다."""
        candidates = self.get_purchase_candidates()
        supplier_count = len({
            int(row["supplier_id"])
            for row in candidates
            if row.get("supplier_id") is not None
        })

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_count,
                    SUM(
                        CASE
                            WHEN date(COALESCE(purchased_at, created_at)) = date('now', 'localtime')
                            THEN 1 ELSE 0
                        END
                    ) AS today_count
                FROM purchase_orders
                """
            ).fetchone()

        return {
            "pending_count": len(candidates),
            "today_count": int(row["today_count"] or 0) if row else 0,
            "total_count": int(row["total_count"] or 0) if row else 0,
            "supplier_count": supplier_count,
        }

    # =========================================================
    # 조회용
    # =========================================================

    def get_purchase_orders(
        self,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    po.*,
                    o.platform,
                    o.ordered_at,
                    s.supplier_code

                FROM purchase_orders AS po

                INNER JOIN orders AS o
                    ON o.id = po.order_id

                LEFT JOIN suppliers AS s
                    ON s.id = po.supplier_id

                ORDER BY
                    po.created_at DESC,
                    po.id DESC
                """
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # =========================================================
    # 공통 함수
    # =========================================================


    @staticmethod
    def _option_unit_multiplier(
        option_name: Any,
    ) -> int:
        """
        옵션 문자열에서 실제 구성 수량을 추출합니다.

        예:
        - "1개 500g" -> 1
        - "2개 500g" -> 2
        - "3팩" -> 3
        - 수량 표현 없음 -> 1

        무게·용량 숫자(500g, 1kg 등)는 수량으로 보지 않습니다.
        """
        if option_name in (None, ""):
            return 1

        text = str(option_name).strip()

        if not text:
            return 1

        patterns = (
            r"(?<!\d)(\d+)\s*(?:개|팩|봉|박스|세트)\s*입\b",
            r"(?<!\d)(\d+)\s*(?:개|팩|봉|박스|세트)(?![가-힣])",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match is not None:
                value = int(match.group(1))

                if value > 0:
                    return value

        return 1

    @classmethod
    def _purchase_quantity(
        cls,
        order_quantity: Any,
        option_name: Any,
    ) -> int:
        try:
            base_quantity = int(order_quantity or 1)
        except (TypeError, ValueError):
            base_quantity = 1

        if base_quantity <= 0:
            base_quantity = 1

        return (
            base_quantity
            * cls._option_unit_multiplier(
                option_name
            )
        )

    @staticmethod
    def _full_address(
        address: Any,
        detail_address: Any,
    ) -> str:
        values = [
            str(value).strip()
            for value in (
                address,
                detail_address,
            )
            if value not in (None, "")
        ]

        return " ".join(values)

    @staticmethod
    def _safe_filename(
        value: str,
    ) -> str:
        cleaned = re.sub(
            r'[\\/:*?"<>|]',
            "_",
            str(value).strip(),
        )

        cleaned = re.sub(
            r"\s+",
            "_",
            cleaned,
        )

        return cleaned or "미지정"