from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from modules.products.product_repository import ProductRepository
from modules.suppliers.supplier_repository import SupplierRepository


class ProductSupplierDialog(QDialog):
    """상품별 공급처와 공급처별 거래조건을 관리한다."""

    def __init__(self, product_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.product_id = int(product_id)
        self.repository = ProductRepository()
        self.supplier_repository = SupplierRepository()
        self.setWindowTitle("상품 공급처별 거래조건 관리")
        self.resize(1380, 620)
        self._build_ui()
        self._load_suppliers()
        self.refresh()

    def _spin(self, maximum: int = 2_000_000_000, minimum: int = 0) -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setGroupSeparatorShown(True)
        return box

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("같은 상품이라도 공급처마다 상품명·코드·단가·택배조건·마감시간·최소수량·포장단위를 다르게 저장할 수 있습니다."))

        group = QGroupBox("공급처별 조건 추가·수정")
        grid = QGridLayout(group)
        self.supplier_combo = QComboBox()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("예: 황도복숭아(중)")
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("예: A001")
        self.price_input = self._spin()
        self.price_input.setSuffix("원")
        self.shipping_fee_input = self._spin(100_000_000)
        self.shipping_fee_input.setSuffix("원")
        self.carrier_input = QComboBox()
        self.carrier_input.setEditable(True)
        self.carrier_input.addItems(["CJ대한통운", "로젠택배", "한진택배", "롯데택배", "우체국택배"])
        self.deadline_input = QLineEdit("14:00")
        self.deadline_input.setMaximumWidth(90)
        self.minimum_qty_input = self._spin(1_000_000, 1)
        self.minimum_qty_input.setValue(1)
        self.package_qty_input = self._spin(1_000_000, 1)
        self.package_qty_input.setValue(1)
        self.package_unit_input = QLineEdit("개")
        self.package_unit_input.setMaximumWidth(90)

        labels = [
            ("공급처", self.supplier_combo), ("공급처 상품명", self.name_input),
            ("공급처 상품코드", self.code_input), ("매입단가", self.price_input),
            ("택배비", self.shipping_fee_input), ("택배사", self.carrier_input),
            ("발주마감", self.deadline_input), ("최소 발주수량", self.minimum_qty_input),
            ("포장단위 수량", self.package_qty_input), ("포장단위명", self.package_unit_input),
        ]
        for idx, (label, widget) in enumerate(labels):
            row, pair = divmod(idx, 5)
            col = pair * 2
            grid.addWidget(QLabel(label), row, col)
            grid.addWidget(widget, row, col + 1)
        save_button = QPushButton("공급처 조건 저장")
        save_button.clicked.connect(self._save_supplier)
        grid.addWidget(save_button, 2, 8, 1, 2)
        layout.addWidget(group)

        headers = ["구분", "공급처", "공급처 상품코드", "공급처 상품명", "매입가", "택배비", "택배사", "발주마감", "최소수량", "포장단위", "사용"]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._load_selected)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        edit_button = QPushButton("선택 조건 불러오기")
        edit_button.clicked.connect(self._load_selected)
        default_button = QPushButton("기본 공급처로 지정")
        default_button.clicked.connect(self._set_default)
        delete_button = QPushButton("연결 삭제")
        delete_button.clicked.connect(self._delete)
        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.accept)
        for button in (edit_button, default_button, delete_button):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _load_suppliers(self) -> None:
        self.supplier_combo.clear()
        try:
            suppliers = self.supplier_repository.get_suppliers(active_only=True)
        except TypeError:
            suppliers = self.supplier_repository.get_suppliers()
        for supplier in suppliers:
            if bool(supplier.get("is_active", 1)):
                self.supplier_combo.addItem(str(supplier.get("supplier_name") or ""), int(supplier["id"]))

    def refresh(self) -> None:
        rows = self.repository.get_product_suppliers(self.product_id)
        self._rows = {int(row["id"]): row for row in rows}
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            package = f"{int(row.get('package_unit_qty') or 1):,}{row.get('package_unit_name') or '개'}/단위"
            values = [
                "기본" if int(row.get("is_default", 0)) else "예비",
                row.get("supplier_name") or "", row.get("supplier_product_code") or "",
                row.get("supplier_product_name") or "", f"{int(row.get('purchase_price') or 0):,}원",
                f"{int(row.get('shipping_fee') or 0):,}원", row.get("carrier") or "",
                row.get("order_deadline") or "14:00", f"{int(row.get('minimum_order_quantity') or 1):,}",
                package, "사용" if int(row.get("is_active", 1)) else "중지",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, int(row["id"]))
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()

    def _selected_link_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _load_selected(self) -> None:
        link_id = self._selected_link_id()
        if link_id is None:
            QMessageBox.warning(self, "선택 필요", "불러올 공급처를 선택해 주세요.")
            return
        row = self._rows[link_id]
        index = self.supplier_combo.findData(int(row["supplier_id"]))
        if index >= 0:
            self.supplier_combo.setCurrentIndex(index)
        self.name_input.setText(str(row.get("supplier_product_name") or ""))
        self.code_input.setText(str(row.get("supplier_product_code") or ""))
        self.price_input.setValue(int(row.get("purchase_price") or 0))
        self.shipping_fee_input.setValue(int(row.get("shipping_fee") or 0))
        self.carrier_input.setCurrentText(str(row.get("carrier") or ""))
        self.deadline_input.setText(str(row.get("order_deadline") or "14:00"))
        self.minimum_qty_input.setValue(max(1, int(row.get("minimum_order_quantity") or 1)))
        self.package_qty_input.setValue(max(1, int(row.get("package_unit_qty") or 1)))
        self.package_unit_input.setText(str(row.get("package_unit_name") or "개"))

    def _save_supplier(self) -> None:
        supplier_id = self.supplier_combo.currentData()
        if supplier_id is None:
            QMessageBox.warning(self, "선택 필요", "공급처를 선택해 주세요.")
            return
        try:
            self.repository.add_product_supplier(
                self.product_id, int(supplier_id),
                supplier_product_name=self.name_input.text(),
                supplier_product_code=self.code_input.text(),
                purchase_price=self.price_input.value(),
                minimum_order_quantity=self.minimum_qty_input.value(),
                package_unit_qty=self.package_qty_input.value(),
                package_unit_name=self.package_unit_input.text(),
                shipping_fee=self.shipping_fee_input.value(),
                carrier=self.carrier_input.currentText(),
                order_deadline=self.deadline_input.text(),
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "저장 실패", str(exc))

    def _set_default(self) -> None:
        link_id = self._selected_link_id()
        if link_id is None:
            QMessageBox.warning(self, "선택 필요", "기본으로 지정할 공급처를 선택해 주세요.")
            return
        try:
            self.repository.set_default_product_supplier(self.product_id, link_id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "변경 실패", str(exc))

    def _delete(self) -> None:
        link_id = self._selected_link_id()
        if link_id is None:
            QMessageBox.warning(self, "선택 필요", "삭제할 공급처 연결을 선택해 주세요.")
            return
        try:
            self.repository.delete_product_supplier(self.product_id, link_id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "삭제 실패", str(exc))
