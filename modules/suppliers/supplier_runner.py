import sys

from PySide6.QtWidgets import QApplication

from modules.suppliers.supplier_page import SupplierPage


def main() -> None:
    app = QApplication.instance()

    if app is None:
        app = QApplication(sys.argv)

    window = SupplierPage()
    window.setWindowTitle("비선상회 ERP - 공급처관리")
    window.resize(1250, 720)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()