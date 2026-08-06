from __future__ import annotations

import json
import sys

from modules.notion_sync.product_notion_sync_service import (
    NotionProductSyncService,
)


def main() -> int:
    service = NotionProductSyncService()

    print("[1/2] Notion 상품 DB 속성 미리보기")
    preview = service.preview_property_mapping(
        page_size=3
    )
    print(
        json.dumps(
            preview,
            ensure_ascii=False,
            indent=2,
        )
    )

    answer = input(
        "\n실제 ERP 동기화를 실행할까요? (YES 입력): "
    ).strip()

    if answer != "YES":
        print("동기화를 취소했습니다.")
        return 0

    print("\n[2/2] Notion → ERP 상품 동기화")
    result = service.sync_products()
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0 if not result.get("failed_count") else 1


if __name__ == "__main__":
    sys.exit(main())