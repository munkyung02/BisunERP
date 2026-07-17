from __future__ import annotations

import os
import queue
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from config.setting import COMPANY, ERP_VERSION
from src.erp_processor import run_order_processing


BASE_DIR = Path(__file__).resolve().parent


class BisunERPApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{COMPANY} ERP v{ERP_VERSION}")
        self.geometry("1050x700")
        self.minsize(900, 600)

        self.message_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.is_running = False

        self._configure_style()
        self._build_ui()
        self.after(100, self._poll_messages)
        self._write_log(f"{COMPANY} ERP v{ERP_VERSION} 준비 완료")
        self._write_log("data 폴더에 쿠팡 주문 엑셀을 넣고 '주문 처리 및 발주서 생성'을 누르세요.\n")

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("맑은 고딕", 22, "bold"))
        style.configure("Sub.TLabel", font=("맑은 고딕", 10))
        style.configure("Menu.TButton", font=("맑은 고딕", 11), padding=10)
        style.configure("Run.TButton", font=("맑은 고딕", 13, "bold"), padding=14)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(22, 18))
        header.pack(fill="x")
        ttk.Label(header, text=f"{COMPANY} ERP", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"v{ERP_VERSION}", style="Sub.TLabel").pack(side="left", padx=(12, 0), pady=(12, 0))

        body = ttk.Frame(self, padding=(20, 0, 20, 20))
        body.pack(fill="both", expand=True)

        sidebar = ttk.LabelFrame(body, text="업무 메뉴", padding=14)
        sidebar.pack(side="left", fill="y", padx=(0, 16))

        self.run_button = ttk.Button(
            sidebar,
            text="주문 처리 및\n발주서 생성",
            style="Run.TButton",
            command=self._start_processing,
            width=20,
        )
        self.run_button.pack(fill="x", pady=(0, 14))

        menu_items = [
            ("주문 파일 폴더 열기", BASE_DIR / "data"),
            ("발주 결과 폴더 열기", BASE_DIR / "output"),
            ("상품 매핑표 열기", BASE_DIR / "output" / "상품매핑표.xlsx"),
            ("미매핑 목록 열기", BASE_DIR / "output" / "미매핑_상품목록.xlsx"),
            ("주문 처리 이력 열기", BASE_DIR / "output" / "주문처리이력.xlsx"),
        ]
        for label, path in menu_items:
            ttk.Button(
                sidebar,
                text=label,
                style="Menu.TButton",
                command=lambda selected=path: self._open_path(selected),
            ).pack(fill="x", pady=4)

        ttk.Separator(sidebar).pack(fill="x", pady=14)
        ttk.Button(sidebar, text="사용 방법", command=self._show_help).pack(fill="x", pady=4)
        ttk.Button(sidebar, text="프로그램 종료", command=self.destroy).pack(fill="x", pady=4)

        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)

        status_frame = ttk.LabelFrame(content, text="처리 상태", padding=12)
        status_frame.pack(fill="x", pady=(0, 12))
        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(status_frame, textvariable=self.status_var, font=("맑은 고딕", 12, "bold")).pack(side="left")
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", length=220)
        self.progress.pack(side="right")

        log_frame = ttk.LabelFrame(content, text="실행 결과", padding=10)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            font=("Consolas", 10),
            relief="flat",
            padx=10,
            pady=10,
        )
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _start_processing(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self.run_button.configure(state="disabled")
        self.status_var.set("주문 처리 중...")
        self.progress.start(12)
        self._write_log("\n" + "=" * 60)
        self._write_log("주문 처리를 시작합니다.")

        thread = threading.Thread(target=self._processing_worker, daemon=True)
        thread.start()

    def _processing_worker(self) -> None:
        capture = StringIO()
        try:
            previous_cwd = Path.cwd()
            os.chdir(BASE_DIR)
            try:
                with redirect_stdout(capture), redirect_stderr(capture):
                    run_order_processing()
            finally:
                os.chdir(previous_cwd)
            self.message_queue.put(("success", capture.getvalue()))
        except Exception:
            details = capture.getvalue() + "\n" + traceback.format_exc()
            self.message_queue.put(("error", details))

    def _poll_messages(self) -> None:
        try:
            while True:
                message_type, message = self.message_queue.get_nowait()
                self._write_log(message)
                self.is_running = False
                self.run_button.configure(state="normal")
                self.progress.stop()
                if message_type == "success":
                    self.status_var.set("처리 완료")
                    messagebox.showinfo("처리 완료", "주문 처리와 발주서 생성 작업이 완료되었습니다.")
                else:
                    self.status_var.set("오류 발생")
                    messagebox.showerror("오류 발생", "처리 중 오류가 발생했습니다. 실행 결과를 확인해 주세요.")
        except queue.Empty:
            pass
        self.after(100, self._poll_messages)

    def _write_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _open_path(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        target = path if path.exists() else path.parent
        if not target.exists():
            messagebox.showwarning("파일 없음", f"아직 생성되지 않았습니다.\n{path}")
            return
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except OSError as error:
            messagebox.showerror("열기 실패", str(error))

    def _show_help(self) -> None:
        messagebox.showinfo(
            "사용 방법",
            "1. data 폴더의 기존 주문 엑셀을 정리합니다.\n"
            "2. 처리할 쿠팡 주문 엑셀 1개를 넣습니다.\n"
            "3. '주문 처리 및 발주서 생성'을 누릅니다.\n"
            "4. 신규 상품은 상품매핑표.xlsx에 정보를 입력합니다.\n"
            "5. 다시 실행하면 미매핑 주문만 재처리됩니다.\n\n"
            "같은 주문은 주문처리이력을 기준으로 중복 발주되지 않습니다.",
        )


if __name__ == "__main__":
    app = BisunERPApp()
    app.mainloop()
