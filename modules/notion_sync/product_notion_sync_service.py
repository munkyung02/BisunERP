from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.notion_sync.notion_api_client import NotionAPIClient
from modules.notion_sync.notion_sync_service import NotionSyncService
from modules.products.product_repository import ProductRepository
from modules.suppliers.supplier_repository import SupplierRepository


@dataclass
class ProductSyncResult:
    total_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    supplier_created_count: int = 0
    errors: list[dict[str, Any]] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_count": self.total_count,
            "created_count": self.created_count,
            "updated_count": self.updated_count,
            "skipped_count": self.skipped_count,
            "failed_count": self.failed_count,
            "supplier_created_count": self.supplier_created_count,
            "errors": self.errors or [],
        }


class NotionProductSyncService:
    """
    Notion 상품 DB를 원본으로 사용해 ERP 상품·공급처를 동기화합니다.

    기본 동기화 기준:
    - 상품코드가 있으면 상품코드로 기존 ERP 상품을 찾습니다.
    - 상품코드가 없으면 상품명+옵션명으로 기존 상품을 찾습니다.
    - 공급처가 ERP에 없으면 자동 생성합니다.
    - Notion의 활성여부를 ERP is_active에 반영합니다.
    """

    PROPERTY_ALIASES: dict[str, tuple[str, ...]] = {
        "product_code": (
            "상품코드", "ERP상품코드", "ERP 코드", "product_code",
        ),
        "product_name": (
            "상품명", "내부상품명", "ERP상품명", "ERP 상품명",
            "product_name", "Name", "이름",
        ),
        "option_name": (
            "옵션명", "옵션", "규격", "option_name",
        ),
        "supplier_name": (
            "공급처", "공급처명", "공급사", "공급사명",
            "supplier_name",
        ),
        "supplier_product_name": (
            "공급처상품명", "공급처 상품명", "매입상품명",
            "supplier_product_name",
        ),
        "purchase_price": (
            "매입가", "매입단가", "공급가", "원가",
            "purchase_price",
        ),
        "sale_price": (
            "판매가", "판매단가", "sale_price",
        ),
        "purchase_round": (
            "발주차수", "발주회차", "차수", "purchase_round",
        ),
        "platform": (
            "플랫폼", "판매채널", "채널", "platform",
        ),
        "platform_product_name": (
            "플랫폼상품명", "플랫폼 상품명", "판매처상품명",
            "판매처 상품명", "platform_product_name",
        ),
        "is_active": (
            "활성여부", "사용여부", "사용", "활성", "is_active",
        ),
    }

    def __init__(
        self,
        *,
        product_repository: ProductRepository | None = None,
        supplier_repository: SupplierRepository | None = None,
        notion_sync_service: NotionSyncService | None = None,
    ) -> None:
        self.product_repository = (
            product_repository or ProductRepository()
        )
        self.supplier_repository = (
            supplier_repository or SupplierRepository()
        )
        self.notion_sync_service = (
            notion_sync_service or NotionSyncService()
        )

    def sync_products(
        self,
        data_source_id: str | None = None,
    ) -> dict[str, Any]:
        token = self.notion_sync_service.get_token()

        if not token:
            raise ValueError(
                "Notion Integration 토큰이 저장되어 있지 않습니다."
            )

        source_id = (
            str(data_source_id or "").strip()
            or self._saved_product_data_source_id()
        )

        if not source_id:
            raise ValueError(
                "상품 DB Data Source ID가 없습니다. "
                "먼저 Notion 연결 화면에서 DB 찾기를 실행하세요."
            )

        client = NotionAPIClient(token)
        pages = client.query_data_source(source_id)

        existing_products = self.product_repository.get_products(
            active_only=None
        )
        by_code = {
            self._key(item.get("product_code")): item
            for item in existing_products
            if self._key(item.get("product_code"))
        }
        by_name_option = {
            self._name_option_key(
                item.get("product_name"),
                item.get("option_name"),
            ): item
            for item in existing_products
        }

        suppliers = self.supplier_repository.get_suppliers(
            active_only=False
        )
        supplier_by_name = {
            self._key(item.get("supplier_name")): item
            for item in suppliers
            if self._key(item.get("supplier_name"))
        }

        result = ProductSyncResult(
            total_count=len(pages),
            errors=[],
        )

        for index, page in enumerate(pages, start=1):
            try:
                properties = page.get("properties") or {}
                row = self._parse_product_row(
                    client,
                    properties,
                )

                product_name = self._clean_text(
                    row.get("product_name")
                )
                if not product_name:
                    result.skipped_count += 1
                    result.errors.append({
                        "row": index,
                        "page_id": page.get("id", ""),
                        "error": "상품명이 없어 건너뛰었습니다.",
                    })
                    continue

                supplier_id = None
                supplier_name = self._clean_text(
                    row.get("supplier_name")
                )

                if supplier_name:
                    supplier_key = self._key(supplier_name)
                    supplier = supplier_by_name.get(supplier_key)

                    if supplier is None:
                        supplier_id = self.supplier_repository.create_supplier(
                            supplier_name=supplier_name,
                        )
                        supplier = self.supplier_repository.get_supplier_by_id(
                            supplier_id
                        ) or {
                            "id": supplier_id,
                            "supplier_name": supplier_name,
                        }
                        supplier_by_name[supplier_key] = supplier
                        result.supplier_created_count += 1
                    else:
                        supplier_id = int(supplier["id"])

                product_code = self._clean_text(
                    row.get("product_code")
                )

                existing = None
                if product_code:
                    existing = by_code.get(
                        self._key(product_code)
                    )

                if existing is None:
                    existing = by_name_option.get(
                        self._name_option_key(
                            product_name,
                            row.get("option_name"),
                        )
                    )

                product_data = {
                    "product_name": product_name,
                    "platform": self._clean_text(
                        row.get("platform")
                    ),
                    "platform_product_name": self._clean_text(
                        row.get("platform_product_name")
                    ),
                    "option_name": self._clean_text(
                        row.get("option_name")
                    ),
                    "supplier_id": supplier_id,
                    "supplier_product_name": self._clean_text(
                        row.get("supplier_product_name")
                    ),
                    "purchase_price": self._to_int(
                        row.get("purchase_price")
                    ),
                    "sale_price": self._to_int(
                        row.get("sale_price")
                    ),
                    "purchase_round": self._clean_text(
                        row.get("purchase_round")
                    ),
                    "is_active": self._to_bool(
                        row.get("is_active"),
                        default=True,
                    ),
                }

                if existing is None:
                    product_id = self.product_repository.create_product(
                        **product_data
                    )
                    result.created_count += 1
                else:
                    product_id = int(existing["id"])
                    self.product_repository.update_product(
                        product_id,
                        **product_data,
                    )
                    result.updated_count += 1

                self.product_repository.update_notion_sync_result(
                    product_id,
                    notion_page_id=str(page.get("id") or ""),
                    notion_last_edited_time=str(
                        page.get("last_edited_time") or ""
                    ),
                    sync_status="동기화완료",
                    sync_message=None,
                )

                refreshed = self.product_repository.get_product_by_id(
                    product_id
                )
                if refreshed:
                    code_key = self._key(
                        refreshed.get("product_code")
                    )
                    if code_key:
                        by_code[code_key] = refreshed
                    by_name_option[
                        self._name_option_key(
                            refreshed.get("product_name"),
                            refreshed.get("option_name"),
                        )
                    ] = refreshed

            except Exception as error:
                result.failed_count += 1
                result.errors.append({
                    "row": index,
                    "page_id": page.get("id", ""),
                    "error": str(error),
                })

        return result.as_dict()

    def preview_property_mapping(
        self,
        data_source_id: str | None = None,
        page_size: int = 3,
    ) -> list[dict[str, Any]]:
        token = self.notion_sync_service.get_token()
        source_id = (
            str(data_source_id or "").strip()
            or self._saved_product_data_source_id()
        )

        if not source_id:
            raise ValueError(
                "상품 DB Data Source ID가 없습니다."
            )

        client = NotionAPIClient(token)
        pages = client.query_data_source(source_id)

        preview: list[dict[str, Any]] = []
        for page in pages[:max(1, int(page_size))]:
            preview.append(
                self._parse_product_row(
                    client,
                    page.get("properties") or {},
                )
            )
        return preview

    def _saved_product_data_source_id(self) -> str:
        settings = self.notion_sync_service.settings_service.get_all()
        return str(
            settings.get("notion.data_source.products") or ""
        ).strip()

    def _parse_product_row(
        self,
        client: NotionAPIClient,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_properties = {
            self._key(name): value
            for name, value in properties.items()
        }

        result: dict[str, Any] = {}
        for field, aliases in self.PROPERTY_ALIASES.items():
            property_object = None

            for alias in aliases:
                property_object = normalized_properties.get(
                    self._key(alias)
                )
                if property_object is not None:
                    break

            result[field] = client.property_value(
                property_object
            )

        return result

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _key(value: Any) -> str:
        return "".join(
            str(value or "").strip().lower().split()
        )

    @classmethod
    def _name_option_key(
        cls,
        product_name: Any,
        option_name: Any,
    ) -> str:
        return (
            f"{cls._key(product_name)}|"
            f"{cls._key(option_name)}"
        )

    @staticmethod
    def _to_int(value: Any) -> int:
        if value in (None, ""):
            return 0
        try:
            return max(0, int(float(value)))
        except (TypeError, ValueError):
            cleaned = "".join(
                ch for ch in str(value)
                if ch.isdigit() or ch in ".-"
            )
            try:
                return max(0, int(float(cleaned)))
            except (TypeError, ValueError):
                return 0

    @staticmethod
    def _to_bool(
        value: Any,
        *,
        default: bool,
    ) -> bool:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0

        normalized = str(value).strip().lower()
        if normalized in {
            "1", "true", "yes", "y", "사용", "활성",
            "사용중", "운영", "판매중",
        }:
            return True
        if normalized in {
            "0", "false", "no", "n", "미사용", "비활성",
            "중지", "판매중지",
        }:
            return False

        return default