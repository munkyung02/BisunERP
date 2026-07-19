from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
from typing import Any

from modules.shipments.shipment_repository import (
    ShipmentRepository,
)
from modules.shipments.shipment_service import (
    ShipmentService,
)
from modules.shipments.export_service import (
    ExportService,
)


class ShipmentPage(ttk.Frame):
    """공급처 송장파일 업로드 및 자동매칭 화면입니다."""

    def __init__(
        self,
        parent: tk.Misc,
    ) -> None:
        super().__init__(parent)

        self.service = ShipmentService()
        self.repository = ShipmentRepository()
        self.export_service = ExportService()

        self.selected_file_path: Path | None = None
        self.preview_result: dict[str, Any] | None = None

        self.supplier_var = tk.StringVar(
            value="해담"
        )
        self.file_path_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="송장파일을 선택해 주세요."
        )

        self._build_ui()
        self.load_saved_shipments()

    def _build_ui(self) -> None:
        self.columnconfigure(
            0,
            weight=1,
        )
        self.rowconfigure(
            2,
            weight=1,
        )

        self._build_header()
        self._build_upload_area()
        self._build_notebook()
        self._build_status_bar()

    def _build_header(self) -> None:
        frame = ttk.Frame(
            self,
            padding=(20, 18, 20, 10),
        )
        frame.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        frame.columnconfigure(
            0,
            weight=1,
        )

        ttk.Label(
            frame,
            text="송장관리",
            font=("맑은 고딕", 18, "bold"),
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )

        ttk.Label(
            frame,
            text=(
                "공급처 송장 회신파일을 업로드하고 "
                "발주내역과 자동으로 연결합니다."
            ),
        ).grid(
            row=1,
            column=0,
            pady=(5, 0),
            sticky="w",
        )

        ttk.Button(
            frame,
            text="저장목록 새로고침",
            command=self.load_saved_shipments,
        ).grid(
            row=0,
            column=1,
            rowspan=2,
            sticky="e",
        )

    def _build_upload_area(self) -> None:
        frame = ttk.LabelFrame(
            self,
            text="공급처 송장파일",
            padding=14,
        )
        frame.grid(
            row=1,
            column=0,
            padx=20,
            pady=(0, 12),
            sticky="ew",
        )

        frame.columnconfigure(
            3,
            weight=1,
        )

        ttk.Label(
            frame,
            text="공급처",
        ).grid(
            row=0,
            column=0,
            padx=(0, 8),
        )

        supplier_combo = ttk.Combobox(
            frame,
            textvariable=self.supplier_var,
            values=list(
                self.service
                .SUPPLIER_PROFILES
                .keys()
            ),
            state="readonly",
            width=15,
        )
        supplier_combo.grid(
            row=0,
            column=1,
            padx=(0, 14),
        )

        ttk.Button(
            frame,
            text="엑셀 선택",
            command=self.select_file,
        ).grid(
            row=0,
            column=2,
            padx=(0, 8),
        )

        ttk.Entry(
            frame,
            textvariable=self.file_path_var,
            state="readonly",
        ).grid(
            row=0,
            column=3,
            sticky="ew",
        )

        ttk.Button(
            frame,
            text="파일 분석",
            command=self.preview_file,
        ).grid(
            row=0,
            column=4,
            padx=(8, 0),
        )

        self.save_button = ttk.Button(
            frame,
            text="매칭 송장 저장",
            command=self.save_matched_shipments,
            state="disabled",
        )
        self.save_button.grid(
            row=0,
            column=5,
            padx=(8, 0),
        )

        ttk.Button(
            frame,
            text="쿠팡 송장등록파일 생성",
            command=self.export_coupang_file,
        ).grid(
            row=0,
            column=6,
            padx=(8, 0),
        )

    def _build_notebook(self) -> None:
        notebook = ttk.Notebook(
            self
        )
        notebook.grid(
            row=2,
            column=0,
            padx=20,
            pady=(0, 10),
            sticky="nsew",
        )

        preview_frame = ttk.Frame(
            notebook
        )
        saved_frame = ttk.Frame(
            notebook
        )

        notebook.add(
            preview_frame,
            text="업로드 미리보기",
        )
        notebook.add(
            saved_frame,
            text="저장된 송장",
        )

        self._build_preview_tree(
            preview_frame
        )
        self._build_saved_tree(
            saved_frame
        )

    def _build_preview_tree(
        self,
        parent: ttk.Frame,
    ) -> None:
        parent.columnconfigure(
            0,
            weight=1,
        )
        parent.rowconfigure(
            0,
            weight=1,
        )

        columns = (
            "excel_row",
            "match_status",
            "receiver_name",
            "receiver_phone",
            "product_name",
            "quantity",
            "carrier",
            "tracking_number",
            "order_number",
            "message",
        )

        self.preview_tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
        )

        headers = {
            "excel_row": "행",
            "match_status": "매칭상태",
            "receiver_name": "수취인",
            "receiver_phone": "전화번호",
            "product_name": "공급처 품목",
            "quantity": "수량",
            "carrier": "택배사",
            "tracking_number": "송장번호",
            "order_number": "주문번호",
            "message": "확인사항",
        }

        widths = {
            "excel_row": 50,
            "match_status": 90,
            "receiver_name": 90,
            "receiver_phone": 120,
            "product_name": 190,
            "quantity": 55,
            "carrier": 100,
            "tracking_number": 150,
            "order_number": 145,
            "message": 250,
        }

        for column in columns:
            self.preview_tree.heading(
                column,
                text=headers[column],
            )
            self.preview_tree.column(
                column,
                width=widths[column],
            )

        scrollbar = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=self.preview_tree.yview,
        )
        self.preview_tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.preview_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

    def _build_saved_tree(
        self,
        parent: ttk.Frame,
    ) -> None:
        parent.columnconfigure(
            0,
            weight=1,
        )
        parent.rowconfigure(
            0,
            weight=1,
        )

        columns = (
            "supplier_name",
            "order_number",
            "receiver_name",
            "product_name",
            "quantity",
            "courier_name",
            "tracking_number",
            "shipment_status",
            "shipped_at",
        )

        self.saved_tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
        )

        headers = {
            "supplier_name": "공급처",
            "order_number": "주문번호",
            "receiver_name": "수취인",
            "product_name": "상품명",
            "quantity": "수량",
            "courier_name": "택배사",
            "tracking_number": "송장번호",
            "shipment_status": "배송상태",
            "shipped_at": "등록일시",
        }

        widths = {
            "supplier_name": 90,
            "order_number": 150,
            "receiver_name": 90,
            "product_name": 220,
            "quantity": 55,
            "courier_name": 100,
            "tracking_number": 160,
            "shipment_status": 80,
            "shipped_at": 150,
        }

        for column in columns:
            self.saved_tree.heading(
                column,
                text=headers[column],
            )
            self.saved_tree.column(
                column,
                width=widths[column],
            )

        scrollbar = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=self.saved_tree.yview,
        )
        self.saved_tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.saved_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

    def _build_status_bar(self) -> None:
        ttk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            padding=(20, 8),
            relief="sunken",
        ).grid(
            row=3,
            column=0,
            sticky="ew",
        )

    def select_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="공급처 송장 엑셀 선택",
            filetypes=[
                (
                    "엑셀 파일",
                    "*.xlsx *.xlsm",
                ),
                (
                    "모든 파일",
                    "*.*",
                ),
            ],
        )

        if not selected:
            return

        self.selected_file_path = Path(
            selected
        )
        self.file_path_var.set(
            selected
        )
        self.preview_result = None
        self.save_button.configure(
            state="disabled"
        )

        self.status_var.set(
            "파일이 선택되었습니다. 파일 분석을 눌러주세요."
        )

    def preview_file(self) -> None:
        if self.selected_file_path is None:
            messagebox.showwarning(
                "파일 선택",
                "먼저 송장 엑셀파일을 선택해 주세요.",
            )
            return

        supplier_name = (
            self.supplier_var.get().strip()
        )

        try:
            result = (
                self.service
                .preview_supplier_shipment_file(
                    file_path=self.selected_file_path,
                    supplier_name=supplier_name,
                )
            )

        except Exception as error:
            messagebox.showerror(
                "송장파일 분석 오류",
                "송장파일을 분석하지 못했습니다.\n\n"
                f"{error}",
            )
            return

        self.preview_result = result
        self._display_preview_result(
            result
        )

        self.save_button.configure(
            state=(
                "normal"
                if result["matched_count"] > 0
                else "disabled"
            )
        )

        self.status_var.set(
            (
                f"전체 {result['total_count']}건 · "
                f"매칭 {result['matched_count']}건 · "
                f"미매칭 {result['unmatched_count']}건 · "
                f"중복후보 {result['ambiguous_count']}건 · "
                f"기등록 {result['duplicate_count']}건 · "
                f"파일오류 {result['error_count']}건"
            )
        )

    def _display_preview_result(
        self,
        result: dict[str, Any],
    ) -> None:
        for item_id in (
            self.preview_tree.get_children()
        ):
            self.preview_tree.delete(
                item_id
            )

        status_texts = {
            "matched": "매칭성공",
            "unmatched": "미매칭",
            "ambiguous": "중복후보",
            "duplicate": "기등록",
        }

        for index, match_result in enumerate(
            result["match_results"]
        ):
            shipment = match_result[
                "shipment"
            ]
            match_status = match_result[
                "status"
            ]

            candidate = match_result.get(
                "candidate",
                {},
            )

            message = ""

            if match_status == "unmatched":
                message = (
                    "일치하는 발주내역 없음"
                )

            elif match_status == "ambiguous":
                message = (
                    f"후보 "
                    f"{len(match_result['candidates'])}건"
                )

            elif match_status == "duplicate":
                message = (
                    "이미 등록된 송장번호"
                )

            self.preview_tree.insert(
                "",
                "end",
                iid=f"match-{index}",
                values=(
                    shipment.get("excel_row", ""),
                    status_texts.get(
                        match_status,
                        match_status,
                    ),
                    shipment.get(
                        "receiver_name",
                        "",
                    ),
                    shipment.get(
                        "receiver_phone",
                        "",
                    ),
                    shipment.get(
                        "product_name",
                        "",
                    ),
                    shipment.get(
                        "quantity",
                        "",
                    ),
                    shipment.get(
                        "carrier",
                        "",
                    ),
                    shipment.get(
                        "tracking_number",
                        "",
                    ),
                    candidate.get(
                        "order_number",
                        "",
                    ),
                    message,
                ),
            )

        for error in result["errors"]:
            self.preview_tree.insert(
                "",
                "end",
                values=(
                    error.get(
                        "excel_row",
                        "",
                    ),
                    "파일오류",
                    error.get(
                        "receiver_name",
                        "",
                    ),
                    error.get(
                        "receiver_phone",
                        "",
                    ),
                    error.get(
                        "product_name",
                        "",
                    ),
                    error.get(
                        "quantity",
                        "",
                    ),
                    error.get(
                        "carrier",
                        "",
                    ),
                    error.get(
                        "tracking_number",
                        "",
                    ),
                    "",
                    error.get(
                        "error_message",
                        "",
                    ),
                ),
            )

    def save_matched_shipments(self) -> None:
        if self.preview_result is None:
            messagebox.showwarning(
                "분석 필요",
                "먼저 송장파일을 분석해 주세요.",
            )
            return

        matched_count = self.preview_result[
            "matched_count"
        ]

        if matched_count <= 0:
            messagebox.showwarning(
                "저장 대상 없음",
                "자동매칭에 성공한 송장이 없습니다.",
            )
            return

        answer = messagebox.askyesno(
            "송장 저장 확인",
            (
                f"자동매칭된 송장 "
                f"{matched_count}건을 저장하시겠습니까?"
            ),
        )

        if not answer:
            return

        try:
            result = (
                self.service
                .save_matched_shipments(
                    self.preview_result[
                        "match_results"
                    ]
                )
            )

        except Exception as error:
            messagebox.showerror(
                "송장 저장 오류",
                "송장을 저장하지 못했습니다.\n\n"
                f"{error}",
            )
            return

        messagebox.showinfo(
            "송장 저장 완료",
            (
                f"저장 완료: "
                f"{result['saved_count']}건\n"
                f"건너뜀: "
                f"{result['skipped_count']}건\n"
                f"오류: "
                f"{result['error_count']}건"
            ),
        )

        self.save_button.configure(
            state="disabled"
        )

        self.load_saved_shipments()

    def export_coupang_file(self):

        file_path = filedialog.askopenfilename(
            title="쿠팡 Delivery 파일 선택",
            filetypes=[
                ("Excel","*.xlsx *.xlsm"),
            ],
        )

        if not file_path:
            return

        try:

            result = (
                self.export_service
                .export_coupang_delivery_file(
                    file_path
                )
            )

        except Exception as error:

            messagebox.showerror(
                "생성 실패",
                str(error),
            )

            return

        messagebox.showinfo(
            "완료",
            f"""
        쿠팡 송장등록 파일 생성 완료

        매칭 : {result['matched_count']}건
        미매칭 : {result['unmatched_count']}건

        저장위치

        {result['output_file_path']}
        """
        )

    def load_saved_shipments(self) -> None:
        try:
            shipments = (
                self.repository.get_shipments()
            )

        except Exception as error:
            messagebox.showerror(
                "송장 조회 오류",
                "저장된 송장을 불러오지 못했습니다.\n\n"
                f"{error}",
            )
            return

        for item_id in (
            self.saved_tree.get_children()
        ):
            self.saved_tree.delete(
                item_id
            )

        for shipment in shipments:
            self.saved_tree.insert(
                "",
                "end",
                values=(
                    shipment.get(
                        "supplier_name",
                        "",
                    ),
                    shipment.get(
                        "order_number",
                        "",
                    ),
                    shipment.get(
                        "receiver_name",
                        "",
                    ),
                    shipment.get(
                        "product_name",
                        "",
                    ),
                    shipment.get(
                        "quantity",
                        "",
                    ),
                    shipment.get(
                        "courier_name",
                        "",
                    ),
                    shipment.get(
                        "tracking_number",
                        "",
                    ),
                    shipment.get(
                        "shipment_status",
                        "",
                    ),
                    shipment.get(
                        "shipped_at",
                        "",
                    ),
                ),
            )

        self.status_var.set(
            f"저장된 송장 {len(shipments):,}건"
        )