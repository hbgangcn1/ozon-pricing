import os
import sys
import types
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db_utils  # noqa: E402


def _cm(conn=None, cursor=None):
    conn = conn or MagicMock()
    cursor = cursor or MagicMock()
    manager = MagicMock()
    manager.__enter__ = MagicMock(return_value=(conn, cursor))
    manager.__exit__ = MagicMock(return_value=False)
    return manager, conn, cursor


def test_fake_session_state_contains_user_key():
    with patch.object(db_utils._FakeSessionState, "_user", {"id": 7}):
        fss = db_utils._FakeSessionState()
        fss._data["x"] = 1
        assert "user" in fss and "x" in fss
        assert fss["user"] == {"id": 7} and fss["x"] == 1
        assert fss.user == {"id": 7}


def test_fake_session_state_set_user_and_getattr():
    db_utils._FakeSessionState.set_user({"id": 8})
    assert db_utils._FakeSessionState._user == {"id": 8}
    db_utils._FakeSessionState.set_user(None)
    with patch.object(db_utils._FakeSessionState, "_user", None):
        try:
            _ = db_utils._FakeSessionState().unknown
            assert False
        except AttributeError:
            pass
    fss = db_utils._FakeSessionState()
    fss._data["abc"] = 42
    assert fss["abc"] == 42


def test_serialize_subscription_expires_all_types():
    assert db_utils._serialize_subscription_expires(None) is None
    assert db_utils._serialize_subscription_expires("") is None
    assert db_utils._serialize_subscription_expires(0) is None
    assert db_utils._serialize_subscription_expires(100) == 100
    assert db_utils._serialize_subscription_expires(100.9) == 100
    dt = datetime(2026, 1, 1, 0, 0, 0)
    assert db_utils._serialize_subscription_expires(dt) == int(dt.timestamp())
    assert db_utils._serialize_subscription_expires(dt.isoformat()) == int(
        dt.timestamp()
    )
    assert db_utils._serialize_subscription_expires("123") == 123
    assert db_utils._serialize_subscription_expires("123.5") == 123
    assert db_utils._serialize_subscription_expires("bad") is None
    d = date(2026, 6, 1)
    assert isinstance(db_utils._serialize_subscription_expires(str(d)), int)


def test_subscription_expires_to_datetime_all_types():
    assert db_utils._subscription_expires_to_datetime(None) is None
    assert db_utils._subscription_expires_to_datetime("") is None
    assert db_utils._subscription_expires_to_datetime(0) is None
    ts = int(datetime(2026, 1, 1).timestamp())
    assert isinstance(db_utils._subscription_expires_to_datetime(ts), datetime)
    assert isinstance(db_utils._subscription_expires_to_datetime(float(ts)), datetime)
    assert isinstance(db_utils._subscription_expires_to_datetime(str(ts)), datetime)
    assert isinstance(
        db_utils._subscription_expires_to_datetime("2026-01-01T00:00:00"),
        datetime,
    )
    assert db_utils._subscription_expires_to_datetime("not-a-date") is None
    assert db_utils._subscription_expires_to_datetime("   ") is None


def test_is_postgresql_connection_all_paths():
    assert db_utils._is_postgresql_connection(None) is False
    conn1 = type("C", (), {})()
    conn1.__class__.__module__ = "psycopg2.extensions"
    assert db_utils._is_postgresql_connection(conn1) is True
    conn2 = type("C", (), {})()
    conn2.__class__.__module__ = "postgresql.driver"
    assert db_utils._is_postgresql_connection(conn2) is True
    PgConn = type("PostgresConnection", (), {})
    PgConn.__module__ = "custom.module"
    assert db_utils._is_postgresql_connection(PgConn()) is True
    PsConn = type("PsycopgConn", (), {})
    PsConn.__module__ = "custom.module"
    assert db_utils._is_postgresql_connection(PsConn()) is True
    conn3 = type("SomeConn", (), {})()
    conn3.__class__.__module__ = "other.module"
    with patch.dict(sys.modules, {"psycopg2": types.SimpleNamespace()}):
        assert db_utils._is_postgresql_connection(conn3) is True


def test_ensure_serial_columns_all_paths():
    conn, cur = MagicMock(), MagicMock()
    with patch.object(db_utils, "_is_postgresql_connection", return_value=False):
        db_utils._ensure_serial_columns(conn, cur)
    cur.execute.assert_not_called()

    conn2, cur2 = MagicMock(), MagicMock()
    cur2.fetchall.return_value = [("tbl1",)]
    cur2.fetchone.return_value = (None,)
    with patch.object(db_utils, "_is_postgresql_connection", return_value=True):
        db_utils._ensure_serial_columns(conn2, cur2)
    assert conn2.commit.called

    conn3, cur3 = MagicMock(), MagicMock()
    cur3.fetchone.return_value = ("nextval('x')",)
    with patch.object(db_utils, "_is_postgresql_connection", return_value=True):
        db_utils._ensure_serial_columns(conn3, cur3, ["users"])
    assert not conn3.commit.called

    conn4, cur4 = MagicMock(), MagicMock()
    exc = db_utils.DB_EXCEPTIONS[0]
    cur4.fetchone.return_value = (None,)
    cur4.execute.side_effect = [None, exc("boom")]
    with patch.object(db_utils, "_is_postgresql_connection", return_value=True):
        db_utils._ensure_serial_columns(conn4, cur4, ["users"])
    assert conn4.rollback.called


def test_safe_execute_fetchone_all_paths():
    cur = MagicMock()
    cur.fetchone.return_value = (1,)
    assert db_utils._safe_execute_fetchone(cur, "S %s", (1,)) == (1,)
    cur.execute.assert_called_with("S %s", (1,))

    cur2 = MagicMock()
    cur2.fetchone.return_value = None
    assert db_utils._safe_execute_fetchone(cur2, "SELECT 1") is None

    cur3 = MagicMock()
    cur3.fetchone.return_value = (2,)
    with patch.object(db_utils, "_safe_adapt_sql", return_value="ADAPTED"):
        assert db_utils._safe_execute_fetchone(cur3, "S ?", (1,), MagicMock()) == (2,)


def test_safe_execute_fetchone_injection_detection():
    cur = MagicMock()
    cur.fetchone.return_value = (1,)
    fake_mod = types.SimpleNamespace(
        detect_sql_injection=lambda sql, params: (False, "warn")
    )
    with patch.dict(os.environ, {"ENABLE_SQL_INJECTION_DETECTION": "true"}):
        with patch.dict(sys.modules, {"sql_injection_protection": fake_mod}):
            assert db_utils._safe_execute_fetchone(cur, "SELECT 1") == (1,)
    cur2 = MagicMock()
    cur2.fetchone.return_value = (1,)
    with patch.dict(os.environ, {"ENABLE_SQL_INJECTION_DETECTION": "true"}):
        with patch.dict(sys.modules, {"sql_injection_protection": None}):
            assert db_utils._safe_execute_fetchone(cur2, "SELECT 1") == (1,)


def test_connection_counter_thresholds(capsys):
    db_utils.reset_connection_counter()
    with patch.object(db_utils, "_connection_counter", 10):
        with patch.object(db_utils, "_CONNECTION_WARNINGS", set()):
            db_utils._increment_connection_counter()
    assert "警告" in capsys.readouterr().out

    with patch.object(db_utils, "_connection_counter", 30):
        with patch.object(db_utils, "_CONNECTION_WARNINGS", set()):
            db_utils._increment_connection_counter()
    assert "严重" in capsys.readouterr().out

    with patch.object(db_utils, "_connection_counter", 1):
        with patch.object(db_utils, "_CONNECTION_WARNINGS", {"warning", "critical"}):
            db_utils._increment_connection_counter()

    with patch.object(db_utils, "_connection_counter", 5):
        with patch.object(db_utils, "_CONNECTION_WARNINGS", {"warning"}):
            db_utils._decrement_connection_counter()

    with patch.object(db_utils, "_connection_counter", 0):
        assert db_utils._decrement_connection_counter() >= 0


def test_check_connections_at_exit_paths(capsys):
    with patch.object(db_utils, "get_connection_count", return_value=0):
        with patch.dict(os.environ, {"DBUTILS_SKIP_EXIT_CLEANUP": "1"}):
            db_utils._check_connections_at_exit()

    with patch.object(db_utils, "get_connection_count", return_value=3):
        with patch.dict(os.environ, {"DBUTILS_SKIP_EXIT_CLEANUP": "0"}):
            with patch.object(db_utils, "_postgres_pool_closed_logged", False):
                with patch("db_adapter.close_connection_pool", MagicMock()):
                    db_utils._check_connections_at_exit()
    assert "连接" in capsys.readouterr().out

    with patch.object(db_utils, "get_connection_count", side_effect=TypeError()):
        with patch.dict(os.environ, {"DBUTILS_SKIP_EXIT_CLEANUP": "1"}):
            db_utils._check_connections_at_exit()

    with patch.object(db_utils, "get_connection_count", return_value=1):
        with patch.dict(os.environ, {"DBUTILS_SKIP_EXIT_CLEANUP": "0"}):
            mock_adapter = MagicMock()
            mock_adapter.close_connection_pool.side_effect = OSError()
            with patch.dict(sys.modules, {"db_adapter": mock_adapter}):
                db_utils._check_connections_at_exit()


def test_cleanup_on_interrupt_and_signal_handler():
    with patch.object(db_utils, "_check_connections_at_exit") as m:
        db_utils._cleanup_on_interrupt()
        m.assert_called_once()
    with patch.object(db_utils, "_cleanup_on_interrupt") as c:
        with patch("sys.exit") as ex:
            db_utils.signal_handler(2, object())
            c.assert_called_once()
            ex.assert_called_once_with(0)


def test_password_functions():
    import hashlib

    h = db_utils.hash_password("test123")
    assert h.startswith("$2b$")
    assert db_utils.verify_password("test123", h) is True
    assert db_utils.verify_password("wrong", h) is False
    legacy = hashlib.sha256("old".encode()).hexdigest()
    assert db_utils.verify_password("old", legacy) is True
    assert db_utils.verify_password("wrong", legacy) is False
    assert db_utils.verify_legacy_password("old", legacy) is True
    assert db_utils.is_bcrypt_hash("$2b$12$abc") is True
    assert db_utils.is_bcrypt_hash("$2a$12$abc") is True
    assert db_utils.is_bcrypt_hash("sha256hash") is False


def test_db_connection_helpers():
    with patch("db_adapter.get_db_connection", return_value="cm"):
        assert db_utils.get_db_connection() == "cm"
    with patch.object(db_utils, "get_db_connection", return_value="cm"):
        assert db_utils.get_db() == "cm"
    raw = MagicMock()
    with patch.object(db_utils, "get_db_connection", return_value=raw):
        with db_utils.DBConnection() as got:
            assert got == raw
    raw.close.assert_called_once()
    with patch.object(db_utils, "get_db_connection", return_value="fb"):
        assert db_utils.get_enhanced_db_connection() == "fb"
    with patch.object(db_utils, "get_connection_stats", return_value={"x": 1}):
        assert db_utils.get_enhanced_connection_stats() == {"x": 1}


def test_current_user_id_paths():
    session = MagicMock()
    session.__contains__ = MagicMock(return_value=True)
    session.__getitem__ = MagicMock(return_value={"id": 11, "role": "user"})
    st = types.SimpleNamespace(session_state=session)
    with patch.object(db_utils, "_st", st):
        assert db_utils.current_user_id() == 11

    session2 = MagicMock()
    session2.__contains__ = MagicMock(side_effect=TypeError())
    session2.user = {"id": 22}
    st2 = types.SimpleNamespace(session_state=session2)
    with patch.object(db_utils, "_st", st2):
        assert db_utils.current_user_id() == 22

    session3 = MagicMock()
    session3.__contains__ = MagicMock(return_value=False)
    session3.user = None
    st3 = types.SimpleNamespace(session_state=session3)
    with patch.object(db_utils, "_st", st3):
        try:
            db_utils.current_user_id()
            assert False
        except ValueError:
            pass

    user_obj = types.SimpleNamespace(id=33, role="user")
    session4 = MagicMock()
    session4.__contains__ = MagicMock(return_value=True)
    session4.__getitem__ = MagicMock(return_value=user_obj)
    st4 = types.SimpleNamespace(session_state=session4)
    with patch.object(db_utils, "_st", st4):
        assert db_utils.current_user_id() == 33


def test_is_admin_paths():
    session = MagicMock()
    session.__contains__ = MagicMock(return_value=True)
    session.__getitem__ = MagicMock(return_value={"id": 1, "role": "admin"})
    st = types.SimpleNamespace(session_state=session)
    with patch.object(db_utils, "_st", st):
        assert db_utils.is_admin() is True

    session2 = MagicMock()
    session2.__contains__ = MagicMock(return_value=False)
    session2.user = None
    st2 = types.SimpleNamespace(session_state=session2)
    with patch.object(db_utils, "_st", st2):
        assert db_utils.is_admin() is False

    session3 = MagicMock()
    session3.__contains__ = MagicMock(return_value=True)
    session3.__getitem__ = MagicMock(return_value={"id": 1, "role": "user"})
    st3 = types.SimpleNamespace(session_state=session3)
    with patch.object(db_utils, "_st", st3):
        assert db_utils.is_admin() is False

    user_obj = types.SimpleNamespace(id=1, role="admin")
    session4 = MagicMock()
    session4.__contains__ = MagicMock(return_value=True)
    session4.__getitem__ = MagicMock(return_value=user_obj)
    st4 = types.SimpleNamespace(session_state=session4)
    with patch.object(db_utils, "_st", st4):
        assert db_utils.is_admin() is True

    with patch.object(db_utils, "is_admin", return_value=False):
        try:
            db_utils.require_admin()
            assert False
        except PermissionError:
            pass


def test_system_config_and_registration():
    cm, _, cur = _cm()
    cur.fetchone.return_value = ("v",)
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch("db_adapter.adapt_sql", side_effect=lambda s: s):
            assert db_utils.get_system_config("k") == "v"
    cur.fetchone.return_value = None
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch("db_adapter.adapt_sql", side_effect=lambda s: s):
            assert db_utils.get_system_config("k", "d") == "d"

    cm_none = MagicMock()
    cm_none.__enter__ = MagicMock(return_value=(MagicMock(), None))
    cm_none.__exit__ = MagicMock(return_value=False)
    with patch("db_utils.get_db_connection", return_value=cm_none):
        assert db_utils.get_system_config("x", "y") == "y"

    cm2, _, cur2 = _cm()
    with patch("db_utils.get_db_connection", return_value=cm2):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            assert db_utils.set_system_config("a", "b", "c") is True
    cur2.execute.side_effect = Exception("x")
    with patch("db_utils.get_db_connection", return_value=cm2):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            assert db_utils.set_system_config("a", "b") is False

    with patch.object(db_utils, "get_system_config", return_value="true"):
        assert db_utils.is_registration_open() is True
    with patch.object(db_utils, "get_system_config", return_value=None):
        assert db_utils.is_registration_open() is False
    with patch.object(db_utils, "get_system_config", return_value="false"):
        assert db_utils.is_registration_open() is False


def test_create_user_validation():
    with patch.object(db_utils, "init_db"):
        assert db_utils.create_user("", "Pwd12345!") is None
    with patch.object(db_utils, "init_db"):
        with patch(
            "db_utils.validate_password_strength",
            return_value={"is_valid": False},
        ):
            assert db_utils.create_user("u", "weak") is None


def test_create_user_duplicate_username():
    cm, _, cur = _cm()
    cur.fetchone.return_value = ("u",)
    with patch.object(db_utils, "init_db"):
        with patch(
            "db_utils.validate_password_strength",
            return_value={"is_valid": True},
        ):
            with patch("db_utils.get_db_connection", return_value=cm):
                with patch.object(
                    db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s
                ):
                    assert db_utils.create_user("u", "Pwd12345!") is None


def test_create_user_duplicate_email():
    cm, _, cur = _cm()
    cur.fetchone.return_value = None
    with patch.object(db_utils, "init_db"):
        with patch(
            "db_utils.validate_password_strength",
            return_value={"is_valid": True},
        ):
            with patch("db_utils.get_db_connection", return_value=cm):
                with patch.object(
                    db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s
                ):
                    with patch.object(
                        db_utils,
                        "_safe_execute_fetchone",
                        return_value=("a@b.com",),
                    ):
                        assert (
                            db_utils.create_user("u2", "Pwd12345!", email="a@b.com")
                            is None
                        )


def test_create_user_pg_with_email():
    cm, conn, cur = _cm()
    cur.fetchone.side_effect = [None, (99,)]
    with patch.object(db_utils, "init_db"):
        with patch(
            "db_utils.validate_password_strength",
            return_value={"is_valid": True},
        ):
            with patch("db_utils.get_db_connection", return_value=cm):
                with patch.object(
                    db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s
                ):
                    with patch.object(
                        db_utils, "_safe_execute_fetchone", return_value=None
                    ):
                        with patch.object(
                            db_utils,
                            "_is_postgresql_connection",
                            return_value=True,
                        ):
                            with patch.object(
                                db_utils, "hash_password", return_value="hp"
                            ):
                                uid = db_utils.create_user(
                                    "u2",
                                    "Pwd12345!",
                                    email="a@b.com",
                                    user_type="free",
                                )
    assert uid == 99 and conn.commit.called


def test_create_user_pg_no_email():
    cm, conn, cur = _cm()
    cur.fetchone.side_effect = [None, (42,)]
    with patch.object(db_utils, "init_db"):
        with patch(
            "db_utils.validate_password_strength",
            return_value={"is_valid": True},
        ):
            with patch("db_utils.get_db_connection", return_value=cm):
                with patch.object(
                    db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s
                ):
                    with patch.object(
                        db_utils,
                        "_is_postgresql_connection",
                        return_value=True,
                    ):
                        with patch.object(db_utils, "hash_password", return_value="hp"):
                            uid = db_utils.create_user("u3", "Pwd12345!")
    assert uid == 42


def test_create_user_test_type_and_exception():
    cm, conn, cur = _cm()
    cur.fetchone.side_effect = [None, (50,)]
    with patch.object(db_utils, "init_db"):
        with patch(
            "db_utils.validate_password_strength",
            return_value={"is_valid": True},
        ):
            with patch("db_utils.get_db_connection", return_value=cm):
                with patch.object(
                    db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s
                ):
                    with patch.object(
                        db_utils,
                        "_is_postgresql_connection",
                        return_value=True,
                    ):
                        with patch.object(db_utils, "hash_password", return_value="hp"):
                            uid = db_utils.create_user(
                                "tester",
                                "Pwd12345!",
                                user_type="test",
                                is_test_user=True,
                            )
    assert uid == 50

    cm2, _, cur2 = _cm()
    cur2.fetchone.return_value = None
    cur2.execute.side_effect = [None, Exception("fail")]
    with patch.object(db_utils, "init_db"):
        with patch(
            "db_utils.validate_password_strength",
            return_value={"is_valid": True},
        ):
            with patch("db_utils.get_db_connection", return_value=cm2):
                with patch.object(
                    db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s
                ):
                    with patch.object(
                        db_utils,
                        "_is_postgresql_connection",
                        return_value=True,
                    ):
                        with patch.object(db_utils, "hash_password", return_value="hp"):
                            assert db_utils.create_user("u4", "Pwd12345!") is None


def test_verify_user_legacy_upgrade():
    cm_ck, _, cur_ck = _cm()
    cur_ck.fetchone.return_value = (True,)
    cm_auth, _, _ = _cm()
    row = (1, "alice", "legacyhash", "user", "a@b.com", "f", "free")
    with patch.dict(db_utils._db_initialized_cache, {"initialized": False}):
        with patch("db_utils.get_db_connection", side_effect=[cm_ck, cm_auth]):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                with patch.object(db_utils, "_safe_execute_fetchone", return_value=row):
                    with patch.object(db_utils, "verify_password", return_value=True):
                        with patch.object(
                            db_utils, "is_bcrypt_hash", return_value=False
                        ):
                            with patch.object(
                                db_utils,
                                "upgrade_user_password_to_bcrypt",
                            ) as up:
                                with patch.object(
                                    db_utils,
                                    "_get_table_columns",
                                    return_value=[
                                        "id",
                                        "username",
                                        "password",
                                        "role",
                                        "email",
                                        "mode",
                                        "user_type",
                                    ],
                                ):
                                    r = db_utils.verify_user("alice", "pw")
    assert r["user_type"] == "free"
    up.assert_called_once_with(1, "pw")


def test_verify_user_not_found_and_wrong_pw():
    with patch.dict(db_utils._db_initialized_cache, {"initialized": True}):
        cm, _, _ = _cm()
        with patch("db_utils.get_db_connection", return_value=cm):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                with patch.object(
                    db_utils, "_safe_execute_fetchone", return_value=None
                ):
                    assert db_utils.verify_user("no_one", "pw") is None

    row = (1, "bob", "hash", "user", None, "f", "free")
    with patch.dict(db_utils._db_initialized_cache, {"initialized": True}):
        cm2, _, _ = _cm()
        with patch("db_utils.get_db_connection", return_value=cm2):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                with patch.object(db_utils, "_safe_execute_fetchone", return_value=row):
                    with patch.object(db_utils, "verify_password", return_value=False):
                        assert db_utils.verify_user("bob", "wrong") is None


def test_verify_user_init_exception():
    cm_ck, _, cur_ck = _cm()
    cur_ck.execute.side_effect = Exception("db error")
    cm_auth, _, _ = _cm()
    with patch.dict(db_utils._db_initialized_cache, {"initialized": False}):
        with patch("db_utils.get_db_connection", side_effect=[cm_ck, cm_auth]):
            with patch.object(db_utils, "init_db") as init_mock:
                init_mock.side_effect = Exception("init fail")
                with patch.object(
                    db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s
                ):
                    with patch.object(
                        db_utils,
                        "_safe_execute_fetchone",
                        return_value=None,
                    ):
                        assert db_utils.verify_user("x", "y") is None


def test_verify_user_bcrypt_no_upgrade():
    row = (5, "c", "$2b$12$hash", "user", None, "f", "free")
    with patch.dict(db_utils._db_initialized_cache, {"initialized": True}):
        cm, _, _ = _cm()
        with patch("db_utils.get_db_connection", return_value=cm):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                with patch.object(db_utils, "_safe_execute_fetchone", return_value=row):
                    with patch.object(db_utils, "verify_password", return_value=True):
                        with patch.object(
                            db_utils, "is_bcrypt_hash", return_value=True
                        ):
                            with patch.object(
                                db_utils,
                                "_get_table_columns",
                                return_value=["id", "username"],
                            ):
                                r = db_utils.verify_user("c", "pw")
    assert r["user_type"] == "free"


def test_upgrade_user_password_to_bcrypt():
    cm, conn, cur = _cm()
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            with patch.object(db_utils, "hash_password", return_value="bcrypt-h"):
                db_utils.upgrade_user_password_to_bcrypt(2, "pw")
    cur.execute.assert_called_once()
    conn.commit.assert_called_once()


def _init_db_helper(is_pg, fetchone_seq, adapt_ret=None, table_cols=None):
    cm, conn, cur = _cm()
    cur.fetchall.return_value = []
    cur.fetchone.side_effect = fetchone_seq
    adapt_fn = (lambda s: s) if adapt_ret is None else (lambda s: adapt_ret)
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            with patch.object(db_utils, "_ensure_serial_columns"):
                with patch.object(
                    db_utils,
                    "_is_postgresql_connection",
                    return_value=is_pg,
                ):
                    with patch.object(db_utils, "hash_password", return_value="h"):
                        with patch("db_adapter.adapt_sql", side_effect=adapt_fn):
                            with patch.object(
                                db_utils,
                                "_get_table_columns",
                                return_value=table_cols or [],
                            ):
                                db_utils.init_db()
    return cm, conn, cur


def test_init_db_pg_full_path():
    _, conn, cur = _init_db_helper(
        True, [("integer", None), None, None], table_cols=["user_type"]
    )
    executed = "\n".join(str(c.args[0]) for c in cur.execute.call_args_list)
    assert "CREATE SEQUENCE" in executed


def test_init_db_non_pg():
    _, conn, _ = _init_db_helper(False, [None])
    assert conn.commit.called


def test_init_db_pg_autoincrement_rewrite():
    cm, conn, cur = _cm()
    exc = db_utils.DB_EXCEPTIONS[0]
    cur.fetchall.return_value = []
    cur.fetchone.side_effect = [("integer", None), None, None]

    def _exec(sql, *args, **kwargs):
        if "ADD CONSTRAINT" in str(sql):
            raise exc("dup")

    cur.execute.side_effect = _exec
    adapted = "CREATE TABLE x (id INTEGER PRIMARY KEY AUTOINCREMENT)"
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            with patch.object(db_utils, "_ensure_serial_columns"):
                with patch.object(
                    db_utils, "_is_postgresql_connection", return_value=True
                ):
                    with patch.object(db_utils, "hash_password", return_value="h"):
                        with patch("db_adapter.adapt_sql", return_value=adapted):
                            with patch.object(
                                db_utils,
                                "_get_table_columns",
                                return_value=["user_type"],
                            ):
                                db_utils.init_db()
    assert conn.rollback.called


def test_init_db_trigger_and_attr_error():
    cm, conn, cur = _cm()
    cur.fetchall.return_value = []
    cur.fetchone.side_effect = [None]
    exc = db_utils.DB_EXCEPTIONS[0]

    def _exec(sql, *args, **kwargs):
        if "DROP TRIGGER" in str(sql):
            raise exc("drop")

    cur.execute.side_effect = _exec
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            with patch.object(db_utils, "_ensure_serial_columns"):
                with patch.object(
                    db_utils, "_is_postgresql_connection", return_value=False
                ):
                    with patch.object(db_utils, "hash_password", return_value="h"):
                        with patch("db_adapter.adapt_sql", side_effect=lambda s: s):
                            with patch.object(
                                db_utils,
                                "_get_table_columns",
                                return_value=[],
                            ):
                                db_utils.init_db()

    cm2, conn2, cur2 = _cm()
    cur2.fetchall.return_value = []

    def _exec2(sql, *args, **kwargs):
        if "ADD CONSTRAINT" in str(sql):
            raise AttributeError("bad")

    cur2.execute.side_effect = _exec2
    cur2.fetchone.side_effect = [("integer", None), None, None]
    with patch("db_utils.get_db_connection", return_value=cm2):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            with patch.object(db_utils, "_ensure_serial_columns"):
                with patch.object(
                    db_utils, "_is_postgresql_connection", return_value=True
                ):
                    with patch.object(db_utils, "hash_password", return_value="h"):
                        with patch("db_adapter.adapt_sql", side_effect=lambda s: s):
                            with patch.object(
                                db_utils,
                                "_get_table_columns",
                                return_value=["user_type"],
                            ):
                                db_utils.init_db()
    assert conn2.rollback.called


def test_get_table_columns_and_timestamp_expr():
    cur = MagicMock()
    cur.fetchall.return_value = [("id",), ("name",)]
    assert db_utils._get_table_columns(cur, "users") == ["id", "name"]
    expr = db_utils._build_safe_timestamp_expr("expiry")
    assert "expiry" in expr and "COALESCE" in expr


def test_connection_stats():
    db_utils.reset_connection_counter()
    stats = db_utils.get_connection_stats()
    assert stats["active_connections"] == 0
    assert db_utils.get_connection_count() == 0
