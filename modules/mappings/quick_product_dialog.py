from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from modules.products.product_repository import ProductRepository
from modules.suppliers.supplier_repository import SupplierRepository


class QuickProductDialog(tk.Toplevel):
    """
    미매핑 주문상품을 ERP 상품으로 빠르게 등록하는 대화상자입니다.

    저장 성공 시 생성된 상품 ID가 result_product_id에 저장됩니다.
    MappingPage는 이 값을 사용해 주문상품을 즉시 연결하고
    자동매핑 규칙을 저장합니다.
    """

    PURCHASE_ROUNDS = (
        "",
        "1차",
        "2차",
        "3차",
        "상시",
    )

    def __init__(
        self,
        parent: tk.Misc,
        *,
        order_item: dict[str, Any] | None = None,
        product_repository: ProductRepository | None = None,
        supplier_repository: SupplierRepository | None = None,
    ) -> None:
        super().__init__(parent)

        self.order_item = order_item or {}
        self.product_repository = (
            product_repository or ProductRepository()
        )
        self.supplier_repository = (
            supplier_repository or SupplierRepository()
        )

        self.result_product_id: int | None = None
        self.suppliers: list[dict[str, Any]] = []
        self.supplier_name_to_id: dict[str, int] = {}

        self.platform_var = tk.StringVar(
            value=str(self.order_item.get("platform") or "")
        )
        self.platform_product_name_var = tk.StringVar(
            value=str(
                self.order_item.get(
                    "platform_product_name"
                ) or ""
            )
        )
        self.product_name_var = tk.StringVar(
            value=str(
                self.order_item.get(
                    "platform_product_name"
                ) or ""
            )
        )
        self.option_name_var = tk.StringVar(
            value=str(self.order_item.get("option_name") or "")
        )
        self.supplier_var = tk.StringVar()
        self.supplier_product_name_var = tk.StringVar(
            value=str(
                self.order_item.get(
                    "platform_product_name"
                ) or ""
            )
        )
        self.purchase_price_var = tk.StringVar(value="0")
        self.sale_price_var = tk.StringVar(
            value=str(
                int(self.order_item.get("unit_price") or 0)
            )
        )
        self.purchase_round_var = tk.StringVar(
            value=str(
                self.order_item.get("purchase_round") or ""
            )
        )
        self.active_var = tk.BooleanVar(value=True)

        self.title("새 상품 등록 및 연결")
        self.geometry("650x540")
        self.minsize(620, 500)
        self.transient(parent)
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self._build_ui()
        self._load_suppliers()
        self._center_on_parent(parent)

        self.product_name_entry.focus_set()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(
            self,
            padding=(20, 18, 20, 10),
        )
        header.grid(row=0, column=0, sticky="ew")

        ttk.Label(
            header,
            text="새 상품 등록 및 연결",
            font=("맑은 고딕", 16, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            header,
            text=(
                "주문상품 정보를 바탕으로 ERP 상품을 등록합니다. "
                "저장 후 현재 주문상품에 바로 연결됩니다."
            ),
        ).pack(anchor="w", pady=(5, 0))

        form = ttk.LabelFrame(
            self,
            text="상품 정보",
            padding=16,
        )
        form.grid(
            row=1,
            column=0,
            padx=20,
            pady=(0, 12),
            sticky="nsew",
        )
        form.columnconfigure(1, weight=1)

        row = 0

        self._add_entry(
            form,
            row,
            "판매 플랫폼",
            self.platform_var,
        )
        row += 1

        self._add_entry(
            form,
            row,
            "판매처 상품명",
            self.platform_product_name_var,
        )
        row += 1

        self.product_name_entry = self._add_entry(
            form,
            row,
            "ERP 상품명 *",
            self.product_name_var,
        )
        row += 1

        self._add_entry(
            form,
            row,
            "옵션",
            self.option_name_var,
        )
        row += 1

        ttk.Label(
            form,
            text="기본 공급처",
            width=16,
        ).grid(
            row=row,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="w",
        )

        self.supplier_combo = ttk.Combobox(
            form,
            textvariable=self.supplier_var,
            state="readonly",
        )
        self.supplier_combo.grid(
            row=row,
            column=1,
            pady=6,
            sticky="ew",
        )
        row += 1

        self._add_entry(
            form,
            row,
            "공급처 상품명",
            self.supplier_product_name_var,
        )
        row += 1

        price_frame = ttk.Frame(form)
        price_frame.grid(
            row=row,
            column=0,
            columnspan=2,
            pady=6,
            sticky="ew",
        )
        price_frame.columnconfigure(1, weight=1)
        price_frame.columnconfigure(3, weight=1)

        ttk.Label(
            price_frame,
            text="매입가",
            width=16,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")

        ttk.Entry(
            price_frame,
            textvariable=self.purchase_price_var,
        ).grid(row=0, column=1, sticky="ew")

        ttk.Label(
            price_frame,
            text="판매가",
            width=10,
        ).grid(
            row=0,
            column=2,
            padx=(16, 10),
            sticky="w",
        )

        ttk.Entry(
            price_frame,
            textvariable=self.sale_price_var,
        ).grid(row=0, column=3, sticky="ew")
        row += 1

        ttk.Label(
            form,
            text="발주 차수",
            width=16,
        ).grid(
            row=row,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="w",
        )

        ttk.Combobox(
            form,
            textvariable=self.purchase_round_var,
            values=self.PURCHASE_ROUNDS,
            state="readonly",
        ).grid(
            row=row,
            column=1,
            pady=6,
            sticky="ew",
        )
        row += 1

        ttk.Checkbutton(
            form,
            text="사용 상품으로 등록",
            variable=self.active_var,
        ).grid(
            row=row,
            column=1,
            pady=(8, 0),
            sticky="w",
        )

        buttons = ttk.Frame(
            self,
            padding=(20, 0, 20, 18),
        )
        buttons.grid(row=2, column=0, sticky="ew")
        buttons.columnconfigure(0, weight=1)

        ttk.Button(
            buttons,
            text="취소",
            command=self.cancel,
        ).grid(row=0, column=1)

        ttk.Button(
            buttons,
            text="상품 등록 및 연결",
            command=self.save,
        ).grid(row=0, column=2, padx=(8, 0))

        self.bind("<Escape>", lambda _event: self.cancel())
        self.bind("<Control-Return>", lambda _event: self.save())

    @staticmethod
    def _add_entry(
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> ttk.Entry:
        ttk.Label(
            parent,
            text=label,
            width=16,
        ).grid(
            row=row,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="w",
        )

        entry = ttk.Entry(
            parent,
            textvariable=variable,
        )
        entry.grid(
            row=row,
            column=1,
            pady=6,
            sticky="ew",
        )
        return entry

    def _load_suppliers(self) -> None:
        try:
            self.suppliers = (
                self.supplier_repository.get_suppliers(
                    active_only=True
                )
            )
        except Exception as error:
            messagebox.showerror(
                "공급처 조회 오류",
                (
                    "공급처 목록을 불러오지 못했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )
            self.suppliers = []

        values = ["공급처 미지정"]
        self.supplier_name_to_id = {}

        for supplier in self.suppliers:
            supplier_id = int(supplier["id"])
            supplier_name = str(
                supplier.get("supplier_name") or ""
            ).strip()

            if not supplier_name:
                continue

            label = supplier_name
            supplier_code = str(
                supplier.get("supplier_code") or ""
            ).strip()

            if supplier_code:
                label = f"{supplier_name} ({supplier_code})"

            values.append(label)
            self.supplier_name_to_id[label] = supplier_id

        self.supplier_combo.configure(values=values)
        self.supplier_var.set("공급처 미지정")

        order_supplier_id = self.order_item.get("supplier_id")

        if order_supplier_id:
            for label, supplier_id in (
                self.supplier_name_to_id.items()
            ):
                if supplier_id == int(order_supplier_id):
                    self.supplier_var.set(label)
                    break

    def save(self) -> None:
        product_name = self.product_name_var.get().strip()

        if not product_name:
            messagebox.showwarning(
                "입력 확인",
                "ERP 상품명을 입력하세요.",
                parent=self,
            )
            self.product_name_entry.focus_set()
            return

        try:
            purchase_price = self._parse_nonnegative_int(
                self.purchase_price_var.get(),
                "매입가",
            )
            sale_price = self._parse_nonnegative_int(
                self.sale_price_var.get(),
                "판매가",
            )

            supplier_id = self.supplier_name_to_id.get(
                self.supplier_var.get()
            )

            product_id = (
                self.product_repository.create_product(
                    product_name=product_name,
                    platform=self.platform_var.get(),
                    platform_product_name=(
                        self.platform_product_name_var.get()
                    ),
                    option_name=self.option_name_var.get(),
                    supplier_id=supplier_id,
                    supplier_product_name=(
                        self.supplier_product_name_var.get()
                    ),
                    purchase_price=purchase_price,
                    sale_price=sale_price,
                    purchase_round=(
                        self.purchase_round_var.get()
                    ),
                    is_active=self.active_var.get(),
                )
            )

            self.result_product_id = int(product_id)
            self.grab_release()
            self.destroy()

        except Exception as error:
            messagebox.showerror(
                "상품 등록 오류",
                (
                    "상품을 등록하지 못했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

    def cancel(self) -> None:
        self.result_product_id = None

        try:
            self.grab_release()
        except tk.TclError:
            pass

        self.destroy()

    @staticmethod
    def _parse_nonnegative_int(
        value: str,
        field_name: str,
    ) -> int:
        cleaned = str(value).strip().replace(",", "")

        if not cleaned:
            return 0

        try:
            number = int(cleaned)
        except ValueError as error:
            raise ValueError(
                f"{field_name}는 숫자로 입력하세요."
            ) from error

        if number < 0:
            raise ValueError(
                f"{field_name}는 0 이상이어야 합니다."
            )

        return number

    def _center_on_parent(
        self,
        parent: tk.Misc,
    ) -> None:
        self.update_idletasks()

        try:
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_width = parent.winfo_width()
            parent_height = parent.winfo_height()

            width = self.winfo_width()
            height = self.winfo_height()

            x = parent_x + max(
                0,
                (parent_width - width) // 2,
            )
            y = parent_y + max(
                0,
                (parent_height - height) // 2,
            )

            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass