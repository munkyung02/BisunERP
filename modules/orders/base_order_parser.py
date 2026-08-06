from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseOrderExcelParser(ABC):
    """판매채널 주문 엑셀 파서의 공통 규격입니다."""

    platform_name = ""
    required_columns: set[str] = set()
    header_search_rows = 15

    def can_parse(self, dataframe: pd.DataFrame) -> bool:
        return self.find_header_row(dataframe) is not None

    def find_header_row(self, dataframe: pd.DataFrame) -> int | None:
        required = {
            self._normalize_column_name(column)
            for column in self.required_columns
        }
        max_rows = min(len(dataframe), self.header_search_rows)

        for row_index in range(max_rows):
            row_values = {
                self._normalize_column_name(value)
                for value in dataframe.iloc[row_index].tolist()
                if self._normalize_column_name(value)
            }
            if required.issubset(row_values):
                return row_index

        return None

    def prepare_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        header_row = self.find_header_row(dataframe)
        if header_row is None:
            raise ValueError(
                f"{self.platform_name} 주문서의 컬럼 행을 찾지 못했습니다."
            )

        raw_columns = dataframe.iloc[header_row].tolist()
        columns = self._make_unique_columns(raw_columns)
        prepared = dataframe.iloc[header_row + 1 :].copy()
        prepared.columns = columns
        return prepared.dropna(how="all").reset_index(drop=True)

    def validate_columns(self, dataframe: pd.DataFrame) -> None:
        current_columns = {
            self._normalize_column_name(column)
            for column in dataframe.columns
        }
        missing_columns = sorted(
            column
            for column in self.required_columns
            if self._normalize_column_name(column) not in current_columns
        )
        if missing_columns:
            raise ValueError(
                f"{self.platform_name} 주문 엑셀에 필요한 컬럼이 없습니다.\n\n"
                "누락 컬럼:\n"
                + "\n".join(f"• {column}" for column in missing_columns)
            )

    @abstractmethod
    def parse(
        self,
        dataframe: pd.DataFrame,
        source_file: str,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @staticmethod
    def _normalize_column_name(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _make_unique_columns(cls, values: list[Any]) -> list[str]:
        columns: list[str] = []
        counts: dict[str, int] = {}
        for index, value in enumerate(values, start=1):
            base_name = cls._normalize_column_name(value) or f"빈컬럼_{index}"
            count = counts.get(base_name, 0)
            counts[base_name] = count + 1
            columns.append(base_name if count == 0 else f"{base_name}_{count + 1}")
        return columns

    @staticmethod
    def clean_text(value: Any) -> str:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
        text = str(value).strip()
        return "" if text.lower() == "nan" else text

    @classmethod
    def clean_identifier(cls, value: Any) -> str:
        text = cls.clean_text(value)
        if text.endswith(".0") and text[:-2].isdigit():
            return text[:-2]
        return text

    @classmethod
    def clean_datetime(cls, value: Any) -> str:
        text = cls.clean_text(value)
        if not text:
            return ""
        try:
            numeric_value = float(text.replace(",", ""))
            if 20000 <= numeric_value <= 80000:
                converted = pd.Timestamp("1899-12-30") + pd.to_timedelta(
                    numeric_value, unit="D"
                )
                return converted.strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            pass
        try:
            converted = pd.to_datetime(value, errors="coerce")
            if pd.isna(converted):
                return text
            return converted.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return text

    @classmethod
    def to_positive_int(cls, value: Any, default: int = 1) -> int:
        text = cls.clean_text(value)
        if not text:
            return default
        try:
            converted = int(float(text.replace(",", "")))
            if converted > 0:
                return converted
        except (TypeError, ValueError):
            pass

        try:
            converted_date = pd.to_datetime(text, errors="coerce")
            if not pd.isna(converted_date) and converted_date.year in {1899, 1900}:
                quantity = (
                    converted_date.normalize() - pd.Timestamp("1899-12-31")
                ).days
                if quantity > 0:
                    return int(quantity)
        except Exception:
            pass
        return default

    @classmethod
    def to_non_negative_int(cls, value: Any, default: int = 0) -> int:
        text = cls.clean_text(value)
        if not text:
            return default
        try:
            converted = int(float(text.replace(",", "")))
        except (TypeError, ValueError):
            return default
        return converted if converted >= 0 else default
