from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from modules.mappings.quick_product_dialog import QuickProductDialog
from modules.orders.order_repository import OrderRepository
from modules.products.product_repository import ProductRepository


class MappingPage(ttk.Frame):
    """미매핑 처리와 전체 매핑 수정에 집중한 실무형 화면입니다."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=16)

        self.order_repository = OrderRepository()
        self.product_repository = ProductRepository()

        self.order_items: list[dict[str, Any]] = []
        self.products: list[dict[str, Any]] = []
        self.history: list[dict[str, Any]] = []

        self.order_search_var = tk.StringVar()
        self.product_search_var = tk.StringVar()
        self.history_search_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="매핑 데이터를 불러오는 중입니다."
        )

        self._build()
        self.refresh_all()

    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x")

        ttk.Label(
            header,
            text="상품매핑",
            font=("맑은 고딕", 20, "bold"),
        ).pack(side="left")

        ttk.Button(
            header,
            text="저장규칙 자동매핑",
            command=self.run_auto_mapping,
        ).pack(side="right")

        ttk.Button(
            header,
            text="새로고침",
            command=self.refresh_all,
        ).pack(side="right", padx=8)

        ttk.Label(
            self,
            text=(
                "한 번 수동 연결한 판매처 상품명·옵션은 "
                "다음 주문부터 자동으로 연결됩니다."
            ),
        ).pack(anchor="w", pady=(4, 12))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.work_tab = ttk.Frame(
            notebook,
            padding=10,
        )
        self.history_tab = ttk.Frame(
            notebook,
            padding=10,
        )

        notebook.add(
            self.work_tab,
            text="미매핑 처리",
        )
        notebook.add(
            self.history_tab,
            text="전체 매핑내역",
        )

        self._build_work_tab()
        self._build_history_tab()

        ttk.Label(
            self,
            textvariable=self.status_var,
            relief="sunken",
            padding=7,
        ).pack(fill="x", pady=(8, 0))

    def _build_work_tab(self) -> None:
        search_bar = ttk.Frame(self.work_tab)
        search_bar.pack(fill="x", pady=(0, 8))

        ttk.Label(
            search_bar,
            text="미매핑 검색",
        ).pack(side="left")

        order_search_entry = ttk.Entry(
            search_bar,
            textvariable=self.order_search_var,
            width=32,
        )
        order_search_entry.pack(
            side="left",
            padx=5,
        )
        order_search_entry.bind(
            "<Return>",
            lambda _event: self.load_order_items(),
        )

        ttk.Button(
            search_bar,
            text="검색",
            command=self.load_order_items,
        ).pack(side="left")

        ttk.Label(
            search_bar,
            text="ERP 상품 검색",
        ).pack(side="left", padx=(25, 0))

        product_search_entry = ttk.Entry(
            search_bar,
            textvariable=self.product_search_var,
            width=28,
        )
        product_search_entry.pack(
            side="left",
            padx=5,
        )
        product_search_entry.bind(
            "<Return>",
            lambda _event: self.load_products(),
        )

        ttk.Button(
            search_bar,
            text="검색",
            command=self.load_products,
        ).pack(side="left")

        panes = ttk.Panedwindow(
            self.work_tab,
            orient="horizontal",
        )
        panes.pack(fill="both", expand=True)

        left = ttk.LabelFrame(
            panes,
            text="미매핑 주문상품",
            padding=6,
        )
        right = ttk.LabelFrame(
            panes,
            text="ERP 상품",
            padding=6,
        )

        panes.add(left, weight=1)
        panes.add(right, weight=1)

        self.order_tree = self._create_tree(
            left,
            columns=(
                "platform",
                "order",
                "name",
                "option",
                "quantity",
            ),
            headings=(
                "플랫폼",
                "주문번호",
                "판매처 상품명",
                "옵션",
                "수량",
            ),
            widths=(70, 125, 260, 130, 55),
        )

        self.product_tree = self._create_tree(
            right,
            columns=(
                "code",
                "name",
                "option",
                "supplier",
            ),
            headings=(
                "상품코드",
                "내부 상품명",
                "옵션",
                "공급처",
            ),
            widths=(105, 230, 125, 110),
        )

        actions = ttk.Frame(self.work_tab)
        actions.pack(fill="x", pady=(8, 0))

        ttk.Button(
            actions,
            text="선택 상품 연결 + 규칙 저장",
            command=self.map_selected_item,
        ).pack(side="left")

        ttk.Button(
            actions,
            text="같은 미매핑 상품 전체 적용",
            command=self.apply_same,
        ).pack(side="left", padx=8)

        ttk.Button(
            actions,
            text="새 상품 등록 및 연결",
            command=self.create_product_and_map,
        ).pack(side="left")

        self.order_tree.bind(
            "<Double-1>",
            lambda _event: self.map_selected_item(),
        )
        self.product_tree.bind(
            "<Double-1>",
            lambda _event: self.map_selected_item(),
        )

    def _build_history_tab(self) -> None:
        search_bar = ttk.Frame(self.history_tab)
        search_bar.pack(fill="x", pady=(0, 8))

        history_entry = ttk.Entry(
            search_bar,
            textvariable=self.history_search_var,
            width=40,
        )
        history_entry.pack(side="left")
        history_entry.bind(
            "<Return>",
            lambda _event: self.load_history(),
        )

        ttk.Button(
            search_bar,
            text="검색",
            command=self.load_history,
        ).pack(side="left", padx=5)

        ttk.Button(
            search_bar,
            text="선택 매핑 해제",
            command=self.unmap_history,
        ).pack(side="right")

        self.history_tree = self._create_tree(
            self.history_tab,
            columns=(
                "platform",
                "order",
                "source",
                "option",
                "target",
                "supplier",
                "status",
            ),
            headings=(
                "플랫폼",
                "주문번호",
                "판매처 상품명",
                "옵션",
                "연결 상품",
                "공급처",
                "상태",
            ),
            widths=(70, 125, 240, 120, 220, 100, 90),
        )

    @staticmethod
    def _create_tree(
        parent: ttk.Frame,
        *,
        columns: tuple[str, ...],
        headings: tuple[str, ...],
        widths: tuple[int, ...],
    ) -> ttk.Treeview:
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            container,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        for column, heading, width in zip(
            columns,
            headings,
            widths,
        ):
            tree.heading(column, text=heading)
            tree.column(
                column,
                width=width,
                minwidth=50,
                anchor=(
                    "center"
                    if column in {
                        "quantity",
                        "status",
                        "platform",
                    }
                    else "w"
                ),
            )

        y_scroll = ttk.Scrollbar(
            container,
            orient="vertical",
            command=tree.yview,
        )
        x_scroll = ttk.Scrollbar(
            container,
            orient="horizontal",
            command=tree.xview,
        )

        tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        return tree

    def refresh_all(self) -> None:
        try:
            self.load_order_items()
            self.load_products()
            self.load_history()
            self._update_status()
        except Exception as error:
            messagebox.showerror(
                "상품매핑 오류",
                (
                    "상품매핑 데이터를 불러오지 못했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

    def refresh_data(self) -> None:
        """MainWindow에서 공통으로 호출할 수 있는 호환 메서드입니다."""
        self.refresh_all()

    def load_order_items(self) -> None:
        self.order_items = (
            self.order_repository.get_order_items(
                keyword=(
                    self.order_search_var.get().strip()
                    or None
                ),
                unmapped_only=True,
            )
        )

        rows = [
            (
                int(item["id"]),
                (
                    item.get("platform") or "",
                    item.get("order_number") or "",
                    item.get("platform_product_name") or "",
                    item.get("option_name") or "",
                    int(item.get("quantity") or 0),
                ),
            )
            for item in self.order_items
        ]

        self._fill_tree(self.order_tree, rows)
        self._update_status()

    def load_products(self) -> None:
        self.products = (
            self.product_repository.get_products(
                keyword=(
                    self.product_search_var.get().strip()
                    or None
                ),
                active_only=True,
            )
        )

        rows = [
            (
                int(product["id"]),
                (
                    product.get("product_code") or "",
                    product.get("product_name") or "",
                    product.get("option_name") or "",
                    product.get("supplier_name")
                    or "미지정",
                ),
            )
            for product in self.products
        ]

        self._fill_tree(self.product_tree, rows)
        self._update_status()

    def load_history(self) -> None:
        rows = self.order_repository.get_order_items(
            keyword=(
                self.history_search_var.get().strip()
                or None
            )
        )

        self.history = [
            item
            for item in rows
            if item.get("product_id")
        ]

        tree_rows = [
            (
                int(item["id"]),
                (
                    item.get("platform") or "",
                    item.get("order_number") or "",
                    item.get("platform_product_name") or "",
                    item.get("option_name") or "",
                    item.get("product_name") or "",
                    item.get("supplier_name")
                    or "미지정",
                    item.get("mapping_status") or "",
                ),
            )
            for item in self.history
        ]

        self._fill_tree(
            self.history_tree,
            tree_rows,
        )
        self._update_status()

    @staticmethod
    def _fill_tree(
        tree: ttk.Treeview,
        rows: list[tuple[int, tuple[Any, ...]]],
    ) -> None:
        tree.delete(*tree.get_children())

        for item_id, values in rows:
            tree.insert(
                "",
                "end",
                iid=str(item_id),
                values=values,
            )

    def _selected_id(
        self,
        tree: ttk.Treeview,
        label: str,
    ) -> int | None:
        selected = tree.selection()

        if not selected:
            messagebox.showwarning(
                "선택 필요",
                f"{label}을 선택해 주세요.",
                parent=self,
            )
            return None

        return int(selected[0])

    def map_selected_item(self) -> None:
        order_item_id = self._selected_id(
            self.order_tree,
            "미매핑 주문상품",
        )
        product_id = self._selected_id(
            self.product_tree,
            "ERP 상품",
        )

        if order_item_id is None or product_id is None:
            return

        try:
            self.order_repository.map_order_item(
                order_item_id,
                product_id,
                "수동매핑",
            )
            applied_count = (
                self.order_repository.save_mapping_rule_for_item(
                    order_item_id,
                    product_id,
                )
            )

            messagebox.showinfo(
                "매핑 완료",
                (
                    "연결 및 자동매핑 규칙을 저장했습니다.\n\n"
                    f"현재 선택 상품 적용: "
                    f"{int(applied_count or 0):,}건"
                ),
                parent=self,
            )
            self.refresh_all()

        except Exception as error:
            messagebox.showerror(
                "매핑 오류",
                f"상품을 연결하지 못했습니다.\n\n{error}",
                parent=self,
            )

    def apply_same(self) -> None:
        order_item_id = self._selected_id(
            self.order_tree,
            "미매핑 주문상품",
        )
        product_id = self._selected_id(
            self.product_tree,
            "ERP 상품",
        )

        if order_item_id is None or product_id is None:
            return

        try:
            self.order_repository.save_mapping_rule_for_item(
                order_item_id,
                product_id,
            )
            count = self.order_repository.apply_saved_rule()

            messagebox.showinfo(
                "일괄 적용",
                (
                    "저장된 규칙으로 동일 상품을 연결했습니다.\n\n"
                    f"적용: {int(count or 0):,}건"
                ),
                parent=self,
            )
            self.refresh_all()

        except Exception as error:
            messagebox.showerror(
                "일괄 매핑 오류",
                f"일괄 매핑에 실패했습니다.\n\n{error}",
                parent=self,
            )

    def run_auto_mapping(self) -> None:
        try:
            result = (
                self.order_repository.auto_map_order_items()
            )

            rule_count = int(
                result.get("rule_mapped_count") or 0
            )
            total_count = int(
                result.get("mapped_count") or 0
            )
            name_count = max(0, total_count - rule_count)

            messagebox.showinfo(
                "자동매핑 완료",
                (
                    f"저장 규칙: {rule_count:,}건\n"
                    f"상품명 자동일치: {name_count:,}건\n"
                    f"미일치: "
                    f"{int(result.get('unmatched_count') or 0):,}건\n"
                    f"중복후보: "
                    f"{int(result.get('ambiguous_count') or 0):,}건"
                ),
                parent=self,
            )
            self.refresh_all()

        except Exception as error:
            messagebox.showerror(
                "자동매핑 오류",
                f"자동매핑에 실패했습니다.\n\n{error}",
                parent=self,
            )

    def unmap_history(self) -> None:
        order_item_id = self._selected_id(
            self.history_tree,
            "매핑내역",
        )

        if order_item_id is None:
            return

        confirmed = messagebox.askyesno(
            "매핑 해제",
            (
                "선택한 상품 연결을 해제하고 저장된 "
                "자동매핑 규칙도 삭제하시겠습니까?"
            ),
            parent=self,
        )

        if not confirmed:
            return

        try:
            self.order_repository.delete_mapping_rule_for_item(
                order_item_id
            )
            self.order_repository.unmap_order_item(
                order_item_id
            )
            self.refresh_all()

        except Exception as error:
            messagebox.showerror(
                "매핑 해제 오류",
                f"매핑을 해제하지 못했습니다.\n\n{error}",
                parent=self,
            )

    def create_product_and_map(self) -> None:
        order_item_id = self._selected_id(
            self.order_tree,
            "미매핑 주문상품",
        )

        if order_item_id is None:
            return

        order_item = next(
            (
                item
                for item in self.order_items
                if int(item["id"]) == order_item_id
            ),
            None,
        )

        if order_item is None:
            messagebox.showerror(
                "상품 등록 오류",
                "선택한 주문상품 정보를 찾을 수 없습니다.",
                parent=self,
            )
            return

        dialog = QuickProductDialog(
            self,
            order_item=order_item,
            product_repository=self.product_repository,
        )
        self.wait_window(dialog)

        if dialog.result_product_id is None:
            return

        try:
            product_id = int(dialog.result_product_id)

            self.order_repository.map_order_item(
                order_item_id,
                product_id,
                "신규상품매핑",
            )
            self.order_repository.save_mapping_rule_for_item(
                order_item_id,
                product_id,
            )
            self.refresh_all()

            messagebox.showinfo(
                "등록 및 연결 완료",
                "새 상품을 등록하고 주문상품에 연결했습니다.",
                parent=self,
            )

        except Exception as error:
            messagebox.showerror(
                "상품 연결 오류",
                (
                    "상품은 등록되었지만 주문상품 연결 중 "
                    "오류가 발생했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )
            self.refresh_all()

    def _update_status(self) -> None:
        self.status_var.set(
            f"미매핑 {len(self.order_items):,}건 · "
            f"사용 상품 {len(self.products):,}건 · "
            f"연결내역 {len(self.history):,}건"
        )