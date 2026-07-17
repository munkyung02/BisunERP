from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.widgets.base_button import ERPButton


class ERPDialog(QDialog):
    """ERP 공통 등록·수정 다이얼로그입니다."""

    def __init__(
        self,
        title: str,
        parent=None,
        width: int = 520,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)

        self.main_layout = QVBoxLayout(self)

        self.main_layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )

        self.main_layout.setSpacing(18)

        self.title_label = QLabel(title)

        self.title_label.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: 700;
                color: #0F172A;
            }
            """
        )

        self.main_layout.addWidget(
            self.title_label
        )

        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(
            self.content_container
        )

        self.content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.main_layout.addWidget(
            self.content_container
        )

        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()

        self.cancel_button = ERPButton(
            "취소",
            "secondary",
        )

        self.save_button = ERPButton(
            "저장",
            "success",
        )

        self.button_layout.addWidget(
            self.cancel_button
        )

        self.button_layout.addWidget(
            self.save_button
        )

        self.main_layout.addLayout(
            self.button_layout
        )

        self.cancel_button.clicked.connect(
            self.reject
        )

    def set_content(
        self,
        widget: QWidget,
    ) -> None:
        """Dialog 본문에 위젯을 추가합니다."""

        self.content_layout.addWidget(widget)

    def set_save_text(
        self,
        text: str,
    ) -> None:
        """저장 버튼 문구를 변경합니다."""

        self.save_button.setText(text)