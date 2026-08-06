from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from .service import OrderValidationService


class OrderValidationPage(ttk.Frame):
    """발주대기 주문을 한 번에 검수하는 화면입니다."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        service: OrderValidationService | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or OrderValidationService()
        self.result_rows: dict[str, dict[str, Any]] = {}
        self.status_var = tk.StringVar(value="주문 검수 준비 완료")
        self.total_var = tk.StringVar(value="검수대상 0건")
        self.pass_var = tk.StringVar(value="정상 0건")
        self.warning_var = tk.StringVar(value="확인필요 0건")
        self.fail_var = tk.StringVar(value="처리불가 0건")
        self._build_ui()
        self.after(100, self.refresh)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self, padding=(20, 18, 20, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="주문 검수",
            font=("맑은 고딕", 19, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            header,
            text="발주대기 주문의 상품매핑·공급처·수량·중복 여부를 확인합니다.",
        ).grid(row=1, column=0, pady=(5, 0), sticky="w")

        ttk.Button(
            header,
            text="새로고침",
            command=self.refresh,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        summary = ttk.Frame(self, padding=(20, 0, 20, 10))
        summary.grid(row=1, column=0, sticky="ew")

        for index, variable in enumerate(
            (self.total_var, self.pass_var, self.warning_var, self.fail_var)
        ):
            ttk.Label(
                summary,
                textvariable=variable,
                font=("맑은 고딕", 11, "bold"),
                padding=(12, 8),
                relief="groove",
            ).grid(row=0, column=index, padx=(0, 8), sticky="w")

        table_frame = ttk.Frame(self, padding=(20, 0, 20, 10))
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = (
            "order_number",
            "level",
            "item_count",
            "warning_count",
            "failed_count",
            "summary",
        )
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        headings = {
            "order_number": "주문번호",
            "level": "검수결과",
            "item_count": "상품수",
            "warning_count": "확인",
            "failed_count": "오류",
            "summary": "내용",
        }
        widths = {
            "order_number": 190,
            "level": 90,
            "item_count": 70,
            "warning_count": 70,
            "failed_count": 70,
            "summary": 520,
        }

        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                anchor="center" if column != "summary" else "w",
            )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview,
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._show_selected_detail)

        footer = ttk.Frame(self, padding=(20, 0, 20, 15))
        footer.grid(row=3, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Button(
            footer,
            text="선택 주문 상세",
            command=self._show_selected_detail,
        ).pack(side="right")

    def refresh(self) -> None:
        try:
            self.status_var.set("주문 검수 중...")
            self.update_idletasks()
            summary = self.service.get_summary()

            children = self.tree.get_children()
            if children:
                self.tree.delete(*children)
            self.result_rows.clear()

            for result in summary["results"]:
                item_id = self.tree.insert(
                    "",
                    "end",
                    values=(
                        result.order_number,
                        self._level_text(result.level),
                        result.item_count,
                        result.warning_count,
                        result.failed_count,
                        result.summary,
                    ),
                )
                self.result_rows[item_id] = result.to_dict()

            self.total_var.set(f"검수대상 {summary['total_count']:,}건")
            self.pass_var.set(f"정상 {summary['pass_count']:,}건")
            self.warning_var.set(f"확인필요 {summary['warning_count']:,}건")
            self.fail_var.set(f"처리불가 {summary['fail_count']:,}건")
            self.status_var.set("주문 검수 완료")

        except Exception as error:
            self.status_var.set("주문 검수 오류")
            messagebox.showerror(
                "주문 검수 오류",
                str(error),
                parent=self.winfo_toplevel(),
            )

    def _show_selected_detail(self, _event: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "주문 선택",
                "검수 결과를 확인할 주문을 선택하세요.",
                parent=self.winfo_toplevel(),
            )
            return

        result = self.result_rows[selection[0]]
        issues = result.get("issues") or []

        if not issues:
            detail = "검수 항목이 모두 정상입니다."
        else:
            lines: list[str] = []
            for index, issue in enumerate(issues, start=1):
                lines.append(
                    f"{index}. [{self._level_text(issue.get('level', ''))}] "
                    f"{issue.get('title', '')}\n"
                    f"   {issue.get('message', '')}"
                )
            detail = "\n\n".join(lines)

        messagebox.showinfo(
            f"주문 검수 - {result.get('order_number', '')}",
            detail,
            parent=self.winfo_toplevel(),
        )

    @staticmethod
    def _level_text(level: str) -> str:
        return {
            "PASS": "정상",
            "WARNING": "확인필요",
            "FAIL": "처리불가",
        }.get(level, level)
