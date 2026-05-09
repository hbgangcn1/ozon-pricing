# pyright: reportUnusedFunction=false, reportUnusedClass=false
from io import BytesIO
import time
from unittest.mock import AsyncMock, patch
from typing import Any, cast

from fastapi import HTTPException
import openpyxl
import pytest

from api.dependencies import (
    get_user_with_subscription,
    require_admin,
)
from api.main import app
from db.commission_categories import create as create_category


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class _RecordingSession:
    def __init__(self, scalar_results=None, execute_results=None):
        self.scalar_results = list(scalar_results or [])
        self.execute_results = list(execute_results or [])
        self.scalar_statements = []
        self.execute_statements = []
        self.added = []
        self._next_id = 1

    async def scalar(self, stmt):
        self.scalar_statements.append(stmt)
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    async def execute(self, stmt):
        self.execute_statements.append(stmt)
        return self.execute_results.pop(0)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1


@pytest.fixture(autouse=True)
def _restore_dependency_overrides():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def _unique_id() -> int:
    return int(time.time() * 1000000)


def _unique_name(prefix: str) -> str:
    return f"{prefix}_{_unique_id()}"


def _commission_payload(name: str) -> dict:
    return {
        "name": name,
        "rfbs_tier1_rate": 0.12,
        "rfbs_tier2_rate": 0.1,
        "rfbs_tier3_rate": 0.08,
    }


def _commission_create_data(name: str, user_id: int) -> dict:
    return {
        "name": name,
        "user_id": user_id,
        "rfbs_tier1_rate": 0.12,
        "rfbs_tier2_rate": 0.1,
        "rfbs_tier3_rate": 0.08,
        "fbp_tier1_rate": 0.11,
        "fbp_tier2_rate": 0.09,
        "fbp_tier3_rate": 0.07,
        "is_active": 1,
    }


def _category_row(category_id: int, user_id: int, name: str) -> dict:
    return {
        "id": category_id,
        "user_id": user_id,
        "name": name,
        "rfbs_tier1_rate": 0.12,
        "rfbs_tier2_rate": 0.1,
        "rfbs_tier3_rate": 0.08,
        "fbp_tier1_rate": 0.11,
        "fbp_tier2_rate": 0.09,
        "fbp_tier3_rate": 0.07,
        "is_active": 1,
    }


def _override_subscription_user(
    user_id: int,
    subscription_type: str,
    role: str = "user",
    trial_expires_at: int = 0,
) -> None:
    app.dependency_overrides[get_user_with_subscription] = lambda: {
        "id": user_id,
        "username": f"user_{user_id}",
        "role": role,
        "user_type": "permanent",
        "subscription_type": subscription_type,
        "remaining_calculations": 100,
        "trial_used": 1 if trial_expires_at else 0,
        "trial_started_at": 0,
        "trial_expires_at": trial_expires_at,
        "trial_plan_at_start": subscription_type if trial_expires_at else "",
    }


def _override_non_admin() -> None:
    def _raise_forbidden():
        raise HTTPException(status_code=403, detail="需要管理员权限")

    app.dependency_overrides[require_admin] = _raise_forbidden


def _build_product_workbook() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["name", "weight_g", "length_cm", "width_cm", "height_cm"])
    sheet.append(["Enterprise Product", 120, 10, 8, 6])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


def _stmt_params(stmt) -> dict:
    return stmt.compile().params


def _await_args(mock: AsyncMock):
    assert mock.await_args is not None
    return mock.await_args


class TestCommissionUserIsolation:
    async def test_user_a_cannot_see_user_b_commission_categories(self, client):
        user_a = _unique_id()
        own_name = _unique_name("own_category")
        _override_subscription_user(user_a, "professional")

        with patch(
            "api.routes.commission_categories.get_all",
            new=AsyncMock(return_value=[_category_row(1, user_a, own_name)]),
        ) as mock_get_all:
            response = await client.get("/api/commission-categories")

        assert response.status_code == 200
        assert response.json() == [_category_row(1, user_a, own_name)]
        assert _await_args(mock_get_all).kwargs == {
            "include_inactive": False,
            "user_id": user_a,
        }

    async def test_user_a_cannot_update_or_delete_user_b_commission_category(
        self,
        client,
    ):
        user_a = _unique_id()
        _override_subscription_user(user_a, "professional")

        with (
            patch(
                "api.routes.commission_categories.get_by_id",
                new=AsyncMock(return_value=None),
            ) as mock_get_by_id,
            patch(
                "api.routes.commission_categories.update",
                new=AsyncMock(),
            ) as mock_update,
            patch(
                "api.routes.commission_categories.soft_delete",
                new=AsyncMock(return_value=False),
            ) as mock_soft_delete,
        ):
            patch_response = await client.patch(
                "/api/commission-categories/99",
                json={"name": _unique_name("updated")},
            )
            delete_response = await client.delete("/api/commission-categories/99")

        assert patch_response.status_code == 404
        assert patch_response.json()["detail"] == "佣金类目不存在"
        assert delete_response.status_code == 404
        assert delete_response.json()["detail"] == "佣金类目不存在"
        mock_get_by_id.assert_awaited_once()
        mock_update.assert_not_awaited()
        mock_soft_delete.assert_awaited_once()

    async def test_duplicate_category_name_for_same_user_fails(self):
        user_id = 1
        name = "同名类目"
        session = _RecordingSession(scalar_results=[123])

        result = await create_category(
            cast(Any, session),
            _commission_create_data(name, user_id),
        )

        assert result is None
        params = _stmt_params(session.scalar_statements[0])
        assert params["name_1"] == name
        assert params["user_id_1"] == user_id

    async def test_different_users_can_have_same_category_name(self):
        name = "共享类目"
        session = _RecordingSession(scalar_results=[None, None])

        first_id = await create_category(
            cast(Any, session), _commission_create_data(name, 1)
        )
        second_id = await create_category(
            cast(Any, session), _commission_create_data(name, 2)
        )

        assert first_id == 1
        assert second_id == 2
        first_params = _stmt_params(session.scalar_statements[0])
        second_params = _stmt_params(session.scalar_statements[1])
        assert first_params["name_1"] == name
        assert first_params["user_id_1"] == 1
        assert second_params["name_1"] == name
        assert second_params["user_id_1"] == 2


class TestCommissionSubscriptionGating:
    async def test_free_tier_user_gets_403_on_commission_category_create(self, client):
        _override_subscription_user(_unique_id(), "free")

        with patch(
            "api.routes.commission_categories.create",
            new=AsyncMock(),
        ) as mock_create:
            response = await client.post(
                "/api/commission-categories",
                json=_commission_payload(_unique_name("free_blocked")),
            )

        assert response.status_code == 403
        mock_create.assert_not_awaited()

    async def test_efficiency_tier_user_gets_403_on_commission_category_create(
        self,
        client,
    ):
        _override_subscription_user(_unique_id(), "efficiency")

        with patch(
            "api.routes.commission_categories.create",
            new=AsyncMock(),
        ) as mock_create:
            response = await client.post(
                "/api/commission-categories",
                json=_commission_payload(_unique_name("efficiency_blocked")),
            )

        assert response.status_code == 403
        mock_create.assert_not_awaited()

    async def test_professional_tier_user_can_create_commission_category(
        self,
        client,
    ):
        user_id = _unique_id()
        category_name = _unique_name("professional_allowed")
        _override_subscription_user(user_id, "professional")

        with (
            patch(
                "api.routes.commission_categories.create",
                new=AsyncMock(return_value=11),
            ) as mock_create,
            patch(
                "api.routes.commission_categories.get_by_id",
                new=AsyncMock(return_value=_category_row(11, user_id, category_name)),
            ) as mock_get_by_id,
        ):
            response = await client.post(
                "/api/commission-categories",
                json=_commission_payload(category_name),
            )

        assert response.status_code == 201
        assert response.json()["user_id"] == user_id
        created_data = _await_args(mock_create).args[1]
        assert created_data["user_id"] == user_id
        mock_get_by_id.assert_awaited_once()

    async def test_enterprise_tier_user_can_create_commission_category(
        self,
        client,
    ):
        user_id = _unique_id()
        category_name = _unique_name("enterprise_allowed")
        _override_subscription_user(user_id, "enterprise")

        with (
            patch(
                "api.routes.commission_categories.create",
                new=AsyncMock(return_value=22),
            ) as mock_create,
            patch(
                "api.routes.commission_categories.get_by_id",
                new=AsyncMock(return_value=_category_row(22, user_id, category_name)),
            ),
        ):
            response = await client.post(
                "/api/commission-categories",
                json=_commission_payload(category_name),
            )

        assert response.status_code == 201
        assert response.json()["user_id"] == user_id
        created_data = _await_args(mock_create).args[1]
        assert created_data["user_id"] == user_id

    async def test_free_tier_user_blocked_on_get_commission_categories(self, client):
        user_id = _unique_id()
        _override_subscription_user(user_id, "free")

        with patch(
            "api.routes.commission_categories.get_all",
            new=AsyncMock(return_value=[]),
        ) as mock_get_all:
            response = await client.get("/api/commission-categories")

        assert response.status_code == 403
        assert response.json()["detail"] == "当前方案暂不支持此功能"
        mock_get_all.assert_not_awaited()

    async def test_commission_category_403_contains_chinese_message(self, client):
        _override_subscription_user(_unique_id(), "free")

        response = await client.post(
            "/api/commission-categories",
            json=_commission_payload(_unique_name("message_check")),
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "当前方案暂不支持此功能"

    async def test_free_tier_trial_active_user_can_create_commission_category(
        self,
        client,
    ):
        user_id = _unique_id()
        category_name = _unique_name("free_trial_allowed")
        future_expiry = int(time.time()) + 3600
        _override_subscription_user(
            user_id, "free", trial_expires_at=future_expiry,
        )

        with (
            patch(
                "api.routes.commission_categories.create",
                new=AsyncMock(return_value=33),
            ),
            patch(
                "api.routes.commission_categories.get_by_id",
                new=AsyncMock(return_value=_category_row(33, user_id, category_name)),
            ),
        ):
            response = await client.post(
                "/api/commission-categories",
                json=_commission_payload(category_name),
            )

        assert response.status_code == 201
        assert response.json()["user_id"] == user_id

    async def test_efficiency_tier_trial_active_user_can_get_commission_categories(
        self,
        client,
    ):
        user_id = _unique_id()
        category_name = _unique_name("eff_trial_get")
        future_expiry = int(time.time()) + 3600
        _override_subscription_user(
            user_id, "efficiency", trial_expires_at=future_expiry,
        )

        with patch(
            "api.routes.commission_categories.get_all",
            new=AsyncMock(return_value=[_category_row(44, user_id, category_name)]),
        ):
            response = await client.get("/api/commission-categories")

        assert response.status_code == 200
        assert response.json()[0]["user_id"] == user_id

    async def test_free_tier_trial_expired_user_blocked_on_create(self, client):
        user_id = _unique_id()
        past_expiry = int(time.time()) - 3600
        _override_subscription_user(
            user_id, "free", trial_expires_at=past_expiry,
        )

        with patch(
            "api.routes.commission_categories.create",
            new=AsyncMock(),
        ) as mock_create:
            response = await client.post(
                "/api/commission-categories",
                json=_commission_payload(_unique_name("expired_blocked")),
            )

        assert response.status_code == 403
        assert response.json()["detail"] == "当前方案暂不支持此功能"
        mock_create.assert_not_awaited()

    async def test_free_tier_trial_expired_user_blocked_on_get(self, client):
        user_id = _unique_id()
        past_expiry = int(time.time()) - 3600
        _override_subscription_user(
            user_id, "free", trial_expires_at=past_expiry,
        )

        with patch(
            "api.routes.commission_categories.get_all",
            new=AsyncMock(return_value=[_category_row(55, user_id, "preserved")]),
        ) as mock_get_all:
            response = await client.get("/api/commission-categories")

        assert response.status_code == 403
        assert response.json()["detail"] == "当前方案暂不支持此功能"
        mock_get_all.assert_not_awaited()


class TestExcelImportSubscriptionGating:
    async def test_free_tier_user_gets_403_on_product_import_preview(self, client):
        _override_subscription_user(_unique_id(), "free")

        response = await client.post(
            "/api/products/import/preview",
            files={"file": ("products.xlsx", _build_product_workbook(), XLSX_MIME)},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "此功能需要企业版或更高订阅等级"

    async def test_professional_tier_user_gets_403_on_product_import_preview(
        self,
        client,
    ):
        _override_subscription_user(_unique_id(), "professional")

        response = await client.post(
            "/api/products/import/preview",
            files={"file": ("products.xlsx", _build_product_workbook(), XLSX_MIME)},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "此功能需要企业版或更高订阅等级"

    async def test_enterprise_tier_user_can_post_product_import_preview(self, client):
        _override_subscription_user(_unique_id(), "enterprise")

        response = await client.post(
            "/api/products/import/preview",
            files={"file": ("products.xlsx", _build_product_workbook(), XLSX_MIME)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["columns"] == [
            "name",
            "weight_g",
            "length_cm",
            "width_cm",
            "height_cm",
        ]
        assert data["preview_rows"][0]["name"] == "Enterprise Product"

    async def test_free_tier_user_gets_403_on_product_import_confirm(self, client):
        _override_subscription_user(_unique_id(), "free")

        response = await client.post(
            "/api/products/import/confirm",
            json={
                "rows": [{"name": "Blocked Product"}],
                "column_mapping": {"name": "name"},
                "conflict_action": "skip",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "此功能需要企业版或更高订阅等级"

    async def test_non_admin_gets_403_on_logistics_pool_import(self, client):
        _override_non_admin()
        _override_subscription_user(_unique_id(), "enterprise")

        response = await client.post(
            "/api/logistics-pool/import",
            files={"file": ("pool.xlsx", _build_product_workbook(), XLSX_MIME)},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "需要管理员权限"
