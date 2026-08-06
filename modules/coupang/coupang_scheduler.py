from __future__ import annotations

import threading
import tkinter as tk
from typing import Callable

from modules.settings.settings_service import SettingsService

from .coupang_order_service import CoupangOrderService


class CoupangOrderScheduler:
    """Tkinter 메인루프와 안전하게 동작하는 쿠팡 주문 자동수집기입니다."""

    def __init__(
        self,
        root: tk.Misc,
        *,
        settings_service: SettingsService | None = None,
        status_callback: Callable[[str], None] | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.settings_service = settings_service or SettingsService()
        self.status_callback = status_callback or (lambda _text: None)
        self.refresh_callback = refresh_callback or (lambda: None)

        self._after_id: str | None = None
        self._running = False
        self._collecting = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._schedule_next(initial=True)

    def stop(self) -> None:
        self._running = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self._after_id = None

    def trigger_now(self) -> None:
        if not self._running or self._collecting:
            return

        settings = self.settings_service.get_coupang_settings()
        if not settings["auto_sync_enabled"]:
            self._schedule_next()
            return
        if not all(
            (
                settings["vendor_id"],
                settings["access_key"],
                settings["secret_key"],
            )
        ):
            self.status_callback(
                "쿠팡 자동수집 대기: Open API 인증정보를 입력하세요."
            )
            self._schedule_next()
            return

        self._collecting = True
        self.status_callback("쿠팡 신규주문 자동수집 중...")

        def worker() -> None:
            try:
                result = CoupangOrderService(
                    settings_service=self.settings_service
                ).collect_recent_orders()
            except Exception as error:
                self.root.after(
                    0,
                    lambda: self._finish_error(error),
                )
            else:
                self.root.after(
                    0,
                    lambda: self._finish_success(result),
                )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def _finish_success(self, result: dict) -> None:
        self._collecting = False
        self.status_callback(str(result.get("message") or "쿠팡 주문수집 완료"))
        try:
            self.refresh_callback()
        finally:
            self._schedule_next()

    def _finish_error(self, error: Exception) -> None:
        self._collecting = False
        self.status_callback(f"쿠팡 주문 자동수집 실패: {error}")
        self._schedule_next()

    def _schedule_next(self, *, initial: bool = False) -> None:
        if not self._running:
            return

        settings = self.settings_service.get_coupang_settings()
        interval_minutes = max(
            1,
            int(settings["sync_interval_minutes"]),
        )
        delay_ms = (
            3000
            if initial
            else interval_minutes * 60 * 1000
        )
        self._after_id = self.root.after(
            delay_ms,
            self.trigger_now,
        )
