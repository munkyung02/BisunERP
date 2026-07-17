from datetime import time
from pathlib import Path

import pandas as pd


MATCH_KEY_COLUMNS = [
    "판매채널",
    "채널상품ID",
    "채널옵션ID",
]


def normalize_id(value) -> str:
    """엑셀에서 숫자로 읽힌 ID를 비교 가능한 문자열로 정리합니다."""

    if pd.isna(value):
        return ""

    text = str(value).strip()

    # 123456.0처럼 읽힌 ID의 .0 제거
    if text.endswith(".0"):
        text = text[:-2]

    return text


def classify_purchase_round(deadline) -> str:
    """발주마감을 09시·13시·14시 발주로 분류합니다."""

    if pd.isna(deadline) or str(deadline).strip() == "":
        return "미분류"

    hour = None
    minute = 0

    # datetime.time 형식
    if isinstance(deadline, time):
        hour = deadline.hour
        minute = deadline.minute

    # pandas Timestamp 형식
    elif isinstance(deadline, pd.Timestamp):
        hour = deadline.hour
        minute = deadline.minute

    # Excel 시간값이 0~1 사이 숫자로 들어온 경우
    elif isinstance(deadline, (int, float)):
        total_minutes = round(float(deadline) * 24 * 60)
        hour = total_minutes // 60
        minute = total_minutes % 60

    # 09:00, 13:30 등의 문자열
    else:
        text = str(deadline).strip()

        try:
            parsed_time = pd.to_datetime(text).time()
            hour = parsed_time.hour
            minute = parsed_time.minute
        except (ValueError, TypeError):
            return "미분류"

    total_minutes = (hour * 60) + minute

    if total_minutes < 13 * 60:
        return "09시 발주"

    if total_minutes < 14 * 60:
        return "13시 발주"

    return "14시 발주"


def match_orders_with_products(
    orders: pd.DataFrame,
    mapping_file: str | Path,
) -> pd.DataFrame:
    """표준 주문과 상품 매핑표를 결합합니다."""

    mapping_path = Path(mapping_file)

    if not mapping_path.exists():
        raise FileNotFoundError(
            f"상품 매핑 파일을 찾을 수 없습니다: {mapping_path.resolve()}"
        )

    mapping = pd.read_excel(mapping_path)

    required_mapping_columns = [
        "판매채널",
        "채널상품ID",
        "채널옵션ID",
        "내부옵션코드",
        "내부상품명",
        "구성수량",
        "공급처",
        "발주마감",
    ]

    missing_columns = [
        column
        for column in required_mapping_columns
        if column not in mapping.columns
    ]

    if missing_columns:
        raise ValueError(
            f"상품 매핑표에 필요한 컬럼이 없습니다: {missing_columns}"
        )

    orders_copy = orders.copy()
    mapping_copy = mapping.copy()

    # 주문서와 매핑표의 ID 형식을 동일하게 정리
    for column in MATCH_KEY_COLUMNS:
        orders_copy[column] = orders_copy[column].apply(normalize_id)
        mapping_copy[column] = mapping_copy[column].apply(normalize_id)

    # 중복된 매핑이 있으면 첫 번째 값만 사용
    mapping_copy = mapping_copy.drop_duplicates(
        subset=MATCH_KEY_COLUMNS,
        keep="first",
    )

    mapping_columns = [
        "판매채널",
        "채널상품ID",
        "채널옵션ID",
        "내부옵션코드",
        "내부상품명",
        "옵션구성",
        "구성수량",
        "공급처",
        "발주마감",
        "택배사",
        "포장방식",
        "메모",
    ]

    existing_mapping_columns = [
        column
        for column in mapping_columns
        if column in mapping_copy.columns
    ]

    matched = orders_copy.merge(
        mapping_copy[existing_mapping_columns],
        on=MATCH_KEY_COLUMNS,
        how="left",
    )

    # 구성수량이 비어 있으면 기본값 1
    matched["구성수량"] = pd.to_numeric(
        matched["구성수량"],
        errors="coerce",
    ).fillna(1)

    matched["주문수량"] = pd.to_numeric(
        matched["주문수량"],
        errors="coerce",
    ).fillna(0)

    matched["발주수량"] = (
        matched["주문수량"] * matched["구성수량"]
    )

    matched["발주회차"] = matched["발주마감"].apply(
        classify_purchase_round
    )

    matched["매핑상태"] = matched.apply(
        lambda row: (
            "매핑완료"
            if str(row.get("내부옵션코드", "")).strip()
            and str(row.get("공급처", "")).strip()
            else "미매핑"
        ),
        axis=1,
    )

    return matched


def create_unmatched_product_list(
    matched_orders: pd.DataFrame,
) -> pd.DataFrame:
    """아직 매핑되지 않은 채널 상품만 중복 없이 추출합니다."""

    unmatched = matched_orders[
        matched_orders["매핑상태"] == "미매핑"
    ].copy()

    columns = [
        "판매채널",
        "채널상품ID",
        "채널옵션ID",
        "채널상품명",
        "채널옵션명",
    ]

    return (
        unmatched[columns]
        .drop_duplicates(subset=MATCH_KEY_COLUMNS)
        .reset_index(drop=True)
    )
