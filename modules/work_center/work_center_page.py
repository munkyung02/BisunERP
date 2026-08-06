from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from modules.work_center.work_center_service import WorkCenterService, WorkTask


class WorkCenterPage(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        *,
        navigate_callback: Callable[[str], None],
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, padding=22)
        self.navigate_callback = navigate_callback
        self.status_callback = status_callback or (lambda _text: None)
        self.service = WorkCenterService()
        self.summary_vars = {key: tk.StringVar(value="0") for key in (
            "orders_today", "purchases_today", "products", "suppliers"
        )}
        self.task_frame: ttk.Frame | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="작업센터", font=("맑은 고딕", 22, "bold")).pack(side="left")
        ttk.Label(header, text="오늘 처리할 업무를 한곳에서 확인합니다.", font=("맑은 고딕", 10)).pack(side="left", padx=(14, 0), pady=(8, 0))
        ttk.Button(header, text="새로고침", command=self.refresh_data).pack(side="right")

        cards = ttk.Frame(self)
        cards.pack(fill="x", pady=(0, 18))
        for index, (key, title) in enumerate((
            ("orders_today", "오늘 주문"),
            ("purchases_today", "오늘 발주"),
            ("products", "사용 상품"),
            ("suppliers", "거래 공급처"),
        )):
            cards.columnconfigure(index, weight=1)
            card = ttk.LabelFrame(cards, text=title, padding=14)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0))
            ttk.Label(card, textvariable=self.summary_vars[key], font=("맑은 고딕", 22, "bold")).pack(anchor="center")

        quick = ttk.LabelFrame(self, text="빠른 작업", padding=12)
        quick.pack(fill="x", pady=(0, 18))
        for title, target in (("신규 상품 등록", "상품관리"), ("신규 공급처 등록", "공급처관리"), ("주문관리", "주문관리"), ("발주관리", "발주관리")):
            ttk.Button(quick, text=title, command=lambda t=target: self._navigate(t)).pack(side="left", padx=(0, 8))

        ttk.Label(self, text="오늘 해야 할 일", font=("맑은 고딕", 16, "bold")).pack(anchor="w", pady=(0, 8))
        self.task_frame = ttk.Frame(self)
        self.task_frame.pack(fill="both", expand=True)
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            summary = self.service.get_summary()
            for key, variable in self.summary_vars.items():
                variable.set(f"{int(summary.get(key, 0)):,}")
            self._render_tasks(self.service.get_tasks())
            self.status_callback("작업센터 새로고침 완료")
        except Exception as error:
            self.status_callback(f"작업센터 조회 실패: {error}")

    def _render_tasks(self, tasks: list[WorkTask]) -> None:
        if self.task_frame is None:
            return
        for child in self.task_frame.winfo_children():
            child.destroy()

        active = [task for task in tasks if task.count > 0]
        if not active:
            ttk.Label(self.task_frame, text="현재 긴급하게 처리할 작업이 없습니다.", font=("맑은 고딕", 13)).pack(anchor="center", pady=50)
            return

        for task in sorted(active, key=lambda item: item.priority):
            row = ttk.Frame(self.task_frame, padding=(12, 10), relief="groove")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=task.title, font=("맑은 고딕", 12, "bold"), width=22).pack(side="left")
            ttk.Label(row, text=task.description).pack(side="left", fill="x", expand=True)
            ttk.Label(row, text=f"{task.count:,}건", font=("맑은 고딕", 12, "bold"), width=10, anchor="e").pack(side="left", padx=12)
            ttk.Button(row, text="처리하기", command=lambda t=task.target: self._navigate(t)).pack(side="right")

    def _navigate(self, target: str) -> None:
        self.status_callback(f"{target} 화면으로 이동")
        self.navigate_callback(target)
