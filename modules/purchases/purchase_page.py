from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from modules.purchases.purchase_service import PurchaseService


class PurchasePage(ttk.Frame):
    """발주대기 및 발주완료 내역을 관리하는 화면입니다."""

    def __init__(
        self,
        parent: tk.Misc,
        purchase_service: PurchaseService | None = None,
    ) -> None:
        super().__init__(parent)

        self.purchase_service = (
            purchase_service or PurchaseService()
        )

        self.candidates: list[dict[str, Any]] = []
        self.purchase_orders: list[dict[str, Any]] = []

        self.status_var = tk.StringVar(
            value="발주대기 데이터를 불러오는 중입니다."
        )
        self.supplier_filter_var = tk.StringVar(
            value="전체"
        )
        self.search_var = tk.StringVar()
        self.view_mode_var = tk.StringVar(
            value="발주대기"
        )

        self._build_ui()
        self.refresh()

    # =========================================================
    # 화면 구성
    # =========================================================

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
        self._build_filter_area()
        self._build_tree_area()
        self._build_bottom_area()

    def _build_header(self) -> None:
        header_frame = ttk.Frame(
            self,
            padding=(
                20,
                18,
                20,
                10,
            ),
        )
        header_frame.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        header_frame.columnconfigure(
            0,
            weight=1,
        )

        title_label = ttk.Label(
            header_frame,
            text="발주관리",
            font=(
                "맑은 고딕",
                18,
                "bold",
            ),
        )
        title_label.grid(
            row=0,
            column=0,
            sticky="w",
        )

        self.summary_label = ttk.Label(
            header_frame,
            text="발주대기 0건",
            font=(
                "맑은 고딕",
                10,
            ),
        )
        self.summary_label.grid(
            row=1,
            column=0,
            pady=(
                5,
                0,
            ),
            sticky="w",
        )

        refresh_button = ttk.Button(
            header_frame,
            text="새로고침",
            command=self.refresh,
        )
        refresh_button.grid(
            row=0,
            column=1,
            rowspan=2,
            padx=(
                10,
                0,
            ),
            sticky="e",
        )

    def _build_filter_area(self) -> None:
        filter_frame = ttk.LabelFrame(
            self,
            text="조회 조건",
            padding=12,
        )
        filter_frame.grid(
            row=1,
            column=0,
            padx=20,
            pady=(
                0,
                10,
            ),
            sticky="ew",
        )

        filter_frame.columnconfigure(
            5,
            weight=1,
        )

        ttk.Label(
            filter_frame,
            text="화면",
        ).grid(
            row=0,
            column=0,
            padx=(
                0,
                5,
            ),
        )

        self.view_mode_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.view_mode_var,
            values=[
                "발주대기",
                "발주완료",
            ],
            state="readonly",
            width=12,
        )
        self.view_mode_combo.grid(
            row=0,
            column=1,
            padx=(
                0,
                16,
            ),
        )
        self.view_mode_combo.bind(
            "<<ComboboxSelected>>",
            self._on_view_mode_changed,
        )

        ttk.Label(
            filter_frame,
            text="공급처",
        ).grid(
            row=0,
            column=2,
            padx=(
                0,
                5,
            ),
        )

        self.supplier_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.supplier_filter_var,
            values=[
                "전체",
            ],
            state="readonly",
            width=18,
        )
        self.supplier_combo.grid(
            row=0,
            column=3,
            padx=(
                0,
                16,
            ),
        )
        self.supplier_combo.bind(
            "<<ComboboxSelected>>",
            self._on_filter_changed,
        )

        ttk.Label(
            filter_frame,
            text="검색",
        ).grid(
            row=0,
            column=4,
            padx=(
                0,
                5,
            ),
        )

        search_entry = ttk.Entry(
            filter_frame,
            textvariable=self.search_var,
        )
        search_entry.grid(
            row=0,
            column=5,
            sticky="ew",
        )
        search_entry.bind(
            "<KeyRelease>",
            self._on_filter_changed,
        )

    def _build_tree_area(self) -> None:
        tree_frame = ttk.Frame(
            self,
            padding=(
                20,
                0,
                20,
                0,
            ),
        )
        tree_frame.grid(
            row=2,
            column=0,
            sticky="nsew",
        )

        tree_frame.columnconfigure(
            0,
            weight=1,
        )
        tree_frame.rowconfigure(
            0,
            weight=1,
        )

        columns = (
            "supplier_name",
            "purchase_round",
            "order_number",
            "product_name",
            "option_name",
            "quantity",
            "receiver_name",
            "receiver_phone",
            "purchase_status",
            "created_at",
        )

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )

        headings = {
            "supplier_name": "공급처",
            "purchase_round": "발주차수",
            "order_number": "주문번호",
            "product_name": "상품명",
            "option_name": "옵션",
            "quantity": "수량",
            "receiver_name": "수령인",
            "receiver_phone": "연락처",
            "purchase_status": "발주상태",
            "created_at": "생성일시",
        }

        widths = {
            "supplier_name": 120,
            "purchase_round": 90,
            "order_number": 140,
            "product_name": 220,
            "option_name": 170,
            "quantity": 65,
            "receiver_name": 90,
            "receiver_phone": 120,
            "purchase_status": 90,
            "created_at": 145,
        }

        center_columns = {
            "purchase_round",
            "quantity",
            "receiver_name",
            "receiver_phone",
            "purchase_status",
            "created_at",
        }

        for column in columns:
            self.tree.heading(
                column,
                text=headings[column],
            )
            self.tree.column(
                column,
                width=widths[column],
                minwidth=55,
                anchor=(
                    "center"
                    if column in center_columns
                    else "w"
                ),
            )

        vertical_scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
        )
        horizontal_scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=vertical_scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set,
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        vertical_scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )
        horizontal_scrollbar.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        self.tree.bind(
            "<Double-1>",
            self._on_tree_double_click,
        )

    def _build_bottom_area(self) -> None:
        bottom_frame = ttk.Frame(
            self,
            padding=(
                20,
                12,
                20,
                18,
            ),
        )
        bottom_frame.grid(
            row=3,
            column=0,
            sticky="ew",
        )

        bottom_frame.columnconfigure(
            0,
            weight=1,
        )

        status_label = ttk.Label(
            bottom_frame,
            textvariable=self.status_var,
        )
        status_label.grid(
            row=0,
            column=0,
            sticky="w",
        )

        self.open_folder_button = ttk.Button(
            bottom_frame,
            text="발주서 폴더 열기",
            command=self.open_purchase_folder,
        )
        self.open_folder_button.grid(
            row=0,
            column=1,
            padx=(
                8,
                0,
            ),
        )

        self.create_button = ttk.Button(
            bottom_frame,
            text="전체 발주서 생성",
            command=self.create_purchase_files,
        )

        self.selected_button = ttk.Button(
            bottom_frame,
            text="선택 발주",
            command=self.create_selected_purchase_files,
        )

        self.selected_button.grid(
            row=0,
            column=3,
            padx=(8, 0),
        )

        self.create_button.grid(
            row=0,
            column=2,
            padx=(
                8,
                0,
            ),
        )

    # =========================================================
    # 조회
    # =========================================================

    def refresh(self) -> None:
        try:
            if self.view_mode_var.get() == "발주완료":
                self.purchase_orders = (
                    self.purchase_service
                    .get_purchase_orders()
                )
            else:
                self.candidates = (
                    self.purchase_service
                    .get_purchase_candidates()
                )

            self._refresh_supplier_filter()
            self._render_tree()

        except Exception as error:
            self.status_var.set(
                "발주 데이터를 불러오지 못했습니다."
            )

            messagebox.showerror(
                "발주관리 오류",
                (
                    "발주 데이터를 불러오는 중 "
                    "오류가 발생했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

    def _refresh_supplier_filter(self) -> None:
        rows = self._get_current_rows()

        supplier_names = sorted(
            {
                str(
                    row.get("supplier_name") or ""
                ).strip()
                for row in rows
                if row.get("supplier_name")
            }
        )

        values = [
            "전체",
            *supplier_names,
        ]

        self.supplier_combo.configure(
            values=values,
        )

        current_supplier = (
            self.supplier_filter_var.get()
        )

        if current_supplier not in values:
            self.supplier_filter_var.set(
                "전체"
            )

    def _render_tree(self) -> None:
        self.tree.delete(
            *self.tree.get_children()
        )

        rows = self._get_filtered_rows()

        for row in rows:
            if self.view_mode_var.get() == "발주완료":
                item_id = str(
                    row.get("id")
                )

                product_name = (
                    row.get("product_name")
                    or ""
                )

                purchase_round = ""
                created_at = (
                    row.get("purchased_at")
                    or row.get("created_at")
                    or ""
                )
            else:
                item_id = str(
                    row.get("order_item_id")
                )

                product_name = (
                    row.get("supplier_product_name")
                    or row.get("product_name")
                    or row.get(
                        "platform_product_name"
                    )
                    or ""
                )

                purchase_round = (
                    row.get("purchase_round")
                    or "기본"
                )
                created_at = (
                    row.get("ordered_at")
                    or ""
                )

            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    row.get("supplier_name") or "",
                    purchase_round,
                    row.get("order_number") or "",
                    product_name,
                    row.get("option_name") or "",
                    row.get("quantity") or 0,
                    row.get("receiver_name") or "",
                    row.get("receiver_phone") or "",
                    row.get("purchase_status") or "",
                    created_at,
                ),
            )

        mode = self.view_mode_var.get()

        self.summary_label.configure(
            text=f"{mode} {len(rows)}건"
        )

        self.status_var.set(
            f"{mode} 목록 {len(rows)}건을 표시했습니다."
        )

        self.create_button.configure(
            state=(
                "normal"
                if mode == "발주대기"
                else "disabled"
            )
        )

        self.selected_button.configure(
            state=(
                "normal"
                if mode == "발주대기"
                else "disabled"
            )
        )

    def _get_current_rows(
        self,
    ) -> list[dict[str, Any]]:
        if self.view_mode_var.get() == "발주완료":
            return self.purchase_orders

        return self.candidates

    def _get_filtered_rows(
        self,
    ) -> list[dict[str, Any]]:
        supplier_filter = (
            self.supplier_filter_var
            .get()
            .strip()
        )

        keyword = (
            self.search_var
            .get()
            .strip()
            .lower()
        )

        filtered_rows: list[
            dict[str, Any]
        ] = []

        for row in self._get_current_rows():
            supplier_name = str(
                row.get("supplier_name") or ""
            ).strip()

            if (
                supplier_filter != "전체"
                and supplier_name
                != supplier_filter
            ):
                continue

            product_name = str(
                row.get("supplier_product_name")
                or row.get("product_name")
                or row.get(
                    "platform_product_name"
                )
                or ""
            )

            search_text = " ".join(
                [
                    supplier_name,
                    str(
                        row.get(
                            "order_number"
                        )
                        or ""
                    ),
                    product_name,
                    str(
                        row.get("option_name")
                        or ""
                    ),
                    str(
                        row.get(
                            "receiver_name"
                        )
                        or ""
                    ),
                    str(
                        row.get(
                            "receiver_phone"
                        )
                        or ""
                    ),
                ]
            ).lower()

            if (
                keyword
                and keyword not in search_text
            ):
                continue

            filtered_rows.append(row)

        return filtered_rows

    # =========================================================
    # 발주서 생성
    # =========================================================

    def create_purchase_files(self) -> None:
        candidates = self._get_filtered_rows()

        if not candidates:
            messagebox.showwarning(
                "발주서 생성",
                "발주 가능한 주문상품이 없습니다.",
                parent=self,
            )
            return

        supplier_count = len(
            {
                candidate.get("supplier_id")
                for candidate in candidates
            }
        )

        confirmed = messagebox.askyesno(
            "발주서 생성 확인",
            (
                f"발주대기 상품 {len(candidates)}건을 "
                f"{supplier_count}개 공급처별로 "
                "발주서 생성하시겠습니까?\n\n"
                "생성 후 해당 상품은 발주완료로 "
                "변경됩니다."
            ),
            parent=self,
        )

        if not confirmed:
            return

        try:
            self.create_button.configure(
                state="disabled"
            )
            self.status_var.set(
                "발주서를 생성하고 있습니다."
            )
            self.update_idletasks()

            result = (
                self.purchase_service
                .create_purchase_files()
            )

            created_count = int(
                result.get(
                    "created_count",
                    0,
                )
            )

            if created_count == 0:
                messagebox.showwarning(
                    "발주 생성 결과",
                    result.get(
                        "message",
                        "발주 가능한 상품이 없습니다.",
                    ),
                    parent=self,
                )
                return

            file_lines = "\n".join(
                Path(file_path).name
                for file_path in result.get(
                    "files",
                    [],
                )
            )

            messagebox.showinfo(
                "발주서 생성 완료",
                (
                    f"발주상품: {created_count}건\n"
                    f"공급처: "
                    f"{result.get('supplier_count', 0)}곳\n\n"
                    f"생성 파일\n{file_lines}"
                ),
                parent=self,
            )

            self.refresh()

        except Exception as error:
            messagebox.showerror(
                "발주서 생성 오류",
                (
                    "발주서 생성 중 오류가 "
                    "발생했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

        finally:
            if (
                self.view_mode_var.get()
                == "발주대기"
            ):
                self.create_button.configure(
                    state="normal"
                )

    def create_selected_purchase_files(self) -> None:
        if self.view_mode_var.get() != "발주대기":
            messagebox.showwarning(
                "선택 발주",
                "발주대기 화면에서만 발주할 수 있습니다.",
                parent=self,
            )
            return

        selected_items = self.tree.selection()

        if not selected_items:
            messagebox.showwarning(
                "선택 발주",
                "발주할 상품을 먼저 선택하세요.",
                parent=self,
            )
            return

        selected_ids = {
            int(item_id)
            for item_id in selected_items
        }

        candidates = [
            candidate
            for candidate in self._get_filtered_rows()
            if int(candidate["order_item_id"])
            in selected_ids
        ]

        if not candidates:
            messagebox.showwarning(
                "선택 발주",
                "선택한 상품의 발주 정보를 찾지 못했습니다.",
                parent=self,
            )
            return

        supplier_count = len(
            {
                candidate.get("supplier_id")
                for candidate in candidates
            }
        )

        supplier_summary: dict[str, int] = {}

        for candidate in candidates:
            supplier_name = str(
                candidate.get("supplier_name")
                or "공급처 미지정"
            )

            supplier_summary[supplier_name] = (
                supplier_summary.get(
                    supplier_name,
                    0,
                )
                + 1
            )

        supplier_lines = "\n".join(
            f"· {supplier_name}: {item_count}건"
            for supplier_name, item_count
            in supplier_summary.items()
        )

        confirmed = messagebox.askyesno(
            "선택 발주 미리보기",
            (
                f"선택한 상품: {len(candidates)}건\n"
                f"공급처: {supplier_count}곳\n\n"
                f"{supplier_lines}\n\n"
                "위 내용으로 발주서를 생성하시겠습니까?\n\n"
                "생성 후 해당 상품은 발주완료로 "
                "변경됩니다."
            ),
            parent=self,
        )

        if not confirmed:
            return

        try:
            self.create_button.configure(
                state="disabled"
            )
            self.selected_button.configure(
                state="disabled"
            )

            self.status_var.set(
                "선택한 상품의 발주서를 생성하고 있습니다."
            )
            self.update_idletasks()

            result = (
                self.purchase_service
                .create_purchase_files(
                    order_item_ids=[
                        int(
                            candidate[
                                "order_item_id"
                            ]
                        )
                        for candidate in candidates
                    ]
                )
            )

            created_count = int(
                result.get(
                    "created_count",
                    0,
                )
            )

            if created_count == 0:
                messagebox.showwarning(
                    "선택 발주 결과",
                    result.get(
                        "message",
                        "발주 가능한 상품이 없습니다.",
                    ),
                    parent=self,
                )
                return

            file_lines = "\n".join(
                Path(file_path).name
                for file_path in result.get(
                    "files",
                    [],
                )
            )

            messagebox.showinfo(
                "선택 발주 완료",
                (
                    f"발주상품: {created_count}건\n"
                    f"공급처: "
                    f"{result.get('supplier_count', 0)}곳\n\n"
                    f"생성 파일\n{file_lines}"
                ),
                parent=self,
            )

            self.refresh()

        except Exception as error:
            messagebox.showerror(
                "선택 발주 오류",
                (
                    "선택 발주서 생성 중 오류가 "
                    "발생했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

        finally:
            if (
                self.view_mode_var.get()
                == "발주대기"
            ):
                self.create_button.configure(
                    state="normal"
                )
                self.selected_button.configure(
                    state="normal"
                )


    # =========================================================
    # 파일 열기
    # =========================================================

    def open_purchase_folder(self) -> None:
        folder_path = Path(
            self.purchase_service.output_root
        )

        folder_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            os.startfile(folder_path)

        except AttributeError:
            messagebox.showinfo(
                "발주서 폴더",
                str(folder_path),
                parent=self,
            )

        except OSError as error:
            messagebox.showerror(
                "폴더 열기 오류",
                (
                    "발주서 폴더를 열지 "
                    "못했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

    def _on_tree_double_click(
        self,
        event: tk.Event,
    ) -> None:
        if self.view_mode_var.get() != "발주완료":
            return

        selected_items = (
            self.tree.selection()
        )

        if not selected_items:
            return

        selected_id = int(
            selected_items[0]
        )

        selected_row = next(
            (
                row
                for row in self.purchase_orders
                if int(row.get("id"))
                == selected_id
            ),
            None,
        )

        if not selected_row:
            return

        purchase_file = selected_row.get(
            "purchase_file"
        )

        if not purchase_file:
            messagebox.showwarning(
                "발주서 열기",
                "저장된 발주서 경로가 없습니다.",
                parent=self,
            )
            return

        file_path = Path(
            str(purchase_file)
        )

        if not file_path.exists():
            messagebox.showwarning(
                "발주서 열기",
                (
                    "발주서 파일을 찾을 수 없습니다.\n\n"
                    f"{file_path}"
                ),
                parent=self,
            )
            return

        try:
            os.startfile(file_path)

        except OSError as error:
            messagebox.showerror(
                "발주서 열기 오류",
                (
                    "발주서 파일을 열지 "
                    "못했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

    # =========================================================
    # 이벤트
    # =========================================================

    def _on_view_mode_changed(
        self,
        event: tk.Event | None = None,
    ) -> None:
        self.supplier_filter_var.set(
            "전체"
        )
        self.search_var.set("")
        self.refresh()

    def _on_filter_changed(
        self,
        event: tk.Event | None = None,
    ) -> None:
        self._render_tree()