from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

from modules.settings.settings_service import SettingsService

from .coupang_api import CoupangAPIClient
from .coupang_order_service import CoupangOrderService


class CoupangSyncPage(ttk.Frame):
    """쿠팡 Open API 인증정보 저장 및 연결 테스트 화면입니다."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        status_callback: Callable[[str], None] | None = None,
        settings_service: SettingsService | None = None,
    ) -> None:
        super().__init__(parent, padding=24)
        self.status_callback = status_callback or (lambda _text: None)
        self.settings_service = settings_service or SettingsService()

        self.vendor_id_var = tk.StringVar()
        self.access_key_var = tk.StringVar()
        self.secret_key_var = tk.StringVar()
        self.auto_sync_var = tk.BooleanVar(value=False)
        self.interval_var = tk.StringVar(value="5")
        self.connection_var = tk.StringVar(value="연결 확인 전")
        self.last_checked_var = tk.StringVar(value="-")
        self.message_var = tk.StringVar(value="-")
        self.show_secret_var = tk.BooleanVar(value=False)
        self.action_buttons: list[ttk.Button] = []
        self.last_order_sync_var = tk.StringVar(value="-")
        self.last_order_result_var = tk.StringVar(value="-")

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        ttk.Label(
            self,
            text="쿠팡 주문동기화",
            font=("맑은 고딕", 22, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text=(
                "쿠팡 Wing에서 발급받은 Open API 정보를 저장하고 "
                "주문조회 권한을 확인합니다."
            ),
        ).grid(row=1, column=0, sticky="w", pady=(4, 18))

        auth_frame = ttk.LabelFrame(
            self,
            text="1. 쿠팡 Open API 인증정보",
            padding=16,
        )
        auth_frame.grid(row=2, column=0, sticky="ew")
        auth_frame.columnconfigure(1, weight=1)

        fields = (
            ("Vendor ID", self.vendor_id_var),
            ("Access Key", self.access_key_var),
        )
        for row_index, (label, variable) in enumerate(fields):
            ttk.Label(
                auth_frame,
                text=label,
                width=16,
            ).grid(
                row=row_index,
                column=0,
                sticky="w",
                padx=(0, 10),
                pady=7,
            )
            ttk.Entry(
                auth_frame,
                textvariable=variable,
            ).grid(
                row=row_index,
                column=1,
                sticky="ew",
                pady=7,
            )

        ttk.Label(
            auth_frame,
            text="Secret Key",
            width=16,
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=7,
        )
        self.secret_entry = ttk.Entry(
            auth_frame,
            textvariable=self.secret_key_var,
            show="●",
        )
        self.secret_entry.grid(
            row=2,
            column=1,
            sticky="ew",
            pady=7,
        )
        ttk.Checkbutton(
            auth_frame,
            text="표시",
            variable=self.show_secret_var,
            command=self._toggle_secret,
        ).grid(row=2, column=2, padx=(8, 0))

        ttk.Label(
            auth_frame,
            text="자동조회 주기",
            width=16,
        ).grid(
            row=3,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=7,
        )
        interval_frame = ttk.Frame(auth_frame)
        interval_frame.grid(row=3, column=1, sticky="w", pady=7)
        ttk.Entry(
            interval_frame,
            textvariable=self.interval_var,
            width=8,
        ).pack(side="left")
        ttk.Label(interval_frame, text="분").pack(
            side="left",
            padx=(6, 0),
        )
        ttk.Checkbutton(
            auth_frame,
            text="자동 주문조회 사용",
            variable=self.auto_sync_var,
        ).grid(row=4, column=1, sticky="w", pady=7)

        button_bar = ttk.Frame(auth_frame)
        button_bar.grid(
            row=5,
            column=1,
            sticky="w",
            pady=(12, 0),
        )
        self._add_button(
            button_bar,
            "인증정보 저장",
            self.save_settings,
        ).pack(side="left")
        self._add_button(
            button_bar,
            "연결 테스트",
            self.test_connection,
        ).pack(side="left", padx=(8, 0))
        self._add_button(
            button_bar,
            "지금 주문수집",
            self.collect_orders_now,
        ).pack(side="left", padx=(8, 0))
        self._add_button(
            button_bar,
            "다시 불러오기",
            self.refresh_data,
        ).pack(side="left", padx=(8, 0))

        status_frame = ttk.LabelFrame(
            self,
            text="2. 연결 상태",
            padding=16,
        )
        status_frame.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(16, 0),
        )
        status_frame.columnconfigure(1, weight=1)

        rows = (
            ("상태", self.connection_var),
            ("마지막 확인", self.last_checked_var),
            ("메시지", self.message_var),
        )
        for row_index, (label, variable) in enumerate(rows):
            ttk.Label(
                status_frame,
                text=label,
                width=16,
            ).grid(
                row=row_index,
                column=0,
                sticky="nw",
                padx=(0, 10),
                pady=6,
            )
            ttk.Label(
                status_frame,
                textvariable=variable,
                wraplength=1000,
                justify="left",
                font=(
                    ("맑은 고딕", 10, "bold")
                    if row_index == 0
                    else ("맑은 고딕", 10)
                ),
            ).grid(
                row=row_index,
                column=1,
                sticky="w",
                pady=6,
            )

        order_frame = ttk.LabelFrame(
            self,
            text="3. 주문수집 상태",
            padding=16,
        )
        order_frame.grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(16, 0),
        )
        order_frame.columnconfigure(1, weight=1)

        ttk.Label(
            order_frame,
            text="마지막 주문수집",
            width=16,
        ).grid(row=0, column=0, sticky="w", pady=6)
        ttk.Label(
            order_frame,
            textvariable=self.last_order_sync_var,
        ).grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(
            order_frame,
            text="수집 결과",
            width=16,
        ).grid(row=1, column=0, sticky="nw", pady=6)
        ttk.Label(
            order_frame,
            textvariable=self.last_order_result_var,
            wraplength=1000,
            justify="left",
        ).grid(row=1, column=1, sticky="w", pady=6)

        note = (
            "Secret Key는 화면에서 가려서 표시되지만 현재 단계에서는 "
            "이 PC의 ERP 설정 DB에 저장됩니다. PC 계정과 데이터 폴더 접근권한을 "
            "안전하게 관리하세요."
        )
        ttk.Label(
            self,
            text=note,
            foreground="#555555",
            wraplength=1050,
            justify="left",
        ).grid(row=5, column=0, sticky="ew", pady=(14, 0))

        self.progress = ttk.Progressbar(
            self,
            mode="indeterminate",
        )
        self.progress.grid(
            row=6,
            column=0,
            sticky="ew",
            pady=(14, 0),
        )

    def _add_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
    ) -> ttk.Button:
        button = ttk.Button(
            parent,
            text=text,
            command=command,
        )
        self.action_buttons.append(button)
        return button

    def _toggle_secret(self) -> None:
        self.secret_entry.configure(
            show="" if self.show_secret_var.get() else "●"
        )

    def refresh_data(self) -> None:
        settings = self.settings_service.get_coupang_settings()
        self.vendor_id_var.set(settings["vendor_id"])
        self.access_key_var.set(settings["access_key"])
        self.secret_key_var.set(settings["secret_key"])
        self.auto_sync_var.set(settings["auto_sync_enabled"])
        self.interval_var.set(
            str(settings["sync_interval_minutes"])
        )
        self.connection_var.set(
            settings["last_connection_status"]
            or "연결 확인 전"
        )
        self.last_checked_var.set(
            settings["last_connection_at"] or "-"
        )
        self.message_var.set(
            settings["last_connection_message"] or "-"
        )
        summary = CoupangOrderService(
            settings_service=self.settings_service
        ).get_last_sync_summary()
        self.last_order_sync_var.set(
            summary["checked_at"] or "-"
        )
        self.last_order_result_var.set(
            summary["message"] or "-"
        )

    def save_settings(self, *, show_message: bool = True) -> None:
        try:
            self.settings_service.save_coupang_settings(
                vendor_id=self.vendor_id_var.get(),
                access_key=self.access_key_var.get(),
                secret_key=self.secret_key_var.get(),
                auto_sync_enabled=self.auto_sync_var.get(),
                sync_interval_minutes=self.interval_var.get(),
            )
        except Exception as error:
            messagebox.showerror(
                "쿠팡 설정 저장 오류",
                str(error),
                parent=self,
            )
            return

        self.connection_var.set(
            "인증정보 저장됨 · 연결 테스트 필요"
        )
        self.status_callback("쿠팡 Open API 인증정보 저장 완료")
        if show_message:
            messagebox.showinfo(
                "저장 완료",
                "쿠팡 Open API 인증정보를 저장했습니다.",
                parent=self,
            )

    def test_connection(self) -> None:
        try:
            self.settings_service.save_coupang_settings(
                vendor_id=self.vendor_id_var.get(),
                access_key=self.access_key_var.get(),
                secret_key=self.secret_key_var.get(),
                auto_sync_enabled=self.auto_sync_var.get(),
                sync_interval_minutes=self.interval_var.get(),
            )
            settings = self.settings_service.get_coupang_settings()
        except Exception as error:
            messagebox.showerror(
                "쿠팡 연결 테스트",
                str(error),
                parent=self,
            )
            return

        def work():
            client = CoupangAPIClient(
                vendor_id=settings["vendor_id"],
                access_key=settings["access_key"],
                secret_key=settings["secret_key"],
            )
            return client.test_connection()

        self._set_busy(True, "쿠팡 Open API 연결 확인 중...")

        def runner() -> None:
            try:
                result = work()
            except Exception as error:
                self.after(
                    0,
                    lambda: self._handle_connection_error(error),
                )
            else:
                self.after(
                    0,
                    lambda: self._handle_connection_success(result),
                )

        threading.Thread(
            target=runner,
            daemon=True,
        ).start()

    def collect_orders_now(self) -> None:
        try:
            self.settings_service.save_coupang_settings(
                vendor_id=self.vendor_id_var.get(),
                access_key=self.access_key_var.get(),
                secret_key=self.secret_key_var.get(),
                auto_sync_enabled=self.auto_sync_var.get(),
                sync_interval_minutes=self.interval_var.get(),
            )
        except Exception as error:
            messagebox.showerror(
                "쿠팡 주문수집",
                str(error),
                parent=self,
            )
            return

        self._set_busy(True, "최근 24시간 쿠팡 주문 수집 중...")

        def runner() -> None:
            try:
                result = CoupangOrderService(
                    settings_service=self.settings_service
                ).collect_recent_orders()
            except Exception as error:
                self.after(
                    0,
                    lambda: self._handle_order_collection_error(error),
                )
            else:
                self.after(
                    0,
                    lambda: self._handle_order_collection_success(result),
                )

        threading.Thread(
            target=runner,
            daemon=True,
        ).start()

    def _handle_order_collection_success(
        self,
        result: dict,
    ) -> None:
        self._set_busy(False, "")
        self.last_order_sync_var.set(
            str(result.get("checked_at") or "-")
        )
        self.last_order_result_var.set(
            str(result.get("message") or "-")
        )
        self.status_callback(
            str(result.get("message") or "쿠팡 주문수집 완료")
        )
        messagebox.showinfo(
            "쿠팡 주문수집 완료",
            (
                f"API 수신: {result.get('received_count', 0)}건\n"
                f"신규 저장: {result.get('created_count', 0)}건\n"
                f"중복 제외: {result.get('duplicate_count', 0)}건\n"
                f"실패: {result.get('failed_count', 0)}건\n"
                f"자동매핑: {result.get('mapping_mapped_count', 0)}건\n"
                f"미매핑: {result.get('mapping_unmatched_count', 0)}건"
            ),
            parent=self,
        )

    def _handle_order_collection_error(
        self,
        error: Exception,
    ) -> None:
        self._set_busy(False, "")
        self.last_order_result_var.set(str(error))
        self.status_callback(f"쿠팡 주문수집 실패: {error}")
        messagebox.showerror(
            "쿠팡 주문수집 실패",
            str(error),
            parent=self,
        )

    def _handle_connection_success(
        self,
        result: dict,
    ) -> None:
        self._set_busy(False, "")
        checked_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        message = (
            f"{result.get('message', '연결 성공')} · "
            f"오늘 ACCEPT 주문 표본 "
            f"{result.get('sample_order_count', 0)}건"
        )
        self.connection_var.set("연결 성공")
        self.last_checked_var.set(checked_at)
        self.message_var.set(message)
        self.settings_service.save_coupang_connection_result(
            checked_at=checked_at,
            status="연결 성공",
            message=message,
        )
        self.status_callback("쿠팡 Open API 연결 테스트 성공")
        messagebox.showinfo(
            "쿠팡 연결 성공",
            (
                "쿠팡 Open API 인증 및 주문조회 권한을 확인했습니다.\n\n"
                f"Vendor ID: {result.get('vendor_id', '')}\n"
                f"HTTP 상태: {result.get('http_status', 200)}"
            ),
            parent=self,
        )

    def _handle_connection_error(
        self,
        error: Exception,
    ) -> None:
        self._set_busy(False, "")
        checked_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        message = str(error)
        self.connection_var.set("연결 실패")
        self.last_checked_var.set(checked_at)
        self.message_var.set(message)
        try:
            self.settings_service.save_coupang_connection_result(
                checked_at=checked_at,
                status="연결 실패",
                message=message,
            )
        except Exception:
            pass
        self.status_callback(f"쿠팡 Open API 연결 실패: {message}")
        messagebox.showerror(
            "쿠팡 연결 실패",
            message,
            parent=self,
        )

    def _set_busy(
        self,
        busy: bool,
        status: str,
    ) -> None:
        state = "disabled" if busy else "normal"
        for button in self.action_buttons:
            button.configure(state=state)

        if busy:
            self.progress.start(10)
            self.status_callback(status)
        else:
            self.progress.stop()
