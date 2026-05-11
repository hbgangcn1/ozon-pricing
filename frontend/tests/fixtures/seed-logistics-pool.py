import asyncio
import sys
import time
from pathlib import Path

from sqlalchemy import delete, select

# pyright: reportMissingImports=false
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import AsyncSessionLocal, engine  # noqa: E402
from db.logistics_pool import insert_row  # noqa: E402
from db.logistics_crud import create_logistics  # noqa: E402
from models.logistics import Logistics  # noqa: E402
from models.logistics_pool import LogisticsPool  # noqa: E402
from models.user import User  # noqa: E402


SEED_NAMES = [
    "E2E_BatchPool_Land",
    "E2E_BatchPool_Air",
    "E2E_BatchPool_Sea",
]
SOURCE_FILE = "e2e-batch-select-seed"
LOGISTICS_NAMES = [
    "BatchTest_E2E_Land_0",
    "BatchTest_E2E_Land_1",
    "BatchTest_E2E_Land_2",
]


def _entry(index: int, name: str, delivery_type: str) -> dict:
    return {
        "name": name,
        "type": delivery_type,
        "min_days": 3 + index,
        "max_days": 7 + index,
        "price_limit": 0,
        "price_min": 0,
        "base_fee": 10 + index,
        "min_weight": 0,
        "max_weight": 2000 + index * 1000,
        "max_sum_of_sides": 300,
        "max_longest_side": 120,
        "allow_battery": 0,
        "allow_liquid": 0,
        "fee_mode": "base_plus_continue",
        "first_fee": 10 + index,
        "first_weight_g": 500,
        "continue_fee": 2 + index,
        "continue_unit": "100",
        "volume_mode": "none",
        "volume_coefficient": 5000,
        "delivery_method": delivery_type,
        "priority_group": chr(ord("A") + index),
        "fulfillment_type": "rfbs",
        "destination": "RU",
        "source_file": SOURCE_FILE,
        "imported_at": int(time.time()),
        "is_active": 1,
    }


async def cleanup() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(LogisticsPool).where(LogisticsPool.name.in_(SEED_NAMES))
        )
        await session.execute(
            delete(Logistics).where(Logistics.name.in_(LOGISTICS_NAMES))
        )
        await session.commit()


async def seed() -> list[int]:
    await cleanup()
    async with AsyncSessionLocal() as session:
        ids = []
        for index, (name, delivery_type) in enumerate(
            zip(SEED_NAMES, ["land", "air", "sea"])
        ):
            ids.append(await insert_row(session, _entry(index, name, delivery_type)))
        await session.commit()
        return ids


async def seed_logistics(username: str) -> list[int]:
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.username == username))
        if user is None or user.id is None:
            raise RuntimeError(f"user not found: {username}")
        await session.execute(
            delete(Logistics).where(
                Logistics.user_id == user.id,
                Logistics.name.in_(LOGISTICS_NAMES),
            )
        )
        ids = []
        for index, name in enumerate(LOGISTICS_NAMES):
            ids.append(await create_logistics(session, user.id, _entry(index, name, "land")))
        await session.commit()
        return ids


async def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "seed"
    try:
        if command == "seed":
            ids = await seed()
            print(",".join(str(item_id) for item_id in ids))
        elif command == "seed-logistics":
            username = sys.argv[2] if len(sys.argv) > 2 else "admin"
            ids = await seed_logistics(username)
            print(",".join(str(item_id) for item_id in ids))
        elif command == "cleanup":
            await cleanup()
            print("cleaned")
        else:
            print("usage: seed-logistics-pool.py [seed|cleanup]", file=sys.stderr)
            return 2
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
