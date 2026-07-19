from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from modules.dashboard.chart_widgets import SevenDayChart
from modules.dashboard.dashboard_service import DashboardService


class DashboardPage(ttk.Frame):
    """업무 알림센터와 7일 통계를 포함한 관리자 대시보드입니다."""

    CARDS = (
        ("today_orders", "오늘 주문", "건"),
        ("today_sales", "오늘 매출", "원"),
        ("average_order", "오늘 객단가", "원"),
        ("total_orders", "전체 주문", "건"),
        ("unmapped", "미매핑", "건"),
        ("purchase_waiting", "발주 대기", "건"),
        ("shipment_waiting", "송장 대기", "건"),
        ("shipping", "배송 중", "건"),
        ("today_profit", "오늘 순이익", "원"),
        ("month_profit", "이번 달 순이익", "원"),
    )

    def __init__(
        self,
        parent: tk.Misc,
        *,
        service: DashboardService | None = None,
        status_callback: Callable[[str], None] | None = None,
        order_action: Callable[[], None] | None = None,
        mapping_action: Callable[[], None] | None = None,
        purchase_action: Callable[[], None] | None = None,
        shipment_action: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or DashboardService()
        self.status_callback = status_callback
        self.actions = {
            "orders": order_action,
            "unmapped": mapping_action,
            "purchase_waiting": purchase_action,
            "shipment_waiting": shipment_action,
            "shipping": shipment_action,
        }
        self.card_vars: dict[str, tk.StringVar] = {}
        self.task_vars: dict[str, tk.StringVar] = {}
        self.updated_var = tk.StringVar(value="마지막 업데이트: -")
        self.notice_var = tk.StringVar(value="데이터를 불러오는 중입니다.")
        self.alert_badge_var = tk.StringVar(value="업무 알림 0")
        self.compare_var = tk.StringVar(value="어제 대비 주문 0건 · 매출 0원")
        self.chart_metric = tk.StringVar(value="order_count")
        self._last_data: dict[str, Any] = {}
        self._startup_alert_shown = False
        self._configure_styles()
        self._build_ui()
        self.after(120, self.refresh_dashboard)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.configure("DashTitle.TLabel", font=("맑은 고딕", 22, "bold"))
        style.configure("DashValue.TLabel", font=("맑은 고딕", 18, "bold"))
        style.configure("DashTask.TLabel", font=("맑은 고딕", 10, "bold"))
        style.configure("AlertBadge.TLabel", font=("맑은 고딕", 10, "bold"), padding=(10, 5))
        style.configure("Dash.Treeview", rowheight=27, font=("맑은 고딕", 9))
        style.configure("Dash.Treeview.Heading", font=("맑은 고딕", 9, "bold"))

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        self._build_header()
        self._build_cards()
        self._build_alert_center()
        self._build_body()
        ttk.Label(self, textvariable=self.notice_var, anchor="w", padding=(24, 7)).grid(
            row=4, column=0, sticky="ew"
        )

    def _build_header(self) -> None:
        frame = ttk.Frame(self, padding=(24, 18, 24, 10))
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="Dashboard", style="DashTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="비선상회 주문·발주·배송 실시간 업무 현황").grid(row=1, column=0, pady=(3, 0), sticky="w")
        ttk.Label(frame, textvariable=self.alert_badge_var, style="AlertBadge.TLabel").grid(row=0, column=1, rowspan=2, padx=(10, 12))
        ttk.Label(frame, textvariable=self.updated_var).grid(row=0, column=2, padx=(10, 12), sticky="e")
        self.refresh_button = ttk.Button(frame, text="새로고침", command=self.refresh_dashboard)
        self.refresh_button.grid(row=0, column=3, rowspan=2, sticky="e")

    def _build_cards(self) -> None:
        frame = ttk.Frame(self, padding=(24, 0, 24, 8))
        frame.grid(row=1, column=0, sticky="ew")
        for column in range(5):
            frame.columnconfigure(column, weight=1, uniform="card")
        for index, (key, title, unit) in enumerate(self.CARDS):
            card = ttk.LabelFrame(frame, padding=(14, 10))
            card.grid(row=index // 5, column=index % 5, padx=4, pady=4, sticky="nsew")
            ttk.Label(card, text=title).pack(anchor="w")
            variable = tk.StringVar(value=f"0{unit}")
            self.card_vars[key] = variable
            ttk.Label(card, textvariable=variable, style="DashValue.TLabel").pack(anchor="w", pady=(5, 0))

    def _build_alert_center(self) -> None:
        outer = ttk.LabelFrame(self, text="오늘 해야 할 일", padding=(10, 8))
        outer.grid(row=2, column=0, padx=24, pady=(2, 8), sticky="ew")
        outer.columnconfigure(0, weight=1)
        task_frame = ttk.Frame(outer)
        task_frame.grid(row=0, column=0, sticky="ew")
        for column in range(4):
            task_frame.columnconfigure(column, weight=1, uniform="task")
        definitions = (
            ("unmapped", "상품 미매핑"),
            ("purchase_waiting", "발주 대기"),
            ("shipment_waiting", "송장 대기"),
            ("shipping", "배송 조회"),
        )
        for column, (key, title) in enumerate(definitions):
            box = ttk.Frame(task_frame, padding=(10, 4))
            box.grid(row=0, column=column, sticky="ew")
            ttk.Label(box, text=title, style="DashTask.TLabel").grid(row=0, column=0, sticky="w")
            variable = tk.StringVar(value="0건")
            self.task_vars[key] = variable
            ttk.Label(box, textvariable=variable, style="DashValue.TLabel").grid(row=1, column=0, sticky="w")
            ttk.Button(box, text="업무 열기", command=lambda k=key: self._run_action(k)).grid(row=0, column=1, rowspan=2, padx=(8, 0), sticky="e")
        ttk.Label(outer, textvariable=self.compare_var).grid(row=1, column=0, pady=(7, 0), sticky="w")

    def _build_body(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.grid(row=3, column=0, padx=24, pady=(0, 8), sticky="nsew")
        orders_tab = ttk.Frame(notebook, padding=10)
        stats_tab = ttk.Frame(notebook, padding=10)
        supplier_tab = ttk.Frame(notebook, padding=10)
        notebook.add(orders_tab, text="최근 주문")
        notebook.add(stats_tab, text="최근 7일 통계")
        notebook.add(supplier_tab, text="공급처 발주")
        self._build_orders(orders_tab)
        self._build_stats(stats_tab)
        self._build_suppliers(supplier_tab)

    def _build_orders(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        columns = ("ordered_at", "platform", "order_number", "receiver", "item", "amount", "status")
        self.order_tree = ttk.Treeview(parent, columns=columns, show="headings", style="Dash.Treeview")
        headings = ("주문일시", "플랫폼", "주문번호", "수취인", "상품", "결제금액", "상태")
        widths = (125, 75, 145, 85, 340, 100, 90)
        for column, heading, width in zip(columns, headings, widths):
            self.order_tree.heading(column, text=heading)
            self.order_tree.column(column, width=width, anchor="e" if column == "amount" else "center" if column in {"ordered_at", "platform", "receiver", "status"} else "w")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.order_tree.yview)
        self.order_tree.configure(yscrollcommand=scrollbar.set)
        self.order_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.order_tree.bind("<Double-1>", lambda _event: self._run_action("orders"))

    def _build_stats(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        control = ttk.Frame(parent)
        control.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(control, text="표시 기준:").pack(side="left")
        ttk.Radiobutton(control, text="주문건수", value="order_count", variable=self.chart_metric, command=self._redraw_chart).pack(side="left", padx=(8, 4))
        ttk.Radiobutton(control, text="매출", value="sales", variable=self.chart_metric, command=self._redraw_chart).pack(side="left")
        self.chart = SevenDayChart(parent)
        self.chart.grid(row=1, column=0, sticky="nsew")

    def _build_suppliers(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        columns = ("supplier", "count", "quantity")
        self.supplier_tree = ttk.Treeview(parent, columns=columns, show="headings", style="Dash.Treeview")
        for column, heading, width in (("supplier", "공급처", 260), ("count", "발주건수", 120), ("quantity", "총수량", 120)):
            self.supplier_tree.heading(column, text=heading)
            self.supplier_tree.column(column, width=width, anchor="w" if column == "supplier" else "e")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.supplier_tree.yview)
        self.supplier_tree.configure(yscrollcommand=scrollbar.set)
        self.supplier_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def refresh_dashboard(self) -> None:
        self.refresh_button.configure(state="disabled")
        self.notice_var.set("대시보드 데이터를 불러오는 중입니다.")
        self._set_status("대시보드 새로고침 중...")
        try:
            data = self.service.get_dashboard_data()
            self._last_data = data
            self._apply_data(data)
            self.updated_var.set(f"마지막 업데이트: {data.get('updated_at', '-')}")
            errors = data.get("errors", [])
            self.notice_var.set("일부 데이터 조회 실패: " + " / ".join(errors) if errors else "대시보드가 최신 데이터로 갱신되었습니다.")
            self._set_status("대시보드 새로고침 완료")
            if not self._startup_alert_shown:
                self._startup_alert_shown = True
                self.after(150, self.show_work_alert)
        except Exception as error:
            self.notice_var.set("대시보드 데이터를 불러오지 못했습니다.")
            self._set_status("대시보드 새로고침 오류")
            messagebox.showerror("대시보드 오류", f"대시보드 데이터를 불러오지 못했습니다.\n\n{error}", parent=self.winfo_toplevel())
        finally:
            self.refresh_button.configure(state="normal")

    def _apply_data(self, data: dict[str, Any]) -> None:
        summary = data.get("summary", {})
        for key, _title, unit in self.CARDS:
            value = self._to_int(summary.get(key))
            self.card_vars[key].set(f"{value:,}원" if unit == "원" else f"{value:,}건")
        task_map = {str(task.get("key")): self._to_int(task.get("count")) for task in data.get("tasks", [])}
        for key, variable in self.task_vars.items():
            variable.set(f"{task_map.get(key, 0):,}건")
        alert_count = self._to_int(data.get("alert_count"))
        urgent_count = self._to_int(data.get("urgent_count"))
        self.alert_badge_var.set(f"업무 알림 {alert_count}개 · 처리 {urgent_count:,}건")
        comparisons = data.get("comparisons", {})
        self.compare_var.set(f"어제 대비 주문 {self._signed(self._to_int(comparisons.get('order_change')), '건')} · 매출 {self._signed(self._to_int(comparisons.get('sales_change')), '원')}")
        self._fill_orders(data.get("recent_orders", []))
        self._fill_suppliers(data.get("supplier_summary", []))
        self._redraw_chart()

    def _fill_orders(self, rows: list[dict[str, Any]]) -> None:
        self._clear_tree(self.order_tree)
        for row in rows:
            self.order_tree.insert("", "end", values=(row.get("ordered_at", "-"), row.get("platform", "-"), row.get("order_number", "-"), row.get("receiver_name", "-"), row.get("item_summary", "-"), f"{self._to_int(row.get('total_amount')):,}원", row.get("status", "-")))

    def _fill_suppliers(self, rows: list[dict[str, Any]]) -> None:
        self._clear_tree(self.supplier_tree)
        for row in sorted(rows, key=lambda item: self._to_int(item.get("purchase_count")), reverse=True):
            self.supplier_tree.insert("", "end", values=(row.get("supplier_name", "공급처 미지정"), f"{self._to_int(row.get('purchase_count')):,}건", f"{self._to_int(row.get('total_quantity')):,}개"))

    def _redraw_chart(self) -> None:
        self.chart.set_data(self._last_data.get("seven_day_stats", []), self.chart_metric.get())

    def show_work_alert(self) -> None:
        tasks = [task for task in self._last_data.get("tasks", []) if self._to_int(task.get("count")) > 0]
        if not tasks:
            return
        lines = ["오늘 처리할 업무가 있습니다.", ""]
        lines.extend(f"• {task.get('title')}: {self._to_int(task.get('count')):,}건" for task in tasks)
        messagebox.showinfo("오늘의 업무 알림", "\n".join(lines), parent=self.winfo_toplevel())

    def _run_action(self, key: str) -> None:
        action = self.actions.get(key)
        if action is not None:
            action()

    def _set_status(self, message: str) -> None:
        if self.status_callback is not None:
            self.status_callback(message)

    @staticmethod
    def _signed(value: int, unit: str) -> str:
        sign = "+" if value > 0 else ""
        return f"{sign}{value:,}{unit}"

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        children = tree.get_children()
        if children:
            tree.delete(*children)

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return 0
