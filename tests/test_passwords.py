import pytest
from db_utils import (
    hash_password,
    verify_password,
    get_db_connection,
)


def test_hash_and_verify_bcrypt_roundtrip():
    pwd = "Secur3-P@ssw0rd-XYZ"
    hashed = hash_password(pwd)
    assert hashed.startswith("$2")
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_sha256_legacy_upgrade_on_login():
    # 手工插入旧 SHA256 密码
    import hashlib
    import time
    username = f"legacy_user_{int(time.time())}"
    legacy_pwd = "Legacy-1234!@#"
    legacy_hash = hashlib.sha256(legacy_pwd.encode()).hexdigest()

    with get_db_connection() as (conn, c):
        from db_adapter import adapt_sql
        sql = adapt_sql(
            "INSERT INTO users (username, password, role, is_test_user) VALUES (?,?,?,?)"
        )
        c.execute(sql, (username, legacy_hash, "user", 1))
        conn.commit()

    # verify_password 先能通过
    assert verify_password(legacy_pwd, legacy_hash) is True

    # 模拟登录升级（调用 db_utils.upgrade_user_password_to_bcrypt）
    from db_utils import upgrade_user_password_to_bcrypt
    from db_adapter import adapt_sql
    new_hash = None
    with get_db_connection() as (conn, c):
        sql = adapt_sql("SELECT id, password FROM users WHERE username=?")
        c.execute(sql, (username,))
        user = c.fetchone()
        if user:
            upgrade_user_password_to_bcrypt(user[0], legacy_pwd)

            sql = adapt_sql("SELECT password FROM users WHERE username=?")
            c.execute(sql, (username,))
            user2 = c.fetchone()
            if user2:
                new_hash = user2[0]
            else:
                pytest.fail("用户未找到")
        else:
            pytest.fail("用户未找到")

    if new_hash is None:
        pytest.fail("未能获取新密码哈希")
    assert new_hash.startswith("$2")
    assert verify_password(legacy_pwd, new_hash) is True

