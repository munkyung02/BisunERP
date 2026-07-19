import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from legacy_order_runner import main as run_legacy_order
from modules.dashboard.dashboard_page import DashboardPage
from modules.mappings.mapping_page import MappingPage
from modules.orders.order_page import OrderPage
from modules.purchases.purchase_page import PurchasePage
from modules.shipments.shipment_page import ShipmentPage
from modules.search.global_search_page import GlobalSearchWindow
from modules.dashboard.dashboard_service import DashboardService
from modules.automation.automation_page import AutomationPage
from modules.settlements.settlement_page import SettlementPage
from modules.management.management_page import ManagementPage


class MainWindow:
    """비선상회 ERP 메인 화면입니다."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("비선상회 ERP v1.5")
        self.root.geometry("1500x900")
        self.root.minsize(1180, 720)

        self.project_root = Path(__file__).resolve().parent.parent
        self.status_var = tk.StringVar(value="시스템 준비 완료")
        self.dashboard_page: DashboardPage | None = None
        self.automation_page: AutomationPage | None = None
        self.settlement_page: SettlementPage | None = None
        self.management_page: ManagementPage | None = None
        self.dashboard_service = DashboardService()
        self.menu_buttons: dict[str, ttk.Button] = {}

        self._configure_style()
        self._create_ui()

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Menu.TButton",
            font=("맑은 고딕", 11),
            padding=(12, 11),
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
            text="비선상회 ERP",
            font=("맑은 고딕", 25, "bold"),
        ).pack(side="left")

        tk.Label(
            header,
            text="v1.5",
            font=("맑은 고딕", 11),
        ).pack(side="left", padx=(10, 0), pady=(10, 0))

        search_box = ttk.Frame(header)
        search_box.pack(side="right")
        self.global_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_box, textvariable=self.global_search_var, width=32)
        search_entry.pack(side="left", padx=(0, 6), ipady=4)
        search_entry.bind("<Return>", lambda _event: self.open_global_search())
        ttk.Button(search_box, text="통합검색", command=self.open_global_search).pack(side="left")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x")

        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True)

        self._create_sidebar(body)
        self._create_content(body)
        self._create_status_bar()

    def _create_sidebar(self, parent: tk.Widget) -> None:
        sidebar = tk.Frame(
            parent,
            width=225,
            padx=16,
            pady=20,
            relief="groove",
            borderwidth=1,
        )
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="ERP 메뉴",
            font=("맑은 고딕", 14, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        menus = [
            ("Dashboard", self.show_dashboard),
            ("주문관리", self.open_orders),
            ("상품관리", self.open_products),
            ("상품매핑", self.open_mappings),
            ("공급처관리", self.open_suppliers),
            ("거래처관리", self.show_preparing),
            ("발주관리", self.open_purchases),
            ("입금관리", self.show_preparing),
            ("송장관리", self.open_shipments),
            ("자동화센터", self.show_automation),
            ("정산센터", self.show_settlement),
            ("경영현황", self.show_management),
            ("통계", self.show_preparing),
            ("환경설정", self.show_preparing),
        ]

        for menu_name, command in menus:
            button = ttk.Button(
                sidebar,
                text=menu_name,
                command=command,
                style="Menu.TButton",
            )
            button.pack(fill="x", pady=4)
            self.menu_buttons[menu_name] = button

        self.root.after(500, self.refresh_menu_badges)

        ttk.Separator(sidebar, orient="horizontal").pack(
            fill="x", pady=(18, 12)
        )

        ttk.Button(
            sidebar,
            text="쿠팡 주문 처리",
            command=self.run_order_engine,
            style="Action.TButton",
        ).pack(fill="x")

    def _create_content(self, parent: tk.Widget) -> None:
        self.content_frame = ttk.Frame(parent)
        self.content_frame.pack(side="left", fill="both", expand=True)
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)

        self.dashboard_page = DashboardPage(
            self.content_frame,
            status_callback=self.status_var.set,
            order_action=self.open_orders,
            mapping_action=self.open_mappings,
            purchase_action=self.open_purchases,
            shipment_action=self.open_shipments,
        )
        self.dashboard_page.grid(row=0, column=0, sticky="nsew")

        self.automation_page = AutomationPage(
            self.content_frame,
            status_callback=self.status_var.set,
            refresh_callback=self._refresh_dashboard_and_badges,
            purchase_action=self.open_purchases,
            shipment_action=self.open_shipments,
        )
        self.automation_page.grid(row=0, column=0, sticky="nsew")

        self.settlement_page = SettlementPage(
            self.content_frame,
            status_callback=self.status_var.set,
            refresh_callback=self._refresh_dashboard_and_badges,
        )
        self.settlement_page.grid(row=0, column=0, sticky="nsew")

        self.management_page = ManagementPage(
            self.content_frame,
            status_callback=self.status_var.set,
        )
        self.management_page.grid(row=0, column=0, sticky="nsew")

        self.dashboard_page.tkraise()

    def show_dashboard(self) -> None:
        if self.dashboard_page is None:
            return
        self.dashboard_page.tkraise()
        self.dashboard_page.refresh_dashboard()
        self.status_var.set("Dashboard 화면")
        self.refresh_menu_badges()


    def show_automation(self) -> None:
        if self.automation_page is None:
            return
        self.automation_page.tkraise()
        self.status_var.set("자동화센터 화면")

    def show_settlement(self) -> None:
        if self.settlement_page is None:
            return
        self.settlement_page.tkraise()
        self.settlement_page.refresh_data()
        self.status_var.set("정산센터 화면")

    def show_management(self) -> None:
        if self.management_page is None:
            return
        self.management_page.tkraise()
        self.management_page.refresh_data()
        self.status_var.set("경영현황 화면")

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
            summary = self.dashboard_service.get_dashboard_data().get("summary", {})
            labels = {
                "상품매핑": int(summary.get("unmapped", 0) or 0),
                "발주관리": int(summary.get("purchase_waiting", 0) or 0),
                "송장관리": int(summary.get("shipment_waiting", 0) or 0),
            }
            for name, count in labels.items():
                button = self.menu_buttons.get(name)
                if button is not None:
                    button.configure(text=f"{name} ({count:,})" if count else name)
        except Exception:
            pass
        self.root.after(60000, self.refresh_menu_badges)

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
        ).pack(fill="x", side="bottom")

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
            self._show_open_error("발주관리", error)

    def open_orders(self) -> None:
        try:
            OrderPage(self.root)
            self.status_var.set("주문관리 화면 실행")
        except Exception as error:
            self._show_open_error("주문관리", error)

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
            self._show_open_error("상품매핑", error)

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
                [sys.executable, "-m", module_name],
                cwd=self.project_root,
            )
            self.status_var.set(f"{display_name} 화면 실행")
        except Exception as error:
            self._show_open_error(display_name, error)

    def run_order_engine(self) -> None:
        confirmed = messagebox.askyesno(
            "발주 기능 실행",
            "data 폴더의 주문 엑셀 파일을 읽어\n"
            "표준 주문, 매핑 결과, 발주서를 생성합니다.\n\n"
            "계속하시겠습니까?",
            parent=self.root,
        )
        if not confirmed:
            return

        self.status_var.set("주문 발주 엔진 실행 중...")
        self.root.update_idletasks()

        try:
            run_legacy_order()
            self.status_var.set("주문 발주 엔진 실행 완료")
            messagebox.showinfo(
                "작업 완료",
                "주문 처리 작업이 완료되었습니다.\n"
                "output 폴더에서 결과 파일을 확인하세요.",
                parent=self.root,
            )
            if self.dashboard_page is not None:
                self.dashboard_page.refresh_dashboard()
            self.refresh_menu_badges()
        except Exception as error:
            self.status_var.set("주문 발주 엔진 실행 오류")
            messagebox.showerror(
                "실행 오류",
                "주문 처리 중 오류가 발생했습니다.\n\n"
                f"{error}",
                parent=self.root,
            )

    def show_preparing(self) -> None:
        messagebox.showinfo(
            "기능 준비 중",
            "해당 기능은 다음 개발 단계에서 추가됩니다.",
            parent=self.root,
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
            self._show_open_error("송장관리", error)

    def _show_open_error(self, display_name: str, error: Exception) -> None:
        self.status_var.set(f"{display_name} 실행 오류")
        messagebox.showerror(
            f"{display_name} 실행 오류",
            f"{display_name} 화면을 열지 못했습니다.\n\n{error}",
            parent=self.root,
        )

    def run(self) -> None:
        self.root.mainloop()
