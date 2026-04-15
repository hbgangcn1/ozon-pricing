# -*- coding: utf-8 -*-
# pyright: reportUnusedFunction=false

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api import dependencies  # noqa: E402
from database import get_db  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _ensure_overrides():
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    yield
    app.dependency_overrides.pop(dependencies.get_current_user_id, None)
    app.dependency_overrides.pop(dependencies.require_admin, None)


class TestRunMigrations:
    async def test_run_migrations_calls_upgrade_head(self):
        with patch("alembic.command.upgrade") as mock_upgrade:
            from database import run_migrations

            await run_migrations()
            mock_upgrade.assert_called_once()
            args = mock_upgrade.call_args[0]
            assert args[1] == "head"

    async def test_run_migrations_propagates_exception(self):
        with patch(
            "alembic.command.upgrade",
            side_effect=RuntimeError("alembic fail"),
        ):
            from database import run_migrations

            with pytest.raises(RuntimeError, match="alembic fail"):
                await run_migrations()

    async def test_run_migrations_ini_path_ends_with_alembic_ini(self):
        captured = {}

        def fake_upgrade(cfg, revision):
            captured["ini"] = cfg.config_file_name
            captured["revision"] = revision

        with patch("alembic.command.upgrade", side_effect=fake_upgrade):
            from database import run_migrations

            await run_migrations()

        assert captured["revision"] == "head"
        assert captured["ini"].endswith("alembic.ini")


class TestLifespanReal:
    @pytest.mark.asyncio
    async def test_lifespan_success_path(self):
        mock_dispose = AsyncMock()
        fake_backup_module = MagicMock()

        with (
            patch("api.main.run_migrations") as mock_migrate,
            patch("api.main.engine") as mock_engine,
            patch.dict("sys.modules", {"postgres_backup_service": fake_backup_module}),
        ):
            mock_engine.dispose = mock_dispose
            from api.main import lifespan

            app_mock = MagicMock()
            ctx = lifespan(app_mock)
            await ctx.__aenter__()
            await ctx.__aexit__(None, None, None)

        mock_migrate.assert_called_once()
        mock_dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_migration_failure_raises(self):
        with patch("api.main.run_migrations", side_effect=RuntimeError("DB down")):
            from api.main import lifespan

            app_mock = MagicMock()
            ctx = lifespan(app_mock)
            with pytest.raises(RuntimeError, match="DB down"):
                await ctx.__aenter__()

    @pytest.mark.asyncio
    async def test_lifespan_backup_start_failure_continues(self):
        mock_dispose = AsyncMock()
        fake_backup_module = MagicMock()
        fake_backup_module.start_backup_service.side_effect = OSError("unavailable")

        with (
            patch("api.main.run_migrations"),
            patch("api.main.engine") as mock_engine,
            patch.dict("sys.modules", {"postgres_backup_service": fake_backup_module}),
        ):
            mock_engine.dispose = mock_dispose
            from api.main import lifespan

            app_mock = MagicMock()
            ctx = lifespan(app_mock)
            await ctx.__aenter__()
            await ctx.__aexit__(None, None, None)

        mock_dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_backup_stop_failure_continues(self):
        mock_dispose = AsyncMock()
        fake_backup_module = MagicMock()
        fake_backup_module.stop_backup_service.side_effect = OSError("stop failed")

        with (
            patch("api.main.run_migrations"),
            patch("api.main.engine") as mock_engine,
            patch.dict("sys.modules", {"postgres_backup_service": fake_backup_module}),
        ):
            mock_engine.dispose = mock_dispose
            from api.main import lifespan

            app_mock = MagicMock()
            ctx = lifespan(app_mock)
            await ctx.__aenter__()
            await ctx.__aexit__(None, None, None)

        mock_dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_engine_disposed_on_shutdown(self):
        mock_dispose = AsyncMock()

        with (
            patch("api.main.run_migrations"),
            patch("api.main.engine") as mock_engine,
        ):
            mock_engine.dispose = mock_dispose
            from api.main import lifespan

            app_mock = MagicMock()
            ctx = lifespan(app_mock)
            await ctx.__aenter__()
            await ctx.__aexit__(None, None, None)

        mock_dispose.assert_called_once()


class TestGlobalExceptionHandlerRealApp:
    def test_non_http_exception_returns_500(self):
        from fastapi import Request as _Request

        @app.get("/_test_error_misc_500")
        async def _raise_runtime(_req: _Request):
            raise RuntimeError("boom")

        try:
            resp = client.get("/_test_error_misc_500")
            assert resp.status_code == 500
            assert resp.json()["detail"] == "Internal server error"
        finally:
            app.routes[:] = [
                r
                for r in app.routes
                if getattr(r, "path", None) != "/_test_error_misc_500"
            ]

    def test_http_exception_preserves_status(self):
        from fastapi import HTTPException as _HTTPException, Request as _Request

        @app.get("/_test_http_403_misc")
        async def _raise_http(_req: _Request):
            raise _HTTPException(status_code=403, detail="Forbidden detail")

        try:
            resp = client.get("/_test_http_403_misc")
            assert resp.status_code == 403
            assert resp.json()["detail"] == "Forbidden detail"
        finally:
            app.routes[:] = [
                r
                for r in app.routes
                if getattr(r, "path", None) != "/_test_http_403_misc"
            ]


class TestAdminErrorPaths:
    @patch("api.routes.admin.create_user", new_callable=AsyncMock)
    def test_create_user_admin_returns_none_raises_400(self, mock_create):
        mock_create.return_value = None
        resp = client.post(
            "/api/admin/users",
            json={
                "username": "failuser",
                "password": "Fail@12345",
                "role": "user",
                "user_type": "free",
            },
            headers={"Authorization": "Bearer faketoken"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "创建用户失败"

    @patch("api.routes.admin.create_user", new_callable=AsyncMock)
    def test_create_user_admin_zero_id_raises_400(self, mock_create):
        mock_create.return_value = 0
        resp = client.post(
            "/api/admin/users",
            json={
                "username": "zerouser",
                "password": "Zero@12345",
                "role": "user",
                "user_type": "free",
            },
            headers={"Authorization": "Bearer faketoken"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "创建用户失败"

    def test_update_user_not_found_returns_404(self):
        mock_session = AsyncMock()
        mock_session.get.return_value = None

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            resp = client.put(
                "/api/admin/users/9999",
                json={"role": "user"},
                headers={"Authorization": "Bearer faketoken"},
            )
            assert resp.status_code == 404
            assert resp.json()["detail"] == "用户不存在"
        finally:
            del app.dependency_overrides[get_db]

    @patch("api.routes.admin.db_admin.reset_user_password", new_callable=AsyncMock)
    def test_reset_password_returns_none_raises_404(self, mock_reset):
        mock_reset.return_value = None
        resp = client.post(
            "/api/admin/users/9999/reset-password",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "用户不存在"

    @patch("api.routes.admin.db_admin.reset_user_password", new_callable=AsyncMock)
    def test_reset_password_returns_empty_string_raises_404(self, mock_reset):
        mock_reset.return_value = ""
        resp = client.post(
            "/api/admin/users/9999/reset-password",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "用户不存在"

    @patch("api.routes.admin.db_admin.delete_user_admin", new_callable=AsyncMock)
    def test_delete_user_not_found_returns_404(self, mock_del):
        mock_del.return_value = False
        resp = client.delete(
            "/api/admin/users/9999",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "用户不存在或删除失败"

    @patch("api.routes.admin.db_admin.delete_user_admin", new_callable=AsyncMock)
    def test_delete_user_returns_none_raises_404(self, mock_del):
        mock_del.return_value = None
        resp = client.delete(
            "/api/admin/users/8888",
            headers={"Authorization": "Bearer faketoken"},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "用户不存在或删除失败"


class TestCommissionCategorySubscriptionGating:
    @staticmethod
    def _with_subscription(subscription_type):
        return {
            "id": 1,
            "username": "tester",
            "role": "user",
            "user_type": "permanent",
            "subscription_type": subscription_type,
            "remaining_calculations": -1,
        }

    def test_get_list_allows_free_tier(self):
        saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()
        app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
        try:
            with patch(
                "api.routes.commission_categories.get_all",
                new=AsyncMock(return_value=[]),
            ):
                response = client.get(
                    "/api/commission-categories",
                    headers={"Authorization": "Bearer faketoken"},
                )
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(saved)

        assert response.status_code == 200
        assert response.json() == []

    def test_create_blocks_free_tier(self):
        saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()
        app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: (
            self._with_subscription("free")
        )
        try:
            with patch(
                "api.routes.commission_categories.create",
                new=AsyncMock(),
            ) as mock_create:
                response = client.post(
                    "/api/commission-categories",
                    json={
                        "name": "服装",
                        "rfbs_tier1_rate": 0.1,
                        "rfbs_tier2_rate": 0.08,
                        "rfbs_tier3_rate": 0.06,
                    },
                    headers={"Authorization": "Bearer faketoken"},
                )
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(saved)

        assert response.status_code == 403
        assert response.json()["detail"] == "此功能需要专业版或更高订阅等级"
        mock_create.assert_not_awaited()

    def test_update_blocks_efficiency_tier(self):
        saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()
        app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: (
            self._with_subscription("efficiency")
        )
        try:
            with (
                patch(
                    "api.routes.commission_categories.get_by_id",
                    new=AsyncMock(return_value={"id": 1}),
                ),
                patch(
                    "api.routes.commission_categories.update",
                    new=AsyncMock(),
                ) as mock_update,
            ):
                response = client.patch(
                    "/api/commission-categories/1",
                    json={"name": "新名称"},
                    headers={"Authorization": "Bearer faketoken"},
                )
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(saved)

        assert response.status_code == 403
        assert response.json()["detail"] == "此功能需要专业版或更高订阅等级"
        mock_update.assert_not_awaited()

    def test_delete_blocks_free_tier(self):
        saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()
        app.dependency_overrides[dependencies.get_user_with_subscription] = lambda: (
            self._with_subscription("free")
        )
        try:
            with patch(
                "api.routes.commission_categories.soft_delete",
                new=AsyncMock(return_value=True),
            ) as mock_delete:
                response = client.delete(
                    "/api/commission-categories/1",
                    headers={"Authorization": "Bearer faketoken"},
                )
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(saved)

        assert response.status_code == 403
        assert response.json()["detail"] == "此功能需要专业版或更高订阅等级"
        mock_delete.assert_not_awaited()
