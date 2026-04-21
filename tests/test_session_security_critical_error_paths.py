# pyright: reportUnusedImport=false, reportUnusedVariable=false
"""
测试 session_security.py 安全关键路径的异常处理
覆盖 create_session、check_concurrent_sessions、
check_suspicious_ip、force_logout_session 的异常处理路径
"""

import sys
import os
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_async_session_cm(mock_session=None):
    """创建模拟的异步上下文管理器（AsyncSessionLocal()）"""
    if mock_session is None:
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm, mock_session


class TestSessionSecurityCriticalErrorPaths:
    """测试会话安全关键路径的异常处理"""

    @patch("session_security.insert_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_create_session_db_error(self, mock_session_local, mock_insert):
        """测试创建会话时数据库错误返回None"""
        mock_cm, mock_session = _make_async_session_cm()
        mock_session_local.return_value = mock_cm

        mock_insert.side_effect = Exception("DB error")

        from session_security import SessionSecurity

        result = await SessionSecurity.create_session(1, {"username": "test"})
        assert result is None

    @patch("session_security.deactivate_session", new_callable=AsyncMock)
    @patch("session_security.get_oldest_active_session", new_callable=AsyncMock)
    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.insert_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_create_session_concurrent_limit_deactivation(
        self,
        mock_session_local,
        mock_insert,
        mock_count,
        mock_oldest,
        mock_deactivate,
    ):
        """测试并发会话上限时自动下线最旧会话"""
        mock_cm, mock_session = _make_async_session_cm()
        mock_session_local.return_value = mock_cm

        mock_count.return_value = 5  # >= MAX_CONCURRENT_SESSIONS
        oldest = MagicMock()
        oldest.session_id = "old_session_1"
        mock_oldest.return_value = oldest
        mock_deactivate.side_effect = Exception("下线超时")
        mock_insert.return_value = None

        from session_security import SessionSecurity

        result, msg = await SessionSecurity.check_and_create_session_atomic(
            1, "new_sess", "127.0.0.1", "TestAgent"
        )
        # 下线失败时整体返回 False
        assert result is False

    @patch("session_security.insert_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_create_session_rollback_failure(
        self, mock_session_local, mock_insert
    ):
        """测试回滚也失败时不崩溃"""
        mock_cm, mock_session = _make_async_session_cm()
        mock_session_local.return_value = mock_cm

        mock_insert.side_effect = Exception("插入失败")
        mock_session.rollback.side_effect = Exception("回滚失败")

        from session_security import SessionSecurity

        # create_session 捕获所有异常并返回 None
        result = await SessionSecurity.create_session(1, {"username": "test"})
        assert result is None

    @patch("session_security.AsyncSessionLocal")
    async def test_check_concurrent_sessions_session_error(self, mock_session_local):
        """测试 AsyncSessionLocal __aenter__ 失败时返回 (True, '')"""
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("连接池已关闭"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_local.return_value = mock_cm

        from session_security import SessionSecurity

        allowed, msg = await SessionSecurity.check_concurrent_sessions(1)
        assert isinstance(allowed, bool)
        assert allowed is True

    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_check_concurrent_sessions_count_error(
        self, mock_session_local, mock_count
    ):
        """测试 count_active_sessions 抛出异常时返回 (True, '')"""
        mock_cm, mock_session = _make_async_session_cm()
        mock_session_local.return_value = mock_cm

        mock_count.side_effect = Exception("查询失败")

        from session_security import SessionSecurity

        allowed, msg = await SessionSecurity.check_concurrent_sessions(1)
        assert allowed is True
        assert msg == ""

    async def test_check_suspicious_ip_localhost(self):
        """测试本地地址不被标记为可疑"""
        from session_security import SessionSecurity

        for addr in ("localhost", "127.0.0.1", "::1"):
            allowed, msg = await SessionSecurity.check_suspicious_ip(1, addr)
            assert allowed is False
            assert msg == ""

    @patch("session_security.deactivate_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_force_logout_session_db_error(
        self, mock_session_local, mock_deactivate
    ):
        """测试 deactivate_session 抛出异常时返回 False"""
        mock_cm, mock_session = _make_async_session_cm()
        mock_session_local.return_value = mock_cm

        mock_deactivate.side_effect = Exception("statement timeout")

        from session_security import SessionSecurity

        result = await SessionSecurity.force_logout_session("test_session", "测试原因")
        assert result is False

    @patch("session_security.deactivate_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_force_logout_session_success(
        self, mock_session_local, mock_deactivate
    ):
        """测试 force_logout_session 成功时返回 True"""
        mock_cm, mock_session = _make_async_session_cm()
        mock_session_local.return_value = mock_cm

        mock_deactivate.return_value = None

        from session_security import SessionSecurity

        result = await SessionSecurity.force_logout_session("test_session", "测试原因")
        assert result is True
        mock_deactivate.assert_awaited_once_with(
            mock_session,
            "test_session",
            reason="测试原因",
        )

    @patch("session_security.AsyncSessionLocal")
    async def test_force_logout_session_factory_error(self, mock_session_local):
        """测试 AsyncSessionLocal 工厂抛出异常时返回 False"""
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("连接失败"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_local.return_value = mock_cm

        from session_security import SessionSecurity

        result = await SessionSecurity.force_logout_session("test_session", "测试原因")
        assert result is False

    @patch("session_security.insert_session", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_create_session_generic_exception(
        self, mock_session_local, mock_insert
    ):
        """测试通用异常时 create_session 返回 None"""
        mock_cm, mock_session = _make_async_session_cm()
        mock_session_local.return_value = mock_cm

        mock_insert.side_effect = RuntimeError("其他数据库错误")

        from session_security import SessionSecurity

        result = await SessionSecurity.create_session(1, {"username": "test"})
        assert result is None

    @patch("session_security.deactivate_session", new_callable=AsyncMock)
    @patch("session_security.get_oldest_active_session", new_callable=AsyncMock)
    @patch("session_security.count_active_sessions", new_callable=AsyncMock)
    @patch("session_security.AsyncSessionLocal")
    async def test_check_concurrent_max_sessions_auto_deactivate(
        self,
        mock_session_local,
        mock_count,
        mock_oldest,
        mock_deactivate,
    ):
        """测试超过最大并发会话数时自动下线并返回 (True, '超过...')"""
        mock_cm, mock_session = _make_async_session_cm()
        mock_session_local.return_value = mock_cm

        mock_count.return_value = 5  # >= MAX_CONCURRENT_SESSIONS
        oldest = MagicMock()
        oldest.session_id = "oldest_sess"
        mock_oldest.return_value = oldest
        mock_deactivate.return_value = None

        from session_security import SessionSecurity

        allowed, msg = await SessionSecurity.check_concurrent_sessions(1)
        assert allowed is True
        assert "超过最大并发会话数" in msg
        mock_deactivate.assert_awaited_once_with(
            mock_session,
            "oldest_sess",
            reason="kicked_by_max_concurrent",
        )
