from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.widgets import (
    ERPBaseSearch,
    ERPButton,
    ERPTable,
)
from modules.suppliers.supplier_dialog import SupplierDialog
from modules.suppliers.supplier_repository import SupplierRepository


class SupplierPage(QWidget):
    """공급처 등록, 조회, 수정, 상태 변경 화면입니다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.repository = SupplierRepository()

        self._build_ui()
        self._connect_signals()
        self.load_suppliers()

    def _build_ui(self) -> None:
        """공급처관리 화면을 구성합니다."""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(16)

        title_label = QLabel("공급처관리")
        title_label.setStyleSheet(
            """
            QLabel {
                font-size: 26px;
                font-weight: 700;
                color: #0F172A;
            }
            """
        )

        description_label = QLabel(
            "상품 공급처와 담당자, 연락처 및 정산계좌 정보를 관리합니다."
        )
        description_label.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: #64748B;
            }
            """
        )

        main_layout.addWidget(title_label)
        main_layout.addWidget(description_label)

        self.search_widget = ERPBaseSearch(
            "공급처명, 담당자, 연락처, 계좌번호를 검색하세요."
        )
        main_layout.addWidget(self.search_widget)

        button_layout = QHBoxLayout()

        self.add_button = ERPButton(
            "공급처 등록",
            "primary",
        )
        self.edit_button = ERPButton(
            "수정",
            "secondary",
        )
        self.active_button = ERPButton(
            "활성/비활성",
            "secondary",
        )
        self.refresh_button = ERPButton(
            "새로고침",
            "secondary",
        )

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.active_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

        self.table = ERPTable()

        self.table.set_headers(
            [
                "공급처코드",
                "공급처명",
                "담당자",
                "연락처",
                "이메일",
                "은행",
                "계좌번호",
                "예금주",
                "상태",
            ]
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        main_layout.addWidget(self.table)

        self.status_label = QLabel("공급처 0개")
        self.status_label.setStyleSheet(
            """
            QLabel {
                color: #64748B;
                font-size: 13px;
            }
            """
        )

        main_layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        """검색창과 버튼 이벤트를 연결합니다."""

        self.search_widget.search_requested.connect(
            self.load_suppliers
        )

        self.search_widget.reset_requested.connect(
            lambda: self.load_suppliers()
        )

        self.add_button.clicked.connect(
            self.open_create_dialog
        )

        self.edit_button.clicked.connect(
            self.open_update_dialog
        )

        self.active_button.clicked.connect(
            self.toggle_selected_supplier
        )

        self.refresh_button.clicked.connect(
            lambda: self.load_suppliers()
        )

        self.table.cellDoubleClicked.connect(
            self._handle_table_double_click
        )

    def load_suppliers(
        self,
        keyword: str | None = None,
    ) -> None:
        """공급처 목록을 DB에서 조회하여 테이블에 표시합니다."""

        try:
            suppliers = self.repository.get_suppliers(
                keyword=keyword,
                active_only=False,
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "조회 오류",
                f"공급처 목록을 불러오지 못했습니다.\n\n{error}",
            )
            return

        self.table.setRowCount(0)

        for supplier in suppliers:
            row_index = self.table.rowCount()
            self.table.insertRow(row_index)

            values = [
                supplier.get("supplier_code"),
                supplier.get("supplier_name"),
                supplier.get("contact_name"),
                supplier.get("phone"),
                supplier.get("email"),
                supplier.get("bank_name"),
                supplier.get("bank_account"),
                supplier.get("account_holder"),
                (
                    "활성"
                    if supplier.get("is_active")
                    else "비활성"
                ),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(
                    "" if value is None else str(value)
                )

                if column_index == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        supplier["id"],
                    )

                if column_index == 8:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )

                self.table.setItem(
                    row_index,
                    column_index,
                    item,
                )

        self.table.resizeColumnsToContents()

        active_count = sum(
            1
            for supplier in suppliers
            if supplier.get("is_active")
        )

        self.status_label.setText(
            f"전체 {len(suppliers)}개 · 활성 {active_count}개"
        )

    def open_create_dialog(self) -> None:
        """공급처 등록창을 엽니다."""

        dialog = SupplierDialog(
            repository=self.repository,
            parent=self,
        )

        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            self.load_suppliers()

            QMessageBox.information(
                self,
                "등록 완료",
                "공급처가 등록되었습니다.",
            )

    def open_update_dialog(self) -> None:
        """선택한 공급처 수정창을 엽니다."""

        supplier_id = self.get_selected_supplier_id()

        if supplier_id is None:
            QMessageBox.warning(
                self,
                "공급처 선택",
                "수정할 공급처를 먼저 선택해 주세요.",
            )
            return

        dialog = SupplierDialog(
            repository=self.repository,
            supplier_id=supplier_id,
            parent=self,
        )

        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            self.load_suppliers()

            QMessageBox.information(
                self,
                "수정 완료",
                "공급처 정보가 수정되었습니다.",
            )

    def toggle_selected_supplier(self) -> None:
        """선택한 공급처의 활성·비활성 상태를 전환합니다."""

        supplier_id = self.get_selected_supplier_id()

        if supplier_id is None:
            QMessageBox.warning(
                self,
                "공급처 선택",
                "상태를 변경할 공급처를 먼저 선택해 주세요.",
            )
            return

        supplier = self.repository.get_supplier_by_id(
            supplier_id
        )

        if supplier is None:
            QMessageBox.warning(
                self,
                "조회 오류",
                "선택한 공급처 정보를 찾을 수 없습니다.",
            )
            return

        current_active = bool(
            supplier.get("is_active")
        )
        new_active = not current_active

        new_status_text = (
            "활성"
            if new_active
            else "비활성"
        )

        answer = QMessageBox.question(
            self,
            "상태 변경",
            (
                f"{supplier['supplier_name']} 공급처를 "
                f"{new_status_text} 상태로 변경하시겠습니까?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            changed_count = (
                self.repository.set_supplier_active(
                    supplier_id,
                    new_active,
                )
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "변경 오류",
                f"공급처 상태를 변경하지 못했습니다.\n\n{error}",
            )
            return

        if changed_count == 0:
            QMessageBox.warning(
                self,
                "변경 실패",
                "변경할 공급처를 찾지 못했습니다.",
            )
            return

        self.load_suppliers()

        QMessageBox.information(
            self,
            "변경 완료",
            f"공급처가 {new_status_text} 상태로 변경되었습니다.",
        )

    def get_selected_supplier_id(
        self,
    ) -> int | None:
        """현재 선택된 행의 공급처 ID를 반환합니다."""

        selected_rows = (
            self.table.selectionModel().selectedRows()
        )

        if not selected_rows:
            return None

        row_index = selected_rows[0].row()
        code_item = self.table.item(row_index, 0)

        if code_item is None:
            return None

        supplier_id = code_item.data(
            Qt.ItemDataRole.UserRole
        )

        if supplier_id is None:
            return None

        return int(supplier_id)

    def _handle_table_double_click(
        self,
        _row: int,
        _column: int,
    ) -> None:
        """공급처 행을 두 번 클릭하면 수정창을 엽니다."""

        self.open_update_dialog()