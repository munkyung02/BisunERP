from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from .operations_check_service import OperationsCheckService


class OperationsCheckPage(ttk.Frame):
    def __init__(self, parent, *, status_callback: Callable[[str], None] | None = None,
                 navigate_callback: Callable[[str], None] | None = None) -> None:
        super().__init__(parent, padding=18)
        self.service = OperationsCheckService()
        self.status_callback = status_callback or (lambda _m: None)
        self.navigate_callback = navigate_callback or (lambda _m: None)
        self.category_var = tk.StringVar(value="전체")
        self.keyword_var = tk.StringVar()
        self.summary_vars = {name: tk.StringVar(value="0") for name in ("활성 공급처", "활성 상품", "미매핑", "발주대기", "송장대기")}
        self.rows: dict[str, dict] = {}
        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self); top.pack(fill="x")
        ttk.Label(top, text="실무 운영 점검", font=("맑은 고딕", 20, "bold")).pack(side="left")
        ttk.Label(top, text="상품·공급처 등록 후 실제 주문 흐름을 안전하게 점검합니다.").pack(side="left", padx=18, pady=(7,0))
        ttk.Button(top, text="새로고침", command=self.refresh_data).pack(side="right")

        cards = ttk.Frame(self); cards.pack(fill="x", pady=(15, 10))
        for idx, name in enumerate(self.summary_vars):
            box = ttk.LabelFrame(cards, text=name, padding=10); box.grid(row=0, column=idx, sticky="ew", padx=4)
            cards.columnconfigure(idx, weight=1)
            ttk.Label(box, textvariable=self.summary_vars[name], font=("맑은 고딕", 17, "bold")).pack()

        tools = ttk.LabelFrame(self, text="실무 시작 도구", padding=10)
        tools.pack(fill="x", pady=(0, 10))
        ttk.Button(tools, text="① 현재 DB 백업", command=self.backup_database).pack(side="left", padx=(0, 7))
        ttk.Button(tools, text="② 테스트 주문 1건 생성", command=self.create_test_order).pack(side="left", padx=7)
        ttk.Button(tools, text="③ TEST 주문 모두 삭제", command=self.delete_test_orders).pack(side="left", padx=7)
        ttk.Label(tools, text="※ TEST-로 시작하는 주문만 삭제되며 실제 주문은 삭제되지 않습니다.").pack(side="left", padx=15)

        filters = ttk.Frame(self); filters.pack(fill="x", pady=(0, 10))
        ttk.Label(filters, text="구분").pack(side="left")
        ttk.Combobox(filters, textvariable=self.category_var,
                     values=("전체","기초데이터","주문정보","상품매핑","발주","송장"),
                     state="readonly", width=12).pack(side="left", padx=(6,12))
        ttk.Label(filters, text="검색").pack(side="left")
        entry = ttk.Entry(filters, textvariable=self.keyword_var, width=30); entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self.refresh_data())
        ttk.Button(filters, text="조회", command=self.refresh_data).pack(side="left")
        ttk.Button(filters, text="선택 항목 처리 화면 열기", command=self.open_selected).pack(side="right")

        table_frame = ttk.Frame(self); table_frame.pack(fill="both", expand=True)
        columns=("level","category","reference","title","detail","target")
        self.tree=ttk.Treeview(table_frame, columns=columns, show="headings", height=22)
        headers={"level":"중요도","category":"구분","reference":"주문/상품","title":"확인 항목","detail":"상세","target":"처리 화면"}
        widths={"level":70,"category":90,"reference":155,"title":180,"detail":430,"target":110}
        for c in columns:
            self.tree.heading(c,text=headers[c]); self.tree.column(c,width=widths[c],anchor="w" if c in ("title","detail") else "center")
        y=ttk.Scrollbar(table_frame,orient="vertical",command=self.tree.yview); self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side="left",fill="both",expand=True); y.pack(side="right",fill="y")
        self.tree.bind("<Double-1>", lambda _e:self.open_selected())

    def refresh_data(self) -> None:
        try:
            summary=self.service.get_summary()
            for name,var in self.summary_vars.items(): var.set(f"{summary.get(name,0):,}")
            rows=self.service.get_checks(self.category_var.get(),self.keyword_var.get())
            for item in self.tree.get_children(): self.tree.delete(item)
            self.rows={}
            for idx,row in enumerate(rows):
                iid=str(idx); self.rows[iid]=row
                self.tree.insert("","end",iid=iid,values=(row["level"],row["category"],row["reference"],row["title"],row["detail"],row["target"]))
            self.status_callback(f"실무 운영 점검 {len(rows):,}건 조회")
        except Exception as error:
            messagebox.showerror("실무점검", f"점검 중 오류가 발생했습니다.\n\n{error}", parent=self)

    def backup_database(self) -> None:
        try:
            path = self.service.create_backup()
            self.status_callback(f"DB 백업 완료: {path.name}")
            messagebox.showinfo("DB 백업 완료", f"안전 백업을 만들었습니다.\n\n{path}", parent=self)
        except Exception as error:
            messagebox.showerror("백업 실패", str(error), parent=self)

    def create_test_order(self) -> None:
        try:
            order_number = self.service.create_test_order()
            self.refresh_data()
            self.status_callback(f"테스트 주문 생성: {order_number}")
            messagebox.showinfo(
                "테스트 주문 생성 완료",
                f"{order_number}\n\n이 주문으로 발주계획 생성 → 발주서 출력 → 발주확정 → 송장등록 흐름을 시험하세요.",
                parent=self,
            )
        except Exception as error:
            messagebox.showerror("테스트 주문 생성 실패", str(error), parent=self)

    def delete_test_orders(self) -> None:
        count = self.service.count_test_orders()
        if count == 0:
            messagebox.showinfo("TEST 주문 정리", "삭제할 TEST 주문이 없습니다.", parent=self)
            return
        if not messagebox.askyesno(
            "TEST 주문 삭제",
            f"TEST-로 시작하는 주문 {count:,}건과 관련 발주·송장 데이터를 삭제합니다.\n실제 주문은 삭제되지 않습니다.\n\n계속할까요?",
            parent=self,
        ):
            return
        try:
            deleted = self.service.delete_test_orders()
            self.refresh_data()
            self.status_callback(f"TEST 주문 {deleted:,}건 삭제 완료")
            messagebox.showinfo("정리 완료", f"TEST 주문 {deleted:,}건을 삭제했습니다.", parent=self)
        except Exception as error:
            messagebox.showerror("TEST 주문 삭제 실패", str(error), parent=self)

    def open_selected(self) -> None:
        selected=self.tree.selection()
        if not selected: return
        row=self.rows.get(selected[0])
        if row: self.navigate_callback(row["target"])
