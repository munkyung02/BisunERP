from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
)


class ERPTable(QTableWidget):
    """ERP 공통 테이블"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAlternatingRowColors(True)

        self.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.setSelectionMode(
            QAbstractItemView.SingleSelection
        )

        self.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.setSortingEnabled(True)

        self.verticalHeader().setVisible(False)

        self.horizontalHeader().setStretchLastSection(True)

        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.Interactive
        )

        self.setShowGrid(True)

    def set_headers(self, headers: list[str]):
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

    def clear_rows(self):
        self.setRowCount(0)

    def add_row(self, values: list):
        row = self.rowCount()

        self.insertRow(row)

        from PySide6.QtWidgets import QTableWidgetItem

        for col, value in enumerate(values):
            item = QTableWidgetItem("" if value is None else str(value))
            self.setItem(row, col, item)
            