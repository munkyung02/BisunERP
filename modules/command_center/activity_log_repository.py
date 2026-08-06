from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"


class ActivityLogRepository:
    """Command Center에서 시작한 작업의 실행 결과만 기록합니다."""

    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS erp_activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    result_status TEXT NOT NULL,
                    result_message TEXT NOT NULL DEFAULT '',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_erp_activity_logs_created_at
                ON erp_activity_logs(created_at);

                CREATE INDEX IF NOT EXISTS idx_erp_activity_logs_status
                ON erp_activity_logs(result_status);
                """
            )
            connection.commit()

    def append(
        self,
        *,
        action: str,
        result_status: str,
        result_message: str = "",
        details: dict[str, Any] | None = None,
    ) -> int:
        details_json = json.dumps(
            details or {},
            ensure_ascii=False,
            default=str,
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO erp_activity_logs (
                    action,
                    result_status,
                    result_message,
                    details_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(action).strip(),
                    str(result_status).strip(),
                    str(result_message).strip(),
                    details_json,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, action, result_status, result_message, created_at
                FROM erp_activity_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_failed_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM erp_activity_logs
                WHERE result_status = '실패'
                """
            ).fetchone()
        return int(row["count"] or 0)
