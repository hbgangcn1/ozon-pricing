"""Coverage tests for database.py edge cases."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import InterfaceError as SAInterfaceError


class TestIsConnectionDead:
    def test_interface_error_returns_true(self):
        from database import _is_connection_dead

        exc = SAInterfaceError("SELECT 1", {}, RuntimeError("closed"))
        assert _is_connection_dead(exc) is True

    def test_connection_closed_message(self):
        from database import _is_connection_dead

        assert _is_connection_dead(RuntimeError("connection closed")) is True

    def test_connection_does_not_exist_message(self):
        from database import _is_connection_dead

        assert _is_connection_dead(RuntimeError("connection does not exist")) is True

    def test_unrelated_error_returns_false(self):
        from database import _is_connection_dead

        assert _is_connection_dead(RuntimeError("something else")) is False


class TestGetDbRollbackFailure:
    @pytest.mark.asyncio
    async def test_rollback_failure_logs_warning(self):
        from database import get_db

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock(side_effect=RuntimeError("DB down"))
        mock_session.rollback = AsyncMock(side_effect=RuntimeError("rollback also failed"))

        mock_local = MagicMock()
        mock_local.__aenter__ = AsyncMock(return_value=mock_session)
        mock_local.__aexit__ = AsyncMock(return_value=False)

        with patch("database.AsyncSessionLocal", return_value=mock_local):
            with patch("database.logger") as mock_logger:
                gen = get_db()
                await gen.__anext__()
                try:
                    await gen.athrow(RuntimeError("DB down"))
                except RuntimeError:
                    pass

        mock_logger.warning.assert_called_once()
        args = mock_logger.warning.call_args[0]
        assert "数据库连接已断开" in args[0]


