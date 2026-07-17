from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.products.product_dialog import ProductDialog
from modules.products.product_repository import ProductRepository


class ProductPage(QWidget):
    """비선상회 ERP 상품관리 페이지입니다."""

    COLUMN_PRODUCT_CODE = 0
    COLUMN_PLATFORM = 1
    COLUMN_PLATFORM_PRODUCT_NAME = 2
    COLUMN_PRODUCT_NAME = 3
    COLUMN_OPTION_NAME = 4
    COLUMN_SUPPLIER_NAME = 5
    COLUMN_SUPPLIER_PRODUCT_NAME = 6
    COLUMN_PURCHASE_PRICE = 7
    COLUMN_SALE_PRICE = 8
    COLUMN_PURCHASE_ROUND = 9
    COLUMN_STATUS = 10

    TABLE_HEADERS = [
        "상품코드",
        "플랫폼",
        "판매처 상품명",
        "내부 상품명",
        "옵션명",
        "공급처",
        "공급처 상품명",
        "매입가",
        "판매가",
        "발주차수",
        "상태",
    ]

    STATUS_FILTERS = [
        ("전체 상품", None),
        ("사용 상품", True),
        ("중지 상품", False),
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.repository = ProductRepository()
        self.current_products: list[dict[str, Any]] = []

        self._create_widgets()
        self._create_layout()
        self._apply_styles()
        self._connect_signals()
        self.load_products()

    # =========================================================
    # 위젯 생성
    # =========================================================

    def _create_widgets(self) -> None:
        self.title_label = QLabel("상품관리")
        self.title_label.setObjectName("pageTitle")

        self.description_label = QLabel(
            "판매처 상품과 공급처 발주 상품을 등록하고 관리합니다."
        )
        self.description_label.setObjectName(
            "pageDescription"
        )

        self.total_card = self._create_summary_card(
            title="전체 상품",
            value="0건",
        )
        self.total_value_label = (
            self.total_card.findChild(
                QLabel,
                "summaryValue",
            )
        )

        self.active_card = self._create_summary_card(
            title="사용 상품",
            value="0건",
        )
        self.active_value_label = (
            self.active_card.findChild(
                QLabel,
                "summaryValue",
            )
        )

        self.inactive_card = self._create_summary_card(
            title="중지 상품",
            value="0건",
        )
        self.inactive_value_label = (
            self.inactive_card.findChild(
                QLabel,
                "summaryValue",
            )
        )

        self.purchase_total_card = (
            self._create_summary_card(
                title="조회 매입금액",
                value="0원",
            )
        )
        self.purchase_total_value_label = (
            self.purchase_total_card.findChild(
                QLabel,
                "summaryValue",
            )
        )

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText(
            "상품코드, 상품명, 판매처 상품명, "
            "공급처 상품명, 공급처명 검색"
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(380)

        self.status_filter_combo = QComboBox()
        self.status_filter_combo.setObjectName(
            "statusFilter"
        )
        self.status_filter_combo.setMinimumWidth(130)

        for label, value in self.STATUS_FILTERS:
            self.status_filter_combo.addItem(
                label,
                value,
            )

        self.search_button = QPushButton("검색")
        self.search_button.setObjectName(
            "secondaryButton"
        )

        self.reset_button = QPushButton(
            "검색 초기화"
        )
        self.reset_button.setObjectName(
            "secondaryButton"
        )

        self.create_button = QPushButton(
            "상품 등록"
        )
        self.create_button.setObjectName(
            "primaryButton"
        )

        self.edit_button = QPushButton(
            "상품 수정"
        )
        self.edit_button.setObjectName(
            "secondaryButton"
        )
        self.edit_button.setEnabled(False)

        self.toggle_active_button = QPushButton(
            "사용 중지"
        )
        self.toggle_active_button.setObjectName(
            "warningButton"
        )
        self.toggle_active_button.setEnabled(False)

        self.refresh_button = QPushButton(
            "새로고침"
        )
        self.refresh_button.setObjectName(
            "secondaryButton"
        )

        self.product_table = QTableWidget()
        self.product_table.setObjectName(
            "productTable"
        )
        self.product_table.setColumnCount(
            len(self.TABLE_HEADERS)
        )
        self.product_table.setHorizontalHeaderLabels(
            self.TABLE_HEADERS
        )

        self.product_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.product_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.product_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.product_table.setAlternatingRowColors(
            True
        )
        self.product_table.setSortingEnabled(True)
        self.product_table.setShowGrid(False)
        self.product_table.verticalHeader().setVisible(
            False
        )
        self.product_table.verticalHeader().setDefaultSectionSize(
            42
        )

        self.product_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._configure_table_header()

        self.result_count_label = QLabel(
            "조회 결과 0건"
        )
        self.result_count_label.setObjectName(
            "resultCount"
        )

        self.selection_info_label = QLabel(
            "수정할 상품을 선택하세요."
        )
        self.selection_info_label.setObjectName(
            "selectionInfo"
        )

    def _create_summary_card(
        self,
        *,
        title: str,
        value: str,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("summaryCard")
        card.setMinimumHeight(92)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            18,
            14,
            18,
            14,
        )
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName(
            "summaryTitle"
        )

        value_label = QLabel(value)
        value_label.setObjectName(
            "summaryValue"
        )

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addStretch()

        return card

    # =========================================================
    # 레이아웃
    # =========================================================

    def _create_layout(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            26,
            24,
            26,
            24,
        )
        main_layout.setSpacing(18)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)
        header_layout.addWidget(
            self.title_label
        )
        header_layout.addWidget(
            self.description_label
        )

        main_layout.addLayout(
            header_layout
        )

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(12)
        summary_layout.addWidget(
            self.total_card
        )
        summary_layout.addWidget(
            self.active_card
        )
        summary_layout.addWidget(
            self.inactive_card
        )
        summary_layout.addWidget(
            self.purchase_total_card
        )

        main_layout.addLayout(
            summary_layout
        )

        search_frame = QFrame()
        search_frame.setObjectName(
            "toolbarFrame"
        )

        search_frame_layout = QVBoxLayout(
            search_frame
        )
        search_frame_layout.setContentsMargins(
            16,
            14,
            16,
            14,
        )
        search_frame_layout.setSpacing(12)

        search_layout = QHBoxLayout()
        search_layout.setSpacing(9)

        search_layout.addWidget(
            self.search_input,
            1,
        )
        search_layout.addWidget(
            self.status_filter_combo
        )
        search_layout.addWidget(
            self.search_button
        )
        search_layout.addWidget(
            self.reset_button
        )

        button_layout = QHBoxLayout()
        button_layout.setSpacing(9)

        button_layout.addWidget(
            self.create_button
        )
        button_layout.addWidget(
            self.edit_button
        )
        button_layout.addWidget(
            self.toggle_active_button
        )
        button_layout.addStretch()
        button_layout.addWidget(
            self.refresh_button
        )

        search_frame_layout.addLayout(
            search_layout
        )
        search_frame_layout.addLayout(
            button_layout
        )

        main_layout.addWidget(
            search_frame
        )

        table_frame = QFrame()
        table_frame.setObjectName(
            "tableFrame"
        )

        table_layout = QVBoxLayout(
            table_frame
        )
        table_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        table_layout.setSpacing(0)
        table_layout.addWidget(
            self.product_table
        )

        main_layout.addWidget(
            table_frame,
            1,
        )

        footer_layout = QHBoxLayout()
        footer_layout.addWidget(
            self.result_count_label
        )
        footer_layout.addStretch()
        footer_layout.addWidget(
            self.selection_info_label
        )

        main_layout.addLayout(
            footer_layout
        )

    # =========================================================
    # 테이블 설정
    # =========================================================

    def _configure_table_header(self) -> None:
        header = self.product_table.horizontalHeader()

        header.setHighlightSections(False)
        header.setMinimumSectionSize(70)

        for column in range(
            len(self.TABLE_HEADERS)
        ):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        header.setSectionResizeMode(
            self.COLUMN_PLATFORM_PRODUCT_NAME,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            self.COLUMN_PRODUCT_NAME,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            self.COLUMN_SUPPLIER_PRODUCT_NAME,
            QHeaderView.ResizeMode.Stretch,
        )

        self.product_table.setColumnWidth(
            self.COLUMN_PRODUCT_CODE,
            110,
        )
        self.product_table.setColumnWidth(
            self.COLUMN_PLATFORM,
            90,
        )
        self.product_table.setColumnWidth(
            self.COLUMN_OPTION_NAME,
            120,
        )
        self.product_table.setColumnWidth(
            self.COLUMN_SUPPLIER_NAME,
            130,
        )
        self.product_table.setColumnWidth(
            self.COLUMN_PURCHASE_PRICE,
            100,
        )
        self.product_table.setColumnWidth(
            self.COLUMN_SALE_PRICE,
            100,
        )
        self.product_table.setColumnWidth(
            self.COLUMN_PURCHASE_ROUND,
            95,
        )
        self.product_table.setColumnWidth(
            self.COLUMN_STATUS,
            75,
        )

    # =========================================================
    # 시그널 연결
    # =========================================================

    def _connect_signals(self) -> None:
        self.search_button.clicked.connect(
            self.search_products
        )

        self.search_input.returnPressed.connect(
            self.search_products
        )

        self.status_filter_combo.currentIndexChanged.connect(
            self.search_products
        )

        self.reset_button.clicked.connect(
            self.reset_search
        )

        self.create_button.clicked.connect(
            self.open_create_dialog
        )

        self.edit_button.clicked.connect(
            self.open_edit_dialog
        )

        self.toggle_active_button.clicked.connect(
            self.toggle_selected_product_active
        )

        self.refresh_button.clicked.connect(
            self.refresh_products
        )

        self.product_table.itemSelectionChanged.connect(
            self._handle_selection_changed
        )

        self.product_table.itemDoubleClicked.connect(
            self._handle_double_click
        )

    # =========================================================
    # 상품 조회
    # =========================================================

    def load_products(
        self,
        keyword: str | None = None,
        active_only: bool | None = None,
    ) -> None:
        """DB에서 상품 목록을 불러와 테이블에 표시합니다."""

        self._set_loading_state(True)

        try:
            products = self._get_products_from_repository(
                keyword=keyword,
                active_only=active_only,
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "상품 조회 오류",
                "상품 목록을 불러오지 못했습니다.\n\n"
                f"{error}",
            )
            return

        finally:
            self._set_loading_state(False)

        self.current_products = products

        sorting_enabled = (
            self.product_table.isSortingEnabled()
        )

        self.product_table.setSortingEnabled(
            False
        )
        self.product_table.setRowCount(0)

        for row_index, product in enumerate(
            products
        ):
            self.product_table.insertRow(
                row_index
            )
            self._set_product_row(
                row_index,
                product,
            )

        self.product_table.setSortingEnabled(
            sorting_enabled
        )

        self.product_table.clearSelection()

        self._update_summary_cards()
        self._update_result_count()
        self._handle_selection_changed()

    def _get_products_from_repository(
        self,
        *,
        keyword: str | None,
        active_only: bool | None,
    ) -> list[dict[str, Any]]:
        """Repository 버전 차이를 고려해 상품을 조회합니다."""

        cleaned_keyword = (
            keyword.strip()
            if keyword
            else None
        )

        try:
            products = self.repository.get_products(
                keyword=cleaned_keyword,
                active_only=active_only,
            )

            return [
                dict(product)
                for product in products
            ]

        except TypeError:
            products = (
                self.repository.get_products()
            )

            converted_products = [
                dict(product)
                for product in products
            ]

            return self._filter_products_locally(
                converted_products,
                keyword=cleaned_keyword,
                active_only=active_only,
            )

    def _filter_products_locally(
        self,
        products: list[dict[str, Any]],
        *,
        keyword: str | None,
        active_only: bool | None,
    ) -> list[dict[str, Any]]:
        """Repository가 검색 인자를 지원하지 않을 때 화면에서 검색합니다."""

        filtered_products = products

        if active_only is not None:
            expected_active = (
                1 if active_only else 0
            )

            filtered_products = [
                product
                for product in filtered_products
                if self._to_int(
                    product.get("is_active")
                )
                == expected_active
            ]

        if keyword:
            lowered_keyword = keyword.lower()

            search_fields = [
                "product_code",
                "platform",
                "platform_product_name",
                "product_name",
                "option_name",
                "supplier_name",
                "supplier_product_name",
                "purchase_round",
            ]

            filtered_products = [
                product
                for product in filtered_products
                if any(
                    lowered_keyword
                    in self._display_text(
                        product.get(field)
                    ).lower()
                    for field in search_fields
                )
            ]

        return filtered_products

    def _set_product_row(
        self,
        row_index: int,
        product: dict[str, Any],
    ) -> None:
        product_id = self._to_int(
            product.get("id")
        )
        is_active = (
            self._to_int(
                product.get("is_active")
            )
            == 1
        )

        product_code_item = (
            self._create_text_item(
                product.get("product_code"),
                default="-",
            )
        )

        product_code_item.setData(
            Qt.ItemDataRole.UserRole,
            product_id,
        )
        product_code_item.setData(
            Qt.ItemDataRole.UserRole + 1,
            1 if is_active else 0,
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_PRODUCT_CODE,
            product_code_item,
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_PLATFORM,
            self._create_text_item(
                product.get("platform"),
                default="-",
                alignment=Qt.AlignmentFlag.AlignCenter,
            ),
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_PLATFORM_PRODUCT_NAME,
            self._create_text_item(
                product.get(
                    "platform_product_name"
                ),
                default="-",
            ),
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_PRODUCT_NAME,
            self._create_text_item(
                product.get("product_name"),
                default="-",
            ),
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_OPTION_NAME,
            self._create_text_item(
                product.get("option_name"),
                default="-",
            ),
        )

        supplier_name = (
            product.get("supplier_name")
            or product.get("supplier")
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_SUPPLIER_NAME,
            self._create_text_item(
                supplier_name,
                default="미지정",
            ),
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_SUPPLIER_PRODUCT_NAME,
            self._create_text_item(
                product.get(
                    "supplier_product_name"
                ),
                default="-",
            ),
        )

        purchase_price = self._to_int(
            product.get("purchase_price")
        )
        sale_price = self._to_int(
            product.get("sale_price")
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_PURCHASE_PRICE,
            self._create_price_item(
                purchase_price
            ),
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_SALE_PRICE,
            self._create_price_item(
                sale_price
            ),
        )

        self.product_table.setItem(
            row_index,
            self.COLUMN_PURCHASE_ROUND,
            self._create_text_item(
                product.get("purchase_round"),
                default="-",
                alignment=Qt.AlignmentFlag.AlignCenter,
            ),
        )

        status_item = QTableWidgetItem(
            "사용" if is_active else "중지"
        )
        status_item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        status_item.setData(
            Qt.ItemDataRole.UserRole,
            1 if is_active else 0,
        )

        if is_active:
            status_item.setForeground(
                QColor("#127A45")
            )
            status_item.setBackground(
                QColor("#EAF8F0")
            )
        else:
            status_item.setForeground(
                QColor("#A33A32")
            )
            status_item.setBackground(
                QColor("#FDEEEE")
            )

        self.product_table.setItem(
            row_index,
            self.COLUMN_STATUS,
            status_item,
        )

    # =========================================================
    # 검색 및 새로고침
    # =========================================================

    def search_products(self) -> None:
        keyword = self.search_input.text().strip()
        active_only = (
            self.status_filter_combo.currentData()
        )

        self.load_products(
            keyword=keyword or None,
            active_only=active_only,
        )

    def reset_search(self) -> None:
        self.search_input.clear()
        self.status_filter_combo.setCurrentIndex(
            0
        )
        self.load_products()

    def refresh_products(self) -> None:
        keyword = self.search_input.text().strip()
        active_only = (
            self.status_filter_combo.currentData()
        )

        self.load_products(
            keyword=keyword or None,
            active_only=active_only,
        )

    # =========================================================
    # 등록 및 수정
    # =========================================================

    def open_create_dialog(self) -> None:
        dialog = ProductDialog(
            parent=self
        )

        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            self.refresh_products()

    def open_edit_dialog(self) -> None:
        product_id = (
            self._get_selected_product_id()
        )

        if product_id is None:
            QMessageBox.information(
                self,
                "상품 선택",
                "수정할 상품을 먼저 선택해 주세요.",
            )
            return

        dialog = ProductDialog(
            parent=self,
            product_id=product_id,
        )

        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            self.refresh_products()

    def _handle_double_click(
        self,
        _: QTableWidgetItem,
    ) -> None:
        self.open_edit_dialog()

    # =========================================================
    # 활성 및 비활성 처리
    # =========================================================

    def toggle_selected_product_active(
        self,
    ) -> None:
        product_id = (
            self._get_selected_product_id()
        )
        current_active = (
            self._get_selected_product_active()
        )

        if product_id is None:
            QMessageBox.information(
                self,
                "상품 선택",
                "상태를 변경할 상품을 선택해 주세요.",
            )
            return

        if current_active is None:
            QMessageBox.warning(
                self,
                "상태 확인 오류",
                "선택한 상품의 현재 상태를 "
                "확인하지 못했습니다.",
            )
            return

        new_active = not current_active

        action_text = (
            "사용 처리"
            if new_active
            else "사용 중지"
        )

        product_name = (
            self._get_selected_product_name()
        )

        answer = QMessageBox.question(
            self,
            "상품 상태 변경",
            f"'{product_name}' 상품을 "
            f"{action_text}하시겠습니까?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            changed_rows = (
                self._change_product_active(
                    product_id=product_id,
                    is_active=new_active,
                )
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "상태 변경 오류",
                "상품 상태를 변경하지 못했습니다.\n\n"
                f"{error}",
            )
            return

        if changed_rows == 0:
            QMessageBox.warning(
                self,
                "상품 없음",
                "상태를 변경할 상품을 "
                "찾을 수 없습니다.",
            )
            return

        QMessageBox.information(
            self,
            "변경 완료",
            f"상품이 {action_text}되었습니다.",
        )

        self.refresh_products()

    def _change_product_active(
        self,
        *,
        product_id: int,
        is_active: bool,
    ) -> int:
        """Repository 메서드 이름 차이를 지원합니다."""

        if hasattr(
            self.repository,
            "set_product_active",
        ):
            method = getattr(
                self.repository,
                "set_product_active",
            )

            try:
                result = method(
                    product_id,
                    is_active,
                )
            except TypeError:
                result = method(
                    product_id=product_id,
                    is_active=is_active,
                )

            return self._normalize_changed_rows(
                result
            )

        if hasattr(
            self.repository,
            "update_product_active",
        ):
            method = getattr(
                self.repository,
                "update_product_active",
            )

            result = method(
                product_id=product_id,
                is_active=is_active,
            )

            return self._normalize_changed_rows(
                result
            )

        raise AttributeError(
            "ProductRepository에 "
            "set_product_active() 메서드가 없습니다."
        )

    @staticmethod
    def _normalize_changed_rows(
        result: Any,
    ) -> int:
        if result is None:
            return 1

        if isinstance(result, bool):
            return 1 if result else 0

        try:
            return int(result)
        except (TypeError, ValueError):
            return 1

    # =========================================================
    # 선택 행 처리
    # =========================================================

    def _handle_selection_changed(self) -> None:
        product_id = (
            self._get_selected_product_id()
        )
        current_active = (
            self._get_selected_product_active()
        )

        has_selection = (
            product_id is not None
        )

        self.edit_button.setEnabled(
            has_selection
        )
        self.toggle_active_button.setEnabled(
            has_selection
        )

        if not has_selection:
            self.toggle_active_button.setText(
                "사용 중지"
            )
            self.selection_info_label.setText(
                "수정할 상품을 선택하세요."
            )
            return

        product_name = (
            self._get_selected_product_name()
        )

        self.selection_info_label.setText(
            f"선택 상품: {product_name}"
        )

        if current_active:
            self.toggle_active_button.setText(
                "사용 중지"
            )
        else:
            self.toggle_active_button.setText(
                "다시 사용"
            )

    def _get_selected_row(
        self,
    ) -> int | None:
        selection_model = (
            self.product_table.selectionModel()
        )

        if selection_model is None:
            return None

        selected_rows = (
            selection_model.selectedRows()
        )

        if not selected_rows:
            return None

        return selected_rows[0].row()

    def _get_selected_product_id(
        self,
    ) -> int | None:
        row = self._get_selected_row()

        if row is None:
            return None

        item = self.product_table.item(
            row,
            self.COLUMN_PRODUCT_CODE,
        )

        if item is None:
            return None

        product_id = item.data(
            Qt.ItemDataRole.UserRole
        )

        try:
            converted_id = int(product_id)
        except (TypeError, ValueError):
            return None

        if converted_id <= 0:
            return None

        return converted_id

    def _get_selected_product_active(
        self,
    ) -> bool | None:
        row = self._get_selected_row()

        if row is None:
            return None

        status_item = self.product_table.item(
            row,
            self.COLUMN_STATUS,
        )

        if status_item is None:
            return None

        is_active = status_item.data(
            Qt.ItemDataRole.UserRole
        )

        return self._to_int(is_active) == 1

    def _get_selected_product_name(
        self,
    ) -> str:
        row = self._get_selected_row()

        if row is None:
            return "선택 상품"

        item = self.product_table.item(
            row,
            self.COLUMN_PRODUCT_NAME,
        )

        if item is None:
            return "선택 상품"

        return item.text().strip() or "선택 상품"

    # =========================================================
    # 요약 표시
    # =========================================================

    def _update_summary_cards(self) -> None:
        total_count = len(
            self.current_products
        )

        active_count = sum(
            1
            for product in self.current_products
            if self._to_int(
                product.get("is_active")
            )
            == 1
        )

        inactive_count = (
            total_count - active_count
        )

        total_purchase_price = sum(
            self._to_int(
                product.get("purchase_price")
            )
            for product in self.current_products
        )

        if self.total_value_label is not None:
            self.total_value_label.setText(
                f"{total_count:,}건"
            )

        if self.active_value_label is not None:
            self.active_value_label.setText(
                f"{active_count:,}건"
            )

        if self.inactive_value_label is not None:
            self.inactive_value_label.setText(
                f"{inactive_count:,}건"
            )

        if (
            self.purchase_total_value_label
            is not None
        ):
            self.purchase_total_value_label.setText(
                f"{total_purchase_price:,}원"
            )

    def _update_result_count(self) -> None:
        keyword = self.search_input.text().strip()
        filter_name = (
            self.status_filter_combo.currentText()
        )

        text = (
            f"조회 결과 "
            f"{len(self.current_products):,}건"
        )

        if keyword:
            text += f" · 검색어: {keyword}"

        if filter_name != "전체 상품":
            text += f" · {filter_name}"

        self.result_count_label.setText(
            text
        )

    # =========================================================
    # 공통 유틸리티
    # =========================================================

    def _set_loading_state(
        self,
        loading: bool,
    ) -> None:
        self.search_button.setEnabled(
            not loading
        )
        self.refresh_button.setEnabled(
            not loading
        )
        self.create_button.setEnabled(
            not loading
        )

        if loading:
            self.result_count_label.setText(
                "상품 목록을 불러오는 중입니다..."
            )

    @staticmethod
    def _create_text_item(
        value: Any,
        *,
        default: str = "",
        alignment: Qt.AlignmentFlag | None = None,
    ) -> QTableWidgetItem:
        text = ProductPage._display_text(
            value
        )

        if not text:
            text = default

        item = QTableWidgetItem(text)

        if alignment is not None:
            item.setTextAlignment(
                alignment
            )

        return item

    @staticmethod
    def _create_price_item(
        value: int,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(
            f"{value:,}"
        )
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        # 숫자 정렬을 위한 원본 값
        item.setData(
            Qt.ItemDataRole.UserRole,
            value,
        )

        return item

    @staticmethod
    def _display_text(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def _to_int(
        value: Any,
    ) -> int:
        if value in (None, ""):
            return 0

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    # =========================================================
    # 디자인
    # =========================================================

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                font-family:
                    "Malgun Gothic",
                    "맑은 고딕",
                    sans-serif;
                font-size: 13px;
                color: #202124;
                background-color: #F5F7FA;
            }

            QLabel#pageTitle {
                font-size: 25px;
                font-weight: 700;
                color: #172033;
                background-color: transparent;
            }

            QLabel#pageDescription {
                font-size: 13px;
                color: #687386;
                background-color: transparent;
            }

            QFrame#summaryCard {
                background-color: #FFFFFF;
                border: 1px solid #E3E8EF;
                border-radius: 10px;
            }

            QLabel#summaryTitle {
                font-size: 12px;
                color: #738095;
                background-color: transparent;
            }

            QLabel#summaryValue {
                font-size: 21px;
                font-weight: 700;
                color: #1F2937;
                background-color: transparent;
            }

            QFrame#toolbarFrame {
                background-color: #FFFFFF;
                border: 1px solid #E3E8EF;
                border-radius: 10px;
            }

            QFrame#tableFrame {
                background-color: #FFFFFF;
                border: 1px solid #E3E8EF;
                border-radius: 10px;
            }

            QLineEdit#searchInput {
                min-height: 38px;
                padding: 0 12px;
                background-color: #FFFFFF;
                border: 1px solid #CDD5DF;
                border-radius: 7px;
                selection-background-color: #315EFB;
            }

            QLineEdit#searchInput:focus {
                border: 1px solid #315EFB;
            }

            QComboBox#statusFilter {
                min-height: 38px;
                padding: 0 10px;
                background-color: #FFFFFF;
                border: 1px solid #CDD5DF;
                border-radius: 7px;
            }

            QPushButton {
                min-height: 38px;
                padding: 0 16px;
                border-radius: 7px;
                font-weight: 600;
            }

            QPushButton#primaryButton {
                color: #FFFFFF;
                background-color: #315EFB;
                border: 1px solid #315EFB;
            }

            QPushButton#primaryButton:hover {
                background-color: #244FE0;
            }

            QPushButton#secondaryButton {
                color: #27344A;
                background-color: #FFFFFF;
                border: 1px solid #CDD5DF;
            }

            QPushButton#secondaryButton:hover {
                background-color: #F2F5F9;
            }

            QPushButton#warningButton {
                color: #A14720;
                background-color: #FFF7ED;
                border: 1px solid #F5C59E;
            }

            QPushButton#warningButton:hover {
                background-color: #FFEDD5;
            }

            QPushButton:disabled {
                color: #A7AFBD;
                background-color: #F0F2F5;
                border: 1px solid #DEE2E8;
            }

            QTableWidget#productTable {
                background-color: #FFFFFF;
                alternate-background-color: #FAFBFD;
                border: none;
                gridline-color: #EDF0F4;
                selection-background-color: #E8EEFF;
                selection-color: #172033;
            }

            QTableWidget#productTable::item {
                padding-left: 8px;
                padding-right: 8px;
                border-bottom: 1px solid #EDF0F4;
            }

            QTableWidget#productTable::item:selected {
                background-color: #E8EEFF;
                color: #172033;
            }

            QHeaderView::section {
                min-height: 40px;
                padding: 0 8px;
                color: #4B5565;
                background-color: #F7F9FC;
                border: none;
                border-bottom: 1px solid #E3E8EF;
                font-weight: 700;
            }

            QLabel#resultCount,
            QLabel#selectionInfo {
                color: #687386;
                background-color: transparent;
            }
            """
        )