from __future__ import annotations

import sqlite3
from pathlib import Path

from modules.orders.order_repository import OrderRepository
from modules.purchases.purchase_service import PurchaseService
from modules.shipments.channel_shipment_export_repository import (
    ChannelShipmentExportRepository,
)
from modules.shipments.shipment_repository import ShipmentRepository


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ReadOnlyConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect_read_only(database_path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    path = Path(database_path).resolve()
    connection = sqlite3.connect(
        f"{path.as_uri()}?mode=ro",
        uri=True,
        factory=ReadOnlyConnection,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


class _ReadOnlyConnectionMixin:
    database_path: Path

    def _connect(self) -> sqlite3.Connection:
        return connect_read_only(self.database_path)


class ReadOnlyOrderRepository(_ReadOnlyConnectionMixin, OrderRepository):
    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path)


class ReadOnlyPurchaseService(_ReadOnlyConnectionMixin, PurchaseService):
    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        super().__init__(database_path=database_path)


class ReadOnlyShipmentRepository(_ReadOnlyConnectionMixin, ShipmentRepository):
    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path)


class ReadOnlyChannelShipmentExportRepository(
    _ReadOnlyConnectionMixin,
    ChannelShipmentExportRepository,
):
    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
