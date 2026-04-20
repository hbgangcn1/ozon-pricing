import logging
from decimal import Decimal
from typing import Any, Optional, cast

from sqlalchemy import delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.logistics import Logistics
from models.product import Product

logger = logging.getLogger(__name__)

_ALLOWED_PRODUCT_FIELDS = {
    "user_id",
    "name",
    "russian_name",
    "category",
    "model",
    "unit_price",
    "weight_g",
    "length_cm",
    "width_cm",
    "height_cm",
    "is_cylinder",
    "cylinder_diameter",
    "cylinder_length",
    "has_battery",
    "battery_capacity_wh",
    "battery_capacity_mah",
    "battery_voltage",
    "has_msds",
    "has_liquid",
    "labeling_fee",
    "shipping_fee",
    "promotion_cost_rate",
    "target_profit_margin",
    "commission_rate",
    "commission_category_id",
    "withdrawal_fee_rate",
    "payment_processing_fee",
    "return_rate",
    "vat_rate",
    "is_test_data",
}

_BOOL_FIELDS = {"is_cylinder", "has_battery", "has_msds", "has_liquid"}
_INT_DEFAULT_FIELDS = {
    "weight_g",
    "length_cm",
    "width_cm",
    "height_cm",
    "battery_capacity_mah",
}
_DECIMAL_DEFAULT_FIELDS = {
    "unit_price",
    "labeling_fee",
    "shipping_fee",
    "promotion_cost_rate",
    "target_profit_margin",
    "commission_rate",
    "withdrawal_fee_rate",
    "payment_processing_fee",
    "return_rate",
    "vat_rate",
}
_FLOAT_DEFAULT_FIELDS = {
    "cylinder_diameter",
    "cylinder_length",
    "battery_capacity_wh",
    "battery_voltage",
}


def _product_to_dict(p: Product) -> dict:
    data = {}
    for column in Product.__table__.columns:
        value = getattr(p, column.name)
        if column.name in _BOOL_FIELDS:
            data[column.name] = bool(value)
            continue
        if value is None and column.name in _INT_DEFAULT_FIELDS:
            data[column.name] = 0
            continue
        if value is None and column.name in _DECIMAL_DEFAULT_FIELDS:
            data[column.name] = Decimal("0")
            continue
        if value is None and column.name in _FLOAT_DEFAULT_FIELDS:
            data[column.name] = 0.0
            continue
        data[column.name] = value
    return data


async def add_product(
    session: AsyncSession,
    user_id: int,
    data: dict,
) -> Optional[int]:
    clean = {}
    for field in _ALLOWED_PRODUCT_FIELDS - {"user_id"}:
        if field in data:
            val = data[field]
            if field in _BOOL_FIELDS:
                val = 1 if val else 0
            clean[field] = val
    product = Product(user_id=user_id, **clean)
    session.add(product)
    await session.flush()
    return product.id


async def get_all_products_for_user(
    session: AsyncSession,
    user_id: int,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list:
    stmt = select(Product).where(Product.user_id == user_id).order_by(Product.id.desc())
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_product_to_dict(p) for p in rows]


async def get_product_by_id(
    session: AsyncSession,
    product_id: int,
    user_id: int,
) -> Optional[dict]:
    if user_id is None:
        raise ValueError("user_id参数是必需的，以确保数据安全隔离")
    stmt = select(Product).where(
        Product.id == product_id,
        Product.user_id == user_id,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _product_to_dict(row) if row else None


async def get_product_by_name(
    session: AsyncSession,
    user_id: int,
    name: str,
) -> Optional[dict]:
    stmt = select(Product).where(
        Product.user_id == user_id,
        Product.name == name,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _product_to_dict(row) if row else None


async def delete_product(
    session: AsyncSession,
    product_id: int,
    user_id: int,
) -> bool:
    stmt = select(Product).where(
        Product.id == product_id,
        Product.user_id == user_id,
    )
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        return False
    await session.delete(product)
    return True


async def batch_delete_products(
    session: AsyncSession,
    ids: list,
    user_id: int,
) -> int:
    if not ids:
        return 0
    stmt = sa_delete(Product).where(
        Product.id.in_(ids),
        Product.user_id == user_id,
    )
    result = await session.execute(stmt)
    rowcount = cast(Any, result).rowcount
    return rowcount or 0


async def update_product(
    session: AsyncSession,
    product_id: int,
    user_id: int,
    data: dict,
) -> bool:
    if not data:
        return False
    stmt = select(Product).where(
        Product.id == product_id,
        Product.user_id == user_id,
    )
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        return False
    allowed = _ALLOWED_PRODUCT_FIELDS - {"user_id"}
    for key, value in data.items():
        if key in allowed and hasattr(product, key):
            setattr(product, key, value)
    return True


async def batch_update_pricing_params(
    session: AsyncSession,
    user_id: int,
    params: dict,
) -> int:
    if not params:
        return 0
    allowed_pricing_fields = {
        "promotion_cost_rate",
        "target_profit_margin",
        "commission_rate",
        "withdrawal_fee_rate",
        "payment_processing_fee",
        "return_rate",
        "vat_rate",
        "unit_price",
        "labeling_fee",
        "shipping_fee",
    }
    clean = {k: v for k, v in params.items() if k in allowed_pricing_fields}
    if not clean:
        return 0
    stmt = update(Product).where(Product.user_id == user_id).values(**clean)
    result = await session.execute(stmt)
    rowcount = cast(Any, result).rowcount
    return rowcount or 0


async def cleanup_test_products(
    session: AsyncSession,
    user_id: Optional[int] = None,
) -> int:
    try:
        stmt = sa_delete(Product).where(Product.is_test_data == 1)
        if user_id is not None:
            stmt = sa_delete(Product).where(
                Product.is_test_data == 1,
                Product.user_id == user_id,
            )
        result = await session.execute(stmt)
        rowcount = cast(Any, result).rowcount
        return rowcount or 0
    except Exception as e:
        logger.warning("清理测试产品时出错: %s", e)
        return 0


def _calculate_group_averages(logistics_list):
    if not logistics_list:
        return 0, 0, 0
    valid = [
        log for log in logistics_list if log["min_days"] > 0 and log["max_days"] > 0
    ]
    if not valid:
        return 0, 0, 0
    avg_fastest = sum(log["min_days"] for log in valid) / len(valid)
    avg_slowest = sum(log["max_days"] for log in valid) / len(valid)
    avg_times = [(log["min_days"] + log["max_days"]) / 2 for log in valid]
    avg_overall = sum(avg_times) / len(avg_times)
    return avg_fastest, avg_slowest, avg_overall


def _assign_priority_group(log, avg_fastest, avg_slowest, avg_overall):
    min_days = log["min_days"]
    max_days = log["max_days"]
    if min_days == 0 and max_days == 0:
        return "E"
    avg_time = (min_days + max_days) / 2
    count_below = 0
    if min_days < avg_fastest:
        count_below += 1
    if max_days < avg_slowest:
        count_below += 1
    if avg_time < avg_overall:
        count_below += 1
    if count_below == 3:
        return "A"
    elif count_below == 2:
        return "B"
    elif count_below == 1:
        return "C"
    else:
        return "D"


async def calculate_and_update_priority_groups(
    session: AsyncSession,
    user_id: int,
) -> None:
    stmt = select(
        Logistics.id,
        Logistics.type,
        Logistics.min_days,
        Logistics.max_days,
    ).where(Logistics.user_id == user_id)
    result = await session.execute(stmt)
    rows = result.all()
    logistics = [
        {"id": r[0], "type": r[1], "min_days": r[2], "max_days": r[3]} for r in rows
    ]
    land = [log for log in logistics if log["type"] == "land"]
    air = [log for log in logistics if log["type"] == "air"]
    land_avgs = _calculate_group_averages(land)
    air_avgs = _calculate_group_averages(air)
    for log in land:
        group = _assign_priority_group(log, *land_avgs)
        await session.execute(
            update(Logistics)
            .where(Logistics.id == log["id"])
            .values(priority_group=group)
        )
    for log in air:
        group = _assign_priority_group(log, *air_avgs)
        await session.execute(
            update(Logistics)
            .where(Logistics.id == log["id"])
            .values(priority_group=group)
        )
