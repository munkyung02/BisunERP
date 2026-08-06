from __future__ import annotations

import json
import sqlite3
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_ROOT / "data" / "bisun_erp.db"
REPORT_DIR = PROJECT_ROOT / "output" / "workflow_tests"


@dataclass
class Snapshot:
    captured_at: str
    counts: dict[str, int]
    order_states: dict[str, int]
    mapping_states: dict[str, int]
    purchase_states: dict[str, int]
    shipment_states: dict[str, int]
    latest_orders: list[dict[str, Any]]


class WorkflowTester:
    def __init__(self) -> None:
        self.snapshots: list[tuple[str, Snapshot]] = []
        self.notes: list[str] = []

    def run(self) -> None:
        print("=" * 74)
        print("BisunERP v1.0 실사용 흐름 테스트")
        print(f"프로젝트: {PROJECT_ROOT}")
        print(f"DB: {DATABASE_PATH}")
        print("=" * 74)

        if not DATABASE_PATH.exists():
            print("\n[오류] 데이터베이스 파일을 찾을 수 없습니다.")
            print("이 파일을 BisunERP 최상위 폴더에서 실행하세요.")
            self.pause()
            return

        self.capture("테스트 시작 전")

        self.step(
            "1. ERP 실행",
            [
                "main.py로 ERP를 실행합니다.",
                "메인화면이 오류 없이 열리는지 확인합니다.",
                "Dashboard, 주문관리, 상품매핑, 발주관리, 송장관리 메뉴를 각각 열어봅니다.",
            ],
        )
        self.capture("ERP 실행 확인 후")

        self.step(
            "2. 테스트 주문 1건 등록",
            [
                "주문관리 또는 일괄등록에서 테스트 주문 1건을 등록합니다.",
                "이미 등록된 실주문을 사용할 경우 별도 주문을 만들지 않아도 됩니다.",
                "주문번호를 메모해 두세요.",
            ],
        )
        self.capture("주문 등록 후")

        self.step(
            "3. 상품매핑",
            [
                "상품매핑 화면에서 방금 주문한 상품을 찾습니다.",
                "기존 상품 연결 또는 새 상품 등록 및 연결을 실행합니다.",
                "미매핑 목록에서 사라지는지 확인합니다.",
            ],
        )
        self.capture("상품매핑 후")

        self.step(
            "4. 발주 생성 및 완료",
            [
                "발주관리에서 해당 주문상품을 확인합니다.",
                "발주를 생성하고 발주완료 상태로 변경합니다.",
                "발주 수량과 공급처가 맞는지 확인합니다.",
            ],
        )
        self.capture("발주완료 후")

        self.step(
            "5. 송장 등록",
            [
                "송장관리에서 해당 주문을 찾습니다.",
                "테스트 송장번호를 입력합니다.",
                "주문 상태가 송장등록완료로 변경되는지 확인합니다.",
            ],
        )
        self.capture("송장등록 후")

        self.step(
            "6. Dashboard 및 통계 확인",
            [
                "Dashboard 숫자가 실제 데이터와 일치하는지 확인합니다.",
                "구매통계 화면이 오류 없이 열리는지 확인합니다.",
                "완료 주문이 미처리 숫자에서 빠졌는지 확인합니다.",
            ],
        )
        self.capture("Dashboard 확인 후")

        self.step(
            "7. 백업 확인",
            [
                "백업 및 복원 화면에서 수동 백업을 1회 실행합니다.",
                "backup 폴더 또는 설정된 백업 경로에 파일이 생성되는지 확인합니다.",
            ],
        )
        self.capture("백업 확인 후")

        note = input(
            "\n테스트 중 발견한 오류나 특이사항을 입력하세요.\n"
            "없으면 Enter: "
        ).strip()
        if note:
            self.notes.append(note)

        report_path = self.write_report()
        self.print_summary(report_path)
        self.pause()

    def step(
        self,
        title: str,
        instructions: list[str],
    ) -> None:
        print("\n" + "-" * 74)
        print(title)
        print("-" * 74)

        for index, instruction in enumerate(
            instructions,
            start=1,
        ):
            print(f"  {index}. {instruction}")

        result = input(
            "\n완료했으면 Enter, 문제가 있으면 내용을 입력하세요: "
        ).strip()

        if result:
            self.notes.append(f"{title}: {result}")

    def capture(self, label: str) -> None:
        try:
            snapshot = self.read_snapshot()
            self.snapshots.append((label, snapshot))
            print(
                f"\n[스냅샷 저장] {label} "
                f"- 주문 {snapshot.counts.get('orders', 0):,}건, "
                f"주문상품 {snapshot.counts.get('order_items', 0):,}건, "
                f"발주 {snapshot.counts.get('purchase_orders', 0):,}건, "
                f"송장 {snapshot.counts.get('shipments', 0):,}건"
            )
        except Exception as error:
            self.notes.append(
                f"{label} 스냅샷 실패: {error}"
            )
            print(
                f"\n[경고] {label} 스냅샷을 저장하지 못했습니다: "
                f"{error}"
            )

    def read_snapshot(self) -> Snapshot:
        connection = sqlite3.connect(
            f"file:{DATABASE_PATH.as_posix()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row

        try:
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

            counts = {}
            for table in (
                "orders",
                "order_items",
                "products",
                "suppliers",
                "purchase_orders",
                "shipments",
            ):
                counts[table] = (
                    self.count_rows(connection, table)
                    if table in tables
                    else 0
                )

            order_states = self.group_counts(
                connection,
                "orders",
                "order_status",
                tables,
            )
            mapping_states = self.group_counts(
                connection,
                "order_items",
                "mapping_status",
                tables,
            )
            purchase_states = self.group_counts(
                connection,
                "purchase_orders",
                "purchase_status",
                tables,
            )
            shipment_states = self.group_counts(
                connection,
                "orders",
                "shipment_status",
                tables,
            )
            latest_orders = self.get_latest_orders(
                connection,
                tables,
            )

            return Snapshot(
                captured_at=datetime.now().isoformat(
                    timespec="seconds"
                ),
                counts=counts,
                order_states=order_states,
                mapping_states=mapping_states,
                purchase_states=purchase_states,
                shipment_states=shipment_states,
                latest_orders=latest_orders,
            )
        finally:
            connection.close()

    @staticmethod
    def count_rows(
        connection: sqlite3.Connection,
        table: str,
    ) -> int:
        return int(
            connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
        )

    @staticmethod
    def group_counts(
        connection: sqlite3.Connection,
        table: str,
        column: str,
        tables: set[str],
    ) -> dict[str, int]:
        if table not in tables:
            return {}

        columns = {
            row["name"]
            for row in connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

        if column not in columns:
            return {}

        rows = connection.execute(
            f"""
            SELECT
                COALESCE({column}, '') AS state,
                COUNT(*) AS count
            FROM {table}
            GROUP BY COALESCE({column}, '')
            ORDER BY count DESC
            """
        ).fetchall()

        return {
            str(row["state"] or "(빈값)"): int(row["count"])
            for row in rows
        }

    @staticmethod
    def get_latest_orders(
        connection: sqlite3.Connection,
        tables: set[str],
    ) -> list[dict[str, Any]]:
        if "orders" not in tables:
            return []

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(orders)"
            ).fetchall()
        }

        wanted = [
            column
            for column in (
                "id",
                "platform",
                "order_number",
                "order_status",
                "mapping_status",
                "purchase_status",
                "shipment_status",
                "created_at",
                "updated_at",
            )
            if column in columns
        ]

        if not wanted:
            return []

        rows = connection.execute(
            f"""
            SELECT {", ".join(wanted)}
            FROM orders
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

        return [
            {key: row[key] for key in row.keys()}
            for row in rows
        ]

    def write_report(self) -> Path:
        report_dir = self.resolve_report_directory()
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        json_path = report_dir / (
            f"workflow_test_{timestamp}.json"
        )
        text_path = report_dir / (
            f"workflow_test_{timestamp}.txt"
        )

        json_payload = {
            "project_root": str(PROJECT_ROOT),
            "database_path": str(DATABASE_PATH),
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "notes": self.notes,
            "snapshots": [
                {
                    "label": label,
                    "snapshot": asdict(snapshot),
                }
                for label, snapshot in self.snapshots
            ],
        }

        json_path.write_text(
            json.dumps(
                json_payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        lines = [
            "BisunERP v1.0 실사용 흐름 테스트 보고서",
            f"생성시각: {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"프로젝트: {PROJECT_ROOT}",
            f"DB: {DATABASE_PATH}",
            "=" * 90,
        ]

        for label, snapshot in self.snapshots:
            lines.extend(
                [
                    "",
                    f"[{label}]",
                    f"시각: {snapshot.captured_at}",
                    "건수:",
                ]
            )

            for name, count in snapshot.counts.items():
                lines.append(
                    f"  - {name}: {count:,}"
                )

            for title, states in (
                ("주문상태", snapshot.order_states),
                ("매핑상태", snapshot.mapping_states),
                ("발주상태", snapshot.purchase_states),
                ("송장상태", snapshot.shipment_states),
            ):
                lines.append(f"{title}:")
                if states:
                    for state, count in states.items():
                        lines.append(
                            f"  - {state}: {count:,}"
                        )
                else:
                    lines.append("  - 확인 가능한 컬럼 없음")

            lines.append("최근 주문:")
            if snapshot.latest_orders:
                for order in snapshot.latest_orders:
                    lines.append(
                        "  - "
                        + " | ".join(
                            f"{key}={value}"
                            for key, value in order.items()
                        )
                    )
            else:
                lines.append("  - 없음")

        lines.extend(
            [
                "",
                "=" * 90,
                "[사용자 기록]",
            ]
        )

        if self.notes:
            for note in self.notes:
                lines.append(f"- {note}")
        else:
            lines.append("- 별도 기록 없음")

        text_path.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

        return text_path

    @staticmethod
    def resolve_report_directory() -> Path:
        candidates = (
            REPORT_DIR,
            PROJECT_ROOT / "output" / "workflow_test_reports",
            PROJECT_ROOT / "workflow_test_reports",
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
            "workflow_reports_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        fallback.mkdir(
            parents=True,
            exist_ok=False,
        )
        return fallback

    def print_summary(self, report_path: Path) -> None:
        print("\n" + "=" * 74)
        print("실사용 흐름 테스트 기록 완료")
        print(f"스냅샷: {len(self.snapshots)}개")
        print(f"사용자 기록: {len(self.notes)}개")
        print(f"보고서: {report_path}")
        print("=" * 74)

        if self.notes:
            print("\n기록된 문제:")
            for note in self.notes:
                print(f"- {note}")
        else:
            print("\n기록된 문제는 없습니다.")

    @staticmethod
    def pause() -> None:
        try:
            input("\nEnter 키를 누르면 종료합니다...")
        except (EOFError, KeyboardInterrupt):
            pass


def main() -> None:
    try:
        WorkflowTester().run()
    except Exception:
        print("\n실사용 테스트 도구 실행 중 오류가 발생했습니다.")
        traceback.print_exc()
        try:
            input("\nEnter 키를 누르면 종료합니다...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    main()
