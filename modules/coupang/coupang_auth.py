from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone


class CoupangHMACAuth:
    """쿠팡 Open API용 HMAC-SHA256 Authorization 헤더 생성기입니다."""

    ALGORITHM = "HmacSHA256"

    @classmethod
    def create_authorization(
        cls,
        *,
        method: str,
        path: str,
        query: str,
        access_key: str,
        secret_key: str,
        now: datetime | None = None,
    ) -> str:
        access_key = str(access_key or "").strip()
        secret_key = str(secret_key or "").strip()

        if not access_key:
            raise ValueError("쿠팡 Access Key가 비어 있습니다.")
        if not secret_key:
            raise ValueError("쿠팡 Secret Key가 비어 있습니다.")
        if not path.startswith("/"):
            raise ValueError("API path는 /로 시작해야 합니다.")

        current = now or datetime.now(timezone.utc)
        signed_date = current.strftime("%y%m%dT%H%M%SZ")
        method = method.upper().strip()
        message = f"{signed_date}{method}{path}{query}"

        signature = hmac.new(
            secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return (
            f"CEA algorithm={cls.ALGORITHM}, "
            f"access-key={access_key}, "
            f"signed-date={signed_date}, "
            f"signature={signature}"
        )
