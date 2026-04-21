# pyright: reportPrivateUsage=false, reportUnusedVariable=false
# -*- coding: utf-8 -*-
import sys
import os
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_security import SessionSecurityEnhanced, SessionSecurity, verify_user  # noqa: E402


def _make_async_session_cm(mock_session=None):
    if mock_session is None:
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm, mock_session


def _inject_security_module(mock_st):
    fake_utils = MagicMock()
    fake_utils._streamlit = mock_st
    sys.modules["security"] = MagicMock(utils=fake_utils)
    sys.modules["security.utils"] = fake_utils
    return fake_utils


def _restore_modules(saved):
    # Only remove keys that were added (not in saved), then restore
    # originals. Avoid sys.modules.clear() which breaks other tests'
    # module references (e.g. app.dependency_overrides).
    added = set(sys.modules) - set(saved)
    for k in added:
        del sys.modules[k]
    sys.modules.update(saved)


class TestDistributedLockRedis:
    def _redis_lock(self, key, client_return=True):
        import session_security_helpers as h

        h.REDIS_AVAILABLE = True
        client = MagicMock()
        client.set.return_value = client_return
        lock = h.DistributedLock(key, timeout=5, redis_available=True)
        return h, client, lock

    def test_acquire_set_true(self):
        import session_security_helpers as h

        orig = h.REDIS_AVAILABLE
        try:
            _, client, lock = self._redis_lock("k1")
            with patch.object(h, "get_redis_client", return_value=client):
                assert lock.acquire() is True and lock.lock_acquired is True
        finally:
            h.REDIS_AVAILABLE = orig

    def test_acquire_set_false(self):
        import session_security_helpers as h

        orig = h.REDIS_AVAILABLE
        try:
            _, client, lock = self._redis_lock("k2", client_return=False)
            with patch.object(h, "get_redis_client", return_value=client):
                assert lock.acquire() is False and lock.lock_acquired is False
        finally:
            h.REDIS_AVAILABLE = orig

    def test_release_calls_delete(self):
        import session_security_helpers as h

        orig = h.REDIS_AVAILABLE
        try:
            _, client, lock = self._redis_lock("k3")
            with patch.object(h, "get_redis_client", return_value=client):
                lock.acquire()
                lock.release()
            client.delete.assert_called_once_with("k3")
            assert lock.lock_acquired is False
        finally:
            h.REDIS_AVAILABLE = orig

    def test_release_no_client_and_no_acquire_noop(self):
        import session_security_helpers as h

        orig = h.REDIS_AVAILABLE
        try:
            _, client, lock = self._redis_lock("k4")
            with patch.object(h, "get_redis_client", return_value=client):
                lock.acquire()
            with patch.object(h, "get_redis_client", return_value=None):
                lock.release()
            assert lock.lock_acquired is False
            lock2 = h.DistributedLock("k6", redis_available=False)
            lock2.release()
            assert lock2.lock_acquired is False
        finally:
            h.REDIS_AVAILABLE = orig

    def test_release_local_runtime_error_suppressed(self):
        import session_security_helpers as h

        lock = h.DistributedLock("k5", redis_available=False)
        lock.lock_acquired = True
        lock.release()
        assert lock.lock_acquired is False

    def test_acquire_no_client_falls_back_local(self):
        import session_security_helpers as h

        orig = h.REDIS_AVAILABLE
        try:
            h.REDIS_AVAILABLE = True
            lock = h.DistributedLock("k7", timeout=5, redis_available=True)
            with patch.object(h, "get_redis_client", return_value=None):
                assert lock.acquire() is True and lock.lock_acquired is True
        finally:
            h.REDIS_AVAILABLE = orig

    def test_redis_unavailable_uses_local_lock(self):
        import session_security_helpers as h

        orig = h.REDIS_AVAILABLE
        try:
            h.REDIS_AVAILABLE = False
            lock = h.DistributedLock("k8", redis_available=True)
            assert lock.redis_available is False
            assert lock.acquire() is True
            lock.release()
        finally:
            h.REDIS_AVAILABLE = orig

    def test_context_manager(self):
        import session_security_helpers as h

        lock = h.DistributedLock("k9", redis_available=False)
        with lock as l:
            assert l.lock_acquired is True
        assert lock.lock_acquired is False


class TestGetClientInfo:
    def _run_with_headers(self, headers_map):
        import session_security_helpers as sh

        mock_headers = MagicMock()
        mock_headers.get = lambda k, *a: headers_map.get(k)
        mock_st = MagicMock()
        mock_st.context.headers = mock_headers
        saved = {k: v for k, v in sys.modules.items()}
        _inject_security_module(mock_st)
        try:
            return sh.get_client_info()
        finally:
            _restore_modules(saved)

    def test_returns_dict_with_keys(self):
        from session_security_helpers import get_client_info

        r = get_client_info()
        assert "ip_address" in r and "user_agent" in r

    def test_import_error_returns_unknown(self):
        real_import = (
            __builtins__.__import__
            if hasattr(__builtins__, "__import__")
            else __import__
        )

        def fake_import(name, *a, **kw):
            if name == "security":
                raise ImportError("no module")
            return real_import(name, *a, **kw)

        import builtins

        with patch.object(builtins, "__import__", side_effect=fake_import):
            from session_security_helpers import get_client_info

            r = get_client_info()
        assert r == {"ip_address": "unknown", "user_agent": "unknown"}

    def test_no_streamlit_attr_returns_unknown(self):
        import session_security_helpers as sh

        saved = {k: v for k, v in sys.modules.items()}
        fake_utils = MagicMock(spec=[])
        sys.modules["security"] = MagicMock(utils=fake_utils)
        sys.modules["security.utils"] = fake_utils
        try:
            assert sh.get_client_info()["ip_address"] == "unknown"
        finally:
            _restore_modules(saved)

    def test_headers_falsy_returns_unknown(self):
        import session_security_helpers as sh

        mock_st = MagicMock()
        mock_st.context.headers = None
        saved = {k: v for k, v in sys.modules.items()}
        _inject_security_module(mock_st)
        try:
            assert sh.get_client_info()["ip_address"] == "unknown"
        finally:
            _restore_modules(saved)

    def test_x_forwarded_for_extracted_with_user_agent(self):
        r = self._run_with_headers(
            {
                "X-Forwarded-For": "192.168.1.1, 10.0.0.1",
                "X-Real-IP": None,
                "User-Agent": "TestUA",
            }
        )
        assert r["ip_address"] == "192.168.1.1" and r["user_agent"] == "TestUA"

    def test_x_forwarded_for_none_uses_x_real_ip(self):
        r = self._run_with_headers(
            {"X-Forwarded-For": None, "X-Real-IP": "10.0.0.5", "User-Agent": None}
        )
        assert r["ip_address"] == "10.0.0.5"

    def test_x_forwarded_for_magicmock_guard(self):
        r = self._run_with_headers(
            {"X-Forwarded-For": "MagicMock-val", "X-Real-IP": None, "User-Agent": None}
        )
        assert r["ip_address"] == "unknown"

    def test_x_real_ip_magicmock_guard(self):
        r = self._run_with_headers(
            {"X-Forwarded-For": None, "X-Real-IP": "MagicMock-IP", "User-Agent": None}
        )
        assert r["ip_address"] == "unknown"

    def test_user_agent_magicmock_guard(self):
        r = self._run_with_headers(
            {"X-Forwarded-For": None, "X-Real-IP": None, "User-Agent": "MagicMock-UA"}
        )
        assert r["user_agent"] == "unknown"

    def test_attribute_error_suppressed(self):
        import session_security_helpers as sh

        fake_utils = MagicMock()
        fake_utils._streamlit = MagicMock()
        type(fake_utils._streamlit.context).headers = property(
            lambda self: (_ for _ in ()).throw(AttributeError("no headers"))
        )
        saved = {k: v for k, v in sys.modules.items()}
        sys.modules["security"] = MagicMock(utils=fake_utils)
        sys.modules["security.utils"] = fake_utils
        try:
            assert sh.get_client_info()["ip_address"] == "unknown"
        finally:
            _restore_modules(saved)

    def test_no_context_headers_attr(self):
        import session_security_helpers as sh

        mock_st = MagicMock(spec=["context"])
        mock_st.context = MagicMock(spec=[])
        saved = {k: v for k, v in sys.modules.items()}
        _inject_security_module(mock_st)
        try:
            assert sh.get_client_info()["ip_address"] == "unknown"
        finally:
            _restore_modules(saved)


class TestGetClientInfoStatic:
    def test_delegates_to_helper(self):
        with patch(
            "session_security.get_client_info",
            return_value={"ip_address": "1.2.3.4", "user_agent": "UA"},
        ) as m:
            r = SessionSecurityEnhanced.get_client_info()
            m.assert_called_once()
            assert r["ip_address"] == "1.2.3.4"


class TestCheckAndCreateSessionAtomic:
    @patch("session_security.insert_session", new_callable=AsyncMock)
    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_success_below_max(self, mock_sl, mock_count, mock_insert):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_count.return_value = 2
        mock_insert.return_value = None
        with patch("session_security.DistributedLock", return_value=MagicMock()):
            ok, msg = await SessionSecurityEnhanced.check_and_create_session_atomic(
                1, "s", "ip", "ua"
            )
        assert ok is True and "成功" in msg

    @patch("session_security.insert_session", new_callable=AsyncMock)
    @patch("session_security.deactivate_session", new_callable=AsyncMock)
    @patch("session_security.get_oldest_active_session", new_callable=AsyncMock)
    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_success_at_max(
        self, mock_sl, mock_count, mock_oldest, mock_deact, mock_insert
    ):
        mock_cm, mock_session = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_count.return_value = 5
        oldest = MagicMock()
        oldest.session_id = "old"
        mock_oldest.return_value = oldest
        mock_deact.return_value = None
        mock_insert.return_value = None
        with patch("session_security.DistributedLock", return_value=MagicMock()):
            ok, _ = await SessionSecurityEnhanced.check_and_create_session_atomic(
                1, "s", "ip", "ua"
            )
        assert ok is True
        mock_deact.assert_awaited_once_with(
            mock_session,
            "old",
            reason="kicked_by_max_concurrent",
        )

    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_exception_returns_false(self, mock_sl, mock_count):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_count.side_effect = Exception("DB err")
        with patch("session_security.DistributedLock", return_value=MagicMock()):
            ok, msg = await SessionSecurityEnhanced.check_and_create_session_atomic(
                1, "s", "ip", "ua"
            )
        assert ok is False and "失败" in msg

    @patch("session_security.get_oldest_active_session", new_callable=AsyncMock)
    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_no_oldest_session(self, mock_sl, mock_count, mock_oldest):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_count.return_value = 5
        mock_oldest.return_value = None
        with patch("session_security.DistributedLock", return_value=MagicMock()):
            with patch("session_security.insert_session", new_callable=AsyncMock):
                ok, _ = await SessionSecurityEnhanced.check_and_create_session_atomic(
                    1, "s", "ip", "ua"
                )
        assert ok is True


class TestUpdateSessionActivityAtomic:
    @patch("session_security.update_session_activity", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_success(self, mock_sl, mock_update):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_update.return_value = None
        with patch("session_security.DistributedLock", return_value=MagicMock()):
            assert (
                await SessionSecurityEnhanced.update_session_activity_atomic("s")
                is True
            )

    @patch("session_security.update_session_activity", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_exception_returns_false(self, mock_sl, mock_update):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_update.side_effect = Exception("err")
        with patch("session_security.DistributedLock", return_value=MagicMock()):
            assert (
                await SessionSecurityEnhanced.update_session_activity_atomic("s")
                is False
            )


class TestCheckSuspiciousIp:
    async def test_localhost_addresses(self):
        for addr in ("localhost", "127.0.0.1", "::1"):
            ok, msg = await SessionSecurityEnhanced.check_suspicious_ip(1, addr)
            assert ok is False and msg == ""

    async def test_non_localhost_addresses(self):
        for addr in ("192.168.1.1", "10.0.0.1", "8.8.8.8"):
            ok, msg = await SessionSecurityEnhanced.check_suspicious_ip(1, addr)
            assert ok is False and msg == ""


class TestRecordLoginAttempt:
    @patch("session_security.add_login_attempt", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_success(self, mock_sl, mock_add):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_add.return_value = None
        await SessionSecurityEnhanced.record_login_attempt("user", True)
        mock_add.assert_called_once()

    @patch("session_security.add_login_attempt", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_exception_not_raised(self, mock_sl, mock_add):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_add.side_effect = Exception("err")
        await SessionSecurityEnhanced.record_login_attempt("user", False)

    @patch("session_security.AsyncSessionLocal")
    async def test_session_error_not_raised(self, mock_sl):
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("conn"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_sl.return_value = mock_cm
        await SessionSecurityEnhanced.record_login_attempt("user", True)


class TestCreateSession:
    @patch("session_security.insert_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_success_returns_session_id(self, mock_sl, mock_insert):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_insert.return_value = None
        sid = await SessionSecurityEnhanced.create_session(
            42, {"ip_address": "1.2.3.4", "user_agent": "UA"}
        )
        assert sid is not None and len(sid) == 64

    @patch("session_security.insert_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_missing_user_info_uses_defaults(self, mock_sl, mock_insert):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_insert.return_value = None
        assert await SessionSecurityEnhanced.create_session(1, {}) is not None

    @patch("session_security.insert_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_db_error_returns_none(self, mock_sl, mock_insert):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_insert.side_effect = Exception("DB error")
        assert await SessionSecurityEnhanced.create_session(1, {}) is None


class TestGetSessionInfo:
    @patch("session_security.get_session_with_user", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_returns_data(self, mock_sl, mock_get):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_get.return_value = {"user_id": 1}
        assert await SessionSecurityEnhanced.get_session_info("s") == {"user_id": 1}

    @patch("session_security.get_session_with_user", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_not_found_returns_none(self, mock_sl, mock_get):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_get.return_value = None
        assert await SessionSecurityEnhanced.get_session_info("s") is None

    @patch("session_security.AsyncSessionLocal")
    async def test_exception_returns_none(self, mock_sl):
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("err"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_sl.return_value = mock_cm
        assert await SessionSecurityEnhanced.get_session_info("s") is None


class TestCheckConcurrentSessions:
    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_under_limit_returns_true_empty(self, mock_sl, mock_count):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_count.return_value = 2
        ok, msg = await SessionSecurityEnhanced.check_concurrent_sessions(1)
        assert ok is True and msg == ""

    @patch("session_security.deactivate_session", new_callable=AsyncMock)
    @patch("session_security.get_oldest_active_session", new_callable=AsyncMock)
    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_at_max_deactivates_oldest(
        self, mock_sl, mock_count, mock_oldest, mock_deact
    ):
        mock_cm, mock_session = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_count.return_value = 5
        oldest = MagicMock()
        oldest.session_id = "old"
        mock_oldest.return_value = oldest
        mock_deact.return_value = None
        ok, msg = await SessionSecurityEnhanced.check_concurrent_sessions(1)
        assert ok is True and "超过" in msg
        mock_deact.assert_awaited_once_with(
            mock_session,
            "old",
            reason="kicked_by_max_concurrent",
        )

    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_exception_returns_true_empty(self, mock_sl, mock_count):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_count.side_effect = Exception("err")
        ok, msg = await SessionSecurityEnhanced.check_concurrent_sessions(1)
        assert ok is True and msg == ""


class TestForceLogoutSession:
    @patch("session_security.deactivate_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_success(self, mock_sl, mock_deact):
        mock_cm, mock_session = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_deact.return_value = None
        assert await SessionSecurityEnhanced.force_logout_session("s", "reason") is True
        mock_deact.assert_awaited_once_with(mock_session, "s", reason="reason")

    @patch("session_security.deactivate_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_exception_returns_false(self, mock_sl, mock_deact):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_deact.side_effect = Exception("err")
        assert (
            await SessionSecurityEnhanced.force_logout_session("s", "reason") is False
        )

    @patch("session_security.AsyncSessionLocal")
    async def test_session_error_returns_false(self, mock_sl):
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("conn"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_sl.return_value = mock_cm
        assert (
            await SessionSecurityEnhanced.force_logout_session("s", "reason") is False
        )


class TestIsUserLocked:
    def test_always_false(self):
        assert SessionSecurityEnhanced.is_user_locked(1) is False
        assert SessionSecurityEnhanced.is_user_locked(999) is False


class TestVerifySessionId:
    @patch(
        "session_security.SessionSecurityEnhanced.get_session_info",
        new_callable=AsyncMock,
    )
    async def test_found_returns_true_info(self, mock_get):
        mock_get.return_value = {"user_id": 1}
        ok, info = await SessionSecurityEnhanced.verify_session_id("s")
        assert ok is True and info == {"user_id": 1}

    @patch(
        "session_security.SessionSecurityEnhanced.get_session_info",
        new_callable=AsyncMock,
    )
    async def test_not_found_returns_false_empty(self, mock_get):
        mock_get.return_value = None
        ok, info = await SessionSecurityEnhanced.verify_session_id("s")
        assert ok is False and info == {}

    @patch(
        "session_security.SessionSecurityEnhanced.get_session_info",
        new_callable=AsyncMock,
    )
    async def test_exception_returns_false_empty(self, mock_get):
        mock_get.side_effect = Exception("err")
        ok, info = await SessionSecurityEnhanced.verify_session_id("s")
        assert ok is False and info == {}


class TestGetSessionTimeout:
    def test_returns_constant(self):
        assert SessionSecurityEnhanced.get_session_timeout() == 3600
        assert (
            SessionSecurityEnhanced.get_session_timeout(user_id=1, user_type="admin")
            == 3600
        )


class TestInvalidateUserSessions:
    @patch("session_security.deactivate_all_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_success_returns_1(self, mock_sl, mock_deact):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_deact.return_value = None
        assert await SessionSecurityEnhanced.invalidate_user_sessions(1) == 1

    @patch("session_security.deactivate_all_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_success_with_exclude(self, mock_sl, mock_deact):
        mock_cm, mock_session = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_deact.return_value = None
        assert (
            await SessionSecurityEnhanced.invalidate_user_sessions(
                1, exclude_session_id="keep"
            )
            == 1
        )
        mock_deact.assert_awaited_once_with(
            mock_session,
            1,
            exclude_session_id="keep",
            reason=None,
        )

    @patch("session_security.deactivate_all_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_reason_passed_to_deactivate_all_sessions(
        self,
        mock_sl,
        mock_deact,
    ):
        mock_cm, mock_session = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_deact.return_value = None
        result = await SessionSecurityEnhanced.invalidate_user_sessions(
            1,
            exclude_session_id="keep",
            reason="password_reset",
        )
        assert result == 1
        mock_deact.assert_awaited_once_with(
            mock_session,
            1,
            exclude_session_id="keep",
            reason="password_reset",
        )

    @patch("session_security.AsyncSessionLocal")
    async def test_exception_returns_0(self, mock_sl):
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("err"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_sl.return_value = mock_cm
        assert await SessionSecurityEnhanced.invalidate_user_sessions(1) == 0


class TestHmacSecret:
    def setup_method(self):
        SessionSecurityEnhanced._hmac_secret_cache = None

    def teardown_method(self):
        SessionSecurityEnhanced._hmac_secret_cache = None

    def test_hmac_secret_delegates(self):
        with patch.object(
            SessionSecurityEnhanced, "_get_hmac_secret", return_value="s"
        ) as m:
            assert SessionSecurityEnhanced.hmac_secret() == "s"
        m.assert_called_once()

    def test_cache_hit_returns_cached(self):
        SessionSecurityEnhanced._hmac_secret_cache = "cached"
        assert SessionSecurityEnhanced._get_hmac_secret() == "cached"

    def test_dev_mode_default_secret(self):
        with patch.dict(os.environ, {"PRODUCTION_MODE": "false"}, clear=True):
            r = SessionSecurityEnhanced._get_hmac_secret()
        assert r == "dev-only-hmac-secret-do-not-use-in-production"

    def test_dev_mode_custom_secret(self):
        with patch.dict(
            os.environ,
            {"PRODUCTION_MODE": "false", "SESSION_HMAC_SECRET": "custom"},
            clear=True,
        ):
            r = SessionSecurityEnhanced._get_hmac_secret()
        assert r == "custom"

    def test_prod_mode_raises_without_secret(self):
        # _get_hmac_secret() skips the raise when "pytest" is in
        # sys.modules (test-env safety net).  Temporarily hide it so
        # the production-mode ValueError fires as expected.
        import sys as _sys

        saved = _sys.modules.pop("pytest", None)
        saved_env = _sys.modules.pop("PYTEST_CURRENT_TEST", None)  # noqa: F841
        try:
            with patch.dict(
                os.environ,
                {"PRODUCTION_MODE": "true"},
                clear=True,
            ):
                try:
                    SessionSecurityEnhanced._get_hmac_secret()
                    assert False, "Should raise"
                except ValueError as e:
                    assert "SESSION_HMAC_SECRET" in str(e)
        finally:
            if saved is not None:
                _sys.modules["pytest"] = saved

    def test_prod_mode_with_secret(self):
        with patch.dict(
            os.environ,
            {"PRODUCTION_MODE": "true", "SESSION_HMAC_SECRET": "prod-secret"},
            clear=True,
        ):
            r = SessionSecurityEnhanced._get_hmac_secret()
        assert r == "prod-secret"

    def test_result_is_cached(self):
        with patch.dict(os.environ, {"PRODUCTION_MODE": "false"}, clear=True):
            SessionSecurityEnhanced._get_hmac_secret()
        assert SessionSecurityEnhanced._hmac_secret_cache is not None


class TestVerifyUser:
    @patch("session_security.verify_user_db", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_class_method(self, mock_sl, mock_verify):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_verify.return_value = {"id": 1}
        r = await SessionSecurityEnhanced.verify_user("u", "p")
        assert r == {"id": 1}

    @patch("session_security.verify_user_db", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_module_level(self, mock_sl, mock_verify):
        mock_cm, _ = _make_async_session_cm()
        mock_sl.return_value = mock_cm
        mock_verify.return_value = {"id": 2}
        r = await verify_user("u2", "p2")
        assert r == {"id": 2}


class TestVerifyPasswordForSensitiveOperation:
    @patch("session_security.verify_user", new_callable=AsyncMock)
    async def test_success_returns_true(self, mock_verify):
        mock_verify.return_value = {"id": 1}
        assert (
            await SessionSecurityEnhanced.verify_password_for_sensitive_operation(
                1, "p"
            )
            is True
        )

    @patch("session_security.verify_user", new_callable=AsyncMock)
    async def test_none_returns_false(self, mock_verify):
        mock_verify.return_value = None
        assert (
            await SessionSecurityEnhanced.verify_password_for_sensitive_operation(
                1, "p"
            )
            is False
        )

    @patch("session_security.verify_user", new_callable=AsyncMock)
    async def test_exception_returns_false(self, mock_verify):
        mock_verify.side_effect = Exception("err")
        assert (
            await SessionSecurityEnhanced.verify_password_for_sensitive_operation(
                1, "p"
            )
            is False
        )


class TestSessionSecurityMisc:
    def test_session_security_alias(self):
        assert SessionSecurity is SessionSecurityEnhanced

    def test_session_security_self_ref(self):
        assert SessionSecurityEnhanced.SessionSecurity is SessionSecurityEnhanced

    def test_generate_session_id(self):
        sid = SessionSecurityEnhanced.generate_session_id(1)
        assert isinstance(sid, str) and len(sid) == 64

    def test_generate_session_id_unique(self):
        ids = {SessionSecurityEnhanced.generate_session_id(1) for _ in range(5)}
        assert len(ids) == 5


class TestRedisAvailability:
    def test_redis_available_is_bool(self):
        from session_security_helpers import REDIS_AVAILABLE

        assert isinstance(REDIS_AVAILABLE, bool)

    def test_get_redis_client_callable(self):
        from session_security_helpers import get_redis_client

        assert callable(get_redis_client)

    def test_fallback_get_redis_client_returns_none(self):
        import session_security_helpers as h

        if not h.REDIS_AVAILABLE:
            assert h.get_redis_client() is None

    def test_lock_redis_flag_false_when_unavailable(self):
        import session_security_helpers as h

        orig = h.REDIS_AVAILABLE
        try:
            h.REDIS_AVAILABLE = False
            lock = h.DistributedLock("k", redis_available=True)
            assert lock.redis_available is False
        finally:
            h.REDIS_AVAILABLE = orig

    def test_lock_redis_flag_true_when_available(self):
        import session_security_helpers as h

        orig = h.REDIS_AVAILABLE
        try:
            h.REDIS_AVAILABLE = True
            lock = h.DistributedLock("k", redis_available=True)
            assert lock.redis_available is True
        finally:
            h.REDIS_AVAILABLE = orig
