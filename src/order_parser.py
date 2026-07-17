import pandas as pd

from config.coupang import COLUMN_MAP, PLATFORM_NAME


def parse_coupang_orders(df: pd.DataFrame) -> pd.DataFrame:
    """쿠팡 주문서를 ERP 표준 형식으로 변환합니다."""

    missing_columns = [
        excel_column
        for excel_column in COLUMN_MAP.values()
        if excel_column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"쿠팡 주문서에 필요한 컬럼이 없습니다: {missing_columns}"
        )

    orders = pd.DataFrame(
        {
            "판매채널": PLATFORM_NAME,
            "주문번호": df[COLUMN_MAP["order_number"]].astype(str),
            "채널상품ID": df[COLUMN_MAP["product_id"]].astype(str),
            "채널옵션ID": df[COLUMN_MAP["option_id"]].astype(str),
            "채널상품명": df[COLUMN_MAP["product_name"]].fillna(""),
            "채널옵션명": df[COLUMN_MAP["option_name"]].fillna(""),
            "주문수량": pd.to_numeric(
                df[COLUMN_MAP["quantity"]],
                errors="coerce",
            ).fillna(0).astype(int),
            "결제금액": pd.to_numeric(
                df[COLUMN_MAP["payment_amount"]],
                errors="coerce",
            ).fillna(0),
            "수취인": df[COLUMN_MAP["receiver_name"]].fillna(""),
            "연락처": df[COLUMN_MAP["receiver_phone"]].fillna(""),
            "우편번호": df[COLUMN_MAP["postal_code"]].fillna(""),
            "주소": df[COLUMN_MAP["address"]].fillna(""),
            "배송메모": df[COLUMN_MAP["delivery_message"]].fillna(""),
        }
    )

    orders["원본고유키"] = (
        orders["판매채널"]
        + "|"
        + orders["주문번호"]
        + "|"
        + orders["채널옵션ID"]
    )

    return orders