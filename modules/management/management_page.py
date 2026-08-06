from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from modules.management.management_service import ManagementService


class ManagementPage(ttk.Frame):
    """매출·이익·고객 지표를 한 화면에 보여주는 대표용 경영현황입니다."""

    CARDS = (
        ("today_sales", "오늘 매출", "원"),
        ("today_profit", "오늘 순이익", "원"),
        ("month_sales", "이번 달 매출", "원"),
        ("month_profit", "이번 달 순이익", "원"),
        ("margin_rate", "이번 달 마진율", "%"),
        ("average_order", "이번 달 객단가", "원"),
        ("repeat_rate", "재구매 고객 비율", "%"),
        ("average_purchase_minutes", "평균 발주시간", "분"),
    )

    def __init__(
        self,
        parent: tk.Misc,
        *,
        service: ManagementService | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, padding=20)
        self.service = service or ManagementService()
        self.status_callback = status_callback
        self.card_values: dict[str, tk.StringVar] = {}
        self._build_ui()
        self.after(100, self.refresh_data)

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="경영현황", font=("맑은 고딕", 22, "bold")).pack(side="left")
        self.updated_var = tk.StringVar(value="-")
        ttk.Label(header, textvariable=self.updated_var).pack(side="right", padx=(12, 0))
        ttk.Button(header, text="새로고침", command=self.refresh_data).pack(side="right")

        cards = ttk.Frame(self)
        cards.pack(fill="x")
        for column in range(4):
            cards.columnconfigure(column, weight=1)
        for index, (key, title, unit) in enumerate(self.CARDS):
            box = ttk.LabelFrame(cards, text=title, padding=14)
            box.grid(row=index // 4, column=index % 4, sticky="nsew", padx=5, pady=5)
            value = tk.StringVar(value=f"0{unit}")
            self.card_values[key] = value
            ttk.Label(box, textvariable=value, font=("맑은 고딕", 18, "bold")).pack(anchor="w")
            if key == "month_sales":
                self.sales_comparison = ttk.Label(box, text="전월 대비 -")
                self.sales_comparison.pack(anchor="w", pady=(5, 0))
            elif key == "month_profit":
                self.profit_comparison = ttk.Label(box, text="전월 대비 -")
                self.profit_comparison.pack(anchor="w", pady=(5, 0))

        content = ttk.Panedwindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, pady=(14, 0))

        product_frame = ttk.LabelFrame(content, text="이번 달 매출 상품 TOP 10", padding=10)
        platform_frame = ttk.LabelFrame(content, text="판매처별 실적", padding=10)
        content.add(product_frame, weight=3)
        content.add(platform_frame, weight=2)

        self.product_tree = ttk.Treeview(
            product_frame,
            columns=("rank", "product", "orders", "sales", "profit"),
            show="headings",
            height=14,
        )
        headings = (("rank", "순위", 55), ("product", "상품", 300), ("orders", "주문", 70),
                    ("sales", "매출", 110), ("profit", "순이익", 110))
        for key, title, width in headings:
            self.product_tree.heading(key, text=title)
            self.product_tree.column(key, width=width, anchor="e" if key in {"orders", "sales", "profit"} else "w")
        self.product_tree.pack(fill="both", expand=True)

        self.platform_tree = ttk.Treeview(
            platform_frame,
            columns=("platform", "orders", "sales", "share"),
            show="headings",
            height=14,
        )
        for key, title, width in (("platform", "판매처", 140), ("orders", "주문", 70),
                                  ("sales", "매출", 120), ("share", "비중", 80)):
            self.platform_tree.heading(key, text=title)
            self.platform_tree.column(key, width=width, anchor="e" if key != "platform" else "w")
        self.platform_tree.pack(fill="both", expand=True)

        self.notice_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.notice_var).pack(fill="x", pady=(10, 0))

    def refresh_data(self) -> None:
        try:
            data = self.service.get_management_data()
            summary = data.get("summary", {})
            for key, _title, unit in self.CARDS:
                value = summary.get(key, 0)
                if unit == "%":
                    text = f"{float(value):,.1f}%"
                else:
                    text = f"{int(value or 0):,}{unit}"
                self.card_values[key].set(text)

            comparisons = data.get("comparisons", {})
            self.sales_comparison.configure(text=f"전월 대비 {self._rate_text(comparisons.get('sales_rate'))}")
            self.profit_comparison.configure(text=f"전월 대비 {self._rate_text(comparisons.get('profit_rate'))}")

            self._clear(self.product_tree)
            for rank, row in enumerate(data.get("top_products", []), start=1):
                self.product_tree.insert("", "end", values=(
                    rank, row.get("product", "-"), f"{int(row.get('orders', 0)):,}건",
                    f"{int(row.get('sales', 0)):,}원", f"{int(row.get('profit', 0)):,}원",
                ))

            self._clear(self.platform_tree)
            month_sales = int(summary.get("month_sales", 0) or 0)
            for row in data.get("platforms", []):
                sales = int(row.get("sales", 0) or 0)
                share = sales / month_sales * 100 if month_sales else 0
                self.platform_tree.insert("", "end", values=(
                    row.get("platform", "-"), f"{int(row.get('orders', 0)):,}건",
                    f"{sales:,}원", f"{share:.1f}%",
                ))

            errors = data.get("errors", [])
            unsettled = int(summary.get("unsettled_count", 0) or 0)
            notice = f"이번 달 비용 미입력 주문 {unsettled:,}건"
            if errors:
                notice += " · 일부 지표 확인 필요: " + " / ".join(errors)
            self.notice_var.set(notice)
            self.updated_var.set(f"최근 갱신 {data.get('updated_at', '-')}")
            self._set_status("경영현황을 새로고침했습니다.")
        except Exception as error:
            self.notice_var.set(f"경영현황을 불러오지 못했습니다: {error}")
            self._set_status("경영현황 조회 실패")

    @staticmethod
    def _rate_text(value: Any) -> str:
        if value is None:
            return "비교 기준 없음"
        number = float(value)
        sign = "+" if number > 0 else ""
        return f"{sign}{number:.1f}%"

    @staticmethod
    def _clear(tree: ttk.Treeview) -> None:
        children = tree.get_children()
        if children:
            tree.delete(*children)

    def _set_status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)
