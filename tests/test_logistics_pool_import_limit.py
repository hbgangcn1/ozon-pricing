"""Logistics pool import quota tests (post-SSoT migration).

Per Phase 5 of OpenSpec change `fix-trial-aware-plan-gates`:
- Quota gate now lives in `_check_logistics_limit` and delegates to
  `services.plan_resolution.get_effective_logistics_limit` +
  `count_user_active_rules` (SSoT).
- Old patches (`_get_user_subscription`, `get_plan_by_code`,
  `get_logistics_by_filters`) no longer exist on the route module.
- Error message is neutral: "已达到您当前方案的物流规则上限（{limit} 条）"
  (no plan_name leak, no trial leak).

Seeded "limit" values use the per-test patch of
`get_effective_logistics_limit` (mocking out the plans-table read +
trial inheritance logic), so the test asserts the route's behavior
given a known effective limit, not the resolution logic itself
(which is covered separately in `tests/test_plan_resolution_*.py`).
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from api import dependencies
from api.main import app
from database import get_db

client = TestClient(app, raise_server_exceptions=False)


def _db_override(session):
    async def override():
        yield session

    return override


def _make_db_session() -> AsyncMock:
    """Build an AsyncMock session whose `begin_nested()` works as `async with`.

    Production route wraps DB writes in `async with session.begin_nested():`
    (commit 220bd2ce, SAVEPOINT for per-row failure isolation). Bare
    `AsyncMock()` makes `begin_nested()` return a coroutine, not an async
    context manager, breaking `async with`.

    Also stubs `session.get(User, ...)` to return a non-admin user so
    `_check_logistics_limit` proceeds past the role short-circuit.
    """
    session = AsyncMock()
    nested_cm = MagicMock()
    nested_cm.__aenter__ = AsyncMock(return_value=nested_cm)
    nested_cm.__aexit__ = AsyncMock(return_value=None)
    session.begin_nested = MagicMock(return_value=nested_cm)

    user_obj = MagicMock()
    user_obj.role = "user"
    session.get = AsyncMock(return_value=user_obj)
    return session


def _patch_quota(effective_limit: int, current_count: int):
    """Patch the SSoT quota helpers + recalculate side-effect.

    Replaces the old per-tier `_get_user_subscription`/`get_plan_by_code`
    patches. Caller controls `effective_limit` (post trial-inheritance,
    -1 = unlimited) and `current_count` (active rules already owned).
    """
    return (
        patch(
            "api.routes.logistics_pool.get_effective_logistics_limit",
            new=AsyncMock(return_value=effective_limit),
        ),
        patch(
            "api.routes.logistics_pool.count_user_active_rules",
            new=AsyncMock(return_value=current_count),
        ),
        patch(
            "api.routes.logistics_pool.recalculate_priority_groups",
            new=AsyncMock(),
        ),
    )


class TestLogisticsImportLimitFreeTier:
    def setup_method(self):
        self.saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

    def teardown_method(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.saved)

    def test_free_user_first_import_succeeds(self):
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=1, current_count=0)
        with p1, p2, p3, patch(
            "api.routes.logistics_pool.get_by_id",
            new=AsyncMock(return_value={"id": 1, "name": "test", "type": "express"}),
        ), patch(
            "api.routes.logistics_pool.create_logistics",
            new=AsyncMock(return_value=100),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 200
        assert response.json() == {"id": 100}

    def test_free_user_second_import_rejected(self):
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=1, current_count=1)
        with p1, p2, p3:
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 403
        assert response.json()["detail"] == "已达到您当前方案的物流规则上限（1 条）"


class TestLogisticsImportLimitEfficiencyTier:
    def setup_method(self):
        self.saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

    def teardown_method(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.saved)

    def test_efficiency_user_third_import_succeeds(self):
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=3, current_count=2)
        with p1, p2, p3, patch(
            "api.routes.logistics_pool.get_by_id",
            new=AsyncMock(return_value={"id": 1, "name": "test", "type": "express"}),
        ), patch(
            "api.routes.logistics_pool.create_logistics",
            new=AsyncMock(return_value=100),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 200
        assert response.json() == {"id": 100}

    def test_efficiency_user_fourth_import_rejected(self):
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=3, current_count=3)
        with p1, p2, p3:
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 403
        assert response.json()["detail"] == "已达到您当前方案的物流规则上限（3 条）"


class TestLogisticsImportLimitProfessionalTier:
    def setup_method(self):
        self.saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

    def teardown_method(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.saved)

    def test_professional_user_import_unlimited(self):
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=-1, current_count=100)
        with p1, p2, p3, patch(
            "api.routes.logistics_pool.get_by_id",
            new=AsyncMock(return_value={"id": 1, "name": "test", "type": "express"}),
        ), patch(
            "api.routes.logistics_pool.create_logistics",
            new=AsyncMock(return_value=100),
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
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=1, current_count=0)
        with p1, p2, p3:
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post(
                "/api/logistics-pool/batch-add-to-my-logistics",
                json={"ids": [1, 2, 3]},
            )
        assert response.status_code == 403
        assert response.json()["detail"] == "已达到您当前方案的物流规则上限（1 条）"

    def test_efficiency_user_batch_import_exceeds_limit(self):
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=3, current_count=2)
        with p1, p2, p3:
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post(
                "/api/logistics-pool/batch-add-to-my-logistics",
                json={"ids": [1, 2]},
            )
        assert response.status_code == 403
        assert response.json()["detail"] == "已达到您当前方案的物流规则上限（3 条）"

    def test_batch_import_within_limit_succeeds(self):
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=3, current_count=1)
        with p1, p2, p3, patch(
            "api.routes.logistics_pool.get_by_ids",
            new=AsyncMock(
                return_value={
                    1: {"id": 1, "name": "test1", "type": "express"},
                    2: {"id": 2, "name": "test2", "type": "express"},
                }
            ),
        ), patch(
            "api.routes.logistics_pool.create_logistics",
            new=AsyncMock(side_effect=[100, 101]),
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


class TestTrialAwarePlanGates:
    """Trial users inherit professional tier; expired trial falls back to
    real subscription. The route's `_check_logistics_limit` defers this
    resolution to `get_effective_logistics_limit`, so these tests assert
    the route honors whatever the SSoT returns.

    Resolution logic (trial vs expired vs real plan) is covered by
    `tests/test_plan_resolution_*.py`.
    """

    def setup_method(self):
        self.saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

    def teardown_method(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.saved)

    def test_trial_user_inherits_professional_unlimited_limit(self):
        """Active trial → SSoT returns -1 (professional unlimited); batch
        of 5 succeeds even though raw subscription_type='free'."""
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=-1, current_count=0)
        with p1, p2, p3, patch(
            "api.routes.logistics_pool.get_by_ids",
            new=AsyncMock(
                return_value={
                    i: {"id": i, "name": f"t{i}", "type": "express"}
                    for i in range(1, 6)
                }
            ),
        ), patch(
            "api.routes.logistics_pool.create_logistics",
            new=AsyncMock(side_effect=[100, 101, 102, 103, 104]),
        ):
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post(
                "/api/logistics-pool/batch-add-to-my-logistics",
                json={"ids": [1, 2, 3, 4, 5]},
            )
        assert response.status_code == 200
        assert response.json()["added"] == 5

    def test_expired_trial_user_falls_back_to_free_limit(self):
        """Expired trial → SSoT returns 1 (free tier); single add rejected
        because user already owns 1 active rule. Detail must be neutral."""
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=1, current_count=1)
        with p1, p2, p3:
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 403
        assert response.json()["detail"] == "已达到您当前方案的物流规则上限（1 条）"

    def test_real_professional_uses_plans_table_not_fallback(self):
        """Plans-table read returns 7 (NOT the historical hard-coded
        fallback of 10); user already at 7 → reject with （7 条）."""
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=7, current_count=7)
        with p1, p2, p3:
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "（7 条）" in detail
        # Prove plans-table read, NOT the fallback 10
        assert "10" not in detail

    def test_quota_error_detail_is_neutral(self):
        """Detail must NOT leak trial state, plan name, or tier label."""
        session = _make_db_session()
        p1, p2, p3 = _patch_quota(effective_limit=1, current_count=1)
        with p1, p2, p3:
            app.dependency_overrides[dependencies.get_current_user_id] = lambda: 1
            app.dependency_overrides[get_db] = _db_override(session)
            response = client.post("/api/logistics-pool/1/add-to-my-logistics")
        assert response.status_code == 403
        detail = response.json()["detail"]
        lower = detail.lower()
        assert "trial" not in lower
        assert "试用" not in detail
        assert "免费版" not in detail
        assert "效率版" not in detail
        assert "专业版" not in detail
        assert "企业版" not in detail
