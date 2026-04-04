import logging
from typing import Optional

from db._proxy import _db

logger = logging.getLogger(__name__)


def get_system_config(
    config_key: str, default_value: Optional[str] = None
) -> Optional[str]:
    with _db.get_db_connection() as (_, c):
        if c is None:
            return default_value
        from db_adapter import adapt_sql as _adapt_sql

        sql = _adapt_sql("SELECT config_value FROM system_config WHERE config_key = ?")
        c.execute(sql, (config_key,))
        result = c.fetchone()
        return result[0] if result else default_value


def set_system_config(
    config_key: str, config_value: str, description: Optional[str] = None
) -> bool:
    with _db.get_db_connection() as (conn, c):
        try:
            sql_raw = """
                INSERT INTO system_config
                (config_key, config_value, description, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (config_key) DO UPDATE SET
                config_value = EXCLUDED.config_value,
                description = EXCLUDED.description,
                updated_at = CURRENT_TIMESTAMP
            """
            sql = _db._safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (config_key, config_value, description))
            conn.commit()
            return True
        except Exception as e:
            logger.warning("设置系统配置失败: %s", e)
            return False


def is_registration_open() -> bool:
    config_value = _db.get_system_config("open_registration", "false")
    return config_value is not None and config_value.lower() == "true"
