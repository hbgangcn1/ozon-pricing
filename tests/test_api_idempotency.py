import pytest
from sqlalchemy import func, select

from api.dependencies import get_current_user_id
from api.main import app
from models.product import Product


@pytest.mark.asyncio
async def test_products_post_idempotency_key_replays_first_response(
    client,
    db_session,
    test_user,
):
    user_id = test_user["id"]
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    try:
        payload = {"name": "Idempotent Product", "weight_g": 100, "unit_price": 12}
        headers = {"Idempotency-Key": f"product-create-{user_id}"}

        first = await client.post("/api/products", json=payload, headers=headers)
        second = await client.post("/api/products", json=payload, headers=headers)

        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json()["id"] == first.json()["id"]

        row_count = await db_session.scalar(
            select(func.count()).select_from(Product).where(
                Product.user_id == user_id,
                Product.name == "Idempotent Product",
            )
        )
        assert row_count == 1
    finally:
        app.dependency_overrides.clear()
