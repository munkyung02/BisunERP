from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.orders.order_repository import OrderRepository
from modules.products.product_repository import ProductRepository
from modules.suppliers.supplier_repository import SupplierRepository


class ProductMasterWizard(QDialog):
    """미매핑 주문상품을 신규 또는 기존 ERP 상품에 확정 연결합니다."""

    HEADERS = ("플랫폼", "플랫폼 상품명", "옵션", "주문건수", "주문상품수량", "최초주문", "최근주문")
    PRODUCT_HEADERS = (
        "상품코드", "상품명", "옵션", "기본 공급처", "활성 공급처", "매핑", "매핑 주문", "최근 주문"
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        database_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("미매핑 상품 등록")
        self.resize(1320, 760)
        self.product_repository = ProductRepository(Path(database_path) if database_path else None)
        self.order_repository = OrderRepository(database_path)
        self.supplier_repository = SupplierRepository(database_path or "data/bisun_erp.db")
        self.groups: list[dict[str, Any]] = []
        self.search_results: list[dict[str, Any]] = []
        self.selected_product: dict[str, Any] | None = None
        self.all_suppliers = self.supplier_repository.get_suppliers(active_only=True)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.create_mode_button = QRadioButton("새 ERP 상품 생성")
        self.existing_mode_button = QRadioButton("기존 ERP 상품 선택")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.create_mode_button)
        self.mode_group.addButton(self.existing_mode_button)

        self.product_code_input = QLineEdit()
        self.product_code_input.setPlaceholderText("비워두면 자동 생성")
        self.product_name_input = QLineEdit()
        self.option_name_input = QLineEdit()
        self.category_input = QLineEdit()
        self.sale_unit_input = QLineEdit()
        self.origin_input = QLineEdit()
        new_form = QFormLayout()
        new_form.addRow("상품코드", self.product_code_input)
        new_form.addRow("상품명 *", self.product_name_input)
        new_form.addRow("옵션명", self.option_name_input)
        new_form.addRow("카테고리", self.category_input)
        new_form.addRow("판매단위", self.sale_unit_input)
        new_form.addRow("원산지", self.origin_input)
        self.new_product_widget = QWidget()
        self.new_product_widget.setLayout(new_form)

        self.product_search_input = QLineEdit()
        self.product_search_input.setPlaceholderText("상품코드, 상품명, 옵션명, 공급처 상품명")
        self.product_search_button = QPushButton("검색")
        search_row = QHBoxLayout()
        search_row.addWidget(self.product_search_input, 1)
        search_row.addWidget(self.product_search_button)
        self.product_results_table = QTableWidget(0, len(self.PRODUCT_HEADERS))
        self.product_results_table.setHorizontalHeaderLabels(self.PRODUCT_HEADERS)
        self.product_results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.product_results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.product_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.product_results_table.horizontalHeader().setStretchLastSection(True)
        existing_layout = QVBoxLayout()
        existing_layout.addLayout(search_row)
        existing_layout.addWidget(self.product_results_table)
        self.existing_product_widget = QWidget()
        self.existing_product_widget.setLayout(existing_layout)

        self.supplier_combo = QComboBox()
        self.supplier_product_name_input = QLineEdit()
        self.supplier_product_code_input = QLineEdit()
        self.default_supplier_check = QCheckBox("기본 공급처")
        self.default_supplier_check.setChecked(True)
        self.default_supplier_check.setEnabled(False)
        supplier_form = QFormLayout()
        supplier_form.addRow("공급처 *", self.supplier_combo)
        supplier_form.addRow("공급처 상품명", self.supplier_product_name_input)
        supplier_form.addRow("공급처 상품코드", self.supplier_product_code_input)
        supplier_form.addRow("", self.default_supplier_check)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("등록 방식 선택:"))
        mode_row.addWidget(self.create_mode_button)
        mode_row.addWidget(self.existing_mode_button)
        mode_row.addStretch()
        right_layout = QVBoxLayout()
        right_layout.addLayout(mode_row)
        right_layout.addWidget(self.new_product_widget)
        right_layout.addWidget(self.existing_product_widget, 1)
        right_layout.addLayout(supplier_form)
        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(right_widget)
        splitter.setSizes([650, 650])
        self.status_label = QLabel()
        self.save_button = QPushButton("저장 후 다음 상품")
        self.save_button.setDefault(True)
        close_button = QPushButton("닫기")
        buttons = QHBoxLayout()
        buttons.addWidget(self.status_label)
        buttons.addStretch()
        buttons.addWidget(self.save_button)
        buttons.addWidget(close_button)
        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addLayout(buttons)

        self.table.itemSelectionChanged.connect(self._load_selected_group)
        self.create_mode_button.toggled.connect(self._mode_changed)
        self.existing_mode_button.toggled.connect(self._mode_changed)
        self.product_search_button.clicked.connect(self.search_existing_products)
        self.product_search_input.returnPressed.connect(self.search_existing_products)
        self.product_results_table.itemSelectionChanged.connect(self._select_existing_product)
        self.supplier_combo.currentIndexChanged.connect(self._supplier_changed)
        self.save_button.clicked.connect(self._save_current)
        close_button.clicked.connect(self.accept)
        self.refresh_groups()

    def _set_no_mode(self) -> None:
        self.mode_group.setExclusive(False)
        self.create_mode_button.setChecked(False)
        self.existing_mode_button.setChecked(False)
        self.mode_group.setExclusive(True)
        self._mode_changed()

    def _mode_changed(self) -> None:
        creating = self.create_mode_button.isChecked()
        existing = self.existing_mode_button.isChecked()
        self.new_product_widget.setVisible(creating)
        self.existing_product_widget.setVisible(existing)
        self.selected_product = None
        self.product_results_table.clearSelection()
        self.default_supplier_check.setChecked(creating)
        self._load_all_suppliers()
        self._update_save_state()

    def _load_all_suppliers(self) -> None:
        self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()
        self.supplier_combo.addItem("공급처 선택", None)
        for supplier in self.all_suppliers:
            self.supplier_combo.addItem(
                str(supplier.get("supplier_name") or ""),
                {"id": int(supplier["id"]), "linked": False, "link": None},
            )
        self.supplier_combo.blockSignals(False)
        self.supplier_product_name_input.clear()
        self.supplier_product_code_input.clear()

    def _load_product_suppliers(self, product_id: int) -> None:
        links = self.product_repository.get_product_suppliers(product_id, active_only=True)
        linked_ids = {int(link["supplier_id"]) for link in links}
        self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()
        self.supplier_combo.addItem("공급처 선택", None)
        for link in links:
            self.supplier_combo.addItem(
                f"[연결됨] {link.get('supplier_name') or ''}",
                {"id": int(link["supplier_id"]), "linked": True, "link": link},
            )
        for supplier in self.all_suppliers:
            if int(supplier["id"]) not in linked_ids:
                self.supplier_combo.addItem(
                    str(supplier.get("supplier_name") or ""),
                    {"id": int(supplier["id"]), "linked": False, "link": None},
                )
        self.supplier_combo.blockSignals(False)
        self.supplier_combo.setCurrentIndex(0)
        self._supplier_changed()

    def refresh_groups(self) -> None:
        self.groups = self.order_repository.get_unmapped_product_groups()
        self.table.setRowCount(len(self.groups))
        for row_index, group in enumerate(self.groups):
            values = (group["platform"], group["platform_product_name"], group["option_name"],
                      group["order_count"], group["total_quantity"], group["first_ordered_at"],
                      group["latest_ordered_at"])
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                if column in (3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, column, item)
        self.status_label.setText(
            f"미매핑 상품 {len(self.groups):,}개" if self.groups else "모든 미매핑 상품 처리가 완료되었습니다."
        )
        if self.groups:
            self.table.selectRow(0)
        else:
            self._clear_form()
        self._update_save_state()

    def _selected_group(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        return self.groups[row] if 0 <= row < len(self.groups) else None

    def _load_selected_group(self) -> None:
        group = self._selected_group()
        if group is None:
            return
        self._clear_form()
        self.product_name_input.setText(str(group["platform_product_name"] or ""))
        self.option_name_input.setText(str(group["option_name"] or ""))
        self.supplier_product_name_input.setText(str(group["platform_product_name"] or ""))
        self.product_search_input.setText(str(group["platform_product_name"] or ""))
        self._set_no_mode()

    def _clear_form(self) -> None:
        for widget in (self.product_code_input, self.product_name_input, self.option_name_input,
                       self.category_input, self.sale_unit_input, self.origin_input,
                       self.product_search_input, self.supplier_product_name_input,
                       self.supplier_product_code_input):
            widget.clear()
        self.search_results = []
        self.product_results_table.setRowCount(0)
        self.selected_product = None

    def search_existing_products(self) -> None:
        self.search_results = self.product_repository.search_active_products(
            self.product_search_input.text(), limit=50
        )
        self.product_results_table.setRowCount(len(self.search_results))
        for row_index, product in enumerate(self.search_results):
            values = (product["product_code"], product["product_name"], product["option_name"],
                      product["default_supplier"], product["active_supplier_count"],
                      product["mapping_count"], product["mapped_order_item_count"],
                      product["latest_order_date"])
            for column, value in enumerate(values):
                self.product_results_table.setItem(row_index, column, QTableWidgetItem(str(value or "")))
        self.product_results_table.clearSelection()
        self.selected_product = None
        self._load_all_suppliers()
        self._update_save_state()

    def _select_existing_product(self) -> None:
        row = self.product_results_table.currentRow()
        if not 0 <= row < len(self.search_results):
            self.selected_product = None
            self._update_save_state()
            return
        self.selected_product = self.search_results[row]
        self._load_product_suppliers(int(self.selected_product["id"]))
        self._update_save_state()

    def _supplier_changed(self) -> None:
        data = self.supplier_combo.currentData()
        link = data.get("link") if isinstance(data, dict) else None
        if link:
            self.default_supplier_check.setChecked(bool(link.get("is_default")))
            self.supplier_product_name_input.setText(str(link.get("supplier_product_name") or ""))
            self.supplier_product_code_input.setText(str(link.get("supplier_product_code") or ""))
        elif self._selected_group() is not None:
            self.default_supplier_check.setChecked(self.create_mode_button.isChecked())
            self.supplier_product_name_input.setText(
                str(self._selected_group().get("platform_product_name") or "")
            )
            self.supplier_product_code_input.clear()
        self._update_save_state()

    def _update_save_state(self) -> None:
        has_group = self._selected_group() is not None
        data = self.supplier_combo.currentData()
        has_supplier = isinstance(data, dict) and data.get("id") is not None
        valid_mode = self.create_mode_button.isChecked() or (
            self.existing_mode_button.isChecked() and self.selected_product is not None
        )
        self.save_button.setEnabled(has_group and has_supplier and valid_mode)

    def _save_current(self) -> None:
        group = self._selected_group()
        supplier_data = self.supplier_combo.currentData()
        if group is None or not isinstance(supplier_data, dict):
            return
        supplier_id = int(supplier_data["id"])
        supplier_product_name = self.supplier_product_name_input.text().strip()
        try:
            if self.create_mode_button.isChecked():
                product_name = self.product_name_input.text().strip()
                if not product_name or not supplier_product_name:
                    raise ValueError("상품명과 공급처 상품명을 입력해 주세요.")
                product_id = self.product_repository.create_product(
                    product_code=self.product_code_input.text(), product_name=product_name,
                    platform=str(group["platform"] or ""),
                    platform_product_name=str(group["platform_product_name"] or ""),
                    option_name=self.option_name_input.text(), category=self.category_input.text(),
                    sale_unit=self.sale_unit_input.text(), origin=self.origin_input.text(),
                    supplier_id=supplier_id, supplier_product_name=supplier_product_name,
                )
                self.product_repository.add_product_supplier(
                    product_id, supplier_id, supplier_product_name=supplier_product_name,
                    supplier_product_code=self.supplier_product_code_input.text(),
                )
                product_label = product_name
            elif self.existing_mode_button.isChecked() and self.selected_product is not None:
                product_id = int(self.selected_product["id"])
                if not supplier_data.get("linked"):
                    if not supplier_product_name:
                        raise ValueError("새 공급처 연결에는 공급처 상품명이 필요합니다.")
                    self.product_repository.add_product_supplier(
                        product_id, supplier_id, supplier_product_name=supplier_product_name,
                        supplier_product_code=self.supplier_product_code_input.text(),
                    )
                product_label = str(self.selected_product["product_name"])
            else:
                raise ValueError("새 ERP 상품 생성 또는 기존 ERP 상품 선택 방식을 먼저 선택해 주세요.")

            mapped_count = self.order_repository.save_mapping_rule_for_item(
                int(group["representative_item_id"]), product_id, supplier_id=supplier_id
            )
        except Exception as error:
            QMessageBox.critical(self, "상품 등록 오류", str(error))
            return
        self.refresh_groups()
        self._set_no_mode()
        self.status_label.setText(
            f"등록 완료: {product_label} / 기존 주문상품 {mapped_count:,}건 매핑"
        )
