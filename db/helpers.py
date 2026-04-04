import logging
import os
from datetime import datetime
from typing import Any, Optional

from psycopg2 import sql as psql

from db._proxy import _db

logger = logging.getLogger(__name__)

try:
    from db_adapter import adapt_sql, get_placeholder
except ImportError:

    def adapt_sql(sql: str) -> str:
        return sql

    def get_placeholder() -> str:
        return "%s"


try:
    from .password_utils import validate_password_strength
except ImportError:
    from password_utils import validate_password_strength


def _get_db_exceptions():
    import psycopg2

    return psycopg2.Error, OSError, ValueError


try:
    import psycopg2  # pyright: ignore[reportUnusedImport]
except ImportError:
    psycopg2 = None  # type: ignore

DB_EXCEPTIONS = _get_db_exceptions()


class _FakeSessionState:
    _instance = None
    _user = None

    def __init__(self):
        self._data = {}

    def __contains__(self, key):
        return key in self._data or key == "user"

    def __getitem__(self, key):
        if key == "user":
            return self._user
        return self._data.get(key)

    def __getattr__(self, key):
        if key == "user":
            return self._user
        raise AttributeError(key)

    @classmethod
    def set_user(cls, user):
        cls._user = user


_st = _FakeSessionState()


def _is_postgresql_connection(conn):
    if conn is None:
        return False

    try:
        import psycopg2

        if isinstance(conn, psycopg2.extensions.connection):
            return True
    except (ImportError, AttributeError):
        pass

    conn_module = type(conn).__module__
    if "psycopg2" in conn_module or "postgresql" in conn_module.lower():
        return True

    conn_class_name = type(conn).__name__.lower()
    if "postgres" in conn_class_name or "psycopg" in conn_class_name:
        return True

    return True


def _ensure_serial_columns(conn, cursor, tables=None):
    if not _db._is_postgresql_connection(conn):
        return
    if tables is None:
        cursor.execute(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND column_name = 'id' AND data_type = 'integer' "
            "AND column_default IS NULL"
        )
        tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        try:
            cursor.execute(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = %s AND column_name = 'id'",
                (table,),
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                continue
            seq_name = f"{table}_id_seq"
            seq_name_id = psql.Identifier(seq_name)
            table_id = psql.Identifier(table)
            cursor.execute(
                psql.SQL("CREATE SEQUENCE IF NOT EXISTS {}").format(seq_name_id)
            )
            cursor.execute(
                psql.SQL(
                    "ALTER TABLE {} ALTER COLUMN id SET DEFAULT nextval({}::regclass)"
                ).format(table_id, psql.Literal(seq_name))
            )
            cursor.execute(
                psql.SQL("ALTER SEQUENCE {} OWNED BY {}.id").format(
                    seq_name_id, table_id
                )
            )
            cursor.execute(
                psql.SQL(
                    "SELECT setval({}, COALESCE((SELECT MAX(id) FROM {}), 0) + 1, false)"
                ).format(psql.Literal(seq_name), table_id)
            )
            conn.commit()
        except DB_EXCEPTIONS:
            conn.rollback()


def _subscription_expires_to_datetime(
    raw_value: Optional[Any],
) -> Optional[datetime]:
    if raw_value in (None, "", 0):
        return None

    try:
        if isinstance(raw_value, (int, float)):
            return datetime.fromtimestamp(int(raw_value))

        cleaned = str(raw_value).strip()
        if cleaned == "":
            return None
        if cleaned.isdigit():
            return datetime.fromtimestamp(int(cleaned))
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError, OSError):
        return None


def _serialize_subscription_expires(value: Optional[Any]) -> Optional[int]:
    if value in (None, "", 0):
        return None

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, datetime):
        return int(value.timestamp())

    cleaned = str(value).strip()
    if cleaned == "":
        return None
    try:
        return int(datetime.fromisoformat(cleaned).timestamp())
    except ValueError:
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None


_TIMESTAMP_NUMERIC_PATTERN = r"^\d+(\.\d+)?$"
_TIMESTAMP_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_TIMESTAMP_FULL_PATTERN = r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$"
_TIMESTAMP_SHORT_PATTERN = r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}$"


def _build_safe_timestamp_expr(column: str) -> str:
    return f"""
        COALESCE(
            CASE
                WHEN {column} IS NULL THEN NULL
                WHEN TRIM({column}::text) = '' THEN NULL
                WHEN TRIM({column}::text) ~ '{_TIMESTAMP_NUMERIC_PATTERN}'
                    THEN to_timestamp(TRIM({column}::text)::double precision)
                WHEN TRIM({column}::text) ~ '{_TIMESTAMP_DATE_PATTERN}'
                    THEN to_timestamp(TRIM({column}::text), 'YYYY-MM-DD')
                WHEN TRIM({column}::text) ~ '{_TIMESTAMP_FULL_PATTERN}'
                    THEN to_timestamp(
                        REPLACE(TRIM({column}::text), 'T', ' '),
                        'YYYY-MM-DD HH24:MI:SS'
                    )
                WHEN TRIM({column}::text) ~ '{_TIMESTAMP_SHORT_PATTERN}'
                    THEN to_timestamp(
                        REPLACE(TRIM({column}::text), 'T', ' '),
                        'YYYY-MM-DD HH24:MI'
                    )
                ELSE NULL
            END,
            to_timestamp(0)
        )
    """


def _safe_execute_fetchone(cursor, sql, params=None, conn=None) -> Any:
    try:
        if os.getenv("ENABLE_SQL_INJECTION_DETECTION", "false").lower() == "true":
            from sql_injection_protection import detect_sql_injection

            is_safe, warning = detect_sql_injection(sql, params)
            if not is_safe:
                _logger = logging.getLogger(__name__)
                _logger.warning("SQL注入检测警告: %s", warning)
                _logger.warning("SQL语句: %s...", sql[:200])
    except (ImportError, Exception):
        pass

    if conn is not None:
        sql = _db._safe_adapt_sql(sql, conn)

    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)
    return cursor.fetchone()


def _safe_adapt_sql(sql: str, conn) -> str:
    return adapt_sql(sql)


def _get_table_columns(cursor, table_name: str) -> list:
    sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
    """
    cursor.execute(sql, (table_name,))
    return [row[0] for row in cursor.fetchall()]
