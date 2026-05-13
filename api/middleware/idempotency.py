import json
import time
from typing import Any

from fastapi import Header, HTTPException
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.idempotency import ApiIdempotencyKey

TTL_SECONDS = 24 * 60 * 60


async def get_cached_response(
    session: AsyncSession,
    scope: str,
    key: str | None,
) -> tuple[int, Any] | None:
    if not key:
        return None
    now = int(time.time())
    await session.execute(
        sa_delete(ApiIdempotencyKey).where(ApiIdempotencyKey.expires_at <= now)
    )
    row = await session.scalar(
        select(ApiIdempotencyKey).where(
            ApiIdempotencyKey.scope == scope,
            ApiIdempotencyKey.key == key,
            ApiIdempotencyKey.expires_at > now,
        )
    )
    if row is None:
        return None
    return row.status_code, json.loads(row.response_body)


async def store_response(
    session: AsyncSession,
    scope: str,
    key: str | None,
    status_code: int,
    body: Any,
) -> None:
    if not key:
        return
    now = int(time.time())
    row = ApiIdempotencyKey(
        scope=scope,
        key=key,
        status_code=status_code,
        response_body=json.dumps(body, default=str, ensure_ascii=False),
        created_at=now,
        expires_at=now + TTL_SECONDS,
    )
    session.add(row)
    await session.flush()


def idempotency_key_header(
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> str | None:
    if idempotency_key is not None and len(idempotency_key) > 255:
        raise HTTPException(status_code=400, detail="Idempotency-Key too long")
    return idempotency_key
