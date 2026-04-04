import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402

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


def _make_db_ctx(fetchone=None, fetchall=None, description=None, rowcount=1):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    cursor.description = description or []
    cursor.rowcount = rowcount
    conn = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=(conn, cursor))
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx, conn, cursor


def _pass_sql(sql, conn):
    return sql


def _multi_fetchone_ctx(values):
    cursor = MagicMock()
    cursor.fetchone.side_effect = values
    cursor.fetchall.return_value = []
    cursor.description = []
    cursor.rowcount = 1
    conn = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=(conn, cursor))
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


class TestSubscriptions:
    @patch("api.routes.subscriptions.get_db_connection")
    @patch("api.routes.subscriptions._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_plans(self, _sql, mock_db):
        cols = [
            ("id",),
            ("code",),
            ("name",),
            ("display_price_month",),
            ("display_price_year",),
            ("actual_price_month",),
            ("actual_price_year",),
            ("test_price_month",),
            ("test_price_year",),
            ("calc_limit",),
            ("logistics_limit",),
            ("sort",),
            ("status",),
            ("description",),
            ("features",),
        ]
        rows = [(1, "free", "免费版", 0, 0, 0, 0, 0, 0, 10, 1, 1, True, "desc", "a,b")]
        ctx, conn, cursor = _make_db_ctx(fetchall=rows, description=cols)
        mock_db.return_value = ctx
        r = client.get("/api/subscriptions/plans")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @patch("api.routes.subscriptions.get_db_connection")
    @patch("api.routes.subscriptions._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_current_subscription(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(fetchone=("enterprise", -1, 999, None))
        mock_db.return_value = ctx
        r = client.get(
            "/api/subscriptions/current", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200
        assert r.json()["plan_code"] == "enterprise"

    @patch("api.routes.subscriptions.get_db_connection")
    @patch("api.routes.subscriptions._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_current_subscription_not_found(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx(fetchone=None)
        mock_db.return_value = ctx
        r = client.get(
            "/api/subscriptions/current", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 404


class TestStatistics:
    @patch("api.routes.statistics.get_db_connection")
    @patch("api.routes.statistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_overview(self, _sql, mock_db):
        mock_db.return_value = _multi_fetchone_ctx(
            [(10,), (2,), (3,), (5,), (1000.0,), (1,)]
        )
        r = client.get(
            "/api/statistics/overview", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200
        assert "total_users" in r.json()

    def test_retention(self):
        r = client.get(
            "/api/statistics/retention", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_revenue(self):
        r = client.get(
            "/api/statistics/revenue", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    def test_feature_usage(self):
        r = client.get(
            "/api/statistics/feature-usage",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    def test_growth(self):
        r = client.get(
            "/api/statistics/growth", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.statistics.get_db_connection")
    @patch("api.routes.statistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_login_logs(self, _sql, mock_db):
        import datetime as dt

        rows = [
            (
                1,
                2,
                dt.datetime(2024, 1, 1),
                "127.0.0.1",
                "Mozilla/5.0",
                "desktop",
                dt.datetime(2024, 1, 1),
            )
        ]
        ctx, conn, cursor = _make_db_ctx(fetchall=rows)
        mock_db.return_value = ctx
        r = client.get(
            "/api/statistics/login-logs", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.statistics.get_db_connection")
    @patch("api.routes.statistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_admin_logs(self, _sql, mock_db):
        import datetime as dt

        rows = [(1, "admin", "create_user", dt.datetime(2024, 1, 1))]
        ctx, conn, cursor = _make_db_ctx(fetchall=rows)
        mock_db.return_value = ctx
        r = client.get(
            "/api/statistics/admin-logs", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.statistics.get_db_connection")
    @patch("api.routes.statistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_user_groups(self, _sql, mock_db):
        mock_db.return_value = _multi_fetchone_ctx([(3,), (7,)])
        r = client.get(
            "/api/statistics/user-groups", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.statistics.get_db_connection")
    @patch("api.routes.statistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_funnel(self, _sql, mock_db):
        mock_db.return_value = _multi_fetchone_ctx([(100,), (20,)])
        r = client.get(
            "/api/statistics/funnel", headers={"Authorization": "Bearer faketoken"}
        )
        assert r.status_code == 200

    @patch("api.routes.statistics.get_db_connection")
    @patch("api.routes.statistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_plan_analysis(self, _sql, mock_db):
        mock_db.return_value = _multi_fetchone_ctx([(10,), (5,), (3,), (2,)])
        r = client.get(
            "/api/statistics/plan-analysis",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

    @patch("api.routes.statistics.get_db_connection")
    @patch("api.routes.statistics._safe_adapt_sql", side_effect=_pass_sql)
    def test_active_users(self, _sql, mock_db):
        mock_db.return_value = _multi_fetchone_ctx([(5,), (15,)])
        r = client.get(
            "/api/statistics/active-users",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200


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

    @patch("api.routes.pricing.calculate_pricing")
    @patch("api.routes.pricing.get_user_logistics")
    @patch("api.routes.pricing.get_fallback_exchange_rate")
    @patch("api.routes.pricing.get_fallback_usd_rate")
    def test_calculate_detailed_with_product_data_no_id(
        self, mock_usd, mock_rate, mock_logistics, mock_calc
    ):
        mock_rate.return_value = 0.085
        mock_usd.return_value = 7.2
        mock_logistics.return_value = []
        mock_calc.return_value = {
            "suggested_price": None,
            "filtered_logistics": {"land": [], "air": []},
        }
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

    def test_calculate_detailed_no_product_data_no_id(self):
        payload = {
            "mode": "detailed",
        }
        r = client.post(
            "/api/pricing/calculate",
            json=payload,
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 400


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


class TestSettings:
    @patch("api.routes.settings._load_backup_service")
    @patch("api.routes.settings.get_db_connection")
    @patch("api.routes.settings._safe_adapt_sql", side_effect=_pass_sql)
    def test_get_settings(self, _sql, mock_db, mock_bs):
        cols = [("config_key",), ("config_value",)]
        rows = [("open_registration", "true")]
        ctx, conn, cursor = _make_db_ctx(fetchall=rows, description=cols)
        mock_db.return_value = ctx
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.get("/api/settings", headers={"Authorization": "Bearer faketoken"})
        assert r.status_code == 200
        assert "open_registration" in r.json()

    @patch("api.routes.settings.get_db_connection")
    @patch("api.routes.settings._safe_adapt_sql", side_effect=_pass_sql)
    def test_update_open_registration(self, _sql, mock_db):
        ctx, conn, cursor = _make_db_ctx()
        mock_db.return_value = ctx
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
            "/api/settings/backup/stats", headers={"Authorization": "Bearer faketoken"}
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
        mock_bs.return_value = _make_backup_service_tuple()
        r = client.get(
            "/api/settings/backup/myfile.dump/download",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert r.status_code == 200

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
        mock_rub.return_value = 0.085
        mock_usd.return_value = 7.2
        r = client.get("/api/exchange/rates")
        assert r.status_code == 200
        body = r.json()
        assert "RUB/CNY" in body
        assert "USD/CNY" in body
        assert "CNY/RUB" in body
        assert "CNY/USD" in body
        assert body["RUB/CNY"] == pytest.approx(0.085, abs=1e-4)
