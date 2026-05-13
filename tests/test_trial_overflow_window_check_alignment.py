"""Guard trial_overflow_window CHECK constraint alignment."""

from __future__ import annotations

import ast
from pathlib import Path

from sqlalchemy import CheckConstraint, Table, text

from models.trial_overflow_window import TrialOverflowWindow


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_PATH = (
    PROJECT_ROOT
    / "alembic"
    / "versions"
    / "b7e2f1a4c5d8_add_pro_trial_overflow.py"
)
TABLE_NAME = "trial_overflow_window"
CONSTRAINT_NAME = "ck_trial_overflow_window_close_reason"


def _literal_call_args(call: ast.Call) -> list[object]:
    args = []
    for arg in call.args:
        if isinstance(arg, ast.Constant):
            args.append(arg.value)
    return args


def _literal_keyword(call: ast.Call, name: str) -> object | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _migration_check_constraint() -> tuple[str, str]:
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node.func) != "sa.CheckConstraint":
            continue
        args = _literal_call_args(node)
        name = _literal_keyword(node, "name")
        if name == CONSTRAINT_NAME and args:
            return str(args[0]), str(name)
    raise AssertionError(f"{CONSTRAINT_NAME} not found in {MIGRATION_PATH}")


def _model_check_constraint() -> tuple[str, str]:
    table = TrialOverflowWindow.__table__
    assert isinstance(table, Table)
    constraints = [
        item
        for item in table.constraints
        if isinstance(item, CheckConstraint)
        and item.name == CONSTRAINT_NAME
    ]
    assert len(constraints) == 1
    constraint = constraints[0]
    return str(constraint.sqltext), str(constraint.name)


def test_model_check_constraint_matches_migration_ddl():
    assert _model_check_constraint() == _migration_check_constraint()


async def test_postgresql_schema_check_constraint_matches_model(db_session):
    model_expr, model_name = _model_check_constraint()
    result = await db_session.execute(
        text(
            "SELECT pg_get_constraintdef(c.oid) "
            "FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            "WHERE n.nspname = current_schema() "
            "AND t.relname = :table AND c.conname = :name"
        ),
        {"table": TABLE_NAME, "name": model_name},
    )
    actual_def = result.scalar_one_or_none()

    assert actual_def is not None
    assert "close_reason" in actual_def
    for value in ("''", "expired", "upgraded", "reselected"):
        assert value in actual_def
    assert model_expr == _migration_check_constraint()[0]
