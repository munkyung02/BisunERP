import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from modules.orders.order_import_service import OrderImportService
from modules.orders.order_repository import OrderRepository
from modules.purchases.purchase_service import PurchaseService


class OrderPage:
    """비선상회 ERP 주문관리 화면입니다."""

    def __init__(
        self,
        parent: tk.Misc,
    ) -> None:
        self.parent = parent
        self.repository = OrderRepository()
        self.import_service = OrderImportService(
            self.repository
        )

        self.purchase_service = PurchaseService()

        self.window = tk.Toplevel(parent)
        self.window.title("비선상회 ERP - 주문관리")
        self.window.geometry("1500x850")
        self.window.minsize(1200, 700)

        self.keyword_var = tk.StringVar()
        self.platform_var = tk.StringVar(
            value="전체"
        )
        self.mapping_status_var = tk.StringVar(
            value="전체"
        )
        self.purchase_status_var = tk.StringVar(
            value="전체"
        )
        self.shipment_status_var = tk.StringVar(
            value="전체"
        )

        self.total_count_var = tk.StringVar(
            value="전체 주문 0건"
        )
        self.today_count_var = tk.StringVar(
            value="오늘 주문 0건"
        )
        self.unmapped_count_var = tk.StringVar(
            value="미매핑 0건"
        )
        self.purchase_waiting_var = tk.StringVar(
            value="발주 대기 0건"
        )
        self.shipping_count_var = tk.StringVar(
            value="배송 진행 0건"
        )

        self.status_var = tk.StringVar(
            value="주문관리 준비 완료"
        )

        self.order_rows: dict[str, dict[str, Any]] = {}

        self._configure_style()
        self._create_ui()
        self.refresh_orders()

        self.window.transient(parent)
        self.window.focus_force()

    # =========================================================
    # 스타일
    # =========================================================

    def _configure_style(self) -> None:
        style = ttk.Style(self.window)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Order.Treeview",
            font=("맑은 고딕", 10),
            rowheight=32,
        )

        style.configure(
            "Order.Treeview.Heading",
            font=("맑은 고딕", 10, "bold"),
        )

        style.configure(
            "Toolbar.TButton",
            font=("맑은 고딕", 10),
            padding=(12, 8),
        )

        style.configure(
            "Primary.TButton",
            font=("맑은 고딕", 10, "bold"),
            padding=(14, 9),
        )

    # =========================================================
    # 화면 구성
    # =========================================================

    def _create_ui(self) -> None:
        self._create_header()
        self._create_summary()
        self._create_search_area()
        self._create_action_area()
        self._create_order_table()
        self._create_status_bar()

    def _create_header(self) -> None:
        header = tk.Frame(
            self.window,
            padx=25,
            pady=18,
        )
        header.pack(fill="x")

        title = tk.Label(
            header,
            text="주문관리",
            font=("맑은 고딕", 24, "bold"),
        )
        title.pack(side="left")

        description = tk.Label(
            header,
            text=(
                "쿠팡 주문을 조회하고 상품매핑·발주·배송 상태를 "
                "관리합니다."
            ),
            font=("맑은 고딕", 10),
        )
        description.pack(
            side="left",
            padx=(15, 0),
            pady=(8, 0),
        )

    def _create_summary(self) -> None:
        summary_frame = tk.Frame(
            self.window,
            padx=25,
            pady=5,
        )
        summary_frame.pack(fill="x")

        summary_values = [
            self.total_count_var,
            self.today_count_var,
            self.unmapped_count_var,
            self.purchase_waiting_var,
            self.shipping_count_var,
        ]

        for index, value_var in enumerate(
            summary_values
        ):
            card = tk.Frame(
                summary_frame,
                padx=18,
                pady=13,
                relief="ridge",
                borderwidth=1,
            )
            card.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0, 10),
            )

            label = tk.Label(
                card,
                textvariable=value_var,
                font=("맑은 고딕", 11, "bold"),
            )
            label.pack()

            summary_frame.grid_columnconfigure(
                index,
                weight=1,
            )

    def _create_search_area(self) -> None:
        search_frame = tk.LabelFrame(
            self.window,
            text="검색 및 필터",
            font=("맑은 고딕", 11, "bold"),
            padx=15,
            pady=13,
        )
        search_frame.pack(
            fill="x",
            padx=25,
            pady=(15, 8),
        )

        tk.Label(
            search_frame,
            text="검색",
            font=("맑은 고딕", 10),
        ).grid(
            row=0,
            column=0,
            padx=(0, 7),
            pady=5,
            sticky="w",
        )

        keyword_entry = ttk.Entry(
            search_frame,
            textvariable=self.keyword_var,
            width=30,
        )
        keyword_entry.grid(
            row=0,
            column=1,
            padx=(0, 15),
            pady=5,
            sticky="ew",
        )
        keyword_entry.bind(
            "<Return>",
            lambda event: self.refresh_orders(),
        )

        tk.Label(
            search_frame,
            text="플랫폼",
            font=("맑은 고딕", 10),
        ).grid(
            row=0,
            column=2,
            padx=(0, 7),
            pady=5,
        )

        self.platform_combo = ttk.Combobox(
            search_frame,
            textvariable=self.platform_var,
            values=["전체", "쿠팡"],
            state="readonly",
            width=11,
        )
        self.platform_combo.grid(
            row=0,
            column=3,
            padx=(0, 15),
            pady=5,
        )

        tk.Label(
            search_frame,
            text="매핑",
            font=("맑은 고딕", 10),
        ).grid(
            row=0,
            column=4,
            padx=(0, 7),
            pady=5,
        )

        mapping_combo = ttk.Combobox(
            search_frame,
            textvariable=self.mapping_status_var,
            values=[
                "전체",
                "미매핑",
                "자동매핑",
                "수동매핑",
                "매핑완료",
                "매핑오류",
            ],
            state="readonly",
            width=11,
        )
        mapping_combo.grid(
            row=0,
            column=5,
            padx=(0, 15),
            pady=5,
        )

        tk.Label(
            search_frame,
            text="발주",
            font=("맑은 고딕", 10),
        ).grid(
            row=0,
            column=6,
            padx=(0, 7),
            pady=5,
        )

        purchase_combo = ttk.Combobox(
            search_frame,
            textvariable=self.purchase_status_var,
            values=[
                "전체",
                "발주대기",
                "발주준비",
                "발주완료",
                "발주취소",
            ],
            state="readonly",
            width=11,
        )
        purchase_combo.grid(
            row=0,
            column=7,
            padx=(0, 15),
            pady=5,
        )

        tk.Label(
            search_frame,
            text="배송",
            font=("맑은 고딕", 10),
        ).grid(
            row=0,
            column=8,
            padx=(0, 7),
            pady=5,
        )

        shipment_combo = ttk.Combobox(
            search_frame,
            textvariable=self.shipment_status_var,
            values=[
                "전체",
                "배송대기",
                "배송준비",
                "배송중",
                "배송완료",
                "배송취소",
            ],
            state="readonly",
            width=11,
        )
        shipment_combo.grid(
            row=0,
            column=9,
            padx=(0, 15),
            pady=5,
        )

        search_button = ttk.Button(
            search_frame,
            text="검색",
            command=self.refresh_orders,
            style="Primary.TButton",
        )
        search_button.grid(
            row=0,
            column=10,
            padx=(5, 5),
            pady=5,
        )

        reset_button = ttk.Button(
            search_frame,
            text="초기화",
            command=self.reset_filters,
            style="Toolbar.TButton",
        )
        reset_button.grid(
            row=0,
            column=11,
            padx=(5, 0),
            pady=5,
        )

        search_frame.grid_columnconfigure(
            1,
            weight=1,
        )

    def _create_action_area(self) -> None:
        action_frame = tk.Frame(
            self.window,
            padx=25,
            pady=5,
        )
        action_frame.pack(fill="x")

        left_frame = tk.Frame(action_frame)
        left_frame.pack(side="left")

        ttk.Button(
            left_frame,
            text="엑셀 불러오기",
            command=self.import_coupang_excel,
            style="Primary.TButton",
        ).pack(
            side="left",
            padx=(0, 8),
        )

        ttk.Button(
            left_frame,
            text="새로고침",
            command=self.refresh_orders,
            style="Toolbar.TButton",
        ).pack(
            side="left",
            padx=(0, 8),
        )

        ttk.Button(
            left_frame,
            text="자동매핑",
            command=self.auto_map_orders,
            style="Primary.TButton",
        ).pack(
            side="left",
            padx=(0, 8),
        )

        ttk.Button(
            left_frame,
            text="발주 생성",
            command=self.create_purchase_files,
            style="Primary.TButton",
        ).pack(
            side="left",
            padx=(0, 8),
        )

        right_frame = tk.Frame(action_frame)
        right_frame.pack(side="right")

        ttk.Button(
            right_frame,
            text="상세 보기",
            command=self.open_selected_order,
            style="Toolbar.TButton",
        ).pack(
            side="left",
            padx=(0, 8),
        )

        ttk.Button(
            right_frame,
            text="선택 주문 삭제",
            command=self.delete_selected_order,
            style="Toolbar.TButton",
        ).pack(side="left")

    # =========================================================
    # 주문 테이블
    # =========================================================

    def _create_order_table(self) -> None:
        table_frame = tk.Frame(
            self.window,
            padx=25,
            pady=10,
        )
        table_frame.pack(
            fill="both",
            expand=True,
        )

        columns = (
            "platform",
            "order_number",
            "ordered_at",
            "receiver_name",
            "item_summary",
            "total_quantity",
            "total_amount",
            "mapping_status",
            "purchase_status",
            "shipment_status",
        )

        self.order_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="Order.Treeview",
            selectmode="browse",
        )

        headings = {
            "platform": "플랫폼",
            "order_number": "주문번호",
            "ordered_at": "주문일시",
            "receiver_name": "수령인",
            "item_summary": "주문상품",
            "total_quantity": "수량",
            "total_amount": "결제금액",
            "mapping_status": "매핑",
            "purchase_status": "발주",
            "shipment_status": "배송",
        }

        widths = {
            "platform": 75,
            "order_number": 145,
            "ordered_at": 135,
            "receiver_name": 90,
            "item_summary": 400,
            "total_quantity": 60,
            "total_amount": 100,
            "mapping_status": 85,
            "purchase_status": 85,
            "shipment_status": 85,
        }

        anchors = {
            "platform": "center",
            "order_number": "center",
            "ordered_at": "center",
            "receiver_name": "center",
            "item_summary": "w",
            "total_quantity": "center",
            "total_amount": "e",
            "mapping_status": "center",
            "purchase_status": "center",
            "shipment_status": "center",
        }

        for column in columns:
            self.order_tree.heading(
                column,
                text=headings[column],
            )

            self.order_tree.column(
                column,
                width=widths[column],
                minwidth=50,
                anchor=anchors[column],
                stretch=(
                    column == "item_summary"
                ),
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

        self.order_tree.bind(
            "<Double-1>",
            lambda event: self.open_selected_order(),
        )

    def _create_status_bar(self) -> None:
        status_bar = tk.Label(
            self.window,
            textvariable=self.status_var,
            anchor="w",
            padx=15,
            pady=7,
            relief="sunken",
            borderwidth=1,
            font=("맑은 고딕", 9),
        )
        status_bar.pack(
            fill="x",
            side="bottom",
        )

    # =========================================================
    # 목록 조회
    # =========================================================

    def refresh_orders(self) -> None:
        try:
            keyword = (
                self.keyword_var.get().strip()
                or None
            )

            platform = self._filter_value(
                self.platform_var.get()
            )

            mapping_status = self._filter_value(
                self.mapping_status_var.get()
            )

            purchase_status = self._filter_value(
                self.purchase_status_var.get()
            )

            shipment_status = self._filter_value(
                self.shipment_status_var.get()
            )

            orders = self.repository.get_orders(
                keyword=keyword,
                platform=platform,
                mapping_status=mapping_status,
                purchase_status=purchase_status,
                shipment_status=shipment_status,
            )

            self._clear_order_table()
            self.order_rows.clear()

            for order in orders:
                item_id = str(order["id"])

                self.order_rows[item_id] = order

                self.order_tree.insert(
                    "",
                    "end",
                    iid=item_id,
                    values=(
                        self._display(
                            order.get("platform")
                        ),
                        self._display(
                            order.get(
                                "order_number"
                            )
                        ),
                        self._display(
                            order.get("ordered_at")
                        ),
                        self._display(
                            order.get(
                                "receiver_name"
                            )
                        ),
                        self._display(
                            order.get(
                                "item_summary"
                            )
                        ),
                        self._format_number(
                            order.get(
                                "total_quantity"
                            )
                        ),
                        self._format_currency(
                            order.get(
                                "total_amount"
                            )
                        ),
                        self._display(
                            order.get(
                                "mapping_status"
                            )
                        ),
                        self._display(
                            order.get(
                                "purchase_status"
                            )
                        ),
                        self._display(
                            order.get(
                                "shipment_status"
                            )
                        ),
                    ),
                )

            self._refresh_counts()

            self.status_var.set(
                f"주문 목록 조회 완료: {len(orders):,}건"
            )

        except Exception as error:
            self.status_var.set(
                "주문 목록 조회 오류"
            )

            messagebox.showerror(
                "조회 오류",
                "주문 목록을 불러오지 못했습니다.\n\n"
                f"{error}",
                parent=self.window,
            )

    def _refresh_counts(self) -> None:
        counts = (
            self.repository.get_order_counts()
        )

        self.total_count_var.set(
            "전체 주문 "
            f"{counts['total_count']:,}건"
        )

        self.today_count_var.set(
            "오늘 주문 "
            f"{counts['today_count']:,}건"
        )

        self.unmapped_count_var.set(
            "미매핑 "
            f"{counts['unmapped_count']:,}건"
        )

        self.purchase_waiting_var.set(
            "발주 대기 "
            f"{counts['purchase_waiting_count']:,}건"
        )

        self.shipping_count_var.set(
            "배송 진행 "
            f"{counts['shipping_count']:,}건"
        )

        platforms = (
            self.repository.get_platforms()
        )

        self.platform_combo.configure(
            values=["전체", *platforms]
        )

    def reset_filters(self) -> None:
        self.keyword_var.set("")
        self.platform_var.set("전체")
        self.mapping_status_var.set("전체")
        self.purchase_status_var.set("전체")
        self.shipment_status_var.set("전체")

        self.refresh_orders()

    # =========================================================
    # 자동 상품매핑
    # =========================================================

    def auto_map_orders(self) -> None:
        confirmed = messagebox.askyesno(
            "자동 상품매핑",
            "미매핑 주문상품을 상품관리 정보와 비교해\n"
            "자동으로 연결합니다.\n\n"
            "계속하시겠습니까?",
            parent=self.window,
        )

        if not confirmed:
            return

        try:
            self.status_var.set(
                "자동 상품매핑 실행 중..."
            )
            self.window.update_idletasks()

            result = (
                self.repository.auto_map_order_items()
            )

            self.refresh_orders()

            messagebox.showinfo(
                "자동매핑 완료",
                "자동 상품매핑이 완료되었습니다.\n\n"
                f"검사 대상: {result['target_count']:,}건\n"
                f"매핑 성공: {result['mapped_count']:,}건\n"
                f"일치 상품 없음: {result['unmatched_count']:,}건\n"
                f"중복 후보: {result['ambiguous_count']:,}건",
                parent=self.window,
            )

        except Exception as error:
            self.status_var.set(
                "자동 상품매핑 오류"
            )

            messagebox.showerror(
                "자동매핑 오류",
                "자동 상품매핑 중 오류가 발생했습니다.\n\n"
                f"{error}",
                parent=self.window,
            )

    # =========================================================
    # 주문 상세
    # =========================================================

    def open_selected_order(self) -> None:
        order_id = self._get_selected_order_id()

        if order_id is None:
            messagebox.showwarning(
                "주문 선택",
                "상세 내용을 볼 주문을 선택해주세요.",
                parent=self.window,
            )
            return

        try:
            order = (
                self.repository.get_order_by_id(
                    order_id
                )
            )

            if order is None:
                messagebox.showwarning(
                    "주문 없음",
                    "선택한 주문을 찾을 수 없습니다.",
                    parent=self.window,
                )
                self.refresh_orders()
                return

            OrderDetailWindow(
                self.window,
                order,
            )

        except Exception as error:
            messagebox.showerror(
                "상세 조회 오류",
                "주문 상세 내용을 불러오지 못했습니다.\n\n"
                f"{error}",
                parent=self.window,
            )

    # =========================================================
    # 주문 삭제
    # =========================================================

    def delete_selected_order(self) -> None:
        order_id = self._get_selected_order_id()

        if order_id is None:
            messagebox.showwarning(
                "주문 선택",
                "삭제할 주문을 선택해주세요.",
                parent=self.window,
            )
            return

        order = self.order_rows.get(
            str(order_id),
            {},
        )

        order_number = order.get(
            "order_number",
            order_id,
        )

        confirmed = messagebox.askyesno(
            "주문 삭제",
            f"주문번호 {order_number}을(를)\n"
            "정말 삭제하시겠습니까?\n\n"
            "주문상품 정보도 함께 삭제됩니다.",
            parent=self.window,
        )

        if not confirmed:
            return

        try:
            deleted_count = (
                self.repository.delete_order(
                    order_id
                )
            )

            if deleted_count:
                self.status_var.set(
                    f"주문 삭제 완료: {order_number}"
                )
            else:
                self.status_var.set(
                    "삭제할 주문을 찾지 못했습니다."
                )

            self.refresh_orders()

        except Exception as error:
            self.status_var.set(
                "주문 삭제 오류"
            )

            messagebox.showerror(
                "삭제 오류",
                "주문을 삭제하지 못했습니다.\n\n"
                f"{error}",
                parent=self.window,
            )

    # =========================================================
    # 준비 중 기능
    # =========================================================

    def import_coupang_excel(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self.window,
            title="쿠팡 주문 엑셀 선택",
            filetypes=[
                (
                    "엑셀 파일",
                    "*.xlsx *.xls",
                ),
                (
                    "모든 파일",
                    "*.*",
                ),
            ],
        )

        if not file_path:
            return

        confirmed = messagebox.askyesno(
            "쿠팡 주문 가져오기",
            "선택한 쿠팡 주문 엑셀을 불러옵니다.\n\n"
            "이미 등록된 주문번호는 자동으로 건너뜁니다.\n"
            "계속하시겠습니까?",
            parent=self.window,
        )

        if not confirmed:
            return

        try:
            self.status_var.set(
                "쿠팡 주문 엑셀 처리 중..."
            )
            self.window.update_idletasks()

            result = (
                self.import_service.import_coupang_excel(
                    file_path
                )
            )

            self.refresh_orders()

            message = (
                "쿠팡 주문 불러오기가 완료되었습니다.\n\n"
                f"파일명: {result['source_file']}\n"
                f"엑셀 행 수: {result['excel_row_count']:,}행\n"
                f"분석 주문: {result['parsed_order_count']:,}건\n"
                f"신규 등록: {result['created_count']:,}건\n"
                f"중복 건너뜀: {result['duplicate_count']:,}건\n"
                f"등록 실패: {result['failed_count']:,}건"
            )

            if result["errors"]:
                error_lines = []

                for error in result["errors"][:5]:
                    error_lines.append(
                        f"• {error.get('order_number') or error.get('row')}: "
                        f"{error.get('error')}"
                    )

                message += (
                    "\n\n오류 내용:\n"
                    + "\n".join(error_lines)
                )

                if len(result["errors"]) > 5:
                    message += (
                        "\n• 그 외 "
                        f"{len(result['errors']) - 5:,}건"
                    )

            self.status_var.set(
                "쿠팡 주문 불러오기 완료: "
                f"신규 {result['created_count']:,}건, "
                f"중복 {result['duplicate_count']:,}건"
            )

            messagebox.showinfo(
                "주문 불러오기 완료",
                message,
                parent=self.window,
            )

        except Exception as error:
            self.status_var.set(
                "쿠팡 주문 불러오기 오류"
            )

            messagebox.showerror(
                "엑셀 불러오기 오류",
                "쿠팡 주문 엑셀을 처리하지 못했습니다.\n\n"
                f"{error}",
                parent=self.window,
            )

    def create_purchase_files(self) -> None:
        confirmed = messagebox.askyesno(
            "공급처별 발주서 생성",
            "상품매핑과 공급처 연결이 완료된 주문상품을\n"
            "공급처별 엑셀 발주서로 생성합니다.\n\n"
            "이미 발주 생성된 상품은 자동으로 제외됩니다.\n"
            "계속하시겠습니까?",
            parent=self.window,
        )

        if not confirmed:
            return

        try:
            self.status_var.set(
                "공급처별 발주서 생성 중..."
            )
            self.window.update_idletasks()

            result = (
                self.purchase_service
                .create_purchase_files()
            )

            self.refresh_orders()

            if result["created_count"] == 0:
                self.status_var.set(
                    "발주 가능한 주문상품 없음"
                )

                messagebox.showwarning(
                    "발주 생성 결과",
                    "발주 가능한 주문상품이 없습니다.\n\n"
                    "먼저 상품관리에서 상품과 공급처를 등록한 뒤\n"
                    "주문관리에서 자동매핑을 실행해주세요.",
                    parent=self.window,
                )
                return

            file_lines = []

            for file_path in result["files"]:
                file_lines.append(
                    f"• {file_path}"
                )

            message = (
                "공급처별 발주서가 생성되었습니다.\n\n"
                f"발주 상품: {result['created_count']:,}건\n"
                f"공급처/차수: {result['supplier_count']:,}개\n"
                f"저장 위치:\n{result['output_directory']}\n\n"
                "생성 파일:\n"
                + "\n".join(file_lines)
            )

            self.status_var.set(
                "발주서 생성 완료: "
                f"{result['created_count']:,}건"
            )

            messagebox.showinfo(
                "발주서 생성 완료",
                message,
                parent=self.window,
            )

        except Exception as error:
            self.status_var.set(
                "발주서 생성 오류"
            )

            messagebox.showerror(
                "발주 생성 오류",
                "공급처별 발주서를 생성하지 못했습니다.\n\n"
                f"{error}",
                parent=self.window,
            )

    # =========================================================
    # 공통 함수
    # =========================================================

    def _get_selected_order_id(
        self,
    ) -> int | None:
        selection = (
            self.order_tree.selection()
        )

        if not selection:
            return None

        try:
            return int(selection[0])
        except (TypeError, ValueError):
            return None

    def _clear_order_table(self) -> None:
        children = (
            self.order_tree.get_children()
        )

        if children:
            self.order_tree.delete(*children)

    @staticmethod
    def _filter_value(
        value: str,
    ) -> str | None:
        cleaned_value = value.strip()

        if not cleaned_value:
            return None

        if cleaned_value == "전체":
            return None

        return cleaned_value

    @staticmethod
    def _display(
        value: Any,
    ) -> str:
        if value in (None, ""):
            return "-"

        return str(value)

    @staticmethod
    def _format_number(
        value: Any,
    ) -> str:
        try:
            return f"{int(value or 0):,}"
        except (TypeError, ValueError):
            return "0"

    @staticmethod
    def _format_currency(
        value: Any,
    ) -> str:
        try:
            return f"{int(value or 0):,}원"
        except (TypeError, ValueError):
            return "0원"


class OrderDetailWindow:
    """선택한 주문과 주문상품의 상세 내용을 표시합니다."""

    def __init__(
        self,
        parent: tk.Misc,
        order: dict[str, Any],
    ) -> None:
        self.order = order

        self.window = tk.Toplevel(parent)
        self.window.title(
            "주문 상세 - "
            f"{order.get('order_number', '')}"
        )
        self.window.geometry("1100x700")
        self.window.minsize(900, 600)
        self.window.transient(parent)

        self._create_ui()
        self.window.focus_force()

    def _create_ui(self) -> None:
        header = tk.Frame(
            self.window,
            padx=22,
            pady=18,
        )
        header.pack(fill="x")

        tk.Label(
            header,
            text="주문 상세",
            font=("맑은 고딕", 20, "bold"),
        ).pack(side="left")

        tk.Label(
            header,
            text=str(
                self.order.get(
                    "order_number",
                    "",
                )
            ),
            font=("맑은 고딕", 12),
        ).pack(
            side="left",
            padx=(15, 0),
            pady=(5, 0),
        )

        self._create_order_information()
        self._create_item_table()
        self._create_close_button()

    def _create_order_information(self) -> None:
        info_frame = tk.LabelFrame(
            self.window,
            text="배송 및 주문 정보",
            font=("맑은 고딕", 11, "bold"),
            padx=15,
            pady=12,
        )
        info_frame.pack(
            fill="x",
            padx=22,
            pady=(0, 12),
        )

        information = [
            (
                "플랫폼",
                self.order.get("platform"),
            ),
            (
                "주문일시",
                self.order.get("ordered_at"),
            ),
            (
                "수령인",
                self.order.get("receiver_name"),
            ),
            (
                "연락처",
                self.order.get("receiver_phone"),
            ),
            (
                "우편번호",
                self.order.get("postal_code"),
            ),
            (
                "주소",
                self._full_address(),
            ),
            (
                "배송메시지",
                self.order.get(
                    "delivery_message"
                ),
            ),
            (
                "결제금액",
                self._currency(
                    self.order.get(
                        "total_amount"
                    )
                ),
            ),
            (
                "매핑상태",
                self.order.get(
                    "mapping_status"
                ),
            ),
            (
                "발주상태",
                self.order.get(
                    "purchase_status"
                ),
            ),
            (
                "배송상태",
                self.order.get(
                    "shipment_status"
                ),
            ),
            (
                "원본파일",
                self.order.get("source_file"),
            ),
        ]

        for index, (
            label_text,
            value,
        ) in enumerate(information):
            row = index // 2
            pair = index % 2

            label_column = pair * 2
            value_column = label_column + 1

            tk.Label(
                info_frame,
                text=label_text,
                font=("맑은 고딕", 10, "bold"),
                anchor="w",
            ).grid(
                row=row,
                column=label_column,
                sticky="nw",
                padx=(0, 8),
                pady=5,
            )

            tk.Label(
                info_frame,
                text=self._display(value),
                font=("맑은 고딕", 10),
                anchor="w",
                justify="left",
                wraplength=380,
            ).grid(
                row=row,
                column=value_column,
                sticky="nw",
                padx=(0, 25),
                pady=5,
            )

        info_frame.grid_columnconfigure(
            1,
            weight=1,
        )
        info_frame.grid_columnconfigure(
            3,
            weight=1,
        )

    def _create_item_table(self) -> None:
        table_frame = tk.LabelFrame(
            self.window,
            text="주문상품",
            font=("맑은 고딕", 11, "bold"),
            padx=12,
            pady=12,
        )
        table_frame.pack(
            fill="both",
            expand=True,
            padx=22,
            pady=(0, 12),
        )

        columns = (
            "platform_product_name",
            "option_name",
            "quantity",
            "unit_price",
            "total_price",
            "product_name",
            "supplier_name",
            "mapping_status",
        )

        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        settings = {
            "platform_product_name": (
                "판매처 상품명",
                250,
                "w",
            ),
            "option_name": (
                "옵션",
                220,
                "w",
            ),
            "quantity": (
                "수량",
                55,
                "center",
            ),
            "unit_price": (
                "단가",
                85,
                "e",
            ),
            "total_price": (
                "합계",
                85,
                "e",
            ),
            "product_name": (
                "ERP 상품",
                150,
                "w",
            ),
            "supplier_name": (
                "공급처",
                100,
                "center",
            ),
            "mapping_status": (
                "매핑",
                80,
                "center",
            ),
        }

        for column in columns:
            heading, width, anchor = (
                settings[column]
            )

            tree.heading(
                column,
                text=heading,
            )
            tree.column(
                column,
                width=width,
                anchor=anchor,
            )

        for item in self.order.get(
            "items",
            [],
        ):
            tree.insert(
                "",
                "end",
                values=(
                    self._display(
                        item.get(
                            "platform_product_name"
                        )
                    ),
                    self._display(
                        item.get("option_name")
                    ),
                    self._number(
                        item.get("quantity")
                    ),
                    self._currency(
                        item.get("unit_price")
                    ),
                    self._currency(
                        item.get("total_price")
                    ),
                    self._display(
                        item.get("product_name")
                    ),
                    self._display(
                        item.get("supplier_name")
                    ),
                    self._display(
                        item.get(
                            "mapping_status"
                        )
                    ),
                ),
            )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=tree.yview,
        )

        tree.configure(
            yscrollcommand=scrollbar.set
        )

        tree.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

    def _create_close_button(self) -> None:
        button_frame = tk.Frame(
            self.window,
            padx=22,
            pady=(0, 18),
        )
        button_frame.pack(fill="x")

        ttk.Button(
            button_frame,
            text="닫기",
            command=self.window.destroy,
        ).pack(side="right")

    def _full_address(self) -> str:
        address = str(
            self.order.get("address") or ""
        ).strip()

        detail_address = str(
            self.order.get(
                "detail_address"
            ) or ""
        ).strip()

        return " ".join(
            value
            for value in (
                address,
                detail_address,
            )
            if value
        )

    @staticmethod
    def _display(
        value: Any,
    ) -> str:
        if value in (None, ""):
            return "-"

        return str(value)

    @staticmethod
    def _currency(
        value: Any,
    ) -> str:
        try:
            return f"{int(value or 0):,}원"
        except (TypeError, ValueError):
            return "0원"

    @staticmethod
    def _number(
        value: Any,
    ) -> str:
        try:
            return f"{int(value or 0):,}"
        except (TypeError, ValueError):
            return "0"