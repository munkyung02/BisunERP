from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.version import ERP_VERSION
from modules.settings.settings_service import SettingsService
from modules.coupang.coupang_sync_page import CoupangSyncPage


class SettingsPage(ttk.Frame):
    """회사정보·출력경로·백업경로·ERP 기본설정을 관리합니다."""

    def __init__(
        self,
        parent: tk.Misc,
        status_callback=None,
        settings_service: SettingsService | None = None,
    ) -> None:
        super().__init__(parent)

        self.settings_service = (
            settings_service or SettingsService()
        )
        self.status_callback = status_callback

        self.company_name_var = tk.StringVar()
        self.business_name_var = tk.StringVar()
        self.representative_var = tk.StringVar()
        self.business_number_var = tk.StringVar()
        self.address_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.email_var = tk.StringVar()
        self.logo_path_var = tk.StringVar()

        self.output_directory_var = tk.StringVar()
        self.backup_directory_var = tk.StringVar()
        self.theme_var = tk.StringVar(value="기본")
        self.auto_save_var = tk.BooleanVar(value=True)
        self.version_var = tk.StringVar(value=ERP_VERSION)
        self.status_var = tk.StringVar(
            value="환경설정을 불러오는 중입니다."
        )

        self._build_ui()
        self.load_settings()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(
            self,
            padding=(20, 18, 20, 10),
        )
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="환경설정",
            font=("맑은 고딕", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            header,
            text=(
                "회사정보와 문서 출력, 백업 경로, "
                "ERP 기본 동작을 설정합니다."
            ),
        ).grid(
            row=1,
            column=0,
            pady=(5, 0),
            sticky="w",
        )

        ttk.Button(
            header,
            text="다시 불러오기",
            command=self.load_settings,
        ).grid(
            row=0,
            column=1,
            rowspan=2,
            sticky="e",
        )

        notebook = ttk.Notebook(self)
        notebook.grid(
            row=1,
            column=0,
            padx=20,
            sticky="nsew",
        )

        self.company_tab = ttk.Frame(
            notebook,
            padding=18,
        )
        self.document_tab = ttk.Frame(
            notebook,
            padding=18,
        )
        self.application_tab = ttk.Frame(
            notebook,
            padding=18,
        )
        self.coupang_tab = ttk.Frame(
            notebook,
            padding=0,
        )

        notebook.add(
            self.company_tab,
            text="회사정보",
        )
        notebook.add(
            self.document_tab,
            text="문서 및 경로",
        )
        notebook.add(
            self.application_tab,
            text="ERP 설정",
        )
        notebook.add(
            self.coupang_tab,
            text="쿠팡 Open API",
        )

        self._build_company_tab()
        self._build_document_tab()
        self._build_application_tab()
        self._build_coupang_tab()

        bottom = ttk.Frame(
            self,
            padding=(20, 12, 20, 18),
        )
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        ttk.Label(
            bottom,
            textvariable=self.status_var,
        ).grid(row=0, column=0, sticky="w")

        ttk.Button(
            bottom,
            text="기본값 복원",
            command=self.reset_settings,
        ).grid(row=0, column=1, padx=(8, 0))

        ttk.Button(
            bottom,
            text="저장",
            command=self.save_settings,
        ).grid(row=0, column=2, padx=(8, 0))

    def _build_company_tab(self) -> None:
        tab = self.company_tab
        tab.columnconfigure(1, weight=1)

        fields = [
            (
                "브랜드명",
                self.company_name_var,
            ),
            (
                "상호명",
                self.business_name_var,
            ),
            (
                "대표자",
                self.representative_var,
            ),
            (
                "사업자번호",
                self.business_number_var,
            ),
            (
                "주소",
                self.address_var,
            ),
            (
                "전화번호",
                self.phone_var,
            ),
            (
                "이메일",
                self.email_var,
            ),
        ]

        for row, (label, variable) in enumerate(fields):
            ttk.Label(
                tab,
                text=label,
                width=14,
            ).grid(
                row=row,
                column=0,
                padx=(0, 10),
                pady=6,
                sticky="w",
            )

            ttk.Entry(
                tab,
                textvariable=variable,
            ).grid(
                row=row,
                column=1,
                pady=6,
                sticky="ew",
            )

        logo_row = len(fields)

        ttk.Label(
            tab,
            text="회사 로고",
            width=14,
        ).grid(
            row=logo_row,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="w",
        )

        logo_frame = ttk.Frame(tab)
        logo_frame.grid(
            row=logo_row,
            column=1,
            pady=6,
            sticky="ew",
        )
        logo_frame.columnconfigure(0, weight=1)

        ttk.Entry(
            logo_frame,
            textvariable=self.logo_path_var,
            state="readonly",
        ).grid(row=0, column=0, sticky="ew")

        ttk.Button(
            logo_frame,
            text="로고 선택",
            command=self.choose_logo,
        ).grid(row=0, column=1, padx=(8, 0))

        ttk.Button(
            logo_frame,
            text="로고 제거",
            command=self.remove_logo,
        ).grid(row=0, column=2, padx=(8, 0))

    def _build_document_tab(self) -> None:
        tab = self.document_tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(2, weight=1)

        ttk.Label(
            tab,
            text="출력 폴더",
            width=14,
        ).grid(
            row=0,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="w",
        )

        output_frame = ttk.Frame(tab)
        output_frame.grid(
            row=0,
            column=1,
            pady=6,
            sticky="ew",
        )
        output_frame.columnconfigure(0, weight=1)

        ttk.Entry(
            output_frame,
            textvariable=self.output_directory_var,
        ).grid(row=0, column=0, sticky="ew")

        ttk.Button(
            output_frame,
            text="폴더 선택",
            command=self.choose_output_directory,
        ).grid(row=0, column=1, padx=(8, 0))

        ttk.Button(
            output_frame,
            text="폴더 열기",
            command=lambda: self.open_directory(
                self.output_directory_var.get()
            ),
        ).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(
            tab,
            text="백업 폴더",
            width=14,
        ).grid(
            row=1,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="w",
        )

        backup_frame = ttk.Frame(tab)
        backup_frame.grid(
            row=1,
            column=1,
            pady=6,
            sticky="ew",
        )
        backup_frame.columnconfigure(0, weight=1)

        ttk.Entry(
            backup_frame,
            textvariable=self.backup_directory_var,
        ).grid(row=0, column=0, sticky="ew")

        ttk.Button(
            backup_frame,
            text="폴더 선택",
            command=self.choose_backup_directory,
        ).grid(row=0, column=1, padx=(8, 0))

        ttk.Button(
            backup_frame,
            text="폴더 열기",
            command=lambda: self.open_directory(
                self.backup_directory_var.get()
            ),
        ).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(
            tab,
            text="발주서 하단 문구",
            width=14,
        ).grid(
            row=2,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="nw",
        )

        self.footer_text = tk.Text(
            tab,
            height=10,
            wrap="word",
        )
        self.footer_text.grid(
            row=2,
            column=1,
            pady=6,
            sticky="nsew",
        )

    def _build_application_tab(self) -> None:
        tab = self.application_tab
        tab.columnconfigure(1, weight=1)

        ttk.Label(
            tab,
            text="화면 테마",
            width=14,
        ).grid(
            row=0,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="w",
        )

        ttk.Combobox(
            tab,
            textvariable=self.theme_var,
            values=self.settings_service.THEMES,
            state="readonly",
            width=18,
        ).grid(
            row=0,
            column=1,
            pady=6,
            sticky="w",
        )

        ttk.Label(
            tab,
            text="자동 저장",
            width=14,
        ).grid(
            row=1,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="w",
        )

        ttk.Checkbutton(
            tab,
            text="입력 내용 자동 저장 사용",
            variable=self.auto_save_var,
        ).grid(
            row=1,
            column=1,
            pady=6,
            sticky="w",
        )

        ttk.Label(
            tab,
            text="ERP 버전",
            width=14,
        ).grid(
            row=2,
            column=0,
            padx=(0, 10),
            pady=6,
            sticky="w",
        )

        ttk.Entry(
            tab,
            textvariable=self.version_var,
            width=18,
            state="readonly",
        ).grid(
            row=2,
            column=1,
            pady=6,
            sticky="w",
        )

        ttk.Label(
            tab,
            text=(
                "테마 설정은 메인 화면에서 해당 값을 읽어 "
                "적용하도록 연결하면 됩니다."
            ),
        ).grid(
            row=3,
            column=0,
            columnspan=2,
            pady=(16, 0),
            sticky="w",
        )

    def _build_coupang_tab(self) -> None:
        self.coupang_tab.rowconfigure(0, weight=1)
        self.coupang_tab.columnconfigure(0, weight=1)
        self.coupang_sync_page = CoupangSyncPage(
            self.coupang_tab,
            status_callback=self.status_callback,
            settings_service=self.settings_service,
        )
        self.coupang_sync_page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

    def refresh_data(self) -> None:
        """MainWindow 호환용 새로고침 메서드입니다."""
        self.load_settings()
        if hasattr(self, "coupang_sync_page"):
            self.coupang_sync_page.refresh_data()

    def load_settings(self) -> None:
        try:
            settings = self.settings_service.load_settings()

            company = settings["company"]
            document = settings["document"]
            backup = settings["backup"]
            application = settings["application"]

            self.company_name_var.set(
                company.get("company_name") or ""
            )
            self.business_name_var.set(
                company.get("business_name") or ""
            )
            self.representative_var.set(
                company.get("representative_name") or ""
            )
            self.business_number_var.set(
                company.get("business_number") or ""
            )
            self.address_var.set(
                company.get("address") or ""
            )
            self.phone_var.set(
                company.get("phone") or ""
            )
            self.email_var.set(
                company.get("email") or ""
            )
            self.logo_path_var.set(
                company.get("logo_path") or ""
            )

            self.output_directory_var.set(
                document.get("output_directory") or ""
            )
            self.backup_directory_var.set(
                backup.get("backup_directory") or ""
            )
            self.theme_var.set(
                application.get("theme") or "기본"
            )
            self.auto_save_var.set(
                bool(
                    application.get(
                        "auto_save",
                        True,
                    )
                )
            )
            self.version_var.set(
                ERP_VERSION
            )

            self.footer_text.delete("1.0", "end")
            self.footer_text.insert(
                "1.0",
                document.get(
                    "purchase_order_footer"
                ) or "",
            )

            self.status_var.set(
                "환경설정을 불러왔습니다."
            )
            if self.status_callback is not None:
                self.status_callback(
                    "환경설정을 불러왔습니다."
                )

        except Exception as error:
            messagebox.showerror(
                "환경설정 오류",
                (
                    "환경설정을 불러오지 못했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

    def save_settings(self) -> None:
        settings = {
            "company": {
                "company_name": (
                    self.company_name_var.get()
                ),
                "business_name": (
                    self.business_name_var.get()
                ),
                "representative_name": (
                    self.representative_var.get()
                ),
                "business_number": (
                    self.business_number_var.get()
                ),
                "address": self.address_var.get(),
                "phone": self.phone_var.get(),
                "email": self.email_var.get(),
                "logo_path": self.logo_path_var.get(),
            },
            "document": {
                "purchase_order_footer": (
                    self.footer_text.get(
                        "1.0",
                        "end",
                    ).strip()
                ),
                "output_directory": (
                    self.output_directory_var.get()
                ),
            },
            "backup": {
                "backup_directory": (
                    self.backup_directory_var.get()
                ),
            },
            "application": {
                "theme": self.theme_var.get(),
                "auto_save": (
                    self.auto_save_var.get()
                ),
                "version": ERP_VERSION,
            },
        }

        try:
            saved = self.settings_service.save_settings(
                settings
            )
            self.settings_service.sync_backup_settings(
                saved["backup"]["backup_directory"]
            )

            self.business_number_var.set(
                saved["company"]["business_number"]
            )
            self.status_var.set(
                "환경설정을 저장했습니다."
            )
            if self.status_callback is not None:
                self.status_callback(
                    "환경설정을 저장했습니다."
                )

            messagebox.showinfo(
                "저장 완료",
                "환경설정을 저장했습니다.",
                parent=self,
            )

        except Exception as error:
            messagebox.showerror(
                "저장 오류",
                (
                    "환경설정을 저장하지 못했습니다.\n\n"
                    f"{error}"
                ),
                parent=self,
            )

    def reset_settings(self) -> None:
        confirmed = messagebox.askyesno(
            "기본값 복원",
            (
                "환경설정을 기본값으로 복원하시겠습니까?\n\n"
                "회사정보와 경로 설정이 초기화됩니다."
            ),
            parent=self,
        )

        if not confirmed:
            return

        try:
            self.settings_service.reset_settings()
            self.load_settings()
        except Exception as error:
            messagebox.showerror(
                "기본값 복원 오류",
                str(error),
                parent=self,
            )

    def choose_logo(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="회사 로고 선택",
            filetypes=[
                (
                    "이미지 파일",
                    "*.png *.jpg *.jpeg *.gif *.bmp",
                ),
                ("모든 파일", "*.*"),
            ],
        )

        if not selected:
            return

        try:
            copied_path = (
                self.settings_service.copy_logo(
                    selected
                )
            )
            self.logo_path_var.set(copied_path)
        except Exception as error:
            messagebox.showerror(
                "로고 선택 오류",
                str(error),
                parent=self,
            )

    def remove_logo(self) -> None:
        self.settings_service.remove_logo()
        self.logo_path_var.set("")

    def choose_output_directory(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="출력 폴더 선택",
            initialdir=(
                self.output_directory_var.get()
                or None
            ),
        )

        if selected:
            self.output_directory_var.set(selected)

    def choose_backup_directory(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="백업 폴더 선택",
            initialdir=(
                self.backup_directory_var.get()
                or None
            ),
        )

        if selected:
            self.backup_directory_var.set(selected)

    def open_directory(self, directory: str) -> None:
        path = Path(directory.strip())

        if not str(path):
            return

        path.mkdir(parents=True, exist_ok=True)

        try:
            os.startfile(path)
        except AttributeError:
            messagebox.showinfo(
                "폴더 위치",
                str(path),
                parent=self,
            )
        except OSError as error:
            messagebox.showerror(
                "폴더 열기 오류",
                str(error),
                parent=self,
            )
