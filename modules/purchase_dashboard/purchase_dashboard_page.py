from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from modules.purchase_dashboard.purchase_dashboard_service import (
    PurchaseDashboardService,
)


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

        self.period_var = tk.StringVar(value="이번달")
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="구매 통계를 불러오는 중입니다."
        )

        self.today_count_var = tk.StringVar(value="0건")
        self.today_amount_var = tk.StringVar(value="0원")
        self.period_amount_var = tk.StringVar(value="0원")
        self.supplier_count_var = tk.StringVar(value="0곳")
        self.pending_count_var = tk.StringVar(value="0건")
        self.average_price_var = tk.StringVar(value="0원")

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
            text="구매 통계",
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
            ("오늘 발주", self.today_count_var),
            ("오늘 발주금액", self.today_amount_var),
            ("조회기간 발주금액", self.period_amount_var),
            ("발주 공급처", self.supplier_count_var),
            ("발주대기", self.pending_count_var),
            ("평균 매입단가", self.average_price_var),
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

        ttk.Label(frame, text="기간").grid(
            row=0,
            column=0,
            padx=(0, 5),
        )

        self.period_combo = ttk.Combobox(
            frame,
            textvariable=self.period_var,
            values=self.service.PERIODS,
            state="readonly",
            width=12,
        )
        self.period_combo.grid(
            row=0,
            column=1,
            padx=(0, 14),
        )
        self.period_combo.bind(
            "<<ComboboxSelected>>",
            self._on_period_changed,
        )

        ttk.Label(frame, text="시작일").grid(
            row=0,
            column=2,
            padx=(0, 5),
        )
        self.start_entry = ttk.Entry(
            frame,
            textvariable=self.start_date_var,
            width=12,
            state="disabled",
        )
        self.start_entry.grid(
            row=0,
            column=3,
            padx=(0, 12),
        )

        ttk.Label(frame, text="종료일").grid(
            row=0,
            column=4,
            padx=(0, 5),
        )
        self.end_entry = ttk.Entry(
            frame,
            textvariable=self.end_date_var,
            width=12,
            state="disabled",
        )
        self.end_entry.grid(
            row=0,
            column=5,
            padx=(0, 12),
        )

        ttk.Button(
            frame,
            text="조회",
            command=self.refresh,
        ).grid(row=0, column=6)

        ttk.Label(
            frame,
            text="직접입력 형식: YYYY-MM-DD",
        ).grid(
            row=0,
            column=7,
            padx=(12, 0),
            sticky="w",
        )

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
                "rank",
                "supplier_product_code",
                "product_name",
                "purchase_count",
                "total_quantity",
                "average_unit_price",
                "total_item_amount",
            ),
            headings={
                "rank": "순위",
                "supplier_product_code": "공급처 코드",
                "product_name": "상품명",
                "purchase_count": "발주횟수",
                "total_quantity": "총수량",
                "average_unit_price": "평균단가",
                "total_item_amount": "총매입",
            },
            widths={
                "rank": 65,
                "supplier_product_code": 130,
                "product_name": 280,
                "purchase_count": 100,
                "total_quantity": 100,
                "average_unit_price": 130,
                "total_item_amount": 150,
            },
        )

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
                period_name=self.period_var.get(),
                custom_start=self.start_date_var.get(),
                custom_end=self.end_date_var.get(),
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
                "구매 통계를 최신 데이터로 갱신했습니다."
            )

        except Exception as error:
            self.status_var.set(
                "구매 통계를 불러오지 못했습니다."
            )
            messagebox.showerror(
                "구매 통계 오류",
                (
                    "구매 통계를 불러오는 중 "
                    "오류가 발생했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

    def _render_kpi(self) -> None:
        summary = self.dashboard_data.get("summary") or {}
        today = self.dashboard_data.get("today_summary") or {}

        self.today_count_var.set(
            f"{int(today.get('purchase_count') or 0):,}건"
        )
        self.today_amount_var.set(
            f"{int(today.get('grand_total') or 0):,}원"
        )
        self.period_amount_var.set(
            f"{int(summary.get('grand_total') or 0):,}원"
        )
        self.supplier_count_var.set(
            f"{int(summary.get('supplier_count') or 0):,}곳"
        )
        self.pending_count_var.set(
            f"{int(summary.get('pending_count') or 0):,}건"
        )
        self.average_price_var.set(
            f"{int(float(summary.get('average_unit_price') or 0)):,}원"
        )

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

        for rank, row in enumerate(
            self.dashboard_data.get("product_ranking") or [],
            start=1,
        ):
            self.product_tree.insert(
                "",
                "end",
                values=(
                    rank,
                    row.get("supplier_product_code") or "",
                    row.get("product_name") or "",
                    f"{int(row.get('purchase_count') or 0):,}회",
                    f"{int(row.get('total_quantity') or 0):,}",
                    f"{int(float(row.get('average_unit_price') or 0)):,}원",
                    f"{int(row.get('total_item_amount') or 0):,}원",
                ),
            )

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

    def _on_period_changed(
        self,
        event: tk.Event | None = None,
    ) -> None:
        custom = self.period_var.get() == "직접입력"
        state = "normal" if custom else "disabled"

        self.start_entry.configure(state=state)
        self.end_entry.configure(state=state)

        if not custom:
            self.start_date_var.set("")
            self.end_date_var.set("")
            self.refresh()