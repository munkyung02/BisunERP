from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from .integrity_service import IntegrityIssue, IntegrityService


class IntegrityPage(ttk.Frame):
    def __init__(self, parent, *, status_callback: Callable[[str], None] | None = None,
                 refresh_callback: Callable[[], None] | None = None) -> None:
        super().__init__(parent, padding=18)
        self.service = IntegrityService()
        self.status_callback = status_callback or (lambda _message: None)
        self.refresh_callback = refresh_callback or (lambda: None)
        self.category_var = tk.StringVar(value="전체")
        self.severity_var = tk.StringVar(value="전체")
        self.keyword_var = tk.StringVar()
        self.summary_vars = {name: tk.StringVar(value="0") for name in ("전체", "긴급", "주의", "확인", "자동복구")}
        self.rows: dict[str, IntegrityIssue] = {}
        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self); top.pack(fill="x")
        ttk.Label(top, text="데이터 점검·복구센터", font=("맑은 고딕", 20, "bold")).pack(side="left")
        ttk.Button(top, text="전체 점검", command=self.refresh_data).pack(side="right")

        ttk.Label(self, text="주문·상품·발주·송장 데이터의 연결 상태와 업무 상태값을 검사합니다. 자동복구 전 DB 백업이 생성됩니다.").pack(anchor="w", pady=(5, 12))
        cards = ttk.Frame(self); cards.pack(fill="x", pady=(0, 10))
        for index, name in enumerate(("전체", "긴급", "주의", "확인", "자동복구")):
            box = ttk.LabelFrame(cards, text=name, padding=9); box.grid(row=0, column=index, sticky="ew", padx=4)
            cards.columnconfigure(index, weight=1)
            ttk.Label(box, textvariable=self.summary_vars[name], font=("맑은 고딕", 17, "bold")).pack()

        filters = ttk.Frame(self); filters.pack(fill="x", pady=(0, 10))
        ttk.Label(filters, text="심각도").pack(side="left")
        ttk.Combobox(filters, textvariable=self.severity_var, values=("전체", "긴급", "주의", "확인"), state="readonly", width=8).pack(side="left", padx=(6, 12))
        ttk.Label(filters, text="구분").pack(side="left")
        ttk.Combobox(filters, textvariable=self.category_var, values=("전체", "참조무결성", "주문금액", "상태동기화", "필수정보", "중복데이터"), state="readonly", width=12).pack(side="left", padx=(6, 12))
        ttk.Label(filters, text="검색").pack(side="left")
        entry = ttk.Entry(filters, textvariable=self.keyword_var, width=28); entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _event: self._apply_filter())
        ttk.Button(filters, text="필터 적용", command=self._apply_filter).pack(side="left")
        ttk.Button(filters, text="선택 자동복구", command=self.repair_selected).pack(side="right")
        ttk.Button(filters, text="복구 가능 전체처리", command=self.repair_all).pack(side="right", padx=(0, 6))

        columns = ("severity", "category", "reference", "title", "detail", "fixable")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended", height=24)
        headers = {"severity":"심각도", "category":"구분", "reference":"대상", "title":"점검내용", "detail":"상세", "fixable":"자동복구"}
        widths = {"severity":70, "category":100, "reference":150, "title":190, "detail":390, "fixable":80}
        for column in columns:
            self.tree.heading(column, text=headers[column])
            self.tree.column(column, width=widths[column], anchor="w" if column in ("title", "detail") else "center")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        self._issues: list[IntegrityIssue] = []

    def refresh_data(self) -> None:
        try:
            self.status_callback("데이터 무결성 점검 중...")
            self.update_idletasks()
            self._issues = self.service.scan()
            summary = self.service.get_summary(self._issues)
            for name, var in self.summary_vars.items(): var.set(f"{summary.get(name, 0):,}")
            self._apply_filter()
            self.status_callback(f"데이터 점검 완료: 문제 {len(self._issues):,}건")
        except Exception as error:
            messagebox.showerror("점검 오류", f"데이터 점검 중 오류가 발생했습니다.\n\n{error}", parent=self)
            self.status_callback("데이터 점검 오류")

    def _apply_filter(self) -> None:
        severity = self.severity_var.get(); category = self.category_var.get(); term = self.keyword_var.get().strip().lower()
        filtered = []
        for issue in self._issues:
            if severity != "전체" and issue.severity != severity: continue
            if category != "전체" and issue.category != category: continue
            if term and term not in " ".join((issue.reference, issue.title, issue.detail)).lower(): continue
            filtered.append(issue)
        for item in self.tree.get_children(): self.tree.delete(item)
        self.rows = {}
        for index, issue in enumerate(filtered):
            iid = str(index); self.rows[iid] = issue
            self.tree.insert("", "end", iid=iid, values=(issue.severity, issue.category, issue.reference, issue.title, issue.detail, "가능" if issue.fixable else "수동확인"))
        self.status_callback(f"점검결과 {len(filtered):,}건 표시")

    def repair_selected(self) -> None:
        selected = [self.rows[iid] for iid in self.tree.selection() if iid in self.rows]
        self._repair(selected)

    def repair_all(self) -> None:
        self._repair([issue for issue in self._issues if issue.fixable])

    def _repair(self, issues: list[IntegrityIssue]) -> None:
        targets = [issue for issue in issues if issue.fixable]
        if not targets:
            messagebox.showinfo("자동복구", "선택한 항목 중 자동복구 가능한 문제가 없습니다.", parent=self)
            return
        if not messagebox.askyesno("자동복구 확인", f"복구 가능한 {len(targets):,}건을 처리합니다.\n처리 전 데이터베이스 백업이 자동 생성됩니다.\n\n계속하시겠습니까?", parent=self):
            return
        result = self.service.repair(targets)
        message = f"자동복구 {result['fixed']:,}건 완료"
        if result.get("backup"): message += f"\n\n백업 파일:\n{result['backup']}"
        if result.get("failed"): message += f"\n\n실패 {len(result['failed']):,}건"
        messagebox.showinfo("자동복구 완료", message, parent=self)
        self.refresh_data(); self.refresh_callback()
