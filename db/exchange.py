import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.config import ExchangeRate

logger = logging.getLogger(__name__)


async def get_exchange_rate_fallback(
    session: AsyncSession,
    currency_pair: str,
) -> Optional[float]:
    try:
        stmt = select(ExchangeRate.rate).where(
            ExchangeRate.currency_pair == currency_pair,
        )
        result = await session.execute(stmt)
        value = result.scalar_one_or_none()
        return float(value) if value is not None else None
    except Exception:
        logger.debug("从数据库获取汇率失败", exc_info=True)
        return None


async def update_exchange_rate_fallback(
    session: AsyncSession,
    currency_pair: str,
    rate: float,
    source: str = "",
) -> None:
    try:
        stmt = select(ExchangeRate).where(
            ExchangeRate.currency_pair == currency_pair,
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if record:
            record.rate = rate
            record.last_updated = now
            record.source = source
        else:
            record = ExchangeRate(
                currency_pair=currency_pair,
                rate=rate,
                last_updated=now,
                source=source,
            )
            session.add(record)
    except Exception:
        logger.debug("更新汇率 fallback 失败", exc_info=True)
