from __future__ import annotations

import os
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .export_service import ExportService


class ExportPage(ttk.Frame):
    ITEMS = ("주문", "입금", "배송", "클레임", "거래처", "상품", "공급처")

    def __init__(self, parent, status_callback=None, service=None):
        super().__init__(parent, padding=22)
        self.status_callback = status_callback or (lambda _text: None)
        self.service = service or ExportService()
        today = date.today()
        self.start_var = tk.StringVar(value=(today - timedelta(days=30)).isoformat())
        self.end_var = tk.StringVar(value=today.isoformat())
        self.output_var = tk.StringVar(value=str(Path.cwd() / "output" / "exports"))
        self.backup_var = tk.BooleanVar(value=True)
        self.item_vars = {name: tk.BooleanVar(value=True) for name in self.ITEMS}
        self.summary_var = tk.StringVar(value="조회 버튼을 눌러 내보낼 데이터 건수를 확인하세요.")
        self._build()

    def _build(self):
        ttk.Label(self, text="데이터 내보내기·운영 백업센터", font=("맑은 고딕", 20, "bold")).pack(anchor="w")
        ttk.Label(self, text="주문·입금·배송 등 운영 데이터를 한 개의 엑셀 파일로 저장합니다.").pack(anchor="w", pady=(4, 18))

        condition = ttk.LabelFrame(self, text="내보내기 조건", padding=14)
        condition.pack(fill="x")
        ttk.Label(condition, text="기간").grid(row=0, column=0, sticky="w")
        ttk.Entry(condition, textvariable=self.start_var, width=14).grid(row=0, column=1, padx=(8, 4))
        ttk.Label(condition, text="~").grid(row=0, column=2)
        ttk.Entry(condition, textvariable=self.end_var, width=14).grid(row=0, column=3, padx=(4, 14))
        ttk.Button(condition, text="최근 30일", command=self._last_30).grid(row=0, column=4, padx=3)
        ttk.Button(condition, text="전체 선택", command=lambda: self._select_all(True)).grid(row=0, column=5, padx=3)
        ttk.Button(condition, text="전체 해제", command=lambda: self._select_all(False)).grid(row=0, column=6, padx=3)

        items = ttk.Frame(condition)
        items.grid(row=1, column=0, columnspan=7, sticky="w", pady=(14, 4))
        for index, name in enumerate(self.ITEMS):
            ttk.Checkbutton(items, text=name, variable=self.item_vars[name]).grid(row=0, column=index, padx=(0, 16))

        path_box = ttk.LabelFrame(self, text="저장 위치", padding=14)
        path_box.pack(fill="x", pady=14)
        ttk.Entry(path_box, textvariable=self.output_var).pack(side="left", fill="x", expand=True)
        ttk.Button(path_box, text="폴더 선택", command=self._choose_folder).pack(side="left", padx=6)
        ttk.Button(path_box, text="폴더 열기", command=self._open_folder).pack(side="left")
        ttk.Checkbutton(path_box, text="내보내기 전 DB 백업", variable=self.backup_var).pack(side="left", padx=(18, 0))

        summary = ttk.LabelFrame(self, text="예상 데이터", padding=16)
        summary.pack(fill="both", expand=True)
        ttk.Label(summary, textvariable=self.summary_var, justify="left", font=("맑은 고딕", 12)).pack(anchor="nw")

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="건수 조회", command=self.refresh_data).pack(side="left")
        ttk.Button(actions, text="엑셀 내보내기", command=self._export, style="Action.TButton").pack(side="right")

    def _last_30(self):
        today = date.today()
        self.start_var.set((today - timedelta(days=30)).isoformat())
        self.end_var.set(today.isoformat())
        self.refresh_data()

    def _select_all(self, value):
        for variable in self.item_vars.values():
            variable.set(value)

    def _choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.cwd()))
        if folder:
            self.output_var.set(folder)

    def _open_folder(self):
        path = Path(self.output_var.get())
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])

    def refresh_data(self):
        try:
            counts = self.service.get_counts(self.start_var.get(), self.end_var.get())
            self.summary_var.set("\n".join(f"{name}: {count:,}건" for name, count in counts.items()))
            self.status_callback("내보내기 대상 건수 조회 완료")
        except Exception as error:
            messagebox.showerror("조회 오류", str(error), parent=self)

    def _export(self):
        try:
            selected = [name for name, variable in self.item_vars.items() if variable.get()]
            excel, backup, counts = self.service.export_excel(self.output_var.get(), self.start_var.get(), self.end_var.get(), selected, create_backup=self.backup_var.get())
            lines = [f"엑셀 파일: {excel}", "", *[f"{name}: {count:,}건" for name, count in counts.items()]]
            if backup:
                lines.extend(["", f"DB 백업: {backup}"])
            self.status_callback("데이터 내보내기 완료")
            messagebox.showinfo("내보내기 완료", "\n".join(lines), parent=self)
        except Exception as error:
            messagebox.showerror("내보내기 오류", str(error), parent=self)
