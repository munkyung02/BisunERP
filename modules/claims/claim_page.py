from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk
from typing import Callable

from .claim_service import ClaimService


class ClaimPage(ttk.Frame):
    """취소·반품·교환·환불 클레임 통합 관리 화면."""

    def __init__(self, parent: tk.Misc, *, service: ClaimService | None = None,
                 status_callback: Callable[[str], None] | None = None,
                 refresh_callback: Callable[[], None] | None = None) -> None:
        super().__init__(parent, padding=22)
        self.service = service or ClaimService()
        self.status_callback = status_callback
        self.refresh_callback = refresh_callback
        self.keyword_var = tk.StringVar()
        self.status_var = tk.StringVar(value="전체")
        self.type_var = tk.StringVar(value="전체")
        self.from_var = tk.StringVar(value=(datetime.now()-timedelta(days=30)).strftime("%Y-%m-%d"))
        self.to_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.summary_vars = {k: tk.StringVar(value="0") for k in ("total","received","processing","hold","completed","pending_refund")}
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1); self.rowconfigure(3, weight=1)
        header = ttk.Frame(self); header.grid(row=0, column=0, sticky="ew", pady=(0,12)); header.columnconfigure(0, weight=1)
        ttk.Label(header, text="클레임관리", font=("맑은 고딕",22,"bold")).grid(row=0,column=0,sticky="w")
        ttk.Label(header, text="취소·반품·교환·환불 요청을 주문과 연결해 처리합니다.").grid(row=1,column=0,sticky="w",pady=(4,0))
        ttk.Button(header,text="클레임 등록",command=self._open_editor).grid(row=0,column=1,rowspan=2,padx=(8,0))

        cards=ttk.Frame(self); cards.grid(row=1,column=0,sticky="ew",pady=(0,12))
        labels=(("전체","total"),("신규 접수","received"),("처리중","processing"),("보류","hold"),("완료","completed"),("환불 예정액","pending_refund"))
        for i,(title,key) in enumerate(labels):
            cards.columnconfigure(i,weight=1); box=ttk.LabelFrame(cards,text=title,padding=9); box.grid(row=0,column=i,sticky="ew",padx=3)
            ttk.Label(box,textvariable=self.summary_vars[key],font=("맑은 고딕",15,"bold")).pack()

        filters=ttk.LabelFrame(self,text="조회 조건",padding=10); filters.grid(row=2,column=0,sticky="ew",pady=(0,10))
        ttk.Label(filters,text="검색").grid(row=0,column=0,padx=(0,4)); ent=ttk.Entry(filters,textvariable=self.keyword_var,width=25); ent.grid(row=0,column=1); ent.bind("<Return>",lambda _e:self.refresh_data())
        ttk.Label(filters,text="상태").grid(row=0,column=2,padx=(12,4)); ttk.Combobox(filters,textvariable=self.status_var,values=("전체",*self.service.CLAIM_STATUSES),state="readonly",width=9).grid(row=0,column=3)
        ttk.Label(filters,text="유형").grid(row=0,column=4,padx=(12,4)); ttk.Combobox(filters,textvariable=self.type_var,values=("전체",*self.service.CLAIM_TYPES),state="readonly",width=10).grid(row=0,column=5)
        ttk.Label(filters,text="접수일").grid(row=0,column=6,padx=(12,4)); ttk.Entry(filters,textvariable=self.from_var,width=11).grid(row=0,column=7); ttk.Label(filters,text="~").grid(row=0,column=8); ttk.Entry(filters,textvariable=self.to_var,width=11).grid(row=0,column=9)
        ttk.Button(filters,text="조회",command=self.refresh_data).grid(row=0,column=10,padx=(10,0)); ttk.Button(filters,text="전체기간",command=self._all_dates).grid(row=0,column=11,padx=(4,0))

        table_frame=ttk.Frame(self); table_frame.grid(row=3,column=0,sticky="nsew"); table_frame.columnconfigure(0,weight=1); table_frame.rowconfigure(0,weight=1)
        cols=("id","status","type","order","receiver","phone","amount","refund","refund_status","requested","manager","reason")
        self.tree=ttk.Treeview(table_frame,columns=cols,show="headings",selectmode="extended")
        headings=("번호","상태","유형","주문번호","수취인","연락처","주문금액","환불금액","환불상태","접수일","담당자","사유")
        widths=(55,70,80,145,80,110,95,95,85,130,75,250)
        for c,h,w in zip(cols,headings,widths): self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor="center" if c!="reason" else "w")
        self.tree.grid(row=0,column=0,sticky="nsew"); self.tree.bind("<Double-1>",lambda _e:self._edit_selected())
        sy=ttk.Scrollbar(table_frame,orient="vertical",command=self.tree.yview); sy.grid(row=0,column=1,sticky="ns"); self.tree.configure(yscrollcommand=sy.set)
        sx=ttk.Scrollbar(table_frame,orient="horizontal",command=self.tree.xview); sx.grid(row=1,column=0,sticky="ew"); self.tree.configure(xscrollcommand=sx.set)

        actions=ttk.Frame(self); actions.grid(row=4,column=0,sticky="ew",pady=(10,0))
        ttk.Button(actions,text="수정",command=self._edit_selected).pack(side="left")
        ttk.Button(actions,text="처리중",command=lambda:self._mark("처리중")).pack(side="left",padx=4)
        ttk.Button(actions,text="완료",command=lambda:self._mark("완료")).pack(side="left")
        ttk.Button(actions,text="보류",command=lambda:self._mark("보류")).pack(side="left",padx=4)
        ttk.Button(actions,text="삭제",command=self._delete_selected).pack(side="left")
        ttk.Button(actions,text="새로고침",command=self.refresh_data).pack(side="right")

    def refresh_data(self) -> None:
        try:
            rows=self.service.list_claims(self.keyword_var.get(),self.status_var.get(),self.type_var.get(),self.from_var.get(),self.to_var.get())
            self.tree.delete(*self.tree.get_children())
            for r in rows:
                self.tree.insert("","end",iid=str(r["id"]),values=(r["id"],r["claim_status"],r["claim_type"],r["order_number"],r["receiver_name"] or "",r["receiver_phone"] or "",f'{int(r["total_amount"] or 0):,}',f'{int(r["refund_amount"] or 0):,}',r["refund_status"],r["requested_at"] or "",r["manager_name"] or "",r["reason"] or ""))
            summary=self.service.get_summary()
            for key,var in self.summary_vars.items(): var.set(f'{summary[key]:,}' + ("원" if key=="pending_refund" else "건"))
            self._set_status(f"클레임 {len(rows):,}건 조회")
        except Exception as e: messagebox.showerror("조회 오류",str(e),parent=self.winfo_toplevel())

    def _all_dates(self) -> None: self.from_var.set(""); self.to_var.set(""); self.refresh_data()
    def _selected_ids(self) -> list[int]: return [int(x) for x in self.tree.selection()]
    def _edit_selected(self) -> None:
        ids=self._selected_ids()
        if not ids: messagebox.showinfo("선택 필요","수정할 클레임을 선택하세요.",parent=self.winfo_toplevel()); return
        self._open_editor(ids[0])
    def _mark(self,status:str) -> None:
        ids=self._selected_ids()
        if not ids: return
        self.service.mark_status(ids,status); self.refresh_data(); self._after_change()
    def _delete_selected(self) -> None:
        ids=self._selected_ids()
        if not ids:return
        if not messagebox.askyesno("삭제 확인",f"선택한 {len(ids)}건을 삭제하시겠습니까?",parent=self.winfo_toplevel()):return
        for cid in ids:self.service.delete_claim(cid)
        self.refresh_data(); self._after_change()
    def _after_change(self) -> None:
        if self.refresh_callback:self.refresh_callback()
    def _set_status(self,text:str) -> None:
        if self.status_callback:self.status_callback(text)

    def _open_editor(self, claim_id: int | None = None) -> None:
        ClaimEditor(self.winfo_toplevel(),self.service,claim_id,on_saved=lambda:(self.refresh_data(),self._after_change()))


class ClaimEditor(tk.Toplevel):
    def __init__(self,parent:tk.Misc,service:ClaimService,claim_id:int|None,on_saved:Callable[[],None]) -> None:
        super().__init__(parent); self.service=service; self.claim_id=claim_id; self.on_saved=on_saved
        self.title("클레임 수정" if claim_id else "클레임 등록"); self.geometry("720x650"); self.resizable(False,False); self.transient(parent); self.grab_set()
        self.order_id_var=tk.StringVar(); self.order_text_var=tk.StringVar(value="주문을 검색해 선택하세요")
        self.type_var=tk.StringVar(value="주문취소"); self.status_var=tk.StringVar(value="접수"); self.refund_status_var=tk.StringVar(value="해당없음"); self.refund_amount_var=tk.StringVar(value="0")
        self.requested_var=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M:%S")); self.manager_var=tk.StringVar(); self.reason_var=tk.StringVar()
        self._build();
        if claim_id:self._load()

    def _build(self)->None:
        frm=ttk.Frame(self,padding=18); frm.pack(fill="both",expand=True); frm.columnconfigure(1,weight=1)
        ttk.Label(frm,text="주문",font=("맑은 고딕",10,"bold")).grid(row=0,column=0,sticky="w",pady=6); ttk.Label(frm,textvariable=self.order_text_var).grid(row=0,column=1,sticky="w"); ttk.Button(frm,text="주문 선택",command=self._choose_order).grid(row=0,column=2)
        fields=(("유형",self.type_var,self.service.CLAIM_TYPES),("처리상태",self.status_var,self.service.CLAIM_STATUSES),("환불상태",self.refund_status_var,self.service.REFUND_STATUSES))
        row=1
        for label,var,values in fields:
            ttk.Label(frm,text=label).grid(row=row,column=0,sticky="w",pady=6); ttk.Combobox(frm,textvariable=var,values=values,state="readonly").grid(row=row,column=1,columnspan=2,sticky="ew"); row+=1
        for label,var in (("환불금액",self.refund_amount_var),("접수일시",self.requested_var),("담당자",self.manager_var),("사유",self.reason_var)):
            ttk.Label(frm,text=label).grid(row=row,column=0,sticky="w",pady=6); ttk.Entry(frm,textvariable=var).grid(row=row,column=1,columnspan=2,sticky="ew"); row+=1
        ttk.Label(frm,text="처리메모").grid(row=row,column=0,sticky="nw",pady=6); self.memo=tk.Text(frm,height=12,wrap="word"); self.memo.grid(row=row,column=1,columnspan=2,sticky="nsew"); frm.rowconfigure(row,weight=1); row+=1
        buttons=ttk.Frame(frm); buttons.grid(row=row,column=0,columnspan=3,sticky="e",pady=(14,0)); ttk.Button(buttons,text="취소",command=self.destroy).pack(side="right"); ttk.Button(buttons,text="저장",command=self._save).pack(side="right",padx=(0,6))

    def _choose_order(self)->None:
        OrderChooser(self,self.service,lambda r:(self.order_id_var.set(str(r["id"])),self.order_text_var.set(f'{r["order_number"]} | {r["receiver_name"] or ""} | {int(r["total_amount"] or 0):,}원')))
    def _load(self)->None:
        r=self.service.get_claim(int(self.claim_id));
        if not r:return
        self.order_id_var.set(str(r["order_id"])); self.order_text_var.set(f'{r["order_number"]} | {r["receiver_name"] or ""} | {int(r["total_amount"] or 0):,}원')
        self.type_var.set(r["claim_type"]); self.status_var.set(r["claim_status"]); self.refund_status_var.set(r["refund_status"]); self.refund_amount_var.set(str(r["refund_amount"] or 0)); self.requested_var.set(r["requested_at"] or ""); self.manager_var.set(r["manager_name"] or ""); self.reason_var.set(r["reason"] or ""); self.memo.insert("1.0",r["memo"] or "")
    def _save(self)->None:
        if not self.order_id_var.get(): messagebox.showwarning("주문 필요","연결할 주문을 선택하세요.",parent=self); return
        try: amount=int(self.refund_amount_var.get().replace(",",""))
        except ValueError: messagebox.showwarning("입력 확인","환불금액은 숫자로 입력하세요.",parent=self); return
        self.service.save_claim({"order_id":int(self.order_id_var.get()),"claim_type":self.type_var.get(),"claim_status":self.status_var.get(),"refund_status":self.refund_status_var.get(),"refund_amount":amount,"requested_at":self.requested_var.get(),"manager_name":self.manager_var.get(),"reason":self.reason_var.get(),"memo":self.memo.get("1.0","end").strip()},self.claim_id)
        self.on_saved(); self.destroy()


class OrderChooser(tk.Toplevel):
    def __init__(self,parent:tk.Misc,service:ClaimService,on_select:Callable[[dict],None])->None:
        super().__init__(parent); self.service=service; self.on_select=on_select; self.title("주문 선택"); self.geometry("850x520"); self.transient(parent); self.grab_set(); self.keyword=tk.StringVar(); self.rows={}; self._build(); self._search()
    def _build(self)->None:
        top=ttk.Frame(self,padding=10); top.pack(fill="x"); ent=ttk.Entry(top,textvariable=self.keyword); ent.pack(side="left",fill="x",expand=True); ent.bind("<Return>",lambda _e:self._search()); ttk.Button(top,text="검색",command=self._search).pack(side="left",padx=(5,0))
        cols=("order","receiver","phone","amount","status","products"); self.tree=ttk.Treeview(self,columns=cols,show="headings");
        for c,h,w in zip(cols,("주문번호","수취인","연락처","금액","주문상태","상품"),(150,90,120,90,100,280)): self.tree.heading(c,text=h); self.tree.column(c,width=w)
        self.tree.pack(fill="both",expand=True,padx=10); self.tree.bind("<Double-1>",lambda _e:self._select())
        ttk.Button(self,text="선택",command=self._select).pack(pady=10)
    def _search(self)->None:
        self.tree.delete(*self.tree.get_children()); self.rows={r["id"]:r for r in self.service.search_orders(self.keyword.get())}
        for oid,r in self.rows.items(): self.tree.insert("","end",iid=str(oid),values=(r["order_number"],r["receiver_name"] or "",r["receiver_phone"] or "",f'{int(r["total_amount"] or 0):,}',r["order_status"],r["products"] or ""))
    def _select(self)->None:
        sel=self.tree.selection();
        if not sel:return
        self.on_select(self.rows[int(sel[0])]); self.destroy()
