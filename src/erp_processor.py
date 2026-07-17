from pathlib import Path

from config.coupang import COLUMN_MAP, PLATFORM_NAME
from config.setting import ERP_VERSION
from src.excel_reader import find_first_excel, read_excel_file
from src.mapping_template import (
    create_mapping_template,
    find_existing_mapping_file,
    sync_mapping_template,
)
from src.matcher import create_unmatched_product_list, match_orders_with_products
from src.order_history import (
    load_order_history,
    save_processed_orders,
    split_new_and_duplicate_orders,
)
from src.order_parser import parse_coupang_orders
from src.purchase_order_generator import generate_purchase_orders


def run_order_processing() -> None:
    print("=" * 60)
    print(f"🚀 비선상회 ERP v{ERP_VERSION} 시작")
    print("=" * 60)

    try:
        output_folder = Path("output")
        output_folder.mkdir(parents=True, exist_ok=True)
        canonical_mapping_file = output_folder / "상품매핑표.xlsx"
        history_file = output_folder / "주문처리이력.xlsx"

        excel_file = find_first_excel("data")
        original_orders = read_excel_file(excel_file)
        all_orders = parse_coupang_orders(original_orders)

        print(f"\n판매채널: {PLATFORM_NAME}")
        print(f"원본 파일: {excel_file.name}")
        print(f"원본 주문 건수: {len(all_orders)}건")
        print("\n필수 컬럼 확인")
        for internal_name, excel_column in COLUMN_MAP.items():
            print(f"{'✅' if excel_column in original_orders.columns else '❌'} {internal_name}: {excel_column}")

        standard_order_file = output_folder / "쿠팡_표준주문.xlsx"
        all_orders.to_excel(standard_order_file, index=False)
        print(f"\n✅ 표준 주문 파일 생성: {standard_order_file.resolve()}")

        mapping_file = canonical_mapping_file if canonical_mapping_file.exists() else find_existing_mapping_file(output_folder)
        if mapping_file is None:
            create_mapping_template(all_orders, canonical_mapping_file)
            print(f"\n✅ 상품매핑표 최초 생성: {canonical_mapping_file.resolve()}")
            print("상품 정보를 입력한 후 프로그램을 다시 실행하세요.")
            return

        if mapping_file != canonical_mapping_file:
            mapping_file.replace(canonical_mapping_file)
            mapping_file = canonical_mapping_file
            print("\n✅ 기존 상품매핑표를 복구해 표준 파일명으로 변경했습니다.")

        _, added_count = sync_mapping_template(all_orders, mapping_file)
        print("\n✅ 기존 상품 매핑 정보를 보존했습니다.")
        print(f"신규 옵션 자동 추가: {added_count}개")

        history = load_order_history(history_file)
        new_orders, duplicate_orders = split_new_and_duplicate_orders(all_orders, history)
        duplicate_file = output_folder / "중복제외_주문목록.xlsx"
        duplicate_orders.to_excel(duplicate_file, index=False)

        print("\n" + "=" * 60)
        print("📦 주문 중복 확인")
        print("=" * 60)
        print(f"전체 주문: {len(all_orders)}건")
        print(f"신규 주문: {len(new_orders)}건")
        print(f"이미 처리된 주문: {len(duplicate_orders)}건")

        if new_orders.empty:
            print("\n✅ 새로 발주할 주문이 없습니다.")
            print("같은 주문 파일을 다시 실행해도 중복 발주되지 않습니다.")
            print(f"중복 제외 목록: {duplicate_file.resolve()}")
            return

        matched_orders = match_orders_with_products(new_orders, mapping_file)
        matched_file = output_folder / "쿠팡_주문_매핑결과.xlsx"
        matched_orders.to_excel(matched_file, index=False)

        unmatched_products = create_unmatched_product_list(matched_orders)
        unmatched_file = output_folder / "미매핑_상품목록.xlsx"
        unmatched_products.to_excel(unmatched_file, index=False)

        generate_purchase_orders(matched_orders)

        total_count = len(matched_orders)
        matched_count = int((matched_orders["매핑상태"] == "매핑완료").sum())
        unmatched_count = int((matched_orders["매핑상태"] == "미매핑").sum())

        # 발주 가능한 매핑완료 주문만 처리 이력에 기록합니다.
        processed_orders = matched_orders[matched_orders["매핑상태"] == "매핑완료"].copy()
        saved_count = save_processed_orders(processed_orders, history_file)

        print("\n" + "=" * 60)
        print("📊 신규 주문 처리 결과")
        print("=" * 60)
        print(f"신규 주문: {total_count}건")
        print(f"매핑 완료: {matched_count}건")
        print(f"미매핑 주문: {unmatched_count}건")
        print(f"처리 이력 저장: {saved_count}건")
        print("\n발주회차별 주문 건수")
        round_counts = matched_orders["발주회차"].value_counts().to_dict()
        for purchase_round in ["09시 발주", "13시 발주", "14시 발주", "미분류"]:
            print(f"- {purchase_round}: {round_counts.get(purchase_round, 0)}건")
        print(f"\n✅ 주문 매핑 결과: {matched_file.resolve()}")
        print(f"✅ 주문 처리 이력: {history_file.resolve()}")
        print(f"✅ 미매핑 상품 목록: {unmatched_file.resolve()}")
        if unmatched_count == 0:
            print("\n🎉 모든 신규 주문의 상품 매핑과 발주 처리가 완료되었습니다.")
        else:
            print("\n⚠️ 미매핑 주문은 처리 이력에 저장하지 않았습니다.")
            print("상품매핑표.xlsx를 입력한 뒤 다시 실행하면 해당 주문만 다시 처리됩니다.")

    except PermissionError:
        print("\n❌ output 폴더의 엑셀 파일이 열려 있습니다. 모두 닫고 다시 실행하세요.")
    except Exception as error:
        print(f"\n❌ 오류 발생: {error}")
        raise


