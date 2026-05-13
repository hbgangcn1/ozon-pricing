"""Ensure schema integrity guard covers every migration CHECK."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.check_schema_integrity import EXPECTED_CHECK_VALUES


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_VERSIONS = PROJECT_ROOT / "alembic" / "versions"


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _literal_arg(call: ast.Call, index: int) -> str | None:
    if len(call.args) <= index:
        return None
    arg = call.args[index]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _literal_keyword(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg != name:
            continue
        if isinstance(keyword.value, ast.Constant):
            value = keyword.value.value
            return value if isinstance(value, str) else None
    return None


def _is_upgrade_body(node: ast.AST) -> bool:
    return isinstance(node, ast.FunctionDef) and node.name == "upgrade"


def _iter_upgrade_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if _is_upgrade_body(node):
            return [item for item in ast.walk(node) if isinstance(item, ast.Call)]
    return []


def _create_table_name(call: ast.Call) -> str | None:
    args = [_literal_arg(call, index) for index in range(2)]
    if args[0] and args[1]:
        return args[1]
    return None


def _migration_check_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for path in ALEMBIC_VERSIONS.glob("*.py"):
        calls = _iter_upgrade_calls(path)
        for call in calls:
            name = _call_name(call.func)
            if name == "op.create_check_constraint":
                constraint = _literal_arg(call, 0)
                table = _create_table_name(call)
                if table and constraint:
                    keys.add((table, constraint))
        keys.update(_create_table_check_keys(calls))
    return keys


def _create_table_check_keys(calls: list[ast.Call]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for call in calls:
        if _call_name(call.func) != "op.create_table":
            continue
        table = _literal_arg(call, 0)
        for child in ast.walk(call):
            if not isinstance(child, ast.Call):
                continue
            if _call_name(child.func) != "sa.CheckConstraint":
                continue
            constraint = _literal_keyword(child, "name")
            if table and constraint:
                keys.add((table, constraint))
    return keys


def test_check_schema_integrity_covers_all_migration_checks():
    expected_keys = {
        (table, constraint)
        for table, constraints in EXPECTED_CHECK_VALUES.items()
        for constraint in constraints
    }
    missing = _migration_check_keys() - expected_keys

    assert missing == set()
