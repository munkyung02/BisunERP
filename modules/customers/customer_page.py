from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.widgets import ERPBaseSearch, ERPButton, ERPTable
from modules.customers.customer_dialog import CustomerDialog
from modules.customers.customer_repository import CustomerRepository


class CustomerPage(QWidget):
    """소매·사업자 거래처와 거래 실적을 관리합니다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.repository = CustomerRepository()
        self._build_ui(); self._connect_signals(); self.load_customers()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self); layout.setContentsMargins(32, 28, 32, 28); layout.setSpacing(16)
        title = QLabel("거래처관리"); title.setStyleSheet("font-size:26px;font-weight:700;color:#0F172A;")
        desc = QLabel("소매 고객과 사업자 거래처의 연락처, 사업자정보 및 주문 실적을 관리합니다.")
        desc.setStyleSheet("font-size:14px;color:#64748B;")
        layout.addWidget(title); layout.addWidget(desc)
        self.search_widget = ERPBaseSearch("상호명, 고객명, 연락처, 사업자번호를 검색하세요.")
        layout.addWidget(self.search_widget)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("유형")); self.type_filter = QComboBox(); self.type_filter.addItems(["전체", "소매", "사업자"])
        controls.addWidget(self.type_filter)
        self.add_button = ERPButton("거래처 등록", "primary")
        self.edit_button = ERPButton("수정", "secondary")
        self.active_button = ERPButton("활성/비활성", "secondary")
        self.refresh_button = ERPButton("새로고침", "secondary")
        for button in (self.add_button, self.edit_button, self.active_button, self.refresh_button): controls.addWidget(button)
        controls.addStretch(); layout.addLayout(controls)
        self.table = ERPTable()
        self.table.set_headers(["유형", "상호명", "고객명/담당자", "연락처", "사업자번호", "주소", "주문건수", "누적 주문금액", "최근 주문일", "상태"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.status_label = QLabel("거래처 0개"); self.status_label.setStyleSheet("color:#64748B;font-size:13px;")
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.search_widget.search_requested.connect(self.load_customers)
        self.search_widget.reset_requested.connect(lambda: self.load_customers())
        self.type_filter.currentTextChanged.connect(lambda _text: self.load_customers())
        self.add_button.clicked.connect(self.open_create_dialog)
        self.edit_button.clicked.connect(self.open_update_dialog)
        self.active_button.clicked.connect(self.toggle_selected_customer)
        self.refresh_button.clicked.connect(lambda: self.load_customers())
        self.table.cellDoubleClicked.connect(lambda _r, _c: self.open_update_dialog())

    def load_customers(self, keyword: str | None = None) -> None:
        try:
            customers = self.repository.get_customers(keyword=keyword, customer_type=self.type_filter.currentText())
        except Exception as error:
            QMessageBox.critical(self, "조회 오류", f"거래처 목록을 불러오지 못했습니다.\n\n{error}"); return
        self.table.setRowCount(0)
        for customer in customers:
            row = self.table.rowCount(); self.table.insertRow(row)
            address = " ".join(filter(None, [customer.get("address"), customer.get("detail_address")]))
            values = [
                customer.get("customer_type"), customer.get("business_name"), customer.get("customer_name"),
                customer.get("phone"), customer.get("business_number"), address,
                f"{int(customer.get('order_count') or 0):,}", f"{int(customer.get('total_order_amount') or 0):,}원",
                customer.get("last_ordered_at") or "-", "활성" if customer.get("is_active") else "비활성",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                if column == 0: item.setData(Qt.ItemDataRole.UserRole, customer["id"])
                if column in (0, 6, 7, 9): item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        active_count = sum(1 for item in customers if item.get("is_active"))
        business_count = sum(1 for item in customers if item.get("customer_type") == "사업자")
        self.status_label.setText(f"전체 {len(customers)}개 · 활성 {active_count}개 · 사업자 {business_count}개")

    def _selected_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows: return None
        item = self.table.item(rows[0].row(), 0)
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return int(value) if value is not None else None

    def open_create_dialog(self) -> None:
        dialog = CustomerDialog(self.repository, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_customers(); QMessageBox.information(self, "등록 완료", "거래처가 등록되었습니다.")

    def open_update_dialog(self) -> None:
        customer_id = self._selected_id()
        if customer_id is None:
            QMessageBox.warning(self, "거래처 선택", "수정할 거래처를 먼저 선택해 주세요."); return
        dialog = CustomerDialog(self.repository, customer_id=customer_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_customers(); QMessageBox.information(self, "수정 완료", "거래처 정보가 수정되었습니다.")

    def toggle_selected_customer(self) -> None:
        customer_id = self._selected_id()
        if customer_id is None:
            QMessageBox.warning(self, "거래처 선택", "상태를 변경할 거래처를 먼저 선택해 주세요."); return
        customer = self.repository.get_customer_by_id(customer_id)
        if customer is None: return
        new_active = not bool(customer.get("is_active"))
        name = customer.get("business_name") or customer.get("customer_name") or "선택 거래처"
        status = "활성" if new_active else "비활성"
        answer = QMessageBox.question(self, "상태 변경", f"{name} 거래처를 {status} 상태로 변경하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes: return
        self.repository.set_customer_active(customer_id, new_active)
        self.load_customers(); QMessageBox.information(self, "변경 완료", f"거래처가 {status} 상태로 변경되었습니다.")
