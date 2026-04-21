"""Password recovery route tests."""

# pyright: reportUnusedFunction=false

from datetime import timedelta
import time
import bcrypt
from unittest.mock import patch

import pytest

from api import dependencies
from api.main import app
from api.routes.auth import recover_start_limiter, recover_verify_limiter
from database import get_db
from db.sessions_crud import insert_session
from models.session import ActiveSession
from models.user import User
from security.tokens import create_access_token
from services.password_reset_service import create_reset_token

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


@pytest.fixture(autouse=True)
def _allow_testserver_origin(monkeypatch):
    monkeypatch.setattr(dependencies, "_ALLOWED_ORIGINS", {"http://testserver"})


@pytest.fixture(autouse=True)
def _reset_recovery_limiters():
    recover_start_limiter.reset()
    recover_verify_limiter.reset()
    yield
    recover_start_limiter.reset()
    recover_verify_limiter.reset()


def _override_db(session):
    async def _get_db_override():
        yield session

    return _get_db_override


async def _prepare_recovery_user(db_session, test_user):
    user = await db_session.get(User, test_user["id"])
    user.security_q1 = "问题1"
    user.security_q2 = "问题2"
    user.security_a1 = bcrypt.hashpw(b"answer1", bcrypt.gensalt()).decode()
    user.security_a2 = bcrypt.hashpw(b"answer2", bcrypt.gensalt()).decode()
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_recover_start_returns_same_shape_for_existing_and_missing(
    client,
    db_session,
    test_user,
):
    user = await _prepare_recovery_user(db_session, test_user)

    existing = await client.post(
        "/api/auth/recover/start",
        json={"username": user.username},
        headers={"X-Forwarded-For": "203.0.113.31"},
    )
    missing = await client.post(
        "/api/auth/recover/start",
        json={"username": "missing-user"},
        headers={"X-Forwarded-For": "203.0.113.32"},
    )

    assert existing.status_code == 200
    assert missing.status_code == 200
    assert existing.json()["message"] == missing.json()["message"]
    assert len(existing.json()["questions"]) == 2
    assert len(missing.json()["questions"]) == 2
    assert missing.json()["questions"] == ["（保密）", "（保密）"]


@pytest.mark.asyncio
async def test_recover_start_rate_limit_single_ip_returns_429(client, db_session, test_user):
    user = await _prepare_recovery_user(db_session, test_user)
    headers = {"X-Forwarded-For": "203.0.113.33"}

    for _ in range(5):
        response = await client.post(
            "/api/auth/recover/start",
            json={"username": user.username},
            headers=headers,
        )
        assert response.status_code == 200

    response = await client.post(
        "/api/auth/recover/start",
        json={"username": user.username},
        headers=headers,
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "请求过于频繁，请稍后再试"


@pytest.mark.asyncio
async def test_recover_verify_correct_answers_returns_token(client, db_session, test_user):
    user = await _prepare_recovery_user(db_session, test_user)

    response = await client.post(
        "/api/auth/recover/verify",
        json={
            "username": user.username,
            "answer1": "answer1",
            "answer2": "answer2",
        },
        headers={"X-Forwarded-For": "203.0.113.34"},
    )

    assert response.status_code == 200
    assert isinstance(response.json()["reset_token"], str)


@pytest.mark.asyncio
async def test_recover_verify_wrong_answers_returns_generic_error(client, db_session, test_user):
    user = await _prepare_recovery_user(db_session, test_user)

    response = await client.post(
        "/api/auth/recover/verify",
        json={
            "username": user.username,
            "answer1": "wrong1",
            "answer2": "wrong2",
        },
        headers={"X-Forwarded-For": "203.0.113.35"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "验证失败，请检查您的回答"


@pytest.mark.asyncio
async def test_recover_verify_missing_user_matches_wrong_answer_bcrypt_count(
    client,
    db_session,
    test_user,
):
    user = await _prepare_recovery_user(db_session, test_user)

    with patch("bcrypt.checkpw", wraps=bcrypt.checkpw) as mock_checkpw:
        wrong_response = await client.post(
            "/api/auth/recover/verify",
            json={
                "username": user.username,
                "answer1": "wrong1",
                "answer2": "wrong2",
            },
            headers={"X-Forwarded-For": "203.0.113.36"},
        )
        wrong_calls = mock_checkpw.call_count

    with patch("bcrypt.checkpw", wraps=bcrypt.checkpw) as mock_checkpw:
        missing_response = await client.post(
            "/api/auth/recover/verify",
            json={
                "username": "missing-user",
                "answer1": "wrong1",
                "answer2": "wrong2",
            },
            headers={"X-Forwarded-For": "203.0.113.46"},
        )
        missing_calls = mock_checkpw.call_count

    assert wrong_response.status_code == 400
    assert missing_response.status_code == 400
    assert wrong_response.json()["detail"] == "验证失败，请检查您的回答"
    assert missing_response.json()["detail"] == "验证失败，请检查您的回答"
    assert wrong_calls == 2
    assert missing_calls == 2


@pytest.mark.asyncio
async def test_recover_verify_rate_limit_single_ip_returns_429(client, db_session, test_user):
    user = await _prepare_recovery_user(db_session, test_user)
    headers = {"X-Forwarded-For": "203.0.113.37"}
    payload = {
        "username": user.username,
        "answer1": "wrong1",
        "answer2": "wrong2",
    }

    for _ in range(5):
        response = await client.post(
            "/api/auth/recover/verify",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 400

    response = await client.post(
        "/api/auth/recover/verify",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "请求过于频繁，请稍后再试"


@pytest.mark.asyncio
async def test_recover_reset_valid_token_clears_active_sessions(client, db_session, test_user):
    await _prepare_recovery_user(db_session, test_user)
    session_id = f"recover-reset-session-{int(time.time() * 1000)}"
    await insert_session(
        db_session,
        session_id=session_id,
        user_id=test_user["id"],
        ip_address="127.0.0.1",
        user_agent="pytest",
        now=1234.0,
    )
    await db_session.commit()

    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        token = await create_reset_token(test_user["id"])
        response = await client.post(
            "/api/auth/recover/reset",
            json={
                "reset_token": token,
                "new_password": "NewStrongP@ss123!",
            },
            headers={"X-Forwarded-For": "203.0.113.38"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["message"] == "密码已重置，请重新登录"

    db_session.expire_all()
    session_row = await db_session.get(ActiveSession, session_id)
    assert session_row is not None
    assert session_row.is_active is False


@pytest.mark.asyncio
async def test_recover_reset_replay_token_returns_400(client, db_session, test_user):
    await _prepare_recovery_user(db_session, test_user)

    token = await create_reset_token(test_user["id"])
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        first = await client.post(
            "/api/auth/recover/reset",
            json={
                "reset_token": token,
                "new_password": "NewStrongP@ss123!",
            },
            headers={"X-Forwarded-For": "203.0.113.39"},
        )
        second = await client.post(
            "/api/auth/recover/reset",
            json={
                "reset_token": token,
                "new_password": "NewStrongP@ss123!",
            },
            headers={"X-Forwarded-For": "203.0.113.39"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"] == "令牌无效或已过期"


async def test_recover_reset_expired_token_returns_400(client):
    expired = create_access_token(
        user_id=1,
        username="password-reset",
        expires_delta=timedelta(seconds=-1),
        extra_claims={"purpose": "password_reset", "jti": "expired-reset"},
    )
    response = await client.post(
        "/api/auth/recover/reset",
        json={
            "reset_token": expired,
            "new_password": "NewStrongP@ss123!",
        },
        headers={"X-Forwarded-For": "203.0.113.40"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "令牌无效或已过期"


@pytest.mark.asyncio
async def test_recover_reset_weak_password_returns_400(client, db_session, test_user):
    await _prepare_recovery_user(db_session, test_user)

    token = await create_reset_token(test_user["id"])
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        response = await client.post(
            "/api/auth/recover/reset",
            json={"reset_token": token, "new_password": "weak"},
            headers={"X-Forwarded-For": "203.0.113.41"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert response.json()["detail"] == "密码不符合要求"
