from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


HISTORY_COLUMNS = [
    "원본고유키",
    "판매채널",
    "주문번호",
    "채널상품ID",
    "채널옵션ID",
    "채널상품명",
    "채널옵션명",
    "주문수량",
    "수취인",
    "처리일시",
]


def load_order_history(history_path: str | Path) -> pd.DataFrame:
    path = Path(history_path)
    if not path.exists():
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    history = pd.read_excel(path)
    for column in HISTORY_COLUMNS:
        if column not in history.columns:
            history[column] = ""
    history["원본고유키"] = history["원본고유키"].fillna("").astype(str).str.strip()
    return history[HISTORY_COLUMNS].copy()


def split_new_and_duplicate_orders(
    orders: pd.DataFrame,
    history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "원본고유키" not in orders.columns:
        raise ValueError("주문 데이터에 원본고유키 컬럼이 없습니다.")

    processed_keys = set(
        history.get("원본고유키", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .str.strip()
    )
    processed_keys.discard("")

    order_keys = orders["원본고유키"].fillna("").astype(str).str.strip()
    duplicate_mask = order_keys.isin(processed_keys)

    duplicates = orders.loc[duplicate_mask].copy().reset_index(drop=True)
    new_orders = orders.loc[~duplicate_mask].copy().reset_index(drop=True)
    return new_orders, duplicates


def save_processed_orders(
    processed_orders: pd.DataFrame,
    history_path: str | Path,
) -> int:
    if processed_orders.empty:
        return 0

    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    history = load_order_history(path)

    rows = processed_orders.copy()
    rows["처리일시"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for column in HISTORY_COLUMNS:
        if column not in rows.columns:
            rows[column] = ""
    rows = rows[HISTORY_COLUMNS]

    combined = pd.concat([history, rows], ignore_index=True)
    combined["원본고유키"] = combined["원본고유키"].fillna("").astype(str).str.strip()
    combined = combined.drop_duplicates(subset=["원본고유키"], keep="first")
    combined.to_excel(path, index=False)
    return len(rows)
