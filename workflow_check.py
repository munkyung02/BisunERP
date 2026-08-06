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
    parser.add_argument(
        "--shipment-file",
        type=Path,
        default=None,
        help="preview or register an Excel shipment file",
    )
    parser.add_argument(
        "--register-shipments",
        action="store_true",
        help="register valid shipments from --shipment-file",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="register valid rows even when the shipment file has errors",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    service = OrderWorkflowService(
        database_path=project_root / "data" / "bisun_erp.db",
        output_root=project_root / "output" / "발주서",
    )

    if args.register_shipments and args.shipment_file is None:
        parser.error("--register-shipments requires --shipment-file")

    if args.allow_partial and not args.register_shipments:
        parser.error("--allow-partial requires --register-shipments")

    if args.shipment_file is not None:
        if args.register_shipments:
            result = service.register_shipments(
                args.shipment_file,
                allow_partial=args.allow_partial,
            )
        else:
            result = service.preview_shipments(
                args.shipment_file
            ).to_dict()
    else:
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
