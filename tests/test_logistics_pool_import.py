from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import dependencies
from api.main import app
from database import get_db

client = TestClient(app, raise_server_exceptions=False)


def _db_override(session):
    async def override():
        yield session

    return override


def test_import_logistics_pool_returns_423_for_permission_error():
    session = AsyncMock()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    app.dependency_overrides[dependencies.require_admin] = lambda: 1
    app.dependency_overrides[get_db] = _db_override(session)
    try:
        with patch(
            "api.routes.logistics_pool.parse_file",
            side_effect=PermissionError("[WinError 32] file locked"),
        ):
            response = client.post(
                "/api/logistics-pool/import",
                files={
                    "file": (
                        "FBP_List_of_services.xlsx",
                        b"dummy",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)

    assert response.status_code == 423
    assert response.json() == {"detail": "文件被占用，请关闭OneDrive同步后重试"}


def test_import_logistics_pool_blocks_non_admin():
    """Regression: endpoint MUST be admin-gated.

    Guards against accidental removal of the
    ``dependencies=[Depends(require_admin)]`` decorator on
    ``POST /api/logistics-pool/import``. We override ``require_admin``
    to raise 403 (mirroring its real behavior for non-admin callers)
    and assert the endpoint propagates the rejection.
    """
    session = AsyncMock()

    def _raise_admin_required():
        raise HTTPException(status_code=403, detail="需要管理员权限")

    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    app.dependency_overrides[dependencies.require_admin] = _raise_admin_required
    app.dependency_overrides[get_db] = _db_override(session)
    try:
        response = client.post(
            "/api/logistics-pool/import",
            files={
                "file": (
                    "FBP_List_of_services.xlsx",
                    b"dummy",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)

    assert response.status_code == 403
    assert response.json() == {"detail": "需要管理员权限"}
