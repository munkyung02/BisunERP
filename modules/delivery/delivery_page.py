from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from typing import Callable

from .delivery_service import DeliveryService


class DeliveryPage(ttk.Frame):
    """송장별 배송 진행 현황 관리 화면."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        service: DeliveryService | None = None,
        status_callback: Callable[[str], None] | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, padding=22)
        self.service = service or DeliveryService()
        self.status_callback = status_callback
        self.refresh_callback = refresh_callback
        self.keyword_var = tk.StringVar()
        self.status_var = tk.StringVar(value="전체")
        self.overdue_only_var = tk.BooleanVar(value=False)
        self.overdue_days_var = tk.IntVar(value=3)
        self.summary_vars: dict[str, tk.StringVar] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="배송현황", font=("맑은 고딕", 22, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="등록된 송장을 조회하고 배송상태를 관리합니다.").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(header, text="새로고침", command=self.refresh_data).grid(row=0, column=1, rowspan=2, padx=(8, 0))

        summary = ttk.Frame(self)
        summary.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for index, (key, title) in enumerate((
            ("total", "전체 송장"), ("ready", "배송준비"), ("shipping", "배송중"),
            ("delivered", "배송완료"), ("overdue", "장기 배송중"),
        )):
            summary.columnconfigure(index, weight=1)
            box = ttk.LabelFrame(summary, text=title, padding=(14, 8))
            box.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 5, 0))
            var = tk.StringVar(value="0건")
            self.summary_vars[key] = var
            ttk.Label(box, textvariable=var, font=("맑은 고딕", 16, "bold")).pack()

        filters = ttk.LabelFrame(self, text="조회 조건", padding=10)
        filters.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text="통합검색").grid(row=0, column=0, padx=(0, 6))
        entry = ttk.Entry(filters, textvariable=self.keyword_var)
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind("<Return>", lambda _event: self.refresh_data())
        ttk.Label(filters, text="상태").grid(row=0, column=2, padx=(12, 6))
        ttk.Combobox(filters, textvariable=self.status_var, values=self.service.STATUSES, state="readonly", width=10).grid(row=0, column=3)
        ttk.Checkbutton(filters, text="장기 배송중만", variable=self.overdue_only_var).grid(row=0, column=4, padx=(12, 4))
        ttk.Spinbox(filters, from_=1, to=30, textvariable=self.overdue_days_var, width=5).grid(row=0, column=5)
        ttk.Label(filters, text="일 이상").grid(row=0, column=6, padx=(3, 8))
        ttk.Button(filters, text="조회", command=self.refresh_data).grid(row=0, column=7)

        table_frame = ttk.Frame(self)
        table_frame.grid(row=3, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = ("order", "receiver", "product", "courier", "tracking", "status", "shipped", "elapsed")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        specs = {
            "order": ("주문번호", 145), "receiver": ("수취인", 100), "product": ("상품/옵션", 260),
            "courier": ("택배사", 105), "tracking": ("송장번호", 145), "status": ("배송상태", 90),
            "shipped": ("출고일시", 135), "elapsed": ("경과", 65),
        }
        for key, (title, width) in specs.items():
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=55, anchor="center" if key not in {"product"} else "w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", lambda _event: self.open_tracking())

        actions = ttk.Frame(self)
        actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="택배사 배송조회 열기", command=self.open_tracking).pack(side="left")
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        for status in self.service.UPDATE_STATUSES:
            ttk.Button(actions, text=f"{status} 처리", command=lambda value=status: self.change_status(value)).pack(side="left", padx=(0, 6))
        self.count_var = tk.StringVar(value="0건 조회")
        ttk.Label(actions, textvariable=self.count_var).pack(side="right")

    def refresh_data(self) -> None:
        try:
            overdue_days = max(1, int(self.overdue_days_var.get()))
            rows = self.service.search(
                keyword=self.keyword_var.get(),
                status=self.status_var.get(),
                overdue_only=self.overdue_only_var.get(),
                overdue_days=overdue_days,
            )
            for item in self.tree.get_children():
                self.tree.delete(item)
            for row in rows:
                product = row.get("product_name") or "-"
                if row.get("option_name"):
                    product += f" / {row['option_name']}"
                quantity = int(row.get("quantity") or 0)
                if quantity:
                    product += f" × {quantity}"
                elapsed = int(row.get("elapsed_days") or 0)
                self.tree.insert("", "end", iid=str(row["id"]), values=(
                    row.get("order_number") or "-", row.get("receiver_name") or "-", product,
                    row.get("courier_name") or "-", row.get("tracking_number") or "-",
                    row.get("shipment_status") or "-", self.service.format_datetime(row.get("shipped_at")),
                    f"{elapsed}일",
                ))
            summary = self.service.get_summary(overdue_days)
            for key, var in self.summary_vars.items():
                var.set(f"{summary.get(key, 0):,}건")
            self.count_var.set(f"{len(rows):,}건 조회")
            self._set_status(f"배송현황 {len(rows):,}건 조회 완료")
        except Exception as error:
            messagebox.showerror("배송현황 조회 오류", str(error), parent=self.winfo_toplevel())

    def _selected_ids(self) -> list[int]:
        return [int(value) for value in self.tree.selection()]

    def change_status(self, status: str) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("선택 필요", "처리할 배송 건을 선택하세요.", parent=self.winfo_toplevel())
            return
        if not messagebox.askyesno("배송상태 변경", f"선택한 {len(ids)}건을 '{status}' 상태로 변경하시겠습니까?", parent=self.winfo_toplevel()):
            return
        try:
            count = self.service.update_status(ids, status)
            self.refresh_data()
            if self.refresh_callback:
                self.refresh_callback()
            self._set_status(f"배송상태 {count:,}건 변경 완료")
        except Exception as error:
            messagebox.showerror("배송상태 변경 오류", str(error), parent=self.winfo_toplevel())

    def open_tracking(self) -> None:
        selected = self.tree.selection()
        if len(selected) != 1:
            messagebox.showinfo("한 건 선택", "배송조회할 송장 한 건을 선택하세요.", parent=self.winfo_toplevel())
            return
        values = self.tree.item(selected[0], "values")
        try:
            webbrowser.open(self.service.get_tracking_url(str(values[3]), str(values[4])))
            self._set_status(f"{values[3]} 배송조회 페이지 열기")
        except Exception as error:
            messagebox.showerror("배송조회 오류", str(error), parent=self.winfo_toplevel())

    def _set_status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)
