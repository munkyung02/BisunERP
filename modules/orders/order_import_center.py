from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from modules.orders.order_import_service import OrderImportService


class OrderImportCenter(tk.Toplevel):
    """
    여러 판매채널 주문 엑셀을 한 번에 분석하고 등록하는 화면입니다.

    현재 지원:
    - 쿠팡

    구조상 이후 스마트스토어, ESM, 카카오, 롯데온 등의
    주문 파서를 추가하면 이 화면은 수정 없이 그대로 사용할 수 있습니다.
    """

    SUPPORTED_EXTENSIONS = {
        ".xlsx",
        ".xls",
    }

    def __init__(
        self,
        parent: tk.Misc,
        service: OrderImportService,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)

        self.service = service
        self.refresh_callback = refresh_callback

        self.selected_files: list[Path] = []
        self.preview: dict[str, Any] | None = None
        self.file_rows: dict[str, dict[str, Any]] = {}
        self.order_rows: dict[str, dict[str, Any]] = {}

        self.title("비선상회 ERP - 주문 가져오기 센터")
        self.geometry("1450x820")
        self.minsize(1150, 680)
        self.transient(parent.winfo_toplevel())

        self.total_file_var = tk.StringVar(value="선택 파일 0개")
        self.success_file_var = tk.StringVar(value="분석 성공 0개")
        self.failed_file_var = tk.StringVar(value="분석 실패 0개")
        self.new_count_var = tk.StringVar(value="신규 주문 0건")
        self.duplicate_count_var = tk.StringVar(value="중복 주문 0건")
        self.error_count_var = tk.StringVar(value="오류 주문 0건")
        self.status_var = tk.StringVar(value="주문서 파일을 추가해주세요.")

        self._configure_style()
        self._create_ui()

        self.grab_set()
        self.focus_force()

    # =========================================================
    # 스타일
    # =========================================================

    def _configure_style(self) -> None:
        style = ttk.Style(self)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "ImportCenter.Treeview",
            font=("맑은 고딕", 10),
            rowheight=31,
        )

        style.configure(
            "ImportCenter.Treeview.Heading",
            font=("맑은 고딕", 10, "bold"),
        )

        style.configure(
            "ImportCenter.Primary.TButton",
            font=("맑은 고딕", 10, "bold"),
            padding=(15, 9),
        )

        style.configure(
            "ImportCenter.Toolbar.TButton",
            font=("맑은 고딕", 10),
            padding=(12, 8),
        )

    # =========================================================
    # 화면 구성
    # =========================================================

    def _create_ui(self) -> None:
        self._create_header()
        self._create_action_area()
        self._create_summary_area()
        self._create_content_area()
        self._create_bottom_area()

    def _create_header(self) -> None:
        header = tk.Frame(
            self,
            padx=24,
            pady=17,
        )
        header.pack(fill="x")

        tk.Label(
            header,
            text="주문 가져오기 센터",
            font=("맑은 고딕", 23, "bold"),
        ).pack(side="left")

        tk.Label(
            header,
            text=(
                "여러 판매채널 주문서를 한 번에 선택하고 "
                "자동 판별·중복 검사·신규 주문 등록을 진행합니다."
            ),
            font=("맑은 고딕", 10),
        ).pack(
            side="left",
            padx=(15, 0),
            pady=(8, 0),
        )

    def _create_action_area(self) -> None:
        frame = tk.Frame(
            self,
            padx=24,
            pady=5,
        )
        frame.pack(fill="x")

        ttk.Button(
            frame,
            text="파일 추가",
            command=self.add_files,
            style="ImportCenter.Primary.TButton",
        ).pack(
            side="left",
            padx=(0, 8),
        )

        ttk.Button(
            frame,
            text="선택 파일 제거",
            command=self.remove_selected_files,
            style="ImportCenter.Toolbar.TButton",
        ).pack(
            side="left",
            padx=(0, 8),
        )

        ttk.Button(
            frame,
            text="전체 비우기",
            command=self.clear_files,
            style="ImportCenter.Toolbar.TButton",
        ).pack(
            side="left",
            padx=(0, 8),
        )

        ttk.Button(
            frame,
            text="분석 및 미리보기",
            command=self.analyze_files,
            style="ImportCenter.Primary.TButton",
        ).pack(
            side="left",
            padx=(12, 8),
        )

        ttk.Button(
            frame,
            text="신규 주문 등록",
            command=self.import_new_orders,
            style="ImportCenter.Primary.TButton",
        ).pack(
            side="right",
        )

    def _create_summary_area(self) -> None:
        frame = tk.Frame(
            self,
            padx=24,
            pady=10,
        )
        frame.pack(fill="x")

        summary_vars = [
            self.total_file_var,
            self.success_file_var,
            self.failed_file_var,
            self.new_count_var,
            self.duplicate_count_var,
            self.error_count_var,
        ]

        for index, variable in enumerate(summary_vars):
            card = tk.Frame(
                frame,
                padx=14,
                pady=11,
                relief="ridge",
                borderwidth=1,
            )
            card.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0, 8),
            )

            tk.Label(
                card,
                textvariable=variable,
                font=("맑은 고딕", 10, "bold"),
            ).pack()

            frame.grid_columnconfigure(
                index,
                weight=1,
            )

    def _create_content_area(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(
            fill="both",
            expand=True,
            padx=24,
            pady=(0, 12),
        )

        self.file_tab = tk.Frame(notebook)
        self.order_tab = tk.Frame(notebook)
        self.error_tab = tk.Frame(notebook)

        notebook.add(
            self.file_tab,
            text="선택 파일",
        )
        notebook.add(
            self.order_tab,
            text="주문 미리보기",
        )
        notebook.add(
            self.error_tab,
            text="오류 및 안내",
        )

        self._create_file_table()
        self._create_order_table()
        self._create_error_view()

    def _create_file_table(self) -> None:
        frame = tk.Frame(
            self.file_tab,
            padx=10,
            pady=10,
        )
        frame.pack(fill="both", expand=True)

        columns = (
            "file_name",
            "platform",
            "excel_rows",
            "order_count",
            "new_count",
            "duplicate_count",
            "error_count",
            "status",
        )

        self.file_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="extended",
            style="ImportCenter.Treeview",
        )

        headings = {
            "file_name": "파일명",
            "platform": "자동 판별",
            "excel_rows": "엑셀 행",
            "order_count": "주문",
            "new_count": "신규",
            "duplicate_count": "중복",
            "error_count": "오류",
            "status": "상태",
        }

        widths = {
            "file_name": 420,
            "platform": 110,
            "excel_rows": 85,
            "order_count": 85,
            "new_count": 85,
            "duplicate_count": 85,
            "error_count": 85,
            "status": 250,
        }

        anchors = {
            "file_name": "w",
            "platform": "center",
            "excel_rows": "center",
            "order_count": "center",
            "new_count": "center",
            "duplicate_count": "center",
            "error_count": "center",
            "status": "w",
        }

        for column in columns:
            self.file_tree.heading(
                column,
                text=headings[column],
            )
            self.file_tree.column(
                column,
                width=widths[column],
                minwidth=60,
                anchor=anchors[column],
                stretch=(
                    column in {
                        "file_name",
                        "status",
                    }
                ),
            )

        y_scroll = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.file_tree.yview,
        )
        x_scroll = ttk.Scrollbar(
            frame,
            orient="horizontal",
            command=self.file_tree.xview,
        )

        self.file_tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        self.file_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        y_scroll.grid(
            row=0,
            column=1,
            sticky="ns",
        )
        x_scroll.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

    def _create_order_table(self) -> None:
        frame = tk.Frame(
            self.order_tab,
            padx=10,
            pady=10,
        )
        frame.pack(fill="both", expand=True)

        columns = (
            "status",
            "platform",
            "order_number",
            "ordered_at",
            "receiver_name",
            "receiver_phone",
            "item_summary",
            "total_quantity",
            "total_amount",
            "source_file",
            "message",
        )

        self.order_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            style="ImportCenter.Treeview",
        )

        headings = {
            "status": "구분",
            "platform": "플랫폼",
            "order_number": "주문번호",
            "ordered_at": "주문일시",
            "receiver_name": "수취인",
            "receiver_phone": "연락처",
            "item_summary": "주문상품",
            "total_quantity": "수량",
            "total_amount": "결제금액",
            "source_file": "원본 파일",
            "message": "안내",
        }

        widths = {
            "status": 70,
            "platform": 80,
            "order_number": 140,
            "ordered_at": 135,
            "receiver_name": 85,
            "receiver_phone": 115,
            "item_summary": 340,
            "total_quantity": 65,
            "total_amount": 100,
            "source_file": 180,
            "message": 240,
        }

        anchors = {
            "status": "center",
            "platform": "center",
            "order_number": "center",
            "ordered_at": "center",
            "receiver_name": "center",
            "receiver_phone": "center",
            "item_summary": "w",
            "total_quantity": "center",
            "total_amount": "e",
            "source_file": "w",
            "message": "w",
        }

        for column in columns:
            self.order_tree.heading(
                column,
                text=headings[column],
            )
            self.order_tree.column(
                column,
                width=widths[column],
                minwidth=55,
                anchor=anchors[column],
                stretch=(
                    column in {
                        "item_summary",
                        "message",
                    }
                ),
            )

        self.order_tree.tag_configure(
            "new",
            background="#eef8ee",
        )
        self.order_tree.tag_configure(
            "duplicate",
            background="#fff7df",
        )
        self.order_tree.tag_configure(
            "error",
            background="#fdeaea",
        )

        y_scroll = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.order_tree.yview,
        )
        x_scroll = ttk.Scrollbar(
            frame,
            orient="horizontal",
            command=self.order_tree.xview,
        )

        self.order_tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        self.order_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        y_scroll.grid(
            row=0,
            column=1,
            sticky="ns",
        )
        x_scroll.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

    def _create_error_view(self) -> None:
        frame = tk.Frame(
            self.error_tab,
            padx=10,
            pady=10,
        )
        frame.pack(fill="both", expand=True)

        self.error_text = tk.Text(
            frame,
            wrap="word",
            font=("맑은 고딕", 10),
            padx=12,
            pady=12,
            state="disabled",
        )

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.error_text.yview,
        )

        self.error_text.configure(
            yscrollcommand=scrollbar.set,
        )

        self.error_text.pack(
            side="left",
            fill="both",
            expand=True,
        )
        scrollbar.pack(
            side="right",
            fill="y",
        )

        self._set_error_text(
            "분석 중 발생한 파일 오류와 주문 오류가 여기에 표시됩니다."
        )

    def _create_bottom_area(self) -> None:
        status_bar = tk.Label(
            self,
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
    # 파일 관리
    # =========================================================

    def add_files(self) -> None:
        selected = filedialog.askopenfilenames(
            parent=self,
            title="주문 엑셀 파일 선택",
            filetypes=[
                (
                    "엑셀 파일",
                    "*.xlsx *.xls",
                ),
                (
                    "모든 파일",
                    "*.*",
                ),
            ],
        )

        if not selected:
            return

        existing = {
            str(path.resolve()).lower()
            for path in self.selected_files
        }

        added_count = 0
        skipped_count = 0

        for raw_path in selected:
            path = Path(raw_path)

            if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                skipped_count += 1
                continue

            normalized = str(path.resolve()).lower()

            if normalized in existing:
                skipped_count += 1
                continue

            self.selected_files.append(path)
            existing.add(normalized)
            added_count += 1

        self.preview = None
        self._refresh_file_selection_table()
        self._clear_order_table()
        self._reset_preview_counts()

        self.status_var.set(
            f"파일 추가 완료: {added_count:,}개"
            + (
                f" / 제외 {skipped_count:,}개"
                if skipped_count
                else ""
            )
        )

    def remove_selected_files(self) -> None:
        selection = self.file_tree.selection()

        if not selection:
            messagebox.showwarning(
                "파일 선택",
                "제거할 파일을 선택해주세요.",
                parent=self,
            )
            return

        remove_paths = {
            self.file_rows[item_id]["path"]
            for item_id in selection
            if item_id in self.file_rows
        }

        self.selected_files = [
            path
            for path in self.selected_files
            if path not in remove_paths
        ]

        self.preview = None
        self._refresh_file_selection_table()
        self._clear_order_table()
        self._reset_preview_counts()

        self.status_var.set(
            f"선택 파일 제거 완료: {len(remove_paths):,}개"
        )

    def clear_files(self) -> None:
        if not self.selected_files:
            return

        confirmed = messagebox.askyesno(
            "전체 비우기",
            "선택한 주문서 파일을 모두 목록에서 제거하시겠습니까?",
            parent=self,
        )

        if not confirmed:
            return

        self.selected_files.clear()
        self.preview = None

        self._refresh_file_selection_table()
        self._clear_order_table()
        self._reset_preview_counts()
        self._set_error_text(
            "분석 중 발생한 파일 오류와 주문 오류가 여기에 표시됩니다."
        )

        self.status_var.set(
            "선택 파일 목록을 비웠습니다."
        )

    # =========================================================
    # 분석
    # =========================================================

    def analyze_files(self) -> None:
        if not self.selected_files:
            messagebox.showwarning(
                "파일 없음",
                "분석할 주문 엑셀 파일을 먼저 추가해주세요.",
                parent=self,
            )
            return

        try:
            self.status_var.set(
                "주문서 자동 판별 및 미리보기 분석 중..."
            )
            self.update_idletasks()

            self.preview = (
                self.service.preview_multiple_excels(
                    self.selected_files
                )
            )

            self._render_analysis_result()
            self.status_var.set(
                "분석 완료: "
                f"신규 {self.preview.get('new_count', 0):,}건 / "
                f"중복 {self.preview.get('duplicate_count', 0):,}건 / "
                f"오류 {self.preview.get('error_count', 0):,}건"
            )

        except Exception as error:
            self.preview = None
            self.status_var.set(
                "주문서 분석 오류"
            )

            messagebox.showerror(
                "분석 오류",
                "주문서 파일을 분석하지 못했습니다.\n\n"
                f"{error}",
                parent=self,
            )

    def _render_analysis_result(self) -> None:
        if self.preview is None:
            return

        self._render_file_results()
        self._render_order_results()
        self._render_error_results()
        self._refresh_summary_counts()

    def _render_file_results(self) -> None:
        self._clear_file_table()
        self.file_rows.clear()

        file_previews = list(
            self.preview.get("files") or []
        )
        file_errors = list(
            self.preview.get("file_errors") or []
        )

        path_by_name = {
            path.name: path
            for path in self.selected_files
        }

        index = 0

        for result in file_previews:
            index += 1
            item_id = f"file_{index}"

            source_file = str(
                result.get("source_file") or ""
            )
            path = path_by_name.get(
                source_file,
                Path(source_file),
            )

            self.file_rows[item_id] = {
                "path": path,
                "result": result,
            }

            self.file_tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    source_file,
                    result.get("platform", ""),
                    self._format_number(
                        result.get("excel_row_count")
                    ),
                    self._format_number(
                        result.get("parsed_order_count")
                    ),
                    self._format_number(
                        result.get("new_count")
                    ),
                    self._format_number(
                        result.get("duplicate_count")
                    ),
                    self._format_number(
                        result.get("error_count")
                    ),
                    "분석 완료",
                ),
            )

        for error_data in file_errors:
            index += 1
            item_id = f"file_{index}"

            source_file = str(
                error_data.get("source_file") or ""
            )
            path = path_by_name.get(
                source_file,
                Path(
                    error_data.get("file_path")
                    or source_file
                ),
            )

            self.file_rows[item_id] = {
                "path": path,
                "result": error_data,
            }

            self.file_tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    source_file,
                    "판별 실패",
                    "0",
                    "0",
                    "0",
                    "0",
                    "0",
                    error_data.get("error", ""),
                ),
            )

    def _render_order_results(self) -> None:
        self._clear_order_table()
        self.order_rows.clear()

        for index, row in enumerate(
            self.preview.get("rows") or [],
            start=1,
        ):
            item_id = f"order_{index}"

            self.order_rows[item_id] = row

            status = str(
                row.get("status") or "error"
            )

            self.order_tree.insert(
                "",
                "end",
                iid=item_id,
                tags=(status,),
                values=(
                    row.get("status_text", ""),
                    row.get("platform", ""),
                    row.get("order_number", ""),
                    row.get("ordered_at", ""),
                    row.get("receiver_name", ""),
                    row.get("receiver_phone", ""),
                    row.get("item_summary", ""),
                    self._format_number(
                        row.get("total_quantity")
                    ),
                    self._format_currency(
                        row.get("total_amount")
                    ),
                    row.get("source_file", ""),
                    row.get("message", ""),
                ),
            )

    def _render_error_results(self) -> None:
        lines: list[str] = []

        file_errors = list(
            self.preview.get("file_errors") or []
        )

        if file_errors:
            lines.append("[파일 분석 오류]")

            for error_data in file_errors:
                lines.append(
                    f"• {error_data.get('source_file', '')}"
                )
                lines.append(
                    f"  {error_data.get('error', '')}"
                )
                lines.append("")

        order_errors = [
            row
            for row in self.preview.get("rows") or []
            if row.get("status") == "error"
        ]

        if order_errors:
            lines.append("[주문 데이터 오류]")

            for row in order_errors:
                lines.append(
                    "• "
                    f"{row.get('platform', '')} / "
                    f"{row.get('order_number', '') or '(주문번호 없음)'} / "
                    f"{row.get('source_file', '')}"
                )
                lines.append(
                    f"  {row.get('message', '')}"
                )
                lines.append("")

        if not lines:
            lines.append(
                "파일 분석 오류와 주문 데이터 오류가 없습니다."
            )

        self._set_error_text(
            "\n".join(lines)
        )

    # =========================================================
    # 주문 등록
    # =========================================================

    def import_new_orders(self) -> None:
        if self.preview is None:
            messagebox.showwarning(
                "미리보기 필요",
                "먼저 주문서 분석 및 미리보기를 실행해주세요.",
                parent=self,
            )
            return

        new_count = int(
            self.preview.get("new_count", 0) or 0
        )

        if new_count <= 0:
            messagebox.showinfo(
                "등록할 주문 없음",
                "등록할 신규 주문이 없습니다.",
                parent=self,
            )
            return

        confirmed = messagebox.askyesno(
            "신규 주문 등록",
            f"신규 주문 {new_count:,}건을 ERP에 등록합니다.\n\n"
            "중복 주문과 오류 주문은 자동으로 제외됩니다.\n"
            "등록 후 이번 주문만 자동 상품매핑합니다.\n\n"
            "계속하시겠습니까?",
            parent=self,
        )

        if not confirmed:
            return

        try:
            self.status_var.set(
                "신규 주문 저장 및 자동 상품매핑 중..."
            )
            self.update_idletasks()

            result = (
                self.service.import_preview_orders(
                    self.preview
                )
            )

            created_count = int(
                result.get("created_count", 0) or 0
            )
            duplicate_count = int(
                result.get("duplicate_count", 0) or 0
            )
            failed_count = int(
                result.get("failed_count", 0) or 0
            )
            mapped_count = int(
                result.get("mapping_mapped_count", 0) or 0
            )
            saved_rule_count = int(
                result.get("mapping_saved_rule_count", 0) or 0
            )
            unmatched_count = int(
                result.get("mapping_unmatched_count", 0) or 0
            )
            ambiguous_count = int(
                result.get("mapping_ambiguous_count", 0) or 0
            )

            if callable(self.refresh_callback):
                self.refresh_callback()

            messagebox.showinfo(
                "주문 등록 완료",
                "주문 가져오기가 완료되었습니다.\n\n"
                f"신규 등록: {created_count:,}건\n"
                f"저장 중 중복 제외: {duplicate_count:,}건\n"
                f"저장 실패: {failed_count:,}건\n\n"
                f"저장 규칙 매핑: {saved_rule_count:,}건\n"
                f"자동매핑 성공: {mapped_count:,}건\n"
                f"미매핑: {unmatched_count:,}건\n"
                f"중복 후보: {ambiguous_count:,}건",
                parent=self,
            )

            self.status_var.set(
                f"주문 등록 완료: {created_count:,}건"
            )

            # 등록 직후 다시 분석하여 방금 저장한 주문을 중복으로 표시합니다.
            self.analyze_files()

        except Exception as error:
            self.status_var.set(
                "신규 주문 등록 오류"
            )

            messagebox.showerror(
                "등록 오류",
                "신규 주문을 등록하지 못했습니다.\n\n"
                f"{error}",
                parent=self,
            )

    # =========================================================
    # 표시 및 초기화
    # =========================================================

    def _refresh_file_selection_table(self) -> None:
        self._clear_file_table()
        self.file_rows.clear()

        for index, path in enumerate(
            self.selected_files,
            start=1,
        ):
            item_id = f"selected_{index}"

            self.file_rows[item_id] = {
                "path": path,
            }

            self.file_tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    path.name,
                    "분석 전",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    str(path.parent),
                ),
            )

        self.total_file_var.set(
            f"선택 파일 {len(self.selected_files):,}개"
        )

    def _refresh_summary_counts(self) -> None:
        if self.preview is None:
            self._reset_preview_counts()
            return

        self.total_file_var.set(
            f"선택 파일 {self.preview.get('file_count', 0):,}개"
        )
        self.success_file_var.set(
            f"분석 성공 {self.preview.get('success_file_count', 0):,}개"
        )
        self.failed_file_var.set(
            f"분석 실패 {self.preview.get('failed_file_count', 0):,}개"
        )
        self.new_count_var.set(
            f"신규 주문 {self.preview.get('new_count', 0):,}건"
        )
        self.duplicate_count_var.set(
            f"중복 주문 {self.preview.get('duplicate_count', 0):,}건"
        )
        self.error_count_var.set(
            f"오류 주문 {self.preview.get('error_count', 0):,}건"
        )

    def _reset_preview_counts(self) -> None:
        self.total_file_var.set(
            f"선택 파일 {len(self.selected_files):,}개"
        )
        self.success_file_var.set(
            "분석 성공 0개"
        )
        self.failed_file_var.set(
            "분석 실패 0개"
        )
        self.new_count_var.set(
            "신규 주문 0건"
        )
        self.duplicate_count_var.set(
            "중복 주문 0건"
        )
        self.error_count_var.set(
            "오류 주문 0건"
        )

    def _clear_file_table(self) -> None:
        children = self.file_tree.get_children()

        if children:
            self.file_tree.delete(*children)

    def _clear_order_table(self) -> None:
        children = self.order_tree.get_children()

        if children:
            self.order_tree.delete(*children)

        self.order_rows.clear()

    def _set_error_text(
        self,
        text: str,
    ) -> None:
        self.error_text.configure(
            state="normal",
        )
        self.error_text.delete(
            "1.0",
            "end",
        )
        self.error_text.insert(
            "1.0",
            text,
        )
        self.error_text.configure(
            state="disabled",
        )

    @staticmethod
    def _format_number(
        value: Any,
    ) -> str:
        try:
            return f"{int(value or 0):,}"
        except (TypeError, ValueError):
            return "0"

    @staticmethod
    def _format_currency(
        value: Any,
    ) -> str:
        try:
            return f"{int(value or 0):,}원"
        except (TypeError, ValueError):
            return "0원"