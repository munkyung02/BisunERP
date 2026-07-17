from pathlib import Path

import pandas as pd


def find_first_excel(data_folder: str | Path) -> Path:
    """data 폴더에서 가장 최근에 수정된 주문 엑셀을 찾습니다."""
    folder = Path(data_folder)
    excel_files = [
        path for path in folder.glob("*.xlsx")
        if not path.name.startswith("~$")
    ]

    if not excel_files:
        raise FileNotFoundError(f"엑셀 파일이 없습니다: {folder.resolve()}")

    return max(excel_files, key=lambda path: path.stat().st_mtime)


def read_excel_file(file_path: str | Path) -> pd.DataFrame:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    return pd.read_excel(path)
