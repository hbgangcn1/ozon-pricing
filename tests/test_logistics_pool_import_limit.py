from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api import dependencies
from api.main import app
from database import get_db

client = TestClient(app, raise_server_exceptions=False)


def _db_override(session):
    async def override():
        yield session

    return override


class TestLogisticsImportLimitFreeTier:
    def setup_method(self):
        self.saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

    def teardown_method(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.saved)

    def test_free_user_first_import_succeeds(self):
        session = AsyncMock()
        with (
            patch(
                "api.routes.logistics_pool._get_user_subscription",
                new=AsyncMock(return_value=("user", "free")),
            ),
            patch(
                "api.routes.logistics_pool.get_logistics_by_filters",
                new=AsyncMock(return_value=([], 0)),
            ),
            patch(
                "api.routes.logistics_pool.get_plan_by_code",
                new=AsyncMock(return_value={"logistics_limit": 1, "plan_name": "免费版", "plan_code": "free"}),
            ),
            patch(
                "api.routes.logistics_pool.get_by_id",
                new=AsyncMock(return_value={"id": 1, "name": "test", "type": "express"}),
            ),
            patch(
                "api.routes.logistics_pool.create_logistics",
                new=AsyncMock(return_value=100),
            ),
            patch(
                "api.routes.logistics_pool.recalculate_priority_groups",
                new=AsyncMock(),
            ),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 200
        assert response.json() == {"id": 100}

    def test_free_user_second_import_rejected(self):
        session = AsyncMock()
        with (
            patch(
                "api.routes.logistics_pool._get_user_subscription",
                new=AsyncMock(return_value=("user", "free")),
            ),
            patch(
                "api.routes.logistics_pool.get_logistics_by_filters",
                new=AsyncMock(return_value=([], 1)),
            ),
            patch(
                "api.routes.logistics_pool.get_plan_by_code",
                new=AsyncMock(return_value={"logistics_limit": 1, "plan_name": "免费版", "plan_code": "free"}),
            ),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 403
        assert "最多只能添加 1 条" in response.json()["detail"]


class TestLogisticsImportLimitEfficiencyTier:
    def setup_method(self):
        self.saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

    def teardown_method(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.saved)

    def test_efficiency_user_third_import_succeeds(self):
        session = AsyncMock()
        with (
            patch(
                "api.routes.logistics_pool._get_user_subscription",
                new=AsyncMock(return_value=("user", "efficiency")),
            ),
            patch(
                "api.routes.logistics_pool.get_logistics_by_filters",
                new=AsyncMock(return_value=([], 2)),
            ),
            patch(
                "api.routes.logistics_pool.get_plan_by_code",
                new=AsyncMock(return_value={"logistics_limit": 3, "plan_name": "效率版", "plan_code": "efficiency"}),
            ),
            patch(
                "api.routes.logistics_pool.get_by_id",
                new=AsyncMock(return_value={"id": 1, "name": "test", "type": "express"}),
            ),
            patch(
                "api.routes.logistics_pool.create_logistics",
                new=AsyncMock(return_value=100),
            ),
            patch(
                "api.routes.logistics_pool.recalculate_priority_groups",
                new=AsyncMock(),
            ),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 200
        assert response.json() == {"id": 100}

    def test_efficiency_user_fourth_import_rejected(self):
        session = AsyncMock()
        with (
            patch(
                "api.routes.logistics_pool._get_user_subscription",
                new=AsyncMock(return_value=("user", "efficiency")),
            ),
            patch(
                "api.routes.logistics_pool.get_logistics_by_filters",
                new=AsyncMock(return_value=([], 3)),
            ),
            patch(
                "api.routes.logistics_pool.get_plan_by_code",
                new=AsyncMock(return_value={"logistics_limit": 3, "plan_name": "效率版", "plan_code": "efficiency"}),
            ),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 403
        assert "最多只能添加 3 条" in response.json()["detail"]


class TestLogisticsImportLimitProfessionalTier:
    def setup_method(self):
        self.saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

    def teardown_method(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.saved)

    def test_professional_user_import_unlimited(self):
        session = AsyncMock()
        with (
            patch(
                "api.routes.logistics_pool._get_user_subscription",
                new=AsyncMock(return_value=("user", "professional")),
            ),
            patch(
                "api.routes.logistics_pool.get_logistics_by_filters",
                new=AsyncMock(return_value=([], 100)),
            ),
            patch(
                "api.routes.logistics_pool.get_plan_by_code",
                new=AsyncMock(return_value={"logistics_limit": -1, "plan_name": "专业版", "plan_code": "professional"}),
            ),
            patch(
                "api.routes.logistics_pool.get_by_id",
                new=AsyncMock(return_value={"id": 1, "name": "test", "type": "express"}),
            ),
            patch(
                "api.routes.logistics_pool.create_logistics",
                new=AsyncMock(return_value=100),
            ),
            patch(
                "api.routes.logistics_pool.recalculate_priority_groups",
                new=AsyncMock(),
            ),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 200
        assert response.json() == {"id": 100}


class TestLogisticsBatchImportLimit:
    def setup_method(self):
        self.saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

    def teardown_method(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.saved)

    def test_free_user_batch_import_exceeds_limit(self):
        session = AsyncMock()
        with (
            patch(
                "api.routes.logistics_pool._get_user_subscription",
                new=AsyncMock(return_value=("user", "free")),
            ),
            patch(
                "api.routes.logistics_pool.get_logistics_by_filters",
                new=AsyncMock(return_value=([], 0)),
            ),
            patch(
                "api.routes.logistics_pool.get_plan_by_code",
                new=AsyncMock(return_value={"logistics_limit": 1, "plan_name": "免费版", "plan_code": "free"}),
            ),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post(
                "/api/logistics-pool/batch-add-to-my-logistics",
                json={"ids": [1, 2, 3]},
            )
        assert response.status_code == 403
        assert "最多只能添加 1 条" in response.json()["detail"]

    def test_efficiency_user_batch_import_exceeds_limit(self):
        session = AsyncMock()
        with (
            patch(
                "api.routes.logistics_pool._get_user_subscription",
                new=AsyncMock(return_value=("user", "efficiency")),
            ),
            patch(
                "api.routes.logistics_pool.get_logistics_by_filters",
                new=AsyncMock(return_value=([], 2)),
            ),
            patch(
                "api.routes.logistics_pool.get_plan_by_code",
                new=AsyncMock(return_value={"logistics_limit": 3, "plan_name": "效率版", "plan_code": "efficiency"}),
            ),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post(
                "/api/logistics-pool/batch-add-to-my-logistics",
                json={"ids": [1, 2]},
            )
        assert response.status_code == 403
        assert "最多只能添加 3 条" in response.json()["detail"]

    def test_batch_import_within_limit_succeeds(self):
        session = AsyncMock()
        with (
            patch(
                "api.routes.logistics_pool._get_user_subscription",
                new=AsyncMock(return_value=("user", "efficiency")),
            ),
            patch(
                "api.routes.logistics_pool.get_logistics_by_filters",
                new=AsyncMock(return_value=([], 1)),
            ),
            patch(
                "api.routes.logistics_pool.get_plan_by_code",
                new=AsyncMock(return_value={"logistics_limit": 3, "plan_name": "效率版", "plan_code": "efficiency"}),
            ),
            patch(
                "api.routes.logistics_pool.get_by_id",
                new=AsyncMock(
                    side_effect=[
                        {"id": 1, "name": "test1", "type": "express"},
                        {"id": 2, "name": "test2", "type": "express"},
                    ]
                ),
            ),
            patch(
                "api.routes.logistics_pool.create_logistics",
                new=AsyncMock(side_effect=[100, 101]),
            ),
            patch(
                "api.routes.logistics_pool.recalculate_priority_groups",
                new=AsyncMock(),
            ),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post(
                "/api/logistics-pool/batch-add-to-my-logistics",
                json={"ids": [1, 2]},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 2