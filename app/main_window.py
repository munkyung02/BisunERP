from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.version import ERP_NAME, get_display_version
from modules.backup_manager.backup_page import BackupPage
from modules.backup_manager.backup_service import BackupService
from modules.dashboard.dashboard_page import DashboardPage
from modules.dashboard.dashboard_service import DashboardService
from modules.coupang.coupang_sync_page import CoupangSyncPage
from modules.coupang.coupang_scheduler import CoupangOrderScheduler
from modules.command_center.command_center_page import CommandCenterPage
from modules.erp_assistant.assistant_page import ERPAssistantPage
from modules.qa_automation.qa_page import QAAutomationPage
from modules.data_import.data_import_page import DataImportPage
from modules.integrity.integrity_page import IntegrityPage
from modules.mappings.mapping_page import MappingPage
from modules.notion_sync.notion_auto_sync_controller import NotionAutoSyncController
from modules.notion_sync.notion_sync_page import NotionSyncPage
from modules.operations_check.operations_check_page import OperationsCheckPage
from modules.orders.order_page import OrderPage
from modules.purchase_dashboard.purchase_dashboard_page import (
    PurchaseDashboardPage,
)
from modules.purchases.purchase_page import PurchasePage
from modules.search.global_search_page import GlobalSearchWindow
from modules.settings.settings_page import SettingsPage
from modules.settings.settings_service import SettingsService
from modules.shipments.shipment_page import ShipmentPage
from modules.work_center.work_center_page import WorkCenterPage


class MainWindow:
    """
    비선상회 ERP v1.0 메인 화면입니다.

    현재 업무 범위:
    주문 수집 → 상품 매핑 → 발주 → 송장 등록 → 종료
    """

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"{ERP_NAME} {get_display_version()}")
        self.root.geometry("1500x900")
        self.root.minsize(1180, 720)

        self.project_root = Path(__file__).resolve().parent.parent
        self.status_var = tk.StringVar(value="시스템 준비 완료")
        self.global_search_var = tk.StringVar()

        self.settings_service = SettingsService()
        self.dashboard_service = DashboardService()
        self.backup_service = BackupService()

        self.dashboard_page: DashboardPage | None = None
        self.command_center_page: CommandCenterPage | None = None
        self.erp_assistant_page: ERPAssistantPage | None = None
        self.qa_automation_page: QAAutomationPage | None = None
        self.purchase_dashboard_page: PurchaseDashboardPage | None = None
        self.data_import_page: DataImportPage | None = None
        self.operations_check_page: OperationsCheckPage | None = None
        self.integrity_page: IntegrityPage | None = None
        self.backup_page: BackupPage | None = None
        self.settings_page: SettingsPage | None = None
        self.notion_sync_page: NotionSyncPage | None = None
        self.coupang_sync_page: CoupangSyncPage | None = None
        self.work_center_page: WorkCenterPage | None = None

        self.menu_buttons: dict[str, ttk.Button] = {}

        self.notion_auto_sync_controller: NotionAutoSyncController | None = None
        self.coupang_order_scheduler: CoupangOrderScheduler | None = None

        self._configure_style()
        self._create_ui()
        self._run_startup_backup()
        self._start_notion_auto_sync()
        self._start_coupang_order_scheduler()

    def _configure_style(self) -> None:
        style = ttk.Style()

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Menu.TButton",
            font=("맑은 고딕", 11),
            padding=(12, 8),
        )
        style.configure(
            "Action.TButton",
            font=("맑은 고딕", 11, "bold"),
            padding=(12, 10),
        )

    def _create_ui(self) -> None:
        header = tk.Frame(self.root, padx=25, pady=15)
        header.pack(fill="x")

        tk.Label(
            header,
            text=ERP_NAME,
            font=("맑은 고딕", 25, "bold"),
        ).pack(side="left")

        tk.Label(
            header,
            text=get_display_version(),
            font=("맑은 고딕", 11),
        ).pack(
            side="left",
            padx=(10, 0),
            pady=(10, 0),
        )

        search_box = ttk.Frame(header)
        search_box.pack(side="right")

        search_entry = ttk.Entry(
            search_box,
            textvariable=self.global_search_var,
            width=32,
        )
        search_entry.pack(
            side="left",
            padx=(0, 6),
            ipady=4,
        )
        search_entry.bind(
            "<Return>",
            lambda _event: self.open_global_search(),
        )

        ttk.Button(
            search_box,
            text="통합검색",
            command=self.open_global_search,
        ).pack(side="left")

        ttk.Separator(
            self.root,
            orient="horizontal",
        ).pack(fill="x")

        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True)

        self._create_sidebar(body)
        self._create_content(body)
        self._create_status_bar()

    def _create_sidebar(self, parent: tk.Widget) -> None:
        sidebar_shell = tk.Frame(
            parent,
            width=225,
            relief="groove",
            borderwidth=1,
        )
        sidebar_shell.pack(side="left", fill="y")
        sidebar_shell.pack_propagate(False)

        sidebar_canvas = tk.Canvas(
            sidebar_shell,
            width=205,
            highlightthickness=0,
            borderwidth=0,
        )
        sidebar_scrollbar = ttk.Scrollbar(
            sidebar_shell,
            orient="vertical",
            command=sidebar_canvas.yview,
        )
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)

        sidebar_scrollbar.pack(side="right", fill="y")
        sidebar_canvas.pack(side="left", fill="both", expand=True)

        sidebar = tk.Frame(
            sidebar_canvas,
            padx=12,
            pady=14,
        )
        sidebar_window = sidebar_canvas.create_window(
            (0, 0),
            window=sidebar,
            anchor="nw",
        )

        def update_scroll_region(_event=None) -> None:
            sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all"))

        def fit_sidebar_width(event) -> None:
            sidebar_canvas.itemconfigure(
                sidebar_window,
                width=max(event.width, 1),
            )

        def on_mousewheel(event) -> None:
            if event.delta:
                sidebar_canvas.yview_scroll(int(-event.delta / 120), "units")

        sidebar.bind("<Configure>", update_scroll_region)
        sidebar_canvas.bind("<Configure>", fit_sidebar_width)
        sidebar_canvas.bind("<Enter>", lambda _e: sidebar_canvas.bind_all("<MouseWheel>", on_mousewheel))
        sidebar_canvas.bind("<Leave>", lambda _e: sidebar_canvas.unbind_all("<MouseWheel>"))

        tk.Label(
            sidebar,
            text="ERP 메뉴",
            font=("맑은 고딕", 14, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        core_menus = [
            ("Dashboard", self.show_dashboard),
            ("Command Center", self.show_command_center),
            ("ERP 도우미", self.show_erp_assistant),
            ("작업센터", self.show_work_center),
            ("주문관리", self.open_orders),
            ("상품관리", self.open_products),
            ("상품매핑", self.open_mappings),
            ("공급처관리", self.open_suppliers),
            ("발주관리", self.open_purchases),
            ("송장관리", self.open_shipments),
        ]

        support_menus = [
            ("시스템 진단", self.show_qa_automation),
            ("일괄등록", self.show_data_import),
            ("구매통계", self.show_purchase_dashboard),
            ("실무점검", self.show_operations_check),
            ("데이터점검", self.show_integrity),
            ("백업 및 복원", self.show_backup),
            ("환경설정", self.show_settings),
            ("노션 동기화", self.show_notion_sync),
            ("쿠팡 주문동기화", self.show_coupang_sync),
        ]

        for menu_name, command in core_menus:
            self._add_menu_button(sidebar, menu_name, command)

        ttk.Separator(
            sidebar,
            orient="horizontal",
        ).pack(fill="x", pady=(10, 8))

        tk.Label(
            sidebar,
            text="관리 도구",
            font=("맑은 고딕", 11, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        for menu_name, command in support_menus:
            self._add_menu_button(sidebar, menu_name, command)

        ttk.Separator(
            sidebar,
            orient="horizontal",
        ).pack(fill="x", pady=(12, 8))

        self.root.after(500, self.refresh_menu_badges)

    def _add_menu_button(
        self,
        parent: tk.Widget,
        menu_name: str,
        command,
    ) -> None:
        button = ttk.Button(
            parent,
            text=menu_name,
            command=command,
            style="Menu.TButton",
        )
        button.pack(fill="x", pady=3)
        self.menu_buttons[menu_name] = button

    def _create_content(self, parent: tk.Widget) -> None:
        self.content_frame = ttk.Frame(parent)
        self.content_frame.pack(
            side="left",
            fill="both",
            expand=True,
        )
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)

        self.dashboard_page = DashboardPage(
            self.content_frame,
            status_callback=self.status_var.set,
            order_action=self.open_orders,
            mapping_action=self.open_mappings,
            purchase_action=self.open_purchases,
            shipment_action=self.open_shipments,
            delivery_action=self.open_shipments,
        )
        self.dashboard_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.command_center_page = CommandCenterPage(
            self.content_frame,
            status_callback=self.status_var.set,
            order_sync_action=self.show_coupang_sync,
            validation_action=self.show_operations_check,
            purchase_action=self.open_purchases,
            shipment_action=self.open_shipments,
        )
        self.command_center_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.erp_assistant_page = ERPAssistantPage(
            self.content_frame,
            status_callback=self.status_var.set,
        )
        self.erp_assistant_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.qa_automation_page = QAAutomationPage(
            self.content_frame,
            status_callback=self.status_var.set,
        )
        self.qa_automation_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.purchase_dashboard_page = PurchaseDashboardPage(
            self.content_frame
        )
        self.purchase_dashboard_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.data_import_page = DataImportPage(
            self.content_frame
        )
        self.data_import_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.operations_check_page = OperationsCheckPage(
            self.content_frame,
            status_callback=self.status_var.set,
            navigate_callback=self.navigate_to_menu,
        )
        self.operations_check_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.integrity_page = IntegrityPage(
            self.content_frame,
            status_callback=self.status_var.set,
            refresh_callback=self._refresh_dashboard_and_badges,
        )
        self.integrity_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.backup_page = BackupPage(
            self.content_frame,
            backup_service=self.backup_service,
        )
        self.backup_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.settings_page = SettingsPage(
            self.content_frame,
            status_callback=self.status_var.set,
            settings_service=self.settings_service,
        )
        self.settings_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.notion_sync_page = NotionSyncPage(
            self.content_frame,
            status_callback=self.status_var.set,
        )
        self.notion_sync_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.coupang_sync_page = CoupangSyncPage(
            self.content_frame,
            status_callback=self.status_var.set,
            settings_service=self.settings_service,
        )
        self.coupang_sync_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.work_center_page = WorkCenterPage(
            self.content_frame,
            navigate_callback=self.navigate_to_menu,
            status_callback=self.status_var.set,
        )
        self.work_center_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.dashboard_page.tkraise()

    def show_dashboard(self) -> None:
        if self.dashboard_page is None:
            return

        self.dashboard_page.tkraise()
        self.dashboard_page.refresh_dashboard()
        self.status_var.set("Dashboard 화면")
        self.refresh_menu_badges()

    def show_command_center(self) -> None:
        if self.command_center_page is None:
            return

        self.command_center_page.tkraise()
        self.command_center_page.refresh_data()
        self.status_var.set("ERP Command Center 화면")

    def show_erp_assistant(self) -> None:
        if self.erp_assistant_page is None:
            return

        self.erp_assistant_page.tkraise()
        self.erp_assistant_page.focus_question()
        self.status_var.set("ERP 도우미 화면")

    def show_qa_automation(self) -> None:
        if self.qa_automation_page is None:
            return

        self.qa_automation_page.tkraise()
        self.qa_automation_page.refresh_data()
        self.status_var.set("QA Automation Center 화면")

    def show_work_center(self) -> None:
        if self.work_center_page is None:
            return

        self.work_center_page.tkraise()
        self.work_center_page.refresh_data()
        self.status_var.set("작업센터 화면")

    def show_purchase_dashboard(self) -> None:
        if self.purchase_dashboard_page is None:
            return

        self.purchase_dashboard_page.tkraise()
        self.purchase_dashboard_page.refresh()
        self.status_var.set("구매통계 화면")

    def show_data_import(self) -> None:
        if self.data_import_page is None:
            return

        self.data_import_page.tkraise()
        self.status_var.set("상품·공급처 일괄등록 화면")

    def show_operations_check(self) -> None:
        if self.operations_check_page is None:
            return

        self.operations_check_page.tkraise()
        self.operations_check_page.refresh_data()
        self.status_var.set("실무 운영 점검 화면")

    def show_integrity(self) -> None:
        if self.integrity_page is None:
            return

        self.integrity_page.tkraise()
        self.integrity_page.refresh_data()
        self.status_var.set("데이터 점검·복구센터 화면")

    def show_backup(self) -> None:
        if self.backup_page is None:
            return

        self.backup_page.tkraise()
        self.backup_page.refresh()
        self.status_var.set("백업 및 복원 화면")

    def show_settings(self) -> None:
        if self.settings_page is None:
            return

        self.settings_page.tkraise()
        self.settings_page.refresh_data()
        self.status_var.set("환경설정 화면")

    def show_notion_sync(self) -> None:
        if self.notion_sync_page is None:
            return

        self.notion_sync_page.tkraise()
        self.notion_sync_page.refresh_data()
        self.status_var.set("노션 동기화 화면")

    def show_coupang_sync(self) -> None:
        if self.coupang_sync_page is None:
            return

        self.coupang_sync_page.tkraise()
        self.coupang_sync_page.refresh_data()
        self.status_var.set("쿠팡 주문동기화 화면")

    def navigate_to_menu(self, target: str) -> None:
        actions = {
            "Command Center": self.show_command_center,
            "ERP 도우미": self.show_erp_assistant,
            "시스템 진단": self.show_qa_automation,
            "작업센터": self.show_work_center,
            "주문관리": self.open_orders,
            "상품관리": self.open_products,
            "상품매핑": self.open_mappings,
            "공급처관리": self.open_suppliers,
            "발주관리": self.open_purchases,
            "송장관리": self.open_shipments,
            "일괄등록": self.show_data_import,
            "구매통계": self.show_purchase_dashboard,
            "데이터점검": self.show_integrity,
            "백업 및 복원": self.show_backup,
            "환경설정": self.show_settings,
            "노션 동기화": self.show_notion_sync,
            "쿠팡 주문동기화": self.show_coupang_sync,
        }

        action = actions.get(target)

        if action is not None:
            action()
            return

        self.status_var.set(
            f"현재 v1.0 범위에 없는 메뉴입니다: {target}"
        )

    def _refresh_dashboard_and_badges(self) -> None:
        if self.dashboard_page is not None:
            self.dashboard_page.refresh_dashboard()

        self.refresh_menu_badges()

    def open_global_search(self) -> None:
        GlobalSearchWindow(
            self.root,
            initial_keyword=self.global_search_var.get(),
            status_callback=self.status_var.set,
        )

    def refresh_menu_badges(self) -> None:
        try:
            summary = (
                self.dashboard_service
                .get_dashboard_data()
                .get("summary", {})
            )

            labels = {
                "상품매핑": int(
                    summary.get("unmapped", 0) or 0
                ),
                "발주관리": int(
                    summary.get("purchase_waiting", 0) or 0
                ),
                "송장관리": int(
                    summary.get("shipment_waiting", 0) or 0
                ),
            }

            for name, count in labels.items():
                button = self.menu_buttons.get(name)

                if button is not None:
                    button.configure(
                        text=(
                            f"{name} ({count:,})"
                            if count
                            else name
                        )
                    )

        except Exception:
            pass

        self.root.after(
            60000,
            self.refresh_menu_badges,
        )

    def _create_status_bar(self) -> None:
        tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            padx=15,
            pady=7,
            relief="sunken",
            borderwidth=1,
            font=("맑은 고딕", 9),
        ).pack(
            fill="x",
            side="bottom",
        )

    def open_orders(self) -> None:
        try:
            OrderPage(self.root)
            self.status_var.set("주문관리 화면 실행")
        except Exception as error:
            self._show_open_error(
                "주문관리",
                error,
            )

    def open_mappings(self) -> None:
        try:
            window = tk.Toplevel(self.root)
            window.title("비선상회 ERP - 상품매핑")
            window.geometry("1500x820")
            window.minsize(1150, 650)

            page = MappingPage(window)
            page.pack(fill="both", expand=True)

            window.transient(self.root)
            window.focus_force()
            self.status_var.set("상품매핑 화면 실행")

        except Exception as error:
            self._show_open_error(
                "상품매핑",
                error,
            )

    def open_purchases(self) -> None:
        try:
            window = tk.Toplevel(self.root)
            window.title("비선상회 ERP - 발주관리")
            window.geometry("1400x800")
            window.minsize(1100, 650)

            page = PurchasePage(window)
            page.pack(fill="both", expand=True)

            window.transient(self.root)
            window.focus_force()
            self.status_var.set("발주관리 화면 실행")

        except Exception as error:
            self._show_open_error(
                "발주관리",
                error,
            )

    def open_shipments(self) -> None:
        try:
            window = tk.Toplevel(self.root)
            window.title("비선상회 ERP - 송장관리")
            window.geometry("1450x820")
            window.minsize(1100, 650)

            page = ShipmentPage(window)
            page.pack(fill="both", expand=True)

            window.transient(self.root)
            window.focus_force()
            self.status_var.set("송장관리 화면 실행")

        except Exception as error:
            self._show_open_error(
                "송장관리",
                error,
            )

    def open_products(self) -> None:
        self._open_module_process(
            module_name="modules.products.product_runner",
            display_name="상품관리",
        )

    def open_suppliers(self) -> None:
        self._open_module_process(
            module_name="modules.suppliers.supplier_runner",
            display_name="공급처관리",
        )

    def _open_module_process(
        self,
        *,
        module_name: str,
        display_name: str,
    ) -> None:
        try:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    module_name,
                ],
                cwd=self.project_root,
            )
            self.status_var.set(
                f"{display_name} 화면 실행"
            )

        except Exception as error:
            self._show_open_error(
                display_name,
                error,
            )

    def _run_startup_backup(self) -> None:
        def run_backup() -> None:
            try:
                result = (
                    self.backup_service
                    .create_startup_backup()
                )

                if result:
                    self.status_var.set(
                        "시작 시 자동 백업 완료"
                    )

            except Exception as error:
                self.status_var.set(
                    f"자동 백업 실패: {error}"
                )

        self.root.after(800, run_backup)

    def _start_notion_auto_sync(self) -> None:
        """
        MainWindow 생성이 끝난 뒤 Notion 자동동기화를 연결합니다.

        자동동기화 자체는 백그라운드 스레드에서 실행되므로
        ERP 화면을 멈추지 않습니다. 연결 실패가 발생해도
        메인 프로그램은 계속 실행됩니다.
        """
        try:
            self.notion_auto_sync_controller = (
                NotionAutoSyncController(
                    self,
                    settings_service=self.settings_service,
                )
            )
            self.notion_auto_sync_controller.start()

        except Exception as error:
            self.notion_auto_sync_controller = None
            self.status_var.set(
                f"Notion 자동동기화 시작 실패: {error}"
            )

    def _start_coupang_order_scheduler(self) -> None:
        """환경설정 주기에 따라 쿠팡 신규주문을 자동 수집합니다."""
        try:
            self.coupang_order_scheduler = CoupangOrderScheduler(
                self.root,
                settings_service=self.settings_service,
                status_callback=self.status_var.set,
                refresh_callback=self._refresh_dashboard_and_badges,
            )
            self.coupang_order_scheduler.start()
        except Exception as error:
            self.coupang_order_scheduler = None
            self.status_var.set(
                f"쿠팡 주문 자동수집 시작 실패: {error}"
            )

    def _show_open_error(
        self,
        display_name: str,
        error: Exception,
    ) -> None:
        self.status_var.set(
            f"{display_name} 실행 오류"
        )
        messagebox.showerror(
            f"{display_name} 실행 오류",
            (
                f"{display_name} 화면을 열지 못했습니다.\n\n"
                f"{error}"
            ),
            parent=self.root,
        )

    def run(self) -> None:
        self.root.mainloop()
