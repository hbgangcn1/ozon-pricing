"""Security question API tests."""

# pyright: reportUnusedFunction=false

import time
from uuid import uuid4

import bcrypt
import pytest

from api import dependencies
from api.main import app
from database import AsyncSessionLocal, get_db
from db.password import hash_password
from models.user import User
from password_recovery import verify_security_answers
from security.tokens import create_access_token
from services.password_reset_service import create_reset_token


def _override_db(session):
    async def _get_db_override():
        yield session
        await session.commit()

    return _get_db_override


async def _create_test_user(db_session, *, security_question=None, security_answer=None):
    username = f"qatest_setq_{uuid4().hex[:8]}"
    if security_answer is not None and not security_answer.startswith("$2"):
        security_answer = bcrypt.hashpw(
            security_answer.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
    user = User(
        username=username,
        password=hash_password("TestP@ss123456"),
        role="user",
        user_type="free",
        subscription_type="free",
        remaining_calculations=10,
        created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        is_test_user=1,
        security_q1=security_question,
        security_a1=security_answer,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    user_id = int(user.id)
    token = create_access_token(user_id, username, role=user.role or "user")
    return user_id, username, token


async def _post_security_question(client, db_session, token, payload):
    old_overrides = {
        dependencies.get_current_user: app.dependency_overrides.pop(
            dependencies.get_current_user, None
        ),
        dependencies.get_current_user_id: app.dependency_overrides.pop(
            dependencies.get_current_user_id, None
        ),
        dependencies.require_admin: app.dependency_overrides.pop(
            dependencies.require_admin, None
        ),
    }
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        return await client.post(
            "/api/auth/security-question",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        for dep, override in old_overrides.items():
            if override is not None:
                app.dependency_overrides[dep] = override


@pytest.mark.asyncio
async def test_set_security_question_success_first_time(client, db_session):
    user_id, _, token = await _create_test_user(db_session)

    response = await _post_security_question(
        client,
        db_session,
        token,
        {
            "question": "您母亲的姓名是？",
            "answer": "AnswerOne",
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["message"] == "安全问题已设置"

    async with AsyncSessionLocal() as verify_session:
        persisted = await verify_session.get(User, user_id)
    if persisted is None:
        raise AssertionError("persisted user missing")
    assert persisted.security_q1 == "您母亲的姓名是？"
    assert persisted.security_a1 is not None
    assert persisted.security_a1 != ""


@pytest.mark.asyncio
async def test_set_security_question_conflict_already_set(client, db_session):
    user_id, _, token = await _create_test_user(
        db_session,
        security_question="您父亲的姓名是？",
        security_answer="OriginalAnswer",
    )

    response = await _post_security_question(
        client,
        db_session,
        token,
        {
            "question": "您出生的城市是？",
            "answer": "AnotherAnswer",
        },
    )

    assert response.status_code == 409
    assert "已设置" in response.json()["detail"] or "无法重复" in response.json()["detail"]

    async with AsyncSessionLocal() as verify_session:
        persisted = await verify_session.get(User, user_id)
    if persisted is None:
        raise AssertionError("persisted user missing")
    assert persisted.security_q1 == "您父亲的姓名是？"


@pytest.mark.asyncio
async def test_set_security_question_invalid_question_returns_422(client, db_session):
    _, _, token = await _create_test_user(db_session)

    response = await _post_security_question(
        client,
        db_session,
        token,
        {
            "question": "这不是预设问题",
            "answer": "ValidAnswer",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_set_security_question_empty_answer_returns_422(client, db_session):
    _, _, token = await _create_test_user(db_session)

    response = await _post_security_question(
        client,
        db_session,
        token,
        {
            "question": "您出生的城市是？",
            "answer": "   ",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_set_security_question_no_auth_returns_401(client, db_session):
    await _create_test_user(db_session)

    old_overrides = {
        dependencies.get_current_user: app.dependency_overrides.pop(
            dependencies.get_current_user, None
        ),
        dependencies.get_current_user_id: app.dependency_overrides.pop(
            dependencies.get_current_user_id, None
        ),
        dependencies.require_admin: app.dependency_overrides.pop(
            dependencies.require_admin, None
        ),
    }
    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        response = await client.post(
            "/api/auth/security-question",
            json={
                "question": "您小学班主任的姓名是？",
                "answer": "ValidAnswer",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        for dep, override in old_overrides.items():
            if override is not None:
                app.dependency_overrides[dep] = override

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_set_security_question_answer_normalized_before_persist(client, db_session):
    _, username, token = await _create_test_user(db_session)

    response = await _post_security_question(
        client,
        db_session,
        token,
        {
            "question": "您最喜欢的宠物名字是？",
            "answer": "  Hello  ",
        },
    )

    assert response.status_code == 200

    for answer in ["hello", "HELLO", "  hello"]:
        ok, message = await verify_security_answers(username, answer)
        assert ok is True
        assert message == "验证成功"


@pytest.mark.asyncio
async def test_set_then_recover_roundtrip(client, db_session):
    user_id, username, token = await _create_test_user(db_session)

    response = await _post_security_question(
        client,
        db_session,
        token,
        {
            "question": "您小学班主任的姓名是？",
            "answer": "RoundTripAnswer",
        },
    )

    assert response.status_code == 200

    ok, message = await verify_security_answers(username, "roundtripanswer")
    assert ok is True
    assert message == "验证成功"

    reset_token = await create_reset_token(user_id)
    assert isinstance(reset_token, str)
    assert reset_token
