from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any, Callable

from modules.settlements.settlement_service import SettlementService


class SettlementPage(ttk.Frame):
    """주문별 매출·비용·순이익을 입력하고 조회하는 정산센터입니다."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        service: SettlementService | None = None,
        status_callback: Callable[[str], None] | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or SettlementService()
        self.status_callback = status_callback
        self.refresh_callback = refresh_callback
        self.selected_order_id: int | None = None
        self.rows_by_id: dict[int, dict[str, Any]] = {}

        today = date.today()
        self.keyword_var = tk.StringVar()
        self.from_var = tk.StringVar(value=today.replace(day=1).isoformat())
        self.to_var = tk.StringVar(value=today.isoformat())
        self.filter_status_var = tk.StringVar(value="전체")
        self.summary_vars = {key: tk.StringVar(value="0") for key in (
            "sales", "total_cost", "net_profit", "waiting_count", "completed_count"
        )}
        self.form_vars = {key: tk.StringVar(value="0") for key in (
            "sales_amount", "purchase_cost", "shipping_fee", "platform_fee", "other_cost"
        )}
        self.form_status_var = tk.StringVar(value="미정산")
        self.memo_var = tk.StringVar()
        self.selected_var = tk.StringVar(value="주문을 선택하세요.")

        self._configure_styles()
        self._build_ui()
        self.after(100, self.refresh_data)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.configure("SettlementTitle.TLabel", font=("맑은 고딕", 22, "bold"))
        style.configure("SettlementValue.TLabel", font=("맑은 고딕", 18, "bold"))
        style.configure("Settlement.Treeview", rowheight=27, font=("맑은 고딕", 9))
        style.configure("Settlement.Treeview.Heading", font=("맑은 고딕", 9, "bold"))

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, padding=(24, 18, 24, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="정산센터", style="SettlementTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="주문별 매출·매입·택배비·수수료를 입력해 실제 순이익을 계산합니다.").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(header, text="새로고침", command=self.refresh_data).grid(row=0, column=1, rowspan=2)

        filters = ttk.LabelFrame(self, text="조회 조건", padding=10)
        filters.grid(row=1, column=0, padx=24, pady=(0, 8), sticky="ew")
        ttk.Label(filters, text="검색").pack(side="left")
        entry = ttk.Entry(filters, textvariable=self.keyword_var, width=24)
        entry.pack(side="left", padx=(5, 12)); entry.bind("<Return>", lambda _e: self.refresh_data())
        ttk.Label(filters, text="기간").pack(side="left")
        ttk.Entry(filters, textvariable=self.from_var, width=11).pack(side="left", padx=(5, 3))
        ttk.Label(filters, text="~").pack(side="left")
        ttk.Entry(filters, textvariable=self.to_var, width=11).pack(side="left", padx=(3, 12))
        ttk.Label(filters, text="상태").pack(side="left")
        ttk.Combobox(filters, textvariable=self.filter_status_var, values=("전체", "미정산", "정산완료"), width=10, state="readonly").pack(side="left", padx=(5, 12))
        ttk.Button(filters, text="조회", command=self.refresh_data).pack(side="left")
        ttk.Button(filters, text="이번 달", command=self._set_this_month).pack(side="left", padx=(5, 0))

        cards = ttk.Frame(self, padding=(24, 0, 24, 8))
        cards.grid(row=2, column=0, sticky="ew")
        definitions = (("sales", "매출", "원"), ("total_cost", "총비용", "원"), ("net_profit", "순이익", "원"), ("waiting_count", "미정산", "건"), ("completed_count", "정산완료", "건"))
        for index, (key, title, unit) in enumerate(definitions):
            cards.columnconfigure(index, weight=1, uniform="settle_card")
            card = ttk.LabelFrame(cards, padding=(12, 9)); card.grid(row=0, column=index, padx=4, sticky="nsew")
            ttk.Label(card, text=title).pack(anchor="w")
            ttk.Label(card, textvariable=self.summary_vars[key], style="SettlementValue.TLabel").pack(anchor="w", pady=(4, 0))

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.grid(row=3, column=0, padx=24, pady=(0, 12), sticky="nsew")
        list_frame = ttk.LabelFrame(paned, text="주문별 정산 목록", padding=8)
        edit_frame = ttk.LabelFrame(paned, text="정산 입력", padding=12)
        paned.add(list_frame, weight=4); paned.add(edit_frame, weight=2)
        self._build_tree(list_frame)
        self._build_form(edit_frame)

    def _build_tree(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1); parent.rowconfigure(0, weight=1)
        columns = ("date", "number", "receiver", "item", "sales", "cost", "profit", "status")
        self.tree = ttk.Treeview(parent, columns=columns, show="headings", style="Settlement.Treeview")
        specs = (("date", "주문일", 95), ("number", "주문번호", 135), ("receiver", "수취인", 75), ("item", "상품", 260), ("sales", "매출", 90), ("cost", "총비용", 90), ("profit", "순이익", 90), ("status", "상태", 75))
        for key, title, width in specs:
            self.tree.heading(key, text=title); self.tree.column(key, width=width, anchor="e" if key in {"sales", "cost", "profit"} else "center" if key in {"date", "receiver", "status"} else "w")
        scroll = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew"); scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_form(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, textvariable=self.selected_var, font=("맑은 고딕", 11, "bold"), wraplength=350).grid(row=0, column=0, columnspan=2, pady=(0, 12), sticky="w")
        fields = (("sales_amount", "매출액"), ("purchase_cost", "매입금액"), ("shipping_fee", "택배비"), ("platform_fee", "플랫폼 수수료"), ("other_cost", "기타 비용"))
        for row, (key, label) in enumerate(fields, start=1):
            ttk.Label(parent, text=label).grid(row=row, column=0, padx=(0, 8), pady=5, sticky="w")
            ttk.Entry(parent, textvariable=self.form_vars[key], justify="right").grid(row=row, column=1, pady=5, sticky="ew")
        ttk.Label(parent, text="정산 상태").grid(row=6, column=0, pady=5, sticky="w")
        ttk.Combobox(parent, textvariable=self.form_status_var, values=("미정산", "정산완료"), state="readonly").grid(row=6, column=1, pady=5, sticky="ew")
        ttk.Label(parent, text="메모").grid(row=7, column=0, pady=5, sticky="w")
        ttk.Entry(parent, textvariable=self.memo_var).grid(row=7, column=1, pady=5, sticky="ew")
        self.preview_var = tk.StringVar(value="예상 순이익: 0원")
        ttk.Label(parent, textvariable=self.preview_var, style="SettlementValue.TLabel").grid(row=8, column=0, columnspan=2, pady=(15, 8), sticky="w")
        for variable in self.form_vars.values(): variable.trace_add("write", lambda *_: self._update_preview())
        buttons = ttk.Frame(parent); buttons.grid(row=9, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="저장", command=self.save_selected).pack(side="left", fill="x", expand=True)
        ttk.Button(buttons, text="입력 초기화", command=self.reset_selected).pack(side="left", padx=(6, 0))

    def refresh_data(self) -> None:
        try:
            rows = self.service.get_rows(keyword=self.keyword_var.get(), ordered_from=self.from_var.get().strip() or None, ordered_to=self.to_var.get().strip() or None, settlement_status=self.filter_status_var.get())
            self.rows_by_id = {int(row["order_id"]): row for row in rows}
            self.tree.delete(*self.tree.get_children())
            for row in rows:
                cost = sum(self._int(row.get(key)) for key in ("purchase_cost", "shipping_fee", "platform_fee", "other_cost"))
                self.tree.insert("", "end", iid=str(row["order_id"]), values=(str(row.get("ordered_at") or "-")[:10], row.get("order_number") or "-", row.get("receiver_name") or "-", row.get("item_summary") or "-", f"{self._int(row.get('sales_amount')):,}", f"{cost:,}", f"{self._int(row.get('net_profit')):,}", row.get("settlement_status") or "미정산"))
            summary = self.service.get_summary(self.from_var.get().strip() or None, self.to_var.get().strip() or None)
            for key in ("sales", "total_cost", "net_profit"):
                self.summary_vars[key].set(f"{summary[key]:,}원")
            for key in ("waiting_count", "completed_count"):
                self.summary_vars[key].set(f"{summary[key]:,}건")
            self._status("정산 데이터 새로고침 완료")
        except Exception as error:
            messagebox.showerror("정산 조회 오류", f"정산 데이터를 불러오지 못했습니다.\n\n{error}", parent=self.winfo_toplevel())

    def _on_select(self, _event: object = None) -> None:
        selected = self.tree.selection()
        if not selected: return
        order_id = int(selected[0]); row = self.rows_by_id.get(order_id)
        if not row: return
        self.selected_order_id = order_id
        self.selected_var.set(f"{row.get('order_number', '-')} · {row.get('receiver_name', '-')}\n{row.get('item_summary', '-')}")
        for key in self.form_vars: self.form_vars[key].set(str(self._int(row.get(key))))
        self.form_status_var.set(str(row.get("settlement_status") or "미정산")); self.memo_var.set(str(row.get("memo") or "")); self._update_preview()

    def save_selected(self) -> None:
        if self.selected_order_id is None:
            messagebox.showinfo("정산 입력", "정산할 주문을 먼저 선택하세요.", parent=self.winfo_toplevel()); return
        try:
            self.service.save_settlement(order_id=self.selected_order_id, sales_amount=self._money("sales_amount"), purchase_cost=self._money("purchase_cost"), shipping_fee=self._money("shipping_fee"), platform_fee=self._money("platform_fee"), other_cost=self._money("other_cost"), memo=self.memo_var.get(), settlement_status=self.form_status_var.get())
            self.refresh_data(); self._status("정산 저장 완료")
            if self.refresh_callback: self.refresh_callback()
        except Exception as error:
            messagebox.showerror("정산 저장 오류", str(error), parent=self.winfo_toplevel())

    def reset_selected(self) -> None:
        if self.selected_order_id is None: return
        row = self.rows_by_id.get(self.selected_order_id, {})
        self.form_vars["sales_amount"].set(str(self._int(row.get("order_sales_amount"))))
        for key in ("purchase_cost", "shipping_fee", "platform_fee", "other_cost"): self.form_vars[key].set("0")
        self.form_status_var.set("미정산"); self.memo_var.set("")

    def _set_this_month(self) -> None:
        today = date.today(); self.from_var.set(today.replace(day=1).isoformat()); self.to_var.set(today.isoformat()); self.refresh_data()

    def _update_preview(self) -> None:
        sales = self._int(self.form_vars["sales_amount"].get())
        costs = sum(self._int(self.form_vars[key].get()) for key in ("purchase_cost", "shipping_fee", "platform_fee", "other_cost"))
        self.preview_var.set(f"예상 순이익: {sales - costs:,}원")

    def _money(self, key: str) -> int:
        text = self.form_vars[key].get().replace(",", "").strip() or "0"
        try: value = int(float(text))
        except ValueError as error: raise ValueError("금액은 숫자로 입력하세요.") from error
        if value < 0: raise ValueError("금액은 0원 이상이어야 합니다.")
        return value

    def _status(self, message: str) -> None:
        if self.status_callback: self.status_callback(message)

    @staticmethod
    def _int(value: Any) -> int:
        try: return int(float(str(value or 0).replace(",", "")))
        except (TypeError, ValueError): return 0
