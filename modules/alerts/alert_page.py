from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .alert_service import AlertService


class AlertPage(ttk.Frame):
    def __init__(self, parent, *, status_callback: Callable[[str], None] | None = None,
                 navigate_callback: Callable[[str], None] | None = None) -> None:
        super().__init__(parent, padding=18)
        self.service=AlertService()
        self.status_callback=status_callback or (lambda _m: None)
        self.navigate_callback=navigate_callback or (lambda _m: None)
        self.category_var=tk.StringVar(value="전체")
        self.keyword_var=tk.StringVar()
        self.days_var=tk.IntVar(value=3)
        self.summary_vars={k:tk.StringVar(value="0") for k in ("전체","긴급","높음","보통")}
        self._build()

    def _build(self):
        top=ttk.Frame(self); top.pack(fill="x")
        ttk.Label(top,text="업무 알림센터",font=("맑은 고딕",20,"bold")).pack(side="left")
        ttk.Button(top,text="새로고침",command=self.refresh_data).pack(side="right")

        cards=ttk.Frame(self); cards.pack(fill="x",pady=(15,10))
        for i,name in enumerate(("전체","긴급","높음","보통")):
            box=ttk.LabelFrame(cards,text=name,padding=10); box.grid(row=0,column=i,sticky="ew",padx=4)
            cards.columnconfigure(i,weight=1)
            ttk.Label(box,textvariable=self.summary_vars[name],font=("맑은 고딕",18,"bold")).pack()

        filters=ttk.Frame(self); filters.pack(fill="x",pady=(0,10))
        ttk.Label(filters,text="구분").pack(side="left")
        ttk.Combobox(filters,textvariable=self.category_var,values=("전체","입금","매핑","발주","송장","배송","클레임"),state="readonly",width=9).pack(side="left",padx=(6,12))
        ttk.Label(filters,text="장기배송 기준").pack(side="left")
        ttk.Spinbox(filters,from_=1,to=30,textvariable=self.days_var,width=5).pack(side="left",padx=(6,3))
        ttk.Label(filters,text="일").pack(side="left",padx=(0,12))
        ttk.Label(filters,text="검색").pack(side="left")
        entry=ttk.Entry(filters,textvariable=self.keyword_var,width=28); entry.pack(side="left",padx=6)
        entry.bind("<Return>",lambda _e:self.refresh_data())
        ttk.Button(filters,text="조회",command=self.refresh_data).pack(side="left")
        ttk.Button(filters,text="선택 업무 열기",command=self.open_selected).pack(side="right")

        cols=("priority","category","order","customer","title","detail","date")
        self.tree=ttk.Treeview(self,columns=cols,show="headings",height=25)
        headers={"priority":"우선순위","category":"구분","order":"주문번호","customer":"수취인","title":"알림내용","detail":"상세","date":"기준일시"}
        widths={"priority":75,"category":70,"order":150,"customer":90,"title":140,"detail":310,"date":130}
        for c in cols:
            self.tree.heading(c,text=headers[c]); self.tree.column(c,width=widths[c],anchor="center" if c not in ("detail","title") else "w")
        y=ttk.Scrollbar(self,orient="vertical",command=self.tree.yview); self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side="left",fill="both",expand=True); y.pack(side="right",fill="y")
        self.tree.bind("<Double-1>",lambda _e:self.open_selected())
        self.rows={}

    def refresh_data(self):
        try: days=max(int(self.days_var.get()),1)
        except Exception: days=3; self.days_var.set(3)
        rows=self.service.get_alerts(category=self.category_var.get(),keyword=self.keyword_var.get(),overdue_days=days)
        for item in self.tree.get_children(): self.tree.delete(item)
        self.rows={}
        for idx,row in enumerate(rows):
            iid=str(idx); self.rows[iid]=row
            self.tree.insert("", "end", iid=iid, values=(row["priority"],row["category"],row["order_number"],row["customer"],row["title"],row["detail"],row["date"]))
        summary=self.service.get_summary(days)
        for k,var in self.summary_vars.items(): var.set(f"{summary.get(k,0):,}")
        self.status_callback(f"업무 알림 {len(rows):,}건 조회")

    def open_selected(self):
        selected=self.tree.selection()
        if not selected: return
        row=self.rows.get(selected[0])
        if row: self.navigate_callback(row["target"])
