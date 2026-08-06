from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from modules.erp_assistant.assistant_service import AssistantAnswer, ERPAssistantService


class ERPAssistantPage(ttk.Frame):
    """Chat-style read-only operational assistant page."""

    SUGGESTED_QUESTIONS = (
        "오늘 주문 몇 건이야?", "미매핑 주문 보여줘", "발주 대기 주문 보여줘",
        "송장 대기 주문 보여줘", "배송중 주문 보여줘", "공급처별 발주 금액 보여줘",
        "오늘 발주 내역 보여줘", "송장번호 없는 주문 보여줘",
    )

    def __init__(self, parent: tk.Misc, status_callback: Callable[[str], None] | None = None) -> None:
        super().__init__(parent, padding=18)
        self.status_callback = status_callback
        self.service = ERPAssistantService()
        self.question_var = tk.StringVar()
        self.notice_var = tk.StringVar(value="ERP 데이터를 조회하는 읽기 전용 도우미입니다.")
        self.result_tree: ttk.Treeview | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(self, text="ERP 도우미", font=("맑은 고딕", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(self, textvariable=self.notice_var).grid(row=1, column=0, sticky="w", pady=(4, 12))

        conversation = ttk.Panedwindow(self, orient="vertical")
        conversation.grid(row=2, column=0, sticky="nsew")
        answer_frame = ttk.LabelFrame(conversation, text="대화", padding=8)
        self.table_frame = ttk.LabelFrame(conversation, text="조회 결과", padding=8)
        conversation.add(answer_frame, weight=1)
        conversation.add(self.table_frame, weight=2)

        self.answer_text = tk.Text(answer_frame, height=10, wrap="word", state="disabled")
        answer_scroll = ttk.Scrollbar(answer_frame, orient="vertical", command=self.answer_text.yview)
        self.answer_text.configure(yscrollcommand=answer_scroll.set)
        self.answer_text.pack(side="left", fill="both", expand=True)
        answer_scroll.pack(side="right", fill="y")
        self._show_empty_table()

        suggestions = ttk.LabelFrame(self, text="추천 질문", padding=8)
        suggestions.grid(row=3, column=0, sticky="ew", pady=(12, 8))
        for index, question in enumerate(self.SUGGESTED_QUESTIONS):
            ttk.Button(suggestions, text=question,
                       command=lambda value=question: self._ask_suggestion(value)).grid(
                row=index // 4, column=index % 4, padx=4, pady=4, sticky="ew"
            )
            suggestions.columnconfigure(index % 4, weight=1)

        input_frame = ttk.Frame(self)
        input_frame.grid(row=4, column=0, sticky="ew")
        input_frame.columnconfigure(0, weight=1)
        self.question_entry = ttk.Entry(input_frame, textvariable=self.question_var)
        self.question_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), ipady=5)
        self.question_entry.bind("<Return>", lambda _event: self.send_question())
        ttk.Button(input_frame, text="보내기", command=self.send_question).grid(row=0, column=1)

    def focus_question(self) -> None:
        self.question_entry.focus_set()

    def _ask_suggestion(self, question: str) -> None:
        self.question_var.set(question)
        self.send_question()

    def send_question(self) -> None:
        question = self.question_var.get().strip()
        if not question:
            self.notice_var.set("질문을 입력해 주세요.")
            return
        self.question_var.set("")
        self._append_message("나", question)
        answer = self.service.ask(question)
        self._append_message("ERP 도우미", answer.message)
        self._render_table(answer)
        self.notice_var.set(answer.message)
        if self.status_callback is not None:
            self.status_callback(answer.message)
        self.question_entry.focus_set()

    def _append_message(self, speaker: str, message: str) -> None:
        self.answer_text.configure(state="normal")
        self.answer_text.insert("end", f"{speaker}\n{message}\n\n")
        self.answer_text.see("end")
        self.answer_text.configure(state="disabled")

    def _clear_table(self) -> None:
        for child in self.table_frame.winfo_children():
            child.destroy()
        self.result_tree = None

    def _show_empty_table(self) -> None:
        self._clear_table()
        ttk.Label(self.table_frame, text="질문 결과가 여기에 표시됩니다.").pack(anchor="center", pady=24)

    def _render_table(self, answer: AssistantAnswer) -> None:
        if not answer.columns:
            self._show_empty_table()
            return
        self._clear_table()
        keys = [column[0] for column in answer.columns]
        tree = ttk.Treeview(self.table_frame, columns=keys, show="headings", height=12)
        vertical = ttk.Scrollbar(self.table_frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(self.table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        for key, title, width in answer.columns:
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=55, anchor="center" if width <= 120 else "w")
        for row in answer.rows:
            tree.insert("", "end", values=[self._display_value(key, row.get(key)) for key in keys])
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table_frame.rowconfigure(0, weight=1)
        self.table_frame.columnconfigure(0, weight=1)
        self.result_tree = tree

    @staticmethod
    def _display_value(key: str, value: object) -> str:
        if value is None:
            return ""
        if key == "purchase_amount":
            try:
                return f"{int(value):,}원"
            except (TypeError, ValueError):
                pass
        return str(value)
