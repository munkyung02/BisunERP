from __future__ import annotations

import hashlib
import gc
import json
import platform
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from core.qa.models import QACheckResult, QAReport
from core.qa.read_only_database import (
    DATABASE_PATH,
    ReadOnlyChannelShipmentExportRepository,
    ReadOnlyOrderRepository,
    ReadOnlyPurchaseService,
    ReadOnlyShipmentRepository,
    connect_read_only,
)
from core.version import ERP_NAME, ERP_VERSION
from modules.command_center.activity_log_repository import ActivityLogRepository
from modules.erp_assistant.assistant_repository import ReadOnlyAssistantRepository
from modules.erp_assistant.intent_parser import AssistantIntent, KoreanIntentParser
from modules.notion_sync.notion_live_service import NotionLiveSyncService
from modules.notion_sync.notion_sync_service import PERSISTENT_TOKEN_PATH
from modules.order_validation.service import OrderValidationService
from modules.orders.order_repository import OrderRepository


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class QAAutomationService:
    CHECKS = (
        ("database", "Database"),
        ("notion_connection", "Notion Connection"),
        ("supplier_preview", "Supplier Preview"),
        ("product_preview", "Product Preview"),
        ("auto_mapping", "Auto Mapping (temporary DB)"),
        ("order_validation", "Order Validation"),
        ("purchase_dry_run", "Purchase Dry Run"),
        ("shipment_readiness", "Shipment Readiness"),
        ("coupang_export", "Coupang Export Readiness"),
        ("smartstore_export", "SmartStore Export Readiness"),
        ("erp_assistant", "ERP Assistant"),
        ("command_center", "Command Center"),
    )

    EXCLUDED_FINGERPRINT_TABLES = {"erp_activity_logs"}

    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path).resolve()
        self.activity_repository = ActivityLogRepository(self.database_path)
        self._shared: dict[str, Any] = {}

    def run_all(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> QAReport:
        started = perf_counter()
        self._shared = {}
        before = self._business_fingerprint()
        results: list[QACheckResult] = []
        for check_id, name in self.CHECKS:
            if progress_callback is not None:
                progress_callback(name)
            results.append(self._run_isolated(check_id, name))

        after = self._business_fingerprint()
        if before != after:
            database_result = next(row for row in results if row.check_id == "database")
            database_result.status = "FAILED"
            database_result.summary = "QA 실행 중 production business data가 변경되었습니다."
            database_result.detail = self._fingerprint_difference(before, after)

        report = QAReport(
            metadata=self.get_report_metadata(),
            results=results,
            elapsed_seconds=round(perf_counter() - started, 3),
            execution_type="full",
        )
        self._log_report(report, "QA 전체 진단")
        return report

    def run_one(self, check_id: str) -> QAReport:
        definitions = dict(self.CHECKS)
        if check_id not in definitions:
            raise ValueError(f"지원하지 않는 QA 검사입니다: {check_id}")
        started = perf_counter()
        self._shared = {}
        before = self._business_fingerprint()
        result = self._run_isolated(check_id, definitions[check_id])
        after = self._business_fingerprint()
        if before != after:
            result.status = "FAILED"
            result.summary = "개별 QA 실행 중 production business data가 변경되었습니다."
            result.detail = self._fingerprint_difference(before, after)
        report = QAReport(
            metadata=self.get_report_metadata(),
            results=[result],
            elapsed_seconds=round(perf_counter() - started, 3),
            execution_type="single",
        )
        self._log_report(report, f"QA 개별 진단 · {definitions[check_id]}")
        return report

    def _run_isolated(self, check_id: str, name: str) -> QACheckResult:
        started = perf_counter()
        try:
            status, summary, detail, data = getattr(self, f"_check_{check_id}")()
        except Exception as error:
            status, summary, detail, data = (
                "FAILED",
                str(error) or error.__class__.__name__,
                f"{error.__class__.__name__}: {error}",
                {"exception_type": error.__class__.__name__},
            )
        return QACheckResult(
            check_id=check_id,
            name=name,
            status=status,
            summary=summary,
            detail=detail,
            elapsed_seconds=round(perf_counter() - started, 3),
            data=data,
        )

    def _check_database(self):
        with connect_read_only(self.database_path) as connection:
            connection.execute("SELECT 1").fetchone()
            quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            table_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                ).fetchone()[0]
            )
        status = "PASS" if quick_check.lower() == "ok" else "FAILED"
        return status, f"SQLite quick_check: {quick_check}", f"테이블 {table_count:,}개", {
            "quick_check": quick_check,
            "table_count": table_count,
        }

    def _check_notion_connection(self):
        token = self._notion_token()
        if not token:
            return "WARNING", "Notion 토큰이 설정되지 않았습니다.", "연결 검사를 건너뛰었습니다.", {}
        result = self._notion_service().connection_test(token)
        count = int(result.get("resource_count", 0) or 0)
        status = "PASS" if count else "WARNING"
        return status, f"Notion 공유 데이터소스 {count:,}개", str(result.get("user_name") or ""), {
            "resource_count": count,
        }

    def _check_supplier_preview(self):
        if not self._notion_token():
            return "WARNING", "Notion 토큰이 없어 공급처 미리보기를 건너뛰었습니다.", "production data는 변경되지 않았습니다.", {}
        preview = self._notion_preview()
        count = len(preview.suppliers)
        status = "PASS" if count else "WARNING"
        return status, f"공급처 미리보기 {count:,}건", self._warning_detail(preview.warnings), {
            "supplier_count": count,
            "warning_count": len(preview.warnings),
        }

    def _check_product_preview(self):
        if not self._notion_token():
            return "WARNING", "Notion 토큰이 없어 상품 미리보기를 건너뛰었습니다.", "production data는 변경되지 않았습니다.", {}
        preview = self._notion_preview()
        count = len(preview.products)
        status = "PASS" if count else "WARNING"
        return status, f"상품 미리보기 {count:,}건", self._warning_detail(preview.warnings), {
            "product_count": count,
            "warning_count": len(preview.warnings),
        }

    def _check_auto_mapping(self):
        with tempfile.TemporaryDirectory(prefix="bisun_qa_mapping_") as temp_dir:
            copied_database = Path(temp_dir) / "qa_mapping.db"
            with connect_read_only(self.database_path) as source:
                target = sqlite3.connect(copied_database)
                try:
                    source.backup(target)
                finally:
                    target.close()
            repository = OrderRepository(copied_database)
            result = repository.auto_map_order_items()
            del repository
            gc.collect()
        target_count = int(result.get("target_count", 0) or 0)
        issue_count = int(result.get("unmatched_count", 0) or 0) + int(
            result.get("ambiguous_count", 0) or 0
        )
        status = "WARNING" if not target_count or issue_count else "PASS"
        summary = (
            "자동매핑 대상이 없습니다."
            if not target_count
            else f"대상 {target_count:,} · 매핑 {int(result.get('mapped_count', 0) or 0):,}"
        )
        return status, summary, json.dumps(result, ensure_ascii=False), result

    def _check_order_validation(self):
        summary = OrderValidationService(
            ReadOnlyOrderRepository(self.database_path)
        ).get_summary()
        total = int(summary.get("total_count", 0) or 0)
        failed = int(summary.get("fail_count", 0) or 0)
        warnings = int(summary.get("warning_count", 0) or 0)
        status = "FAILED" if failed else "WARNING" if warnings or not total else "PASS"
        detail = {key: value for key, value in summary.items() if key != "results"}
        return status, f"전체 {total:,} · 주의 {warnings:,} · 실패 {failed:,}", json.dumps(detail, ensure_ascii=False), detail

    def _check_purchase_dry_run(self):
        service = ReadOnlyPurchaseService(self.database_path)
        candidates = service.get_purchase_candidates()
        validation = service.validate_purchase_candidates(candidates)
        errors = len(validation.get("errors") or [])
        warnings = len(validation.get("warnings") or [])
        status = "FAILED" if errors else "WARNING" if warnings or not candidates else "PASS"
        return status, f"후보 {len(candidates):,} · 주의 {warnings:,} · 오류 {errors:,}", self._validation_detail(validation), {
            "candidate_count": len(candidates),
            "warning_count": warnings,
            "error_count": errors,
        }

    def _check_shipment_readiness(self):
        repository = ReadOnlyShipmentRepository(self.database_path)
        waiting = repository.get_shipment_waiting_count()
        summary = repository.get_shipment_summary()
        status = "PASS" if waiting else "WARNING"
        return status, f"송장등록 대기 {waiting:,}건", json.dumps(summary, ensure_ascii=False), summary

    def _check_coupang_export(self):
        missing_tables = self._missing_tables(
            "channel_order_item_metadata",
            "channel_shipment_export_history",
        )
        if missing_tables:
            return "WARNING", "Coupang export schema가 준비되지 않았습니다.", ", ".join(missing_tables), {
                "missing_tables": missing_tables,
            }
        rows = ReadOnlyChannelShipmentExportRepository(
            self.database_path
        ).get_coupang_candidates()
        status = "PASS" if rows else "WARNING"
        return status, f"쿠팡 미출력 대상 {len(rows):,}건", "파일 생성과 이력 기록은 실행하지 않았습니다.", {
            "candidate_count": len(rows),
        }

    def _check_smartstore_export(self):
        missing_tables = self._missing_tables(
            "channel_order_item_metadata",
            "channel_shipment_export_history",
        )
        if missing_tables:
            return "WARNING", "SmartStore export schema가 준비되지 않았습니다.", ", ".join(missing_tables), {
                "missing_tables": missing_tables,
            }
        repository = ReadOnlyChannelShipmentExportRepository(self.database_path)
        rows = repository.get_smartstore_candidates()
        missing = repository.count_smartstore_missing_metadata()
        status = "PASS" if rows and not missing else "WARNING"
        return status, f"스마트스토어 미출력 대상 {len(rows):,} · 메타데이터 없음 {missing:,}", "파일 생성과 이력 기록은 실행하지 않았습니다.", {
            "candidate_count": len(rows),
            "missing_metadata_count": missing,
        }

    def _check_erp_assistant(self):
        parsed = KoreanIntentParser().parse("오늘 주문 몇 건이야?")
        count = ReadOnlyAssistantRepository(self.database_path).get_today_order_count()
        if parsed.intent is not AssistantIntent.TODAY_ORDER_COUNT:
            return "FAILED", "ERP Assistant intent parser 응답이 올바르지 않습니다.", str(parsed.intent), {}
        return "PASS", f"ERP Assistant 사용 가능 · 오늘 주문 {count:,}건", parsed.intent.value, {
            "today_order_count": count,
        }

    def _check_command_center(self):
        from modules.command_center.command_center_page import CommandCenterPage
        from modules.command_center.command_center_service import CommandCenterService

        methods = {
            "get_data": callable(getattr(CommandCenterService, "get_data", None)),
            "run_daily_operation": callable(
                getattr(CommandCenterService, "run_daily_operation", None)
            ),
            "page": CommandCenterPage is not None,
        }
        status = "PASS" if all(methods.values()) else "FAILED"
        return status, "Command Center 업무 서비스 사용 가능" if status == "PASS" else "Command Center 구성요소 누락", json.dumps(methods, ensure_ascii=False), methods

    def _notion_service(self) -> NotionLiveSyncService:
        service = self._shared.get("notion_service")
        if service is None:
            service = NotionLiveSyncService.__new__(NotionLiveSyncService)
            self._shared["notion_service"] = service
        return service

    def _missing_tables(self, *table_names: str) -> list[str]:
        placeholders = ",".join("?" for _ in table_names)
        with connect_read_only(self.database_path) as connection:
            existing = {
                str(row[0])
                for row in connection.execute(
                    f"SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ({placeholders})",
                    table_names,
                ).fetchall()
            }
        return [name for name in table_names if name not in existing]

    def _notion_preview(self):
        if "notion_preview_error" in self._shared:
            raise self._shared["notion_preview_error"]
        if "notion_preview" not in self._shared:
            token = self._notion_token()
            if not token:
                raise RuntimeError("Notion 토큰이 설정되지 않아 미리보기를 실행할 수 없습니다.")
            try:
                self._shared["notion_preview"] = self._notion_service().preview(token)
            except Exception as error:
                self._shared["notion_preview_error"] = error
                raise
        return self._shared["notion_preview"]

    def _notion_token(self) -> str:
        if PERSISTENT_TOKEN_PATH.exists():
            try:
                payload = json.loads(PERSISTENT_TOKEN_PATH.read_text(encoding="utf-8"))
                token = str(payload.get("token") or "").strip()
                if token:
                    return token
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        with connect_read_only(self.database_path) as connection:
            row = connection.execute(
                "SELECT setting_value FROM settings WHERE setting_key = ?",
                ("notion.api_token",),
            ).fetchone()
        return str(row[0] or "").strip() if row else ""

    def get_report_metadata(self) -> dict[str, str]:
        with connect_read_only(self.database_path) as connection:
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            schema_version = int(connection.execute("PRAGMA schema_version").fetchone()[0])
        return {
            "ERP Name": ERP_NAME,
            "ERP Version": ERP_VERSION,
            "Git Branch": self._git_value("branch", "--show-current"),
            "Git Commit": self._git_value("rev-parse", "HEAD"),
            "Execution Time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "Python Version": platform.python_version(),
            "SQLite Version": sqlite3.sqlite_version,
            "Database user_version": str(user_version),
            "Database schema_version": str(schema_version),
            "Database Path": str(self.database_path),
        }

    @staticmethod
    def _git_value(*arguments: str) -> str:
        try:
            return subprocess.run(
                ["git", *arguments],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            ).stdout.strip() or "unavailable"
        except (OSError, subprocess.SubprocessError):
            return "unavailable"

    def _business_fingerprint(self) -> dict[str, str]:
        fingerprints: dict[str, str] = {}
        with connect_read_only(self.database_path) as connection:
            tables = [
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
                if str(row[0]) not in self.EXCLUDED_FINGERPRINT_TABLES
            ]
            for table in tables:
                quoted = table.replace('"', '""')
                digest = hashlib.sha256()
                for row in connection.execute(f'SELECT * FROM "{quoted}" ORDER BY rowid'):
                    digest.update(json.dumps(tuple(row), ensure_ascii=False, default=str).encode("utf-8"))
                    digest.update(b"\n")
                fingerprints[table] = digest.hexdigest()
        return fingerprints

    @staticmethod
    def _fingerprint_difference(before: dict[str, str], after: dict[str, str]) -> str:
        names = sorted(set(before) | set(after))
        changed = [name for name in names if before.get(name) != after.get(name)]
        return "변경 감지 테이블: " + (", ".join(changed) if changed else "없음")

    def _log_report(self, report: QAReport, action: str) -> None:
        status = "실패" if report.failed_count else "주의" if report.warning_count else "성공"
        self.activity_repository.append(
            action=action,
            result_status=status,
            result_message=(
                f"PASS {report.pass_count} · WARNING {report.warning_count} · "
                f"FAILED {report.failed_count} · {report.elapsed_seconds:.2f}초"
            ),
            details=report.as_dict(),
        )

    @staticmethod
    def _warning_detail(warnings: list[str]) -> str:
        return "\n".join(warnings) if warnings else "주의사항 없음"

    @staticmethod
    def _validation_detail(validation: dict[str, Any]) -> str:
        messages = [
            *[f"ERROR · {value}" for value in validation.get("errors") or []],
            *[f"WARNING · {value}" for value in validation.get("warnings") or []],
        ]
        return "\n".join(messages) if messages else "발주 필수정보 검사 통과"
