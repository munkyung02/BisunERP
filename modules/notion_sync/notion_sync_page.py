from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

from core.database import Database

from .notion_live_service import NotionLiveSyncService
from .notion_sync_service import (
    TARGET_DATABASES,
    NotionDataSource,
    NotionSyncService,
)


class NotionSyncPage(ttk.Frame):
    """Notion Integration settings and database discovery screen."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        status_callback: Callable[[str], None] | None = None,
        service: NotionSyncService | None = None,
    ) -> None:
        super().__init__(parent, padding=24)
        self.status_callback = status_callback or (lambda _text: None)
        self.service = service or NotionSyncService()
        self.live_service = NotionLiveSyncService()
        self.database = Database()
        self.database.initialize()
        self.token_var = tk.StringVar()
        self.connection_var = tk.StringVar(value="연결 확인 전")
        self.last_checked_var = tk.StringVar(value="-")
        self.last_sync_var = tk.StringVar(value="-")
        self.last_sync_status_var = tk.StringVar(value="실행 이력 없음")
        self.last_sync_summary_var = tk.StringVar(value="-")
        self.row_status_vars = {name: tk.StringVar(value="찾기 전") for name in TARGET_DATABASES}
        self.discovered: dict[str, NotionDataSource | None] = {}
        self.action_buttons: list[ttk.Button] = []
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="노션 동기화", font=("맑은 고딕", 22, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            self,
            text="Notion을 기준정보 Master DB로 사용하기 위한 연결 설정입니다.",
            font=("맑은 고딕", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 18))

        connection = ttk.LabelFrame(self, text="1. Notion Integration 연결", padding=16)
        connection.grid(row=2, column=0, sticky="ew")
        connection.columnconfigure(1, weight=1)

        ttk.Label(connection, text="Integration 토큰").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.token_entry = ttk.Entry(connection, textvariable=self.token_var, show="●")
        self.token_entry.grid(row=0, column=1, sticky="ew")

        show_var = tk.BooleanVar(value=False)

        def toggle_token() -> None:
            self.token_entry.configure(show="" if show_var.get() else "●")

        ttk.Checkbutton(
            connection, text="표시", variable=show_var, command=toggle_token
        ).grid(row=0, column=2, padx=(8, 0))

        button_bar = ttk.Frame(connection)
        button_bar.grid(row=1, column=1, sticky="w", pady=(12, 0))
        self._add_action_button(button_bar, "토큰 저장", self.save_token).pack(side="left")
        self._add_action_button(button_bar, "연결 테스트", self.test_connection).pack(
            side="left", padx=(8, 0)
        )
        self._add_action_button(button_bar, "DB 다시 찾기", self.discover_databases).pack(
            side="left", padx=(8, 0)
        )
        self._add_action_button(button_bar, "가져올 내용 확인", self.preview_sync).pack(
            side="left", padx=(8, 0)
        )
        self._add_action_button(button_bar, "상품·공급처 동기화", self.run_sync).pack(
            side="left", padx=(8, 0)
        )

        ttk.Label(connection, text="연결 상태").grid(row=2, column=0, sticky="w", pady=(14, 0))
        ttk.Label(connection, textvariable=self.connection_var, font=("맑은 고딕", 10, "bold")).grid(
            row=2, column=1, sticky="w", pady=(14, 0)
        )
        ttk.Label(connection, text="마지막 확인").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Label(connection, textvariable=self.last_checked_var).grid(
            row=3, column=1, sticky="w", pady=(6, 0)
        )

        databases = ttk.LabelFrame(self, text="2. 공유된 데이터베이스 확인", padding=16)
        databases.grid(row=3, column=0, sticky="nsew", pady=(16, 0))
        databases.columnconfigure(1, weight=1)

        ttk.Label(databases, text="데이터베이스", font=("맑은 고딕", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(databases, text="상태", font=("맑은 고딕", 10, "bold")).grid(
            row=0, column=1, sticky="w"
        )

        for index, title in enumerate(TARGET_DATABASES, start=1):
            ttk.Label(databases, text=title).grid(row=index, column=0, sticky="w", pady=7)
            ttk.Label(databases, textvariable=self.row_status_vars[title]).grid(
                row=index, column=1, sticky="w", pady=7
            )

        note = (
            "노션에서 각 원본 데이터베이스 페이지의 우측 상단 ••• → 연결 추가에서 "
            "생성한 Integration을 공유해야 검색됩니다. 연결된 데이터베이스만 ERP가 읽을 수 있습니다."
        )
        ttk.Label(
            self,
            text=note,
            wraplength=1000,
            justify="left",
            foreground="#555555",
        ).grid(row=4, column=0, sticky="ew", pady=(14, 0))

        status_frame = ttk.LabelFrame(
            self,
            text="3. 최근 동기화 상태",
            padding=14,
        )
        status_frame.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        status_frame.columnconfigure(1, weight=1)

        ttk.Label(status_frame, text="최근 실행").grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        ttk.Label(
            status_frame,
            textvariable=self.last_sync_var,
            font=("맑은 고딕", 10, "bold"),
        ).grid(row=0, column=1, sticky="w")

        ttk.Label(status_frame, text="실행 상태").grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=(7, 0)
        )
        ttk.Label(
            status_frame,
            textvariable=self.last_sync_status_var,
            font=("맑은 고딕", 10, "bold"),
        ).grid(row=1, column=1, sticky="w", pady=(7, 0))

        ttk.Label(status_frame, text="변경 요약").grid(
            row=2, column=0, sticky="nw", padx=(0, 12), pady=(7, 0)
        )
        ttk.Label(
            status_frame,
            textvariable=self.last_sync_summary_var,
            wraplength=980,
            justify="left",
        ).grid(row=2, column=1, sticky="w", pady=(7, 0))

        ttk.Button(
            status_frame,
            text="실행 이력 새로고침",
            command=self.refresh_sync_history,
        ).grid(row=0, column=2, rowspan=2, padx=(12, 0), sticky="e")

        history_frame = ttk.LabelFrame(
            self,
            text="4. 최근 실행 이력",
            padding=12,
        )
        history_frame.grid(row=6, column=0, sticky="nsew", pady=(16, 0))
        history_frame.rowconfigure(0, weight=1)
        history_frame.columnconfigure(0, weight=1)

        columns = (
            "synced_at",
            "status",
            "supplier",
            "product",
            "condition",
            "warnings",
            "duration",
            "message",
        )
        self.history_tree = ttk.Treeview(
            history_frame,
            columns=columns,
            show="headings",
            height=8,
        )
        headings = {
            "synced_at": "실행 시각",
            "status": "상태",
            "supplier": "공급처 생성/수정/비활성",
            "product": "상품 생성/수정/비활성",
            "condition": "조건 생성/수정/비활성",
            "warnings": "주의",
            "duration": "소요시간",
            "message": "메시지",
        }
        widths = {
            "synced_at": 145,
            "status": 60,
            "supplier": 165,
            "product": 165,
            "condition": 165,
            "warnings": 55,
            "duration": 75,
            "message": 270,
        }
        for column in columns:
            self.history_tree.heading(column, text=headings[column])
            self.history_tree.column(
                column,
                width=widths[column],
                minwidth=50,
                anchor="center" if column != "message" else "w",
            )
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        history_scroll = ttk.Scrollbar(
            history_frame,
            orient="vertical",
            command=self.history_tree.yview,
        )
        history_scroll.grid(row=0, column=1, sticky="ns")
        self.history_tree.configure(yscrollcommand=history_scroll.set)

        log_frame = ttk.LabelFrame(self, text="5. 현재 실행 메시지", padding=12)
        log_frame.grid(row=7, column=0, sticky="nsew", pady=(16, 0))
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=5, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self._append_log(
            "토큰은 이 PC에 자동 저장됩니다 · 새 버전으로 바꿔도 다시 붙여넣지 않아도 됩니다."
        )

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.grid(row=8, column=0, sticky="ew", pady=(12, 0))
        self.rowconfigure(6, weight=1)

    def _add_action_button(self, parent: tk.Widget, text: str, command) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command)
        self.action_buttons.append(button)
        return button

    def refresh_data(self) -> None:
        token = self.service.get_token()
        self.token_var.set(token)
        values = self.service.settings_service.get_all()
        self.last_checked_var.set(values.get("notion.last_discovery_at", "-") or "-")
        for title in TARGET_DATABASES:
            source_id = values.get(self.service._setting_key(title), "")
            self.row_status_vars[title].set(
                f"저장됨 · {self._short_id(source_id)}" if source_id else "찾기 전"
            )

        self.refresh_sync_history()

    def save_token(self) -> None:
        try:
            self.service.save_token(self.token_var.get())
        except Exception as error:
            messagebox.showerror("토큰 저장", str(error), parent=self)
            return
        self.connection_var.set("토큰 저장됨 · 연결 테스트 필요")
        self.status_callback("Notion 토큰 저장 완료")
        messagebox.showinfo(
            "토큰 저장 완료",
            "토큰을 이 PC에 고정 저장했습니다. 다음 버전에서도 자동으로 불러옵니다.\n\n이제 ‘연결 테스트’를 누르세요.",
            parent=self,
        )

    def test_connection(self) -> None:
        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("연결 테스트", "Integration 토큰을 입력하세요.", parent=self)
            return

        def work() -> None:
            result = self.service.test_connection(token)
            self.service.save_token(token)
            return result

        def success(result) -> None:
            self.connection_var.set(f"연결됨 · {result['name']}")
            self.last_checked_var.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.status_callback("Notion 연결 테스트 성공")
            messagebox.showinfo(
                "연결 성공",
                f"Notion Integration 연결에 성공했습니다.\n\n연결명: {result['name']}",
                parent=self,
            )

        self._run_async("Notion 연결 확인 중...", work, success)

    def discover_databases(self) -> None:
        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("DB 찾기", "Integration 토큰을 입력하세요.", parent=self)
            return

        for variable in self.row_status_vars.values():
            variable.set("검색 중...")

        def work():
            sources = self.service.discover_data_sources(token)
            matched = self.service.match_target_databases(sources)
            self.service.save_token(token)
            self.service.save_discovery_result(matched)
            return sources, matched

        def success(result) -> None:
            sources, matched = result
            self.discovered = matched
            found = 0
            for title, source in matched.items():
                if source:
                    found += 1
                    self.row_status_vars[title].set(
                        f"찾음 · {source.title} · {self._short_id(source.data_source_id)}"
                    )
                else:
                    self.row_status_vars[title].set("못 찾음 · 노션 공유 여부 확인")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.last_checked_var.set(now)
            self.connection_var.set(f"연결됨 · 공유 DB {len(sources)}개 검색")
            self.status_callback(f"Notion DB 검색 완료: 목표 {found}/{len(TARGET_DATABASES)}개")
            messagebox.showinfo(
                "DB 검색 완료",
                f"Notion에서 공유된 데이터 소스 {len(sources)}개를 확인했습니다.\n"
                f"필요한 DB는 {found}/{len(TARGET_DATABASES)}개 찾았습니다.",
                parent=self,
            )

        self._run_async("Notion 데이터베이스 검색 중...", work, success)


    def preview_sync(self) -> None:
        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("가져올 내용 확인", "Integration 토큰을 입력하세요.", parent=self)
            return

        def work():
            self.live_service.save_token(token)
            return self.live_service.preview(token)

        def success(preview) -> None:
            self._append_log(
                f"미리보기 완료 · 공급처 {len(preview.suppliers)}개 · 상품 {len(preview.products)}개"
            )
            for warning in preview.warnings:
                self._append_log(f"주의 · {warning}")
            message = (
                f"노션에서 가져올 데이터를 확인했습니다.\n\n"
                f"공급처: {len(preview.suppliers)}개\n"
                f"상품: {len(preview.products)}개\n"
                f"주의사항: {len(preview.warnings)}개\n\n"
                "아직 ERP 데이터는 변경하지 않았습니다."
            )
            messagebox.showinfo("가져올 내용 확인", message, parent=self)

        self._run_async("Notion 데이터 미리보기 중...", work, success)

    def run_sync(self) -> None:
        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("동기화", "Integration 토큰을 입력하세요.", parent=self)
            return
        approved = messagebox.askyesno(
            "상품·공급처 동기화",
            "노션의 상품 DB와 공급처 DB 내용을 ERP로 가져옵니다.\n\n"
            "같은 상품 또는 공급처가 있으면 업데이트하고, 없으면 새로 등록합니다.\n"
            "계속할까요?",
            parent=self,
        )
        if not approved:
            return

        def work():
            self.live_service.save_token(token)
            return self.live_service.sync(token)

        def success(result) -> None:
            text = (
                "동기화 완료 · "
                f"공급처 생성 {result.get('supplier_created', 0)} / "
                f"수정 {result.get('supplier_updated', 0)} / "
                f"비활성 {result.get('supplier_deactivated', 0)} · "
                f"상품 생성 {result.get('product_created', 0)} / "
                f"수정 {result.get('product_updated', 0)} / "
                f"비활성 {result.get('product_deactivated', 0)} · "
                f"조건 생성 {result.get('condition_created', 0)} / "
                f"수정 {result.get('condition_updated', 0)} / "
                f"비활성 {result.get('condition_deactivated', 0)} · "
                f"{float(result.get('duration_seconds', 0) or 0):.2f}초"
            )
            self._append_log(text)
            for warning in result.get("warnings", []):
                self._append_log(f"주의 · {warning}")
            self.refresh_sync_history()
            self.status_callback("Notion 상품·공급처 동기화 완료")
            messagebox.showinfo(
                "동기화 완료",
                "노션 데이터를 ERP로 가져왔습니다.\n\n"
                f"공급처 생성: {result.get('supplier_created', 0)}개\n"
                f"공급처 수정: {result.get('supplier_updated', 0)}개\n"
                f"공급처 비활성: {result.get('supplier_deactivated', 0)}개\n"
                f"상품 생성: {result.get('product_created', 0)}개\n"
                f"상품 수정: {result.get('product_updated', 0)}개\n"
                f"상품 비활성: {result.get('product_deactivated', 0)}개\n"
                f"조건 생성: {result.get('condition_created', 0)}개\n"
                f"조건 수정: {result.get('condition_updated', 0)}개\n"
                f"조건 비활성: {result.get('condition_deactivated', 0)}개\n"
                f"주의사항: {len(result.get('warnings', []))}개\n"
                f"소요시간: {float(result.get('duration_seconds', 0) or 0):.2f}초",
                parent=self,
            )

        self._run_async("Notion 상품·공급처 동기화 중...", work, success)

    def refresh_sync_history(self) -> None:
        if not hasattr(self, "history_tree"):
            return

        try:
            with self.database.connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        synced_at,
                        status,
                        supplier_created,
                        supplier_updated,
                        COALESCE(supplier_deactivated, 0) AS supplier_deactivated,
                        product_created,
                        product_updated,
                        COALESCE(product_deactivated, 0) AS product_deactivated,
                        condition_created,
                        condition_updated,
                        COALESCE(condition_deactivated, 0) AS condition_deactivated,
                        warning_count,
                        COALESCE(duration_seconds, 0) AS duration_seconds,
                        message,
                        COALESCE(error_message, '') AS error_message
                    FROM notion_sync_logs
                    ORDER BY id DESC
                    LIMIT 20
                    """
                ).fetchall()
        except Exception as error:
            self.last_sync_status_var.set("이력 조회 실패")
            self.last_sync_summary_var.set(str(error))
            return

        for item_id in self.history_tree.get_children():
            self.history_tree.delete(item_id)

        for row in rows:
            detail_message = (
                row["error_message"]
                if row["status"] == "실패" and row["error_message"]
                else (row["message"] or "")
            )
            self.history_tree.insert(
                "",
                "end",
                values=(
                    row["synced_at"],
                    row["status"],
                    (
                        f"{row['supplier_created']}/"
                        f"{row['supplier_updated']}/"
                        f"{row['supplier_deactivated']}"
                    ),
                    (
                        f"{row['product_created']}/"
                        f"{row['product_updated']}/"
                        f"{row['product_deactivated']}"
                    ),
                    (
                        f"{row['condition_created']}/"
                        f"{row['condition_updated']}/"
                        f"{row['condition_deactivated']}"
                    ),
                    row["warning_count"],
                    f"{float(row['duration_seconds'] or 0):.2f}초",
                    detail_message,
                ),
            )

        if not rows:
            self.last_sync_var.set("-")
            self.last_sync_status_var.set("실행 이력 없음")
            self.last_sync_summary_var.set("-")
            return

        latest = rows[0]
        self.last_sync_var.set(latest["synced_at"])
        self.last_sync_status_var.set(latest["status"])
        if latest["status"] == "실패":
            self.last_sync_summary_var.set(
                latest["error_message"]
                or latest["message"]
                or "오류 내용 없음"
            )
        else:
            self.last_sync_summary_var.set(
                "공급처 "
                f"{latest['supplier_created']}/"
                f"{latest['supplier_updated']}/"
                f"{latest['supplier_deactivated']} · "
                "상품 "
                f"{latest['product_created']}/"
                f"{latest['product_updated']}/"
                f"{latest['product_deactivated']} · "
                "조건 "
                f"{latest['condition_created']}/"
                f"{latest['condition_updated']}/"
                f"{latest['condition_deactivated']} · "
                f"주의 {latest['warning_count']} · "
                f"{float(latest['duration_seconds'] or 0):.2f}초"
            )

    def _append_log(self, text: str) -> None:
        if not hasattr(self, "log_text"):
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _run_async(self, status: str, work, success) -> None:
        self._set_busy(True, status)

        def runner() -> None:
            try:
                result = work()
            except Exception as error:
                self.after(0, lambda: self._handle_error(error))
            else:
                self.after(0, lambda: self._handle_success(result, success))

        threading.Thread(target=runner, daemon=True).start()

    def _handle_success(self, result, success) -> None:
        self._set_busy(False, "")
        success(result)

    def _handle_error(self, error: Exception) -> None:
        self._set_busy(False, "")
        self.connection_var.set("연결 실패")
        self._append_log(f"실패 · {error}")
        self.refresh_sync_history()
        self.status_callback(f"Notion 오류: {error}")
        messagebox.showerror("Notion 연결 오류", str(error), parent=self)

    def _set_busy(self, busy: bool, status: str) -> None:
        state = "disabled" if busy else "normal"
        for button in self.action_buttons:
            button.configure(state=state)
        if busy:
            self.progress.start(10)
            self.status_callback(status)
        else:
            self.progress.stop()

    @staticmethod
    def _short_id(value: str) -> str:
        clean = value.replace("-", "")
        if len(clean) <= 10:
            return clean
        return f"{clean[:6]}…{clean[-4:]}"