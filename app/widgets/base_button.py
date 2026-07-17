from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


class ERPButton(QPushButton):
    """비선상회 ERP 공통 버튼입니다."""

    BUTTON_STYLES = {
        "primary": """
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #1D4ED8;
            }

            QPushButton:pressed {
                background-color: #1E40AF;
            }

            QPushButton:disabled {
                background-color: #CBD5E1;
                color: #64748B;
            }
        """,
        "success": """
            QPushButton {
                background-color: #16A34A;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #15803D;
            }

            QPushButton:pressed {
                background-color: #166534;
            }

            QPushButton:disabled {
                background-color: #CBD5E1;
                color: #64748B;
            }
        """,
        "danger": """
            QPushButton {
                background-color: #DC2626;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #B91C1C;
            }

            QPushButton:pressed {
                background-color: #991B1B;
            }

            QPushButton:disabled {
                background-color: #CBD5E1;
                color: #64748B;
            }
        """,
        "secondary": """
            QPushButton {
                background-color: white;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #F8FAFC;
                border-color: #94A3B8;
            }

            QPushButton:pressed {
                background-color: #F1F5F9;
            }

            QPushButton:disabled {
                background-color: #F1F5F9;
                color: #94A3B8;
            }
        """,
    }

    def __init__(
        self,
        text: str,
        button_type: str = "primary",
        parent=None,
    ) -> None:
        super().__init__(text, parent)

        self.button_type = button_type

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)

        self.set_button_type(button_type)

    def set_button_type(
        self,
        button_type: str,
    ) -> None:
        """버튼 종류에 맞는 스타일을 적용합니다."""

        if button_type not in self.BUTTON_STYLES:
            raise ValueError(
                f"지원하지 않는 버튼 종류입니다: {button_type}"
            )

        self.button_type = button_type
        self.setStyleSheet(
            self.BUTTON_STYLES[button_type]
        )