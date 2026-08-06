from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)

from modules.customers.customer_repository import CustomerRepository


class CustomerDialog(QDialog):
    """거래처 등록 및 수정 대화상자입니다."""

    def __init__(self, repository: CustomerRepository, customer_id: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.customer_id = customer_id
        self.setWindowTitle("거래처 수정" if customer_id else "거래처 등록")
        self.setMinimumWidth(560)
        self._build_ui()
        if customer_id is not None:
            self._load_customer()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)
        title = QLabel("거래처 정보 수정" if self.customer_id else "새 거래처 등록")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #0F172A;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(11)
        self.type_input = QComboBox(); self.type_input.addItems(["소매", "사업자"])
        self.business_name_input = QLineEdit()
        self.customer_name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.business_number_input = QLineEdit()
        self.representative_input = QLineEdit()
        self.postal_code_input = QLineEdit()
        self.address_input = QLineEdit()
        self.detail_address_input = QLineEdit()
        self.memo_input = QTextEdit(); self.memo_input.setFixedHeight(75)
        self.active_checkbox = QCheckBox("활성 거래처"); self.active_checkbox.setChecked(True)

        form.addRow("거래처 유형 *", self.type_input)
        form.addRow("상호명", self.business_name_input)
        form.addRow("고객명/담당자 *", self.customer_name_input)
        form.addRow("연락처", self.phone_input)
        form.addRow("이메일", self.email_input)
        form.addRow("사업자번호", self.business_number_input)
        form.addRow("대표자명", self.representative_input)
        form.addRow("우편번호", self.postal_code_input)
        form.addRow("주소", self.address_input)
        form.addRow("상세주소", self.detail_address_input)
        form.addRow("메모", self.memo_input)
        form.addRow("사용 상태", self.active_checkbox)
        layout.addLayout(form)

        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("취소"); save = QPushButton("저장")
        save.setDefault(True)
        save.setStyleSheet("QPushButton{min-height:36px;padding:0 18px;border:none;border-radius:6px;background:#2563EB;color:white;font-weight:600;} QPushButton:hover{background:#1D4ED8;}")
        cancel.setStyleSheet("QPushButton{min-height:36px;padding:0 18px;border:1px solid #CBD5E1;border-radius:6px;background:white;color:#334155;font-weight:600;}")
        buttons.addWidget(cancel); buttons.addWidget(save); layout.addLayout(buttons)
        cancel.clicked.connect(self.reject); save.clicked.connect(self._save)
        self.type_input.currentTextChanged.connect(self._update_type_fields)
        self._update_type_fields(self.type_input.currentText())

    def _update_type_fields(self, customer_type: str) -> None:
        is_business = customer_type == "사업자"
        self.business_name_input.setEnabled(is_business)
        self.business_number_input.setEnabled(is_business)
        self.representative_input.setEnabled(is_business)

    def _values(self) -> dict:
        return {
            "customer_type": self.type_input.currentText(),
            "business_name": self.business_name_input.text(),
            "customer_name": self.customer_name_input.text(),
            "phone": self.phone_input.text(),
            "email": self.email_input.text(),
            "postal_code": self.postal_code_input.text(),
            "address": self.address_input.text(),
            "detail_address": self.detail_address_input.text(),
            "business_number": self.business_number_input.text(),
            "representative_name": self.representative_input.text(),
            "memo": self.memo_input.toPlainText(),
        }

    def _load_customer(self) -> None:
        customer = self.repository.get_customer_by_id(int(self.customer_id))
        if customer is None:
            QMessageBox.critical(self, "조회 오류", "거래처 정보를 찾을 수 없습니다.")
            self.reject(); return
        self.type_input.setCurrentText(customer.get("customer_type") or "소매")
        mapping = [
            (self.business_name_input, "business_name"), (self.customer_name_input, "customer_name"),
            (self.phone_input, "phone"), (self.email_input, "email"),
            (self.business_number_input, "business_number"), (self.representative_input, "representative_name"),
            (self.postal_code_input, "postal_code"), (self.address_input, "address"),
            (self.detail_address_input, "detail_address"),
        ]
        for widget, key in mapping: widget.setText(customer.get(key) or "")
        self.memo_input.setPlainText(customer.get("memo") or "")
        self.active_checkbox.setChecked(bool(customer.get("is_active", 1)))

    def _save(self) -> None:
        try:
            if self.customer_id is None:
                self.repository.create_customer(**self._values())
            else:
                self.repository.update_customer(
                    int(self.customer_id), is_active=self.active_checkbox.isChecked(), **self._values()
                )
        except Exception as error:
            QMessageBox.warning(self, "저장 확인", str(error)); return
        self.accept()
