from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Any, Callable

from modules.receipts.receipt_service import PAYMENT_STATUSES, ReceiptService


class ReceiptPage(ttk.Frame):
    """주문별 계좌이체 입금 상태를 조회하고 수정하는 화면입니다."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        service: ReceiptService | None = None,
        status_callback: Callable[[str], None] | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, padding=18)
        self.service = service or ReceiptService()
        self.status_callback = status_callback
        self.refresh_callback = refresh_callback
        self.rows_by_item: dict[str, dict[str, Any]] = {}
        self.selected_order_id = 0
        self._build_ui()
        self.after(100, self.refresh_data)

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="입금관리", font=("맑은 고딕", 22, "bold")).pack(side="left")
        ttk.Button(header, text="새로고침", command=self.refresh_data).pack(side="right")

        filters = ttk.LabelFrame(self, text="검색 조건", padding=10)
        filters.pack(fill="x", pady=(0, 10))
        self.keyword_var = tk.StringVar()
        self.from_var = tk.StringVar(value=date.today().replace(day=1).isoformat())
        self.to_var = tk.StringVar(value=date.today().isoformat())
        self.status_var = tk.StringVar(value="전체")
        ttk.Label(filters, text="검색").grid(row=0, column=0, padx=4)
        keyword = ttk.Entry(filters, textvariable=self.keyword_var, width=24)
        keyword.grid(row=0, column=1, padx=4)
        keyword.bind("<Return>", lambda _event: self.refresh_data())
        ttk.Label(filters, text="주문일").grid(row=0, column=2, padx=(12, 4))
        ttk.Entry(filters, textvariable=self.from_var, width=12).grid(row=0, column=3, padx=4)
        ttk.Label(filters, text="~").grid(row=0, column=4)
        ttk.Entry(filters, textvariable=self.to_var, width=12).grid(row=0, column=5, padx=4)
        ttk.Label(filters, text="상태").grid(row=0, column=6, padx=(12, 4))
        status_box = ttk.Combobox(
            filters, textvariable=self.status_var, values=("전체", *PAYMENT_STATUSES),
            state="readonly", width=11,
        )
        status_box.grid(row=0, column=7, padx=4)
        ttk.Button(filters, text="조회", command=self.refresh_data).grid(row=0, column=8, padx=(12, 4))
        ttk.Button(filters, text="초기화", command=self.reset_filters).grid(row=0, column=9, padx=4)

        summary = ttk.Frame(self)
        summary.pack(fill="x", pady=(0, 10))
        self.summary_var = tk.StringVar(value="입금 현황을 불러오는 중입니다.")
        ttk.Label(summary, textvariable=self.summary_var, font=("맑은 고딕", 11, "bold")).pack(side="left")

        pane = ttk.Panedwindow(self, orient="vertical")
        pane.pack(fill="both", expand=True)
        table_frame = ttk.Frame(pane)
        form_frame = ttk.LabelFrame(pane, text="선택 주문 입금정보", padding=12)
        pane.add(table_frame, weight=4)
        pane.add(form_frame, weight=2)

        columns = (
            "ordered_at", "order_number", "receiver", "product", "order_amount",
            "depositor", "payment_amount", "balance", "status", "paid_at",
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        headings = (
            ("ordered_at", "주문일", 125), ("order_number", "주문번호", 150),
            ("receiver", "수취인", 85), ("product", "상품", 250),
            ("order_amount", "주문금액", 95), ("depositor", "입금자", 90),
            ("payment_amount", "입금액", 95), ("balance", "미입금액", 95),
            ("status", "입금상태", 85), ("paid_at", "입금일시", 135),
        )
        for key, title, width in headings:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="e" if "amount" in key or key == "balance" else "w")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.depositor_var = tk.StringVar()
        self.amount_var = tk.StringVar(value="0")
        self.method_var = tk.StringVar(value="계좌이체")
        self.payment_status_var = tk.StringVar(value="입금대기")
        self.paid_at_var = tk.StringVar()
        self.bank_message_var = tk.StringVar()
        self.memo_var = tk.StringVar()

        fields = (
            ("입금자명", self.depositor_var, 18), ("입금액", self.amount_var, 14),
            ("입금방법", self.method_var, 14), ("입금상태", self.payment_status_var, 12),
            ("입금일시", self.paid_at_var, 20), ("은행문자", self.bank_message_var, 34),
            ("메모", self.memo_var, 34),
        )
        for index, (label, variable, width) in enumerate(fields):
            row, pair = divmod(index, 4)
            column = pair * 2
            ttk.Label(form_frame, text=label).grid(row=row, column=column, sticky="w", padx=(0, 5), pady=5)
            if label == "입금상태":
                widget = ttk.Combobox(
                    form_frame, textvariable=variable, values=PAYMENT_STATUSES,
                    state="readonly", width=width,
                )
            else:
                widget = ttk.Entry(form_frame, textvariable=variable, width=width)
            widget.grid(row=row, column=column + 1, sticky="ew", padx=(0, 12), pady=5)
        for column in (1, 3, 5, 7):
            form_frame.columnconfigure(column, weight=1)

        buttons = ttk.Frame(form_frame)
        buttons.grid(row=2, column=0, columnspan=8, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="주문금액 전액", command=self.fill_full_amount).pack(side="left", padx=4)
        ttk.Button(buttons, text="입금완료 처리", command=self.mark_completed).pack(side="left", padx=4)
        ttk.Button(buttons, text="저장", command=self.save_payment).pack(side="left", padx=4)
        ttk.Button(buttons, text="입금기록 삭제", command=self.delete_payment).pack(side="left", padx=4)

    def reset_filters(self) -> None:
        self.keyword_var.set("")
        self.from_var.set(date.today().replace(day=1).isoformat())
        self.to_var.set(date.today().isoformat())
        self.status_var.set("전체")
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            rows = self.service.get_rows(
                keyword=self.keyword_var.get(), ordered_from=self.from_var.get().strip() or None,
                ordered_to=self.to_var.get().strip() or None, payment_status=self.status_var.get(),
            )
            self.tree.delete(*self.tree.get_children())
            self.rows_by_item.clear()
            for row in rows:
                item = self.tree.insert("", "end", values=(
                    str(row.get("ordered_at") or "-")[:16], row.get("order_number", "-"),
                    row.get("receiver_name", "-"), str(row.get("item_summary") or "-").split(" | ")[0],
                    f"{self._to_int(row.get('order_amount')):,}", row.get("depositor_name", ""),
                    f"{self._to_int(row.get('payment_amount')):,}",
                    f"{max(0, self._to_int(row.get('balance'))):,}", row.get("payment_status", "입금대기"),
                    str(row.get("paid_at") or "-")[:16],
                ))
                self.rows_by_item[item] = row
            summary = self.service.get_summary()
            self.summary_var.set(
                f"전체 {summary['total_count']:,}건 · 입금대기 {summary['waiting_count']:,}건 · "
                f"부분입금 {summary['partial_count']:,}건 · 입금완료 {summary['completed_count']:,}건 · "
                f"입금액 {summary['received_amount']:,}원 · 미입금액 {summary['balance_amount']:,}원"
            )
            self._set_status(f"입금관리 {len(rows):,}건 조회")
        except Exception as error:
            messagebox.showerror("입금관리", f"입금 내역을 불러오지 못했습니다.\n{error}", parent=self)
            self._set_status("입금관리 조회 실패")

    def _on_select(self, _event: tk.Event[Any] | None = None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        row = self.rows_by_item.get(selected[0])
        if not row:
            return
        self.selected_order_id = self._to_int(row.get("order_id"))
        self.depositor_var.set(str(row.get("depositor_name") or row.get("receiver_name") or ""))
        self.amount_var.set(str(self._to_int(row.get("payment_amount"))))
        self.method_var.set(str(row.get("payment_method") or "계좌이체"))
        self.payment_status_var.set(str(row.get("payment_status") or "입금대기"))
        self.paid_at_var.set(str(row.get("paid_at") or "")[:16])
        self.bank_message_var.set(str(row.get("bank_message") or ""))
        self.memo_var.set(str(row.get("memo") or ""))

    def fill_full_amount(self) -> None:
        row = self._selected_row()
        if row:
            self.amount_var.set(str(self._to_int(row.get("order_amount"))))

    def mark_completed(self) -> None:
        row = self._selected_row()
        if not row:
            return
        self.fill_full_amount()
        self.payment_status_var.set("입금완료")
        self.paid_at_var.set(datetime.now().strftime("%Y-%m-%d %H:%M"))
        self.save_payment()

    def save_payment(self) -> None:
        if not self._selected_row():
            return
        try:
            self.service.save_payment(
                order_id=self.selected_order_id,
                depositor_name=self.depositor_var.get(),
                payment_amount=self._parse_amount(self.amount_var.get()),
                payment_method=self.method_var.get(),
                payment_status=self.payment_status_var.get(),
                paid_at=self.paid_at_var.get(),
                bank_message=self.bank_message_var.get(), memo=self.memo_var.get(),
            )
            self.refresh_data()
            self._notify_refresh()
            self._set_status("입금정보를 저장했습니다.")
        except Exception as error:
            messagebox.showerror("입금 저장", str(error), parent=self)

    def delete_payment(self) -> None:
        if not self._selected_row():
            return
        if not messagebox.askyesno("입금기록 삭제", "선택 주문의 입금기록을 삭제할까요?", parent=self):
            return
        try:
            self.service.delete_payment(self.selected_order_id)
            self.refresh_data()
            self._notify_refresh()
            self._set_status("입금기록을 삭제했습니다.")
        except Exception as error:
            messagebox.showerror("입금기록 삭제", str(error), parent=self)

    def _selected_row(self) -> dict[str, Any] | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("입금관리", "주문을 먼저 선택하세요.", parent=self)
            return None
        return self.rows_by_item.get(selected[0])

    def _notify_refresh(self) -> None:
        if self.refresh_callback:
            self.refresh_callback()

    def _set_status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)

    @staticmethod
    def _parse_amount(value: str) -> int:
        try:
            return int(float(value.replace(",", "").strip() or 0))
        except ValueError as error:
            raise ValueError("입금액은 숫자로 입력하세요.") from error

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(str(value or 0).replace(",", "")))
        except (TypeError, ValueError):
            return 0
