from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from modules.backup_manager.backup_service import BackupService


class BackupPage(ttk.Frame):
    """데이터베이스 백업·복원·자동정리를 관리합니다."""

    def __init__(
        self,
        parent: tk.Misc,
        backup_service: BackupService | None = None,
    ) -> None:
        super().__init__(parent)

        self.backup_service = backup_service or BackupService()
        self.backups: list[dict[str, Any]] = []

        settings = self.backup_service.load_settings()

        self.auto_backup_var = tk.BooleanVar(
            value=bool(
                settings.get(
                    "auto_backup_enabled",
                    True,
                )
            )
        )
        self.startup_backup_var = tk.BooleanVar(
            value=bool(
                settings.get(
                    "auto_backup_on_startup",
                    True,
                )
            )
        )
        self.retention_days_var = tk.StringVar(
            value=str(
                settings.get("retention_days", 30)
            )
        )
        self.max_count_var = tk.StringVar(
            value=str(
                settings.get("max_backup_count", 100)
            )
        )
        self.backup_root_var = tk.StringVar(
            value=str(
                settings.get(
                    "backup_root",
                    self.backup_service.backup_root,
                )
            )
        )
        self.status_var = tk.StringVar(
            value="백업 목록을 불러오는 중입니다."
        )

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self._build_header()
        self._build_summary_area()
        self._build_settings_area()
        self._build_tree_area()
        self._build_bottom_area()

    def _build_header(self) -> None:
        frame = ttk.Frame(
            self,
            padding=(20, 18, 20, 10),
        )
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text="백업 및 복원",
            font=("맑은 고딕", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            frame,
            text=(
                "ERP 데이터베이스를 안전하게 백업하고 "
                "필요할 때 복원합니다."
            ),
        ).grid(
            row=1,
            column=0,
            pady=(5, 0),
            sticky="w",
        )

        ttk.Button(
            frame,
            text="새로고침",
            command=self.refresh,
        ).grid(
            row=0,
            column=1,
            rowspan=2,
            sticky="e",
        )

    def _build_summary_area(self) -> None:
        frame = ttk.Frame(
            self,
            padding=(20, 0, 20, 10),
        )
        frame.grid(row=1, column=0, sticky="ew")

        self.count_var = tk.StringVar(value="0개")
        self.latest_var = tk.StringVar(value="-")
        self.total_size_var = tk.StringVar(value="0 B")

        cards = [
            ("전체 백업", self.count_var),
            ("최근 백업", self.latest_var),
            ("전체 용량", self.total_size_var),
        ]

        for index, (title, variable) in enumerate(cards):
            frame.columnconfigure(index, weight=1)
            card = ttk.LabelFrame(
                frame,
                text=title,
                padding=(15, 9),
            )
            card.grid(
                row=0,
                column=index,
                padx=(0 if index == 0 else 6, 0),
                sticky="ew",
            )
            ttk.Label(
                card,
                textvariable=variable,
                font=("맑은 고딕", 13, "bold"),
            ).pack(anchor="w")

    def _build_settings_area(self) -> None:
        frame = ttk.LabelFrame(
            self,
            text="자동 백업 설정",
            padding=12,
        )
        frame.grid(
            row=2,
            column=0,
            padx=20,
            pady=(0, 10),
            sticky="ew",
        )
        frame.columnconfigure(7, weight=1)

        ttk.Checkbutton(
            frame,
            text="자동 백업 사용",
            variable=self.auto_backup_var,
        ).grid(row=0, column=0, padx=(0, 12))

        ttk.Checkbutton(
            frame,
            text="ERP 시작 시 하루 1회 자동 백업",
            variable=self.startup_backup_var,
        ).grid(row=0, column=1, padx=(0, 18))

        ttk.Label(
            frame,
            text="보관일",
        ).grid(row=0, column=2, padx=(0, 5))
        ttk.Entry(
            frame,
            textvariable=self.retention_days_var,
            width=7,
        ).grid(row=0, column=3, padx=(0, 12))

        ttk.Label(
            frame,
            text="최대 개수",
        ).grid(row=0, column=4, padx=(0, 5))
        ttk.Entry(
            frame,
            textvariable=self.max_count_var,
            width=7,
        ).grid(row=0, column=5, padx=(0, 12))

        ttk.Button(
            frame,
            text="설정 저장",
            command=self.save_settings,
        ).grid(row=0, column=6)

        path_frame = ttk.Frame(frame)
        path_frame.grid(
            row=1,
            column=0,
            columnspan=8,
            pady=(10, 0),
            sticky="ew",
        )
        path_frame.columnconfigure(1, weight=1)

        ttk.Label(
            path_frame,
            text="백업 폴더",
        ).grid(row=0, column=0, padx=(0, 8))

        ttk.Entry(
            path_frame,
            textvariable=self.backup_root_var,
        ).grid(row=0, column=1, sticky="ew")

        ttk.Button(
            path_frame,
            text="폴더 선택",
            command=self.choose_backup_folder,
        ).grid(row=0, column=2, padx=(8, 0))

    def _build_tree_area(self) -> None:
        frame = ttk.Frame(
            self,
            padding=(20, 0, 20, 0),
        )
        frame.grid(row=3, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        columns = (
            "created_at",
            "filename",
            "size_text",
            "folder",
            "path",
        )

        self.tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        headings = {
            "created_at": "백업일시",
            "filename": "파일명",
            "size_text": "용량",
            "folder": "폴더",
            "path": "전체 경로",
        }

        widths = {
            "created_at": 155,
            "filename": 300,
            "size_text": 95,
            "folder": 110,
            "path": 480,
        }

        for column in columns:
            self.tree.heading(
                column,
                text=headings[column],
            )
            self.tree.column(
                column,
                width=widths[column],
                minwidth=70,
                anchor=(
                    "center"
                    if column in {
                        "created_at",
                        "size_text",
                        "folder",
                    }
                    else "w"
                ),
            )

        y_scroll = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.tree.yview,
        )
        x_scroll = ttk.Scrollbar(
            frame,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        self.tree.bind(
            "<Double-1>",
            self._open_selected_file,
        )

    def _build_bottom_area(self) -> None:
        frame = ttk.Frame(
            self,
            padding=(20, 12, 20, 18),
        )
        frame.grid(row=4, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            textvariable=self.status_var,
        ).grid(row=0, column=0, sticky="w")

        ttk.Button(
            frame,
            text="백업 폴더 열기",
            command=self.open_backup_folder,
        ).grid(row=0, column=1, padx=(8, 0))

        ttk.Button(
            frame,
            text="지금 백업",
            command=self.create_backup,
        ).grid(row=0, column=2, padx=(8, 0))

        ttk.Button(
            frame,
            text="외부 DB 복원",
            command=self.restore_external_backup,
        ).grid(row=0, column=3, padx=(8, 0))

        ttk.Button(
            frame,
            text="선택 백업 복원",
            command=self.restore_selected_backup,
        ).grid(row=0, column=4, padx=(8, 0))

        ttk.Button(
            frame,
            text="선택 삭제",
            command=self.delete_selected_backup,
        ).grid(row=0, column=5, padx=(8, 0))

    def refresh(self) -> None:
        try:
            self.backups = self.backup_service.list_backups()

            self.tree.delete(
                *self.tree.get_children()
            )

            for index, item in enumerate(self.backups):
                self.tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        item.get("created_at") or "",
                        item.get("filename") or "",
                        item.get("size_text") or "",
                        item.get("folder") or "",
                        item.get("path") or "",
                    ),
                )

            total_size = sum(
                int(item.get("size_bytes") or 0)
                for item in self.backups
            )

            self.count_var.set(
                f"{len(self.backups):,}개"
            )
            self.latest_var.set(
                self.backups[0]["created_at"]
                if self.backups
                else "-"
            )
            self.total_size_var.set(
                self.backup_service._format_size(
                    total_size
                )
            )
            self.status_var.set(
                f"백업 {len(self.backups):,}개를 표시했습니다."
            )

        except Exception as error:
            messagebox.showerror(
                "백업 목록 오류",
                f"백업 목록을 불러오지 못했습니다.\n\n{error}",
                parent=self,
            )

    def create_backup(self) -> None:
        try:
            self.status_var.set(
                "데이터베이스를 백업하고 있습니다."
            )
            self.update_idletasks()

            result = self.backup_service.create_backup(
                reason="수동"
            )

            messagebox.showinfo(
                "백업 완료",
                (
                    "데이터베이스 백업을 완료했습니다.\n\n"
                    f"파일: {result['filename']}\n"
                    f"용량: "
                    f"{self.backup_service._format_size(result['size_bytes'])}"
                ),
                parent=self,
            )
            self.refresh()

        except Exception as error:
            messagebox.showerror(
                "백업 오류",
                f"백업 중 오류가 발생했습니다.\n\n{error}",
                parent=self,
            )

    def restore_selected_backup(self) -> None:
        selected = self._get_selected_backup()

        if not selected:
            messagebox.showwarning(
                "백업 복원",
                "복원할 백업을 선택하세요.",
                parent=self,
            )
            return

        self._restore_backup(
            Path(str(selected["path"]))
        )

    def restore_external_backup(self) -> None:
        selected_path = filedialog.askopenfilename(
            parent=self,
            title="복원할 데이터베이스 선택",
            filetypes=[
                ("SQLite 데이터베이스", "*.db"),
                ("모든 파일", "*.*"),
            ],
        )

        if not selected_path:
            return

        self._restore_backup(Path(selected_path))

    def _restore_backup(self, path: Path) -> None:
        confirmed = messagebox.askyesno(
            "데이터베이스 복원 확인",
            (
                "선택한 백업으로 현재 ERP 데이터를 "
                "교체합니다.\n\n"
                "현재 데이터는 복원 직전에 자동으로 "
                "안전 백업됩니다.\n\n"
                "계속하시겠습니까?"
            ),
            parent=self,
        )

        if not confirmed:
            return

        try:
            result = self.backup_service.restore_backup(
                path
            )

            messagebox.showinfo(
                "복원 완료",
                (
                    "데이터베이스 복원이 완료되었습니다.\n\n"
                    "ERP를 완전히 종료한 뒤 다시 실행해야 "
                    "복원된 데이터가 정확히 적용됩니다."
                ),
                parent=self,
            )
            self.refresh()

        except Exception as error:
            messagebox.showerror(
                "복원 오류",
                f"복원 중 오류가 발생했습니다.\n\n{error}",
                parent=self,
            )

    def delete_selected_backup(self) -> None:
        selected = self._get_selected_backup()

        if not selected:
            messagebox.showwarning(
                "백업 삭제",
                "삭제할 백업을 선택하세요.",
                parent=self,
            )
            return

        confirmed = messagebox.askyesno(
            "백업 삭제 확인",
            (
                f"{selected['filename']}\n\n"
                "이 백업 파일을 삭제하시겠습니까?"
            ),
            parent=self,
        )

        if not confirmed:
            return

        try:
            self.backup_service.delete_backup(
                str(selected["path"])
            )
            self.refresh()
        except Exception as error:
            messagebox.showerror(
                "백업 삭제 오류",
                f"백업을 삭제하지 못했습니다.\n\n{error}",
                parent=self,
            )

    def save_settings(self) -> None:
        try:
            settings = {
                "auto_backup_enabled": (
                    self.auto_backup_var.get()
                ),
                "auto_backup_on_startup": (
                    self.startup_backup_var.get()
                ),
                "retention_days": int(
                    self.retention_days_var.get()
                ),
                "max_backup_count": int(
                    self.max_count_var.get()
                ),
                "backup_root": (
                    self.backup_root_var.get().strip()
                ),
            }

            self.backup_service.save_settings(
                settings
            )

            messagebox.showinfo(
                "설정 저장",
                "자동 백업 설정을 저장했습니다.",
                parent=self,
            )
            self.refresh()

        except ValueError:
            messagebox.showwarning(
                "설정 확인",
                "보관일과 최대 개수는 숫자로 입력하세요.",
                parent=self,
            )
        except Exception as error:
            messagebox.showerror(
                "설정 저장 오류",
                f"설정을 저장하지 못했습니다.\n\n{error}",
                parent=self,
            )

    def choose_backup_folder(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="백업 폴더 선택",
            initialdir=self.backup_root_var.get(),
        )

        if selected:
            self.backup_root_var.set(selected)

    def open_backup_folder(self) -> None:
        path = Path(
            self.backup_root_var.get().strip()
            or self.backup_service.backup_root
        )
        path.mkdir(parents=True, exist_ok=True)

        try:
            os.startfile(path)
        except AttributeError:
            messagebox.showinfo(
                "백업 폴더",
                str(path),
                parent=self,
            )
        except OSError as error:
            messagebox.showerror(
                "폴더 열기 오류",
                f"백업 폴더를 열지 못했습니다.\n\n{error}",
                parent=self,
            )

    def _open_selected_file(
        self,
        event: tk.Event | None = None,
    ) -> None:
        selected = self._get_selected_backup()
        if not selected:
            return

        path = Path(str(selected["path"]))

        try:
            os.startfile(path.parent)
        except (AttributeError, OSError):
            messagebox.showinfo(
                "백업 위치",
                str(path),
                parent=self,
            )

    def _get_selected_backup(
        self,
    ) -> dict[str, Any] | None:
        selected_items = self.tree.selection()

        if not selected_items:
            return None

        index = int(selected_items[0])

        if index < 0 or index >= len(self.backups):
            return None

        return self.backups[index]