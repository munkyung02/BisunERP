from __future__ import annotations

import ast
import importlib.util
import json
import sqlite3
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "bisun_erp.db"
REPORT_DIR = PROJECT_ROOT / "output" / "diagnostics"

REQUIRED_FILES = (
    "main.py",
    "app/main_window.py",
    "core/database.py",
    "modules/orders/order_page.py",
    "modules/orders/order_repository.py",
    "modules/products/product_page.py",
    "modules/products/product_repository.py",
    "modules/suppliers/supplier_repository.py",
    "modules/mappings/mapping_page.py",
    "modules/mappings/quick_product_dialog.py",
    "modules/purchases/purchase_page.py",
    "modules/purchases/purchase_repository.py",
    "modules/shipments/shipment_page.py",
    "modules/settings/settings_page.py",
    "modules/settings/settings_service.py",
    "modules/backup_manager/backup_page.py",
    "modules/backup_manager/backup_service.py",
    "modules/purchase_dashboard/purchase_dashboard_page.py",
)

REQUIRED_TABLES = {
    "suppliers",
    "products",
    "orders",
    "order_items",
    "purchase_orders",
    "shipments",
    "settings",
}

REQUIRED_COLUMNS = {
    "orders": {
        "id",
        "platform",
        "order_number",
        "order_status",
        "mapping_status",
        "purchase_status",
        "shipment_status",
    },
    "order_items": {
        "id",
        "order_id",
        "platform_product_name",
        "quantity",
        "product_id",
        "mapping_status",
    },
    "products": {
        "id",
        "product_name",
        "is_active",
    },
    "suppliers": {
        "id",
        "supplier_name",
        "is_active",
    },
    "purchase_orders": {
        "id",
        "order_item_id",
        "purchase_status",
    },
    "shipments": {
        "id",
        "order_id",
        "tracking_number",
    },
}

ALLOWED_ORDER_STATES = {
    "주문접수",
    "매핑완료",
    "발주완료",
    "송장등록완료",
}

IGNORED_FILE_NAMES = {
    "legacy_order_runner.py",
    "cli.py",
}

IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "backup",
    "logs",
    "output",
}


@dataclass
class CheckResult:
    category: str
    name: str
    status: str
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


class PreflightChecker:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def add(
        self,
        category: str,
        name: str,
        status: str,
        detail: str = "",
    ) -> None:
        self.results.append(
            CheckResult(
                category=category,
                name=name,
                status=status,
                detail=detail.strip(),
            )
        )

    def run(self) -> int:
        print("=" * 70)
        print("BisunERP v1.0 사전점검")
        print(f"프로젝트: {PROJECT_ROOT}")
        print(f"시작시각: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print("=" * 70)

        self.check_required_files()
        self.check_python_syntax()
        self.check_internal_imports()
        self.check_database()
        self.check_settings_files()
        self.check_backup_configuration()

        report_path = self.write_report()
        self.print_summary(report_path)

        failures = sum(
            result.status == "FAIL"
            for result in self.results
        )
        return 1 if failures else 0

    def check_required_files(self) -> None:
        for relative_path in REQUIRED_FILES:
            path = PROJECT_ROOT / relative_path
            self.add(
                "필수파일",
                relative_path,
                "PASS" if path.exists() else "FAIL",
                (
                    ""
                    if path.exists()
                    else "필수 소스 파일이 없습니다."
                ),
            )

    def check_python_syntax(self) -> None:
        for path in self.iter_python_files():
            relative = path.relative_to(PROJECT_ROOT)

            try:
                source = path.read_text(encoding="utf-8")
                ast.parse(source, filename=str(path))
                self.add(
                    "문법검사",
                    str(relative),
                    "PASS",
                )
            except UnicodeDecodeError:
                self.add(
                    "문법검사",
                    str(relative),
                    "WARN",
                    "UTF-8로 읽을 수 없습니다.",
                )
            except SyntaxError as error:
                self.add(
                    "문법검사",
                    str(relative),
                    "FAIL",
                    (
                        f"{error.msg} "
                        f"(line {error.lineno}, "
                        f"column {error.offset})"
                    ),
                )
            except OSError as error:
                self.add(
                    "문법검사",
                    str(relative),
                    "FAIL",
                    str(error),
                )

    def check_internal_imports(self) -> None:
        checked: set[str] = set()

        for path in self.iter_python_files():
            try:
                tree = ast.parse(
                    path.read_text(encoding="utf-8"),
                    filename=str(path),
                )
            except Exception:
                continue

            for node in ast.walk(tree):
                module_name = None

                if isinstance(node, ast.ImportFrom):
                    if node.level == 0:
                        module_name = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".", 1)[0]
                        if top in {
                            "app",
                            "core",
                            "config",
                            "modules",
                            "src",
                        }:
                            self._check_module(
                                alias.name,
                                checked,
                            )
                    continue

                if module_name:
                    top = module_name.split(".", 1)[0]
                    if top in {
                        "app",
                        "core",
                        "config",
                        "modules",
                        "src",
                    }:
                        self._check_module(
                            module_name,
                            checked,
                        )

    def _check_module(
        self,
        module_name: str,
        checked: set[str],
    ) -> None:
        if module_name in checked:
            return

        checked.add(module_name)

        module_path = PROJECT_ROOT.joinpath(
            *module_name.split(".")
        )
        file_path = module_path.with_suffix(".py")
        init_path = module_path / "__init__.py"

        exists = file_path.exists() or init_path.exists()

        self.add(
            "내부 import",
            module_name,
            "PASS" if exists else "FAIL",
            (
                ""
                if exists
                else (
                    "프로젝트 내부에서 import하지만 "
                    "해당 모듈을 찾을 수 없습니다."
                )
            ),
        )

    def check_database(self) -> None:
        if not DATABASE_PATH.exists():
            self.add(
                "데이터베이스",
                "DB 파일 존재",
                "FAIL",
                str(DATABASE_PATH),
            )
            return

        self.add(
            "데이터베이스",
            "DB 파일 존재",
            "PASS",
            str(DATABASE_PATH),
        )

        try:
            connection = sqlite3.connect(
                f"file:{DATABASE_PATH.as_posix()}?mode=ro",
                uri=True,
            )
            connection.row_factory = sqlite3.Row
        except sqlite3.Error as error:
            self.add(
                "데이터베이스",
                "읽기 전용 연결",
                "FAIL",
                str(error),
            )
            return

        try:
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            self.add(
                "데이터베이스",
                "SQLite 무결성",
                (
                    "PASS"
                    if str(integrity).lower() == "ok"
                    else "FAIL"
                ),
                str(integrity),
            )

            tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }

            for table in sorted(REQUIRED_TABLES):
                self.add(
                    "DB 테이블",
                    table,
                    "PASS" if table in tables else "FAIL",
                    (
                        ""
                        if table in tables
                        else "필수 테이블이 없습니다."
                    ),
                )

            for table, required_columns in (
                REQUIRED_COLUMNS.items()
            ):
                if table not in tables:
                    continue

                columns = {
                    row["name"]
                    for row in connection.execute(
                        f"PRAGMA table_info({table})"
                    ).fetchall()
                }

                missing = sorted(
                    required_columns - columns
                )

                self.add(
                    "DB 컬럼",
                    table,
                    "PASS" if not missing else "FAIL",
                    (
                        ""
                        if not missing
                        else "누락: " + ", ".join(missing)
                    ),
                )

            self.check_duplicate_data(
                connection,
                tables,
            )
            self.check_orphans(
                connection,
                tables,
            )
            self.check_workflow_states(
                connection,
                tables,
            )

        except sqlite3.Error as error:
            self.add(
                "데이터베이스",
                "DB 점검 실행",
                "FAIL",
                str(error),
            )
        finally:
            connection.close()

    def check_duplicate_data(
        self,
        connection: sqlite3.Connection,
        tables: set[str],
    ) -> None:
        duplicate_queries = []

        if "orders" in tables:
            duplicate_queries.append(
                (
                    "중복 주문번호",
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT platform, order_number
                        FROM orders
                        GROUP BY platform, order_number
                        HAVING COUNT(*) > 1
                    )
                    """,
                )
            )

        if "products" in tables:
            duplicate_queries.append(
                (
                    "중복 상품명·옵션",
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT
                            TRIM(COALESCE(product_name, '')) AS product_name,
                            TRIM(COALESCE(option_name, '')) AS option_name
                        FROM products
                        WHERE is_active = 1
                        GROUP BY
                            TRIM(COALESCE(product_name, '')),
                            TRIM(COALESCE(option_name, ''))
                        HAVING COUNT(*) > 1
                    )
                    """,
                )
            )

        if "suppliers" in tables:
            duplicate_queries.append(
                (
                    "중복 공급처명",
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT
                            TRIM(COALESCE(supplier_name, ''))
                        FROM suppliers
                        WHERE is_active = 1
                        GROUP BY
                            TRIM(COALESCE(supplier_name, ''))
                        HAVING COUNT(*) > 1
                    )
                    """,
                )
            )

        for name, query in duplicate_queries:
            count = int(
                connection.execute(query).fetchone()[0]
            )
            self.add(
                "중복데이터",
                name,
                "PASS" if count == 0 else "WARN",
                f"중복 그룹 {count:,}개",
            )

    def check_orphans(
        self,
        connection: sqlite3.Connection,
        tables: set[str],
    ) -> None:
        checks = []

        if {"orders", "order_items"} <= tables:
            checks.append(
                (
                    "주문 없는 주문상품",
                    """
                    SELECT COUNT(*)
                    FROM order_items oi
                    LEFT JOIN orders o
                        ON o.id = oi.order_id
                    WHERE o.id IS NULL
                    """,
                )
            )

        if {"products", "order_items"} <= tables:
            checks.append(
                (
                    "없는 상품에 연결된 주문상품",
                    """
                    SELECT COUNT(*)
                    FROM order_items oi
                    LEFT JOIN products p
                        ON p.id = oi.product_id
                    WHERE oi.product_id IS NOT NULL
                      AND p.id IS NULL
                    """,
                )
            )

        if {"order_items", "purchase_orders"} <= tables:
            checks.append(
                (
                    "주문상품 없는 발주",
                    """
                    SELECT COUNT(*)
                    FROM purchase_orders po
                    LEFT JOIN order_items oi
                        ON oi.id = po.order_item_id
                    WHERE oi.id IS NULL
                    """,
                )
            )

        if {"orders", "shipments"} <= tables:
            checks.append(
                (
                    "주문 없는 송장",
                    """
                    SELECT COUNT(*)
                    FROM shipments s
                    LEFT JOIN orders o
                        ON o.id = s.order_id
                    WHERE o.id IS NULL
                    """,
                )
            )

        for name, query in checks:
            try:
                count = int(
                    connection.execute(query).fetchone()[0]
                )
            except sqlite3.Error as error:
                self.add(
                    "관계무결성",
                    name,
                    "WARN",
                    f"검사 생략: {error}",
                )
                continue

            self.add(
                "관계무결성",
                name,
                "PASS" if count == 0 else "FAIL",
                f"{count:,}건",
            )

    def check_workflow_states(
        self,
        connection: sqlite3.Connection,
        tables: set[str],
    ) -> None:
        if "orders" not in tables:
            return

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(orders)"
            ).fetchall()
        }

        if "order_status" not in columns:
            return

        rows = connection.execute(
            """
            SELECT
                COALESCE(order_status, '') AS state,
                COUNT(*) AS count
            FROM orders
            GROUP BY COALESCE(order_status, '')
            ORDER BY count DESC
            """
        ).fetchall()

        unexpected = [
            f"{row['state'] or '(빈값)'} {row['count']:,}건"
            for row in rows
            if str(row["state"]) not in ALLOWED_ORDER_STATES
        ]

        self.add(
            "업무상태",
            "주문 상태값",
            "PASS" if not unexpected else "WARN",
            (
                "정상"
                if not unexpected
                else "기존/예외 상태: " + ", ".join(unexpected)
            ),
        )

    def check_settings_files(self) -> None:
        settings_path = DATA_DIR / "app_settings.json"
        backup_settings_path = (
            DATA_DIR / "backup_settings.json"
        )

        self.check_json_file(
            settings_path,
            "환경설정 JSON",
            required=False,
        )
        self.check_json_file(
            backup_settings_path,
            "백업설정 JSON",
            required=False,
        )

    def check_json_file(
        self,
        path: Path,
        name: str,
        *,
        required: bool,
    ) -> None:
        if not path.exists():
            self.add(
                "설정파일",
                name,
                "FAIL" if required else "WARN",
                (
                    "파일이 없습니다. 최초 저장 전이라면 정상입니다."
                ),
            )
            return

        try:
            loaded = json.loads(
                path.read_text(encoding="utf-8")
            )
            self.add(
                "설정파일",
                name,
                "PASS" if isinstance(loaded, dict) else "FAIL",
                (
                    ""
                    if isinstance(loaded, dict)
                    else "JSON 최상위 값이 객체가 아닙니다."
                ),
            )
        except Exception as error:
            self.add(
                "설정파일",
                name,
                "FAIL",
                str(error),
            )

    def check_backup_configuration(self) -> None:
        settings_path = DATA_DIR / "backup_settings.json"
        backup_root = PROJECT_ROOT / "backup"

        if settings_path.exists():
            try:
                data = json.loads(
                    settings_path.read_text(
                        encoding="utf-8"
                    )
                )
                configured = data.get("backup_root")
                if configured:
                    backup_root = Path(str(configured))
            except Exception:
                pass

        try:
            backup_root.mkdir(
                parents=True,
                exist_ok=True,
            )
            probe = backup_root / ".bisun_write_test"
            probe.write_text(
                "BisunERP backup write test",
                encoding="utf-8",
            )
            probe.unlink()

            self.add(
                "백업",
                "백업 폴더 쓰기 권한",
                "PASS",
                str(backup_root),
            )
        except OSError as error:
            self.add(
                "백업",
                "백업 폴더 쓰기 권한",
                "FAIL",
                f"{backup_root}\n{error}",
            )

    def iter_python_files(self) -> Iterable[Path]:
        for path in PROJECT_ROOT.rglob("*.py"):
            if path.name in IGNORED_FILE_NAMES:
                continue

            relative_parts = path.relative_to(
                PROJECT_ROOT
            ).parts

            if any(
                part in IGNORED_DIR_NAMES
                for part in relative_parts
            ):
                continue

            yield path

    def _resolve_report_directory(self) -> Path:
        """
        output/diagnostics가 폴더가 아니라 기존 파일로 존재해도
        점검 보고서를 저장할 수 있는 안전한 폴더를 선택합니다.
        """
        candidates = (
            REPORT_DIR,
            PROJECT_ROOT / "output" / "diagnostics_reports",
            PROJECT_ROOT / "diagnostics_reports",
        )

        for candidate in candidates:
            try:
                if candidate.exists() and not candidate.is_dir():
                    continue

                candidate.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                return candidate

            except OSError:
                continue

        fallback = PROJECT_ROOT / (
            "preflight_reports_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        fallback.mkdir(
            parents=True,
            exist_ok=False,
        )
        return fallback

    def write_report(self) -> Path:
        report_dir = self._resolve_report_directory()

        report_path = report_dir / (
            "preflight_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".txt"
        )

        counts = {
            status: sum(
                result.status == status
                for result in self.results
            )
            for status in ("PASS", "WARN", "FAIL")
        }

        lines = [
            "BisunERP v1.0 사전점검 보고서",
            f"생성시각: {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"프로젝트: {PROJECT_ROOT}",
            "",
            (
                f"PASS {counts['PASS']} | "
                f"WARN {counts['WARN']} | "
                f"FAIL {counts['FAIL']}"
            ),
            "=" * 90,
        ]

        current_category = None

        for result in self.results:
            if result.category != current_category:
                current_category = result.category
                lines.extend(
                    [
                        "",
                        f"[{current_category}]",
                    ]
                )

            lines.append(
                f"{result.status:4} | {result.name}"
            )

            if result.detail:
                for detail_line in result.detail.splitlines():
                    lines.append(
                        f"       {detail_line}"
                    )

        report_path.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

        return report_path

    def print_summary(self, report_path: Path) -> None:
        counts = {
            status: sum(
                result.status == status
                for result in self.results
            )
            for status in ("PASS", "WARN", "FAIL")
        }

        print()
        print("=" * 70)
        print(
            f"PASS {counts['PASS']} | "
            f"WARN {counts['WARN']} | "
            f"FAIL {counts['FAIL']}"
        )
        print(f"보고서: {report_path}")
        print("=" * 70)

        important = [
            result
            for result in self.results
            if result.status in {"WARN", "FAIL"}
        ]

        if not important:
            print("중요한 문제가 발견되지 않았습니다.")
            return

        for result in important:
            print(
                f"[{result.status}] "
                f"{result.category} / {result.name}"
            )
            if result.detail:
                print(f"  {result.detail}")


def main() -> None:
    try:
        exit_code = PreflightChecker().run()
    except Exception:
        print("사전점검 실행 중 예외가 발생했습니다.")
        traceback.print_exc()
        exit_code = 2

    try:
        input("\nEnter 키를 누르면 종료합니다...")
    except (EOFError, KeyboardInterrupt):
        pass

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
