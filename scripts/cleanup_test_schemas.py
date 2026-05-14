import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from urllib.parse import quote_plus


def _make_url():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from db_config import POSTGRES_CONFIG

    pw = quote_plus(POSTGRES_CONFIG["password"])
    return (
        f"postgresql+asyncpg://{POSTGRES_CONFIG['user']}:{pw}"
        f"@{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}"
        f"/{POSTGRES_CONFIG['database']}"
    )


async def cleanup():
    url = _make_url()
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'test_%'"
            )
        )
        schemas = [row[0] for row in result.fetchall()]
        print(f"Found schemas: {schemas}")
        for schema in schemas:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            print(f"Dropped {schema}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(cleanup())
