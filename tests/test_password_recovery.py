import time
import bcrypt
import pytest
from sqlalchemy import select, update

from password_recovery import (
    log_password_recovery_event,
    get_user_security_questions,
    verify_security_answers,
    reset_password,
    unlock_user,
    admin_reset_password,
    get_password_recovery_logs,
    MAX_RESET_ATTEMPTS,
)
from models.user import User
from models.log import PasswordRecoveryLog


async def _set_user_security_questions(
    session,
    username,
    q1,
    a1_hash=None,
    locked_until=None,
    attempt_count=0,
):
    values = {
        "security_q1": q1,
        "reset_attempt_count": attempt_count,
    }
    if a1_hash:
        values["security_a1"] = a1_hash
    if locked_until is not None:
        values["reset_locked_until"] = locked_until
    await session.execute(
        update(User).where(User.username == username).values(**values)
    )
    await session.commit()


async def _set_legacy_q2_a2(session, username, q2, a2_hash):
    """直接写入老数据 q2/a2 字段（模拟旧版本残留数据）。"""
    await session.execute(
        update(User)
        .where(User.username == username)
        .values(security_q2=q2, security_a2=a2_hash)
    )
    await session.commit()


async def _get_user_field(session, username, *fields):
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if len(fields) == 1:
        return getattr(user, fields[0])
    return tuple(getattr(user, f) for f in fields)


class TestPasswordRecoveryLog:
    async def test_log_password_recovery_event(self, _clean_db, db_session):  # noqa: ARG001
        unique_user = f"test_log_user_{int(time.time() * 1000)}"
        await log_password_recovery_event(
            username=unique_user,
            event_type="request",
            success=True,
            attempt_count=0,
            ip_address="127.0.0.1",
        )

        result = await db_session.execute(
            select(PasswordRecoveryLog).where(
                PasswordRecoveryLog.username == unique_user
            )
        )
        entry = result.scalars().first()

        assert entry is not None
        assert entry.username == unique_user
        assert entry.event_type == "request"
        assert entry.success == 1


class TestGetUserSecurityQuestions:
    async def test_get_user_security_questions_not_exist(self, _clean_db):  # noqa: ARG001
        result = await get_user_security_questions("nonexistent_user")
        assert result is None

    async def test_get_user_security_questions_no_questions(self, _clean_db, test_user):  # noqa: ARG001
        username = test_user["username"]
        result = await get_user_security_questions(username)

        assert result is not None
        assert result["has_questions"] is False
        assert result["reset_attempt_count"] == 0

    async def test_get_user_security_questions_with_questions(
        self, _clean_db, test_user, db_session
    ):  # noqa: ARG001
        username = test_user["username"]
        await _set_user_security_questions(db_session, username, "问题1")

        result = await get_user_security_questions(username)

        assert result is not None
        assert result["has_questions"] is True
        assert result["security_q1"] == "问题1"
        assert "security_q2" not in result
        assert result["is_locked"] is False

    async def test_get_user_security_questions_locked(
        self, _clean_db, test_user, db_session
    ):  # noqa: ARG001
        username = test_user["username"]
        lock_until = time.time() + 3600

        await _set_user_security_questions(
            db_session,
            username,
            "问题1",
            locked_until=lock_until,
            attempt_count=MAX_RESET_ATTEMPTS,
        )

        result = await get_user_security_questions(username)

        assert result is not None
        assert result["is_locked"] is True
        if result["reset_locked_until"]:
            time_diff = abs(result["reset_locked_until"] - lock_until)
            assert time_diff < 120, (
                f"时间戳差异过大: {time_diff}秒，"
                f"期望: {lock_until}, 实际: {result['reset_locked_until']}"
            )

    async def test_get_user_security_questions_lock_expired(
        self, _clean_db, test_user, db_session
    ):  # noqa: ARG001
        username = test_user["username"]
        lock_until = time.time() - 100

        await _set_user_security_questions(
            db_session,
            username,
            "问题1",
            locked_until=lock_until,
            attempt_count=MAX_RESET_ATTEMPTS,
        )

        result = await get_user_security_questions(username)

        assert result is not None
        assert result["is_locked"] is False
        assert result["reset_locked_until"] is None
        assert result["reset_attempt_count"] == 0


class TestVerifySecurityAnswers:
    async def test_verify_security_answers_user_not_exist(self, _clean_db):  # noqa: ARG001
        is_valid, msg = await verify_security_answers("nonexistent_user", "答案1")
        assert is_valid is False
        assert "不存在" in msg

    async def test_verify_security_answers_no_questions(self, _clean_db, test_user):  # noqa: ARG001
        username = test_user["username"]
        is_valid, msg = await verify_security_answers(username, "答案1")
        assert is_valid is False
        assert "未设置" in msg

    async def test_verify_security_answers_locked(
        self, _clean_db, test_user, db_session
    ):  # noqa: ARG001
        username = test_user["username"]
        lock_until = time.time() + 3600
        a1_hash = bcrypt.hashpw("answer1".encode(), bcrypt.gensalt()).decode()

        await _set_user_security_questions(
            db_session,
            username,
            "问题1",
            a1_hash=a1_hash,
            locked_until=lock_until,
        )

        is_valid, msg = await verify_security_answers(username, "answer1")
        assert is_valid is False
        assert "锁定" in msg

    async def test_verify_security_answers_correct(
        self, _clean_db, test_user, db_session
    ):  # noqa: ARG001
        username = test_user["username"]
        a1_hash = bcrypt.hashpw("answer1".encode(), bcrypt.gensalt()).decode()

        await _set_user_security_questions(
            db_session, username, "问题1", a1_hash=a1_hash
        )

        is_valid, msg = await verify_security_answers(username, "answer1")
        assert is_valid is True
        assert "成功" in msg

        count = await _get_user_field(db_session, username, "reset_attempt_count")
        assert count == 0

    async def test_verify_security_answers_incorrect(
        self, _clean_db, test_user, db_session
    ):  # noqa: ARG001
        username = test_user["username"]
        a1_hash = bcrypt.hashpw("correct1".encode(), bcrypt.gensalt()).decode()

        await _set_user_security_questions(
            db_session,
            username,
            "问题1",
            a1_hash=a1_hash,
            attempt_count=0,
        )

        is_valid, _ = await verify_security_answers(username, "wrong1")
        assert is_valid is False

        db_session.expire_all()
        count = await _get_user_field(db_session, username, "reset_attempt_count")
        assert count == 1

    async def test_verify_security_answers_max_attempts(
        self, _clean_db, test_user, db_session
    ):  # noqa: ARG001
        username = test_user["username"]
        a1_hash = bcrypt.hashpw("correct1".encode(), bcrypt.gensalt()).decode()

        await _set_user_security_questions(
            db_session,
            username,
            "问题1",
            a1_hash=a1_hash,
            attempt_count=MAX_RESET_ATTEMPTS - 1,
        )

        is_valid, msg = await verify_security_answers(username, "wrong1")
        assert is_valid is False
        assert "锁定" in msg

        db_session.expire_all()
        lock_until, count = await _get_user_field(
            db_session, username, "reset_locked_until", "reset_attempt_count"
        )
        assert lock_until is not None
        assert count == MAX_RESET_ATTEMPTS

    async def test_verify_ignores_legacy_q2_a2(
        self, _clean_db, test_user, db_session
    ):  # noqa: ARG001
        """老用户即使 DB 中残留 q2/a2，verify_security_answers 只看 q1/a1。"""
        username = test_user["username"]
        a1_hash = bcrypt.hashpw("answer1".encode(), bcrypt.gensalt()).decode()
        legacy_a2_hash = bcrypt.hashpw(
            "legacy_old_answer".encode(), bcrypt.gensalt()
        ).decode()

        await _set_user_security_questions(
            db_session, username, "问题1", a1_hash=a1_hash
        )
        await _set_legacy_q2_a2(db_session, username, "旧问题", legacy_a2_hash)

        db_session.expire_all()
        legacy_q2, legacy_a2 = await _get_user_field(
            db_session, username, "security_q2", "security_a2"
        )
        assert legacy_q2 == "旧问题"
        assert legacy_a2 == legacy_a2_hash

        is_valid, msg = await verify_security_answers(username, "answer1")
        assert is_valid is True
        assert "成功" in msg

        db_session.expire_all()
        still_q2, still_a2 = await _get_user_field(
            db_session, username, "security_q2", "security_a2"
        )
        assert still_q2 == "旧问题"
        assert still_a2 == legacy_a2_hash


class TestResetPassword:
    async def test_reset_password_user_not_exist(self, _clean_db):  # noqa: ARG001
        is_valid, msg = await reset_password("nonexistent_user", "NewP@ss123456")
        assert is_valid is False
        assert "不存在" in msg

    async def test_reset_password_weak_password(self, _clean_db, test_user):  # noqa: ARG001
        username = test_user["username"]
        is_valid, msg = await reset_password(username, "weak")
        assert is_valid is False
        assert "强度不够" in msg

    async def test_reset_password_success(self, _clean_db, test_user, db_session):  # noqa: ARG001
        username = test_user["username"]
        new_password = "NewP@ss123456"

        is_valid, msg = await reset_password(username, new_password)
        assert is_valid is True
        assert "成功" in msg

        db_session.expire_all()
        stored_hash = await _get_user_field(db_session, username, "password")
        assert isinstance(stored_hash, str)
        assert stored_hash != test_user["password"]
        assert bcrypt.checkpw(new_password.encode(), stored_hash.encode())

    async def test_reset_password_clears_lock(self, _clean_db, test_user, db_session):  # noqa: ARG001
        username = test_user["username"]
        lock_until = time.time() + 3600

        await _set_user_security_questions(
            db_session,
            username,
            "q1",
            locked_until=lock_until,
            attempt_count=MAX_RESET_ATTEMPTS,
        )

        is_valid, _ = await reset_password(username, "NewP@ss123456")
        assert is_valid is True

        db_session.expire_all()
        lock_result, count = await _get_user_field(
            db_session, username, "reset_locked_until", "reset_attempt_count"
        )
        assert lock_result is None
        assert count == 0


class TestUnlockUser:
    async def test_unlock_user_not_exist(self, _clean_db):  # noqa: ARG001
        is_valid, msg = await unlock_user("nonexistent_user", "admin")
        assert is_valid is False
        assert "不存在" in msg

    async def test_unlock_user_success(self, _clean_db, test_user, db_session):  # noqa: ARG001
        username = test_user["username"]
        lock_until = time.time() + 3600

        await _set_user_security_questions(
            db_session,
            username,
            "q1",
            locked_until=lock_until,
            attempt_count=MAX_RESET_ATTEMPTS,
        )

        is_valid, msg = await unlock_user(username, "admin")
        assert is_valid is True
        assert "解锁" in msg

        db_session.expire_all()
        lock_result, count = await _get_user_field(
            db_session, username, "reset_locked_until", "reset_attempt_count"
        )
        assert lock_result is None
        assert count == 0


class TestAdminResetPassword:
    async def test_admin_reset_password_user_not_exist(self, _clean_db):  # noqa: ARG001
        is_valid, msg = await admin_reset_password(
            "nonexistent_user", "NewP@ss123456", "admin"
        )
        assert is_valid is False
        assert "不存在" in msg

    async def test_admin_reset_password_weak_password(self, _clean_db, test_user):  # noqa: ARG001
        username = test_user["username"]
        is_valid, msg = await admin_reset_password(username, "weak", "admin")
        assert is_valid is False
        assert "强度不够" in msg

    async def test_admin_reset_password_success(self, _clean_db, test_user, db_session):  # noqa: ARG001
        username = test_user["username"]
        new_password = "NewP@ss123456"
        lock_until = time.time() + 3600

        await _set_user_security_questions(
            db_session,
            username,
            "q1",
            locked_until=lock_until,
            attempt_count=MAX_RESET_ATTEMPTS,
        )

        is_valid, msg = await admin_reset_password(username, new_password, "admin")
        assert is_valid is True
        assert "重置" in msg

        db_session.expire_all()
        stored_hash, lock_result, count = await _get_user_field(
            db_session,
            username,
            "password",
            "reset_locked_until",
            "reset_attempt_count",
        )
        assert stored_hash != test_user["password"]
        assert lock_result is None
        assert count == 0
        assert bcrypt.checkpw(new_password.encode(), stored_hash.encode())


class TestGetPasswordRecoveryLogs:
    async def test_get_password_recovery_logs_empty(self, _clean_db):  # noqa: ARG001
        logs = await get_password_recovery_logs(limit=0)
        assert isinstance(logs, list)

    async def test_get_password_recovery_logs_all(self, _clean_db):  # noqa: ARG001
        for i in range(5):
            await log_password_recovery_event(
                username=f"user{i}", event_type="request", success=True, attempt_count=0
            )

        logs = await get_password_recovery_logs(limit=10)
        assert len(logs) >= 5

        for log in logs:
            assert "username" in log
            assert "event_type" in log
            assert "success" in log
            assert "created_at" in log

    async def test_get_password_recovery_logs_by_username(self, _clean_db):  # noqa: ARG001
        username = f"test_user_log_{int(time.time())}"

        for i in range(3):
            await log_password_recovery_event(
                username=username, event_type="request", success=True, attempt_count=i
            )

        await log_password_recovery_event(
            username=f"other_user_{int(time.time())}",
            event_type="request",
            success=True,
        )

        logs = await get_password_recovery_logs(username=username)
        assert len(logs) >= 3
        assert all(log["username"] == username for log in logs)

    async def test_get_password_recovery_logs_limit(self, _clean_db):  # noqa: ARG001
        for i in range(10):
            await log_password_recovery_event(
                username=f"user{i}", event_type="request", success=True
            )

        logs = await get_password_recovery_logs(limit=5)
        assert len(logs) == 5

    @pytest.mark.parametrize("username_filter", [None, "specific_user"])
    async def test_get_password_recovery_logs_format(self, _clean_db, username_filter):  # noqa: ARG001
        target = username_filter or "format_test_user"
        await log_password_recovery_event(
            username=target, event_type="request", success=False, attempt_count=1
        )

        logs = await get_password_recovery_logs(username=username_filter, limit=5)
        assert isinstance(logs, list)
        if logs:
            log = logs[0]
            assert isinstance(log["success"], bool)
            assert isinstance(log["created_at"], str)
