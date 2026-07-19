from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from modules.mappings.quick_product_dialog import QuickProductDialog
from modules.orders.order_repository import OrderRepository
from modules.products.product_repository import ProductRepository


class MappingPage(ttk.Frame):
    """주문상품과 ERP 상품을 연결하는 상품매핑 화면입니다."""

    def __init__(
        self,
        parent: tk.Misc,
    ) -> None:
        super().__init__(parent)

        self.order_repository = OrderRepository()
        self.product_repository = ProductRepository()

        self.order_items: list[dict[str, Any]] = []
        self.products: list[dict[str, Any]] = []

        self.order_search_var = tk.StringVar()
        self.product_search_var = tk.StringVar()

        self.status_var = tk.StringVar(
            value="상품매핑 데이터를 불러오는 중입니다."
        )

        self._build_ui()
        self.refresh_all()

    # =========================================================
    # 화면 구성
    # =========================================================

    def _build_ui(self) -> None:
        self.columnconfigure(
            0,
            weight=1,
        )
        self.columnconfigure(
            1,
            weight=0,
        )
        self.columnconfigure(
            2,
            weight=1,
        )
        self.rowconfigure(
            2,
            weight=1,
        )

        self._build_header()
        self._build_search_area()
        self._build_mapping_area()
        self._build_status_bar()

    def _build_header(self) -> None:
        header = ttk.Frame(
            self,
            padding=(20, 18, 20, 10),
        )
        header.grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="ew",
        )

        header.columnconfigure(
            0,
            weight=1,
        )

        title = ttk.Label(
            header,
            text="상품매핑",
            font=("맑은 고딕", 18, "bold"),
        )
        title.grid(
            row=0,
            column=0,
            sticky="w",
        )

        description = ttk.Label(
            header,
            text=(
                "주문으로 들어온 판매처 상품을 "
                "ERP 상품과 공급처에 연결합니다."
            ),
        )
        description.grid(
            row=1,
            column=0,
            pady=(5, 0),
            sticky="w",
        )

        auto_button = ttk.Button(
            header,
            text="자동매핑 실행",
            command=self.run_auto_mapping,
        )
        auto_button.grid(
            row=0,
            column=1,
            rowspan=2,
            padx=(10, 0),
            sticky="e",
        )

        refresh_button = ttk.Button(
            header,
            text="새로고침",
            command=self.refresh_all,
        )
        refresh_button.grid(
            row=0,
            column=2,
            rowspan=2,
            padx=(8, 0),
            sticky="e",
        )

    def _build_search_area(self) -> None:
        left_search = ttk.LabelFrame(
            self,
            text="미매핑 주문상품 검색",
            padding=10,
        )
        left_search.grid(
            row=1,
            column=0,
            padx=(20, 8),
            pady=(0, 10),
            sticky="ew",
        )

        left_search.columnconfigure(
            0,
            weight=1,
        )

        order_entry = ttk.Entry(
            left_search,
            textvariable=self.order_search_var,
        )
        order_entry.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        order_entry.bind(
            "<Return>",
            lambda _: self.load_order_items(),
        )

        ttk.Button(
            left_search,
            text="검색",
            command=self.load_order_items,
        ).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )

        right_search = ttk.LabelFrame(
            self,
            text="ERP 상품 검색",
            padding=10,
        )
        right_search.grid(
            row=1,
            column=2,
            padx=(8, 20),
            pady=(0, 10),
            sticky="ew",
        )

        right_search.columnconfigure(
            0,
            weight=1,
        )

        product_entry = ttk.Entry(
            right_search,
            textvariable=self.product_search_var,
        )
        product_entry.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        product_entry.bind(
            "<Return>",
            lambda _: self.load_products(),
        )

        ttk.Button(
            right_search,
            text="검색",
            command=self.load_products,
        ).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )

    def _build_mapping_area(self) -> None:
        self._build_order_item_tree()
        self._build_center_buttons()
        self._build_product_tree()

    def _build_order_item_tree(self) -> None:
        frame = ttk.LabelFrame(
            self,
            text="미매핑 주문상품",
            padding=10,
        )
        frame.grid(
            row=2,
            column=0,
            padx=(20, 8),
            pady=(0, 10),
            sticky="nsew",
        )

        frame.columnconfigure(
            0,
            weight=1,
        )
        frame.rowconfigure(
            0,
            weight=1,
        )

        columns = (
            "platform",
            "order_number",
            "product_name",
            "option_name",
            "quantity",
        )

        self.order_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        self.order_tree.heading(
            "platform",
            text="플랫폼",
        )
        self.order_tree.heading(
            "order_number",
            text="주문번호",
        )
        self.order_tree.heading(
            "product_name",
            text="판매처 상품명",
        )
        self.order_tree.heading(
            "option_name",
            text="옵션명",
        )
        self.order_tree.heading(
            "quantity",
            text="수량",
        )

        self.order_tree.column(
            "platform",
            width=70,
            anchor="center",
        )
        self.order_tree.column(
            "order_number",
            width=130,
        )
        self.order_tree.column(
            "product_name",
            width=260,
        )
        self.order_tree.column(
            "option_name",
            width=140,
        )
        self.order_tree.column(
            "quantity",
            width=55,
            anchor="center",
        )

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.order_tree.yview,
        )
        self.order_tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.order_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        self.order_tree.bind(
            "<Double-1>",
            lambda _: self.create_product_and_map(),
        )

    def _build_center_buttons(self) -> None:
        frame = ttk.Frame(
            self,
            padding=10,
        )
        frame.grid(
            row=2,
            column=1,
            pady=(0, 10),
            sticky="ns",
        )

        ttk.Label(
            frame,
            text="선택 상품 연결",
            font=("맑은 고딕", 10, "bold"),
        ).pack(
            pady=(100, 15),
        )

        ttk.Button(
            frame,
            text="새 상품 등록\n및 즉시 매핑",
            command=self.create_product_and_map,
            width=16,
        ).pack(
            pady=(5, 12),
            ipady=4,
        )

        ttk.Separator(
            frame,
            orient="horizontal",
        ).pack(
            fill="x",
            pady=(0, 12),
        )

        ttk.Button(
            frame,
            text="← 기존 상품 매핑",
            command=self.map_selected_item,
            width=16,
        ).pack(
            pady=5,
        )

        ttk.Button(
            frame,
            text="매핑 해제",
            command=self.unmap_selected_item,
            width=16,
        ).pack(
            pady=5,
        )

    def _build_product_tree(self) -> None:
        frame = ttk.LabelFrame(
            self,
            text="ERP 등록 상품",
            padding=10,
        )
        frame.grid(
            row=2,
            column=2,
            padx=(8, 20),
            pady=(0, 10),
            sticky="nsew",
        )

        frame.columnconfigure(
            0,
            weight=1,
        )
        frame.rowconfigure(
            0,
            weight=1,
        )

        columns = (
            "product_code",
            "product_name",
            "option_name",
            "supplier_name",
            "purchase_round",
        )

        self.product_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        self.product_tree.heading(
            "product_code",
            text="상품코드",
        )
        self.product_tree.heading(
            "product_name",
            text="내부 상품명",
        )
        self.product_tree.heading(
            "option_name",
            text="옵션명",
        )
        self.product_tree.heading(
            "supplier_name",
            text="공급처",
        )
        self.product_tree.heading(
            "purchase_round",
            text="차수",
        )

        self.product_tree.column(
            "product_code",
            width=105,
        )
        self.product_tree.column(
            "product_name",
            width=240,
        )
        self.product_tree.column(
            "option_name",
            width=130,
        )
        self.product_tree.column(
            "supplier_name",
            width=100,
        )
        self.product_tree.column(
            "purchase_round",
            width=60,
            anchor="center",
        )

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.product_tree.yview,
        )
        self.product_tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.product_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        self.product_tree.bind(
            "<Double-1>",
            lambda _: self.map_selected_item(),
        )

    def _build_status_bar(self) -> None:
        status = ttk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            padding=(20, 8),
            relief="sunken",
        )
        status.grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="ew",
        )

    # =========================================================
    # 데이터 조회
    # =========================================================

    def refresh_all(self) -> None:
        self.load_order_items()
        self.load_products()

    def load_order_items(self) -> None:
        keyword = (
            self.order_search_var.get().strip()
            or None
        )

        try:
            self.order_items = (
                self.order_repository.get_order_items(
                    keyword=keyword,
                    unmapped_only=True,
                )
            )

        except Exception as error:
            messagebox.showerror(
                "주문상품 조회 오류",
                "미매핑 주문상품을 불러오지 못했습니다.\n\n"
                f"{error}",
            )
            return

        for item_id in self.order_tree.get_children():
            self.order_tree.delete(item_id)

        for item in self.order_items:
            order_item_id = int(item["id"])

            self.order_tree.insert(
                "",
                "end",
                iid=str(order_item_id),
                values=(
                    item.get("platform") or "",
                    item.get("order_number") or "",
                    item.get("platform_product_name") or "",
                    item.get("option_name") or "",
                    item.get("quantity") or 0,
                ),
            )

        self._update_status()

    def load_products(self) -> None:
        keyword = (
            self.product_search_var.get().strip()
            or None
        )

        try:
            self.products = (
                self.product_repository.get_products(
                    keyword=keyword,
                    active_only=True,
                )
            )

        except Exception as error:
            messagebox.showerror(
                "상품 조회 오류",
                "ERP 상품을 불러오지 못했습니다.\n\n"
                f"{error}",
            )
            return

        for item_id in self.product_tree.get_children():
            self.product_tree.delete(item_id)

        for product in self.products:
            product_id = int(product["id"])

            self.product_tree.insert(
                "",
                "end",
                iid=str(product_id),
                values=(
                    product.get("product_code") or "",
                    product.get("product_name") or "",
                    product.get("option_name") or "",
                    product.get("supplier_name") or "미지정",
                    product.get("purchase_round") or "",
                ),
            )

        self._update_status()

    # =========================================================
    # 새 상품 등록 및 즉시 매핑
    # =========================================================

    def create_product_and_map(self) -> None:
        order_item = self._get_selected_order_item()

        if order_item is None:
            messagebox.showwarning(
                "주문상품 선택",
                "왼쪽에서 새 상품으로 등록할 주문상품을 선택해 주세요.",
            )
            return

        order_item_id = int(order_item["id"])

        dialog = QuickProductDialog(
            self,
            order_item=order_item,
        )
        self.wait_window(dialog)

        product_id = dialog.result_product_id

        if product_id is None:
            return

        try:
            changed_rows = (
                self.order_repository.map_order_item(
                    order_item_id=order_item_id,
                    product_id=int(product_id),
                    mapping_status="신규상품매핑",
                )
            )

        except Exception as error:
            messagebox.showerror(
                "즉시 매핑 오류",
                (
                    "상품은 등록되었지만 주문상품 연결에 실패했습니다.\n\n"
                    f"등록된 상품 ID: {product_id}\n"
                    f"오류: {error}"
                ),
            )
            self.refresh_all()
            return

        if changed_rows == 0:
            messagebox.showwarning(
                "즉시 매핑 실패",
                (
                    "상품은 등록되었지만 연결할 주문상품을 찾지 못했습니다.\n"
                    "목록을 새로고침한 뒤 확인해 주세요."
                ),
            )
            self.refresh_all()
            return

        messagebox.showinfo(
            "등록 및 매핑 완료",
            (
                "새 ERP 상품이 등록되었고\n"
                "선택한 주문상품과 즉시 연결되었습니다."
            ),
        )

        self.refresh_all()

    def _get_selected_order_item(
        self,
    ) -> dict[str, Any] | None:
        selection = self.order_tree.selection()

        if not selection:
            return None

        try:
            selected_id = int(selection[0])
        except (TypeError, ValueError):
            return None

        for item in self.order_items:
            try:
                item_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue

            if item_id == selected_id:
                return item

        return None

    # =========================================================
    # 자동매핑
    # =========================================================

    def run_auto_mapping(self) -> None:
        try:
            result = (
                self.order_repository
                .auto_map_order_items()
            )

        except Exception as error:
            messagebox.showerror(
                "자동매핑 오류",
                "자동매핑을 실행하지 못했습니다.\n\n"
                f"{error}",
            )
            return

        messagebox.showinfo(
            "자동매핑 완료",
            (
                f"대상: {result['target_count']}건\n"
                f"매핑 성공: {result['mapped_count']}건\n"
                f"일치 상품 없음: {result['unmatched_count']}건\n"
                f"중복 후보: {result['ambiguous_count']}건"
            ),
        )

        self.refresh_all()

    # =========================================================
    # 수동매핑
    # =========================================================

    def map_selected_item(self) -> None:
        order_selection = (
            self.order_tree.selection()
        )
        product_selection = (
            self.product_tree.selection()
        )

        if not order_selection:
            messagebox.showwarning(
                "주문상품 선택",
                "왼쪽에서 주문상품을 선택해 주세요.",
            )
            return

        if not product_selection:
            messagebox.showwarning(
                "ERP 상품 선택",
                "오른쪽에서 연결할 ERP 상품을 선택해 주세요.",
            )
            return

        order_item_id = int(
            order_selection[0]
        )
        product_id = int(
            product_selection[0]
        )

        order_values = self.order_tree.item(
            order_selection[0],
            "values",
        )
        product_values = self.product_tree.item(
            product_selection[0],
            "values",
        )

        answer = messagebox.askyesno(
            "상품매핑 확인",
            (
                f"판매처 상품\n"
                f"{order_values[2]}\n\n"
                f"ERP 상품\n"
                f"{product_values[1]}\n\n"
                f"두 상품을 연결하시겠습니까?"
            ),
        )

        if not answer:
            return

        try:
            changed_rows = (
                self.order_repository.map_order_item(
                    order_item_id=order_item_id,
                    product_id=product_id,
                    mapping_status="수동매핑",
                )
            )

        except Exception as error:
            messagebox.showerror(
                "상품매핑 오류",
                "상품을 연결하지 못했습니다.\n\n"
                f"{error}",
            )
            return

        if changed_rows == 0:
            messagebox.showwarning(
                "매핑 실패",
                "연결할 주문상품을 찾지 못했습니다.",
            )
            return

        messagebox.showinfo(
            "매핑 완료",
            "주문상품과 ERP 상품이 연결되었습니다.",
        )

        self.refresh_all()

    def unmap_selected_item(self) -> None:
        messagebox.showinfo(
            "안내",
            (
                "현재 왼쪽 목록은 미매핑 상품만 표시하므로 "
                "매핑 해제 기능은 다음 단계에서 "
                "전체 매핑내역 화면과 함께 연결합니다."
            ),
        )

    # =========================================================
    # 상태 표시
    # =========================================================

    def _update_status(self) -> None:
        self.status_var.set(
            (
                f"미매핑 주문상품 "
                f"{len(self.order_items):,}건 · "
                f"사용 가능한 ERP 상품 "
                f"{len(self.products):,}건"
            )
        )