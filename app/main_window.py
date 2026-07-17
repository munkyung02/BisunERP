import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from legacy_order_runner import main as run_legacy_order
from modules.orders.order_page import OrderPage
from modules.purchases.purchase_page import PurchasePage


class MainWindow:
    """비선상회 ERP 메인 화면입니다."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("비선상회 ERP v1.0")
        self.root.geometry("1200x720")
        self.root.minsize(1000, 650)

        self.project_root = (
            Path(__file__).resolve().parent.parent
        )

        self.status_var = tk.StringVar(
            value="시스템 준비 완료"
        )

        self._configure_style()
        self._create_ui()

    # =========================================================
    # 스타일 설정
    # =========================================================

    def _configure_style(self) -> None:
        style = ttk.Style()

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Menu.TButton",
            font=("맑은 고딕", 12),
            padding=(12, 12),
        )

        style.configure(
            "Action.TButton",
            font=("맑은 고딕", 11, "bold"),
            padding=(12, 10),
        )

    # =========================================================
    # 전체 화면 구성
    # =========================================================

    def _create_ui(self) -> None:
        header = tk.Frame(
            self.root,
            padx=25,
            pady=18,
        )
        header.pack(fill="x")

        title = tk.Label(
            header,
            text="비선상회 ERP",
            font=("맑은 고딕", 25, "bold"),
        )
        title.pack(side="left")

        version = tk.Label(
            header,
            text="v1.0",
            font=("맑은 고딕", 11),
        )
        version.pack(
            side="left",
            padx=(10, 0),
            pady=(10, 0),
        )

        separator = ttk.Separator(
            self.root,
            orient="horizontal",
        )
        separator.pack(fill="x")

        body = tk.Frame(self.root)
        body.pack(
            fill="both",
            expand=True,
        )

        self._create_sidebar(body)
        self._create_dashboard(body)
        self._create_status_bar()

    # =========================================================
    # 왼쪽 메뉴
    # =========================================================

    def _create_sidebar(
        self,
        parent: tk.Widget,
    ) -> None:
        sidebar = tk.Frame(
            parent,
            width=250,
            padx=20,
            pady=25,
            relief="groove",
            borderwidth=1,
        )
        sidebar.pack(
            side="left",
            fill="y",
        )
        sidebar.pack_propagate(False)

        menu_title = tk.Label(
            sidebar,
            text="ERP 메뉴",
            font=("맑은 고딕", 14, "bold"),
        )
        menu_title.pack(
            anchor="w",
            pady=(0, 15),
        )

        menus = [
            ("주문관리", self.open_orders),
            ("상품관리", self.open_products),
            ("공급처관리", self.open_suppliers),
            ("거래처관리", self.show_preparing),
            ("발주관리", self.open_purchases),
            ("입금관리", self.show_preparing),
            ("송장관리", self.show_preparing),
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
            button.pack(
                fill="x",
                pady=5,
            )

    # =========================================================
    # 대시보드
    # =========================================================

    def _create_dashboard(
        self,
        parent: tk.Widget,
    ) -> None:
        content = tk.Frame(
            parent,
            padx=35,
            pady=30,
        )
        content.pack(
            side="left",
            fill="both",
            expand=True,
        )

        dashboard_title = tk.Label(
            content,
            text="대시보드",
            font=("맑은 고딕", 22, "bold"),
        )
        dashboard_title.pack(anchor="w")

        description = tk.Label(
            content,
            text=(
                "비선상회 주문·발주 업무를 "
                "한곳에서 관리합니다."
            ),
            font=("맑은 고딕", 12),
        )
        description.pack(
            anchor="w",
            pady=(5, 25),
        )

        summary_frame = tk.Frame(content)
        summary_frame.pack(fill="x")

        self._create_summary_card(
            summary_frame,
            title="오늘 주문",
            value="0건",
        )

        self._create_summary_card(
            summary_frame,
            title="발주 대기",
            value="0건",
        )

        self._create_summary_card(
            summary_frame,
            title="배송 중",
            value="0건",
        )

        action_frame = tk.LabelFrame(
            content,
            text="빠른 실행",
            font=("맑은 고딕", 12, "bold"),
            padx=25,
            pady=25,
        )
        action_frame.pack(
            fill="x",
            pady=(35, 0),
        )

        run_button = ttk.Button(
            action_frame,
            text="쿠팡 주문 불러오기 및 발주서 생성",
            command=self.run_order_engine,
            style="Action.TButton",
        )
        run_button.pack(anchor="w")

        guide = tk.Label(
            action_frame,
            text=(
                "data 폴더의 첫 번째 엑셀 주문서를 읽어 "
                "기존 발주 엔진을 실행합니다."
            ),
            font=("맑은 고딕", 10),
            justify="left",
        )
        guide.pack(
            anchor="w",
            pady=(10, 0),
        )

    def _create_summary_card(
        self,
        parent: tk.Widget,
        title: str,
        value: str,
    ) -> None:
        card = tk.Frame(
            parent,
            padx=25,
            pady=20,
            relief="ridge",
            borderwidth=1,
        )
        card.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 15),
        )

        title_label = tk.Label(
            card,
            text=title,
            font=("맑은 고딕", 11),
        )
        title_label.pack(anchor="w")

        value_label = tk.Label(
            card,
            text=value,
            font=("맑은 고딕", 22, "bold"),
        )
        value_label.pack(
            anchor="w",
            pady=(8, 0),
        )

    # =========================================================
    # 상태 표시줄
    # =========================================================

    def _create_status_bar(self) -> None:
        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            padx=15,
            pady=8,
            relief="sunken",
            borderwidth=1,
            font=("맑은 고딕", 9),
        )
        status_bar.pack(
            fill="x",
            side="bottom",
        )

    # =========================================================
    # 발주관리
    # =========================================================

    def open_purchases(self) -> None:
        """Tkinter 발주관리 화면을 엽니다."""

        try:
            purchase_window = tk.Toplevel(self.root)

            purchase_window.title("비선상회 ERP - 발주관리")
            purchase_window.geometry("1400x800")
            purchase_window.minsize(1100, 650)

            purchase_page = PurchasePage(
                purchase_window
            )

            purchase_page.pack(
                fill="both",
                expand=True,
            )

            purchase_window.transient(
                self.root
            )

            purchase_window.focus_force()

            self.status_var.set(
                "발주관리 화면 실행"
            )

        except Exception as error:
            self.status_var.set(
                "발주관리 실행 오류"
            )

            messagebox.showerror(
                "발주관리 실행 오류",
                "발주관리 화면을 열지 못했습니다.\n\n"
                f"{error}",
            )    

    # =========================================================
    # 주문관리
    # =========================================================

    def open_orders(self) -> None:
        """Tkinter 주문관리 화면을 엽니다."""

        try:
            OrderPage(self.root)
            self.status_var.set(
                "주문관리 화면 실행"
            )

        except Exception as error:
            self.status_var.set(
                "주문관리 실행 오류"
            )

            messagebox.showerror(
                "주문관리 실행 오류",
                "주문관리 화면을 열지 못했습니다.\n\n"
                f"{error}",
            )

    # =========================================================
    # 상품관리
    # =========================================================

    def open_products(self) -> None:
        """PySide6 상품관리 화면을 별도 프로세스로 실행합니다."""

        try:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "modules.products.product_runner",
                ],
                cwd=self.project_root,
            )

            self.status_var.set(
                "상품관리 화면 실행"
            )

        except Exception as error:
            self.status_var.set(
                "상품관리 실행 오류"
            )

            messagebox.showerror(
                "상품관리 실행 오류",
                "상품관리 화면을 열지 못했습니다.\n\n"
                f"{error}",
            )

    # =========================================================
    # 공급처관리
    # =========================================================

    def open_suppliers(self) -> None:
        """PySide6 공급처관리 화면을 별도 프로세스로 실행합니다."""

        try:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "modules.suppliers.supplier_runner",
                ],
                cwd=self.project_root,
            )

            self.status_var.set(
                "공급처관리 화면 실행"
            )

        except Exception as error:
            self.status_var.set(
                "공급처관리 실행 오류"
            )

            messagebox.showerror(
                "공급처관리 실행 오류",
                "공급처관리 화면을 열지 못했습니다.\n\n"
                f"{error}",
            )

    # =========================================================
    # 기존 주문 발주 엔진
    # =========================================================

    def run_order_engine(self) -> None:
        confirmed = messagebox.askyesno(
            "발주 기능 실행",
            "data 폴더의 주문 엑셀 파일을 읽어\n"
            "표준 주문, 매핑 결과, 발주서를 생성합니다.\n\n"
            "계속하시겠습니까?",
        )

        if not confirmed:
            return

        self.status_var.set(
            "주문 발주 엔진 실행 중..."
        )
        self.root.update_idletasks()

        try:
            run_legacy_order()

            self.status_var.set(
                "주문 발주 엔진 실행 완료"
            )

            messagebox.showinfo(
                "작업 완료",
                "주문 처리 작업이 완료되었습니다.\n"
                "output 폴더에서 결과 파일을 확인하세요.",
            )

        except Exception as error:
            self.status_var.set(
                "주문 발주 엔진 실행 오류"
            )

            messagebox.showerror(
                "실행 오류",
                "주문 처리 중 오류가 발생했습니다.\n\n"
                f"{error}",
            )

    # =========================================================
    # 준비 중 메뉴
    # =========================================================

    def show_preparing(self) -> None:
        messagebox.showinfo(
            "기능 준비 중",
            "해당 기능은 다음 개발 단계에서 추가됩니다.",
        )

    # =========================================================
    # 프로그램 실행
    # =========================================================

    def run(self) -> None:
        self.root.mainloop()