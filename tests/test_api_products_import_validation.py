"""API-W13-01: ProductImportItem Pydantic 校验测试.

覆盖 /api/products/import/confirm 的 rows[*] 强类型校验。
"""

from api.dependencies import get_current_user_id, get_user_with_subscription
from api.main import app


def _user_override(user_id):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def _subscription_override(user_id):
    app.dependency_overrides[get_user_with_subscription] = lambda: {
        "id": user_id,
        "username": "tester",
        "role": "user",
        "user_type": "permanent",
        "subscription_type": "enterprise",
        "remaining_calculations": -1,
    }


def _clear_overrides():
    app.dependency_overrides.clear()


class TestProductImportValidation:
    async def test_import_invalid_price_is_reported_and_valid_row_imported(
        self,
        client,
        test_user,
    ):
        user_id = test_user["id"]
        _user_override(user_id)
        _subscription_override(user_id)
        try:
            response = await client.post(
                "/api/products/import/confirm",
                json={
                    "rows": [
                        {"name": "GoodPrice", "unit_price": 10},
                        {"name": "BadPrice", "unit_price": -1},
                    ],
                    "column_mapping": {"name": "name", "unit_price": "unit_price"},
                    "conflict_action": "skip",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["imported"] == 1
            assert data["failed_rows"][0]["row_index"] == 2
            assert "unit_price" in data["failed_rows"][0]["error"]
        finally:
            _clear_overrides()

    async def test_import_missing_required_field(self, client, test_user):
        user_id = test_user["id"]
        _user_override(user_id)
        _subscription_override(user_id)
        try:
            response = await client.post(
                "/api/products/import/confirm",
                json={
                    "rows": [{"weight_g": 100}],
                    "column_mapping": {"name": "name"},
                    "conflict_action": "skip",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["imported"] == 0
            assert data["failed_rows"][0]["row_index"] == 1
        finally:
            _clear_overrides()

    async def test_import_invalid_weight_too_large(self, client, test_user):
        user_id = test_user["id"]
        _user_override(user_id)
        _subscription_override(user_id)
        try:
            response = await client.post(
                "/api/products/import/confirm",
                json={
                    "rows": [{"name": "Heavy", "weight_g": 99_999_999}],
                    "column_mapping": {"name": "name", "weight_g": "weight_g"},
                    "conflict_action": "skip",
                },
            )
            assert response.status_code == 200
            assert response.json()["failed_rows"][0]["row_index"] == 1
        finally:
            _clear_overrides()

    async def test_import_valid_batch_succeeds(self, client, test_user):
        user_id = test_user["id"]
        _user_override(user_id)
        _subscription_override(user_id)
        try:
            response = await client.post(
                "/api/products/import/confirm",
                json={
                    "rows": [
                        {
                            "name": "ValidProductA",
                            "weight_g": 100,
                            "length_cm": 10,
                            "width_cm": 5,
                            "height_cm": 3,
                        },
                        {
                            "name": "ValidProductB",
                            "weight_g": 200,
                            "unit_price": 19.99,
                        },
                    ],
                    "column_mapping": {
                        "name": "name",
                        "weight_g": "weight_g",
                        "length_cm": "length_cm",
                        "width_cm": "width_cm",
                        "height_cm": "height_cm",
                        "unit_price": "unit_price",
                    },
                    "conflict_action": "skip",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["imported"] == 2
            assert data["errors"] == []
            assert data["failed_rows"] == []
        finally:
            _clear_overrides()
