import pytest

from api.dependencies import get_current_user_id, require_admin
from api.main import app


PRODUCT_DATA = {"name": "IfMatch Product", "weight_g": 100, "unit_price": 10}
LOGISTICS_DATA = {
    "name": "IfMatch Logistics",
    "type": "land",
    "min_days": 1,
    "max_days": 7,
    "fee_mode": "base_weight",
    "first_fee": 10,
    "first_weight_g": 500,
    "continue_fee": 2,
    "continue_unit": "g",
}


def _clear_overrides():
    app.dependency_overrides.clear()


def _user_override(user_id: int) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def _admin_override(admin_id: int) -> None:
    app.dependency_overrides[require_admin] = lambda: admin_id


@pytest.mark.asyncio
async def test_product_delete_requires_current_if_match(client, test_user, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    _user_override(test_user["id"])
    try:
        created = await client.post("/api/products", json=PRODUCT_DATA)
        product_id = created.json()["id"]
        get_resp = await client.get(f"/api/products/{product_id}")
        assert get_resp.headers["ETag"].startswith('W/"')

        missing = await client.delete(f"/api/products/{product_id}")
        assert missing.status_code == 428

        stale = await client.delete(
            f"/api/products/{product_id}", headers={"If-Match": 'W/"stale"'}
        )
        assert stale.status_code == 412

        ok = await client.delete(
            f"/api/products/{product_id}",
            headers={"If-Match": get_resp.headers["ETag"]},
        )
        assert ok.status_code == 200
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_logistics_delete_requires_current_if_match(client, test_user, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    _user_override(test_user["id"])
    try:
        created = await client.post("/api/logistics", json=LOGISTICS_DATA)
        logistics_id = created.json()["id"]
        get_resp = await client.get(f"/api/logistics/{logistics_id}")

        assert (await client.delete(f"/api/logistics/{logistics_id}")).status_code == 428
        stale = await client.delete(
            f"/api/logistics/{logistics_id}", headers={"If-Match": 'W/"stale"'}
        )
        assert stale.status_code == 412
        ok = await client.delete(
            f"/api/logistics/{logistics_id}",
            headers={"If-Match": get_resp.headers["ETag"]},
        )
        assert ok.status_code == 200
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_admin_delete_requires_current_if_match(client, test_admin, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    admin_id = test_admin["id"]
    _admin_override(admin_id)
    try:
        created = await client.post(
            "/api/admin/users",
            json={
                "username": f"if_match_user_{admin_id}",
                "password": "TestPass@123",
                "role": "user",
                "user_type": "free",
            },
        )
        user_id = created.json()["id"]
        get_resp = await client.get(f"/api/admin/users/{user_id}")

        assert (await client.delete(f"/api/admin/users/{user_id}")).status_code == 428
        stale = await client.delete(
            f"/api/admin/users/{user_id}", headers={"If-Match": 'W/"stale"'}
        )
        assert stale.status_code == 412
        ok = await client.delete(
            f"/api/admin/users/{user_id}",
            headers={"If-Match": get_resp.headers["ETag"]},
        )
        assert ok.status_code == 200
    finally:
        _clear_overrides()
