import sys
import os
import tempfile
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402
from database import get_db  # noqa: E402

MOCK_USER = {
    "id": 1,
    "username": "testuser",
    "role": "admin",
    "user_type": "enterprise",
    "remaining_calculations": 100,
}

app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
app.dependency_overrides[dependencies.require_admin] = lambda: 1
app.dependency_overrides[dependencies.get_current_user] = lambda: MOCK_USER

client = TestClient(app, raise_server_exceptions=False)


def _make_backup_service_tuple():
    backup_system = MagicMock()
    start_bs = MagicMock()
    stop_bs = MagicMock()
    create_manual = MagicMock(return_value=True)
    get_auto = MagicMock(
        return_value={
            "enabled": True,
            "interval_hours": 6,
            "max_backups": 28,
        }
    )
    update_auto = MagicMock()
    list_files = MagicMock(return_value=[])
    get_info = MagicMock(
        return_value={
            "count": 0,
            "total_size_mb": 0.0,
            "files": [],
        }
    )
    delete_file = MagicMock(return_value=True)
    read_file = MagicMock(return_value=b"data")
    restore_db = MagicMock(return_value=True)
    return (
        backup_system,
        start_bs,
        stop_bs,
        create_manual,
        get_auto,
        update_auto,
        list_files,
        get_info,
        delete_file,
        read_file,
        restore_db,
    )


class TestSubscriptions:
    @patch("api.routes.subscriptions.get_plans", new_callable=AsyncMock)
    def test_get_plans(self, mock_get):
        mock_get.return_value = [
            {
                "id": 1,
                "plan_code": "free",
                "plan_name": "免费版",
                "display_price_month": 0,
                "display_price_year": 0,
                "actual_price_month": 0,
                "actual_price_year": 0,
                "test_price_month": 0,
                "test_price_year": 0,
                "calc_limit": 10,
                "logistics_limit": 1,
                "sort_order": 1,
                "is_active": True,
                "description": "desc",
                "features": "a,b",
            }
        ]
        r = client.get("/api/subscriptions/plans")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @patch("api.routes.subscriptions.get_plan_by_code", new_callable=AsyncMock)
    @patch(
        "api.routes.subscriptions.get_user_subscription_info", new_callable=AsyncMock
    )
    def test_get_current_subscription(self, mock_info, mock_plan):
        mock_info.return_value = {
            "user_type": "enterprise",
            "subscription_expires": -1,
            "remaining_calculations": 999,
        }
        mock_plan.return_value = {"calc_limit": -1, "logistics_limit": 999}
        r = client.get(
            "/api/subscriptions/current",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200
        assert r.json()["plan_code"] == "enterprise"

    @patch(
        "api.routes.subscriptions.get_user_subscription_info", new_callable=AsyncMock
    )
    def test_get_current_subscription_not_found(self, mock_info):
        mock_info.return_value = None
        r = client.get(
            "/api/subscriptions/current",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 404


class TestStatistics:
    @patch("api.routes.statistics.get_revenue_stats", new_callable=AsyncMock)
    @patch("api.routes.statistics.count_paid_orders", new_callable=AsyncMock)
    @patch("api.routes.statistics.count_users_by_type", new_callable=AsyncMock)
    @patch("api.routes.statistics.count_total_users", new_callable=AsyncMock)
    def test_overview(self, mock_total, mock_by_type, mock_orders, mock_rev):
        mock_total.return_value = 10
        mock_by_type.return_value = {"professional": 2, "efficiency": 3}
        mock_orders.return_value = 5
        mock_rev.return_value = {"total_revenue": 100000}

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )
        mock_session.scalar = AsyncMock(return_value=1)

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get(
                "/api/statistics/overview",
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
            assert "total_users" in r.json()
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.statistics.get_monthly_retention", new_callable=AsyncMock)
    def test_retention(self, mock_retention):
        mock_retention.return_value = [
            {"month": "2025-01", "retention": 50},
        ]
        mock_session = MagicMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get(
                "/api/statistics/retention",
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
            assert isinstance(r.json(), list)
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.statistics.get_monthly_revenue", new_callable=AsyncMock)
    def test_revenue(self, mock_revenue):
        mock_revenue.return_value = [
            {"month": "2025-01", "revenue": 1000.0},
        ]
        mock_session = AsyncMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get(
                "/api/statistics/revenue",
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
            assert isinstance(r.json(), list)
        finally:
            del app.dependency_overrides[get_db]

    def test_login_logs(self):
        mock_row = MagicMock()
        mock_log = MagicMock()
        mock_user = MagicMock()
        mock_log.id = 1
        mock_log.ip_address = "127.0.0.1"
        mock_log.created_at = 1704067200
        mock_user.username = "testuser"
        mock_row = (mock_log, "testuser")

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.scalar.return_value = 1

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get(
                "/api/statistics/login-logs",
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["items"][0]["username"] == "testuser"
            assert body["items"][0]["action"] == "登录"
            assert body["items"][0]["status"] == "成功"
            assert body["total"] == 1
        finally:
            del app.dependency_overrides[get_db]

    def test_admin_logs(self):
        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.action_type = "create_user"
        mock_log.created_at = 1704067200
        mock_row = (mock_log, "admin")

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.scalar.return_value = 1

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get(
                "/api/statistics/admin-logs",
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["items"][0]["admin"] == "admin"
            assert body["items"][0]["action"] == "create_user"
            assert body["total"] == 1
        finally:
            del app.dependency_overrides[get_db]

    def test_active_users(self):
        mock_session = AsyncMock()
        mock_session.scalar.side_effect = [5, 15]

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get(
                "/api/statistics/active-users",
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
        finally:
            del app.dependency_overrides[get_db]


class TestPricing:
    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics")
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_calculate_fast_mode(self, mock_usd, mock_rate, mock_logistics, mock_calc):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = {
            "suggested_price": None,
            "filtered_logistics": {"land": [], "air": []},
        }
        payload = {
            "mode": "fast",
            "product_data": {"name": "test", "weight_g": 100},
        }
        r = client.post(
            "/api/pricing/calculate",
            json=payload,
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    def test_pricing_progress_sse(self):
        with client.stream("GET", "/api/pricing/progress") as r:
            assert r.status_code == 200

    @patch("api.routes.pricing.decrement_user_calculations", new_callable=AsyncMock)
    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics")
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_calculate_detailed_with_product_data_no_id(
        self, mock_usd, mock_rate, mock_logistics, mock_calc, mock_decrement
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = {
            "suggested_price": None,
            "filtered_logistics": {"land": [], "air": []},
        }
        mock_decrement.return_value = True
        payload = {
            "mode": "detailed",
            "product_data": {
                "name": "test_product",
                "weight_g": 200,
                "unit_price": 10.0,
            },
        }
        r = client.post(
            "/api/pricing/calculate",
            json=payload,
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.pricing.decrement_user_calculations", new_callable=AsyncMock)
    def test_calculate_detailed_no_product_data_no_id(self, mock_decrement):
        mock_decrement.return_value = False
        payload = {
            "mode": "detailed",
        }
        r = client.post(
            "/api/pricing/calculate",
            json=payload,
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 403


class TestSettings:
    @pytest.fixture(autouse=True)
    def _ensure_admin_override(self):
        app.dependency_overrides[dependencies.require_admin] = lambda: 1
        yield
        app.dependency_overrides.pop(dependencies.require_admin, None)

    @patch("api.routes.settings._load_backup_service")
    @patch("api.routes.settings.get_all_config", new_callable=AsyncMock)
    def test_get_settings(self, mock_config, mock_bs):
        mock_config.return_value = [
            {"config_key": "open_registration", "config_value": "true"}
        ]
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.get("/api/settings", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200
        assert "open_registration" in r.json()

    @patch("api.routes.settings.set_system_config", new_callable=AsyncMock)
    def test_update_open_registration(self, mock_set):
        r = client.put(
            "/api/settings/open-registration?enabled=true",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_get_backups(self, mock_bs):
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.get(
            "/api/settings/backups", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_create_backup(self, mock_bs):
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.post(
            "/api/settings/backup", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_get_backup_settings(self, mock_bs):
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.get(
            "/api/settings/backup/settings",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_update_backup_settings(self, mock_bs):
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.put(
            "/api/settings/backup/settings",
            json={"interval_hours": 12},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_get_backup_stats(self, mock_bs):
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.get(
            "/api/settings/backup/stats",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_delete_backup(self, mock_bs):
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.delete(
            "/api/settings/backup/myfile.dump",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_delete_backup_bad_extension(self, mock_bs):
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.delete(
            "/api/settings/backup/evil.exe",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 400

    @patch("api.routes.settings._load_backup_service")
    def test_restore_backup(self, mock_bs):
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.post(
            "/api/settings/backup/myfile.dump/restore",
            json={"create_snapshot": False},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.settings._load_backup_service")
    def test_download_backup(self, mock_bs):
        fd, tmp_path = tempfile.mkstemp(suffix=".dump")
        try:
            os.write(fd, b"data")
            os.close(fd)
            tup = list(_make_backup_service_tuple())
            tup[0].get_backup_file_path.return_value = tmp_path
            mock_bs.return_value = tuple(tup)
            r = client.get(
                "/api/settings/backup/myfile.dump/download",
                headers={"Authorization": "Bearer faketoken"},
            )
            assert r.status_code == 200
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @patch("api.routes.settings._load_backup_service")
    def test_download_backup_bad_extension(self, mock_bs):
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.get(
            "/api/settings/backup/evil.sh/download",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 400


class TestExchange:
    @patch("api.routes.exchange.get_fallback_exchange_rate")
    @patch("api.routes.exchange.get_fallback_usd_rate")
    def test_get_rates(self, mock_usd, mock_rub):
        mock_rub.return_value = Decimal("0.085")
        mock_usd.return_value = Decimal("7.2")
        r = client.get("/api/exchange/rates")
        assert r.status_code == 200
        body = r.json()
        assert "RUB/CNY" in body
        assert "USD/CNY" in body
        assert "CNY/RUB" in body
        assert "CNY/USD" in body
        assert body["RUB/CNY"] == pytest.approx(0.085, abs=1e-4)
