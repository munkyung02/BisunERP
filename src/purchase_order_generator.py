from pathlib import Path

import pandas as pd


# 비선상회 ERP 프로젝트 기준 경로
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
PURCHASE_ORDER_DIR = OUTPUT_DIR / "발주서"


# 발주서 생성에 반드시 필요한 열
REQUIRED_COLUMNS = [
    "판매채널",
    "주문번호",
    "채널상품명",
    "채널옵션명",
    "주문수량",
    "수취인",
    "연락처",
    "우편번호",
    "주소",
    "배송메모",
    "내부옵션코드",
    "내부상품명",
    "구성수량",
    "공급처",
    "발주수량",
    "발주회차",
    "매핑상태",
]


def create_purchase_order_folder() -> Path:
    """
    output/발주서 폴더가 없으면 자동으로 생성합니다.
    이미 존재하면 그대로 사용합니다.
    """
    PURCHASE_ORDER_DIR.mkdir(parents=True, exist_ok=True)
    return PURCHASE_ORDER_DIR


def validate_purchase_order_columns(df: pd.DataFrame) -> None:
    """
    발주서 생성에 필요한 열이 모두 존재하는지 확인합니다.

    필요한 열이 없으면 어떤 열이 빠졌는지 알려주고
    프로그램 실행을 중단합니다.
    """
    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise ValueError(
            "발주서 생성에 필요한 열이 없습니다.\n"
            f"누락된 열: {missing_text}"
        )


def prepare_purchase_order_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    주문 매핑 결과에서 발주 가능한 주문만 추려냅니다.

    조건:
    1. 매핑상태가 '매핑완료'
    2. 공급처가 비어 있지 않음
    3. 발주회차가 비어 있지 않음
    4. 발주회차가 '미분류'가 아님
    """
    validate_purchase_order_columns(df)

    prepared_df = df.copy()

    # 문자열 열의 빈칸과 NaN 값을 정리합니다.
    text_columns = [
        "공급처",
        "발주회차",
        "매핑상태",
        "내부상품명",
        "채널옵션명",
        "수취인",
        "연락처",
        "우편번호",
        "주소",
        "배송메모",
    ]

    for column in text_columns:
        prepared_df[column] = (
            prepared_df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    # 발주수량을 숫자로 변환합니다.
    prepared_df["발주수량"] = pd.to_numeric(
        prepared_df["발주수량"],
        errors="coerce",
    ).fillna(0)

    # 실제 발주 가능한 주문만 남깁니다.
    prepared_df = prepared_df[
        (prepared_df["매핑상태"] == "매핑완료")
        & (prepared_df["공급처"] != "")
        & (prepared_df["발주회차"] != "")
        & (prepared_df["발주회차"] != "미분류")
        & (prepared_df["발주수량"] > 0)
    ].copy()

    return prepared_df


def print_purchase_order_summary(df: pd.DataFrame) -> None:
    """
    생성 대상 주문의 간단한 요약을 터미널에 출력합니다.
    """
    if df.empty:
        print("발주서로 생성할 주문이 없습니다.")
        return

    supplier_count = df["공급처"].nunique()
    round_count = df["발주회차"].nunique()
    order_count = len(df)
    total_quantity = df["발주수량"].sum()

    print("=== 발주서 생성 대상 요약 ===")
    print(f"주문 행 수: {order_count}건")
    print(f"공급처 수: {supplier_count}곳")
    print(f"발주회차 수: {round_count}개")
    print(f"총 발주수량: {int(total_quantity)}")

def create_purchase_order_sheet(
    supplier_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    공급처 발주 요약을 생성합니다.

    같은 내부상품명의 발주수량을 합산합니다.
    """

    summary_df = (
        supplier_df
        .groupby(
            "내부상품명",
            as_index=False,
        )["발주수량"]
        .sum()
        .sort_values("내부상품명")
    )

    return summary_df


def generate_purchase_orders(df: pd.DataFrame) -> None:
    """
    발주회차별, 공급처별 발주서를 생성합니다.
    """

    print()
    print("=" * 60)
    print("공급처별 발주서 생성 시작")
    print("=" * 60)

    create_purchase_order_folder()

    prepared_df = prepare_purchase_order_data(df)

    print_purchase_order_summary(prepared_df)

    if prepared_df.empty:
        print()
        print("생성할 발주서가 없습니다.")
        return

    # 발주회차와 공급처를 기준으로 주문을 분리합니다.
    grouped = prepared_df.groupby(
        ["발주회차", "공급처"],
        sort=True,
    )

    print()
    print("=== 생성 예정 발주서 ===")

    for (purchase_round, supplier), supplier_df in grouped:
        print(
            f"{purchase_round} | "
            f"{supplier} | "
            f"{len(supplier_df)}건"
        )

        # 발주회차별 폴더를 생성합니다.
        round_folder = PURCHASE_ORDER_DIR / purchase_round
        round_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        # 공급처별 발주서 파일명을 생성합니다.
        file_name = f"{supplier}_발주서.xlsx"
        save_path = round_folder / file_name

        # 상품별 발주수량 요약표를 생성합니다.
        summary_df = create_purchase_order_sheet(
            supplier_df
        )

        # 같은 시트에 상품 요약과 주문 상세를 저장합니다.
        with pd.ExcelWriter(
            save_path,
            engine="openpyxl",
        ) as writer:
            summary_df.to_excel(
                writer,
                sheet_name="발주서",
                startrow=0,
                index=False,
            )

            supplier_df.to_excel(
                writer,
                sheet_name="발주서",
                startrow=len(summary_df) + 3,
                index=False,
            )

        print(f"✅ 생성 완료: {save_path.name}")

    print()
    print("발주서 생성 완료")
    