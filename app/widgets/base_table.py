from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)


class ERPTable(QTableWidget):
    """비선상회 ERP 공통 목록 테이블입니다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setAlternatingRowColors(True)

        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.setSortingEnabled(True)
        self.setShowGrid(True)

        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

    def set_headers(
        self,
        headers: list[str],
    ) -> None:
        """테이블 제목을 설정합니다."""

        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

    def clear_rows(self) -> None:
        """테이블의 모든 데이터 행을 삭제합니다."""

        self.setSortingEnabled(False)
        self.setRowCount(0)
        self.setSortingEnabled(True)

    def add_row(
        self,
        values: list[Any],
        row_id: int | None = None,
    ) -> int:
        """
        테이블에 행을 추가합니다.

        row_id는 첫 번째 셀의 UserRole 영역에 저장됩니다.
        화면에는 표시되지 않지만 수정·비활성화 시 사용합니다.
        """

        sorting_enabled = self.isSortingEnabled()
        self.setSortingEnabled(False)

        row_index = self.rowCount()
        self.insertRow(row_index)

        for column_index, value in enumerate(values):
            text = "" if value is None else str(value)
            item = QTableWidgetItem(text)

            if column_index == 0 and row_id is not None:
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    row_id,
                )

            self.setItem(
                row_index,
                column_index,
                item,
            )

        self.setSortingEnabled(sorting_enabled)

        return row_index

    def selected_row_index(self) -> int | None:
        """현재 선택된 행 번호를 반환합니다."""

        selected_rows = self.selectionModel().selectedRows()

        if not selected_rows:
            return None

        return selected_rows[0].row()

    def selected_row_id(self) -> int | None:
        """현재 선택된 행의 내부 DB ID를 반환합니다."""

        row_index = self.selected_row_index()

        if row_index is None:
            return None

        first_item = self.item(row_index, 0)

        if first_item is None:
            return None

        value = first_item.data(
            Qt.ItemDataRole.UserRole
        )

        if value is None:
            return None

        return int(value)

    def selected_value(
        self,
        column_index: int,
    ) -> str | None:
        """선택된 행에서 지정한 열의 값을 가져옵니다."""

        row_index = self.selected_row_index()

        if row_index is None:
            return None

        item = self.item(
            row_index,
            column_index,
        )

        if item is None:
            return None

        return item.text()

    def resize_columns_to_contents(
        self,
    ) -> None:
        """데이터에 맞춰 열 너비를 조정합니다."""

        self.resizeColumnsToContents()
        self.horizontalHeader().setStretchLastSection(True)