from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from modules.oms_adapters.defaults import create_default_adapter_registry
from modules.oms_adapters.legacy_excel_adapter import LegacyExcelOrderAdapter
from modules.orders.base_order_parser import BaseOrderExcelParser


DEFAULT_EXCEL_PASSWORD = "1111"


class OrderExcelParser:
    """판매채널 자동 판별과 파서 실행을 담당합니다."""

    def __init__(self, excel_password: str = DEFAULT_EXCEL_PASSWORD) -> None:
        self.excel_password = excel_password
        self.adapter_registry = create_default_adapter_registry()
        self.parsers: list[BaseOrderExcelParser] = [
            adapter.parser
            for adapter in self.adapter_registry.adapters
            if isinstance(adapter, LegacyExcelOrderAdapter)
        ]

    def read_excel(self, file_path: str | Path) -> pd.DataFrame:
        path = self._validate_file_path(file_path)
        try:
            return self._read_raw_dataframe(path)
        except Exception as original_error:
            try:
                with tempfile.TemporaryDirectory(prefix="bisun_order_") as temp_dir:
                    output_path = Path(temp_dir) / f"decrypted_{path.name}"
                    self._decrypt_with_msoffcrypto(path, output_path)
                    return self._read_raw_dataframe(output_path)
            except Exception as decrypt_error:
                raise RuntimeError(
                    "주문 엑셀 파일을 읽지 못했습니다.\n\n"
                    f"기본 비밀번호 '{self.excel_password}'로 열기를 시도했습니다.\n\n"
                    f"첫 번째 읽기 오류:\n{original_error}\n\n"
                    f"암호 해제 오류:\n{decrypt_error}\n\n"
                    "필요 패키지: pip install msoffcrypto-tool"
                ) from decrypt_error

    @staticmethod
    def _read_raw_dataframe(path: Path) -> pd.DataFrame:
        dataframe = pd.read_excel(path, header=None, dtype=str)
        dataframe = dataframe.dropna(how="all").reset_index(drop=True)
        if dataframe.empty:
            raise ValueError("엑셀 파일에 주문 데이터가 없습니다.")
        return dataframe

    def _decrypt_with_msoffcrypto(self, source_path: Path, output_path: Path) -> None:
        import msoffcrypto
        with source_path.open("rb") as source_file:
            office_file = msoffcrypto.OfficeFile(source_file)
            office_file.load_key(password=self.excel_password)
            with output_path.open("wb") as output_file:
                office_file.decrypt(output_file)

    def detect_platform(
        self,
        file_path: str | Path | None = None,
        dataframe: pd.DataFrame | None = None,
    ) -> str:
        if dataframe is None:
            if file_path is None:
                raise ValueError("파일 경로 또는 데이터프레임이 필요합니다.")
            dataframe = self.read_excel(file_path)
        return self._find_parser(dataframe).platform_name

    def parse(self, file_path: str | Path) -> dict[str, Any]:
        path = self._validate_file_path(file_path)
        dataframe = self.read_excel(path)
        parser = self._find_parser(dataframe)
        orders = parser.parse(dataframe=dataframe, source_file=path.name)
        prepared_dataframe = parser.prepare_dataframe(dataframe)
        return {
            "platform": parser.platform_name,
            "source_file": path.name,
            "excel_row_count": len(prepared_dataframe),
            "parsed_order_count": len(orders),
            "orders": orders,
        }

    def parse_multiple(self, file_paths: Iterable[str | Path]) -> dict[str, Any]:
        normalized_paths = list(file_paths)
        if not normalized_paths:
            raise ValueError("선택한 주문서 파일이 없습니다.")

        file_results: list[dict[str, Any]] = []
        all_orders: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for file_path in normalized_paths:
            try:
                result = self.parse(file_path)
                file_results.append(result)
                all_orders.extend(result["orders"])
            except Exception as error:
                errors.append({"file_path": str(file_path), "error": str(error)})

        return {
            "file_count": len(normalized_paths),
            "success_file_count": len(file_results),
            "failed_file_count": len(errors),
            "parsed_order_count": len(all_orders),
            "files": file_results,
            "orders": all_orders,
            "errors": errors,
        }

    def register_parser(self, parser: BaseOrderExcelParser) -> None:
        if not isinstance(parser, BaseOrderExcelParser):
            raise TypeError("BaseOrderExcelParser를 상속한 파서만 등록할 수 있습니다.")
        self.adapter_registry.register(
            LegacyExcelOrderAdapter(
                parser,
                adapter_id=f"legacy.{parser.platform_name}.{len(self.parsers) + 1}",
                display_name=f"{parser.platform_name} 주문 Excel",
                version="1.0",
                priority=(len(self.parsers) + 1) * 100,
            )
        )
        self.parsers.append(parser)

    def _find_parser(self, dataframe: pd.DataFrame) -> BaseOrderExcelParser:
        matched_adapters = self.adapter_registry.matching_adapters(dataframe)
        matched = [
            adapter.parser
            for adapter in matched_adapters
            if isinstance(adapter, LegacyExcelOrderAdapter)
        ]
        if not matched:
            raise ValueError(
                "지원하는 판매채널 주문서 형식을 확인할 수 없습니다.\n\n"
                "현재 지원 채널: 쿠팡, 스마트스토어"
            )
        if len(matched) > 1:
            platforms = ", ".join(parser.platform_name for parser in matched)
            raise ValueError(f"판매채널을 하나로 판별하지 못했습니다.\n\n판별 후보: {platforms}")
        return matched[0]

    @staticmethod
    def _validate_file_path(file_path: str | Path) -> Path:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다.\n{path}")
        if path.suffix.lower() not in {".xlsx", ".xls"}:
            raise ValueError("엑셀 파일만 불러올 수 있습니다.")
        return path
