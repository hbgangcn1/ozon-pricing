"""Tests for GET /api/statistics/orders endpoint."""

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from database import get_db  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def _admin_override():
    return 1


def _setup_admin():
    from api.dependencies import require_admin
    app.dependency_overrides[require_admin] = _admin_override


def _cleanup():
    app.dependency_overrides.clear()


MOCK_ORDERS_DATA = {
    "orders": [
        {
            "order_id": "ORD_001",
            "username": "robert",
            "amount": 99.0,
            "order_type": "professional",
            "status": "SUCCESS",
            "created_at": "1778000000",
        },
        {
            "order_id": "ORD_002",
            "username": "testuser",
            "amount": 49.0,
            "order_type": "efficiency",
            "status": "PENDING",
            "created_at": "1777000000",
        },
    ],
    "total": 2,
}


class TestAdminOrdersList:
    @patch("api.routes.statistics.get_all_orders", new_callable=AsyncMock)
    def test_admin_gets_orders(self, mock_get_all):
        mock_get_all.return_value = MOCK_ORDERS_DATA
        _setup_admin()
        mock_session = MagicMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get("/api/statistics/orders")
            assert r.status_code == 200
            data = r.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2
            assert data["items"][0]["order_id"] == "ORD_001"
            assert data["items"][0]["username"] == "robert"
        finally:
            _cleanup()

    def test_non_admin_gets_403(self):
        from api.dependencies import require_admin

        def _non_admin():
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="管理员权限不足")

        app.dependency_overrides[require_admin] = _non_admin
        try:
            r = client.get("/api/statistics/orders")
            assert r.status_code == 403
        finally:
            _cleanup()

    @patch("api.routes.statistics.get_all_orders", new_callable=AsyncMock)
    def test_search_by_username(self, mock_get_all):
        mock_get_all.return_value = MOCK_ORDERS_DATA
        _setup_admin()
        mock_session = MagicMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get("/api/statistics/orders?search=robert")
            assert r.status_code == 200
            mock_get_all.assert_called_once()
            call_kwargs = mock_get_all.call_args
            assert call_kwargs.kwargs.get("search") == "robert" or call_kwargs[1].get("search") == "robert"
        finally:
            _cleanup()

    @patch("api.routes.statistics.get_all_orders", new_callable=AsyncMock)
    def test_search_by_order_id(self, mock_get_all):
        mock_get_all.return_value = MOCK_ORDERS_DATA
        _setup_admin()
        mock_session = MagicMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get("/api/statistics/orders?search=ORD_001")
            assert r.status_code == 200
            mock_get_all.assert_called_once()
        finally:
            _cleanup()

    @patch("api.routes.statistics.get_all_orders", new_callable=AsyncMock)
    def test_status_filter(self, mock_get_all):
        mock_get_all.return_value = MOCK_ORDERS_DATA
        _setup_admin()
        mock_session = MagicMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get("/api/statistics/orders?status=SUCCESS")
            assert r.status_code == 200
            mock_get_all.assert_called_once()
            call_kwargs = mock_get_all.call_args
            assert call_kwargs.kwargs.get("status") == "SUCCESS" or call_kwargs[1].get("status") == "SUCCESS"
        finally:
            _cleanup()

    @patch("api.routes.statistics.get_all_orders", new_callable=AsyncMock)
    def test_date_range_filter(self, mock_get_all):
        mock_get_all.return_value = MOCK_ORDERS_DATA
        _setup_admin()
        mock_session = MagicMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_db] = override
        try:
            r = client.get("/api/statistics/orders?date_from=2026-01-01&date_to=2026-01-31")
            assert r.status_code == 200
            mock_get_all.assert_called_once()
        finally:
            _cleanup()
