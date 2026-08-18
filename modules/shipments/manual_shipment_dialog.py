from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from modules.shipments.shipment_service import ShipmentService


class ManualShipmentDialog(tk.Toplevel):
    """선택 공급처의 발주완료 주문상품에 송장을 직접 입력합니다."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        service: ShipmentService,
        supplier_name: str,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.supplier_name = supplier_name
        self.on_saved = on_saved
        self.rows: list[dict[str, Any]] = []
        self.carrier_vars: dict[int, tk.StringVar] = {}
        self.tracking_vars: dict[int, tk.StringVar] = {}
        self.all_carrier_var = tk.StringVar()

        self.title(f"송장 직접입력 - {supplier_name}")
        self.geometry("1500x650")
        self.minsize(1100, 420)
        self.transient(parent.winfo_toplevel())
        self._build_ui()
        self._load_rows()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(
            top,
            text=f"공급처: {self.supplier_name}",
            font=("맑은 고딕", 11, "bold"),
        ).pack(side="left")
        ttk.Label(top, text="전체 택배사").pack(side="left", padx=(24, 6))
        ttk.Combobox(
            top,
            textvariable=self.all_carrier_var,
            values=self.service.get_standard_carriers(),
            state="readonly",
            width=15,
        ).pack(side="left")
        ttk.Button(top, text="전체 적용", command=self._apply_all_carrier).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(top, text="목록 새로고침", command=self._load_rows).pack(
            side="right"
        )

        container = ttk.Frame(self, padding=(12, 0, 12, 0))
        container.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            container, orient="vertical", command=self.canvas.yview
        )
        self.grid_frame = ttk.Frame(self.canvas)
        self.grid_window = self.canvas.create_window(
            (0, 0), window=self.grid_frame, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.grid_frame.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(
                self.grid_window, width=event.width
            ),
        )

        bottom = ttk.Frame(self, padding=12)
        bottom.pack(fill="x")
        self.count_label = ttk.Label(bottom, text="대상 0건")
        self.count_label.pack(side="left")
        ttk.Button(bottom, text="닫기", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="입력 송장 저장", command=self._save).pack(
            side="right", padx=(0, 8)
        )

    def _load_rows(self) -> None:
        self.rows = self.service.get_manual_shipment_candidates(
            self.supplier_name
        )
        self.carrier_vars.clear()
        self.tracking_vars.clear()
        for child in self.grid_frame.winfo_children():
            child.destroy()

        headers = (
            "주문번호", "채널", "수취인", "전화번호", "상품명", "옵션",
            "수량", "발주차수", "주문일", "주소", "택배사", "송장번호",
        )
        for column, text in enumerate(headers):
            ttk.Label(
                self.grid_frame,
                text=text,
                font=("맑은 고딕", 9, "bold"),
                anchor="center",
                padding=5,
                relief="ridge",
            ).grid(row=0, column=column, sticky="nsew")

        carriers = self.service.get_standard_carriers()
        for row_number, row in enumerate(self.rows, start=1):
            purchase_order_id = int(row["purchase_order_id"])
            values = (
                row.get("order_number"), row.get("platform"),
                row.get("receiver_name"), row.get("receiver_phone"),
                row.get("product_name"), row.get("option_name"),
                row.get("quantity"), row.get("purchase_round"),
                row.get("ordered_at"), row.get("address"),
            )
            for column, value in enumerate(values):
                ttk.Label(
                    self.grid_frame,
                    text=str(value or ""),
                    padding=4,
                    relief="ridge",
                    anchor="w",
                ).grid(row=row_number, column=column, sticky="nsew")

            carrier_var = tk.StringVar(value=str(row.get("purchase_carrier") or ""))
            tracking_var = tk.StringVar()
            self.carrier_vars[purchase_order_id] = carrier_var
            self.tracking_vars[purchase_order_id] = tracking_var
            ttk.Combobox(
                self.grid_frame,
                textvariable=carrier_var,
                values=carriers,
                state="readonly",
                width=14,
            ).grid(row=row_number, column=10, sticky="nsew", padx=2, pady=2)
            ttk.Entry(
                self.grid_frame,
                textvariable=tracking_var,
                width=20,
            ).grid(row=row_number, column=11, sticky="nsew", padx=2, pady=2)

        self.grid_frame.columnconfigure(4, weight=2)
        self.grid_frame.columnconfigure(9, weight=2)
        self.count_label.configure(text=f"대상 {len(self.rows):,}건")

    def _apply_all_carrier(self) -> None:
        carrier = self.all_carrier_var.get().strip()
        if not carrier:
            return
        for variable in self.carrier_vars.values():
            variable.set(carrier)

    def _save(self) -> None:
        entered: list[dict[str, Any]] = []
        for row in self.rows:
            purchase_order_id = int(row["purchase_order_id"])
            tracking = self.tracking_vars[purchase_order_id].get().strip()
            if tracking:
                entered.append(
                    {
                        "purchase_order_id": purchase_order_id,
                        "carrier": self.carrier_vars[purchase_order_id].get(),
                        "tracking_number": tracking,
                    }
                )
        if not entered:
            messagebox.showwarning(
                "저장 대상 없음", "송장번호가 입력된 행이 없습니다.", parent=self
            )
            return
        missing_count = len(self.rows) - len(entered)
        if not messagebox.askyesno(
            "송장 직접입력 확인",
            f"송장 {len(entered):,}건을 등록합니다.\n\n"
            f"공급처: {self.supplier_name}\n"
            f"등록 대상: {len(entered):,}건\n미입력: {missing_count:,}건",
            parent=self,
        ):
            return
        try:
            result = self.service.save_manual_shipments(entered)
        except Exception as error:
            messagebox.showerror(
                "송장 직접입력 오류", str(error), parent=self
            )
            return
        messagebox.showinfo(
            "송장 직접입력 완료",
            f"저장 완료: {result.get('saved_count', 0):,}건\n"
            f"건너뜀: {result.get('skipped_count', 0):,}건\n"
            f"오류: {result.get('error_count', 0):,}건",
            parent=self,
        )
        if self.on_saved is not None:
            self.on_saved()
        self._load_rows()
