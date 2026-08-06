from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from core.qa.models import QACheckResult, QAReport
from modules.qa_automation.qa_report_service import QAReportService
from modules.qa_automation.qa_service import QAAutomationService


class QAAutomationPage(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = QAAutomationService()
        self.report_service = QAReportService()
        self.status_callback = status_callback
        self.current_report: QAReport | None = None
        self.results: dict[str, QACheckResult] = {}
        self._running = False
        self.status_var = tk.StringVar(value="진단을 실행해 주세요.")
        self.summary_var = tk.StringVar(value="PASS 0 · WARNING 0 · FAILED 0")
        self._build_ui()
        self._render_pending_checks()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        header = ttk.Frame(self, padding=(22, 16, 22, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="QA Automation Center", font=("맑은 고딕", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="production business data를 변경하지 않고 핵심 업무를 진단합니다.").grid(row=1, column=0, sticky="w", pady=(3, 0))
        action_frame = ttk.Frame(header)
        action_frame.grid(row=0, column=1, rowspan=2, sticky="e")
        self.run_button = ttk.Button(action_frame, text="전체 진단 실행", command=self.run_all)
        self.run_button.pack(side="left", padx=(0, 8))
        self.rerun_button = ttk.Button(action_frame, text="선택 검사 재실행", command=self.rerun_selected)
        self.rerun_button.pack(side="left", padx=(0, 8))
        self.pdf_button = ttk.Button(action_frame, text="PDF 보고서", command=lambda: self.export_report("pdf"), state="disabled")
        self.pdf_button.pack(side="left", padx=(0, 8))
        self.excel_button = ttk.Button(action_frame, text="Excel 보고서", command=lambda: self.export_report("xlsx"), state="disabled")
        self.excel_button.pack(side="left")

        summary = ttk.Frame(self, padding=(22, 0, 22, 10))
        summary.grid(row=1, column=0, sticky="ew")
        ttk.Label(summary, textvariable=self.summary_var, font=("맑은 고딕", 11, "bold")).pack(side="left")
        ttk.Label(summary, textvariable=self.status_var).pack(side="right")

        body = ttk.Panedwindow(self, orient="vertical")
        body.grid(row=2, column=0, padx=22, pady=(0, 10), sticky="nsew")
        table_frame = ttk.LabelFrame(body, text="진단 결과", padding=8)
        detail_frame = ttk.LabelFrame(body, text="상세 내용", padding=8)
        body.add(table_frame, weight=3)
        body.add(detail_frame, weight=2)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table_frame, columns=("no", "status", "check", "elapsed", "summary"), show="headings", selectmode="browse")
        for column, title, width, anchor in (
            ("no", "No", 45, "center"),
            ("status", "상태", 90, "center"),
            ("check", "검사", 230, "w"),
            ("elapsed", "소요시간", 90, "e"),
            ("summary", "결과", 560, "w"),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor=anchor)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._show_selected_detail)
        self.tree.bind("<Double-1>", lambda _event: self.rerun_selected())
        self.detail_text = tk.Text(detail_frame, height=9, wrap="word", state="disabled")
        self.detail_text.pack(fill="both", expand=True)
        ttk.Label(self, text="검사 실행은 백그라운드에서 처리되며 화면 갱신은 Tkinter 메인 스레드에서 수행됩니다.", relief="sunken", padding=(12, 6)).grid(row=3, column=0, padx=22, pady=(0, 12), sticky="ew")

    def _render_pending_checks(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, (check_id, name) in enumerate(self.service.CHECKS, start=1):
            self.tree.insert("", "end", iid=check_id, values=(index, "-", name, "-", "대기"))

    def run_all(self) -> None:
        if self._running:
            return
        self._set_running(True, "전체 진단을 시작합니다...")

        def work() -> QAReport:
            return self.service.run_all(
                lambda name: self.after(0, lambda value=name: self.status_var.set(f"실행 중 · {value}"))
            )

        self._start_worker(work, self._finish_full_run)

    def rerun_selected(self) -> None:
        if self._running:
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("선택 검사 재실행", "재실행할 검사를 선택해 주세요.", parent=self)
            return
        check_id = selected[0]
        self._set_running(True, f"재실행 중 · {self.tree.item(check_id, 'values')[2]}")
        self._start_worker(lambda: self.service.run_one(check_id), self._finish_single_run)

    def _start_worker(self, work, success) -> None:
        def runner() -> None:
            try:
                value = work()
            except Exception as error:
                self.after(0, lambda err=error: self._finish_error(err))
            else:
                self.after(0, lambda result=value: success(result))
        threading.Thread(target=runner, daemon=True).start()

    def _finish_full_run(self, report: QAReport) -> None:
        self.current_report = report
        self.results = {row.check_id: row for row in report.results}
        self._render_results()
        self._set_running(False, f"전체 진단 완료 · {report.elapsed_seconds:.2f}초")
        self._enable_reports(True)

    def _finish_single_run(self, report: QAReport) -> None:
        result = report.results[0]
        self.results[result.check_id] = result
        ordered_results = [self.results[cid] for cid, _name in self.service.CHECKS if cid in self.results]
        self.current_report = QAReport(
            metadata=report.metadata,
            results=ordered_results,
            elapsed_seconds=sum(row.elapsed_seconds for row in ordered_results),
            execution_type="mixed",
        )
        self._render_results()
        self._set_running(False, f"개별 진단 완료 · {result.name}")
        self._enable_reports(bool(ordered_results))

    def _finish_error(self, error: Exception) -> None:
        self._set_running(False, f"진단 실행 오류: {error}")
        messagebox.showerror("시스템 진단 오류", str(error), parent=self)

    def _set_running(self, running: bool, message: str) -> None:
        self._running = running
        state = "disabled" if running else "normal"
        self.run_button.configure(state=state)
        self.rerun_button.configure(state=state)
        self.status_var.set(message)
        if self.status_callback is not None:
            self.status_callback(message)

    def _enable_reports(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.pdf_button.configure(state=state)
        self.excel_button.configure(state=state)

    def _render_results(self) -> None:
        for index, (check_id, name) in enumerate(self.service.CHECKS, start=1):
            result = self.results.get(check_id)
            values = (
                index,
                result.status if result else "-",
                name,
                f"{result.elapsed_seconds:.2f}초" if result else "-",
                result.summary if result else "대기",
            )
            if self.tree.exists(check_id):
                self.tree.item(check_id, values=values)
            else:
                self.tree.insert("", "end", iid=check_id, values=values)
        if self.current_report is not None:
            self.summary_var.set(
                f"PASS {self.current_report.pass_count} · WARNING {self.current_report.warning_count} · "
                f"FAILED {self.current_report.failed_count} · 총 {self.current_report.elapsed_seconds:.2f}초"
            )

    def _show_selected_detail(self, _event=None) -> None:
        selected = self.tree.selection()
        result = self.results.get(selected[0]) if selected else None
        text = result.detail if result else "검사를 실행하면 상세 결과가 표시됩니다."
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def export_report(self, report_type: str) -> None:
        if self._running or self.current_report is None:
            return
        self._set_running(True, f"{report_type.upper()} 보고서 생성 중...")
        exporter = self.report_service.export_pdf if report_type == "pdf" else self.report_service.export_excel

        def success(path: str) -> None:
            self._set_running(False, f"보고서 생성 완료: {path}")
            self._enable_reports(True)
            messagebox.showinfo("QA 보고서 생성 완료", f"보고서를 저장했습니다.\n\n{path}", parent=self)

        self._start_worker(lambda: exporter(self.current_report), success)

    def refresh_data(self) -> None:
        if not self._running:
            self.status_var.set("진단을 실행해 주세요.")
