from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)


class ERPForm(QWidget):
    """ERP 등록·수정 화면에서 사용하는 공통 폼입니다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.form_layout = QFormLayout(self)

        self.form_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.form_layout.setSpacing(12)

        self.fields: dict[str, QWidget] = {}

    def add_text_field(
        self,
        name: str,
        label: str,
        placeholder: str = "",
        required: bool = False,
    ) -> QLineEdit:
        """한 줄 텍스트 입력 필드를 추가합니다."""

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setMinimumHeight(34)

        display_label = (
            f"{label} *"
            if required
            else label
        )

        self.form_layout.addRow(
            display_label,
            field,
        )

        self.fields[name] = field

        return field

    def add_number_field(
        self,
        name: str,
        label: str,
        minimum: int = 0,
        maximum: int = 999_999_999,
    ) -> QSpinBox:
        """숫자 입력 필드를 추가합니다."""

        field = QSpinBox()

        field.setRange(
            minimum,
            maximum,
        )

        field.setMinimumHeight(34)
        field.setGroupSeparatorShown(True)

        self.form_layout.addRow(
            label,
            field,
        )

        self.fields[name] = field

        return field

    def add_combo_field(
        self,
        name: str,
        label: str,
        items: list[str] | None = None,
    ) -> QComboBox:
        """선택 목록 필드를 추가합니다."""

        field = QComboBox()
        field.setMinimumHeight(34)

        if items:
            field.addItems(items)

        self.form_layout.addRow(
            label,
            field,
        )

        self.fields[name] = field

        return field

    def text_value(
        self,
        name: str,
    ) -> str:
        """텍스트 필드 값을 반환합니다."""

        field = self.fields.get(name)

        if not isinstance(field, QLineEdit):
            raise KeyError(
                f"텍스트 필드를 찾을 수 없습니다: {name}"
            )

        return field.text().strip()

    def number_value(
        self,
        name: str,
    ) -> int:
        """숫자 필드 값을 반환합니다."""

        field = self.fields.get(name)

        if not isinstance(field, QSpinBox):
            raise KeyError(
                f"숫자 필드를 찾을 수 없습니다: {name}"
            )

        return field.value()

    def combo_value(
        self,
        name: str,
    ) -> str:
        """콤보박스의 현재 표시 값을 반환합니다."""

        field = self.fields.get(name)

        if not isinstance(field, QComboBox):
            raise KeyError(
                f"선택 필드를 찾을 수 없습니다: {name}"
            )

        return field.currentText().strip()

    def clear_fields(self) -> None:
        """모든 입력값을 초기화합니다."""

        for field in self.fields.values():
            if isinstance(field, QLineEdit):
                field.clear()

            elif isinstance(field, QSpinBox):
                field.setValue(
                    field.minimum()
                )

            elif isinstance(field, QComboBox):
                if field.count() > 0:
                    field.setCurrentIndex(0)