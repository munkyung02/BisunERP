from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Callable

from modules.notion_sync.notion_live_service import (
    NotionLiveSyncService,
)
from modules.settings.settings_service import SettingsService


class NotionAutoSyncController:
    """
    MainWindow와 NotionLiveSyncService 사이를 연결하는 자동동기화 제어기입니다.

    특징:
    - 기본 30초 주기
    - 중복 실행 방지
    - ERP 화면 멈춤 방지(백그라운드 스레드)
    - 오류가 발생해도 ERP는 계속 실행
    - 프로그램 종료 시 안전 정지
    """

    DEFAULT_INTERVAL_SECONDS = 30
    MIN_INTERVAL_SECONDS = 15

    def __init__(
        self,
        app: Any,
        *,
        live_service: NotionLiveSyncService | None = None,
        settings_service: SettingsService | None = None,
    ) -> None:
        self.app = app
        self.root = app.root
        self.status_callback: Callable[[str], None] = (
            app.status_var.set
        )

        self.live_service = (
            live_service or NotionLiveSyncService()
        )
        self.settings_service = (
            settings_service or SettingsService()
        )

        self._stop_event = threading.Event()
        self._sync_lock = threading.Lock()
        self._timer_id: str | None = None
        self._started = False
        self._closed = False

        self.enabled = self._read_enabled()
        self.interval_seconds = self._read_interval()

    def start(self) -> None:
        if self._started or self._closed:
            return

        self._started = True
        self._install_close_handler()

        if not self.enabled:
            self.status_callback(
                "Notion 자동동기화 OFF"
            )
            return

        self.status_callback(
            f"Notion 자동동기화 준비 · {self.interval_seconds}초 주기"
        )

        # ERP 시작 직후 다른 초기화 작업과 겹치지 않도록 조금 기다립니다.
        self._schedule_next(delay_ms=3000)

    def stop(self) -> None:
        if self._closed:
            return

        self._closed = True
        self._stop_event.set()

        if self._timer_id is not None:
            try:
                self.root.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        self.settings_service.save({
            "notion.auto_sync.enabled": (
                "1" if self.enabled else "0"
            )
        })

        if self.enabled:
            self._stop_event.clear()
            self.status_callback(
                f"Notion 자동동기화 ON · {self.interval_seconds}초 주기"
            )
            self._schedule_next(delay_ms=500)
        else:
            if self._timer_id is not None:
                try:
                    self.root.after_cancel(self._timer_id)
                except Exception:
                    pass
                self._timer_id = None
            self.status_callback(
                "Notion 자동동기화 OFF"
            )

    def set_interval(self, seconds: int) -> None:
        clean_seconds = max(
            self.MIN_INTERVAL_SECONDS,
            int(seconds),
        )
        self.interval_seconds = clean_seconds
        self.settings_service.save({
            "notion.auto_sync.interval_seconds": str(
                clean_seconds
            )
        })

        if self.enabled:
            self._schedule_next(
                delay_ms=clean_seconds * 1000
            )

    def run_now(self) -> None:
        if self._closed:
            return

        if self._sync_lock.locked():
            self.status_callback(
                "Notion 동기화가 이미 실행 중입니다."
            )
            return

        thread = threading.Thread(
            target=self._sync_once,
            daemon=True,
            name="BisunERP-NotionAutoSync",
        )
        thread.start()

    def _schedule_next(
        self,
        *,
        delay_ms: int | None = None,
    ) -> None:
        if (
            self._closed
            or self._stop_event.is_set()
            or not self.enabled
        ):
            return

        if self._timer_id is not None:
            try:
                self.root.after_cancel(self._timer_id)
            except Exception:
                pass

        wait_ms = (
            int(delay_ms)
            if delay_ms is not None
            else self.interval_seconds * 1000
        )

        self._timer_id = self.root.after(
            max(100, wait_ms),
            self._on_timer,
        )

    def _on_timer(self) -> None:
        self._timer_id = None

        if (
            self._closed
            or self._stop_event.is_set()
            or not self.enabled
        ):
            return

        self.run_now()
        self._schedule_next()

    def _sync_once(self) -> None:
        if not self._sync_lock.acquire(blocking=False):
            return

        try:
            token = self.live_service.get_token()

            if not token:
                self._post_status(
                    "Notion 자동동기화 대기 · 토큰 없음"
                )
                return

            self._post_status(
                "Notion 자동동기화 실행 중..."
            )

            result = self.live_service.sync(token)

            supplier_count = (
                int(result.get("supplier_created", 0) or 0)
                + int(result.get("supplier_updated", 0) or 0)
            )
            product_count = (
                int(result.get("product_created", 0) or 0)
                + int(result.get("product_updated", 0) or 0)
            )
            now = datetime.now().strftime("%H:%M:%S")

            self._post_status(
                "Notion 자동동기화 완료 "
                f"· 공급처 {supplier_count} "
                f"· 상품 {product_count} "
                f"· {now}"
            )

            self._refresh_visible_pages()

        except Exception as error:
            self._post_status(
                f"Notion 자동동기화 실패: {error}"
            )

        finally:
            self._sync_lock.release()

    def _refresh_visible_pages(self) -> None:
        def refresh() -> None:
            try:
                notion_page = getattr(
                    self.app,
                    "notion_sync_page",
                    None,
                )
                if notion_page is not None:
                    notion_page.refresh_data()

                dashboard_page = getattr(
                    self.app,
                    "dashboard_page",
                    None,
                )
                if dashboard_page is not None:
                    dashboard_page.refresh_dashboard()

                self.app.refresh_menu_badges()

            except Exception:
                # 화면 새로고침 실패는 동기화 성공 자체를 취소하지 않습니다.
                pass

        try:
            self.root.after(0, refresh)
        except Exception:
            pass

    def _post_status(self, text: str) -> None:
        try:
            self.root.after(
                0,
                lambda message=text: self.status_callback(message),
            )
        except Exception:
            pass

    def _install_close_handler(self) -> None:
        def close_app() -> None:
            self.stop()
            try:
                self.root.destroy()
            except Exception:
                pass

        self.root.protocol(
            "WM_DELETE_WINDOW",
            close_app,
        )

    def _read_enabled(self) -> bool:
        values = self.settings_service.get_all()
        raw = str(
            values.get(
                "notion.auto_sync.enabled",
                "1",
            )
        ).strip().lower()

        return raw not in {
            "0",
            "false",
            "off",
            "no",
            "n",
            "비활성",
        }

    def _read_interval(self) -> int:
        values = self.settings_service.get_all()
        raw = values.get(
            "notion.auto_sync.interval_seconds",
            self.DEFAULT_INTERVAL_SECONDS,
        )

        try:
            interval = int(raw)
        except (TypeError, ValueError):
            interval = self.DEFAULT_INTERVAL_SECONDS

        return max(
            self.MIN_INTERVAL_SECONDS,
            interval,
        )