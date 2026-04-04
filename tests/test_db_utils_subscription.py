from datetime import datetime, timedelta
import time

from db_utils import (
    create_user,
    get_db_connection,
)
from db_utils import (
    get_user_subscription_info,
    get_plans,
    update_user_subscription,
    check_user_subscription_status,
    decrement_user_calculations,
)


def _get_user_id(username: str) -> int:
    with get_db_connection() as (conn, c):
        # noinspection PyProtectedMember
        # noqa: SLF001
        from db_utils import (
            _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
            get_placeholder,
        )

        placeholder = get_placeholder()
        sql_raw = f"SELECT id FROM users WHERE username={placeholder}"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (username,))
        row = c.fetchone()
        return int(row[0])


def test_subscription_test_user():
    username = f"test_user_sub_{int(time.time() * 1000)}"
    user_id = create_user(
        username, "Strong-P@ss-123", role="user", user_type="test", is_test_user=True
    )
    assert user_id is not None
    update_user_subscription(
        user_id, {"user_type": "test", "subscription_type": "test"}
    )
    status = check_user_subscription_status(user_id)
    assert status["valid"] is True
    assert "测试用户" in status["message"]


def test_subscription_monthly_and_decrement():
    username = f"monthly_user_sub_{int(time.time() * 1000)}"
    assert create_user(username, "Strong-P@ss-999", role="user", is_test_user=True)
    uid = _get_user_id(username)
    update_user_subscription(
        uid,
        {
            "user_type": "monthly",
            "expiry_date": (datetime.now() + timedelta(days=2)).isoformat(),
            "remaining_calculations": 2,
        },
    )
    status = check_user_subscription_status(uid)
    assert status["valid"] is True
    assert status.get("remaining_calculations") == 2

    assert decrement_user_calculations(uid) is True
    assert decrement_user_calculations(uid) is True
    # 第三次应为 False
    assert decrement_user_calculations(uid) is False


def test_subscription_enterprise_expiry():
    username = f"enterprise_user_sub_{int(time.time() * 1000)}"
    user_id = create_user(username, "Strong-P@ss-777", role="user", is_test_user=True)
    assert user_id is not None
    update_user_subscription(
        user_id,
        {
            "user_type": "enterprise",
            "subscription_type": "enterprise",
            "expiry_date": (datetime.now() - timedelta(days=1)).isoformat(),
        },
    )
    status = check_user_subscription_status(user_id)
    assert status["valid"] is False
    assert "已过期" in status["message"] or "过期" in status["message"]
