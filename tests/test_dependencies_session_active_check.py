# pyright: reportPrivateUsage=false

from uuid import uuid4

from fastapi import HTTPException

import pytest

from api.dependencies import _get_user
from db.sessions_crud import insert_session
from models.session import ActiveSession
from security.tokens import create_access_token


@pytest.mark.asyncio
async def test_get_user_rejects_inactive_session_with_reason(db_session, test_user):
    sid = f"dep-inactive-{uuid4().hex}"
    await insert_session(
        db_session,
        session_id=sid,
        user_id=test_user["id"],
        ip_address="127.0.0.1",
        user_agent="pytest",
        now=1.0,
    )
    session_row = await db_session.get(ActiveSession, sid)
    session_row.is_active = False
    session_row.inactive_reason = "kicked_by_new_login"
    await db_session.commit()

    token = create_access_token(
        user_id=test_user["id"],
        username=test_user["username"],
        extra_claims={"sid": sid},
    )

    with pytest.raises(HTTPException) as exc_info:
        await _get_user(token, db_session)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == {
        "error": "会话已失效",
        "reason": "kicked_by_new_login",
    }


@pytest.mark.asyncio
async def test_get_user_rejects_missing_session_row(db_session, test_user):
    token = create_access_token(
        user_id=test_user["id"],
        username=test_user["username"],
        extra_claims={"sid": f"missing-dep-{uuid4().hex}"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await _get_user(token, db_session)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == {"error": "会话已失效", "reason": None}


@pytest.mark.asyncio
async def test_get_user_accepts_active_session(db_session, test_user):
    sid = f"dep-active-{uuid4().hex}"
    await insert_session(
        db_session,
        session_id=sid,
        user_id=test_user["id"],
        ip_address="127.0.0.1",
        user_agent="pytest",
        now=1.0,
    )
    await db_session.commit()

    token = create_access_token(
        user_id=test_user["id"],
        username=test_user["username"],
        extra_claims={"sid": sid},
    )

    user = await _get_user(token, db_session)
    assert user.id == test_user["id"]
    assert user.username == test_user["username"]


@pytest.mark.asyncio
async def test_get_user_without_sid_skips_session_check(db_session, test_user):
    token = create_access_token(
        user_id=test_user["id"],
        username=test_user["username"],
    )

    user = await _get_user(token, db_session)
    assert user.id == test_user["id"]
    assert user.username == test_user["username"]
