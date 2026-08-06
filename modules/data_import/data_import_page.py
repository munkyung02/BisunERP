from __future__ import annotations
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from .data_import_service import DataImportService

class DataImportPage(ttk.Frame):
    def __init__(self,parent,service=None):
        super().__init__(parent,padding=20); self.service=service or DataImportService(); self.file_var=tk.StringVar(); self.status_var=tk.StringVar(value="양식을 내려받아 상품과 공급처를 입력하세요."); self._build()
    def _build(self):
        ttk.Label(self,text="실무 데이터 일괄등록",font=("맑은 고딕",20,"bold")).pack(anchor="w")
        ttk.Label(self,text="공급처와 상품을 한 엑셀 파일에서 검사한 뒤 정상 행만 등록합니다.").pack(anchor="w",pady=(4,16))
        bar=ttk.Frame(self); bar.pack(fill="x")
        ttk.Button(bar,text="엑셀 양식 내려받기",command=self.download_template).pack(side="left")
        ttk.Entry(bar,textvariable=self.file_var).pack(side="left",fill="x",expand=True,padx=8)
        ttk.Button(bar,text="파일 선택",command=self.choose_file).pack(side="left")
        ttk.Button(bar,text="검사",command=self.validate).pack(side="left",padx=(8,0))
        ttk.Button(bar,text="정상 행 등록",command=self.import_data).pack(side="left",padx=(8,0))
        self.tree=ttk.Treeview(self,columns=("sheet","row","message"),show="headings",height=20)
        for c,t,w in (("sheet","시트",100),("row","행",70),("message","검사 결과",800)):
            self.tree.heading(c,text=t); self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True,pady=14)
        ttk.Label(self,textvariable=self.status_var).pack(anchor="w")
    def download_template(self):
        path=filedialog.asksaveasfilename(defaultextension=".xlsx",initialfile="비선상회_상품_공급처_등록양식.xlsx",filetypes=[("Excel","*.xlsx")])
        if path:
            self.service.create_template(path); self.status_var.set(f"양식 저장 완료: {path}"); messagebox.showinfo("완료","엑셀 양식을 저장했습니다.")
    def choose_file(self):
        path=filedialog.askopenfilename(filetypes=[("Excel","*.xlsx")])
        if path:self.file_var.set(path);self.validate()
    def _show(self,result):
        for i in self.tree.get_children():self.tree.delete(i)
        if result["errors"]:
            for e in result["errors"]:self.tree.insert("","end",values=(e["sheet"],e["row"],e["message"]))
        else:self.tree.insert("","end",values=("전체","-","오류 없음 · 등록 가능합니다."))
        self.status_var.set(f"공급처 {len(result['suppliers'])}행 · 상품 {len(result['products'])}행 · 오류 {len(result['errors'])}건")
    def validate(self):
        try:self._show(self.service.validate_file(self.file_var.get()))
        except Exception as e:messagebox.showerror("검사 오류",str(e))
    def import_data(self):
        try:
            r=self.service.import_file(self.file_var.get()); messagebox.showinfo("등록 완료",f"공급처 신규 {r['created_suppliers']} / 수정 {r['updated_suppliers']}\n상품 신규 {r['created_products']} / 수정 {r['updated_products']}\n오류 제외 {len(r['errors'])}건"); self.validate()
        except Exception as e:messagebox.showerror("등록 오류",str(e))
