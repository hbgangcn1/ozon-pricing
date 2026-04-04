import logging

from db._proxy import _db

logger = logging.getLogger(__name__)


def get_exchange_rate_fallback(currency_pair: str):
    """从数据库读取汇率fallback值，读不到时返回None"""
    try:
        with _db.get_db_connection() as (conn, c):
            sql_raw = "SELECT rate FROM exchange_rates WHERE currency_pair = %s"
            sql = _db._safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (currency_pair,))
            row = c.fetchone()
            return float(row[0]) if row else None
    except Exception:
        logger.debug("从数据库获取汇率失败，返回None", exc_info=True)
        return None


def update_exchange_rate_fallback(currency_pair: str, rate: float, source: str = ""):
    """成功获取外部API汇率后，更新数据库中的fallback值"""
    try:
        with _db.get_db_connection() as (conn, c):
            sql_raw = (
                "INSERT INTO exchange_rates"
                " (currency_pair, rate, last_updated, source)"
                " VALUES (%s, %s, NOW(), %s)"
                " ON CONFLICT (currency_pair)"
                " DO UPDATE SET rate = EXCLUDED.rate,"
                " last_updated = EXCLUDED.last_updated,"
                " source = EXCLUDED.source"
            )
            sql = _db._safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (currency_pair, rate, source))
            conn.commit()
    except Exception:
        logger.debug("更新汇率fallback到数据库失败", exc_info=True)
