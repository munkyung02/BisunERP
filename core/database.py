import sqlite3
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "bisun_erp.db"


class Database:
    def __init__(self, database_path: Optional[Path] = None) -> None:
        self.database_path = database_path or DATABASE_PATH

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            self._create_suppliers_table(connection)
            self._create_products_table(connection)
            self._migrate_suppliers_table(connection)
            self._migrate_products_table(connection)
            self._create_supplier_product_conditions_table(connection)
            self._migrate_supplier_product_conditions_table(connection)
            self._create_notion_sync_logs_table(connection)
            self._migrate_notion_sync_logs_table(connection)
            self._create_customers_table(connection)
            self._create_orders_table(connection)
            self._create_order_items_table(connection)
            self._create_purchase_orders_table(connection)
            self._create_payments_table(connection)
            self._create_shipments_table(connection)
            self._migrate_shipments_table(connection)
            self._create_settings_table(connection)

            connection.commit()

    def _create_suppliers_table(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_code TEXT UNIQUE,
                supplier_name TEXT NOT NULL,
                contact_name TEXT,
                phone TEXT,
                email TEXT,
                bank_name TEXT,
                bank_account TEXT,
                account_holder TEXT,
                address TEXT,
                memo TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _create_products_table(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT UNIQUE,
                platform TEXT,
                platform_product_name TEXT,
                product_name TEXT NOT NULL,
                option_name TEXT,
                supplier_id INTEGER,
                supplier_product_name TEXT,
                purchase_price INTEGER NOT NULL DEFAULT 0,
                sale_price INTEGER NOT NULL DEFAULT 0,
                purchase_round TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (supplier_id)
                    REFERENCES suppliers(id)
                    ON DELETE SET NULL
            )
            """
        )


    def _migrate_suppliers_table(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute("PRAGMA table_info(suppliers)").fetchall()
        existing = {row["name"] for row in rows}
        columns = {
            "order_method": "TEXT",
            "default_courier": "TEXT",
            "default_shipping_fee": "INTEGER NOT NULL DEFAULT 0",
            "settlement_method": "TEXT",
            "handled_items": "TEXT",
            "notion_page_id": "TEXT",
            "notion_last_edited_time": "TEXT",
        }
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE suppliers ADD COLUMN {name} {definition}")

    def _migrate_products_table(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute("PRAGMA table_info(products)").fetchall()
        existing = {row["name"] for row in rows}
        columns = {
            "category": "TEXT",
            "sale_unit": "TEXT",
            "season": "TEXT",
            "origin": "TEXT",
            "packaging_type": "TEXT",
            "sales_status": "TEXT NOT NULL DEFAULT '판매중'",
            "notion_page_id": "TEXT",
            "notion_last_edited_time": "TEXT",
        }
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE products ADD COLUMN {name} {definition}")

    def _create_supplier_product_conditions_table(
        self, connection: sqlite3.Connection
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS supplier_product_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                supplier_id INTEGER NOT NULL,
                supplier_product_name TEXT,
                supplier_product_code TEXT,
                purchase_price INTEGER NOT NULL DEFAULT 0,
                minimum_order_quantity INTEGER NOT NULL DEFAULT 1,
                package_unit INTEGER NOT NULL DEFAULT 1,
                package_unit_name TEXT,
                shipping_fee INTEGER NOT NULL DEFAULT 0,
                courier_name TEXT,
                order_deadline TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'ERP',
                notion_page_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, supplier_id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
            )
            """
        )


    def _migrate_supplier_product_conditions_table(
        self, connection: sqlite3.Connection
    ) -> None:
        rows = connection.execute("PRAGMA table_info(supplier_product_conditions)").fetchall()
        existing = {row["name"] for row in rows}
        if "notion_last_edited_time" not in existing:
            connection.execute(
                "ALTER TABLE supplier_product_conditions ADD COLUMN notion_last_edited_time TEXT"
            )

    def _create_notion_sync_logs_table(
        self, connection: sqlite3.Connection
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notion_sync_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT,
                supplier_created INTEGER NOT NULL DEFAULT 0,
                supplier_updated INTEGER NOT NULL DEFAULT 0,
                supplier_deactivated INTEGER NOT NULL DEFAULT 0,
                product_created INTEGER NOT NULL DEFAULT 0,
                product_updated INTEGER NOT NULL DEFAULT 0,
                product_deactivated INTEGER NOT NULL DEFAULT 0,
                condition_created INTEGER NOT NULL DEFAULT 0,
                condition_updated INTEGER NOT NULL DEFAULT 0,
                condition_deactivated INTEGER NOT NULL DEFAULT 0,
                warning_count INTEGER NOT NULL DEFAULT 0,
                duration_seconds REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT '성공',
                message TEXT,
                error_message TEXT,
                synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _migrate_notion_sync_logs_table(
        self, connection: sqlite3.Connection
    ) -> None:
        """기존 DB에도 확장된 Notion 동기화 로그 컬럼을 안전하게 추가합니다."""
        rows = connection.execute(
            "PRAGMA table_info(notion_sync_logs)"
        ).fetchall()
        existing = {row["name"] for row in rows}
        columns = {
            "supplier_deactivated": "INTEGER NOT NULL DEFAULT 0",
            "product_deactivated": "INTEGER NOT NULL DEFAULT 0",
            "condition_deactivated": "INTEGER NOT NULL DEFAULT 0",
            "duration_seconds": "REAL NOT NULL DEFAULT 0",
            "error_message": "TEXT",
        }
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(
                    f"ALTER TABLE notion_sync_logs ADD COLUMN {name} {definition}"
                )

    def _create_customers_table(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_type TEXT NOT NULL DEFAULT '소매',
                business_name TEXT,
                customer_name TEXT,
                phone TEXT,
                email TEXT,
                postal_code TEXT,
                address TEXT,
                detail_address TEXT,
                business_number TEXT,
                representative_name TEXT,
                memo TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _create_orders_table(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                order_number TEXT NOT NULL,
                ordered_at TEXT,
                customer_id INTEGER,
                receiver_name TEXT,
                receiver_phone TEXT,
                postal_code TEXT,
                address TEXT,
                detail_address TEXT,
                delivery_message TEXT,
                order_status TEXT NOT NULL DEFAULT '주문접수',
                payment_status TEXT NOT NULL DEFAULT '결제완료',
                mapping_status TEXT NOT NULL DEFAULT '미매핑',
                purchase_status TEXT NOT NULL DEFAULT '발주대기',
                shipment_status TEXT NOT NULL DEFAULT '배송대기',
                total_amount INTEGER NOT NULL DEFAULT 0,
                source_file TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(platform, order_number),

                FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON DELETE SET NULL
            )
            """
        )

    def _create_order_items_table(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER,
                platform_product_name TEXT NOT NULL,
                option_name TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price INTEGER NOT NULL DEFAULT 0,
                total_price INTEGER NOT NULL DEFAULT 0,
                supplier_id INTEGER,
                purchase_round TEXT,
                mapping_status TEXT NOT NULL DEFAULT '미매핑',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (product_id)
                    REFERENCES products(id)
                    ON DELETE SET NULL,

                FOREIGN KEY (supplier_id)
                    REFERENCES suppliers(id)
                    ON DELETE SET NULL
            )
            """
        )

    def _create_purchase_orders_table(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER,
                order_id INTEGER NOT NULL,
                order_item_id INTEGER NOT NULL,
                supplier_name TEXT,
                order_number TEXT NOT NULL,
                product_name TEXT NOT NULL,
                option_name TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                receiver_name TEXT,
                receiver_phone TEXT,
                postal_code TEXT,
                address TEXT,
                delivery_message TEXT,
                purchase_status TEXT NOT NULL DEFAULT '발주대기',
                purchase_file TEXT,
                purchased_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(order_item_id),

                FOREIGN KEY (supplier_id)
                    REFERENCES suppliers(id)
                    ON DELETE SET NULL,

                FOREIGN KEY (order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (order_item_id)
                    REFERENCES order_items(id)
                    ON DELETE CASCADE
            )
            """
        )

    def _create_payments_table(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                customer_id INTEGER,
                depositor_name TEXT,
                payment_amount INTEGER NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL DEFAULT '계좌이체',
                payment_status TEXT NOT NULL DEFAULT '입금대기',
                paid_at TEXT,
                bank_message TEXT,
                memo TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (order_id)
                    REFERENCES orders(id)
                    ON DELETE SET NULL,

                FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON DELETE SET NULL
            )
            """
        )

    def _create_shipments_table(
            self,
            connection: sqlite3.Connection,
        ) -> None:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shipments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    order_item_id INTEGER,
                    supplier_id INTEGER,
                    courier_name TEXT,
                    tracking_number TEXT,
                    shipment_status TEXT NOT NULL DEFAULT '배송준비',
                    shipped_at TEXT,
                    delivered_at TEXT,
                    memo TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (order_id)
                        REFERENCES orders(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (order_item_id)
                        REFERENCES order_items(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (supplier_id)
                        REFERENCES suppliers(id)
                        ON DELETE SET NULL
                )
                """
        )
            
    def _migrate_shipments_table(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        """
        기존 shipments 테이블에 필요한 컬럼을 안전하게 추가합니다.
        이미 컬럼이 존재하면 아무 작업도 하지 않습니다.
        """

        rows = connection.execute(
            """
            PRAGMA table_info(shipments)
            """
        ).fetchall()

        existing_columns = {
            row["name"]
            for row in rows
        }

        if "order_item_id" not in existing_columns:
            connection.execute(
                """
                ALTER TABLE shipments
                ADD COLUMN order_item_id INTEGER
                """
            )

        if "supplier_id" not in existing_columns:
            connection.execute(
                """
                ALTER TABLE shipments
                ADD COLUMN supplier_id INTEGER
                """
            )            

    def _create_settings_table(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT NOT NULL UNIQUE,
                setting_value TEXT,
                description TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def get_table_names(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()

        return [row["name"] for row in rows]


def initialize_database() -> Database:
    database = Database()
    database.initialize()

    return database