from __future__ import annotations

import hashlib
import re
import sqlite3
from time import perf_counter
from dataclasses import dataclass
from typing import Any

from core.database import Database
from modules.settings.settings_service import SettingsService

from .notion_api_client import NotionAPIClient, NotionResource
from .notion_sync_service import NotionSyncService


def normalize_purchase_deadline(value: Any) -> str | None:
    """Normalize a Notion product deadline without applying supplier defaults."""
    text = str(value or "").strip()
    if not text:
        return None
    match = re.fullmatch(r"(\d{1,2})(?::(\d{1,2})(?::\d{1,2})?|시(?:\s*(\d{1,2})\s*분?)?)", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or match.group(3) or 0)
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


@dataclass
class LivePreview:
    suppliers: list[dict[str, Any]]
    products: list[dict[str, Any]]
    shipping_policies: list[dict[str, Any]]
    warnings: list[str]
    resources: dict[str, NotionResource]


class NotionLiveSyncService:
    """Live Notion API discovery and synchronization for ERP master data."""

    RESOURCE_ALIASES = {
        "suppliers": (
            "공급처 DB", "공급처DB", "공급처 관리", "공급처관리", "공급사 DB", "공급사", "공급처",
        ),
        "products": (
            "상품 DB", "상품DB", "상품 운영", "상품운영", "상품 관리", "상품관리", "ERP 상품", "상품",
        ),
        "orders": ("주문 DB", "주문DB", "주문 관리", "주문관리", "주문"),
        "purchases": ("발주 DB", "발주DB", "발주 관리", "발주관리", "발주"),
        "conditions": (
            "공급처 상품조건 DB", "공급처상품조건 DB", "상품조건 DB", "상품 옵션 DB", "상품옵션 DB",
        ),
        "shipping_policies": (
            "상품 배송정책", "상품배송정책", "배송정책", "상품 배송 정책", "배송 정책",
        ),
        "mappings": ("상품매핑 DB", "상품 매핑 DB", "상품매핑관리", "상품 매핑 관리"),
        "channels": ("판매채널 DB", "판매 채널 DB", "판매채널관리", "판매 채널 관리"),
        "carriers": ("택배사 DB", "택배사DB", "택배사 관리", "택배사관리"),
        "purchase_templates": ("발주서 DB", "발주서DB", "발주서 관리", "발주서관리"),
    }

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()
        self.database.initialize()
        self.settings = SettingsService(self.database)
        self.discovery_service = NotionSyncService(SettingsService(self.database))

    def get_token(self) -> str:
        return self.settings.get_all().get("notion.api_token", "").strip()

    def save_token(self, token: str) -> None:
        token = token.strip()
        if token and not (token.startswith("ntn_") or token.startswith("secret_")):
            raise ValueError("Notion 액세스 토큰 형식이 올바르지 않습니다.")
        values = self.settings.get_all()
        values["notion.api_token"] = token
        self.settings.save(values)

    def connection_test(self, token: str | None = None) -> dict[str, Any]:
        client = NotionAPIClient(token or self.get_token())
        user = client.get_current_user()
        resources = client.search_data_sources()
        discovered = self._discover(resources)
        return {
            "user_name": user.get("name") or "Bisun ERP 연결",
            "resource_count": len(resources),
            "resources": discovered,
        }

    def discover(self, token: str | None = None) -> dict[str, NotionResource]:
        client = NotionAPIClient(token or self.get_token())
        return self._discover(client.search_data_sources())

    def preview(self, token: str | None = None) -> LivePreview:
        client = NotionAPIClient(token or self.get_token())
        resources = self._discover(client.search_data_sources())
        warnings: list[str] = []
        if "suppliers" not in resources:
            warnings.append("공급처 DB를 찾지 못했습니다. 원본 데이터베이스가 Bisun ERP 연결과 공유되어 있는지 확인하세요.")
        if "products" not in resources:
            warnings.append("상품 DB를 찾지 못했습니다. 원본 데이터베이스가 Bisun ERP 연결과 공유되어 있는지 확인하세요.")

        supplier_rows = (
            client.query_data_source(resources["suppliers"].resource_id)
            if "suppliers" in resources else []
        )
        suppliers = [self._supplier_from_page(page) for page in supplier_rows]
        suppliers = [row for row in suppliers if row["supplier_name"]]
        supplier_by_page = {row["notion_page_id"]: row["supplier_name"] for row in suppliers}

        product_rows = (
            client.query_data_source(resources["products"].resource_id)
            if "products" in resources else []
        )
        products = [self._product_from_page(page, supplier_by_page) for page in product_rows]
        products = [row for row in products if row["product_name"]]

        supplier_names = {row["supplier_name"] for row in suppliers}
        for product in products:
            supplier_name = product.get("supplier_name", "")
            if supplier_name and supplier_name not in supplier_names:
                warnings.append(f"상품 '{product['product_name']}'의 공급처 '{supplier_name}'가 공급처 DB에 없습니다.")

        shipping_rows = (
            client.query_data_source(resources["shipping_policies"].resource_id)
            if "shipping_policies" in resources else []
        )
        shipping_policies = [self._shipping_policy_from_page(page) for page in shipping_rows]

        return LivePreview(
            suppliers=suppliers,
            products=products,
            shipping_policies=shipping_policies,
            warnings=warnings,
            resources=resources,
        )

    def sync(self, token: str | None = None) -> dict[str, Any]:
        started_at = perf_counter()
        counters: dict[str, int] = {
            "supplier_created": 0,
            "supplier_updated": 0,
            "product_created": 0,
            "product_updated": 0,
            "condition_created": 0,
            "condition_updated": 0,
            "shipping_policy_created": 0,
            "shipping_policy_updated": 0,
            "shipping_policy_deactivated": 0,
            "supplier_deactivated": 0,
            "product_deactivated": 0,
            "condition_deactivated": 0,
        }
        preview: LivePreview | None = None

        try:
            preview = self.preview(token)

            with self.database.connect() as connection:
                supplier_ids: dict[str, int] = {}
                active_supplier_page_ids = {
                    str(row.get("notion_page_id") or "").strip()
                    for row in preview.suppliers
                    if str(row.get("notion_page_id") or "").strip()
                }
                active_product_page_ids = {
                    str(row.get("notion_page_id") or "").strip()
                    for row in preview.products
                    if str(row.get("notion_page_id") or "").strip()
                }
                active_shipping_page_ids = {
                    str(row.get("notion_page_id") or "").strip()
                    for row in getattr(preview, "shipping_policies", [])
                    if str(row.get("notion_page_id") or "").strip()
                }

                for row in preview.suppliers:
                    supplier_id, created = self._upsert_supplier(connection, row)
                    supplier_ids[row["supplier_name"]] = supplier_id
                    counters["supplier_created" if created else "supplier_updated"] += 1

                for row in preview.products:
                    supplier_name = row.get("supplier_name", "")
                    if supplier_name and supplier_name not in supplier_ids:
                        supplier_id, created = self._upsert_supplier(
                            connection,
                            {
                                "supplier_name": supplier_name,
                                "contact_name": "",
                                "phone": "",
                                "email": "",
                                "order_method": "",
                                "default_courier": row.get("courier_name", ""),
                                "default_shipping_fee": 0,
                                "settlement_method": "",
                                "handled_items": row["product_name"],
                                "memo": "Notion 상품 DB 관계에서 자동 생성",
                                "is_active": 1,
                                "notion_page_id": "",
                                "notion_last_edited_time": "",
                            },
                        )
                        supplier_ids[supplier_name] = supplier_id
                        counters[
                            "supplier_created" if created else "supplier_updated"
                        ] += 1

                    product_id, created = self._upsert_product(
                        connection,
                        row,
                        supplier_ids.get(supplier_name),
                    )
                    counters["product_created" if created else "product_updated"] += 1

                    if supplier_name:
                        condition_created = self._upsert_condition(
                            connection,
                            product_id,
                            supplier_ids[supplier_name],
                            row,
                        )
                        counters[
                            "condition_created"
                            if condition_created
                            else "condition_updated"
                        ] += 1

                # Upsert shipping policies from Notion (상품 배송정책)
                for row in getattr(preview, "shipping_policies", []):
                    rels = row.get("product_relation") or []
                    if not rels:
                        preview.warnings.append(
                            f"Shipping policy {row.get('notion_page_id')} has no product relation; skipped."
                        )
                        continue

                    for rel in rels:
                        product_page_id = str(rel)
                        product_row = connection.execute(
                            "SELECT id FROM products WHERE notion_page_id=?",
                            (product_page_id,),
                        ).fetchone()
                        if not product_row:
                            preview.warnings.append(
                                f"Shipping policy {row.get('notion_page_id')} product relation {product_page_id} not found in ERP; skipped."
                            )
                            continue
                        product_id = int(product_row["id"])

                        existing = connection.execute(
                            "SELECT id FROM product_shipping_policies WHERE notion_page_id=? AND product_id=?",
                            (row.get("notion_page_id"), product_id),
                        ).fetchone()

                        if existing:
                            connection.execute(
                                """
                                UPDATE product_shipping_policies
                                SET product_id=?, policy_name=?, min_quantity=?, max_quantity=?,
                                    shipping_fee=?, shipping_type=COALESCE(?, shipping_type), is_active=?, memo=?, notion_last_edited_time=?, updated_at=CURRENT_TIMESTAMP
                                WHERE id=?
                                """,
                                (
                                    product_id,
                                    row.get("policy_name") or "",
                                    int(row.get("min_quantity") or 0),
                                    (row.get("max_quantity") if row.get("max_quantity") not in (None, "") else None),
                                    int(row.get("shipping_fee") or 0),
                                    row.get("shipping_type") or None,
                                    1 if row.get("is_active") else 0,
                                    row.get("memo") or "",
                                    row.get("notion_last_edited_time") or "",
                                    int(existing["id"]),
                                ),
                            )
                            counters["shipping_policy_updated"] += 1
                        else:
                            connection.execute(
                                """
                                INSERT INTO product_shipping_policies
                                    (product_id, policy_name, min_quantity, max_quantity, shipping_fee, shipping_type, is_active, memo, notion_page_id, notion_last_edited_time)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    product_id,
                                    row.get("policy_name") or "",
                                    int(row.get("min_quantity") or 0),
                                    (row.get("max_quantity") if row.get("max_quantity") not in (None, "") else None),
                                    int(row.get("shipping_fee") or 0),
                                    row.get("shipping_type") or "구간형",
                                    1 if row.get("is_active") else 0,
                                    row.get("memo") or "",
                                    row.get("notion_page_id") or "",
                                    row.get("notion_last_edited_time") or "",
                                ),
                            )
                            counters["shipping_policy_created"] += 1

                counters.update(
                    self._deactivate_missing_notion_rows(
                        connection,
                        active_supplier_page_ids=active_supplier_page_ids,
                        active_product_page_ids=active_product_page_ids,
                        active_shipping_page_ids=active_shipping_page_ids,
                    )
                )

                duration_seconds = round(perf_counter() - started_at, 3)
                self._insert_sync_log(
                    connection,
                    counters=counters,
                    warning_count=len(preview.warnings),
                    duration_seconds=duration_seconds,
                    status="성공",
                    message="Notion API 실시간 동기화 완료",
                    error_message="",
                )

                connection.execute(
                    """
                    INSERT INTO settings(
                        setting_key, setting_value, description, updated_at
                    )
                    VALUES(
                        'notion.last_sync_at',
                        CURRENT_TIMESTAMP,
                        '마지막 Notion API 동기화 시각',
                        CURRENT_TIMESTAMP
                    )
                    ON CONFLICT(setting_key) DO UPDATE SET
                        setting_value=CURRENT_TIMESTAMP,
                        updated_at=CURRENT_TIMESTAMP
                    """
                )
                connection.commit()

            return {
                **counters,
                "warnings": preview.warnings,
                "resources": preview.resources,
                "duration_seconds": duration_seconds,
            }

        except Exception as error:
            duration_seconds = round(perf_counter() - started_at, 3)
            try:
                with self.database.connect() as connection:
                    self._insert_sync_log(
                        connection,
                        counters=counters,
                        warning_count=(
                            len(preview.warnings)
                            if preview is not None
                            else 0
                        ),
                        duration_seconds=duration_seconds,
                        status="실패",
                        message="Notion API 실시간 동기화 실패",
                        error_message=str(error),
                    )
                    connection.commit()
            except Exception:
                # 로그 저장 오류가 원래 동기화 오류를 가리지 않도록 합니다.
                pass
            raise

    @staticmethod
    def _insert_sync_log(
        connection: sqlite3.Connection,
        *,
        counters: dict[str, int],
        warning_count: int,
        duration_seconds: float,
        status: str,
        message: str,
        error_message: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO notion_sync_logs (
                source_file,
                supplier_created,
                supplier_updated,
                supplier_deactivated,
                product_created,
                product_updated,
                product_deactivated,
                condition_created,
                condition_updated,
                condition_deactivated,
                warning_count,
                duration_seconds,
                status,
                message,
                error_message
            ) VALUES (
                'NOTION_API',
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?
            )
            """,
            (
                int(counters.get("supplier_created", 0) or 0),
                int(counters.get("supplier_updated", 0) or 0),
                int(counters.get("supplier_deactivated", 0) or 0),
                int(counters.get("product_created", 0) or 0),
                int(counters.get("product_updated", 0) or 0),
                int(counters.get("product_deactivated", 0) or 0),
                int(counters.get("condition_created", 0) or 0),
                int(counters.get("condition_updated", 0) or 0),
                int(counters.get("condition_deactivated", 0) or 0),
                int(warning_count or 0),
                float(duration_seconds or 0),
                status,
                message,
                error_message,
            ),
        )

    @staticmethod
    def _deactivate_missing_notion_rows(
        connection: sqlite3.Connection,
        *,
        active_supplier_page_ids: set[str],
        active_product_page_ids: set[str],
        active_shipping_page_ids: set[str] | None = None,
    ) -> dict[str, int]:
        """
        Notion에서 더 이상 조회되지 않는 기존 Notion 연동 데이터를 삭제하지 않고
        ERP에서 안전하게 비활성화합니다.

        적용 대상:
        - notion_page_id가 있는 데이터만 처리
        - ERP에서 직접 만든 데이터는 건드리지 않음
        - 상품이 사라지면 해당 공급처 상품조건도 비활성화
        """

        supplier_count = 0
        product_count = 0
        condition_count = 0

        supplier_rows = connection.execute(
            """
            SELECT id, notion_page_id
            FROM suppliers
            WHERE COALESCE(notion_page_id, '') <> ''
              AND is_active = 1
            """
        ).fetchall()

        missing_supplier_ids = [
            int(row["id"])
            for row in supplier_rows
            if str(row["notion_page_id"] or "").strip()
            not in active_supplier_page_ids
        ]

        if missing_supplier_ids:
            placeholders = ",".join("?" for _ in missing_supplier_ids)
            cursor = connection.execute(
                f"""
                UPDATE suppliers
                SET is_active = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """,
                missing_supplier_ids,
            )
            supplier_count = max(0, int(cursor.rowcount or 0))

            cursor = connection.execute(
                f"""
                UPDATE supplier_product_conditions
                SET is_active = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE supplier_id IN ({placeholders})
                  AND is_active = 1
                """,
                missing_supplier_ids,
            )
            condition_count += max(0, int(cursor.rowcount or 0))

        product_rows = connection.execute(
            """
            SELECT id, notion_page_id
            FROM products
            WHERE COALESCE(notion_page_id, '') <> ''
              AND is_active = 1
            """
        ).fetchall()

        missing_product_ids = [
            int(row["id"])
            for row in product_rows
            if str(row["notion_page_id"] or "").strip()
            not in active_product_page_ids
        ]

        if missing_product_ids:
            placeholders = ",".join("?" for _ in missing_product_ids)
            cursor = connection.execute(
                f"""
                UPDATE products
                SET is_active = 0,
                    sales_status = '판매중지',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """,
                missing_product_ids,
            )
            product_count = max(0, int(cursor.rowcount or 0))

            cursor = connection.execute(
                f"""
                UPDATE supplier_product_conditions
                SET is_active = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_id IN ({placeholders})
                  AND is_active = 1
                """,
                missing_product_ids,
            )
            condition_count += max(0, int(cursor.rowcount or 0))

        # Deactivate product_shipping_policies that are no longer present in Notion
        shipping_count = 0
        if active_shipping_page_ids is None:
            active_shipping_page_ids = set()
        shipping_rows = connection.execute(
            """
            SELECT id, notion_page_id
            FROM product_shipping_policies
            WHERE COALESCE(notion_page_id, '') <> ''
              AND is_active = 1
            """
        ).fetchall()

        missing_shipping_ids = [
            int(row["id"])
            for row in shipping_rows
            if str(row["notion_page_id"] or "").strip() not in (active_shipping_page_ids or set())
        ]

        if missing_shipping_ids:
            placeholders = ",".join("?" for _ in missing_shipping_ids)
            cursor = connection.execute(
                f"""
                UPDATE product_shipping_policies
                SET is_active = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """,
                missing_shipping_ids,
            )
            shipping_count = max(0, int(cursor.rowcount or 0))

        return {
            "supplier_deactivated": supplier_count,
            "product_deactivated": product_count,
            "condition_deactivated": condition_count,
        }

    def _discover(self, resources: list[NotionResource]) -> dict[str, NotionResource]:
        discovered: dict[str, NotionResource] = {}
        for key, aliases in self.RESOURCE_ALIASES.items():
            ranked: list[tuple[int, NotionResource]] = []
            for resource in resources:
                normalized = self._normalize(resource.title)
                for rank, alias in enumerate(aliases):
                    alias_normalized = self._normalize(alias)
                    if normalized == alias_normalized:
                        ranked.append((rank, resource))
                        break
                    if alias_normalized and alias_normalized in normalized:
                        ranked.append((rank + 10, resource))
                        break
            if ranked:
                ranked.sort(key=lambda item: (item[0], len(item[1].title)))
                discovered[key] = ranked[0][1]
        return discovered

    @staticmethod
    def _normalize(text: str) -> str:
        return "".join(character for character in text.lower() if character.isalnum() or "가" <= character <= "힣")

    @staticmethod
    def _properties(page: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return page.get("properties") or {}

    @classmethod
    def _value(cls, properties: dict[str, dict[str, Any]], *names: str) -> Any:
        for name in names:
            if name in properties:
                return NotionAPIClient.property_value(properties[name])
        normalized = {cls._normalize(key): value for key, value in properties.items()}
        for name in names:
            match = normalized.get(cls._normalize(name))
            if match is not None:
                return NotionAPIClient.property_value(match)
        return ""

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(value or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_active(value: Any, default: bool = True) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        text = str(value or "").strip().lower()
        if not text:
            return 1 if default else 0
        return 0 if text in {"false", "0", "no", "off", "중지", "판매중지", "비활성"} else 1

    def _supplier_from_page(self, page: dict[str, Any]) -> dict[str, Any]:
        p = self._properties(page)
        return {
            "supplier_name": str(self._value(p, "공급처", "이름", "Name") or "").strip(),
            "contact_name": str(self._value(p, "담당자") or "").strip(),
            "phone": str(self._value(p, "연락처", "전화번호") or "").strip(),
            "email": str(self._value(p, "이메일") or "").strip(),
            "order_method": str(self._value(p, "발주방법") or "").strip(),
            "default_courier": str(self._value(p, "기본택배사", "택배사") or "").strip(),
            "default_shipping_fee": self._to_int(self._value(p, "기본배송비", "배송비")),
            "settlement_method": str(self._value(p, "정산방식") or "").strip(),
            "handled_items": str(self._value(p, "취급품목") or "").strip(),
            "memo": str(self._value(p, "메모") or "").strip(),
            "is_active": self._to_active(self._value(p, "사용여부", "활성"), True),
            "notion_page_id": str(page.get("id") or ""),
            "notion_last_edited_time": str(page.get("last_edited_time") or ""),
        }

    def _product_from_page(
        self,
        page: dict[str, Any],
        supplier_by_page: dict[str, str],
    ) -> dict[str, Any]:
        p = self._properties(page)
        relation = self._value(p, "공급처")
        relation_ids = relation if isinstance(relation, list) else []
        supplier_name = supplier_by_page.get(relation_ids[0], "") if relation_ids else str(relation or "")
        product_name = str(self._value(p, "이름", "상품명", "Name") or "").strip()
        sales_active = self._to_active(self._value(p, "판매여부", "사용여부"), True)
        return {
            "product_name": product_name,
            "product_code": str(self._value(p, "상품코드(SKU)", "SKU", "상품코드") or "").strip(),
            "sale_price": self._to_int(self._value(p, "판매가")),
            "category": str(self._value(p, "카테고리") or "").strip(),
            "sale_unit": str(self._value(p, "판매단위") or "").strip(),
            "season": str(self._value(p, "시즌") or "").strip(),
            "origin": str(self._value(p, "원산지") or "").strip(),
            "packaging_type": str(self._value(p, "포장방식") or "").strip(),
            "sales_status": "판매중" if sales_active else "판매중지",
            "supplier_name": supplier_name.strip(),
            "purchase_price": self._to_int(self._value(p, "원가", "매입단가")),
            "courier_name": str(self._value(p, "택배사", "기본택배사") or "").strip(),
            "purchase_deadline": normalize_purchase_deadline(self._value(p, "발주마감")),
            "supplier_product_name": str(self._value(p, "공급처상품명") or product_name).strip(),
            "notion_page_id": str(page.get("id") or ""),
            "notion_last_edited_time": str(page.get("last_edited_time") or ""),
        }

    def _shipping_policy_from_page(self, page: dict[str, Any]) -> dict[str, Any]:
        p = self._properties(page)
        relation = self._value(p, "상품")
        relation_ids = relation if isinstance(relation, list) else []

        def _opt_int(val: Any):
            if val in (None, ""):
                return None
            try:
                return int(float(val))
            except Exception:
                return None

        return {
            "policy_name": str(self._value(p, "정책명", "이름", "Name") or "").strip(),
            "product_relation": relation_ids,
            "min_quantity": self._to_int(self._value(p, "최소수량", "min")),
            "max_quantity": _opt_int(self._value(p, "최대수량", "max")),
            "shipping_fee": self._to_int(self._value(p, "배송비", "배송 비용", "shipping_fee")),
            "shipping_type": str(self._value(p, "배송비유형", "배송비 유형", "배송 유형", "shipping_type") or "구간형").strip(),
            "is_active": self._to_active(self._value(p, "적용여부", "적용", "is_active"), True),
            "memo": str(self._value(p, "메모", "비고") or "").strip(),
            "notion_page_id": str(page.get("id") or ""),
            "notion_last_edited_time": str(page.get("last_edited_time") or ""),
        }

    @staticmethod
    def _stable_code(prefix: str, name: str) -> str:
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8].upper()
        return f"{prefix}-{digest}"

    def _upsert_supplier(self, c: sqlite3.Connection, row: dict[str, Any]) -> tuple[int, bool]:
        existing = None
        if row.get("notion_page_id"):
            existing = c.execute(
                "SELECT id FROM suppliers WHERE notion_page_id=?", (row["notion_page_id"],)
            ).fetchone()
        if existing is None:
            existing = c.execute(
                "SELECT id FROM suppliers WHERE supplier_name=?", (row["supplier_name"],)
            ).fetchone()
        if existing:
            c.execute(
                """
                UPDATE suppliers SET supplier_name=?, contact_name=?, phone=?, email=?,
                    order_method=?, default_courier=?, default_shipping_fee=?,
                    settlement_method=?, handled_items=?,
                    memo=CASE WHEN ?<>'' THEN ? ELSE memo END,
                    is_active=?, notion_page_id=COALESCE(NULLIF(?, ''), notion_page_id),
                    notion_last_edited_time=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    row["supplier_name"], row["contact_name"], row["phone"], row["email"],
                    row["order_method"], row["default_courier"], row["default_shipping_fee"],
                    row["settlement_method"], row["handled_items"], row["memo"], row["memo"],
                    row["is_active"], row.get("notion_page_id", ""),
                    row.get("notion_last_edited_time", ""), existing["id"],
                ),
            )
            return int(existing["id"]), False
        cursor = c.execute(
            """
            INSERT INTO suppliers (
                supplier_code, supplier_name, contact_name, phone, email,
                order_method, default_courier, default_shipping_fee,
                settlement_method, handled_items, memo, is_active,
                notion_page_id, notion_last_edited_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._stable_code("NT-S", row["supplier_name"]), row["supplier_name"],
                row["contact_name"], row["phone"], row["email"], row["order_method"],
                row["default_courier"], row["default_shipping_fee"], row["settlement_method"],
                row["handled_items"], row["memo"], row["is_active"],
                row.get("notion_page_id", ""), row.get("notion_last_edited_time", ""),
            ),
        )
        return int(cursor.lastrowid), True

    def _upsert_product(
        self, c: sqlite3.Connection, row: dict[str, Any], supplier_id: int | None
    ) -> tuple[int, bool]:
        existing = None
        if row.get("notion_page_id"):
            existing = c.execute(
                "SELECT id FROM products WHERE notion_page_id=?", (row["notion_page_id"],)
            ).fetchone()
        if existing is None and row.get("product_code"):
            existing = c.execute(
                "SELECT id FROM products WHERE product_code=?", (row["product_code"],)
            ).fetchone()
        if existing is None:
            existing = c.execute(
                "SELECT id FROM products WHERE product_name=?", (row["product_name"],)
            ).fetchone()
        code = row["product_code"] or self._stable_code("NT-P", row["product_name"])
        if existing:
            c.execute(
                """
                UPDATE products SET product_code=?, product_name=?, sale_price=?, category=?,
                    sale_unit=?, season=?, origin=?, packaging_type=?, sales_status=?, is_active=?,
                    supplier_id=COALESCE(?, supplier_id), purchase_price=?, supplier_product_name=?,
                    purchase_deadline=?,
                    notion_page_id=COALESCE(NULLIF(?, ''), notion_page_id),
                    notion_last_edited_time=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    code, row["product_name"], row["sale_price"], row["category"], row["sale_unit"],
                    row["season"], row["origin"], row["packaging_type"], row["sales_status"],
                    1 if row["sales_status"] == "판매중" else 0, supplier_id,
                    row["purchase_price"], row["supplier_product_name"],
                    row["purchase_deadline"],
                    row.get("notion_page_id", ""), row.get("notion_last_edited_time", ""),
                    existing["id"],
                ),
            )
            return int(existing["id"]), False
        cursor = c.execute(
            """
            INSERT INTO products (
                product_code, product_name, supplier_id, supplier_product_name,
                purchase_price, sale_price, category, sale_unit, season, origin,
                packaging_type, sales_status, is_active, notion_page_id,
                notion_last_edited_time, purchase_deadline
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code, row["product_name"], supplier_id, row["supplier_product_name"],
                row["purchase_price"], row["sale_price"], row["category"], row["sale_unit"],
                row["season"], row["origin"], row["packaging_type"], row["sales_status"],
                1 if row["sales_status"] == "판매중" else 0,
                row.get("notion_page_id", ""), row.get("notion_last_edited_time", ""),
                row["purchase_deadline"],
            ),
        )
        return int(cursor.lastrowid), True

    def _upsert_condition(
        self, c: sqlite3.Connection, product_id: int, supplier_id: int, row: dict[str, Any]
    ) -> bool:
        self._upsert_product_supplier_price(
            c,
            product_id,
            supplier_id,
            row,
        )
        existing = c.execute(
            "SELECT id FROM supplier_product_conditions WHERE product_id=? AND supplier_id=?",
            (product_id, supplier_id),
        ).fetchone()
        if existing:
            c.execute(
                """
                UPDATE supplier_product_conditions SET supplier_product_name=?, purchase_price=?,
                    courier_name=?, order_deadline=?, is_default=1, is_active=1,
                    source='NOTION_API', notion_page_id=?, notion_last_edited_time=?,
                    updated_at=CURRENT_TIMESTAMP WHERE id=?
                """,
                (
                    row["supplier_product_name"], row["purchase_price"], row["courier_name"],
                    row["purchase_deadline"] or "", row.get("notion_page_id", ""),
                    row.get("notion_last_edited_time", ""), existing["id"],
                ),
            )
            return False
        c.execute(
            """
            INSERT INTO supplier_product_conditions (
                product_id, supplier_id, supplier_product_name, purchase_price,
                courier_name, order_deadline, is_default, source,
                notion_page_id, notion_last_edited_time
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 'NOTION_API', ?, ?)
            """,
            (
                product_id, supplier_id, row["supplier_product_name"], row["purchase_price"],
                row["courier_name"], row["purchase_deadline"] or "", row.get("notion_page_id", ""),
                row.get("notion_last_edited_time", ""),
            ),
        )
        return True

    @staticmethod
    def _upsert_product_supplier_price(
        c: sqlite3.Connection,
        product_id: int,
        supplier_id: int,
        row: dict[str, Any],
    ) -> None:
        c.execute(
            """
            INSERT INTO product_suppliers (
                product_id,
                supplier_id,
                supplier_product_name,
                purchase_price,
                order_deadline,
                is_default,
                is_active
            ) VALUES (?, ?, ?, ?, ?, 1, 1)
            ON CONFLICT(product_id, supplier_id) DO UPDATE SET
                purchase_price=excluded.purchase_price,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                product_id,
                supplier_id,
                row.get("supplier_product_name") or "",
                int(row.get("purchase_price") or 0),
                row.get("purchase_deadline") or "14:00",
            ),
        )
