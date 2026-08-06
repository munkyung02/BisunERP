from pathlib import Path

from config.coupang import COLUMN_MAP, PLATFORM_NAME
from src.excel_reader import find_first_excel, read_excel_file
from src.mapping_template import create_mapping_template
from src.matcher import (
    create_unmatched_product_list,
    match_orders_with_products,
)
from src.order_parser import parse_coupang_orders
from src.purchase_order_generator import generate_purchase_orders


def main() -> None:
    print("=" * 55)
    print("🚀 비선상회 ERP v0.4 시작")
    print("=" * 55)

    try:
        # 폴더 설정
        output_folder = Path("output")
        output_folder.mkdir(parents=True, exist_ok=True)

        mapping_file = output_folder / "상품매핑_초기템플릿.xlsx"

        # 1. 쿠팡 원본 주문서 읽기
        excel_file = find_first_excel("data")
        original_orders = read_excel_file(excel_file)

        # 2. ERP 표준 주문으로 변환
        orders = parse_coupang_orders(original_orders)

        print(f"\n판매채널: {PLATFORM_NAME}")
        print(f"원본 파일: {excel_file.name}")
        print(f"주문 건수: {len(orders)}건")

        print("\n필수 컬럼 확인")

        for internal_name, excel_column in COLUMN_MAP.items():
            exists = excel_column in original_orders.columns
            result = "✅" if exists else "❌"
            print(f"{result} {internal_name}: {excel_column}")

        # 3. 표준 주문 파일 저장
        standard_order_file = output_folder / "쿠팡_표준주문.xlsx"
        orders.to_excel(standard_order_file, index=False)

        print("\n✅ 표준 주문 파일 생성 완료")
        print(f"📁 {standard_order_file.resolve()}")

        # 4. 매핑 템플릿은 처음 한 번만 생성
        if not mapping_file.exists():
            create_mapping_template(
                orders=orders,
                output_path=mapping_file,
            )

            print("\n✅ 상품 매핑 템플릿 최초 생성 완료")
            print(f"📁 {mapping_file.resolve()}")
            print("상품 정보를 입력한 후 프로그램을 다시 실행하세요.")
            return

        print("\n✅ 기존 상품 매핑표를 사용합니다.")
        print("대표님이 입력한 매핑 정보는 덮어쓰지 않습니다.")

        # 5. 주문과 상품 매핑
        matched_orders = match_orders_with_products(
            orders=orders,
            mapping_file=mapping_file,
        )

        matched_file = output_folder / "쿠팡_주문_매핑결과.xlsx"
        matched_orders.to_excel(matched_file, index=False)

        # 6. 미매핑 상품 별도 저장
        unmatched_products = create_unmatched_product_list(
            matched_orders
        )

        unmatched_file = output_folder / "미매핑_상품목록.xlsx"
        unmatched_products.to_excel(unmatched_file, index=False)

        total_count = len(matched_orders)
        # 7. 공급처별 발주서 생성 준비
        generate_purchase_orders(matched_orders)

        # 8. 결과 집계
        
        matched_count = (
            matched_orders["매핑상태"] == "매핑완료"
        ).sum()
        unmatched_count = (
            matched_orders["매핑상태"] == "미매핑"
        ).sum()

        print("\n" + "=" * 55)
        print("📊 상품 매핑 결과")
        print("=" * 55)
        print(f"전체 주문: {total_count}건")
        print(f"매핑 완료: {matched_count}건")
        print(f"미매핑 주문: {unmatched_count}건")

        print("\n발주회차별 주문 건수")

        round_counts = (
            matched_orders["발주회차"]
            .value_counts()
            .to_dict()
        )

        for purchase_round in [
            "09시 발주",
            "13시 발주",
            "14시 발주",
            "미분류",
        ]:
            count = round_counts.get(purchase_round, 0)
            print(f"- {purchase_round}: {count}건")

        print("\n✅ 주문 매핑 결과 파일")
        print(f"📁 {matched_file.resolve()}")

        print("\n✅ 미매핑 상품 목록")
        print(f"📁 {unmatched_file.resolve()}")

        if unmatched_count == 0:
            print("\n🎉 모든 주문의 상품 매핑이 완료되었습니다.")
        else:
            print(
                "\n⚠️ 미매핑_상품목록.xlsx를 확인해 "
                "상품 매핑표에 추가해야 합니다."
            )

    except PermissionError:
        print(
            "\n❌ 저장하려는 엑셀 파일이 열려 있습니다.\n"
            "output 폴더의 엑셀 파일을 모두 닫고 다시 실행하세요."
        )

    except Exception as error:
        print(f"\n❌ 오류 발생: {error}")


if __name__ == "__main__":
    main()