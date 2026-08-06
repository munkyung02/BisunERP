import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from modules.orders.order_import_center import OrderImportCenter
from modules.orders.order_import_service import OrderImportService
from modules.orders.order_repository import OrderRepository
from modules.order_validation.page import OrderValidationPage
from modules.order_validation.service import OrderValidationService
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
        self.validation_service = OrderValidationService(self.repository)

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
            value="송장 등록 0건"
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
                "판매채널 주문을 통합 조회하고 상품매핑·발주·송장등록 상태를 "
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
            text="송장",
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
                "송장대기",
                "송장등록완료",
                "배송대기",
                "배송중",
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
            text="주문 가져오기",
            command=self.open_order_import_center,
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
            text="주문 검수",
            command=self.open_order_validation,
            style="Primary.TButton",
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
            "shipment_status": "송장",
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
                        self._shipment_display(
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
            "송장 등록 "
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
    # 주문 검수
    # =========================================================

    def open_order_validation(self) -> None:
        try:
            window = tk.Toplevel(self.window)
            window.title("비선상회 ERP - 주문 검수")
            window.geometry("1200x760")
            window.minsize(950, 620)

            page = OrderValidationPage(
                window,
                service=self.validation_service,
            )
            page.pack(fill="both", expand=True)

            window.transient(self.window)
            window.focus_force()
            self.status_var.set("주문 검수 화면 실행")

        except Exception as error:
            self.status_var.set("주문 검수 실행 오류")
            messagebox.showerror(
                "주문 검수 오류",
                f"주문 검수 화면을 열지 못했습니다.\n\n{error}",
                parent=self.window,
            )

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

    def open_order_import_center(self) -> None:
        """여러 판매채널 주문서를 통합 가져오는 화면을 엽니다."""

        try:
            OrderImportCenter(
                parent=self.window,
                service=self.import_service,
                refresh_callback=self.refresh_orders,
            )

            self.status_var.set(
                "주문 가져오기 센터 실행"
            )

        except Exception as error:
            self.status_var.set(
                "주문 가져오기 센터 실행 오류"
            )

            messagebox.showerror(
                "주문 가져오기 오류",
                "주문 가져오기 센터를 열지 못했습니다.\n\n"
                f"{error}",
                parent=self.window,
            )

    def create_purchase_files(self) -> None:
        try:
            validation_summary = self.validation_service.get_summary()
            fail_count = int(validation_summary.get("fail_count", 0) or 0)
            warning_count = int(validation_summary.get("warning_count", 0) or 0)

            if fail_count:
                messagebox.showerror(
                    "발주 전 주문 검수 필요",
                    (
                        f"처리 불가 주문이 {fail_count:,}건 있습니다.\n\n"
                        "상품 미매핑 또는 공급처 미연결 항목을 먼저 해결한 뒤 "
                        "발주서를 생성해주세요.\n\n"
                        "[주문 검수] 버튼에서 주문별 오류를 확인할 수 있습니다."
                    ),
                    parent=self.window,
                )
                self.open_order_validation()
                return

            if warning_count:
                proceed = messagebox.askyesno(
                    "확인 필요 주문 존재",
                    (
                        f"확인이 필요한 주문이 {warning_count:,}건 있습니다.\n\n"
                        "수량 이상·옵션 없음·중복 가능성을 확인하지 않고 "
                        "발주 생성을 계속하시겠습니까?"
                    ),
                    parent=self.window,
                )
                if not proceed:
                    self.open_order_validation()
                    return

        except Exception as error:
            messagebox.showerror(
                "주문 검수 오류",
                f"발주 전 주문 검수를 완료하지 못했습니다.\n\n{error}",
                parent=self.window,
            )
            return

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
    def _shipment_display(
        value: Any,
    ) -> str:
        """기존 배송 상태를 송장 업무 기준으로 표시합니다."""

        status = str(value or "").strip()

        if status in {
            "송장등록완료",
            "배송중",
            "배송완료",
        }:
            return "송장등록완료"

        return "송장대기"

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
    """
    주문부터 송장등록까지 한 화면에서 확인하는 주문 상세창입니다.

    업무 흐름:
    주문접수 → 상품매핑 → 발주 → 송장등록완료
    """

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
        self.window.geometry("1450x780")
        self.window.minsize(1100, 650)
        self.window.transient(parent)

        self._configure_style()
        self._create_ui()

        self.window.focus_force()

    def _configure_style(self) -> None:
        style = ttk.Style(self.window)

        style.configure(
            "Detail.Treeview",
            font=("맑은 고딕", 9),
            rowheight=31,
        )
        style.configure(
            "Detail.Treeview.Heading",
            font=("맑은 고딕", 9, "bold"),
        )
        style.configure(
            "Workflow.TLabel",
            font=("맑은 고딕", 11, "bold"),
            padding=(12, 7),
        )

    def _create_ui(self) -> None:
        self._create_header()
        self._create_workflow()
        self._create_order_information()
        self._create_item_table()
        self._create_close_button()

    # =========================================================
    # 상단
    # =========================================================

    def _create_header(self) -> None:
        header = tk.Frame(
            self.window,
            padx=22,
            pady=16,
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

        workflow_status = self._display(
            self.order.get(
                "workflow_status"
            )
        )

        tk.Label(
            header,
            text=f"현재 단계: {workflow_status}",
            font=("맑은 고딕", 12, "bold"),
            padx=12,
            pady=6,
            relief="ridge",
            borderwidth=1,
        ).pack(side="right")

    # =========================================================
    # 업무 진행 단계
    # =========================================================

    def _create_workflow(self) -> None:
        outer = tk.LabelFrame(
            self.window,
            text="업무 진행",
            font=("맑은 고딕", 11, "bold"),
            padx=12,
            pady=10,
        )
        outer.pack(
            fill="x",
            padx=22,
            pady=(0, 10),
        )

        current_index = self._workflow_index()

        steps = (
            "주문접수",
            "상품매핑",
            "발주완료",
            "송장등록완료",
        )

        for index, title in enumerate(steps):
            completed = index <= current_index

            text = (
                f"✓ {title}"
                if completed
                else title
            )

            label = ttk.Label(
                outer,
                text=text,
                style="Workflow.TLabel",
                relief="ridge",
                anchor="center",
            )
            label.grid(
                row=0,
                column=index * 2,
                sticky="ew",
            )

            outer.grid_columnconfigure(
                index * 2,
                weight=1,
            )

            if index < len(steps) - 1:
                ttk.Label(
                    outer,
                    text="→",
                    font=("맑은 고딕", 13, "bold"),
                ).grid(
                    row=0,
                    column=index * 2 + 1,
                    padx=8,
                )

    def _workflow_index(self) -> int:
        status = str(
            self.order.get(
                "workflow_status"
            )
            or ""
        ).strip()

        mapping = {
            "주문접수": 0,
            "상품매핑대기": 0,
            "발주대기": 1,
            "송장대기": 2,
            "송장등록완료": 3,
        }

        return mapping.get(
            status,
            0,
        )

    # =========================================================
    # 주문 정보
    # =========================================================

    def _create_order_information(self) -> None:
        info_frame = tk.LabelFrame(
            self.window,
            text="주문 및 수령 정보",
            font=("맑은 고딕", 11, "bold"),
            padx=15,
            pady=10,
        )
        info_frame.pack(
            fill="x",
            padx=22,
            pady=(0, 10),
        )

        information = (
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
        )

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
                pady=4,
            )

            tk.Label(
                info_frame,
                text=self._display(value),
                font=("맑은 고딕", 10),
                anchor="w",
                justify="left",
                wraplength=500,
            ).grid(
                row=row,
                column=value_column,
                sticky="nw",
                padx=(0, 25),
                pady=4,
            )

        info_frame.grid_columnconfigure(
            1,
            weight=1,
        )
        info_frame.grid_columnconfigure(
            3,
            weight=1,
        )

    # =========================================================
    # 상품별 매핑·발주·송장
    # =========================================================

    def _create_item_table(self) -> None:
        table_frame = tk.LabelFrame(
            self.window,
            text="상품별 처리 현황",
            font=("맑은 고딕", 11, "bold"),
            padx=12,
            pady=12,
        )
        table_frame.pack(
            fill="both",
            expand=True,
            padx=22,
            pady=(0, 10),
        )

        columns = (
            "platform_product",
            "mapped_product",
            "supplier",
            "quantity",
            "mapping_status",
            "purchase_status",
            "courier",
            "tracking_number",
            "tracking_registered_at",
            "tracking_status",
        )

        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="Detail.Treeview",
        )

        headings = {
            "platform_product": "판매처 상품",
            "mapped_product": "매핑 상품",
            "supplier": "공급처",
            "quantity": "수량",
            "mapping_status": "매핑",
            "purchase_status": "발주",
            "courier": "택배사",
            "tracking_number": "송장번호",
            "tracking_registered_at": "송장등록일",
            "tracking_status": "최종 상태",
        }

        widths = {
            "platform_product": 275,
            "mapped_product": 210,
            "supplier": 120,
            "quantity": 55,
            "mapping_status": 85,
            "purchase_status": 85,
            "courier": 90,
            "tracking_number": 150,
            "tracking_registered_at": 145,
            "tracking_status": 105,
        }

        centered = {
            "supplier",
            "quantity",
            "mapping_status",
            "purchase_status",
            "courier",
            "tracking_registered_at",
            "tracking_status",
        }

        for column in columns:
            tree.heading(
                column,
                text=headings[column],
            )
            tree.column(
                column,
                width=widths[column],
                minwidth=50,
                anchor=(
                    "center"
                    if column in centered
                    else "w"
                ),
                stretch=column in {
                    "platform_product",
                    "mapped_product",
                },
            )

        vertical_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=tree.yview,
        )
        horizontal_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=tree.xview,
        )

        tree.configure(
            yscrollcommand=vertical_scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set,
        )

        tree.grid(
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

        for item in self.order.get(
            "items",
            [],
        ):
            platform_product = self._combine(
                item.get(
                    "platform_product_name"
                ),
                item.get("option_name"),
            )

            mapped_product = self._combine(
                item.get("product_name"),
                item.get(
                    "supplier_product_name"
                ),
            )

            tree.insert(
                "",
                "end",
                values=(
                    platform_product,
                    mapped_product,
                    self._display(
                        item.get(
                            "supplier_name"
                        )
                    ),
                    self._number(
                        item.get("quantity")
                    ),
                    self._display(
                        item.get(
                            "mapping_status"
                        )
                    ),
                    self._display(
                        item.get(
                            "display_purchase_status"
                        )
                    ),
                    self._display(
                        item.get(
                            "courier_name"
                        )
                    ),
                    self._display(
                        item.get(
                            "tracking_number"
                        )
                    ),
                    self._display(
                        item.get(
                            "tracking_registered_at"
                        )
                        or item.get(
                            "shipment_created_at"
                        )
                    ),
                    self._display(
                        item.get(
                            "tracking_status"
                        )
                    ),
                ),
            )

    # =========================================================
    # 하단
    # =========================================================

    def _create_close_button(self) -> None:
        button_frame = tk.Frame(
            self.window,
            padx=22,
            pady=(0, 15),
        )
        button_frame.pack(fill="x")

        tk.Label(
            button_frame,
            text=(
                "비선상회 ERP의 처리는 송장등록완료에서 종료됩니다."
            ),
            font=("맑은 고딕", 9),
        ).pack(side="left")

        ttk.Button(
            button_frame,
            text="닫기",
            command=self.window.destroy,
        ).pack(side="right")

    # =========================================================
    # 공통
    # =========================================================

    def _full_address(self) -> str:
        values = [
            self.order.get("address"),
            self.order.get("detail_address"),
        ]

        return " ".join(
            str(value).strip()
            for value in values
            if value not in (
                None,
                "",
            )
        )

    @staticmethod
    def _combine(
        first: Any,
        second: Any,
    ) -> str:
        values = [
            str(value).strip()
            for value in (
                first,
                second,
            )
            if value not in (
                None,
                "",
            )
            and str(value).strip()
        ]

        return " / ".join(values) or "-"

    @staticmethod
    def _display(
        value: Any,
    ) -> str:
        if value in (
            None,
            "",
        ):
            return "-"

        return str(value)

    @staticmethod
    def _currency(
        value: Any,
    ) -> str:
        try:
            return f"{int(value or 0):,}원"
        except (
            TypeError,
            ValueError,
        ):
            return "0원"

    @staticmethod
    def _number(
        value: Any,
    ) -> str:
        try:
            return f"{int(value or 0):,}"
        except (
            TypeError,
            ValueError,
        ):
            return "0"