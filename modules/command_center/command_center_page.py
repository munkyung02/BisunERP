from __future__ import annotations

import tkinter as tk
import threading
from tkinter import messagebox, ttk
from typing import Callable

from modules.command_center.command_center_service import CommandCenterService
from modules.command_center.daily_operation_summary_dialog import (
    DailyOperationSummaryDialog,
)


class CommandCenterPage(ttk.Frame):
    """일일 주문→매핑→발주→송장 업무를 한 화면에서 연결합니다."""

    CARDS = (
        ("today_orders", "오늘 주문", "건"),
        ("unmapped", "미매핑 주문", "건"),
        ("purchase_pending", "발주 대기", "건"),
        ("shipment_pending", "송장 대기", "건"),
        ("shipping", "배송 중", "건"),
        ("failed_jobs", "실패 작업", "건"),
        ("today_purchase_amount", "오늘 발주금액", "원"),
        ("today_sales_amount", "오늘 매출금액", "원"),
    )

    def __init__(
        self,
        parent: tk.Misc,
        *,
        status_callback: Callable[[str], None] | None = None,
        order_sync_action: Callable[[], None] | None = None,
        validation_action: Callable[[], None] | None = None,
        purchase_action: Callable[[], None] | None = None,
        shipment_action: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = CommandCenterService()
        self.status_callback = status_callback
        self.actions = {
            "주문 동기화": order_sync_action,
            "주문 검수": validation_action,
            "발주 생성": purchase_action,
            "송장 등록": shipment_action,
        }
        self.card_vars = {
            key: tk.StringVar(value="-")
            for key, _title, _unit in self.CARDS
        }
        self.notice_var = tk.StringVar(value="업무 현황을 불러오는 중입니다.")
        self._daily_operation_running = False
        self._build_ui()
        self.after(100, self.refresh_data)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, padding=(22, 16, 22, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text="ERP Command Center",
            font=("맑은 고딕", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="오늘의 주문·매핑·발주·송장 업무를 순서대로 처리합니다.",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Button(header, text="새로고침", command=self.refresh_data).grid(
            row=0, column=1, rowspan=2, sticky="e"
        )

        cards = ttk.Frame(self, padding=(22, 4, 22, 10))
        cards.grid(row=1, column=0, sticky="ew")
        for index, (key, title, unit) in enumerate(self.CARDS):
            row, column = divmod(index, 4)
            card = ttk.LabelFrame(cards, text=title, padding=(14, 8))
            card.grid(row=row, column=column, sticky="ew", padx=4, pady=4)
            cards.columnconfigure(column, weight=1)
            ttk.Label(
                card,
                textvariable=self.card_vars[key],
                font=("맑은 고딕", 16, "bold"),
                anchor="center",
            ).pack(fill="x")
            ttk.Label(card, text=unit, anchor="center").pack(fill="x")

        actions = ttk.LabelFrame(self, text="오늘 업무", padding=10)
        actions.grid(row=2, column=0, padx=22, pady=(0, 10), sticky="ew")
        buttons = (
            ("주문 동기화", lambda: self._run_navigation("주문 동기화")),
            ("자동매핑", self._run_auto_mapping),
            ("주문 검수", lambda: self._run_navigation("주문 검수")),
            ("발주 생성", lambda: self._run_navigation("발주 생성")),
            ("송장 등록", lambda: self._run_navigation("송장 등록")),
        )
        for index, (label, command) in enumerate(buttons):
            ttk.Button(actions, text=label, command=command).grid(
                row=0, column=index, padx=(0, 8), sticky="ew"
            )
            actions.columnconfigure(index, weight=1)
        ttk.Button(
            actions,
            text="채널별 송장파일 생성 - 준비 중",
            state="disabled",
        ).grid(row=0, column=5, sticky="ew")
        actions.columnconfigure(5, weight=1)
        self.daily_operation_button = ttk.Button(
            actions,
            text="오늘 업무 시작",
            command=self._start_daily_operation,
        )
        self.daily_operation_button.grid(
            row=1,
            column=0,
            columnspan=6,
            pady=(10, 0),
            sticky="ew",
        )

        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=3, column=0, padx=22, pady=(0, 10), sticky="nsew")

        exception_frame = ttk.LabelFrame(body, text="Exception Center", padding=8)
        activity_frame = ttk.LabelFrame(body, text="Activity Log", padding=8)
        body.add(exception_frame, weight=1)
        body.add(activity_frame, weight=2)

        self.exception_tree = ttk.Treeview(
            exception_frame,
            columns=("category", "count", "detail"),
            show="headings",
            height=12,
        )
        for column, title, width in (
            ("category", "예외", 190),
            ("count", "건수", 65),
            ("detail", "내용", 280),
        ):
            self.exception_tree.heading(column, text=title)
            self.exception_tree.column(column, width=width, anchor="center" if column == "count" else "w")
        self.exception_tree.pack(fill="both", expand=True)

        self.activity_tree = ttk.Treeview(
            activity_frame,
            columns=("time", "action", "result", "message"),
            show="headings",
            height=12,
        )
        for column, title, width in (
            ("time", "시간", 135),
            ("action", "작업", 115),
            ("result", "결과", 70),
            ("message", "내용", 390),
        ):
            self.activity_tree.heading(column, text=title)
            self.activity_tree.column(column, width=width, anchor="center" if column == "result" else "w")
        self.activity_tree.pack(fill="both", expand=True)

        ttk.Label(
            self,
            textvariable=self.notice_var,
            anchor="w",
            relief="sunken",
            padding=(12, 6),
        ).grid(row=4, column=0, padx=22, pady=(0, 12), sticky="ew")

    def refresh_data(self) -> None:
        try:
            data = self.service.get_data()
            cards = data["cards"]
            for key, _title, unit in self.CARDS:
                value = int(cards.get(key, 0) or 0)
                self.card_vars[key].set(f"{value:,}")

            self._replace_rows(
                self.exception_tree,
                (
                    (row["category"], f"{row['count']:,}", row["detail"])
                    for row in data["exceptions"]
                ),
            )
            self._replace_rows(
                self.activity_tree,
                (
                    (
                        str(row["created_at"])[:19],
                        row["action"],
                        row["result_status"],
                        row["result_message"],
                    )
                    for row in data["activity"]
                ),
            )
            error_count = len(data.get("errors", []))
            self.notice_var.set(
                "Command Center 업데이트 완료"
                if not error_count
                else f"업데이트 완료 · 집계 확인사항 {error_count}건"
            )
        except Exception as error:
            self.notice_var.set(f"Command Center 조회 실패: {error}")

    def _run_navigation(self, action: str) -> None:
        callback = self.actions.get(action)
        if callback is None:
            messagebox.showwarning("준비 중", f"{action} 연결을 확인하세요.", parent=self)
            return
        result = self.service.run_navigation_action(action, callback)
        self._show_result(action, result)

    def _run_auto_mapping(self) -> None:
        result = self.service.run_auto_mapping()
        self._show_result("자동매핑", result)

    def _start_daily_operation(self) -> None:
        if self._daily_operation_running:
            return
        self._daily_operation_running = True
        self.daily_operation_button.configure(state="disabled")
        self.notice_var.set("오늘 업무를 시작합니다...")

        def progress(step_name: str) -> None:
            self.after(
                0,
                lambda name=step_name: self.notice_var.set(f"실행 중 · {name}"),
            )

        def worker() -> None:
            try:
                result = self.service.run_daily_operation(progress)
            except Exception as error:
                self.after(0, lambda err=error: self._finish_daily_operation(None, err))
            else:
                self.after(0, lambda value=result: self._finish_daily_operation(value))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_daily_operation(
        self,
        result: dict | None,
        error: Exception | None = None,
    ) -> None:
        self._daily_operation_running = False
        self.daily_operation_button.configure(state="normal")
        if error is not None or result is None:
            message = str(error or "오늘 업무 실행 결과를 확인할 수 없습니다.")
            self.notice_var.set(f"오늘 업무 실행 실패: {message}")
            messagebox.showerror("오늘 업무 시작 실패", message, parent=self)
            self.refresh_data()
            return

        self.notice_var.set(
            "오늘 업무 완료 · "
            f"PASS {result.get('pass_count', 0):,} · "
            f"WARNING {result.get('warning_count', 0):,} · "
            f"FAILED {result.get('failed_count', 0):,}"
        )
        self.refresh_data()
        DailyOperationSummaryDialog(self, result)

    def _show_result(self, action: str, result: dict) -> None:
        message = str(result.get("message") or "")
        if self.status_callback is not None:
            self.status_callback(message)
        if not result.get("success"):
            messagebox.showerror(f"{action} 실패", message, parent=self)
        self.refresh_data()

    @staticmethod
    def _replace_rows(tree: ttk.Treeview, rows) -> None:
        for item_id in tree.get_children():
            tree.delete(item_id)
        for values in rows:
            tree.insert("", "end", values=values)
