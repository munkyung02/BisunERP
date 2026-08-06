from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from openpyxl import Workbook

from modules.shipments.shipment_service import ShipmentService


class SimpleShipmentImportDialog(tk.Toplevel):
    """기본 송장양식과 공급처 회신 발주서를 지원하는 일괄등록 창."""

    def __init__(self, parent: tk.Misc, refresh_callback=None) -> None:
        super().__init__(parent)
        self.title("간편 송장 일괄등록")
        self.geometry("1050x650")
        self.minsize(900, 560)
        self.transient(parent.winfo_toplevel())
        self.service = ShipmentService()
        self.refresh_callback = refresh_callback
        self.file_path: Path | None = None
        self.preview: dict[str, Any] | None = None
        self.file_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="기본양식 또는 공급처가 송장을 입력해 회신한 발주서를 선택하세요."
        )
        self._build_ui()

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=16)
        header.pack(fill="x")
        ttk.Label(
            header,
            text="간편 송장 일괄등록",
            font=("맑은 고딕", 17, "bold"),
        ).pack(side="left")
        ttk.Button(
            header,
            text="기본양식 저장",
            command=self.save_template,
        ).pack(side="right")

        box = ttk.LabelFrame(self, text="엑셀 파일", padding=12)
        box.pack(fill="x", padx=16, pady=(0, 10))
        box.columnconfigure(1, weight=1)
        ttk.Button(
            box,
            text="파일 선택",
            command=self.select_file,
        ).grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(
            box,
            textvariable=self.file_var,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew")
        ttk.Button(
            box,
            text="미리보기",
            command=self.preview_file,
        ).grid(row=0, column=2, padx=(8, 0))
        self.save_button = ttk.Button(
            box,
            text="정상건 일괄등록",
            command=self.save_rows,
            state="disabled",
        )
        self.save_button.grid(row=0, column=3, padx=(8, 0))

        columns = (
            "row", "status", "order_number", "carrier",
            "tracking", "items", "message",
        )
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        labels = {
            "row": "행", "status": "상태",
            "order_number": "주문번호 / 수취인",
            "carrier": "택배사", "tracking": "송장번호",
            "items": "적용상품", "message": "확인사항",
        }
        widths = {
            "row": 50, "status": 80, "order_number": 190,
            "carrier": 110, "tracking": 180,
            "items": 80, "message": 300,
        }
        for col in columns:
            self.tree.heading(col, text=labels[col])
            self.tree.column(
                col,
                width=widths[col],
                anchor="center" if col in {"row", "status", "items"} else "w",
            )
        self.tree.pack(fill="both", expand=True, padx=16)
        ttk.Label(
            self,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
            padding=(12, 7),
        ).pack(fill="x", padx=16, pady=12)

    def save_template(self) -> None:
        target = filedialog.asksaveasfilename(
            title="송장 일괄등록 양식 저장",
            defaultextension=".xlsx",
            initialfile="비선상회_송장일괄등록양식.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not target:
            return

        wb = Workbook()
        ws = wb.active
        ws.title = "송장등록"
        ws.append(["주문번호", "택배사", "송장번호"])
        ws.append(["예시-주문번호", "CJ대한통운", "123456789012"])
        ws.column_dimensions["A"].width = 24
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 24
        wb.save(target)
        messagebox.showinfo(
            "저장 완료",
            f"양식을 저장했습니다.\n\n{target}",
            parent=self,
        )

    def select_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="송장 엑셀 선택",
            filetypes=[("Excel", "*.xlsx *.xlsm")],
        )
        if not selected:
            return

        self.file_path = Path(selected)
        self.file_var.set(selected)
        self.preview = None
        self.save_button.configure(state="disabled")
        self.status_var.set("파일을 선택했습니다. 미리보기를 눌러주세요.")

    def preview_file(self) -> None:
        if self.file_path is None:
            messagebox.showwarning(
                "파일 선택",
                "먼저 엑셀파일을 선택하세요.",
                parent=self,
            )
            return

        try:
            self.preview = self.service.preview_simple_shipment_file(
                self.file_path
            )
        except Exception as exc:
            messagebox.showerror("분석 오류", str(exc), parent=self)
            return

        for iid in self.tree.get_children():
            self.tree.delete(iid)

        for row in self.preview["rows"]:
            self.tree.insert(
                "",
                "end",
                values=(
                    row["excel_row"],
                    row["status_text"],
                    row.get("order_number", ""),
                    row["carrier"],
                    row["tracking_number"],
                    row.get("item_count", 0),
                    row.get("message", ""),
                ),
            )

        self.save_button.configure(
            state="normal" if self.preview["valid_count"] else "disabled"
        )
        source_text = self.preview.get("source_type", "송장양식")
        self.status_var.set(
            f"{source_text} · 전체 {self.preview['total_count']}건 · "
            f"등록가능 {self.preview['valid_count']}건 · "
            f"오류/중복 {self.preview['error_count']}건"
        )

    def save_rows(self) -> None:
        if not self.preview or not self.preview["valid_count"]:
            return

        if not messagebox.askyesno(
            "등록 확인",
            f"정상 송장 {self.preview['valid_count']}건을 등록하시겠습니까?",
            parent=self,
        ):
            return

        try:
            result = self.service.save_simple_shipments(
                self.preview["rows"]
            )
        except Exception as exc:
            messagebox.showerror("등록 오류", str(exc), parent=self)
            return

        messagebox.showinfo(
            "등록 완료",
            (
                f"전체 행: {result['total_count']}건\n"
                f"등록 성공: {result['success_count']}건\n"
                f"건너뜀: {result['skipped_count']}건\n"
                f"오류: {result['error_count']}건\n"
                f"쿠팡 전송 성공: "
                f"{result.get('coupang_success_count', 0)}건\n"
                f"쿠팡 전송 실패: "
                f"{result.get('coupang_failed_count', 0)}건"
                + (
                    "\n" + "\n".join(
                        result.get("coupang_skipped_messages", [])
                    )
                    if result.get("coupang_skipped_messages")
                    else ""
                )
                + (
                    "\n\n오류 내역:\n"
                    + "\n".join(result["errors"][:10])
                    if result["errors"]
                    else ""
                )
            ),
            parent=self,
        )
        self.save_button.configure(state="disabled")
        if self.refresh_callback:
            self.refresh_callback()
