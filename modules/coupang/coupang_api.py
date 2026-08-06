from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Any

from .coupang_auth import CoupangHMACAuth


class CoupangAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class CoupangAPIClient:
    """쿠팡 Open API 요청을 수행하는 최소 공통 클라이언트입니다."""

    BASE_URL = "https://api-gateway.coupang.com"

    def __init__(
        self,
        *,
        vendor_id: str,
        access_key: str,
        secret_key: str,
        timeout_seconds: int = 20,
    ) -> None:
        self.vendor_id = str(vendor_id or "").strip()
        self.access_key = str(access_key or "").strip()
        self.secret_key = str(secret_key or "").strip()
        self.timeout_seconds = max(1, int(timeout_seconds))

        if not self.vendor_id:
            raise ValueError("쿠팡 Vendor ID가 비어 있습니다.")
        if not self.access_key:
            raise ValueError("쿠팡 Access Key가 비어 있습니다.")
        if not self.secret_key:
            raise ValueError("쿠팡 Secret Key가 비어 있습니다.")

    def request(
        self,
        *,
        method: str,
        path: str,
        query_params: dict[str, Any] | None = None,
        body: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any]:
        method = method.upper().strip()
        query = urllib.parse.urlencode(
            query_params or {},
            doseq=True,
        )
        authorization = CoupangHMACAuth.create_authorization(
            method=method,
            path=path,
            query=query,
            access_key=self.access_key,
            secret_key=self.secret_key,
        )

        url = f"{self.BASE_URL}{path}"
        if query:
            url = f"{url}?{query}"

        encoded_body = None
        if body is not None:
            encoded_body = json.dumps(
                body,
                ensure_ascii=False,
            ).encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=encoded_body,
            method=method,
        )
        request.add_header(
            "Content-Type",
            "application/json;charset=UTF-8",
        )
        request.add_header("Authorization", authorization)
        request.add_header("X-Requested-By", self.vendor_id)
        request.add_header("X-MARKET", "KR")
        request.add_header(
            "User-Agent",
            "BisunERP/2.8 CoupangOpenAPI",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read().decode(
                    response.headers.get_content_charset()
                    or "utf-8",
                    errors="replace",
                )
                if not raw.strip():
                    return {
                        "http_status": int(response.status),
                        "data": None,
                    }

                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"raw": raw}

                if isinstance(payload, dict):
                    payload.setdefault(
                        "http_status",
                        int(response.status),
                    )
                    return payload

                return {
                    "http_status": int(response.status),
                    "data": payload,
                }

        except urllib.error.HTTPError as error:
            response_body = error.read().decode(
                "utf-8",
                errors="replace",
            )
            detail = self._extract_error_message(response_body)
            raise CoupangAPIError(
                f"쿠팡 API 오류 {error.code}: {detail}",
                status_code=int(error.code),
                response_body=response_body,
            ) from error
        except urllib.error.URLError as error:
            reason = getattr(error, "reason", error)
            raise CoupangAPIError(
                f"쿠팡 API 서버에 연결하지 못했습니다: {reason}"
            ) from error
        except socket.timeout as error:
            raise CoupangAPIError(
                "쿠팡 API 연결 시간이 초과되었습니다."
            ) from error

    def upload_invoices(
        self,
        invoice_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """쿠팡 송장업로드 처리 API를 호출합니다."""
        if not invoice_items:
            raise ValueError("쿠팡에 전송할 송장정보가 없습니다.")

        path = (
            "/v2/providers/openapi/apis/api/v4/vendors/"
            f"{self.vendor_id}/orders/invoices"
        )
        result = self.request(
            method="POST",
            path=path,
            body={
                "vendorId": self.vendor_id,
                "orderSheetInvoiceApplyDtos": invoice_items,
            },
        )

        code = str(result.get("code") or "")
        if code and code != "200":
            raise CoupangAPIError(
                str(
                    result.get("message")
                    or f"쿠팡 송장업로드 실패(code={code})"
                )
            )
        return result

    def get_order_sheets(
        self,
        *,
        created_at_from: str,
        created_at_to: str,
        status: str,
    ) -> list[dict[str, Any]]:
        """
        24시간 이내 분단위 구간의 발주서 목록을 조회합니다.

        status 예:
        - ACCEPT: 결제완료
        - INSTRUCT: 상품준비중
        - DEPARTURE: 배송지시
        """
        normalized_status = str(status or "").strip().upper()
        valid_statuses = {
            "ACCEPT",
            "INSTRUCT",
            "DEPARTURE",
            "DELIVERING",
            "FINAL_DELIVERY",
            "NONE_TRACKING",
        }
        if normalized_status not in valid_statuses:
            raise ValueError(
                "지원하지 않는 쿠팡 발주서 상태입니다: "
                f"{normalized_status}"
            )

        path = (
            "/v2/providers/openapi/apis/api/v5/vendors/"
            f"{self.vendor_id}/ordersheets"
        )
        result = self.request(
            method="GET",
            path=path,
            query_params={
                "createdAtFrom": created_at_from,
                "createdAtTo": created_at_to,
                "searchType": "timeFrame",
                "status": normalized_status,
            },
        )

        code = result.get("code")
        if code not in (None, 200, "200"):
            raise CoupangAPIError(
                str(
                    result.get("message")
                    or f"쿠팡 발주서 조회 실패(code={code})"
                )
            )

        data = result.get("data")
        if data is None:
            return []
        if not isinstance(data, list):
            raise CoupangAPIError(
                "쿠팡 발주서 응답의 data 형식이 목록이 아닙니다."
            )

        return [
            item
            for item in data
            if isinstance(item, dict)
        ]

    def test_connection(self) -> dict[str, Any]:
        """
        오늘 날짜의 발주서 목록을 최대 1건만 조회해 인증과 권한을 확인합니다.
        주문이 0건이어도 HTTP 200이면 연결 성공으로 처리합니다.
        """
        today = date.today().isoformat()
        path = (
            "/v2/providers/openapi/apis/api/v5/vendors/"
            f"{self.vendor_id}/ordersheets"
        )
        result = self.request(
            method="GET",
            path=path,
            query_params={
                "createdAtFrom": today,
                "createdAtTo": today,
                "status": "ACCEPT",
                "maxPerPage": 1,
            },
        )

        response_code = str(result.get("code") or "").upper()
        if response_code and response_code not in {
            "SUCCESS",
            "200",
        }:
            message = str(
                result.get("message")
                or "쿠팡 API가 오류 응답을 반환했습니다."
            )
            raise CoupangAPIError(message)

        data = result.get("data")
        order_count = 0
        if isinstance(data, list):
            order_count = len(data)
        elif isinstance(data, dict):
            for key in ("data", "content", "orderSheetList"):
                value = data.get(key)
                if isinstance(value, list):
                    order_count = len(value)
                    break

        return {
            "connected": True,
            "vendor_id": self.vendor_id,
            "http_status": int(result.get("http_status") or 200),
            "sample_order_count": order_count,
            "message": "쿠팡 Open API 인증 및 주문조회 권한 확인 완료",
        }

    @staticmethod
    def _extract_error_message(response_body: str) -> str:
        try:
            payload = json.loads(response_body)
        except json.JSONDecodeError:
            return response_body.strip() or "응답 내용 없음"

        if isinstance(payload, dict):
            return str(
                payload.get("message")
                or payload.get("error")
                or payload.get("code")
                or payload
            )
        return str(payload)
