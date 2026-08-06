from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.settings.settings_service import SettingsService

from .coupang_api import CoupangAPIClient


class CoupangShipmentService:
    """ERP에 저장된 쿠팡 주문 송장을 Open API로 전송합니다."""

    CARRIER_CODES = {
        "CJ대한통운": "CJGLS",
        "CJ 대한통운": "CJGLS",
        "대한통운": "CJGLS",
        "CJ": "CJGLS",
        "CJ택배": "CJGLS",
        "한진": "HANJIN",
        "한진택배": "HANJIN",
        "롯데": "HYUNDAI",
        "롯데택배": "HYUNDAI",
        "롯데글로벌로지스": "HYUNDAI",
        "로젠": "KGB",
        "로젠택배": "KGB",
        "우체국": "EPOST",
        "우체국택배": "EPOST",
        "경동": "KDEXP",
        "경동택배": "KDEXP",
        "대신": "DAESIN",
        "대신택배": "DAESIN",
        "천일": "CHUNIL",
        "천일택배": "CHUNIL",
        "천일특송": "CHUNIL",
        "일양": "ILYANG",
        "일양택배": "ILYANG",
        "일양로지스": "ILYANG",
        "업체직송": "DIRECT",
        "직접배송": "DIRECT",
    }

    def __init__(
        self,
        *,
        database_path: str | Path,
        settings_service: SettingsService | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.settings_service = settings_service or SettingsService()

    def send_shipment(
        self,
        shipment_id: int,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        shipment = self._load_shipment(int(shipment_id))

        if shipment["platform"] != "쿠팡":
            return {
                "shipment_id": int(shipment_id),
                "skipped": True,
                "succeed": False,
                "message": "쿠팡 주문이 아니므로 API 전송하지 않았습니다.",
            }

        if (
            not force
            and shipment["api_status"] == "전송완료"
        ):
            return {
                "shipment_id": int(shipment_id),
                "skipped": True,
                "succeed": True,
                "message": "이미 쿠팡 전송이 완료된 송장입니다.",
            }

        carrier_code = self._carrier_code(
            shipment["courier_name"]
        )
        tracking_number = self._tracking_number(
            shipment["tracking_number"]
        )

        dto = {
            "shipmentBoxId": self._required_int(
                shipment["shipment_box_id"],
                "shipmentBoxId",
            ),
            "orderId": self._required_int(
                shipment["coupang_order_id"],
                "orderId",
            ),
            "vendorItemId": self._required_int(
                shipment["vendor_item_id"],
                "vendorItemId",
            ),
            "deliveryCompanyCode": carrier_code,
            "invoiceNumber": tracking_number,
            "splitShipping": False,
            "preSplitShipped": False,
            "estimatedShippingDate": "",
        }

        settings = self.settings_service.get_coupang_settings()
        client = CoupangAPIClient(
            vendor_id=settings["vendor_id"],
            access_key=settings["access_key"],
            secret_key=settings["secret_key"],
        )

        request_json = json.dumps(
            dto,
            ensure_ascii=False,
        )

        try:
            response = client.upload_invoices([dto])
            parsed = self._parse_response(response)

            self._save_result(
                shipment_id=int(shipment_id),
                succeed=parsed["succeed"],
                result_code=parsed["result_code"],
                result_message=parsed["result_message"],
                retry_required=parsed["retry_required"],
                request_json=request_json,
                response_json=json.dumps(
                    response,
                    ensure_ascii=False,
                ),
            )

            if not parsed["succeed"]:
                raise RuntimeError(
                    parsed["result_message"]
                    or parsed["result_code"]
                    or "쿠팡 송장전송 실패"
                )

            return {
                "shipment_id": int(shipment_id),
                "skipped": False,
                **parsed,
            }

        except Exception as error:
            self._save_result(
                shipment_id=int(shipment_id),
                succeed=False,
                result_code="REQUEST_ERROR",
                result_message=str(error),
                retry_required=True,
                request_json=request_json,
                response_json="",
            )
            raise

    def send_pending(
        self,
        *,
        limit: int = 100,
        force_failed: bool = False,
    ) -> dict[str, Any]:
        shipment_ids = self._pending_ids(
            limit=limit,
            force_failed=force_failed,
        )
        success_count = 0
        failed_count = 0
        skipped_count = 0
        errors: list[dict[str, Any]] = []

        for shipment_id in shipment_ids:
            try:
                result = self.send_shipment(
                    shipment_id,
                    force=force_failed,
                )
                if result.get("skipped"):
                    skipped_count += 1
                elif result.get("succeed"):
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as error:
                failed_count += 1
                errors.append(
                    {
                        "shipment_id": shipment_id,
                        "error": str(error),
                    }
                )

        return {
            "target_count": len(shipment_ids),
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "errors": errors,
        }

    def retry_failed(
        self,
        *,
        limit: int = 100,
    ) -> dict[str, Any]:
        return self.send_pending(
            limit=limit,
            force_failed=True,
        )

    def _load_shipment(self, shipment_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    sh.id AS shipment_id,
                    sh.courier_name,
                    sh.tracking_number,
                    COALESCE(o.platform, '') AS platform,
                    COALESCE(col.coupang_order_id, '') AS coupang_order_id,
                    COALESCE(col.shipment_box_id, '') AS shipment_box_id,
                    COALESCE(coil.vendor_item_id, '') AS vendor_item_id,
                    COALESCE(log.api_status, '') AS api_status
                FROM shipments AS sh
                INNER JOIN orders AS o
                    ON o.id = sh.order_id
                LEFT JOIN coupang_order_links AS col
                    ON col.erp_order_id = sh.order_id
                LEFT JOIN coupang_order_item_links AS coil
                    ON coil.erp_order_item_id = sh.order_item_id
                LEFT JOIN coupang_shipment_api_logs AS log
                    ON log.shipment_id = sh.id
                WHERE sh.id = ?
                """,
                (shipment_id,),
            ).fetchone()

        if row is None:
            raise ValueError("송장정보를 찾을 수 없습니다.")
        return dict(row)

    def _pending_ids(
        self,
        *,
        limit: int,
        force_failed: bool,
    ) -> list[int]:
        condition = (
            "COALESCE(log.api_status, '') = '전송실패'"
            if force_failed
            else "COALESCE(log.api_status, '') != '전송완료'"
        )
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT sh.id
                FROM shipments AS sh
                INNER JOIN orders AS o
                    ON o.id = sh.order_id
                   AND o.platform = '쿠팡'
                LEFT JOIN coupang_shipment_api_logs AS log
                    ON log.shipment_id = sh.id
                WHERE {condition}
                ORDER BY sh.id
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [int(row["id"]) for row in rows]

    def _save_result(
        self,
        *,
        shipment_id: int,
        succeed: bool,
        result_code: str,
        result_message: str,
        retry_required: bool,
        request_json: str,
        response_json: str,
    ) -> None:
        api_status = "전송완료" if succeed else "전송실패"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO coupang_shipment_api_logs (
                    shipment_id,
                    api_status,
                    result_code,
                    result_message,
                    retry_required,
                    retry_count,
                    request_json,
                    response_json,
                    last_attempt_at,
                    sent_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, 1, ?, ?,
                    CURRENT_TIMESTAMP,
                    CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(shipment_id)
                DO UPDATE SET
                    api_status = excluded.api_status,
                    result_code = excluded.result_code,
                    result_message = excluded.result_message,
                    retry_required = excluded.retry_required,
                    retry_count = coupang_shipment_api_logs.retry_count + 1,
                    request_json = excluded.request_json,
                    response_json = excluded.response_json,
                    last_attempt_at = CURRENT_TIMESTAMP,
                    sent_at = CASE
                        WHEN excluded.api_status = '전송완료'
                        THEN CURRENT_TIMESTAMP
                        ELSE coupang_shipment_api_logs.sent_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    shipment_id,
                    api_status,
                    result_code,
                    result_message,
                    1 if retry_required else 0,
                    request_json,
                    response_json,
                    1 if succeed else 0,
                ),
            )

            if succeed:
                connection.execute(
                    """
                    UPDATE shipments
                    SET
                        shipment_status = '배송중',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (shipment_id,),
                )

            connection.commit()

    @staticmethod
    def _parse_response(
        response: dict[str, Any],
    ) -> dict[str, Any]:
        data = response.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("쿠팡 송장응답 data 형식이 올바르지 않습니다.")

        response_list = data.get("responseList")
        if not isinstance(response_list, list) or not response_list:
            raise RuntimeError(
                str(
                    data.get("responseMessage")
                    or "쿠팡 송장응답 결과가 없습니다."
                )
            )

        item = response_list[0]
        if not isinstance(item, dict):
            raise RuntimeError("쿠팡 송장 개별응답 형식이 올바르지 않습니다.")

        return {
            "succeed": bool(item.get("succeed")),
            "result_code": str(item.get("resultCode") or ""),
            "result_message": str(item.get("resultMessage") or ""),
            "retry_required": bool(item.get("retryRequired")),
        }

    @classmethod
    def _carrier_code(cls, courier_name: Any) -> str:
        original = str(courier_name or "").strip()
        normalized = original.replace(" ", "")
        for name, code in cls.CARRIER_CODES.items():
            if name.replace(" ", "") == normalized:
                return code
        raise ValueError(
            f"쿠팡 택배사 코드를 찾을 수 없습니다: {original}"
        )

    @staticmethod
    def _tracking_number(value: Any) -> str:
        text = str(value or "").strip().replace(" ", "")
        if text.endswith(".0"):
            text = text[:-2]
        if not text:
            raise ValueError("송장번호가 비어 있습니다.")
        return text

    @staticmethod
    def _required_int(
        value: Any,
        field_name: str,
    ) -> int:
        try:
            converted = int(str(value).strip())
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name} 값이 올바르지 않습니다: {value}"
            ) from None
        if converted <= 0:
            raise ValueError(f"{field_name}는 1 이상이어야 합니다.")
        return converted

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
