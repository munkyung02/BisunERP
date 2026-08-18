from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from modules.purchases.purchase_service import PurchaseService


class DeadlinePurchaseConfirmDialog(tk.Toplevel):
    """시간대별 발주 대상의 최종 수동 확인 창입니다."""

    @staticmethod
    def summarize_candidates(
        candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int, int]:
        grouped: dict[int, dict[str, Any]] = {}
        for item in candidates:
            supplier_id = int(item["supplier_id"])
            bucket = grouped.setdefault(
                supplier_id,
                {
                    "supplier_name": str(item.get("supplier_name") or ""),
                    "count": 0,
                    "quantity": 0,
                    "amount": 0,
                },
            )
            bucket["count"] += 1
            bucket["quantity"] += int(
                item.get("purchase_quantity") or item.get("quantity") or 0
            )
            bucket["amount"] += int(item.get("item_amount") or 0)
        rows = sorted(grouped.values(), key=lambda value: value["supplier_name"])
        return (
            rows,
            sum(int(row["quantity"]) for row in rows),
            sum(int(row["amount"]) for row in rows),
        )

    def __init__(
        self,
        parent: tk.Misc,
        deadline: str,
        candidates: list[dict[str, Any]],
    ) -> None:
        super().__init__(parent)
        self.result = False
        self.title(f"{deadline} 발주 대상 확인")
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(True, True)

        supplier_rows, total_quantity, total_amount = self.summarize_candidates(candidates)
        summary = ttk.LabelFrame(self, text="발주 요약", padding=12)
        summary.pack(fill="x", padx=16, pady=(16, 8))
        ttk.Label(
            summary,
            text=(
                f"발주마감: {deadline}    공급처: {len(supplier_rows):,}곳    "
                f"주문상품: {len(candidates):,}건    총 수량: {total_quantity:,}개    "
                f"총 상품금액: {total_amount:,}원"
            ),
            font=("맑은 고딕", 10, "bold"),
        ).pack(anchor="w")

        tree = ttk.Treeview(
            self,
            columns=("supplier", "count", "quantity", "amount"),
            show="headings",
            height=max(4, min(12, len(supplier_rows))),
        )
        for column, text, width, anchor in (
            ("supplier", "공급처", 220, "w"),
            ("count", "건수", 90, "center"),
            ("quantity", "수량", 100, "center"),
            ("amount", "금액", 140, "e"),
        ):
            tree.heading(column, text=text)
            tree.column(column, width=width, anchor=anchor)
        for row in supplier_rows:
            tree.insert(
                "",
                "end",
                values=(
                    row["supplier_name"],
                    f"{int(row['count']):,}건",
                    f"{int(row['quantity']):,}개",
                    f"{int(row['amount']):,}원",
                ),
            )
        tree.pack(fill="both", expand=True, padx=16, pady=8)

        buttons = ttk.Frame(self, padding=(16, 8, 16, 16))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="취소", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text=f"{deadline} 발주서 생성",
            command=self._confirm,
        ).pack(side="right", padx=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_visibility()
        self.focus_set()
        self.wait_window(self)

    def _confirm(self) -> None:
        self.result = True
        self.destroy()


class PurchasePage(ttk.Frame):
    """발주대기 및 발주완료 내역을 관리하는 화면입니다."""

    PURCHASE_DEADLINES = ("09:00", "09:30", "12:00", "13:00", "14:00")

    def __init__(
        self,
        parent: tk.Misc,
        purchase_service: PurchaseService | None = None,
    ) -> None:
        super().__init__(parent)

        self.purchase_service = purchase_service or PurchaseService()
        self.candidates: list[dict[str, Any]] = []
        self.purchase_orders: list[dict[str, Any]] = []
        self.supplier_summaries: list[dict[str, Any]] = []

        self.status_var = tk.StringVar(
            value="발주 데이터를 불러오는 중입니다."
        )
        self.supplier_filter_var = tk.StringVar(value="전체")
        self.search_var = tk.StringVar()
        self.view_mode_var = tk.StringVar(value="발주대기")
        self.history_period_var = tk.StringVar(value="최근 7일")

        self.kpi_pending_var = tk.StringVar(value="0건")
        self.kpi_today_var = tk.StringVar(value="0건")
        self.kpi_total_var = tk.StringVar(value="0건")
        self.kpi_supplier_var = tk.StringVar(value="0곳")
        self.deadline_warning_var = tk.StringVar(value="발주마감시간 확인 중")
        self.deadline_buttons: dict[str, ttk.Button] = {}

        self._build_ui()
        self.history_period_combo.configure(state="disabled")
        self.refresh()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)

        self._build_header()
        self._build_kpi_area()
        self._build_deadline_area()
        self._build_filter_area()
        self._build_supplier_center()
        self._build_tree_area()
        self._build_bottom_area()

    def _build_header(self) -> None:
        frame = ttk.Frame(self, padding=(20, 18, 20, 10))
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text="발주관리",
            font=("맑은 고딕", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.summary_label = ttk.Label(
            frame,
            text="발주대기 0건",
            font=("맑은 고딕", 10),
        )
        self.summary_label.grid(
            row=1,
            column=0,
            pady=(5, 0),
            sticky="w",
        )

        ttk.Button(
            frame,
            text="새로고침",
            command=self.refresh,
        ).grid(
            row=0,
            column=1,
            rowspan=2,
            padx=(10, 0),
            sticky="e",
        )

    def _build_kpi_area(self) -> None:
        frame = ttk.Frame(self, padding=(20, 0, 20, 10))
        frame.grid(row=1, column=0, sticky="ew")

        cards = [
            ("발주대기", self.kpi_pending_var),
            ("오늘 발주", self.kpi_today_var),
            ("전체 발주", self.kpi_total_var),
            ("대기 공급처", self.kpi_supplier_var),
        ]

        for index, (title, variable) in enumerate(cards):
            frame.columnconfigure(index, weight=1)
            card = ttk.LabelFrame(
                frame,
                text=title,
                padding=(18, 10),
            )
            card.grid(
                row=0,
                column=index,
                padx=(0 if index == 0 else 6, 0),
                sticky="ew",
            )
            ttk.Label(
                card,
                textvariable=variable,
                font=("맑은 고딕", 15, "bold"),
            ).pack(anchor="w")

    def _build_deadline_area(self) -> None:
        frame = ttk.LabelFrame(
            self,
            text="발주 마감시간",
            padding=12,
        )
        frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        frame.columnconfigure(len(self.PURCHASE_DEADLINES), weight=1)

        for column, deadline in enumerate(self.PURCHASE_DEADLINES):
            button = ttk.Button(
                frame,
                text=f"{deadline} 발주 (0건)",
                command=lambda value=deadline: self.create_deadline_purchase_files(value),
            )
            button.grid(row=0, column=column, padx=(0, 8), sticky="w")
            self.deadline_buttons[deadline] = button

        self.deadline_warning_label = tk.Label(
            frame,
            textvariable=self.deadline_warning_var,
            anchor="w",
            fg="#9A3412",
            bg="#FFF7ED",
            padx=10,
            pady=6,
        )
        self.deadline_warning_label.grid(
            row=1,
            column=0,
            columnspan=len(self.PURCHASE_DEADLINES) + 1,
            pady=(10, 0),
            sticky="ew",
        )

    def _build_filter_area(self) -> None:
        frame = ttk.LabelFrame(
            self,
            text="조회 조건",
            padding=12,
        )
        frame.grid(
            row=3,
            column=0,
            padx=20,
            pady=(0, 10),
            sticky="ew",
        )
        frame.columnconfigure(7, weight=1)

        ttk.Label(frame, text="화면").grid(row=0, column=0, padx=(0, 5))
        self.view_mode_combo = ttk.Combobox(
            frame,
            textvariable=self.view_mode_var,
            values=["발주대기", "발주완료"],
            state="readonly",
            width=12,
        )
        self.view_mode_combo.grid(row=0, column=1, padx=(0, 16))
        self.view_mode_combo.bind(
            "<<ComboboxSelected>>",
            self._on_view_mode_changed,
        )

        ttk.Label(frame, text="공급처").grid(row=0, column=2, padx=(0, 5))
        self.supplier_combo = ttk.Combobox(
            frame,
            textvariable=self.supplier_filter_var,
            values=["전체"],
            state="readonly",
            width=18,
        )
        self.supplier_combo.grid(row=0, column=3, padx=(0, 16))
        self.supplier_combo.bind(
            "<<ComboboxSelected>>",
            self._on_filter_changed,
        )

        ttk.Label(frame, text="기간").grid(row=0, column=4, padx=(0, 5))
        self.history_period_combo = ttk.Combobox(
            frame,
            textvariable=self.history_period_var,
            values=["오늘", "최근 7일", "최근 30일", "전체"],
            state="readonly",
            width=11,
        )
        self.history_period_combo.grid(row=0, column=5, padx=(0, 16))
        self.history_period_combo.bind(
            "<<ComboboxSelected>>",
            self._on_filter_changed,
        )

        ttk.Label(frame, text="검색").grid(row=0, column=6, padx=(0, 5))
        search = ttk.Entry(frame, textvariable=self.search_var)
        search.grid(row=0, column=7, sticky="ew")
        search.bind("<KeyRelease>", self._on_filter_changed)


    def _build_supplier_center(self) -> None:
        frame = ttk.LabelFrame(
            self,
            text="공급처별 발주 현황",
            padding=10,
        )
        frame.grid(
            row=4,
            column=0,
            padx=20,
            pady=(0, 10),
            sticky="ew",
        )
        frame.columnconfigure(0, weight=1)

        columns = (
            "supplier_name",
            "pending_count",
            "pending_quantity",
            "today_count",
            "total_count",
            "pending_amount",
            "purchase_rounds",
        )
        self.supplier_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            height=5,
            selectmode="browse",
        )
        headings = {
            "supplier_name": "공급처",
            "pending_count": "발주대기",
            "pending_quantity": "대기수량",
            "today_count": "오늘 발주",
            "total_count": "누적 발주",
            "pending_amount": "대기 상품금액",
            "purchase_rounds": "발주차수",
        }
        widths = {
            "supplier_name": 170,
            "pending_count": 80,
            "pending_quantity": 80,
            "today_count": 80,
            "total_count": 80,
            "pending_amount": 120,
            "purchase_rounds": 160,
        }
        for column in columns:
            self.supplier_tree.heading(column, text=headings[column])
            self.supplier_tree.column(
                column,
                width=widths[column],
                anchor="w" if column in {"supplier_name", "purchase_rounds"} else "center",
            )
        self.supplier_tree.grid(row=0, column=0, rowspan=3, sticky="ew")
        self.supplier_tree.bind("<<TreeviewSelect>>", self._on_supplier_selected)

        self.supplier_purchase_button = ttk.Button(
            frame,
            text="선택 공급처 발주",
            command=self.create_selected_supplier_purchase_files,
        )
        self.supplier_purchase_button.grid(row=0, column=1, padx=(10, 0), sticky="ew")

        ttk.Button(
            frame,
            text="공급처 필터 해제",
            command=self._clear_supplier_selection,
        ).grid(row=1, column=1, padx=(10, 0), pady=(6, 0), sticky="ew")

        ttk.Label(
            frame,
            text="공급처를 선택하면 아래 주문상품 목록도 같이 좁혀집니다.",
            wraplength=190,
        ).grid(row=2, column=1, padx=(10, 0), pady=(8, 0), sticky="nw")

    def _build_tree_area(self) -> None:
        frame = ttk.Frame(self, padding=(20, 0, 20, 0))
        frame.grid(row=5, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        columns = (
            "supplier_name",
            "purchase_round",
            "order_number",
            "supplier_product_code",
            "product_name",
            "option_name",
            "quantity",
            "unit_price",
            "item_amount",
            "shipping_fee",
            "carrier",
            "purchase_status",
            "created_at",
        )

        self.tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )

        headings = {
            "supplier_name": "공급처",
            "purchase_round": "발주차수",
            "order_number": "주문번호",
            "supplier_product_code": "공급처 코드",
            "product_name": "공급처 상품명",
            "option_name": "옵션",
            "quantity": "수량",
            "unit_price": "매입단가",
            "item_amount": "상품금액",
            "shipping_fee": "택배비",
            "carrier": "택배사",
            "purchase_status": "상태",
            "created_at": "일시",
        }

        widths = {
            "supplier_name": 120,
            "purchase_round": 85,
            "order_number": 140,
            "supplier_product_code": 110,
            "product_name": 220,
            "option_name": 160,
            "quantity": 65,
            "unit_price": 90,
            "item_amount": 100,
            "shipping_fee": 85,
            "carrier": 100,
            "purchase_status": 90,
            "created_at": 145,
        }

        center_columns = {
            "purchase_round",
            "supplier_product_code",
            "quantity",
            "unit_price",
            "item_amount",
            "shipping_fee",
            "carrier",
            "purchase_status",
            "created_at",
        }

        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=55,
                anchor="center" if column in center_columns else "w",
            )

        y_scroll = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.tree.yview,
        )
        x_scroll = ttk.Scrollbar(
            frame,
            orient="horizontal",
            command=self.tree.xview,
        )
        self.tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Double-1>", self._on_tree_double_click)

    def _build_bottom_area(self) -> None:
        frame = ttk.Frame(self, padding=(20, 12, 20, 18))
        frame.grid(row=6, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            textvariable=self.status_var,
        ).grid(row=0, column=0, sticky="w")

        self.open_folder_button = ttk.Button(
            frame,
            text="발주서 폴더 열기",
            command=self.open_purchase_folder,
        )
        self.open_folder_button.grid(row=0, column=1, padx=(8, 0))

        self.create_button = ttk.Button(
            frame,
            text="조회 목록 전체 발주",
            command=self.create_purchase_files,
        )
        self.create_button.grid(row=0, column=2, padx=(8, 0))

        self.selected_button = ttk.Button(
            frame,
            text="선택 발주",
            command=self.create_selected_purchase_files,
        )
        self.selected_button.grid(row=0, column=3, padx=(8, 0))

    def refresh(self) -> None:
        try:
            self.candidates = self.purchase_service.get_purchase_candidates()
            self.purchase_orders = self.purchase_service.get_purchase_orders()
            self.supplier_summaries = self.purchase_service.get_supplier_purchase_summary()
            self._update_kpi()
            self._refresh_supplier_filter()
            self._render_supplier_center()
            self._refresh_deadline_area()
            self._render_tree()
        except Exception as error:
            self.status_var.set("발주 데이터를 불러오지 못했습니다.")
            messagebox.showerror(
                "발주관리 오류",
                f"발주 데이터를 불러오는 중 오류가 발생했습니다.\n\n{error}",
                parent=self,
            )

    def _refresh_deadline_area(self) -> None:
        pending_mode = self.view_mode_var.get() == "발주대기"
        counts = {deadline: 0 for deadline in self.PURCHASE_DEADLINES}
        missing: list[dict[str, Any]] = []
        for item in self.candidates:
            deadline = item.get("normalized_purchase_deadline")
            if deadline in counts:
                counts[str(deadline)] += 1
            elif deadline is None:
                missing.append(item)

        for deadline, button in self.deadline_buttons.items():
            count = counts[deadline]
            button.configure(
                text=f"{deadline} 발주 ({count:,}건)",
                state="normal" if pending_mode and count > 0 else "disabled",
            )

        if missing:
            names: list[str] = []
            for item in missing:
                name = str(
                    item.get("supplier_product_name")
                    or item.get("product_name")
                    or item.get("platform_product_name")
                    or "상품명 없음"
                ).strip()
                if name and name not in names:
                    names.append(name)
            example = names[0] if names else "상품명 없음"
            suffix = f" 외 {len(names) - 1:,}개 상품" if len(names) > 1 else ""
            self.deadline_warning_var.set(
                f"⚠ 발주마감시간 미설정/오류 {len(missing):,}건 — {example}{suffix}"
            )
            self.deadline_warning_label.configure(fg="#9A3412", bg="#FFF7ED")
        else:
            self.deadline_warning_var.set("발주마감시간 미설정 없음")
            self.deadline_warning_label.configure(fg="#166534", bg="#F0FDF4")

    def create_deadline_purchase_files(self, deadline: str) -> None:
        if self.view_mode_var.get() != "발주대기":
            return
        try:
            candidates = self.purchase_service.get_purchase_candidates_by_deadline(deadline)
        except Exception as error:
            messagebox.showerror(
                "시간대별 발주 조회 오류",
                str(error),
                parent=self,
            )
            return
        if not candidates:
            messagebox.showinfo(
                f"{deadline} 발주",
                "현재 발주 가능한 미발주 주문상품이 없습니다.",
                parent=self,
            )
            self.refresh()
            return

        validation = self._validate_before_purchase(candidates)
        if validation is None:
            return
        dialog = DeadlinePurchaseConfirmDialog(self, deadline, candidates)
        if not dialog.result:
            return
        self._execute_purchase([
            int(item["order_item_id"])
            for item in candidates
        ])

    def _update_kpi(self) -> None:
        summary = self.purchase_service.get_dashboard_summary()
        self.kpi_pending_var.set(
            f"{int(summary.get('pending_count', 0)):,}건"
        )
        self.kpi_today_var.set(
            f"{int(summary.get('today_count', 0)):,}건"
        )
        self.kpi_total_var.set(
            f"{int(summary.get('total_count', 0)):,}건"
        )
        self.kpi_supplier_var.set(
            f"{int(summary.get('supplier_count', 0)):,}곳"
        )

    def _refresh_supplier_filter(self) -> None:
        supplier_names = sorted({
            str(row.get("supplier_name") or "").strip()
            for row in self._get_current_rows()
            if row.get("supplier_name")
        })
        values = ["전체", *supplier_names]
        self.supplier_combo.configure(values=values)

        if self.supplier_filter_var.get() not in values:
            self.supplier_filter_var.set("전체")


    def _render_supplier_center(self) -> None:
        self.supplier_tree.delete(*self.supplier_tree.get_children())

        for index, row in enumerate(self.supplier_summaries, start=1):
            self.supplier_tree.insert(
                "",
                "end",
                iid=f"supplier_{index}",
                values=(
                    row.get("supplier_name") or "공급처 미지정",
                    f"{int(row.get('pending_count') or 0):,}건",
                    f"{int(row.get('pending_quantity') or 0):,}개",
                    f"{int(row.get('today_count') or 0):,}건",
                    f"{int(row.get('total_count') or 0):,}건",
                    f"{int(row.get('pending_amount') or 0):,}원",
                    row.get("purchase_rounds") or "",
                ),
            )

        can_purchase = any(
            int(row.get("pending_count") or 0) > 0
            for row in self.supplier_summaries
        )
        state = (
            "normal"
            if can_purchase and self.view_mode_var.get() == "발주대기"
            else "disabled"
        )
        self.supplier_purchase_button.configure(state=state)

    def _selected_supplier_name(self) -> str | None:
        selected = self.supplier_tree.selection()
        if not selected:
            return None
        values = self.supplier_tree.item(selected[0], "values")
        return str(values[0]).strip() if values else None

    def _on_supplier_selected(self, _event: tk.Event | None = None) -> None:
        supplier_name = self._selected_supplier_name()
        if supplier_name:
            self.supplier_filter_var.set(supplier_name)
            self._render_tree()

    def _clear_supplier_selection(self) -> None:
        self.supplier_tree.selection_remove(self.supplier_tree.selection())
        self.supplier_filter_var.set("전체")
        self._render_tree()

    def create_selected_supplier_purchase_files(self) -> None:
        if self.view_mode_var.get() != "발주대기":
            return

        supplier_name = self._selected_supplier_name()
        if not supplier_name:
            messagebox.showwarning(
                "공급처 발주",
                "먼저 공급처를 선택하세요.",
                parent=self,
            )
            return

        candidates = [
            item for item in self.candidates
            if str(item.get("supplier_name") or "").strip() == supplier_name
        ]
        if not candidates:
            messagebox.showwarning(
                "공급처 발주",
                "선택한 공급처에 발주 가능한 상품이 없습니다.",
                parent=self,
            )
            return

        total_quantity = sum(
            int(item.get("purchase_quantity") or item.get("quantity") or 0)
            for item in candidates
        )
        confirmed = messagebox.askyesno(
            "공급처별 발주 확인",
            (
                f"공급처: {supplier_name}\n"
                f"주문상품: {len(candidates):,}건\n"
                f"총 발주수량: {total_quantity:,}개\n\n"
                "이 공급처의 발주서를 생성하시겠습니까?"
            ),
            parent=self,
        )
        if confirmed:
            self._execute_purchase([int(item["order_item_id"]) for item in candidates])

    def _render_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        rows = self._get_filtered_rows()
        mode = self.view_mode_var.get()

        for row in rows:
            if mode == "발주완료":
                item_id = str(row.get("id"))
                created_at = (
                    row.get("purchased_at")
                    or row.get("created_at")
                    or ""
                )
                unit_price = int(row.get("unit_price") or 0)
                item_amount = int(row.get("item_amount") or 0)
                shipping_fee = int(row.get("shipping_fee") or 0)
            else:
                item_id = str(row.get("order_item_id"))
                created_at = row.get("ordered_at") or ""
                unit_price = int(row.get("unit_price") or 0)
                item_amount = int(row.get("item_amount") or 0)
                shipping_fee = int(row.get("shipping_fee") or 0)

            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    row.get("supplier_name") or "",
                    row.get("purchase_round") or "기본",
                    row.get("order_number") or "",
                    row.get("supplier_product_code") or "",
                    row.get("supplier_product_name")
                    or row.get("product_name")
                    or row.get("platform_product_name")
                    or "",
                    row.get("option_name") or "",
                    int(row.get("purchase_quantity") or row.get("quantity") or 0),
                    f"{unit_price:,}원",
                    f"{item_amount:,}원",
                    f"{shipping_fee:,}원",
                    row.get("carrier") or "",
                    row.get("purchase_status")
                    or ("발주대기" if mode == "발주대기" else ""),
                    created_at,
                ),
            )

        total_quantity = sum(
            int(row.get("purchase_quantity") or row.get("quantity") or 0)
            for row in rows
        )
        total_amount = sum(
            int(row.get("item_amount") or 0)
            for row in rows
        )

        self.summary_label.configure(
            text=(
                f"{mode} {len(rows):,}건 · "
                f"수량 {total_quantity:,}개 · "
                f"상품금액 {total_amount:,}원"
            )
        )
        self.status_var.set(
            f"{mode} 목록 {len(rows):,}건을 표시했습니다."
        )

        state = "normal" if mode == "발주대기" else "disabled"
        self.create_button.configure(state=state)
        self.selected_button.configure(state=state)

    def _get_current_rows(self) -> list[dict[str, Any]]:
        return (
            self.purchase_orders
            if self.view_mode_var.get() == "발주완료"
            else self.candidates
        )

    def _get_filtered_rows(self) -> list[dict[str, Any]]:
        supplier_filter = self.supplier_filter_var.get().strip()
        keyword = self.search_var.get().strip().lower()
        rows: list[dict[str, Any]] = []
        history_period = self.history_period_var.get().strip()

        for row in self._get_current_rows():
            if self.view_mode_var.get() == "발주완료" and history_period != "전체":
                date_text = str(row.get("purchased_at") or row.get("created_at") or "")
                try:
                    purchased_date = datetime.fromisoformat(date_text.replace("Z", "+00:00")).date()
                    today = datetime.now().date()
                    if history_period == "오늘" and purchased_date != today:
                        continue
                    if history_period == "최근 7일" and (today - purchased_date).days > 6:
                        continue
                    if history_period == "최근 30일" and (today - purchased_date).days > 29:
                        continue
                except ValueError:
                    continue
            supplier_name = str(row.get("supplier_name") or "").strip()

            if (
                supplier_filter != "전체"
                and supplier_name != supplier_filter
            ):
                continue

            search_text = " ".join([
                supplier_name,
                str(row.get("order_number") or ""),
                str(row.get("supplier_product_code") or ""),
                str(
                    row.get("supplier_product_name")
                    or row.get("product_name")
                    or row.get("platform_product_name")
                    or ""
                ),
                str(row.get("option_name") or ""),
                str(row.get("receiver_name") or ""),
                str(row.get("receiver_phone") or ""),
            ]).lower()

            if keyword and keyword not in search_text:
                continue

            rows.append(row)

        return rows

    def create_purchase_files(self) -> None:
        candidates = self._get_filtered_rows()

        if not candidates:
            messagebox.showwarning(
                "발주서 생성",
                "발주 가능한 주문상품이 없습니다.",
                parent=self,
            )
            return

        supplier_count = len({
            int(item["supplier_id"])
            for item in candidates
        })
        total_quantity = sum(
            int(item.get("purchase_quantity") or item.get("quantity") or 0)
            for item in candidates
        )
        total_amount = sum(
            int(item.get("item_amount") or 0)
            for item in candidates
        )

        validation = self._validate_before_purchase(candidates)
        if validation is None:
            return

        warning_text = self._format_validation_warnings(validation)

        confirmed = messagebox.askyesno(
            "발주서 생성 확인",
            (
                f"발주상품: {len(candidates):,}건\n"
                f"공급처: {supplier_count:,}곳\n"
                f"총 수량: {total_quantity:,}개\n"
                f"상품금액: {total_amount:,}원"
                f"{warning_text}\n\n"
                "조회 목록 전체를 발주하시겠습니까?"
            ),
            parent=self,
        )
        if not confirmed:
            return

        self._execute_purchase([
            int(item["order_item_id"])
            for item in candidates
        ])

    def create_selected_purchase_files(self) -> None:
        if self.view_mode_var.get() != "발주대기":
            return

        selected_items = self.tree.selection()

        if not selected_items:
            messagebox.showwarning(
                "선택 발주",
                "발주할 상품을 먼저 선택하세요.",
                parent=self,
            )
            return

        selected_ids = {int(item_id) for item_id in selected_items}
        candidates = [
            item
            for item in self._get_filtered_rows()
            if int(item["order_item_id"]) in selected_ids
        ]

        validation = self._validate_before_purchase(candidates)
        if validation is None:
            return

        warning_text = self._format_validation_warnings(validation)

        confirmed = messagebox.askyesno(
            "선택 발주 확인",
            (
                f"선택 상품 {len(candidates):,}건"
                f"{warning_text}\n\n"
                "발주하시겠습니까?"
            ),
            parent=self,
        )
        if not confirmed:
            return

        self._execute_purchase([
            int(item["order_item_id"])
            for item in candidates
        ])


    def _validate_before_purchase(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        validation = self.purchase_service.validate_purchase_candidates(candidates)
        errors = list(validation.get("errors") or [])

        if errors:
            lines = "\n".join(f"· {message}" for message in errors[:10])
            more = len(errors) - 10
            if more > 0:
                lines += f"\n· 그 외 {more:,}건"
            messagebox.showerror(
                "발주 전 필수정보 확인",
                (
                    "발주를 진행할 수 없는 항목이 있습니다.\n\n"
                    f"{lines}\n\n"
                    "주문관리 또는 상품관리에서 정보를 수정한 뒤 다시 시도하세요."
                ),
                parent=self,
            )
            return None

        return validation

    @staticmethod
    def _format_validation_warnings(validation: dict[str, Any]) -> str:
        warnings = list(validation.get("warnings") or [])
        if not warnings:
            return ""

        lines = "\n".join(f"· {message}" for message in warnings[:6])
        more = len(warnings) - 6
        if more > 0:
            lines += f"\n· 그 외 {more:,}건"
        return f"\n\n주의사항 {len(warnings):,}건\n{lines}"

    def _execute_purchase(self, order_item_ids: list[int]) -> None:
        try:
            self.create_button.configure(state="disabled")
            self.selected_button.configure(state="disabled")
            for button in self.deadline_buttons.values():
                button.configure(state="disabled")
            self.status_var.set("발주서를 생성하고 있습니다.")
            self.update_idletasks()

            result = self.purchase_service.create_purchase_files(
                order_item_ids=order_item_ids
            )

            if int(result.get("created_count", 0)) == 0:
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
                Path(path).name
                for path in result.get("files", [])
            )
            messagebox.showinfo(
                "발주서 생성 완료",
                (
                    f"발주상품: {result.get('created_count', 0):,}건\n"
                    f"공급처·차수 그룹: "
                    f"{result.get('supplier_count', 0):,}개\n\n"
                    f"생성 파일\n{file_lines}"
                ),
                parent=self,
            )
            self.refresh()

        except Exception as error:
            messagebox.showerror(
                "발주서 생성 오류",
                f"발주서 생성 중 오류가 발생했습니다.\n\n{error}",
                parent=self,
            )
        finally:
            if self.view_mode_var.get() == "발주대기":
                self.create_button.configure(state="normal")
                self.selected_button.configure(state="normal")
            self._refresh_deadline_area()

    def open_purchase_folder(self) -> None:
        folder_path = Path(self.purchase_service.output_root)
        folder_path.mkdir(parents=True, exist_ok=True)

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
                f"발주서 폴더를 열지 못했습니다.\n\n{error}",
                parent=self,
            )

    def _on_tree_double_click(self, event: tk.Event) -> None:
        if self.view_mode_var.get() != "발주완료":
            return

        selected_items = self.tree.selection()
        if not selected_items:
            return

        selected_id = int(selected_items[0])
        selected_row = next(
            (
                row
                for row in self.purchase_orders
                if int(row.get("id")) == selected_id
            ),
            None,
        )

        if not selected_row:
            return

        purchase_file = selected_row.get("purchase_file")
        if not purchase_file:
            messagebox.showwarning(
                "발주서 열기",
                "저장된 발주서 경로가 없습니다.",
                parent=self,
            )
            return

        file_path = Path(str(purchase_file))
        if not file_path.exists():
            messagebox.showwarning(
                "발주서 열기",
                f"발주서 파일을 찾을 수 없습니다.\n\n{file_path}",
                parent=self,
            )
            return

        try:
            os.startfile(file_path)
        except OSError as error:
            messagebox.showerror(
                "발주서 열기 오류",
                f"발주서 파일을 열지 못했습니다.\n\n{error}",
                parent=self,
            )

    def _on_view_mode_changed(
        self,
        event: tk.Event | None = None,
    ) -> None:
        self.supplier_filter_var.set("전체")
        self.search_var.set("")
        self._refresh_supplier_filter()
        self.history_period_combo.configure(
            state="readonly" if self.view_mode_var.get() == "발주완료" else "disabled"
        )
        self._render_supplier_center()
        self._refresh_deadline_area()
        self._render_tree()

    def _on_filter_changed(
        self,
        event: tk.Event | None = None,
    ) -> None:
        self._render_tree()
