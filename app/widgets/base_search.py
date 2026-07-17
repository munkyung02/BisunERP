from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)


class ERPBaseSearch(QWidget):
    """ERP 공통 검색 위젯"""

    search_requested = Signal(str)
    reset_requested = Signal()

    def __init__(self, placeholder="검색어를 입력하세요.", parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)

        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText(placeholder)

        self.search_button = QPushButton("검색")

        self.reset_button = QPushButton("초기화")

        layout.addWidget(self.keyword_edit)
        layout.addWidget(self.search_button)
        layout.addWidget(self.reset_button)

        self.search_button.clicked.connect(self.search)

        self.reset_button.clicked.connect(self.reset)

        self.keyword_edit.returnPressed.connect(self.search)

    def keyword(self):
        return self.keyword_edit.text().strip()

    def search(self):
        self.search_requested.emit(self.keyword())

    def reset(self):
        self.keyword_edit.clear()
        self.reset_requested.emit()
        