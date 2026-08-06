import sys
from PySide6.QtWidgets import QApplication
from modules.customers.customer_page import CustomerPage


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = CustomerPage()
    window.setWindowTitle("비선상회 ERP - 거래처관리")
    window.resize(1400, 760)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
