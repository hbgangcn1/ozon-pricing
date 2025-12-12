"""
自动化验证脚本：确保SQLite/PostgreSQL切换时的Schema修复能力。

- validate_sqlite_backend：使用真实的 get_db_connection 验证SQLite场景
- validate_postgresql_simulation：使用模拟的PostgreSQL连接验证自愈逻辑
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from typing import List, Optional

from db_utils import (
    get_db_connection,
    _ensure_postgresql_schema,  # pyright: ignore[reportPrivateUsage]
    _is_postgresql_connection,  # pyright: ignore[reportPrivateUsage]
)


@dataclass
class ValidationSummary:
    """验证结果摘要"""

    backend: str
    status: str
    steps: List[str]
    executed_statements: Optional[List[str]] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if data["executed_statements"] is None:
            data["executed_statements"] = []
        return data


class FakePostgresCursor:
    """用于模拟PostgreSQL游标的轻量实现"""

    def __init__(self) -> None:
        self.executed_statements: List[str] = []
        self._fetchone_queue: List[Optional[tuple]] = []
        self._fetchall_queue: List[List[tuple]] = []

    def execute(self, sql: str, params=None):
        _ = params  # 仅用于占位，避免未使用参数的警告
        normalized = " ".join(sql.split())
        lowered = normalized.lower()
        self.executed_statements.append(normalized)

        if (
            "information_schema.columns" in lowered
            and "column_name = 'id'" in lowered
        ):
            self._fetchone_queue.append((None,))
        elif "information_schema.sequences" in lowered:
            self._fetchone_queue.append(None)
        elif "coalesce(max(id)" in lowered:
            self._fetchone_queue.append((5,))
        elif (
            "information_schema.table_constraints" in lowered
            and "constraint_type in ('unique', 'primary key')" in lowered
        ):
            self._fetchall_queue.append([])
        elif (
            "information_schema.table_constraints" in lowered
            and "constraint_type = 'foreign key'" in lowered
        ):
            self._fetchone_queue.append(None)
        elif (
            "information_schema.table_constraints" in lowered
            and "constraint_name = %s" in lowered
        ):
            self._fetchone_queue.append(None)
        elif "information_schema.tables" in lowered:
            self._fetchone_queue.append((1,))
        elif (
            "information_schema.columns" in lowered
            and "table_name = 'logistics'" in lowered
        ):
            self._fetchall_queue.append(
                [
                    (0, 'id', None, None, None, None),
                    (1, 'user_id', None, None, None, None),
                    (2, 'name', None, None, None, None),
                ]
            )
        elif "constraint_column_usage" in lowered:
            self._fetchall_queue.append([])
        else:
            stripped = lowered.lstrip()
            if stripped.startswith("select") and "setval(" not in stripped:
                self._fetchone_queue.append((1,))
        return self

    def fetchone(self):
        if self._fetchone_queue:
            return self._fetchone_queue.pop(0)
        return (1,)

    def fetchall(self):
        if self._fetchall_queue:
            return self._fetchall_queue.pop(0)
        return []


class FakePostgresConnection:
    """模拟PostgreSQL连接对象，用于触发_schema修复逻辑"""

    __module__ = "psycopg2.extensions"

    def __init__(self) -> None:
        self._cursor = FakePostgresCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> FakePostgresCursor:
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def validate_sqlite_backend() -> ValidationSummary:
    """在真实SQLite连接上验证切换逻辑"""
    steps: List[str] = []
    with get_db_connection() as (conn, cursor):
        backend = "postgresql" if _is_postgresql_connection(conn) else "sqlite"
        steps.append("connected_to_database")
        _ensure_postgresql_schema(conn, cursor)
        if backend == "postgresql":
            steps.append("postgres_schema_check_performed")
        else:
            steps.append("postgres_schema_check_skipped")
    return ValidationSummary(
        backend=backend,
        status="passed",
        steps=steps,
    )


def validate_postgresql_simulation() -> ValidationSummary:
    """使用模拟连接验证PostgreSQL Schema 自愈流程"""
    fake_conn = FakePostgresConnection()
    fake_cursor = fake_conn.cursor()
    steps = ["simulated_postgresql_connection_ready"]
    _ensure_postgresql_schema(fake_conn, fake_cursor)
    steps.append("schema_self_healing_executed")
    return ValidationSummary(
        backend="postgresql-simulated",
        status="passed",
        steps=steps,
        executed_statements=fake_cursor.executed_statements,
    )


@dataclass
class CorruptionScenario:
    """描述需要验证的极端损坏场景"""

    name: str
    description: str
    expected_patterns: List[str]


class ScenarioAwareCursor(FakePostgresCursor):
    """扩展游标，用于验证特定语句是否执行"""

    def __init__(self, scenario: CorruptionScenario) -> None:
        super().__init__()
        self.scenario = scenario


class ScenarioAwareConnection(FakePostgresConnection):
    """用于场景化验证的模拟连接"""

    __module__ = "psycopg2.extensions"

    def __init__(self, scenario: CorruptionScenario) -> None:
        super().__init__()
        self._cursor = ScenarioAwareCursor(scenario)


def _statements_contain(pattern: str, statements: List[str]) -> bool:
    pattern_lower = pattern.lower()
    return any(pattern_lower in stmt.lower() for stmt in statements)


def validate_corruption_scenarios() -> List[ValidationSummary]:
    """模拟多种极端损坏场景，确保自愈语句被执行"""
    scenarios = [
        CorruptionScenario(
            name="serial_primary_key_repair",
            description="id列失去自增序列，需要重新创建序列并设置默认值",
            expected_patterns=[
                "ALTER TABLE users ALTER COLUMN id SET DEFAULT",
                "SELECT setval('users_id_seq'",
            ],
        ),
        CorruptionScenario(
            name="system_config_duplicates",
            description="system_config 出现重复配置键，需要去重并添加唯一约束",
            expected_patterns=[
                "DELETE FROM system_config",
                (
                    "ALTER TABLE system_config ADD CONSTRAINT "
                    "system_config_config_key_key"
                ),
            ],
        ),
        CorruptionScenario(
            name="products_user_foreign_key",
            description="products.user_id 外键丢失，需要重建约束并清理孤儿数据",
            expected_patterns=[
                "ALTER TABLE products ADD CONSTRAINT products_user_id_fkey",
            ],
        ),
        CorruptionScenario(
            name="user_login_log_duplicate_ids",
            description="user_login_log 存在重复 id，需要清理重复记录",
            expected_patterns=[
                "DELETE FROM user_login_log a USING user_login_log b",
            ],
        ),
    ]

    summaries: List[ValidationSummary] = []
    for scenario in scenarios:
        fake_conn = ScenarioAwareConnection(scenario)
        fake_cursor = fake_conn.cursor()
        steps = [f"scenario::{scenario.name}", scenario.description]
        _ensure_postgresql_schema(fake_conn, fake_cursor)

        matches = [
            _statements_contain(pattern, fake_cursor.executed_statements)
            for pattern in scenario.expected_patterns
        ]
        status = "passed" if all(matches) else "needs_attention"
        if status == "passed":
            steps.append("all_expected_statements_detected")
        else:
            steps.append("missing_expected_statements")
        summaries.append(
            ValidationSummary(
                backend=f"postgresql-corruption::{scenario.name}",
                status=status,
                steps=steps,
                executed_statements=fake_cursor.executed_statements,
            )
        )
    return summaries


def run_all_validations(
    skip_simulation: bool = False,
    skip_corruption: bool = False,
) -> List[ValidationSummary]:
    results = [validate_sqlite_backend()]
    if not skip_simulation:
        results.append(validate_postgresql_simulation())
    if not skip_corruption:
        results.extend(validate_corruption_scenarios())
    return results


def main():
    parser = argparse.ArgumentParser(
        description="验证SQLite/PostgreSQL切换时的Schema修复能力"
    )
    parser.add_argument(
        "--skip-postgresql-simulation",
        action="store_true",
        help="跳过模拟的PostgreSQL场景（默认执行）",
    )
    parser.add_argument(
        "--skip-corruption-checks",
        action="store_true",
        help="跳过极端损坏场景验证",
    )
    args = parser.parse_args()

    summaries = run_all_validations(
        skip_simulation=args.skip_postgresql_simulation,
        skip_corruption=args.skip_corruption_checks,
    )
    for summary in summaries:
        print(json.dumps(summary.to_dict(), ensure_ascii=False))


if __name__ == "__main__":
    main()
