from pathlib import Path

import scripts.check_schema_integrity as schema


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        text = " ".join(query.split()).lower()
        if "pg_get_constraintdef" in text:
            key = params if params is not None else (None, None)
            self.rows = [(self.conn.checks.get(key),)] if key in self.conn.checks else []
        elif "information_schema.columns" in text:
            table = params[0] if params is not None else ""
            self.rows = [(col,) for col in self.conn.not_null.get(table, set())]
        elif "foreign_table_name" in text:
            self.rows = list(self.conn.foreign_keys)
        elif "from pg_indexes" in text:
            table = params[0] if params is not None else ""
            self.rows = [(idx,) for idx in self.conn.indexes.get(table, set())]
        else:
            self.rows = []

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, checks, not_null, foreign_keys, indexes):
        self.checks = checks
        self.not_null = not_null
        self.foreign_keys = foreign_keys
        self.indexes = indexes

    def cursor(self):
        return _Cursor(self)


def _happy_conn(monkeypatch):
    checks = {
        ("logistics", "logistics_volume_mode_check"): (
            "CHECK volume_mode IN ('none','max_actual_vs_volume','longest_side','sum_of_sides')"
        ),
        ("trial_overflow_window", "ck_trial_overflow_window_close_reason"): (
            "CHECK close_reason IN ('', 'expired', 'upgraded', 'reselected')"
        ),
    }
    not_null = {table: set(cols) for table, cols in schema.EXPECTED_NOT_NULL.items()}
    foreign_keys = set(schema.EXPECTED_FOREIGN_KEYS)
    indexes = {table: set(items) for table, items in schema.EXPECTED_INDEXES.items()}
    monkeypatch.setattr(schema, "expected_checks", lambda: schema.EXPECTED_CHECK_VALUES)
    return _Conn(checks, not_null, foreign_keys, indexes)


def test_scan_alembic_checks_extracts_create_and_table_constraints(tmp_path):
    version = tmp_path / "v.py"
    version.write_text(
        "from alembic import op\nimport sqlalchemy as sa\n"
        "op.create_check_constraint('ck_a', 'table_a', \"kind IN ('x', 'y')\")\n"
        "op.create_table('table_b', sa.Column('id', sa.Integer()), "
        "sa.CheckConstraint(\"reason IN ('', 'done')\", name='ck_b'))\n",
        encoding="utf-8",
    )

    found = schema.scan_alembic_checks(Path(tmp_path))

    assert found["table_a"]["ck_a"] == {"x", "y"}
    assert found["table_b"]["ck_b"] == {"''", "done"}


def test_run_checks_happy_path(monkeypatch):
    failures = schema.run_checks(_happy_conn(monkeypatch))
    assert failures == []


def test_run_checks_reports_check_drift(monkeypatch):
    conn = _happy_conn(monkeypatch)
    conn.checks[("logistics", "logistics_volume_mode_check")] = "CHECK volume_mode IN ('none')"

    failures = schema.run_checks(conn)

    assert any("missing values" in failure for failure in failures)


def test_run_checks_reports_missing_not_null(monkeypatch):
    conn = _happy_conn(monkeypatch)
    conn.not_null["payment_orders"].remove("amount")

    failures = schema.run_checks(conn)

    assert any("payment_orders" in failure and "amount" in failure for failure in failures)


def test_run_checks_reports_missing_foreign_key(monkeypatch):
    conn = _happy_conn(monkeypatch)
    conn.foreign_keys.remove(("password_reset_tokens", "user_id", "users", "id"))

    failures = schema.run_checks(conn)

    assert any("password_reset_tokens.user_id" in failure for failure in failures)


def test_run_checks_reports_missing_index(monkeypatch):
    conn = _happy_conn(monkeypatch)
    conn.indexes["logistics"].remove("ix_logistics_user_id_id_desc")

    failures = schema.run_checks(conn)

    assert any("ix_logistics_user_id_id_desc" in failure for failure in failures)


def test_expected_not_null_tables_exist_in_orm_metadata():
    import importlib
    import pkgutil

    import models

    for module_info in pkgutil.iter_modules(models.__path__):
        importlib.import_module(f"models.{module_info.name}")

    orm_table_names = set(models.Base.metadata.tables.keys())

    phantom = sorted(set(schema.EXPECTED_NOT_NULL.keys()) - orm_table_names)
    assert phantom == [], (
        f"EXPECTED_NOT_NULL contains phantom tables not in SQLAlchemy metadata: "
        f"{phantom}. Add the ORM model + alembic migration first, or remove the entry."
    )


def test_expected_indexes_tables_exist_in_orm_metadata():
    import importlib
    import pkgutil

    import models

    for module_info in pkgutil.iter_modules(models.__path__):
        importlib.import_module(f"models.{module_info.name}")

    orm_table_names = set(models.Base.metadata.tables.keys())

    phantom = sorted(set(schema.EXPECTED_INDEXES.keys()) - orm_table_names)
    assert phantom == [], (
        f"EXPECTED_INDEXES contains phantom tables not in SQLAlchemy metadata: {phantom}."
    )
