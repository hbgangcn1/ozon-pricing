import pytest

from api.dependencies import get_current_user_id
from api.main import app


@pytest.mark.asyncio
async def test_products_list_rejects_limit_over_200(client, test_user):
    app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
    try:
        response = await client.get("/api/products?limit=300")
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
