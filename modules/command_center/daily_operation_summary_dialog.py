from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any


class DailyOperationSummaryDialog(tk.Toplevel):
    """Shows the completed one-click workflow without opening outputs automatically."""

    def __init__(self, parent: tk.Misc, result: dict[str, Any]) -> None:
        super().__init__(parent)
        self.title("오늘 업무 결과")
        self.geometry("920x570")
        self.minsize(760, 460)
        self.transient(parent.winfo_toplevel())
        self.result = result
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(18, 16, 18, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text="오늘 업무 실행 결과",
            font=("맑은 고딕", 17, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=(
                f"PASS {int(self.result.get('pass_count', 0) or 0):,} · "
                f"WARNING {int(self.result.get('warning_count', 0) or 0):,} · "
                f"FAILED {int(self.result.get('failed_count', 0) or 0):,} · "
                f"총 {float(self.result.get('elapsed_seconds', 0) or 0):.2f}초"
            ),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        table_frame = ttk.Frame(self, padding=(18, 0, 18, 8))
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(
            table_frame,
            columns=("status", "step", "result", "elapsed"),
            show="headings",
            height=13,
        )
        for column, title, width, anchor in (
            ("status", "상태", 85, "center"),
            ("step", "단계", 220, "w"),
            ("result", "결과", 470, "w"),
            ("elapsed", "소요시간", 85, "e"),
        ):
            tree.heading(column, text=title)
            tree.column(column, width=width, anchor=anchor)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for step in self.result.get("steps", []):
            tree.insert(
                "",
                "end",
                values=(
                    step.get("status", ""),
                    f"{step.get('step', '')}. {step.get('name', '')}",
                    step.get("message", ""),
                    f"{float(step.get('elapsed_seconds', 0) or 0):.2f}초",
                ),
            )

        footer = ttk.Frame(self, padding=(18, 4, 18, 16))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Label(footer, text="생성 결과").pack(side="left", padx=(0, 10))
        seen_paths: set[str] = set()
        for output in self.result.get("output_paths", []):
            path = str(output.get("path") or "").strip()
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            ttk.Button(
                footer,
                text=str(output.get("label") or "폴더 열기"),
                command=lambda value=path: self._open_folder(value),
            ).pack(side="left", padx=(0, 8))
        ttk.Button(footer, text="닫기", command=self.destroy).pack(side="right")

    def _open_folder(self, folder: str) -> None:
        path = Path(folder)
        if not path.exists() or not path.is_dir():
            messagebox.showwarning(
                "폴더 열기",
                f"폴더를 찾을 수 없습니다.\n\n{path}",
                parent=self,
            )
            return
        try:
            os.startfile(path)
        except OSError as error:
            messagebox.showerror(
                "폴더 열기 오류",
                f"폴더를 열지 못했습니다.\n\n{error}",
                parent=self,
            )
