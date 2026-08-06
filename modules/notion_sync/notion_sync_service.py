from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.version import ERP_NAME, ERP_VERSION
from modules.settings.settings_service import SettingsService


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"


def _persistent_token_path() -> Path:
    """Return a per-user token path that survives project ZIP upgrades."""
    base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
    if base:
        root = Path(base) / "BisunERP"
    else:
        root = Path.home() / ".bisun_erp"
    root.mkdir(parents=True, exist_ok=True)
    return root / "notion_token.json"


PERSISTENT_TOKEN_PATH = _persistent_token_path()

TARGET_DATABASES = (
    "상품 DB",
    "공급처 DB",
    "상품매핑 DB",
    "판매채널 DB",
    "택배사 DB",
    "발주서 DB",
)


class NotionApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class NotionDataSource:
    title: str
    data_source_id: str
    url: str = ""


class NotionSyncService:
    """Notion connection, discovery, and sync preparation service."""

    def __init__(self, settings_service: SettingsService | None = None) -> None:
        self.settings_service = settings_service or SettingsService()

    def get_token(self) -> str:
        # 1) User-profile token survives replacing the whole project folder.
        if PERSISTENT_TOKEN_PATH.exists():
            try:
                payload = json.loads(PERSISTENT_TOKEN_PATH.read_text(encoding="utf-8"))
                token = str(payload.get("token") or "").strip()
                if token:
                    return token
            except (OSError, json.JSONDecodeError, TypeError):
                pass

        # 2) Backward compatibility: migrate an existing project-local token.
        token = self.settings_service.get_all().get("notion.api_token", "").strip()
        if token:
            self._save_persistent_token(token)
        return token

    def save_token(self, token: str) -> None:
        clean = token.strip()
        if not clean:
            raise ValueError("Notion Integration 토큰을 입력하세요.")
        self.settings_service.save({"notion.api_token": clean})
        self._save_persistent_token(clean)

    def clear_token(self) -> None:
        self.settings_service.save({"notion.api_token": ""})
        try:
            PERSISTENT_TOKEN_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _save_persistent_token(token: str) -> None:
        temp_path = PERSISTENT_TOKEN_PATH.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps({"token": token}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(PERSISTENT_TOKEN_PATH)

    def test_connection(self, token: str | None = None) -> dict[str, Any]:
        data = self._request("GET", "/users/me", token=token)
        return {
            "name": str(data.get("name") or "Notion Integration"),
            "type": str(data.get("type") or "bot"),
            "id": str(data.get("id") or ""),
        }

    def discover_data_sources(self, token: str | None = None) -> list[NotionDataSource]:
        results: list[NotionDataSource] = []
        cursor: str | None = None

        while True:
            payload: dict[str, Any] = {
                "page_size": 100,
                "filter": {"property": "object", "value": "data_source"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            }
            if cursor:
                payload["start_cursor"] = cursor

            response = self._request("POST", "/search", payload, token=token)
            for item in response.get("results", []):
                title = self._extract_title(item)
                source_id = str(item.get("id") or "")
                if title and source_id:
                    results.append(
                        NotionDataSource(
                            title=title,
                            data_source_id=source_id,
                            url=str(item.get("url") or ""),
                        )
                    )

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break

        return results

    def match_target_databases(
        self,
        sources: list[NotionDataSource],
    ) -> dict[str, NotionDataSource | None]:
        aliases = {
            "상품 DB": ("상품db", "상품운영", "상품관리", "erp상품", "상품"),
            "공급처 DB": ("공급처db", "공급처관리", "공급사db", "공급사", "공급처"),
            "상품매핑 DB": ("상품매핑db", "상품매핑관리", "상품매핑"),
            "판매채널 DB": ("판매채널db", "판매채널관리", "판매채널"),
            "택배사 DB": ("택배사db", "택배사관리", "택배사"),
            "발주서 DB": ("발주서db", "발주서관리", "발주서"),
        }
        matched: dict[str, NotionDataSource | None] = {}
        for target in TARGET_DATABASES:
            candidates: list[tuple[int, int, NotionDataSource]] = []
            for source in sources:
                normalized = self._normalize_name(source.title)
                for rank, alias in enumerate(aliases[target]):
                    alias_key = self._normalize_name(alias)
                    if normalized == alias_key:
                        candidates.append((rank, len(normalized), source))
                        break
                    if alias_key and alias_key in normalized:
                        candidates.append((rank + 20, len(normalized), source))
                        break
            candidates.sort(key=lambda item: (item[0], item[1]))
            matched[target] = candidates[0][2] if candidates else None
        return matched

    def query_preview(
        self,
        data_source_id: str,
        token: str | None = None,
        page_size: int = 5,
    ) -> list[dict[str, Any]]:
        response = self._request(
            "POST",
            f"/data_sources/{data_source_id}/query",
            {"page_size": max(1, min(int(page_size), 20))},
            token=token,
        )
        return list(response.get("results", []))

    def save_discovery_result(
        self,
        matched: dict[str, NotionDataSource | None],
    ) -> None:
        values: dict[str, str] = {
            "notion.last_discovery_at": datetime.now().isoformat(timespec="seconds")
        }
        for title, source in matched.items():
            key = self._setting_key(title)
            values[key] = source.data_source_id if source else ""
        self.settings_service.save(values)

    @staticmethod
    def _setting_key(title: str) -> str:
        aliases = {
            "상품 DB": "products",
            "공급처 DB": "suppliers",
            "상품매핑 DB": "mappings",
            "판매채널 DB": "channels",
            "택배사 DB": "carriers",
            "발주서 DB": "purchase_templates",
        }
        return f"notion.data_source.{aliases[title]}"

    @staticmethod
    def _normalize_name(value: str) -> str:
        return "".join(value.lower().split()).replace("데이터베이스", "db")

    @staticmethod
    def _extract_title(item: dict[str, Any]) -> str:
        title_value = item.get("title", [])
        if isinstance(title_value, list):
            return "".join(
                str(part.get("plain_text") or part.get("text", {}).get("content") or "")
                for part in title_value
                if isinstance(part, dict)
            ).strip()
        return str(title_value or "").strip()

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        *,
        token: str | None = None,
    ) -> dict[str, Any]:
        access_token = (token if token is not None else self.get_token()).strip()
        if not access_token:
            raise ValueError("Notion Integration 토큰이 저장되어 있지 않습니다.")

        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        request = urllib.request.Request(
            f"{NOTION_API_BASE}{endpoint}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
                "User-Agent": f"{ERP_NAME}/{ERP_VERSION}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
                message = detail.get("message") or raw
            except json.JSONDecodeError:
                message = raw

            if error.code == 401:
                friendly = "토큰이 올바르지 않거나 만료되었습니다."
            elif error.code == 403:
                friendly = "Integration에 필요한 읽기 권한이 없습니다."
            elif error.code == 404:
                friendly = "공유되지 않은 Notion 데이터베이스입니다."
            elif error.code == 429:
                friendly = "Notion 요청이 너무 많습니다. 잠시 후 다시 시도하세요."
            else:
                friendly = str(message or f"HTTP {error.code}")
            raise NotionApiError(friendly) from error
        except urllib.error.URLError as error:
            raise NotionApiError(
                "Notion 서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요."
            ) from error
        except TimeoutError as error:
            raise NotionApiError("Notion 연결 시간이 초과되었습니다.") from error
