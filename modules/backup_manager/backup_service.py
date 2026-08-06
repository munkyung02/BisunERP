from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"
BACKUP_ROOT = PROJECT_ROOT / "backup"
SETTINGS_PATH = PROJECT_ROOT / "data" / "backup_settings.json"


class BackupService:
    """SQLite 데이터베이스 백업·복원·보관정책을 관리합니다."""

    DEFAULT_SETTINGS = {
        "auto_backup_enabled": True,
        "auto_backup_on_startup": True,
        "retention_days": 30,
        "max_backup_count": 100,
        "backup_root": str(BACKUP_ROOT),
    }

    def __init__(
        self,
        database_path: str | Path | None = None,
        backup_root: str | Path | None = None,
        settings_path: str | Path | None = None,
    ) -> None:
        self.database_path = Path(database_path or DATABASE_PATH)
        self.settings_path = Path(settings_path or SETTINGS_PATH)

        self.settings = self.load_settings()

        configured_root = backup_root or self.settings.get(
            "backup_root"
        )
        self.backup_root = Path(
            configured_root or BACKUP_ROOT
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.backup_root.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.settings_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =========================================================
    # 설정
    # =========================================================

    def load_settings(self) -> dict[str, Any]:
        settings = dict(self.DEFAULT_SETTINGS)

        if self.settings_path.exists():
            try:
                loaded = json.loads(
                    self.settings_path.read_text(
                        encoding="utf-8"
                    )
                )
                if isinstance(loaded, dict):
                    settings.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass

        return settings

    def save_settings(
        self,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        cleaned = dict(self.DEFAULT_SETTINGS)
        cleaned.update(settings)

        cleaned["auto_backup_enabled"] = bool(
            cleaned.get("auto_backup_enabled", True)
        )
        cleaned["auto_backup_on_startup"] = bool(
            cleaned.get("auto_backup_on_startup", True)
        )
        cleaned["retention_days"] = max(
            1,
            int(cleaned.get("retention_days", 30)),
        )
        cleaned["max_backup_count"] = max(
            1,
            int(cleaned.get("max_backup_count", 100)),
        )

        root = Path(
            str(
                cleaned.get("backup_root")
                or BACKUP_ROOT
            )
        )
        root.mkdir(parents=True, exist_ok=True)
        cleaned["backup_root"] = str(root)

        self.settings_path.write_text(
            json.dumps(
                cleaned,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.settings = cleaned
        self.backup_root = root
        return dict(cleaned)

    # =========================================================
    # 백업
    # =========================================================

    def create_backup(
        self,
        *,
        reason: str = "수동",
    ) -> dict[str, Any]:
        if not self.database_path.exists():
            raise FileNotFoundError(
                f"데이터베이스 파일을 찾을 수 없습니다.\n"
                f"{self.database_path}"
            )

        now = datetime.now()
        date_folder = self.backup_root / now.strftime(
            "%Y-%m-%d"
        )
        date_folder.mkdir(parents=True, exist_ok=True)

        safe_reason = self._safe_filename(reason) or "백업"
        backup_path = date_folder / (
            f"bisun_erp_{now.strftime('%Y%m%d_%H%M%S')}_"
            f"{safe_reason}.db"
        )

        source_connection = sqlite3.connect(
            self.database_path
        )
        backup_connection = sqlite3.connect(
            backup_path
        )

        try:
            source_connection.backup(backup_connection)
            backup_connection.commit()
        finally:
            backup_connection.close()
            source_connection.close()

        self._verify_database(backup_path)
        self.cleanup_old_backups()

        return {
            "path": str(backup_path),
            "filename": backup_path.name,
            "size_bytes": backup_path.stat().st_size,
            "created_at": now.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "reason": reason,
        }

    def create_startup_backup(
        self,
    ) -> dict[str, Any] | None:
        settings = self.load_settings()

        if not settings.get("auto_backup_enabled", True):
            return None

        if not settings.get(
            "auto_backup_on_startup",
            True,
        ):
            return None

        today_backups = [
            item
            for item in self.list_backups()
            if str(item.get("created_at", "")).startswith(
                datetime.now().strftime("%Y-%m-%d")
            )
            and "자동시작" in str(
                item.get("filename", "")
            )
        ]

        if today_backups:
            return None

        return self.create_backup(reason="자동시작")

    # =========================================================
    # 복원
    # =========================================================

    def restore_backup(
        self,
        backup_path: str | Path,
    ) -> dict[str, Any]:
        source_path = Path(backup_path)

        if not source_path.exists():
            raise FileNotFoundError(
                "선택한 백업 파일을 찾을 수 없습니다."
            )

        self._verify_database(source_path)

        safety_backup = None

        if self.database_path.exists():
            safety_backup = self.create_backup(
                reason="복원직전"
            )

        temp_path = self.database_path.with_suffix(
            ".restore_tmp.db"
        )

        try:
            shutil.copy2(source_path, temp_path)
            self._verify_database(temp_path)

            if self.database_path.exists():
                self.database_path.unlink()

            temp_path.replace(self.database_path)

        except Exception:
            if temp_path.exists():
                temp_path.unlink()

            raise

        return {
            "restored_from": str(source_path),
            "database_path": str(self.database_path),
            "safety_backup": (
                safety_backup.get("path")
                if safety_backup
                else None
            ),
            "restored_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "restart_required": True,
        }

    # =========================================================
    # 목록·삭제·정리
    # =========================================================

    def list_backups(
        self,
    ) -> list[dict[str, Any]]:
        if not self.backup_root.exists():
            return []

        backups: list[dict[str, Any]] = []

        for path in self.backup_root.rglob("*.db"):
            try:
                stat = path.stat()
                created = datetime.fromtimestamp(
                    stat.st_mtime
                )
                backups.append({
                    "path": str(path),
                    "filename": path.name,
                    "created_at": created.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "size_bytes": stat.st_size,
                    "size_text": self._format_size(
                        stat.st_size
                    ),
                    "folder": path.parent.name,
                })
            except OSError:
                continue

        backups.sort(
            key=lambda item: item["created_at"],
            reverse=True,
        )
        return backups

    def delete_backup(
        self,
        backup_path: str | Path,
    ) -> None:
        path = Path(backup_path)

        if not path.exists():
            return

        try:
            path.resolve().relative_to(
                self.backup_root.resolve()
            )
        except ValueError as error:
            raise ValueError(
                "백업 폴더 외부의 파일은 삭제할 수 없습니다."
            ) from error

        path.unlink()

        try:
            path.parent.rmdir()
        except OSError:
            pass

    def cleanup_old_backups(
        self,
    ) -> dict[str, int]:
        settings = self.load_settings()
        retention_days = max(
            1,
            int(settings.get("retention_days", 30)),
        )
        max_count = max(
            1,
            int(settings.get("max_backup_count", 100)),
        )

        backups = self.list_backups()
        cutoff = datetime.now() - timedelta(
            days=retention_days
        )
        deleted = 0

        for item in backups:
            path = Path(str(item["path"]))

            try:
                modified = datetime.fromtimestamp(
                    path.stat().st_mtime
                )
            except OSError:
                continue

            if modified < cutoff:
                self.delete_backup(path)
                deleted += 1

        remaining = self.list_backups()

        for item in remaining[max_count:]:
            self.delete_backup(str(item["path"]))
            deleted += 1

        return {
            "deleted_count": deleted,
            "remaining_count": len(
                self.list_backups()
            ),
        }

    # =========================================================
    # 검증·유틸
    # =========================================================

    @staticmethod
    def _verify_database(
        database_path: Path,
    ) -> None:
        connection = sqlite3.connect(database_path)

        try:
            result = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()
        finally:
            connection.close()

        if not result or result[0] != "ok":
            raise ValueError(
                "선택한 데이터베이스 파일의 무결성 검사에 "
                "실패했습니다."
            )

    @staticmethod
    def _safe_filename(value: str) -> str:
        invalid = '<>:"/\\|?*'
        cleaned = "".join(
            "_" if character in invalid else character
            for character in str(value).strip()
        )
        return "_".join(cleaned.split())

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        size = float(size_bytes)

        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:,.1f} {unit}"
            size /= 1024

        return f"{size_bytes:,} B"