import pytest

from api.main import app
from api.dependencies import get_current_user_id

LOGISTICS_DATA = {
    "name": "Test Logistics Rule",
    "type": "land",
    "min_days": 5,
    "max_days": 15,
    "fee_mode": "base_weight",
    "first_fee": 10.0,
    "first_weight_g": 500,
    "continue_fee": 2.0,
    "continue_unit": "g",
    "is_active": True,
}

PRODUCT_DATA = {
    "name": "Test Product",
    "weight_g": 500,
    "length_cm": 20,
    "width_cm": 15,
    "height_cm": 10,
    "unit_price": 99.9,
}


def _user_override(user_id):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def _clear_overrides():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/logistics — list logistics
# ---------------------------------------------------------------------------


class TestListLogistics:
    async def test_list_empty_initially(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        try:
            resp = await client.get("/api/logistics")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# POST /api/logistics — create logistics rule
# ---------------------------------------------------------------------------


class TestCreateLogistics:
    async def test_create_success(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        created_id = None
        try:
            resp = await client.post("/api/logistics", json=LOGISTICS_DATA)
            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == LOGISTICS_DATA["name"]
            assert "id" in data
            created_id = data["id"]
        finally:
            _clear_overrides()
            if created_id:
                _user_override(uid)
                await client.delete(f"/api/logistics/{created_id}")
                _clear_overrides()


# ---------------------------------------------------------------------------
# Full CRUD flow for logistics
# ---------------------------------------------------------------------------


class TestLogisticsCRUD:
    async def test_full_crud_flow(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        created_id = None
        try:
            list_resp = await client.get("/api/logistics")
            assert list_resp.status_code == 200
            initial_count = len(list_resp.json())

            create_resp = await client.post("/api/logistics", json=LOGISTICS_DATA)
            assert create_resp.status_code == 201
            created_id = create_resp.json()["id"]

            list_resp2 = await client.get("/api/logistics")
            assert len(list_resp2.json()) == initial_count + 1

            get_resp = await client.get(f"/api/logistics/{created_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == created_id
            assert get_resp.json()["name"] == LOGISTICS_DATA["name"]

            update_resp = await client.put(
                f"/api/logistics/{created_id}",
                json={"name": "Updated Rule Name"},
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["name"] == "Updated Rule Name"

            del_resp = await client.delete(f"/api/logistics/{created_id}")
            assert del_resp.status_code == 200
            created_id = None

            gone_resp = await client.get("/api/logistics/999999999")
            assert gone_resp.status_code == 404
        finally:
            _clear_overrides()
            if created_id:
                _user_override(uid)
                await client.delete(f"/api/logistics/{created_id}")
                _clear_overrides()

    async def test_get_nonexistent_returns_404(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        try:
            resp = await client.get("/api/logistics/999999999")
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    async def test_delete_nonexistent_returns_404(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        try:
            resp = await client.delete("/api/logistics/999999999")
            assert resp.status_code == 404
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# POST /api/logistics/batch-delete
# ---------------------------------------------------------------------------


class TestBatchDeleteLogistics:
    async def test_batch_delete_success(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        ids = []
        try:
            for i in range(2):
                data = dict(LOGISTICS_DATA)
                data["name"] = f"Batch Rule {i}"
                resp = await client.post("/api/logistics", json=data)
                assert resp.status_code == 201
                ids.append(resp.json()["id"])

            batch_resp = await client.post("/api/logistics/batch-delete", json=ids)
            assert batch_resp.status_code == 200
            assert "message" in batch_resp.json()
            ids = []
        finally:
            _clear_overrides()
            if ids:
                _user_override(uid)
                for rid in ids:
                    await client.delete(f"/api/logistics/{rid}")
                _clear_overrides()

    async def test_batch_delete_empty_list(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        try:
            resp = await client.post("/api/logistics/batch-delete", json=[])
            assert resp.status_code == 400
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# GET /api/products — list products
# ---------------------------------------------------------------------------


class TestListProducts:
    async def test_list_empty_initially(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        try:
            resp = await client.get("/api/products")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# POST /api/products — create product
# ---------------------------------------------------------------------------


class TestCreateProduct:
    async def test_create_success(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        created_id = None
        try:
            resp = await client.post("/api/products", json=PRODUCT_DATA)
            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == PRODUCT_DATA["name"]
            assert "id" in data
            created_id = data["id"]
        finally:
            _clear_overrides()
            if created_id:
                _user_override(uid)
                await client.delete(f"/api/products/{created_id}")
                _clear_overrides()


# ---------------------------------------------------------------------------
# Full CRUD flow for products
# ---------------------------------------------------------------------------


class TestProductCRUD:
    async def test_full_crud_flow(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        created_id = None
        try:
            list_resp = await client.get("/api/products")
            assert list_resp.status_code == 200
            initial_count = len(list_resp.json())

            create_resp = await client.post("/api/products", json=PRODUCT_DATA)
            assert create_resp.status_code == 201
            created_id = create_resp.json()["id"]

            list_resp2 = await client.get("/api/products")
            assert len(list_resp2.json()) == initial_count + 1

            get_resp = await client.get(f"/api/products/{created_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == created_id
            assert get_resp.json()["name"] == PRODUCT_DATA["name"]

            update_resp = await client.put(
                f"/api/products/{created_id}",
                json={"name": "Updated Product Name"},
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["name"] == "Updated Product Name"

            del_resp = await client.delete(f"/api/products/{created_id}")
            assert del_resp.status_code == 200
            created_id = None
        finally:
            _clear_overrides()
            if created_id:
                _user_override(uid)
                await client.delete(f"/api/products/{created_id}")
                _clear_overrides()

    async def test_get_nonexistent_returns_404(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        try:
            resp = await client.get("/api/products/999999999")
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    async def test_delete_nonexistent_returns_404(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        try:
            resp = await client.delete("/api/products/999999999")
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    async def test_update_nonexistent_returns_404(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        try:
            resp = await client.put(
                "/api/products/999999999",
                json={"name": "nope"},
            )
            assert resp.status_code == 404
        finally:
            _clear_overrides()
