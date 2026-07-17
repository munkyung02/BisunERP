import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
)

from modules.products.product_page import ProductPage


class ProductWindow(QMainWindow):
    """비선상회 ERP 상품관리 독립 실행 창입니다."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(
            "비선상회 ERP - 상품관리"
        )
        self.resize(
            1500,
            850,
        )
        self.setMinimumSize(
            1100,
            650,
        )

        self.product_page = ProductPage()
        self.setCentralWidget(
            self.product_page
        )


def main() -> int:
    app = QApplication.instance()

    owns_application = app is None

    if app is None:
        app = QApplication(sys.argv)

    window = ProductWindow()
    window.show()

    if owns_application:
        return app.exec()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())