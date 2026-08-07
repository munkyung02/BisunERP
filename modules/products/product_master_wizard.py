from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
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
    """미매핑 주문상품을 상품 마스터로 연속 등록하는 운영 도구입니다."""

    HEADERS = (
        "플랫폼",
        "플랫폼 상품명",
        "옵션",
        "주문건수",
        "주문상품수량",
        "최초주문",
        "최근주문",
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        database_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("미매핑 상품 등록")
        self.resize(1180, 680)

        self.product_repository = ProductRepository(Path(database_path) if database_path else None)
        self.order_repository = OrderRepository(database_path)
        self.supplier_repository = SupplierRepository(
            database_path or "data/bisun_erp.db"
        )
        self.groups: list[dict[str, Any]] = []

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.product_code_input = QLineEdit()
        self.product_code_input.setPlaceholderText("비워두면 자동 생성")
        self.product_name_input = QLineEdit()
        self.option_name_input = QLineEdit()
        self.category_input = QLineEdit()
        self.sale_unit_input = QLineEdit()
        self.origin_input = QLineEdit()
        self.supplier_combo = QComboBox()
        self.supplier_product_name_input = QLineEdit()
        self.supplier_product_code_input = QLineEdit()
        self.default_supplier_check = QCheckBox("기본 공급처")
        self.default_supplier_check.setChecked(True)
        self.default_supplier_check.setEnabled(False)
        self.default_supplier_check.setToolTip(
            "새 상품의 첫 공급처는 즉시 발주가 가능하도록 기본 공급처로 등록됩니다."
        )

        form = QFormLayout()
        form.addRow("상품코드", self.product_code_input)
        form.addRow("상품명 *", self.product_name_input)
        form.addRow("옵션명", self.option_name_input)
        form.addRow("카테고리", self.category_input)
        form.addRow("판매단위", self.sale_unit_input)
        form.addRow("원산지", self.origin_input)
        form.addRow("공급처 *", self.supplier_combo)
        form.addRow("공급처 상품명 *", self.supplier_product_name_input)
        form.addRow("공급처 상품코드", self.supplier_product_code_input)
        form.addRow("", self.default_supplier_check)

        form_widget = QWidget()
        form_widget.setLayout(form)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(form_widget)
        splitter.setSizes([760, 380])

        self.status_label = QLabel()
        self.save_button = QPushButton("등록 후 다음 상품")
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
        self.save_button.clicked.connect(self._save_current)
        close_button.clicked.connect(self.accept)

        self._load_suppliers()
        self.refresh_groups()

    def _load_suppliers(self) -> None:
        self.supplier_combo.clear()
        for supplier in self.supplier_repository.get_suppliers(active_only=True):
            self.supplier_combo.addItem(
                str(supplier.get("supplier_name") or ""), int(supplier["id"])
            )

    def refresh_groups(self) -> None:
        self.groups = self.order_repository.get_unmapped_product_groups()
        self.table.setRowCount(len(self.groups))
        for row_index, group in enumerate(self.groups):
            values = (
                group["platform"],
                group["platform_product_name"],
                group["option_name"],
                group["order_count"],
                group["total_quantity"],
                group["first_ordered_at"],
                group["latest_ordered_at"],
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                if column in (3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, column, item)
        self.status_label.setText(f"미매핑 상품 {len(self.groups):,}개")
        self.save_button.setEnabled(bool(self.groups) and self.supplier_combo.count() > 0)
        if self.groups:
            self.table.selectRow(0)
        else:
            self._clear_form()

    def _selected_group(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        return self.groups[row] if 0 <= row < len(self.groups) else None

    def _load_selected_group(self) -> None:
        group = self._selected_group()
        if group is None:
            return
        self.product_code_input.clear()
        self.product_name_input.setText(str(group["platform_product_name"] or ""))
        self.option_name_input.setText(str(group["option_name"] or ""))
        self.category_input.clear()
        self.sale_unit_input.clear()
        self.origin_input.clear()
        self.supplier_product_name_input.setText(
            str(group["platform_product_name"] or "")
        )
        self.supplier_product_code_input.clear()
        self.product_name_input.setFocus()
        self.product_name_input.selectAll()

    def _clear_form(self) -> None:
        for widget in (
            self.product_code_input,
            self.product_name_input,
            self.option_name_input,
            self.category_input,
            self.sale_unit_input,
            self.origin_input,
            self.supplier_product_name_input,
            self.supplier_product_code_input,
        ):
            widget.clear()

    def _save_current(self) -> None:
        group = self._selected_group()
        if group is None:
            return
        product_name = self.product_name_input.text().strip()
        supplier_product_name = self.supplier_product_name_input.text().strip()
        supplier_id = self.supplier_combo.currentData()
        if not product_name or not supplier_product_name or supplier_id is None:
            QMessageBox.warning(self, "필수 입력", "상품명, 공급처, 공급처 상품명을 입력해 주세요.")
            return

        try:
            product_id = self.product_repository.create_product(
                product_code=self.product_code_input.text(),
                product_name=product_name,
                platform=str(group["platform"] or ""),
                platform_product_name=str(group["platform_product_name"] or ""),
                option_name=self.option_name_input.text(),
                category=self.category_input.text(),
                sale_unit=self.sale_unit_input.text(),
                origin=self.origin_input.text(),
                supplier_id=int(supplier_id),
                supplier_product_name=supplier_product_name,
            )
            self.product_repository.add_product_supplier(
                product_id,
                int(supplier_id),
                supplier_product_name=supplier_product_name,
                supplier_product_code=self.supplier_product_code_input.text(),
            )
            mapped_count = self.order_repository.save_mapping_rule_for_item(
                int(group["representative_item_id"]), product_id
            )
        except Exception as error:
            QMessageBox.critical(self, "상품 등록 오류", str(error))
            return

        self.refresh_groups()
        self.status_label.setText(
            f"등록 완료: {product_name} / 기존 주문상품 {mapped_count:,}건 매핑"
        )

