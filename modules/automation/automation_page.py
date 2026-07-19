from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from modules.automation.automation_service import (
    AutomationResult,
    AutomationService,
)


class AutomationPage(ttk.Frame):
    """비선상회 ERP 자동화센터 화면입니다."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        service: AutomationService | None = None,
        status_callback: Callable[[str], None] | None = None,
        refresh_callback: Callable[[], None] | None = None,
        purchase_action: Callable[[], None] | None = None,
        shipment_action: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, padding=24)
        self.service = service or AutomationService()
        self.status_callback = status_callback
        self.refresh_callback = refresh_callback
        self.purchase_action = purchase_action
        self.shipment_action = shipment_action
        self.message_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.running = False
        self.step_status_vars: dict[str, tk.StringVar] = {}
        self.action_buttons: list[ttk.Button] = []

        self._configure_styles()
        self._build_ui()
        self.after(100, self._poll_queue)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.configure(
            "AutomationTitle.TLabel",
            font=("맑은 고딕", 22, "bold"),
        )
        style.configure(
            "AutomationStep.TLabel",
            font=("맑은 고딕", 12, "bold"),
        )
        style.configure(
            "AutomationRun.TButton",
            font=("맑은 고딕", 11, "bold"),
            padding=(16, 10),
        )

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="자동화센터",
            style="AutomationTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="반복 업무를 단계별로 실행하고 진행 로그를 확인합니다.",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.run_all_button = ttk.Button(
            header,
            text="지원 단계 한번에 실행",
            command=self._confirm_run_all,
            style="AutomationRun.TButton",
        )
        self.run_all_button.grid(row=0, column=1, rowspan=2, sticky="e")
        self.action_buttons.append(self.run_all_button)

        steps_frame = ttk.LabelFrame(
            self,
            text="자동화 단계",
            padding=14,
        )
        steps_frame.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        steps_frame.columnconfigure(1, weight=1)

        definitions = (
            ("collect", "1. 주문 수집 및 발주서 생성", "실행", self._run_collect),
            ("mapping", "2. 상품 자동매핑", "실행", self._run_mapping),
            ("purchase", "3. 발주 결과 확인", "열기", self._open_purchase),
            ("shipment", "4. 송장 엑셀 등록", "열기", self._open_shipment),
            ("delivery", "5. 배송조회", "준비 중", self._show_delivery_notice),
        )

        for row, (key, title, button_text, command) in enumerate(definitions):
            ttk.Label(
                steps_frame,
                text=title,
                style="AutomationStep.TLabel",
            ).grid(row=row, column=0, padx=(0, 16), pady=8, sticky="w")

            status_var = tk.StringVar(value="대기")
            self.step_status_vars[key] = status_var
            ttk.Label(
                steps_frame,
                textvariable=status_var,
            ).grid(row=row, column=1, pady=8, sticky="w")

            button = ttk.Button(
                steps_frame,
                text=button_text,
                command=command,
                width=12,
            )
            button.grid(row=row, column=2, pady=8, sticky="e")
            if key != "delivery":
                self.action_buttons.append(button)

        log_frame = ttk.LabelFrame(
            self,
            text="실행 로그",
            padding=10,
        )
        log_frame.grid(row=2, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            font=("Consolas", 10),
            state="disabled",
        )
        scrollbar = ttk.Scrollbar(
            log_frame,
            orient="vertical",
            command=self.log_text.yview,
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        footer = ttk.Frame(self)
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(
            footer,
            text=(
                "현재 자동 실행 범위: 기존 주문 엔진 → 자동 상품매핑 → 발주 결과 확인. "
                "송장 파일 선택과 배송조회 API는 다음 단계에서 연결합니다."
            ),
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            footer,
            text="로그 지우기",
            command=self._clear_log,
        ).grid(row=0, column=1, sticky="e")

    def _confirm_run_all(self) -> None:
        if self.running:
            return
        confirmed = messagebox.askyesno(
            "자동화 실행",
            "주문 엔진 실행과 자동 상품매핑을 순서대로 진행합니다.\n\n계속하시겠습니까?",
            parent=self.winfo_toplevel(),
        )
        if confirmed:
            self._start_worker("pipeline")

    def _run_collect(self) -> None:
        self._start_worker("collect")

    def _run_mapping(self) -> None:
        self._start_worker("mapping")

    def _start_worker(self, job: str) -> None:
        if self.running:
            messagebox.showinfo(
                "실행 중",
                "다른 자동화 작업이 실행 중입니다.",
                parent=self.winfo_toplevel(),
            )
            return

        self.running = True
        self._set_buttons_enabled(False)
        self._set_status("자동화 작업 실행 중...")
        threading.Thread(
            target=self._worker,
            args=(job,),
            daemon=True,
        ).start()

    def _worker(self, job: str) -> None:
        try:
            if job == "pipeline":
                self.message_queue.put(("step", ("collect", "실행 중")))
                result = self.service.collect_orders()
                self.message_queue.put(("result", ("collect", result)))
                if not result.success:
                    return

                self.message_queue.put(("step", ("mapping", "실행 중")))
                result = self.service.auto_map_orders()
                self.message_queue.put(("result", ("mapping", result)))
                if result.success:
                    purchase = self.service.prepare_purchase_orders()
                    self.message_queue.put(("result", ("purchase", purchase)))

            elif job == "collect":
                self.message_queue.put(("step", ("collect", "실행 중")))
                result = self.service.collect_orders()
                self.message_queue.put(("result", ("collect", result)))

            elif job == "mapping":
                self.message_queue.put(("step", ("mapping", "실행 중")))
                result = self.service.auto_map_orders()
                self.message_queue.put(("result", ("mapping", result)))

        except Exception as error:
            self.message_queue.put(("error", error))
        finally:
            self.message_queue.put(("finished", None))

    def _poll_queue(self) -> None:
        try:
            while True:
                event, payload = self.message_queue.get_nowait()
                if event == "step":
                    key, text = payload  # type: ignore[misc]
                    self.step_status_vars[key].set(text)
                elif event == "result":
                    key, result = payload  # type: ignore[misc]
                    assert isinstance(result, AutomationResult)
                    self.step_status_vars[key].set(
                        "완료" if result.success else "확인 필요"
                    )
                    self._append_log(self.service.format_log(result))
                elif event == "error":
                    self._append_log(f"[오류] {payload}")
                    messagebox.showerror(
                        "자동화 오류",
                        f"자동화 실행 중 오류가 발생했습니다.\n\n{payload}",
                        parent=self.winfo_toplevel(),
                    )
                elif event == "finished":
                    self.running = False
                    self._set_buttons_enabled(True)
                    self._set_status("자동화 작업 완료")
                    if self.refresh_callback is not None:
                        self.refresh_callback()
        except queue.Empty:
            pass

        self.after(100, self._poll_queue)

    def _open_purchase(self) -> None:
        self.step_status_vars["purchase"].set("화면 열기")
        if self.purchase_action is not None:
            self.purchase_action()

    def _open_shipment(self) -> None:
        self.step_status_vars["shipment"].set("화면 열기")
        if self.shipment_action is not None:
            self.shipment_action()

    def _show_delivery_notice(self) -> None:
        result = self.service.check_delivery()
        self.step_status_vars["delivery"].set("API 연결 전")
        self._append_log(self.service.format_log(result))
        messagebox.showinfo(
            "배송조회",
            result.message,
            parent=self.winfo_toplevel(),
        )

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.action_buttons:
            button.configure(state=state)

    def _set_status(self, message: str) -> None:
        if self.status_callback is not None:
            self.status_callback(message)
