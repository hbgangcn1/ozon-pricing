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


# Priority 3 (history-tracking): default test_user fixture is free-tier
# (logistics_limit=1); these multi-record tests pre-date the limit
# enforcement added in api/routes/logistics.py:81-88. Bump the user to
# the professional plan (logistics_limit=10) inline so the test exercises
# its actual scenario instead of tripping the free-tier guard.
async def _upgrade_to_professional(user_id: int) -> None:
    from sqlalchemy import update
    from database import AsyncSessionLocal
    from models.user import User

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(subscription_type="professional")
        )
        await session.commit()


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
            data = resp.json()
            assert "items" in data
            assert isinstance(data["items"], list)
        finally:
            _clear_overrides()

    async def test_filters_by_fulfillment_type_and_destination(self, client, test_user):
        uid = test_user["id"]
        await _upgrade_to_professional(uid)
        _user_override(uid)
        created_ids = []
        try:
            payloads = [
                {
                    **LOGISTICS_DATA,
                    "name": "RFBS-RU Rule",
                    "fulfillment_type": "rfbs",
                    "destination": "RU",
                },
                {
                    **LOGISTICS_DATA,
                    "name": "FBP-BY Rule",
                    "type": "air",
                    "fulfillment_type": "fbp",
                    "destination": "BY",
                },
                {
                    **LOGISTICS_DATA,
                    "name": "RFBS-KZ Rule",
                    "fulfillment_type": "rfbs",
                    "destination": "KZ",
                },
            ]

            for payload in payloads:
                resp = await client.post("/api/logistics", json=payload)
                assert resp.status_code == 201
                created_ids.append(resp.json()["id"])

            fulfillment_resp = await client.get(
                "/api/logistics", params={"fulfillment_type": "fbp"}
            )
            assert fulfillment_resp.status_code == 200
            fulfillment_items = fulfillment_resp.json()["items"]
            assert [item["name"] for item in fulfillment_items] == ["FBP-BY Rule"]

            destination_resp = await client.get(
                "/api/logistics", params={"destination": "KZ"}
            )
            assert destination_resp.status_code == 200
            destination_items = destination_resp.json()["items"]
            assert [item["name"] for item in destination_items] == ["RFBS-KZ Rule"]

            combined_resp = await client.get(
                "/api/logistics",
                params={"fulfillment_type": "rfbs", "destination": "RU"},
            )
            assert combined_resp.status_code == 200
            combined_items = combined_resp.json()["items"]
            assert [item["name"] for item in combined_items] == ["RFBS-RU Rule"]
        finally:
            _clear_overrides()
            if created_ids:
                _user_override(uid)
                for created_id in created_ids:
                    item = await client.get(f"/api/logistics/{created_id}")
                    await client.delete(
                        f"/api/logistics/{created_id}",
                        headers={"If-Match": item.headers["ETag"]},
                    )
                _clear_overrides()

    async def test_filters_by_type(self, client, test_user):
        uid = test_user["id"]
        await _upgrade_to_professional(uid)
        _user_override(uid)
        created_ids = []
        try:
            payloads = [
                {**LOGISTICS_DATA, "name": "Land-1", "type": "land"},
                {**LOGISTICS_DATA, "name": "Land-2", "type": "land"},
                {**LOGISTICS_DATA, "name": "Air-1", "type": "air"},
            ]
            for payload in payloads:
                resp = await client.post("/api/logistics", json=payload)
                assert resp.status_code == 201
                created_ids.append(resp.json()["id"])

            land_resp = await client.get("/api/logistics", params={"type": "land"})
            assert land_resp.status_code == 200
            land_data = land_resp.json()
            land_names = [i["name"] for i in land_data["items"]]
            assert "Land-1" in land_names
            assert "Land-2" in land_names
            assert "Air-1" not in land_names
            assert land_data["total"] >= 2

            air_resp = await client.get("/api/logistics", params={"type": "air"})
            assert air_resp.status_code == 200
            air_data = air_resp.json()
            air_names = [i["name"] for i in air_data["items"]]
            assert "Air-1" in air_names
            assert "Land-1" not in air_names
            assert air_data["total"] >= 1
        finally:
            _clear_overrides()
            if created_ids:
                _user_override(uid)
                for created_id in created_ids:
                    await client.delete(f"/api/logistics/{created_id}")
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
            initial_count = len(list_resp.json()["items"])

            create_resp = await client.post("/api/logistics", json=LOGISTICS_DATA)
            assert create_resp.status_code == 201
            created_id = create_resp.json()["id"]

            list_resp2 = await client.get("/api/logistics")
            assert len(list_resp2.json()["items"]) == initial_count + 1

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

    async def test_toggle_transport_success(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        created_id = None
        try:
            create_resp = await client.post("/api/logistics", json=LOGISTICS_DATA)
            assert create_resp.status_code == 201
            created = create_resp.json()
            created_id = created["id"]
            assert created["type"] == "land"

            toggle_resp = await client.patch(
                f"/api/logistics/{created_id}/toggle-transport"
            )
            assert toggle_resp.status_code == 200
            assert toggle_resp.json()["type"] == "air"
        finally:
            _clear_overrides()
            if created_id:
                _user_override(uid)
                await client.delete(f"/api/logistics/{created_id}")
                _clear_overrides()

    async def test_toggle_transport_nonexistent_returns_404(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        try:
            resp = await client.patch("/api/logistics/999999999/toggle-transport")
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    async def test_toggle_transport_unauthenticated_returns_401(self, client):
        resp = await client.patch("/api/logistics/1/toggle-transport")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/logistics/batch-delete
# ---------------------------------------------------------------------------


class TestBatchDeleteLogistics:
    async def test_batch_delete_success(self, client, test_user):
        uid = test_user["id"]
        await _upgrade_to_professional(uid)
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
                item = await client.get(f"/api/products/{created_id}")
                await client.delete(
                    f"/api/products/{created_id}",
                    headers={"If-Match": item.headers["ETag"]},
                )
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


# ---------------------------------------------------------------------------
# commission_category_id round-trip for products
# ---------------------------------------------------------------------------


class TestProductCommissionCategory:
    async def test_create_product_with_commission_category_id(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        created_id = None
        try:
            payload = {**PRODUCT_DATA, "commission_category_id": 42}
            resp = await client.post("/api/products", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["commission_category_id"] == 42
            created_id = data["id"]

            get_resp = await client.get(f"/api/products/{created_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["commission_category_id"] == 42
        finally:
            _clear_overrides()
            if created_id:
                _user_override(uid)
                await client.delete(f"/api/products/{created_id}")
                created_id = None
                _clear_overrides()

    async def test_update_product_commission_category_id(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        created_id = None
        try:
            resp = await client.post("/api/products", json=PRODUCT_DATA)
            assert resp.status_code == 201
            created_id = resp.json()["id"]

            update_resp = await client.put(
                f"/api/products/{created_id}",
                json={"commission_category_id": 99},
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["commission_category_id"] == 99

            get_resp = await client.get(f"/api/products/{created_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["commission_category_id"] == 99
        finally:
            _clear_overrides()
            if created_id:
                _user_override(uid)
                await client.delete(f"/api/products/{created_id}")
                created_id = None
                _clear_overrides()

    async def test_commission_category_id_round_trip(self, client, test_user):
        uid = test_user["id"]
        _user_override(uid)
        created_id = None
        try:
            create_resp = await client.post(
                "/api/products",
                json={**PRODUCT_DATA, "commission_category_id": 10},
            )
            assert create_resp.status_code == 201
            created_id = create_resp.json()["id"]

            get_resp1 = await client.get(f"/api/products/{created_id}")
            assert get_resp1.status_code == 200
            assert get_resp1.json()["commission_category_id"] == 10

            update_resp1 = await client.put(
                f"/api/products/{created_id}",
                json={"commission_category_id": 20},
            )
            assert update_resp1.status_code == 200
            assert update_resp1.json()["commission_category_id"] == 20

            get_resp2 = await client.get(f"/api/products/{created_id}")
            assert get_resp2.status_code == 200
            assert get_resp2.json()["commission_category_id"] == 20

            update_resp2 = await client.put(
                f"/api/products/{created_id}",
                json={"commission_category_id": None},
            )
            assert update_resp2.status_code == 200
            assert update_resp2.json()["commission_category_id"] is None

            get_resp3 = await client.get(f"/api/products/{created_id}")
            assert get_resp3.status_code == 200
            assert get_resp3.json()["commission_category_id"] is None
        finally:
            _clear_overrides()
            if created_id:
                _user_override(uid)
                await client.delete(f"/api/products/{created_id}")
                created_id = None
                _clear_overrides()
