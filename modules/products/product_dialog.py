from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from modules.products.product_repository import ProductRepository
from modules.suppliers.supplier_repository import SupplierRepository


class ProductDialog(QDialog):
    """상품 등록 및 수정 대화상자입니다."""

    PLATFORM_ITEMS = [
        "",
        "쿠팡",
        "스마트스토어",
        "기타",
    ]

    PURCHASE_ROUND_ITEMS = [
        "",
        "1차",
        "2차",
        "3차",
        "상시",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        product_id: int | None = None,
    ) -> None:
        super().__init__(parent)

        self.product_id = product_id
        self.product_repository = ProductRepository()
        self.supplier_repository = SupplierRepository()

        self.setWindowTitle(
            "상품 수정" if self.product_id else "상품 등록"
        )
        self.setMinimumWidth(620)
        self.setModal(True)

        self._create_widgets()
        self._create_layout()
        self._connect_signals()
        self._load_suppliers()

        if self.product_id is not None:
            self._load_product()

    def _create_widgets(self) -> None:
        self.product_code_label = QLabel(
            "저장 시 자동 생성"
        )
        self.product_code_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText(
            "예: 동해안 자연산 흑고동"
        )

        self.platform_combo = QComboBox()
        self.platform_combo.addItems(
            self.PLATFORM_ITEMS
        )
        self.platform_combo.setEditable(True)
        self.platform_combo.setInsertPolicy(
            QComboBox.InsertPolicy.NoInsert
        )

        self.platform_product_name_input = QLineEdit()
        self.platform_product_name_input.setPlaceholderText(
            "예: 비선상회 동해안 자연산 흑고동 1kg"
        )

        self.option_name_input = QLineEdit()
        self.option_name_input.setPlaceholderText(
            "예: 1kg / 중대사이즈"
        )

        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumWidth(300)

        self.supplier_product_name_input = QLineEdit()
        self.supplier_product_name_input.setPlaceholderText(
            "공급처 발주서에 사용할 상품명"
        )

        self.purchase_price_input = QSpinBox()
        self.purchase_price_input.setRange(
            0,
            2_000_000_000,
        )
        self.purchase_price_input.setSingleStep(100)
        self.purchase_price_input.setSuffix("원")
        self.purchase_price_input.setGroupSeparatorShown(
            True
        )

        self.sale_price_input = QSpinBox()
        self.sale_price_input.setRange(
            0,
            2_000_000_000,
        )
        self.sale_price_input.setSingleStep(100)
        self.sale_price_input.setSuffix("원")
        self.sale_price_input.setGroupSeparatorShown(
            True
        )

        self.purchase_round_combo = QComboBox()
        self.purchase_round_combo.addItems(
            self.PURCHASE_ROUND_ITEMS
        )
        self.purchase_round_combo.setEditable(True)
        self.purchase_round_combo.setInsertPolicy(
            QComboBox.InsertPolicy.NoInsert
        )

        self.active_checkbox = QCheckBox(
            "사용 중인 상품"
        )
        self.active_checkbox.setChecked(True)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        save_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Save
        )
        cancel_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        )

        if save_button is not None:
            save_button.setText("저장")

        if cancel_button is not None:
            cancel_button.setText("취소")

    def _create_layout(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )
        main_layout.setSpacing(18)

        title_label = QLabel(
            "상품 정보"
        )
        title_label.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: bold;
            }
            """
        )
        main_layout.addWidget(title_label)

        required_label = QLabel(
            "* 표시는 필수 입력 항목입니다."
        )
        required_label.setStyleSheet(
            "color: #666666;"
        )
        main_layout.addWidget(required_label)

        basic_group = QGroupBox(
            "기본 정보"
        )
        basic_form = QFormLayout(basic_group)
        basic_form.setHorizontalSpacing(24)
        basic_form.setVerticalSpacing(14)

        basic_form.addRow(
            "상품코드",
            self.product_code_label,
        )
        basic_form.addRow(
            "상품명 *",
            self.product_name_input,
        )
        basic_form.addRow(
            "플랫폼",
            self.platform_combo,
        )
        basic_form.addRow(
            "판매처 상품명",
            self.platform_product_name_input,
        )
        basic_form.addRow(
            "옵션명",
            self.option_name_input,
        )

        main_layout.addWidget(basic_group)

        supplier_group = QGroupBox(
            "공급 및 발주 정보"
        )
        supplier_form = QFormLayout(
            supplier_group
        )
        supplier_form.setHorizontalSpacing(24)
        supplier_form.setVerticalSpacing(14)

        supplier_form.addRow(
            "공급처",
            self.supplier_combo,
        )
        supplier_form.addRow(
            "공급처 상품명",
            self.supplier_product_name_input,
        )
        supplier_form.addRow(
            "발주차수",
            self.purchase_round_combo,
        )

        main_layout.addWidget(supplier_group)

        price_group = QGroupBox(
            "가격 정보"
        )
        price_layout = QHBoxLayout(
            price_group
        )

        purchase_price_form = QFormLayout()
        purchase_price_form.addRow(
            "매입가",
            self.purchase_price_input,
        )

        sale_price_form = QFormLayout()
        sale_price_form.addRow(
            "판매가",
            self.sale_price_input,
        )

        price_layout.addLayout(
            purchase_price_form
        )
        price_layout.addSpacing(20)
        price_layout.addLayout(
            sale_price_form
        )

        main_layout.addWidget(price_group)
        main_layout.addWidget(
            self.active_checkbox
        )
        main_layout.addStretch()
        main_layout.addWidget(
            self.button_box
        )

    def _connect_signals(self) -> None:
        self.button_box.accepted.connect(
            self._save_product
        )
        self.button_box.rejected.connect(
            self.reject
        )

    def _load_suppliers(self) -> None:
        """활성 공급처를 콤보박스에 불러옵니다."""

        self.supplier_combo.clear()
        self.supplier_combo.addItem(
            "공급처 미지정",
            None,
        )

        try:
            suppliers = (
                self.supplier_repository.get_suppliers()
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "공급처 불러오기 오류",
                "공급처 목록을 불러오지 못했습니다.\n\n"
                f"{error}",
            )
            return

        for supplier in suppliers:
            is_active = int(
                supplier.get("is_active", 1)
            )

            if is_active != 1:
                continue

            supplier_id = supplier.get("id")
            supplier_name = (
                supplier.get("supplier_name")
                or "이름 없는 공급처"
            )
            supplier_code = supplier.get(
                "supplier_code"
            )

            display_text = supplier_name

            if supplier_code:
                display_text = (
                    f"{supplier_name} "
                    f"({supplier_code})"
                )

            self.supplier_combo.addItem(
                display_text,
                supplier_id,
            )

    def _load_product(self) -> None:
        """수정 대상 상품 정보를 불러옵니다."""

        if self.product_id is None:
            return

        try:
            product = (
                self.product_repository
                .get_product_by_id(
                    self.product_id
                )
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "상품 조회 오류",
                "상품 정보를 불러오지 못했습니다.\n\n"
                f"{error}",
            )
            self.reject()
            return

        if product is None:
            QMessageBox.warning(
                self,
                "상품 없음",
                "수정할 상품을 찾을 수 없습니다.",
            )
            self.reject()
            return

        self.product_code_label.setText(
            self._text(
                product.get("product_code")
            )
            or "-"
        )

        self.product_name_input.setText(
            self._text(
                product.get("product_name")
            )
        )

        self._set_combo_text(
            self.platform_combo,
            product.get("platform"),
        )

        self.platform_product_name_input.setText(
            self._text(
                product.get(
                    "platform_product_name"
                )
            )
        )

        self.option_name_input.setText(
            self._text(
                product.get("option_name")
            )
        )

        self.supplier_product_name_input.setText(
            self._text(
                product.get(
                    "supplier_product_name"
                )
            )
        )

        self.purchase_price_input.setValue(
            self._integer(
                product.get("purchase_price")
            )
        )

        self.sale_price_input.setValue(
            self._integer(
                product.get("sale_price")
            )
        )

        self._set_combo_text(
            self.purchase_round_combo,
            product.get("purchase_round"),
        )

        self.active_checkbox.setChecked(
            bool(
                self._integer(
                    product.get("is_active")
                )
            )
        )

        self._select_supplier(
            product.get("supplier_id")
        )

    def _select_supplier(
        self,
        supplier_id: Any,
    ) -> None:
        if supplier_id is None:
            self.supplier_combo.setCurrentIndex(0)
            return

        for index in range(
            self.supplier_combo.count()
        ):
            combo_supplier_id = (
                self.supplier_combo.itemData(index)
            )

            if combo_supplier_id == supplier_id:
                self.supplier_combo.setCurrentIndex(
                    index
                )
                return

        # 비활성 공급처가 기존 상품에 연결된 경우
        try:
            supplier = (
                self.supplier_repository
                .get_supplier_by_id(
                    int(supplier_id)
                )
            )

        except Exception:
            supplier = None

        if supplier:
            supplier_name = (
                supplier.get("supplier_name")
                or "알 수 없는 공급처"
            )

            self.supplier_combo.addItem(
                f"{supplier_name} (비활성)",
                supplier_id,
            )
            self.supplier_combo.setCurrentIndex(
                self.supplier_combo.count() - 1
            )
        else:
            self.supplier_combo.setCurrentIndex(0)

    def _save_product(self) -> None:
        product_name = (
            self.product_name_input.text().strip()
        )

        if not product_name:
            QMessageBox.warning(
                self,
                "입력 확인",
                "상품명을 입력해 주세요.",
            )
            self.product_name_input.setFocus()
            return

        supplier_id = (
            self.supplier_combo.currentData()
        )

        product_data = {
            "product_name": product_name,
            "platform": (
                self.platform_combo
                .currentText()
                .strip()
                or None
            ),
            "platform_product_name": (
                self.platform_product_name_input
                .text()
                .strip()
                or None
            ),
            "option_name": (
                self.option_name_input
                .text()
                .strip()
                or None
            ),
            "supplier_id": supplier_id,
            "supplier_product_name": (
                self.supplier_product_name_input
                .text()
                .strip()
                or None
            ),
            "purchase_price": (
                self.purchase_price_input.value()
            ),
            "sale_price": (
                self.sale_price_input.value()
            ),
            "purchase_round": (
                self.purchase_round_combo
                .currentText()
                .strip()
                or None
            ),
            "is_active": (
                self.active_checkbox.isChecked()
            ),
        }

        try:
            if self.product_id is None:
                self.product_repository.create_product(
                    **product_data
                )

                success_message = (
                    "상품이 등록되었습니다."
                )

            else:
                changed_rows = (
                    self.product_repository
                    .update_product(
                        self.product_id,
                        **product_data,
                    )
                )

                if changed_rows == 0:
                    raise ValueError(
                        "수정할 상품을 찾을 수 없습니다."
                    )

                success_message = (
                    "상품 정보가 수정되었습니다."
                )

        except ValueError as error:
            QMessageBox.warning(
                self,
                "저장할 수 없음",
                str(error),
            )
            return

        except Exception as error:
            QMessageBox.critical(
                self,
                "저장 오류",
                "상품 저장 중 오류가 발생했습니다.\n\n"
                f"{error}",
            )
            return

        QMessageBox.information(
            self,
            "저장 완료",
            success_message,
        )
        self.accept()

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""

        return str(value)

    @staticmethod
    def _integer(value: Any) -> int:
        if value in (None, ""):
            return 0

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _set_combo_text(
        combo: QComboBox,
        value: Any,
    ) -> None:
        text = ProductDialog._text(value)

        index = combo.findText(text)

        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentText(text)