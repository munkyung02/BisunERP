from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk
from typing import Callable

from modules.dashboard.chart_widgets import SevenDayChart
from modules.statistics.statistics_service import StatisticsService


class StatisticsPage(ttk.Frame):
    """기간별 판매 성과를 조회하는 통계 화면입니다."""

    def __init__(self, parent: tk.Misc, *, service: StatisticsService | None = None, status_callback: Callable[[str], None] | None = None) -> None:
        super().__init__(parent, padding=20)
        self.service = service or StatisticsService()
        self.status_callback = status_callback
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.metric_var = tk.StringVar(value="sales")
        self.summary_vars = {key: tk.StringVar(value="0") for key in ("order_count", "total_sales", "average_order", "item_quantity", "customer_count")}
        self._build_ui()
        self.set_preset(30)

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="통계", font=("맑은 고딕", 22, "bold")).pack(side="left")
        self.updated_var = tk.StringVar(value="-")
        ttk.Label(header, textvariable=self.updated_var).pack(side="right")

        filters = ttk.LabelFrame(self, text="조회 기간", padding=10)
        filters.pack(fill="x")
        ttk.Label(filters, text="시작일").pack(side="left")
        ttk.Entry(filters, textvariable=self.start_var, width=13).pack(side="left", padx=(5, 12))
        ttk.Label(filters, text="종료일").pack(side="left")
        ttk.Entry(filters, textvariable=self.end_var, width=13).pack(side="left", padx=(5, 12))
        for label, days in (("오늘", 1), ("7일", 7), ("30일", 30), ("90일", 90)):
            ttk.Button(filters, text=label, command=lambda value=days: self.set_preset(value)).pack(side="left", padx=2)
        ttk.Button(filters, text="조회", command=self.refresh_data).pack(side="right")

        cards = ttk.Frame(self)
        cards.pack(fill="x", pady=10)
        definitions = (("order_count", "주문 건수", "건"), ("total_sales", "총 매출", "원"), ("average_order", "평균 객단가", "원"), ("item_quantity", "판매 수량", "개"), ("customer_count", "구매 고객", "명"))
        for index, (key, title, unit) in enumerate(definitions):
            cards.columnconfigure(index, weight=1)
            box = ttk.LabelFrame(cards, text=title, padding=12)
            box.grid(row=0, column=index, sticky="nsew", padx=4)
            ttk.Label(box, textvariable=self.summary_vars[key], font=("맑은 고딕", 17, "bold")).pack(anchor="w")
            ttk.Label(box, text=unit).pack(anchor="e")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        trend = ttk.Frame(notebook, padding=10)
        products = ttk.Frame(notebook, padding=10)
        platforms = ttk.Frame(notebook, padding=10)
        customers = ttk.Frame(notebook, padding=10)
        statuses = ttk.Frame(notebook, padding=10)
        notebook.add(trend, text="일자별 추이")
        notebook.add(products, text="상품 순위")
        notebook.add(platforms, text="판매처")
        notebook.add(customers, text="고객 순위")
        notebook.add(statuses, text="처리 상태")

        controls = ttk.Frame(trend)
        controls.pack(fill="x")
        ttk.Radiobutton(controls, text="매출", variable=self.metric_var, value="sales", command=self._redraw_chart).pack(side="left")
        ttk.Radiobutton(controls, text="주문", variable=self.metric_var, value="orders", command=self._redraw_chart).pack(side="left")
        self.chart = SevenDayChart(trend, height=330)
        self.chart.pack(fill="both", expand=True, pady=(8, 0))
        self.daily_rows: list[dict] = []

        self.product_tree = self._tree(products, (("rank", "순위", 55), ("product", "상품/옵션", 430), ("orders", "주문", 90), ("quantity", "수량", 90), ("sales", "매출", 130)))
        self.platform_tree = self._tree(platforms, (("platform", "판매처", 240), ("orders", "주문", 120), ("sales", "매출", 160), ("share", "비중", 100)))
        self.customer_tree = self._tree(customers, (("rank", "순위", 55), ("name", "고객명", 180), ("phone", "연락처", 180), ("orders", "주문", 100), ("sales", "매출", 150)))
        self.status_tree = self._tree(statuses, (("category", "구분", 160), ("status", "상태", 260), ("count", "주문 건수", 140)))

    def _tree(self, parent: ttk.Frame, columns: tuple[tuple[str, str, int], ...]) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=[item[0] for item in columns], show="headings")
        for key, title, width in columns:
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="e" if key in {"rank", "orders", "quantity", "sales", "share", "count"} else "w")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return tree

    def set_preset(self, days: int) -> None:
        end = date.today()
        start = end - timedelta(days=max(1, days) - 1)
        self.start_var.set(start.isoformat())
        self.end_var.set(end.isoformat())
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            data = self.service.get_statistics(self.start_var.get(), self.end_var.get())
            summary = data["summary"]
            for key, variable in self.summary_vars.items():
                variable.set(f"{int(summary.get(key, 0)):,}")
            self.daily_rows = data["daily"]
            self._redraw_chart()
            self._fill(self.product_tree, [(index, row["product"], f"{row['orders']:,}건", f"{row['quantity']:,}개", f"{row['sales']:,}원") for index, row in enumerate(data["products"], 1)])
            total_sales = int(summary.get("total_sales", 0))
            self._fill(self.platform_tree, [(row["platform"], f"{row['orders']:,}건", f"{row['sales']:,}원", f"{(row['sales'] / total_sales * 100 if total_sales else 0):.1f}%") for row in data["platforms"]])
            self._fill(self.customer_tree, [(index, row["name"], row["phone"], f"{row['orders']:,}건", f"{row['sales']:,}원") for index, row in enumerate(data["customers"], 1)])
            self._fill(self.status_tree, [(row["category"], row["status"], f"{row['count']:,}건") for row in data["statuses"]])
            self.updated_var.set(f"최근 갱신 {data['updated_at']}")
            self._status("통계 조회를 완료했습니다.")
        except Exception as error:
            messagebox.showerror("통계 조회 오류", str(error), parent=self)
            self._status("통계 조회 실패")

    def _redraw_chart(self) -> None:
        metric = self.metric_var.get()
        rows = [{**row, "order_count": row.get("orders", 0)} for row in self.daily_rows]
        self.chart.set_data(rows, "sales" if metric == "sales" else "order_count")

    @staticmethod
    def _fill(tree: ttk.Treeview, rows: list[tuple]) -> None:
        children = tree.get_children()
        if children:
            tree.delete(*children)
        for row in rows:
            tree.insert("", "end", values=row)

    def _status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)
