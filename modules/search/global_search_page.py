from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from modules.search.global_search_service import GlobalSearchService


class GlobalSearchWindow(tk.Toplevel):
    """주문·발주·송장 통합 검색 창입니다."""

    def __init__(self, parent: tk.Misc, *, initial_keyword: str = "", status_callback: Callable[[str], None] | None = None) -> None:
        super().__init__(parent)
        self.service = GlobalSearchService()
        self.status_callback = status_callback
        self.keyword_var = tk.StringVar(value=initial_keyword)
        self.result_var = tk.StringVar(value="주문번호, 수취인, 전화번호, 상품명, 송장번호를 검색할 수 있습니다.")

        self.title("비선상회 ERP - 전역 검색")
        self.geometry("1320x760")
        self.minsize(1050, 620)
        self.transient(parent)
        self._build_ui()
        self.keyword_entry.focus_set()
        self.bind("<Return>", lambda _event: self.search())
        if initial_keyword.strip(): self.after(100, self.search)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=18)
        header.pack(fill="x")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="전역 검색", font=("맑은 고딕", 19, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="주문·발주·송장 데이터를 한 번에 검색합니다.").grid(row=1, column=0, pady=(3, 0), sticky="w")

        search_frame = ttk.Frame(self, padding=(18, 0, 18, 12))
        search_frame.pack(fill="x")
        search_frame.columnconfigure(0, weight=1)
        self.keyword_entry = ttk.Entry(search_frame, textvariable=self.keyword_var, font=("맑은 고딕", 12))
        self.keyword_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew", ipady=6)
        ttk.Button(search_frame, text="통합 검색", command=self.search).grid(row=0, column=1, ipadx=12, ipady=5)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        self.order_tree = self._tree_tab("주문", ("order_number", "receiver_name", "receiver_phone", "product_name", "amount", "status"), ("주문번호", "수취인", "전화번호", "상품", "결제금액", "상태"), (150, 90, 120, 350, 100, 100))
        self.purchase_tree = self._tree_tab("발주", ("order_number", "supplier_name", "receiver_name", "receiver_phone", "product_name", "quantity", "status"), ("주문번호", "공급처", "수취인", "전화번호", "상품", "수량", "상태"), (140, 110, 85, 120, 330, 70, 90))
        self.shipment_tree = self._tree_tab("송장", ("order_number", "receiver_name", "product_name", "courier_name", "tracking_number", "status"), ("주문번호", "수취인", "상품", "택배사", "송장번호", "상태"), (150, 90, 330, 100, 180, 100))
        ttk.Label(self, textvariable=self.result_var, anchor="w", padding=(18, 8)).pack(fill="x")

    def _tree_tab(self, title: str, columns: tuple[str, ...], headings: tuple[str, ...], widths: tuple[int, ...]) -> ttk.Treeview:
        frame = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(frame, text=title)
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading); tree.column(column, width=width, minwidth=60, anchor="e" if column in {"amount", "quantity"} else "w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview); tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew"); scroll.grid(row=0, column=1, sticky="ns")
        return tree

    def search(self) -> None:
        try:
            data = self.service.search(self.keyword_var.get())
        except ValueError as error:
            messagebox.showwarning("검색어 확인", str(error), parent=self); return
        except Exception as error:
            messagebox.showerror("검색 오류", f"검색 중 오류가 발생했습니다.\n\n{error}", parent=self); return
        self._fill(self.order_tree, data["orders"], ("order_number", "receiver_name", "receiver_phone", "product_name", "amount", "status"), money_key="amount")
        self._fill(self.purchase_tree, data["purchases"], ("order_number", "supplier_name", "receiver_name", "receiver_phone", "product_name", "quantity", "status"))
        self._fill(self.shipment_tree, data["shipments"], ("order_number", "receiver_name", "product_name", "courier_name", "tracking_number", "status"))
        self.notebook.tab(0, text=f"주문 ({len(data['orders'])})"); self.notebook.tab(1, text=f"발주 ({len(data['purchases'])})"); self.notebook.tab(2, text=f"송장 ({len(data['shipments'])})")
        error_text = f" · 일부 오류 {len(data['errors'])}건" if data["errors"] else ""
        self.result_var.set(f"'{data['keyword']}' 검색 결과 총 {data['total_count']:,}건{error_text}")
        if self.status_callback: self.status_callback(f"전역 검색 완료: {data['total_count']:,}건")

    @staticmethod
    def _fill(tree: ttk.Treeview, rows: list[dict[str, Any]], columns: tuple[str, ...], money_key: str | None = None) -> None:
        children = tree.get_children()
        if children: tree.delete(*children)
        for row in rows:
            values=[]
            for column in columns:
                value=row.get(column, "-")
                if column == money_key: value=f"{int(value or 0):,}원"
                elif column == "quantity": value=f"{int(value or 0):,}개"
                values.append(value)
            tree.insert("", "end", values=values)
