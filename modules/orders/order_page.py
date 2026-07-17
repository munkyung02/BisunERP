import tkinter as tk
from tkinter import messagebox, ttk

from modules.orders.order_repository import OrderRepository


class OrderPage(tk.Toplevel):
    """비선상회 ERP 주문관리 화면입니다."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

        self.repository = OrderRepository()
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="주문 데이터를 불러오는 중입니다.")

        self.title("비선상회 ERP - 주문관리")
        self.geometry("1380x760")
        self.minsize(1100, 650)

        self.protocol("WM_DELETE_WINDOW", self._close_window)

        self._configure_style()
        self._create_ui()
        self.load_orders()

    def _configure_style(self) -> None:
        style = ttk.Style(self)

        style.configure(
            "Order.Treeview",
            rowheight=30,
            font=("맑은 고딕", 10),
        )

        style.configure(
            "Order.Treeview.Heading",
            font=("맑은 고딕", 10, "bold"),
        )

        style.configure(
            "OrderAction.TButton",
            font=("맑은 고딕", 10),
            padding=(12, 8),
        )

    def _create_ui(self) -> None:
        header = tk.Frame(
            self,
            padx=25,
            pady=20,
        )
        header.pack(fill="x")

        title = tk.Label(
            header,
            text="주문관리",
            font=("맑은 고딕", 22, "bold"),
        )
        title.pack(side="left")

        description = tk.Label(
            header,
            text="쿠팡 및 비선상회 주문을 조회하고 관리합니다.",
            font=("맑은 고딕", 10),
        )
        description.pack(side="left", padx=(15, 0), pady=(8, 0))

        ttk.Separator(
            self,
            orient="horizontal",
        ).pack(fill="x")

        self._create_toolbar()
        self._create_summary_area()
        self._create_order_table()
        self._create_status_bar()

    def _create_toolbar(self) -> None:
        toolbar = tk.Frame(
            self,
            padx=25,
            pady=15,
        )
        toolbar.pack(fill="x")

        search_label = tk.Label(
            toolbar,
            text="검색",
            font=("맑은 고딕", 10, "bold"),
        )
        search_label.pack(side="left")

        search_entry = ttk.Entry(
            toolbar,
            textvariable=self.search_var,
            width=40,
            font=("맑은 고딕", 10),
        )
        search_entry.pack(side="left", padx=(10, 8))
        search_entry.bind("<Return>", self._search_with_enter)

        search_button = ttk.Button(
            toolbar,
            text="검색",
            command=self.load_orders,
            style="OrderAction.TButton",
        )
        search_button.pack(side="left")

        reset_button = ttk.Button(
            toolbar,
            text="검색 초기화",
            command=self.reset_search,
            style="OrderAction.TButton",
        )
        reset_button.pack(side="left", padx=(8, 0))

        refresh_button = ttk.Button(
            toolbar,
            text="새로고침",
            command=self.load_orders,
            style="OrderAction.TButton",
        )
        refresh_button.pack(side="right")

        import_button = ttk.Button(
            toolbar,
            text="쿠팡 주문 가져오기",
            command=self.show_import_preparing,
            style="OrderAction.TButton",
        )
        import_button.pack(side="right", padx=(0, 8))

    def _create_summary_area(self) -> None:
        summary = tk.Frame(
            self,
            padx=25,
            pady=5,
        )
        summary.pack(fill="x")

        self.all_count_var = tk.StringVar(value="전체 주문 0건")
        self.unmapped_count_var = tk.StringVar(value="미매핑 0건")
        self.purchase_waiting_var = tk.StringVar(value="발주 대기 0건")
        self.shipping_count_var = tk.StringVar(value="배송 중 0건")

        variables = [
            self.all_count_var,
            self.unmapped_count_var,
            self.purchase_waiting_var,
            self.shipping_count_var,
        ]

        for variable in variables:
            label = tk.Label(
                summary,
                textvariable=variable,
                padx=18,
                pady=10,
                relief="ridge",
                borderwidth=1,
                font=("맑은 고딕", 10, "bold"),
            )
            label.pack(side="left", padx=(0, 8))

    def _create_order_table(self) -> None:
        table_frame = tk.Frame(
            self,
            padx=25,
            pady=15,
        )
        table_frame.pack(fill="both", expand=True)

        columns = (
            "platform",
            "order_number",
            "ordered_at",
            "receiver_name",
            "product_name",
            "option_name",
            "quantity",
            "mapping_status",
            "purchase_status",
            "shipment_status",
        )

        self.order_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="Order.Treeview",
        )

        column_settings = {
            "platform": ("판매채널", 90, "center"),
            "order_number": ("주문번호", 145, "center"),
            "ordered_at": ("주문일시", 145, "center"),
            "receiver_name": ("수령인", 90, "center"),
            "product_name": ("상품명", 260, "w"),
            "option_name": ("옵션", 180, "w"),
            "quantity": ("수량", 60, "center"),
            "mapping_status": ("매핑상태", 90, "center"),
            "purchase_status": ("발주상태", 90, "center"),
            "shipment_status": ("배송상태", 90, "center"),
        }

        for column_name, (
            heading,
            width,
            anchor,
        ) in column_settings.items():
            self.order_tree.heading(
                column_name,
                text=heading,
            )

            self.order_tree.column(
                column_name,
                width=width,
                minwidth=50,
                anchor=anchor,
            )

        vertical_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.order_tree.yview,
        )

        horizontal_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.order_tree.xview,
        )

        self.order_tree.configure(
            yscrollcommand=vertical_scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set,
        )

        self.order_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        vertical_scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        horizontal_scrollbar.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        table_frame.grid_rowconfigure(
            0,
            weight=1,
        )

        table_frame.grid_columnconfigure(
            0,
            weight=1,
        )

    def _create_status_bar(self) -> None:
        status_bar = tk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            padx=15,
            pady=8,
            relief="sunken",
            borderwidth=1,
            font=("맑은 고딕", 9),
        )
        status_bar.pack(fill="x", side="bottom")

    def load_orders(self) -> None:
        self.status_var.set("주문 데이터를 조회하고 있습니다.")
        self.update_idletasks()

        try:
            for item_id in self.order_tree.get_children():
                self.order_tree.delete(item_id)

            orders = self.repository.get_orders(
                search_text=self.search_var.get()
            )

            for order in orders:
                self.order_tree.insert(
                    "",
                    "end",
                    values=(
                        order["platform"],
                        order["order_number"],
                        order["ordered_at"],
                        order["receiver_name"],
                        order["product_name"],
                        order["option_name"],
                        order["quantity"],
                        order["mapping_status"],
                        order["purchase_status"],
                        order["shipment_status"],
                    ),
                )

            self._refresh_summary()

            if orders:
                self.status_var.set(
                    f"주문 항목 {len(orders)}개를 불러왔습니다."
                )
            else:
                self.status_var.set(
                    "저장된 주문이 없습니다. "
                    "다음 단계에서 쿠팡 주문 가져오기를 연결합니다."
                )

        except Exception as error:
            self.status_var.set("주문 조회 중 오류가 발생했습니다.")

            messagebox.showerror(
                "주문 조회 오류",
                "주문 데이터를 불러오지 못했습니다.\n\n"
                f"오류 내용: {error}",
                parent=self,
            )

    def _refresh_summary(self) -> None:
        counts = self.repository.get_status_counts()

        self.all_count_var.set(
            f"전체 주문 {counts['all']}건"
        )
        self.unmapped_count_var.set(
            f"미매핑 {counts['unmapped']}건"
        )
        self.purchase_waiting_var.set(
            f"발주 대기 {counts['purchase_waiting']}건"
        )
        self.shipping_count_var.set(
            f"배송 중 {counts['shipping']}건"
        )

    def reset_search(self) -> None:
        self.search_var.set("")
        self.load_orders()

    def _search_with_enter(
        self,
        event: tk.Event,
    ) -> None:
        self.load_orders()

    def show_import_preparing(self) -> None:
        messagebox.showinfo(
            "쿠팡 주문 가져오기",
            "화면 연결은 완료되었습니다.\n\n"
            "다음 Sprint에서 쿠팡 엑셀 주문을 "
            "SQLite에 저장하는 기능을 연결합니다.",
            parent=self,
        )

    def _close_window(self) -> None:
        self.destroy()
        