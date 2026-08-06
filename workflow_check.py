from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.workflow import OrderWorkflowService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BisunERP 주문→매핑→발주 흐름 점검"
    )
    parser.add_argument(
        "--order-id",
        type=int,
        default=None,
        help="특정 ERP 주문 ID만 처리",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="실제로 발주서를 생성",
    )
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="주의사항이 있어도 발주서 생성",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    service = OrderWorkflowService(
        database_path=project_root / "data" / "bisun_erp.db",
        output_root=project_root / "output" / "발주서",
    )

    result = service.execute(
        order_id=args.order_id,
        create_purchase_files=args.create,
        allow_warnings=args.allow_warnings,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
