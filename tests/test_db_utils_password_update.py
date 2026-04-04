import hashlib
import time

from db_utils import (
    get_db_connection,
    verify_password,
    update_user_password,
)
from db_utils import (
    create_user,
    get_user_detail,
    get_user_detail,
    verify_user,
    get_all_users as get_all_users_db,
)


def test_update_user_password_bcrypt_and_wrong_current():
    # 手工插入一个 bcrypt 密码的用户
    from db_utils import (
        hash_password,
        _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
        get_placeholder,
        _is_postgresql_connection,  # pyright: ignore[reportPrivateUsage]
    )

    with get_db_connection() as (conn, c):
        placeholder = get_placeholder()
        uname = f"upd_user_b_{int(time.time() * 1000)}"
        if _is_postgresql_connection(conn):
            sql_raw = f"INSERT INTO users(username,password,role,is_test_user) VALUES({placeholder},{placeholder},{placeholder},{placeholder}) RETURNING id"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (uname, hash_password("Old-P@ss-1!"), "user", 1))
            uid = c.fetchone()[0]
        else:
            sql_raw = f"INSERT INTO users(username,password,role,is_test_user) VALUES({placeholder},{placeholder},{placeholder},{placeholder})"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (uname, hash_password("Old-P@ss-1!"), "user", 1))
            uid = c.lastrowid
        conn.commit()

    # 错误口令应返回 False
    assert update_user_password(uid, "WRONG", "New-P@ss-2!") is False
    # 正确口令应更新成功
    assert update_user_password(uid, "Old-P@ss-1!", "New-P@ss-2!") is True

    with get_db_connection() as (conn, c):
        placeholder = get_placeholder()
        sql_raw = f"SELECT password FROM users WHERE id={placeholder}"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (uid,))
        hp = c.fetchone()[0]
    assert verify_password("New-P@ss-2!", hp) is True


def test_update_user_password_from_sha256_to_bcrypt():
    # 手工插入一个旧 SHA256 密码用户
    from db_utils import (
        _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
        get_placeholder,
        _is_postgresql_connection,  # pyright: ignore[reportPrivateUsage]
    )

    legacy_pwd = "Legacy-Old-1!"
    legacy_hash = hashlib.sha256(legacy_pwd.encode()).hexdigest()
    with get_db_connection() as (conn, c):
        placeholder = get_placeholder()
        uname = f"upd_user_sha_{int(time.time() * 1000)}"
        if _is_postgresql_connection(conn):
            sql_raw = f"INSERT INTO users(username,password,role,is_test_user) VALUES({placeholder},{placeholder},{placeholder},{placeholder}) RETURNING id"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (uname, legacy_hash, "user", 1))
            uid = c.fetchone()[0]
        else:
            sql_raw = f"INSERT INTO users(username,password,role,is_test_user) VALUES({placeholder},{placeholder},{placeholder},{placeholder})"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (uname, legacy_hash, "user", 1))
            uid = c.lastrowid
        conn.commit()

    # 使用旧口令更新为新口令，应成功并把存储改为 bcrypt
    assert update_user_password(uid, legacy_pwd, "New-Bcrypt-3!") is True
    with get_db_connection() as (conn, c):
        placeholder = get_placeholder()
        sql_raw = f"SELECT password FROM users WHERE id={placeholder}"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (uid,))
        hp = c.fetchone()[0]
    assert hp.startswith("$2")
    assert verify_password("New-Bcrypt-3!", hp) is True
