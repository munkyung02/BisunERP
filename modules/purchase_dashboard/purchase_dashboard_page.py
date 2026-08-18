from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Any

from modules.purchase_dashboard.purchase_dashboard_service import (
    PurchaseDashboardService,
)


class CalendarPopup(tk.Toplevel):
    """외부 패키지 없이 날짜를 선택하는 작은 달력 팝업입니다."""

    def __init__(self, parent: tk.Misc, target_var: tk.StringVar) -> None:
        super().__init__(parent)
        self.target_var = target_var
        try:
            selected = datetime.strptime(target_var.get(), "%Y-%m-%d").date()
        except ValueError:
            selected = date.today()
        self.year = selected.year
        self.month = selected.month
        self.title("날짜 선택")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self._draw()

    def _draw(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        header = ttk.Frame(self, padding=8)
        header.pack(fill="x")
        ttk.Button(header, text="◀", width=3, command=lambda: self._move(-1)).pack(side="left")
        ttk.Label(header, text=f"{self.year}년 {self.month}월", anchor="center").pack(
            side="left", expand=True, fill="x"
        )
        ttk.Button(header, text="▶", width=3, command=lambda: self._move(1)).pack(side="right")

        body = ttk.Frame(self, padding=(8, 0, 8, 8))
        body.pack()
        for column, name in enumerate(("월", "화", "수", "목", "금", "토", "일")):
            ttk.Label(body, text=name, anchor="center", width=4).grid(row=0, column=column)
        for row_index, week in enumerate(calendar.monthcalendar(self.year, self.month), start=1):
            for column, day in enumerate(week):
                if day:
                    ttk.Button(
                        body,
                        text=str(day),
                        width=4,
                        command=lambda value=day: self._select(value),
                    ).grid(row=row_index, column=column, padx=1, pady=1)

    def _move(self, offset: int) -> None:
        value = self.year * 12 + self.month - 1 + offset
        self.year, month_index = divmod(value, 12)
        self.month = month_index + 1
        self._draw()

    def _select(self, day: int) -> None:
        self.target_var.set(date(self.year, self.month, day).isoformat())
        self.destroy()


class PurchaseDashboardPage(ttk.Frame):
    """공급처·상품·월별 구매 통계를 보여주는 화면입니다."""

    def __init__(
        self,
        parent: tk.Misc,
        service: PurchaseDashboardService | None = None,
    ) -> None:
        super().__init__(parent)

        self.service = service or PurchaseDashboardService()
        self.dashboard_data: dict[str, Any] = {}

        today = date.today()
        self.start_date_var = tk.StringVar(value=today.replace(day=1).isoformat())
        self.end_date_var = tk.StringVar(value=today.isoformat())
        self.status_var = tk.StringVar(
            value="구매 통계를 불러오는 중입니다."
        )

        self.order_count_var = tk.StringVar(value="0건")
        self.sales_amount_var = tk.StringVar(value="0원")
        self.purchase_amount_var = tk.StringVar(value="0원")
        self.profit_amount_var = tk.StringVar(value="0원")

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self._build_header()
        self._build_kpi_area()
        self._build_filter_area()
        self._build_content_area()
        self._build_status_area()

    def _build_header(self) -> None:
        frame = ttk.Frame(self, padding=(20, 18, 20, 10))
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text="판매·손익 통계",
            font=("맑은 고딕", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.period_summary_label = ttk.Label(
            frame,
            text="조회기간을 불러오는 중입니다.",
        )
        self.period_summary_label.grid(
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
            ("조회기간 주문", self.order_count_var),
            ("조회기간 매출", self.sales_amount_var),
            ("조회기간 매입", self.purchase_amount_var),
            ("조회기간 순익", self.profit_amount_var),
        ]

        for index, (title, variable) in enumerate(cards):
            frame.columnconfigure(index, weight=1)
            card = ttk.LabelFrame(
                frame,
                text=title,
                padding=(14, 9),
            )
            card.grid(
                row=0,
                column=index,
                padx=(0 if index == 0 else 5, 0),
                sticky="ew",
            )
            ttk.Label(
                card,
                textvariable=variable,
                font=("맑은 고딕", 13, "bold"),
            ).pack(anchor="w")

    def _build_filter_area(self) -> None:
        frame = ttk.LabelFrame(
            self,
            text="조회 조건",
            padding=12,
        )
        frame.grid(
            row=2,
            column=0,
            padx=20,
            pady=(0, 10),
            sticky="ew",
        )
        frame.columnconfigure(7, weight=1)

        ttk.Label(frame, text="조회기간").grid(
            row=0,
            column=0,
            padx=(0, 5),
        )

        ttk.Label(frame, text="시작일").grid(
            row=0,
            column=1,
            padx=(0, 5),
        )
        self.start_entry = ttk.Entry(
            frame,
            textvariable=self.start_date_var,
            width=12,
            state="readonly",
        )
        self.start_entry.grid(
            row=0,
            column=2,
        )
        self.start_entry.bind("<Button-1>", lambda _event: self._open_calendar(self.start_date_var))
        ttk.Button(
            frame, text="📅", width=3,
            command=lambda: self._open_calendar(self.start_date_var),
        ).grid(row=0, column=3, padx=(3, 12))

        ttk.Label(frame, text="~").grid(row=0, column=4, padx=(0, 12))

        ttk.Label(frame, text="종료일").grid(
            row=0,
            column=5,
            padx=(0, 5),
        )
        self.end_entry = ttk.Entry(
            frame,
            textvariable=self.end_date_var,
            width=12,
            state="readonly",
        )
        self.end_entry.grid(
            row=0,
            column=6,
        )
        self.end_entry.bind("<Button-1>", lambda _event: self._open_calendar(self.end_date_var))
        ttk.Button(
            frame, text="📅", width=3,
            command=lambda: self._open_calendar(self.end_date_var),
        ).grid(row=0, column=7, padx=(3, 12))

        ttk.Button(
            frame,
            text="조회",
            command=self.refresh,
        ).grid(row=0, column=8)

    def _build_content_area(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.grid(
            row=3,
            column=0,
            padx=20,
            sticky="nsew",
        )

        self.supplier_tab = ttk.Frame(notebook, padding=10)
        self.product_tab = ttk.Frame(notebook, padding=10)
        self.monthly_tab = ttk.Frame(notebook, padding=10)
        self.alert_tab = ttk.Frame(notebook, padding=10)

        notebook.add(self.supplier_tab, text="공급처 TOP10")
        notebook.add(self.product_tab, text="상품 TOP20")
        notebook.add(self.monthly_tab, text="월별 구매 통계")
        notebook.add(self.alert_tab, text="확인 알림")

        self.supplier_tree = self._create_tree(
            self.supplier_tab,
            columns=(
                "rank",
                "supplier_name",
                "purchase_count",
                "total_quantity",
                "total_item_amount",
                "total_shipping_fee",
                "grand_total",
            ),
            headings={
                "rank": "순위",
                "supplier_name": "공급처",
                "purchase_count": "발주건수",
                "total_quantity": "상품수량",
                "total_item_amount": "상품금액",
                "total_shipping_fee": "택배비",
                "grand_total": "총 발주금액",
            },
            widths={
                "rank": 65,
                "supplier_name": 190,
                "purchase_count": 100,
                "total_quantity": 100,
                "total_item_amount": 140,
                "total_shipping_fee": 110,
                "grand_total": 150,
            },
        )

        self.product_tree = self._create_tree(
            self.product_tab,
            columns=(
                "product_name",
                "order_count",
                "total_quantity",
                "sales",
                "purchase",
                "profit",
                "margin_rate",
                "unconfirmed_count",
                "profit_status",
            ),
            headings={
                "product_name": "상품명",
                "order_count": "주문수",
                "total_quantity": "판매수량",
                "sales": "매출",
                "purchase": "매입",
                "profit": "순익",
                "margin_rate": "순익률",
                "unconfirmed_count": "미확정 주문",
                "profit_status": "상태",
            },
            widths={
                "product_name": 280,
                "order_count": 90,
                "total_quantity": 100,
                "sales": 130,
                "purchase": 130,
                "profit": 130,
                "margin_rate": 100,
                "unconfirmed_count": 100,
                "profit_status": 110,
            },
        )
        self.product_tree.tag_configure("loss", background="#FDECEC")
        self.product_tree.tag_configure("margin_under_5", background="#FFF0E0")
        self.product_tree.tag_configure("margin_under_10", background="#FFF9D9")

        self.monthly_tree = self._create_tree(
            self.monthly_tab,
            columns=(
                "month",
                "purchase_count",
                "total_quantity",
                "supplier_count",
                "total_item_amount",
                "total_shipping_fee",
                "grand_total",
            ),
            headings={
                "month": "월",
                "purchase_count": "발주건수",
                "total_quantity": "총수량",
                "supplier_count": "공급처수",
                "total_item_amount": "상품금액",
                "total_shipping_fee": "택배비",
                "grand_total": "총 발주금액",
            },
            widths={
                "month": 110,
                "purchase_count": 100,
                "total_quantity": 100,
                "supplier_count": 100,
                "total_item_amount": 150,
                "total_shipping_fee": 120,
                "grand_total": 160,
            },
        )

        self.alert_tree = self._create_tree(
            self.alert_tab,
            columns=(
                "level",
                "title",
                "message",
            ),
            headings={
                "level": "구분",
                "title": "대상",
                "message": "내용",
            },
            widths={
                "level": 90,
                "title": 220,
                "message": 620,
            },
        )

    @staticmethod
    def _create_tree(
        parent: ttk.Frame,
        *,
        columns: tuple[str, ...],
        headings: dict[str, str],
        widths: dict[str, int],
    ) -> ttk.Treeview:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
        )

        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(
                column,
                width=widths[column],
                minwidth=60,
                anchor=(
                    "w"
                    if column in {
                        "supplier_name",
                        "product_name",
                        "title",
                        "message",
                    }
                    else "center"
                ),
            )

        y_scroll = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=tree.yview,
        )
        x_scroll = ttk.Scrollbar(
            parent,
            orient="horizontal",
            command=tree.xview,
        )
        tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        return tree

    def _build_status_area(self) -> None:
        ttk.Label(
            self,
            textvariable=self.status_var,
            padding=(20, 10, 20, 16),
        ).grid(row=4, column=0, sticky="ew")

    def refresh(self) -> None:
        try:
            data = self.service.get_dashboard_data(
                start_date=self.start_date_var.get(),
                end_date=self.end_date_var.get(),
            )
            data["alerts"] = self.service.build_alerts(data)
            self.dashboard_data = data

            self._render_kpi()
            self._render_supplier_ranking()
            self._render_product_ranking()
            self._render_monthly_statistics()
            self._render_alerts()

            self.period_summary_label.configure(
                text=(
                    f"조회기간: {data['start_date']} ~ "
                    f"{data['end_date']}"
                )
            )
            self.status_var.set(
                "판매·손익 통계를 최신 데이터로 갱신했습니다."
            )

        except Exception as error:
            self.status_var.set(
                "판매·손익 통계를 불러오지 못했습니다."
            )
            messagebox.showerror(
                "판매·손익 통계 오류",
                (
                    "판매·손익 통계를 불러오는 중 "
                    "오류가 발생했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

    def _render_kpi(self) -> None:
        summary = self.dashboard_data.get("sales_profit_summary") or {}
        self.order_count_var.set(f"{int(summary.get('order_count') or 0):,}건")
        self.sales_amount_var.set(f"{int(summary.get('sales') or 0):,}원")
        self.purchase_amount_var.set(f"{int(summary.get('purchase') or 0):,}원")
        self.profit_amount_var.set(f"{int(summary.get('profit') or 0):,}원")

    def _render_supplier_ranking(self) -> None:
        self.supplier_tree.delete(
            *self.supplier_tree.get_children()
        )

        for rank, row in enumerate(
            self.dashboard_data.get("supplier_ranking") or [],
            start=1,
        ):
            self.supplier_tree.insert(
                "",
                "end",
                values=(
                    rank,
                    row.get("supplier_name") or "",
                    f"{int(row.get('purchase_count') or 0):,}건",
                    f"{int(row.get('total_quantity') or 0):,}",
                    f"{int(row.get('total_item_amount') or 0):,}원",
                    f"{int(row.get('total_shipping_fee') or 0):,}원",
                    f"{int(row.get('grand_total') or 0):,}원",
                ),
            )

    def _render_product_ranking(self) -> None:
        self.product_tree.delete(
            *self.product_tree.get_children()
        )

        for row in self.dashboard_data.get("product_ranking") or []:
            confirmed = bool(row.get("is_confirmed"))
            unconfirmed_count = int(row.get("unconfirmed_count") or 0)
            tag = ""
            if confirmed and unconfirmed_count == 0:
                tag = self._profit_color_tag(
                    row.get("sales"),
                    row.get("profit"),
                )
            self.product_tree.insert(
                "",
                "end",
                values=(
                    row.get("product_name") or "",
                    f"{int(row.get('order_count') or 0):,}건",
                    f"{int(row.get('total_quantity') or 0):,}",
                    f"{int(row.get('sales') or 0):,}원",
                    (
                        f"{int(row.get('purchase') or 0):,}원"
                        if confirmed else "미확정"
                    ),
                    (
                        f"{int(row.get('profit') or 0):,}원"
                        if confirmed else "미확정"
                    ),
                    (
                        f"{float(row.get('margin_rate')):.2f}%"
                        if confirmed else "미확정"
                    ),
                    f"{unconfirmed_count:,}건",
                    (
                        "부분 미확정"
                        if confirmed and unconfirmed_count > 0
                        else "확정" if confirmed else "미확정"
                    ),
                ),
                tags=((tag,) if tag else ()),
            )

    @staticmethod
    def _profit_color_tag(sales: Any, profit: Any) -> str:
        if sales is None or profit is None:
            return ""
        sales_value = float(sales)
        profit_value = float(profit)
        if sales_value <= 0:
            return ""
        if profit_value < 0:
            return "loss"
        margin_rate = profit_value / sales_value * 100
        if margin_rate < 5:
            return "margin_under_5"
        if margin_rate < 10:
            return "margin_under_10"
        return ""

    def _render_monthly_statistics(self) -> None:
        self.monthly_tree.delete(
            *self.monthly_tree.get_children()
        )

        for row in reversed(
            self.dashboard_data.get("monthly_statistics") or []
        ):
            self.monthly_tree.insert(
                "",
                "end",
                values=(
                    row.get("month") or "",
                    f"{int(row.get('purchase_count') or 0):,}건",
                    f"{int(row.get('total_quantity') or 0):,}",
                    f"{int(row.get('supplier_count') or 0):,}곳",
                    f"{int(row.get('total_item_amount') or 0):,}원",
                    f"{int(row.get('total_shipping_fee') or 0):,}원",
                    f"{int(row.get('grand_total') or 0):,}원",
                ),
            )

    def _render_alerts(self) -> None:
        self.alert_tree.delete(
            *self.alert_tree.get_children()
        )

        alerts = self.dashboard_data.get("alerts") or []

        if not alerts:
            self.alert_tree.insert(
                "",
                "end",
                values=(
                    "정상",
                    "확인사항 없음",
                    "현재 표시할 구매 관련 알림이 없습니다.",
                ),
            )
            return

        for alert in alerts:
            self.alert_tree.insert(
                "",
                "end",
                values=(
                    alert.get("level") or "",
                    alert.get("title") or "",
                    alert.get("message") or "",
                ),
            )

    def _open_calendar(self, target_var: tk.StringVar) -> None:
        CalendarPopup(self, target_var)
