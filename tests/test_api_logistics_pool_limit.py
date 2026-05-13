import pytest

from api.dependencies import get_current_user_id
from api.main import app


@pytest.mark.asyncio
async def test_logistics_pool_batch_add_rejects_51_ids(client, test_user):
    app.dependency_overrides[get_current_user_id] = lambda: test_user["id"]
    try:
        response = await client.post(
            "/api/logistics-pool/batch-add-to-my-logistics",
            json={"ids": list(range(1, 52))},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
