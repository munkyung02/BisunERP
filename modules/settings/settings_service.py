from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from core.database import Database
from core.version import ERP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SETTINGS_PATH = DATA_DIR / "app_settings.json"
ASSET_DIR = PROJECT_ROOT / "assets" / "company"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "backup"


class SettingsService:
    """
    ERP 환경설정 통합 서비스입니다.

    기존 코드 호환:
    - SettingsService()
    - SettingsService(database)
    - get_all()
    - save(flat_values)

    신규 환경설정 화면:
    - load_settings()
    - save_settings(nested_values)
    - reset_settings()
    """

    DEFAULT_SETTINGS: dict[str, Any] = {
        "company": {
            "company_name": "비선상회",
            "business_name": "더유",
            "representative_name": "",
            "business_number": "",
            "address": "",
            "phone": "",
            "email": "",
            "logo_path": "",
        },
        "document": {
            "purchase_order_footer": "",
            "output_directory": str(DEFAULT_OUTPUT_DIR),
        },
        "backup": {
            "backup_directory": str(DEFAULT_BACKUP_DIR),
        },
        "application": {
            "theme": "기본",
            "auto_save": True,
            "version": ERP_VERSION,
        },
    }

    LEGACY_DEFAULTS: dict[str, str] = {
        "system.confirm_before_order_engine": "1",
        "notion.api_token": "",
        "coupang.vendor_id": "",
        "coupang.access_key": "",
        "coupang.secret_key": "",
        "coupang.auto_sync_enabled": "0",
        "coupang.sync_interval_minutes": "5",
        "coupang.last_connection_at": "",
        "coupang.last_connection_status": "",
        "coupang.last_connection_message": "",
        "coupang.last_order_sync_at": "",
        "coupang.last_order_sync_status": "",
        "coupang.last_order_sync_message": "",
        "coupang.last_order_sync_created": "0",
        "coupang.last_order_sync_duplicate": "0",
        "coupang.last_order_sync_failed": "0",
    }

    THEMES = (
        "기본",
        "밝게",
        "어둡게",
    )

    def __init__(
        self,
        database: Database | str | Path | None = None,
        settings_path: str | Path | None = None,
    ) -> None:
        if isinstance(database, Database):
            self.database = database
        elif isinstance(database, (str, Path)):
            self.database = Database(Path(database))
        else:
            self.database = Database()

        self.database.initialize()

        self.settings_path = Path(
            settings_path or SETTINGS_PATH
        )

        self.settings_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        ASSET_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # =========================================================
    # 기존 DB 기반 설정 API
    # =========================================================

    def get_all(self) -> dict[str, str]:
        values = dict(self.LEGACY_DEFAULTS)

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT setting_key, setting_value
                FROM settings
                ORDER BY setting_key
                """
            ).fetchall()

        for row in rows:
            values[str(row["setting_key"])] = str(
                row["setting_value"] or ""
            )

        values.update(
            self._nested_to_flat(self.load_settings())
        )
        return values

    def save(self, values: dict[str, Any]) -> None:
        if not isinstance(values, dict):
            raise TypeError("설정값은 딕셔너리여야 합니다.")

        with self.database.connect() as connection:
            for key, value in values.items():
                if isinstance(value, (dict, list, tuple)):
                    stored_value = json.dumps(
                        value,
                        ensure_ascii=False,
                    )
                elif isinstance(value, bool):
                    stored_value = "1" if value else "0"
                elif value is None:
                    stored_value = ""
                else:
                    stored_value = str(value)

                connection.execute(
                    """
                    INSERT INTO settings (
                        setting_key,
                        setting_value,
                        updated_at
                    )
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(setting_key)
                    DO UPDATE SET
                        setting_value = excluded.setting_value,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (str(key), stored_value),
                )

            connection.commit()

    # =========================================================
    # 쿠팡 Open API 설정
    # =========================================================

    def get_coupang_settings(self) -> dict[str, Any]:
        values = self.get_all()
        interval_text = str(
            values.get("coupang.sync_interval_minutes", "5") or "5"
        ).strip()

        try:
            interval_minutes = max(1, int(interval_text))
        except ValueError:
            interval_minutes = 5

        return {
            "vendor_id": str(
                values.get("coupang.vendor_id", "") or ""
            ).strip(),
            "access_key": str(
                values.get("coupang.access_key", "") or ""
            ).strip(),
            "secret_key": str(
                values.get("coupang.secret_key", "") or ""
            ).strip(),
            "auto_sync_enabled": (
                str(
                    values.get("coupang.auto_sync_enabled", "0")
                    or "0"
                )
                == "1"
            ),
            "sync_interval_minutes": interval_minutes,
            "last_connection_at": str(
                values.get("coupang.last_connection_at", "") or ""
            ),
            "last_connection_status": str(
                values.get("coupang.last_connection_status", "") or ""
            ),
            "last_connection_message": str(
                values.get("coupang.last_connection_message", "") or ""
            ),
        }

    def save_coupang_settings(
        self,
        *,
        vendor_id: str,
        access_key: str,
        secret_key: str,
        auto_sync_enabled: bool = False,
        sync_interval_minutes: int = 5,
    ) -> dict[str, Any]:
        vendor_id = str(vendor_id or "").strip()
        access_key = str(access_key or "").strip()
        secret_key = str(secret_key or "").strip()

        if vendor_id and not vendor_id[:1].upper() in {"A", "C"}:
            raise ValueError(
                "Vendor ID는 일반적으로 A 또는 C로 시작합니다. "
                "Wing에서 업체코드를 다시 확인하세요."
            )

        try:
            interval = int(sync_interval_minutes)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "자동 동기화 주기는 숫자로 입력하세요."
            ) from error

        if interval < 1:
            raise ValueError(
                "자동 동기화 주기는 1분 이상이어야 합니다."
            )

        self.save(
            {
                "coupang.vendor_id": vendor_id,
                "coupang.access_key": access_key,
                "coupang.secret_key": secret_key,
                "coupang.auto_sync_enabled": (
                    "1" if auto_sync_enabled else "0"
                ),
                "coupang.sync_interval_minutes": str(interval),
            }
        )
        return self.get_coupang_settings()

    def save_coupang_connection_result(
        self,
        *,
        checked_at: str,
        status: str,
        message: str,
    ) -> None:
        self.save(
            {
                "coupang.last_connection_at": checked_at,
                "coupang.last_connection_status": status,
                "coupang.last_connection_message": message,
            }
        )

    # =========================================================
    # 신규 JSON 기반 환경설정 API
    # =========================================================

    def load_settings(self) -> dict[str, Any]:
        settings = self._deep_copy(
            self.DEFAULT_SETTINGS
        )

        if self.settings_path.exists():
            try:
                loaded = json.loads(
                    self.settings_path.read_text(
                        encoding="utf-8"
                    )
                )
                if isinstance(loaded, dict):
                    settings = self._deep_merge(
                        settings,
                        loaded,
                    )
            except (OSError, json.JSONDecodeError):
                pass

        flat_values = self._load_flat_settings_from_db()
        settings = self._apply_flat_to_nested(
            settings,
            flat_values,
        )
        return settings

    def save_settings(
        self,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        validated = self.validate_settings(settings)

        self.settings_path.write_text(
            json.dumps(
                validated,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.save(self._nested_to_flat(validated))
        return validated

    def reset_settings(self) -> dict[str, Any]:
        return self.save_settings(
            self._deep_copy(self.DEFAULT_SETTINGS)
        )

    def validate_settings(
        self,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        merged = self._deep_merge(
            self._deep_copy(self.DEFAULT_SETTINGS),
            settings,
        )

        company = merged["company"]
        document = merged["document"]
        backup = merged["backup"]
        application = merged["application"]

        for key in (
            "company_name",
            "business_name",
            "representative_name",
            "address",
            "phone",
            "email",
            "logo_path",
        ):
            company[key] = str(
                company.get(key) or ""
            ).strip()

        company["business_number"] = (
            self._format_business_number(
                str(
                    company.get(
                        "business_number"
                    ) or ""
                )
            )
        )

        if not company["company_name"]:
            raise ValueError("브랜드명을 입력하세요.")

        if company["email"] and "@" not in company["email"]:
            raise ValueError(
                "이메일 주소 형식을 확인하세요."
            )

        output_directory = Path(
            str(
                document.get("output_directory")
                or DEFAULT_OUTPUT_DIR
            )
        )
        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        document["output_directory"] = str(
            output_directory
        )
        document["purchase_order_footer"] = str(
            document.get("purchase_order_footer") or ""
        ).strip()

        backup_directory = Path(
            str(
                backup.get("backup_directory")
                or DEFAULT_BACKUP_DIR
            )
        )
        backup_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        backup["backup_directory"] = str(
            backup_directory
        )

        theme = str(
            application.get("theme") or "기본"
        ).strip()
        if theme not in self.THEMES:
            theme = "기본"

        application["theme"] = theme
        application["auto_save"] = bool(
            application.get("auto_save", True)
        )
        # application.version is retained as compatibility data only.
        # Runtime version always comes from core.version.
        application["version"] = ERP_VERSION

        return merged

    # =========================================================
    # 로고·백업 연동
    # =========================================================

    def copy_logo(
        self,
        source_path: str | Path,
    ) -> str:
        source = Path(source_path)

        if not source.exists():
            raise FileNotFoundError(
                "선택한 로고 파일을 찾을 수 없습니다."
            )

        allowed_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
        }

        if source.suffix.lower() not in allowed_extensions:
            raise ValueError(
                "PNG, JPG, JPEG, GIF, BMP 형식만 사용할 수 있습니다."
            )

        target = ASSET_DIR / (
            "company_logo" + source.suffix.lower()
        )

        for existing in ASSET_DIR.glob(
            "company_logo.*"
        ):
            if existing != target:
                try:
                    existing.unlink()
                except OSError:
                    pass

        shutil.copy2(source, target)
        return str(target)

    def remove_logo(self) -> None:
        for path in ASSET_DIR.glob("company_logo.*"):
            try:
                path.unlink()
            except OSError:
                pass

    def sync_backup_settings(
        self,
        backup_directory: str,
    ) -> None:
        backup_settings_path = (
            DATA_DIR / "backup_settings.json"
        )
        settings: dict[str, Any] = {}

        if backup_settings_path.exists():
            try:
                loaded = json.loads(
                    backup_settings_path.read_text(
                        encoding="utf-8"
                    )
                )
                if isinstance(loaded, dict):
                    settings = loaded
            except (OSError, json.JSONDecodeError):
                settings = {}

        settings["backup_root"] = str(
            backup_directory
        )

        backup_settings_path.write_text(
            json.dumps(
                settings,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # =========================================================
    # 변환
    # =========================================================

    def _load_flat_settings_from_db(
        self,
    ) -> dict[str, str]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT setting_key, setting_value
                FROM settings
                """
            ).fetchall()

        return {
            str(row["setting_key"]): str(
                row["setting_value"] or ""
            )
            for row in rows
        }

    @staticmethod
    def _nested_to_flat(
        settings: dict[str, Any],
    ) -> dict[str, str]:
        company = settings.get("company") or {}
        document = settings.get("document") or {}
        backup = settings.get("backup") or {}
        application = settings.get("application") or {}

        return {
            "company.company_name": str(
                company.get("company_name") or ""
            ),
            "company.business_name": str(
                company.get("business_name") or ""
            ),
            "company.representative_name": str(
                company.get("representative_name") or ""
            ),
            "company.business_number": str(
                company.get("business_number") or ""
            ),
            "company.address": str(
                company.get("address") or ""
            ),
            "company.phone": str(
                company.get("phone") or ""
            ),
            "company.email": str(
                company.get("email") or ""
            ),
            "company.logo_path": str(
                company.get("logo_path") or ""
            ),
            "document.purchase_order_footer": str(
                document.get("purchase_order_footer") or ""
            ),
            "document.output_directory": str(
                document.get("output_directory") or ""
            ),
            "backup.backup_directory": str(
                backup.get("backup_directory") or ""
            ),
            "application.theme": str(
                application.get("theme") or "기본"
            ),
            "application.auto_save": (
                "1"
                if application.get("auto_save", True)
                else "0"
            ),
            "application.version": str(
                ERP_VERSION
            ),
        }

    @staticmethod
    def _apply_flat_to_nested(
        settings: dict[str, Any],
        flat: dict[str, str],
    ) -> dict[str, Any]:
        mapping = {
            "company.company_name": (
                "company",
                "company_name",
            ),
            "company.business_name": (
                "company",
                "business_name",
            ),
            "company.representative_name": (
                "company",
                "representative_name",
            ),
            "company.business_number": (
                "company",
                "business_number",
            ),
            "company.address": (
                "company",
                "address",
            ),
            "company.phone": (
                "company",
                "phone",
            ),
            "company.email": (
                "company",
                "email",
            ),
            "company.logo_path": (
                "company",
                "logo_path",
            ),
            "document.purchase_order_footer": (
                "document",
                "purchase_order_footer",
            ),
            "document.output_directory": (
                "document",
                "output_directory",
            ),
            "backup.backup_directory": (
                "backup",
                "backup_directory",
            ),
            "application.theme": (
                "application",
                "theme",
            ),
        }

        for flat_key, nested_keys in mapping.items():
            if flat_key in flat:
                section, key = nested_keys
                settings[section][key] = flat[flat_key]

        if "application.auto_save" in flat:
            settings["application"]["auto_save"] = (
                flat["application.auto_save"] == "1"
            )

        return settings

    # =========================================================
    # 유틸
    # =========================================================

    @staticmethod
    def _format_business_number(
        value: str,
    ) -> str:
        digits = "".join(
            character
            for character in value
            if character.isdigit()
        )

        if len(digits) == 10:
            return (
                f"{digits[:3]}-"
                f"{digits[3:5]}-"
                f"{digits[5:]}"
            )

        return value.strip()

    @staticmethod
    def _deep_copy(
        value: dict[str, Any],
    ) -> dict[str, Any]:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
            )
        )

    @classmethod
    def _deep_merge(
        cls,
        base: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        for key, value in override.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                base[key] = cls._deep_merge(
                    base[key],
                    value,
                )
            else:
                base[key] = value

        return base
