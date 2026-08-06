from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

from core.version import ERP_NAME, ERP_VERSION


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_VERSION = "2026-03-11"


class NotionAPIError(RuntimeError):
    """Readable error returned by the Notion REST API."""


@dataclass(frozen=True)
class NotionResource:
    resource_id: str
    title: str
    object_type: str
    parent_database_id: str = ""


class NotionAPIClient:
    """Small stdlib-only client for the current Notion REST API."""

    def __init__(self, token: str, *, timeout: int = 25) -> None:
        self.token = token.strip()
        self.timeout = timeout
        if not self.token:
            raise ValueError("Notion 액세스 토큰을 입력하세요.")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{NOTION_API_BASE}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": NOTION_API_VERSION,
                "Content-Type": "application/json",
                "User-Agent": f"{ERP_NAME}/{ERP_VERSION}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            detail = ""
            try:
                payload = json.loads(error.read().decode("utf-8"))
                detail = str(payload.get("message") or payload.get("code") or "")
            except Exception:
                detail = str(error.reason or "")
            if error.code == 401:
                detail = detail or "토큰이 올바르지 않거나 만료되었습니다."
            elif error.code == 403:
                detail = detail or "연결에 이 페이지 또는 데이터베이스 접근 권한이 없습니다."
            elif error.code == 404:
                detail = detail or "공유된 데이터베이스를 찾지 못했습니다."
            elif error.code == 429:
                detail = detail or "Notion API 요청 한도를 초과했습니다. 잠시 후 다시 시도하세요."
            raise NotionAPIError(f"Notion API 오류 ({error.code}): {detail}") from error
        except urllib.error.URLError as error:
            raise NotionAPIError(f"Notion 서버에 연결하지 못했습니다: {error.reason}") from error

    def get_current_user(self) -> dict[str, Any]:
        return self._request("GET", "/users/me")

    def search_data_sources(self) -> list[NotionResource]:
        resources: list[NotionResource] = []
        cursor: str | None = None
        while True:
            payload: dict[str, Any] = {
                "page_size": 100,
                "filter": {"property": "object", "value": "data_source"},
            }
            if cursor:
                payload["start_cursor"] = cursor
            response = self._request("POST", "/search", payload)
            for item in response.get("results", []):
                title = self._plain_text(item.get("title")) or str(item.get("name") or "")
                parent = item.get("parent") or {}
                resources.append(
                    NotionResource(
                        resource_id=str(item.get("id") or ""),
                        title=title.strip(),
                        object_type=str(item.get("object") or "data_source"),
                        parent_database_id=str(parent.get("database_id") or ""),
                    )
                )
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break
        return resources

    def retrieve_data_source(self, data_source_id: str) -> dict[str, Any]:
        return self._request("GET", f"/data_sources/{data_source_id}")

    def create_page(
        self,
        data_source_id: str,
        *,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/pages",
            {
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": data_source_id,
                },
                "properties": properties,
            },
        )

    def update_page(
        self,
        page_id: str,
        *,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/pages/{page_id}",
            {"properties": properties},
        )

    def query_data_source(
        self,
        data_source_id: str,
        *,
        filter_object: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            if filter_object:
                payload["filter"] = filter_object
            if sorts:
                payload["sorts"] = sorts
            response = self._request("POST", f"/data_sources/{data_source_id}/query", payload)
            rows.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break
        return rows

    @classmethod
    def property_value(cls, property_object: dict[str, Any] | None) -> Any:
        prop = property_object or {}
        kind = str(prop.get("type") or "")
        value = prop.get(kind)
        if kind in {"title", "rich_text"}:
            return cls._plain_text(value)
        if kind == "number":
            return value if value is not None else 0
        if kind in {"select", "status"}:
            return (value or {}).get("name", "")
        if kind == "multi_select":
            return ", ".join(str(item.get("name") or "") for item in (value or []))
        if kind == "checkbox":
            return bool(value)
        if kind in {"email", "phone_number", "url"}:
            return value or ""
        if kind == "date":
            return (value or {}).get("start", "")
        if kind == "relation":
            return [str(item.get("id") or "") for item in (value or []) if item.get("id")]
        if kind == "people":
            return ", ".join(str(item.get("name") or item.get("id") or "") for item in (value or []))
        if kind == "formula":
            formula = value or {}
            formula_type = formula.get("type")
            return formula.get(formula_type) if formula_type else ""
        if kind == "rollup":
            rollup = value or {}
            rollup_type = rollup.get("type")
            if rollup_type == "array":
                return ", ".join(str(cls.property_value(item)) for item in rollup.get("array", []))
            return rollup.get(rollup_type) if rollup_type else ""
        if kind == "unique_id":
            unique_id = value or {}
            prefix = unique_id.get("prefix") or ""
            number = unique_id.get("number")
            return f"{prefix}{number}" if number is not None else ""
        return value if value is not None else ""

    @staticmethod
    def _plain_text(items: Iterable[dict[str, Any]] | None) -> str:
        return "".join(str(item.get("plain_text") or "") for item in (items or []))
