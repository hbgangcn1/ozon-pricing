import os
import sys
import types
import time
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db_utils  # noqa: E402


def _cm(conn=None, cursor=None):
    conn = conn or MagicMock()
    cursor = cursor or MagicMock()
    mgr = MagicMock()
    mgr.__enter__ = MagicMock(return_value=(conn, cursor))
    mgr.__exit__ = MagicMock(return_value=False)
    return mgr, conn, cursor


def _add_product_ctx(cur_fetchone, cols, is_pg):
    cm, conn, cur = _cm()
    fake = types.SimpleNamespace(
        SQLSecurityError=ValueError,
        validate_field_names=lambda f, a: True,
    )
    cur.fetchone.return_value = cur_fetchone
    return (cm, conn, cur, fake, cols, is_pg)


def _run_add_product(ctx, data, exec_side=None):
    cm, conn, cur, fake, cols, is_pg = ctx
    if exec_side:
        cur.execute.side_effect = exec_side
    with patch.dict(sys.modules, {"sql_security": fake}):
        with patch("db_utils.get_db_connection", return_value=cm):
            with patch.object(db_utils, "_get_table_columns", return_value=cols):
                with patch.object(
                    db_utils, "_is_postgresql_connection", return_value=is_pg
                ):
                    with patch.object(
                        db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s
                    ):
                        with patch.object(
                            db_utils, "get_placeholder", return_value="%s"
                        ):
                            return db_utils.add_product(data)


def test_add_product_with_is_test_data_column():
    ctx = _add_product_ctx((321,), ["is_test_data"], True)
    assert _run_add_product(ctx, {"user_id": 8, "name": "p"}) == 321
    assert ctx[1].commit.called


def test_add_product_alter_column_non_pg():
    ctx = _add_product_ctx((10,), [], False)
    assert _run_add_product(ctx, {"user_id": 1, "name": "x"}) == 10


def test_add_product_alter_column_db_exception():
    ctx = _add_product_ctx((5,), [], True)
    exc = db_utils.DB_EXCEPTIONS[0]
    n = [0]

    def _exec(sql, *a, **kw):
        n[0] += 1
        if n[0] == 1 and "ALTER TABLE" in str(sql):
            raise exc("col exists")

    assert _run_add_product(ctx, {"user_id": 1}, _exec) == 5


def test_add_product_sql_security_error():
    class Err(Exception):
        pass

    fake = types.SimpleNamespace(
        SQLSecurityError=Err,
        validate_field_names=lambda *a: (_ for _ in ()).throw(Err("x")),
    )
    cm, _, _ = _cm()
    with patch.dict(sys.modules, {"sql_security": fake}):
        with patch("db_utils.get_db_connection", return_value=cm):
            with patch.object(
                db_utils, "_get_table_columns", return_value=["is_test_data"]
            ):
                with patch.object(
                    db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s
                ):
                    with patch.object(db_utils, "get_placeholder", return_value="%s"):
                        try:
                            db_utils.add_product({"user_id": 1})
                            assert False
                        except ValueError:
                            pass


def test_get_all_products_for_user_pg_path():
    cm, _, cur = _cm()
    cur.fetchall.return_value = [(1, 9, "A"), (2, 9, "B")]
    cur.description = [("id",), ("user_id",), ("name",)]
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            with patch.object(db_utils, "_is_postgresql_connection", return_value=True):
                assert db_utils.get_all_products_for_user(9)[0]["name"] == "A"


def test_get_all_products_for_user_non_pg():
    cm, _, cur = _cm()
    cur.fetchall.return_value = [(1, 9, "X")]
    cur.description = [("id",), ("user_id",), ("name",)]
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            with patch.object(
                db_utils, "_is_postgresql_connection", return_value=False
            ):
                assert db_utils.get_all_products_for_user(9)[0]["name"] == "X"


def test_ensure_admin_product_deletion_pg():
    cm, conn, _ = _cm()
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_is_postgresql_connection", return_value=True):
            db_utils.ensure_admin_product_deletion_allowed()
    assert conn.commit.called


def test_ensure_admin_product_deletion_non_pg():
    cm, conn, _ = _cm()
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_is_postgresql_connection", return_value=False):
            db_utils.ensure_admin_product_deletion_allowed()
    assert conn.commit.called


def test_ensure_admin_product_deletion_exception():
    cm, _, cur = _cm()
    cur.execute.side_effect = db_utils.DB_EXCEPTIONS[0]("x")
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_is_postgresql_connection", return_value=False):
            db_utils.ensure_admin_product_deletion_allowed()


def test_batch_delete_products_empty():
    assert db_utils.batch_delete_products([], 5) == 0


def _bd_ctx():
    fake = types.SimpleNamespace(
        SQLSecurityError=ValueError,
        build_in_clause=lambda ids: ("IN (%s,%s)", list(ids)),
    )
    cm, conn, cur = _cm()
    cur.rowcount = 2
    return cm, conn, cur, fake


def test_batch_delete_products_success():
    cm, conn, cur, fake = _bd_ctx()
    with patch.dict(sys.modules, {"sql_security": fake}):
        with patch("db_utils.get_db_connection", return_value=cm):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                assert db_utils.batch_delete_products([1, 2], 5) == 2
    assert conn.commit.called


def test_batch_delete_products_security_error():
    def _err(*a, **kw):
        raise ValueError("bad")

    fake = types.SimpleNamespace(SQLSecurityError=ValueError, build_in_clause=_err)
    cm, _, _ = _cm()
    with patch.dict(sys.modules, {"sql_security": fake}):
        with patch("db_utils.get_db_connection", return_value=cm):
            try:
                db_utils.batch_delete_products([1], 5)
                assert False
            except ValueError:
                pass


def _cleanup_ctx(cols, exc=None):
    cm, _, cur = _cm()
    cur.rowcount = 3
    if exc:
        return cm, cur, cols, exc
    return cm, cur, cols


def test_cleanup_test_products_with_user():
    cm, cur, cols = _cleanup_ctx(["is_test_data"])
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_get_table_columns", return_value=cols):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                assert db_utils.cleanup_test_products(10) == 3


def test_cleanup_test_products_no_user():
    cm, cur, cols = _cleanup_ctx(["is_test_data"])
    cur.rowcount = 5
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_get_table_columns", return_value=cols):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                assert db_utils.cleanup_test_products() == 5


def test_cleanup_test_products_no_column():
    cm, _, _ = _cm()
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_get_table_columns", return_value=[]):
            assert db_utils.cleanup_test_products() == 0


def test_cleanup_test_products_exception():
    cm, _, _ = _cm()
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_get_table_columns", side_effect=Exception("x")):
            assert db_utils.cleanup_test_products() == 0


def test_update_product_empty_updates():
    assert db_utils.update_product(1, 2, {}) is False


def _up_ctx(rowcount=1):
    fake = types.SimpleNamespace(
        SQLSecurityError=ValueError,
        build_update_set_clause=lambda d, a: ("name=%s", ["n"]),
    )
    cm, conn, cur = _cm()
    cur.rowcount = rowcount
    return cm, conn, cur, fake


def test_update_product_success():
    cm, conn, cur, fake = _up_ctx()
    with patch.dict(sys.modules, {"sql_security": fake}):
        with patch("db_utils.get_db_connection", return_value=cm):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                assert db_utils.update_product(1, 2, {"name": "x"}) is True


def test_update_product_security_error():
    def _bad(*a, **kw):
        raise ValueError("bad")

    fake = types.SimpleNamespace(
        SQLSecurityError=ValueError, build_update_set_clause=_bad
    )
    cm, _, _ = _cm()
    with patch.dict(sys.modules, {"sql_security": fake}):
        with patch("db_utils.get_db_connection", return_value=cm):
            try:
                db_utils.update_product(1, 2, {"name": "x"})
                assert False
            except ValueError:
                pass


def test_batch_update_pricing_params_empty():
    cm, _, _ = _cm()
    with patch("db_utils.get_db_connection", return_value=cm):
        assert db_utils.batch_update_pricing_params([], 2, {"unit_price": 9}) == 0
    with patch("db_utils.get_db_connection", return_value=cm):
        assert db_utils.batch_update_pricing_params([1], 2, {}) == 0


def test_batch_update_pricing_params_success():
    fake = types.SimpleNamespace(
        SQLSecurityError=ValueError,
        build_update_set_clause=lambda d, a: ("unit_price=%s", [9]),
        build_in_clause=lambda ids: ("IN (%s)", [1]),
    )
    cm, conn, cur = _cm()
    cur.rowcount = 1
    with patch.dict(sys.modules, {"sql_security": fake}):
        with patch("db_utils.get_db_connection", return_value=cm):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                assert (
                    db_utils.batch_update_pricing_params([1], 2, {"unit_price": 9}) == 1
                )


def test_batch_update_pricing_params_security_error():
    def _bad(*a, **kw):
        raise ValueError("bad")

    fake = types.SimpleNamespace(
        SQLSecurityError=ValueError, build_update_set_clause=_bad, build_in_clause=_bad
    )
    cm, _, _ = _cm()
    with patch.dict(sys.modules, {"sql_security": fake}):
        with patch("db_utils.get_db_connection", return_value=cm):
            try:
                db_utils.batch_update_pricing_params([1], 2, {"unit_price": 9})
                assert False
            except ValueError:
                pass


def test_calculate_priority_groups_full_flow():
    cm, conn, cur = _cm()
    cur.fetchall.return_value = [
        (1, "land", 1, 2),
        (2, "land", 3, 5),
        (3, "land", 0, 0),
        (4, "air", 2, 4),
        (5, "air", 4, 8),
    ]
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            db_utils.calculate_and_update_priority_groups(7)
    assert conn.commit.called


def test_calculate_priority_groups_empty():
    cm, conn, cur = _cm()
    cur.fetchall.return_value = []
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            db_utils.calculate_and_update_priority_groups(7)
    assert conn.commit.called


def test_calculate_priority_groups_only_zero_days():
    cm, conn, cur = _cm()
    cur.fetchall.return_value = [(1, "land", 0, 0), (2, "air", 0, 0)]
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            db_utils.calculate_and_update_priority_groups(7)
    assert conn.commit.called


def test_get_user_subscription_info_cursor_none():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=(MagicMock(), None))
    cm.__exit__ = MagicMock(return_value=False)
    with patch("db_utils.get_db_connection", return_value=cm):
        assert db_utils.get_user_subscription_info(1) is None


def test_get_user_subscription_info_not_found():
    cm, _, cur = _cm()
    cur.fetchone.return_value = None
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            assert db_utils.get_user_subscription_info(1) is None


def test_get_user_subscription_info_dict():
    cm, _, cur = _cm()
    cur.fetchone.return_value = {"id": 1, "username": "u"}
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            assert db_utils.get_user_subscription_info(1)["id"] == 1


def test_get_user_subscription_info_mapping_like():
    class R:
        def __init__(self, d):
            self._d = d

        def keys(self):
            return self._d.keys()

        def __iter__(self):
            return iter(self._d)

        def __getitem__(self, k):
            return self._d[k]

    cm, _, cur = _cm()
    cur.fetchone.return_value = R({"id": 1})
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            assert "subscription_type" in db_utils.get_user_subscription_info(1)


def test_get_user_subscription_info_short_tuple():
    cm, _, cur = _cm()
    cur.fetchone.return_value = (1, "u")
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            assert db_utils.get_user_subscription_info(1)["role"] is None


def test_get_user_subscription_info_full_tuple():
    cm, _, cur = _cm()
    cur.fetchone.return_value = (
        1,
        "u",
        "free",
        None,
        10,
        None,
        None,
        "user",
        "free",
        None,
    )
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            info = db_utils.get_user_subscription_info(1)
    assert info["id"] == 1 and info["subscription_type"] == "free"


def test_update_user_subscription_success():
    cm, _, cur = _cm()
    cur.rowcount = 1
    with patch("db_utils.get_db_connection", return_value=cm):
        with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
            with patch.object(db_utils, "get_placeholder", return_value="%s"):
                assert (
                    db_utils.update_user_subscription(1, {"user_type": "monthly"})
                    is True
                )


def _sub(info):
    with patch.object(db_utils, "get_user_subscription_info", return_value=info):
        return db_utils.check_user_subscription_status(1)


def test_check_subscription_user_not_found():
    assert _sub(None)["valid"] is False


def test_check_subscription_admin():
    assert _sub({"role": "admin"})["user_type"] == "admin"


def test_check_subscription_permanent():
    assert _sub({"subscription_type": "permanent"})["valid"] is True


def test_check_subscription_test_no_login():
    r = _sub({"subscription_type": "test", "first_login_date": None})
    assert "未开始" in r["message"]


def test_check_subscription_test_active():
    d = (datetime.now() - timedelta(days=2)).isoformat()
    r = _sub({"subscription_type": "test", "first_login_date": d})
    assert r["valid"] is True and "remaining_days" in r


def test_check_subscription_test_expired():
    d = (datetime.now() - timedelta(days=8)).isoformat()
    assert _sub({"subscription_type": "test", "first_login_date": d})["valid"] is False


def test_check_subscription_test_bad_date():
    assert (
        _sub({"subscription_type": "test", "first_login_date": "bad"})["valid"] is True
    )


def test_check_subscription_monthly_active():
    f = (date.today() + timedelta(days=5)).isoformat()
    r = _sub(
        {"subscription_type": "monthly", "expiry_date": f, "remaining_calculations": -1}
    )
    assert r["valid"] is True and "无限次" in r["message"]


def test_check_subscription_monthly_active_limited():
    f = (date.today() + timedelta(days=5)).isoformat()
    r = _sub(
        {"subscription_type": "monthly", "expiry_date": f, "remaining_calculations": 50}
    )
    assert r["valid"] is True and "50次" in r["message"]


def test_check_subscription_monthly_expired():
    p = (date.today() - timedelta(days=1)).isoformat()
    assert (
        _sub(
            {
                "subscription_type": "monthly",
                "expiry_date": p,
                "remaining_calculations": 10,
            }
        )["valid"]
        is False
    )


def test_check_subscription_monthly_no_expiry():
    assert (
        _sub(
            {
                "subscription_type": "monthly",
                "expiry_date": None,
                "remaining_calculations": 10,
            }
        )["valid"]
        is False
    )


def test_check_subscription_monthly_datetime_expiry():
    dt = datetime.now() + timedelta(days=3)
    assert (
        _sub(
            {
                "subscription_type": "monthly",
                "expiry_date": dt,
                "remaining_calculations": -1,
            }
        )["valid"]
        is True
    )


def test_check_subscription_monthly_date_expiry():
    d = date.today() + timedelta(days=3)
    assert (
        _sub(
            {
                "subscription_type": "monthly",
                "expiry_date": d,
                "remaining_calculations": -1,
            }
        )["valid"]
        is True
    )


def test_check_subscription_monthly_iso_T_expiry():
    f = (datetime.now() + timedelta(days=3)).isoformat()
    assert (
        _sub(
            {
                "subscription_type": "monthly",
                "expiry_date": f,
                "remaining_calculations": -1,
            }
        )["valid"]
        is True
    )


def test_check_subscription_monthly_bad_type():
    assert (
        _sub(
            {
                "subscription_type": "monthly",
                "expiry_date": object(),
                "remaining_calculations": 1,
            }
        )["valid"]
        is False
    )


def test_check_subscription_enterprise_active_datetime():
    assert (
        _sub(
            {
                "subscription_type": "enterprise",
                "expiry_date": datetime.now() + timedelta(days=10),
            }
        )["valid"]
        is True
    )


def test_check_subscription_enterprise_active_date():
    assert (
        _sub(
            {
                "subscription_type": "enterprise",
                "expiry_date": date.today() + timedelta(days=2),
            }
        )["valid"]
        is True
    )


def test_check_subscription_enterprise_expired():
    p = (date.today() - timedelta(days=1)).isoformat()
    assert _sub({"subscription_type": "enterprise", "expiry_date": p})["valid"] is False


def test_check_subscription_enterprise_no_expiry():
    assert (
        _sub({"subscription_type": "enterprise", "expiry_date": None})["valid"] is False
    )


def test_check_subscription_enterprise_iso_T():
    f = (datetime.now() + timedelta(days=5)).isoformat()
    assert _sub({"subscription_type": "enterprise", "expiry_date": f})["valid"] is True


def test_check_subscription_enterprise_bad_date():
    assert (
        _sub({"subscription_type": "enterprise", "expiry_date": object()})["valid"]
        is False
    )


def test_check_subscription_gratitude():
    r = _sub({"subscription_type": "gratitude", "remaining_calculations": -1})
    assert r["valid"] is True and r["remaining_days"] == -1


def test_check_subscription_free_normal():
    r = _sub({"subscription_type": "free", "remaining_calculations": 5})
    assert r["valid"] is True and "5次" in r["message"]


def test_check_subscription_free_minus_one_fix():
    fix_cm, fix_conn, _ = _cm()
    with patch.object(
        db_utils,
        "get_user_subscription_info",
        return_value={"subscription_type": "free", "remaining_calculations": -1},
    ):
        with patch("db_utils.get_db_connection", return_value=fix_cm):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                r = db_utils.check_user_subscription_status(2)
    assert r["remaining_calculations"] == 10 and fix_conn.commit.called


def test_check_subscription_free_minus_one_db_error():
    fix_cm, _, fix_cur = _cm()
    fix_cur.execute.side_effect = db_utils.DB_EXCEPTIONS[0]("db error")
    with patch.object(
        db_utils,
        "get_user_subscription_info",
        return_value={"subscription_type": "free", "remaining_calculations": -1},
    ):
        with patch("db_utils.get_db_connection", return_value=fix_cm):
            with patch.object(db_utils, "_safe_adapt_sql", side_effect=lambda s, c: s):
                assert (
                    db_utils.check_user_subscription_status(2)["remaining_calculations"]
                    == 10
                )


def test_check_subscription_efficiency_with_subscription_expires():
    ft = int(time.time()) + 3 * 86400
    r = _sub(
        {
            "subscription_type": "efficiency",
            "remaining_calculations": -1,
            "subscription_expires": ft,
        }
    )
    assert r["valid"] is True and "效率版" in r["message"]


def test_check_subscription_professional_expired_by_timestamp():
    pt = int(time.time()) - 60
    assert (
        _sub(
            {
                "subscription_type": "professional",
                "remaining_calculations": -1,
                "subscription_expires": pt,
            }
        )["valid"]
        is False
    )


def test_check_subscription_efficiency_with_expiry_date():
    f = (datetime.now() + timedelta(days=5)).isoformat()
    assert (
        _sub(
            {
                "subscription_type": "efficiency",
                "remaining_calculations": -1,
                "expiry_date": f,
            }
        )["valid"]
        is True
    )


def test_check_subscription_professional_bad_expiry():
    assert (
        _sub(
            {
                "subscription_type": "professional",
                "remaining_calculations": -1,
                "expiry_date": "invalid",
            }
        )["valid"]
        is False
    )


def test_check_subscription_no_expiry_info():
    r = _sub({"subscription_type": "efficiency", "remaining_calculations": -1})
    assert r["valid"] is False and "不完整" in r["message"]


def test_check_subscription_free_with_subscription_expires():
    ft = int(time.time()) + 2 * 86400
    r = _sub(
        {
            "subscription_type": "free",
            "remaining_calculations": 5,
            "subscription_expires": ft,
        }
    )
    assert r["valid"] is True and "5次" in r["message"]


def test_check_subscription_free_with_unlimited():
    ft = int(time.time()) + 2 * 86400
    with patch.object(
        db_utils,
        "get_user_subscription_info",
        return_value={
            "subscription_type": "free",
            "remaining_calculations": -1,
            "subscription_expires": ft,
        },
    ):
        r = db_utils.check_user_subscription_status(1)
    assert r["remaining_calculations"] == 10


def test_check_subscription_unknown_type():
    assert "未知" in _sub({"subscription_type": "mystery"})["message"]


def test_check_subscription_monthly_pure_date_format():
    f = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
    assert (
        _sub(
            {
                "subscription_type": "monthly",
                "expiry_date": f,
                "remaining_calculations": 10,
            }
        )["valid"]
        is True
    )


def test_check_subscription_enterprise_pure_date_format():
    f = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
    assert _sub({"subscription_type": "enterprise", "expiry_date": f})["valid"] is True
