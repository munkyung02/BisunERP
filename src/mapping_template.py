from pathlib import Path

import pandas as pd


MAPPING_KEY_COLUMNS = ["판매채널", "채널상품ID", "채널옵션ID"]
MAPPING_COLUMNS = [
    "판매채널", "채널상품ID", "채널옵션ID", "채널상품명", "채널옵션명",
    "내부옵션코드", "내부상품명", "옵션구성", "구성수량", "공급처",
    "발주마감", "택배사", "포장방식", "매핑상태", "메모",
]


def _normalize_id(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def build_mapping_rows(orders: pd.DataFrame) -> pd.DataFrame:
    required = ["판매채널", "채널상품ID", "채널옵션ID", "채널상품명", "채널옵션명"]
    missing = [column for column in required if column not in orders.columns]
    if missing:
        raise ValueError(f"매핑표 생성에 필요한 컬럼이 없습니다: {missing}")

    mapping = (
        orders[required].copy()
        .drop_duplicates(subset=MAPPING_KEY_COLUMNS)
        .sort_values(MAPPING_KEY_COLUMNS)
        .reset_index(drop=True)
    )
    mapping["내부옵션코드"] = ""
    mapping["내부상품명"] = ""
    mapping["옵션구성"] = ""
    mapping["구성수량"] = 1
    mapping["공급처"] = ""
    mapping["발주마감"] = ""
    mapping["택배사"] = ""
    mapping["포장방식"] = ""
    mapping["매핑상태"] = "미매핑"
    mapping["메모"] = ""
    return mapping[MAPPING_COLUMNS]


def create_mapping_template(orders: pd.DataFrame, output_path: str | Path) -> Path:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    build_mapping_rows(orders).to_excel(output_file, index=False)
    return output_file


def find_existing_mapping_file(output_folder: str | Path) -> Path | None:
    """파일명이 깨져도 컬럼 구조와 입력 데이터로 기존 매핑표를 찾습니다."""
    folder = Path(output_folder)
    candidates: list[tuple[int, Path]] = []
    for path in folder.glob("*.xlsx"):
        try:
            df = pd.read_excel(path, nrows=200)
        except Exception:
            continue
        if not set(MAPPING_COLUMNS).issubset(df.columns):
            continue
        filled = 0
        if "내부옵션코드" in df:
            filled += df["내부옵션코드"].fillna("").astype(str).str.strip().ne("").sum()
        if "공급처" in df:
            filled += df["공급처"].fillna("").astype(str).str.strip().ne("").sum()
        candidates.append((int(filled), path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1].stat().st_mtime))[1]


def sync_mapping_template(orders: pd.DataFrame, mapping_path: str | Path) -> tuple[Path, int]:
    """기존 입력값은 보존하고 새 상품 옵션만 매핑표에 추가합니다."""
    path = Path(mapping_path)
    existing = pd.read_excel(path)
    for column in MAPPING_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    existing = existing[MAPPING_COLUMNS].copy()
    incoming = build_mapping_rows(orders)

    for column in MAPPING_KEY_COLUMNS:
        existing[column] = existing[column].apply(_normalize_id)
        incoming[column] = incoming[column].apply(_normalize_id)

    existing_keys = set(map(tuple, existing[MAPPING_KEY_COLUMNS].itertuples(index=False, name=None)))
    new_mask = [tuple(row) not in existing_keys for row in incoming[MAPPING_KEY_COLUMNS].itertuples(index=False, name=None)]
    additions = incoming.loc[new_mask]
    merged = pd.concat([existing, additions], ignore_index=True)
    merged = merged.drop_duplicates(subset=MAPPING_KEY_COLUMNS, keep="first")
    merged.to_excel(path, index=False)
    return path, len(additions)
