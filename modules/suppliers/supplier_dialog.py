from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.suppliers.supplier_repository import SupplierRepository


class SupplierDialog(QDialog):
    """공급처 등록과 수정을 처리하는 공용 다이얼로그입니다."""

    def __init__(
        self,
        repository: SupplierRepository,
        supplier_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.repository = repository
        self.supplier_id = supplier_id

        self.setModal(True)
        self.setMinimumWidth(540)

        self._build_ui()

        if self.supplier_id is None:
            self.setWindowTitle("공급처 등록")
            self.title_label.setText("공급처 등록")
            self.active_checkbox.setChecked(True)
            self.active_checkbox.hide()
        else:
            self.setWindowTitle("공급처 수정")
            self.title_label.setText("공급처 수정")
            self._load_supplier()

    def _build_ui(self) -> None:
        """다이얼로그 화면을 구성합니다."""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        self.title_label = QLabel()
        self.title_label.setStyleSheet(
            """
            QLabel {
                font-size: 22px;
                font-weight: 700;
                color: #0F172A;
            }
            """
        )

        description_label = QLabel(
            "공급처 기본정보와 정산계좌 정보를 입력해 주세요."
        )
        description_label.setStyleSheet(
            """
            QLabel {
                font-size: 13px;
                color: #64748B;
            }
            """
        )

        main_layout.addWidget(self.title_label)
        main_layout.addWidget(description_label)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(
            form_layout.labelAlignment()
        )

        self.supplier_name_input = QLineEdit()
        self.supplier_name_input.setPlaceholderText(
            "예: 통영수산"
        )

        self.manager_name_input = QLineEdit()
        self.manager_name_input.setPlaceholderText(
            "담당자 이름"
        )

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText(
            "예: 010-1234-5678"
        )

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText(
            "예: supplier@example.com"
        )

        self.bank_name_input = QLineEdit()
        self.bank_name_input.setPlaceholderText(
            "예: 농협"
        )

        self.account_number_input = QLineEdit()
        self.account_number_input.setPlaceholderText(
            "계좌번호"
        )

        self.account_holder_input = QLineEdit()
        self.account_holder_input.setPlaceholderText(
            "예금주"
        )

        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText(
            "공급처 주소"
        )

        self.memo_input = QTextEdit()
        self.memo_input.setPlaceholderText(
            "발주 방법, 정산일, 배송 관련 참고사항 등을 입력하세요."
        )
        self.memo_input.setFixedHeight(100)

        self.active_checkbox = QCheckBox(
            "활성 공급처"
        )

        form_layout.addRow(
            "공급처명 *",
            self.supplier_name_input,
        )
        form_layout.addRow(
            "담당자",
            self.manager_name_input,
        )
        form_layout.addRow(
            "연락처",
            self.phone_input,
        )
        form_layout.addRow(
            "이메일",
            self.email_input,
        )
        form_layout.addRow(
            "은행",
            self.bank_name_input,
        )
        form_layout.addRow(
            "계좌번호",
            self.account_number_input,
        )
        form_layout.addRow(
            "예금주",
            self.account_holder_input,
        )
        form_layout.addRow(
            "주소",
            self.address_input,
        )
        form_layout.addRow(
            "메모",
            self.memo_input,
        )
        form_layout.addRow(
            "사용 상태",
            self.active_checkbox,
        )

        main_layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("취소")
        self.save_button = QPushButton("저장")

        self.cancel_button.setMinimumWidth(90)
        self.save_button.setMinimumWidth(90)

        self.save_button.setDefault(True)

        self.save_button.setStyleSheet(
            """
            QPushButton {
                min-height: 36px;
                padding: 0 18px;
                border: none;
                border-radius: 6px;
                background-color: #2563EB;
                color: white;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #1D4ED8;
            }

            QPushButton:pressed {
                background-color: #1E40AF;
            }
            """
        )

        self.cancel_button.setStyleSheet(
            """
            QPushButton {
                min-height: 36px;
                padding: 0 18px;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background-color: white;
                color: #334155;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #F8FAFC;
            }
            """
        )

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)

        self.cancel_button.clicked.connect(
            self.reject
        )
        self.save_button.clicked.connect(
            self._save_supplier
        )

    def _load_supplier(self) -> None:
        """수정할 공급처 정보를 조회해 입력창에 표시합니다."""

        if self.supplier_id is None:
            return

        supplier = self.repository.get_supplier_by_id(
            self.supplier_id
        )

        if supplier is None:
            QMessageBox.critical(
                self,
                "조회 오류",
                "수정할 공급처 정보를 찾을 수 없습니다.",
            )
            self.reject()
            return

        self.supplier_name_input.setText(
            self._text(supplier.get("supplier_name"))
        )
        self.manager_name_input.setText(
            self._text(supplier.get("contact_name"))
        )
        self.phone_input.setText(
            self._text(supplier.get("phone"))
        )
        self.email_input.setText(
            self._text(supplier.get("email"))
        )
        self.bank_name_input.setText(
            self._text(supplier.get("bank_name"))
        )
        self.account_number_input.setText(
            self._text(supplier.get("bank_account"))
        )
        self.account_holder_input.setText(
            self._text(supplier.get("account_holder"))
        )
        self.address_input.setText(
            self._text(supplier.get("address"))
        )
        self.memo_input.setPlainText(
            self._text(supplier.get("memo"))
        )
        self.active_checkbox.setChecked(
            bool(supplier.get("is_active"))
        )

    def _save_supplier(self) -> None:
        """입력값을 검증한 후 공급처를 저장합니다."""

        supplier_name = (
            self.supplier_name_input.text().strip()
        )

        if not supplier_name:
            QMessageBox.warning(
                self,
                "입력 확인",
                "공급처명을 입력해 주세요.",
            )
            self.supplier_name_input.setFocus()
            return

        email = self.email_input.text().strip()

        if email and "@" not in email:
            QMessageBox.warning(
                self,
                "입력 확인",
                "이메일 주소 형식을 확인해 주세요.",
            )
            self.email_input.setFocus()
            return

        values = {
            "supplier_name": supplier_name,
            "manager_name": (
                self.manager_name_input.text().strip()
                or None
            ),
            "phone": (
                self.phone_input.text().strip()
                or None
            ),
            "email": email or None,
            "bank_name": (
                self.bank_name_input.text().strip()
                or None
            ),
            "account_number": (
                self.account_number_input.text().strip()
                or None
            ),
            "account_holder": (
                self.account_holder_input.text().strip()
                or None
            ),
            "address": (
                self.address_input.text().strip()
                or None
            ),
            "memo": (
                self.memo_input.toPlainText().strip()
                or None
            ),
        }

        try:
            if self.supplier_id is None:
                self.repository.create_supplier(
                    **values
                )
            else:
                self.repository.update_supplier(
                    self.supplier_id,
                    **values,
                    is_active=(
                        self.active_checkbox.isChecked()
                    ),
                )

        except (ValueError, RuntimeError) as error:
            QMessageBox.warning(
                self,
                "저장 실패",
                str(error),
            )
            return

        except Exception as error:
            QMessageBox.critical(
                self,
                "저장 오류",
                f"공급처 저장 중 오류가 발생했습니다.\n\n{error}",
            )
            return

        self.accept()

    @staticmethod
    def _text(value: Any) -> str:
        """None을 빈 문자열로 변환합니다."""

        if value is None:
            return ""

        return str(value)