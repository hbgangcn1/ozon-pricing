# -*- coding: utf-8 -*-
"""
postgres_backup_service_settings.py 单元测试
"""
import pytest
from unittest.mock import MagicMock, patch


class TestGetAutoBackupSettings:
    def test_get_settings_defaults_when_no_config(self):
        with patch(
            "postgres_backup_service_settings.try_get_system_config",
            return_value=None,
        ):
            backup_system = MagicMock()
            backup_system.backup_interval_hours = 24
            backup_system.max_backups = 10

            from postgres_backup_service_settings import get_auto_backup_settings

            result = get_auto_backup_settings(backup_system)
            assert result["enabled"] is True
            assert result["interval_hours"] == 24
            assert result["max_backups"] == 10

    def test_get_settings_reads_from_config(self):
        mock_get_config = MagicMock(
            side_effect=lambda key, default: {
                "auto_backup_enabled": "false",
                "auto_backup_interval_hours": "12",
                "auto_backup_max_backups": "5",
            }.get(key, default)
        )
        with patch(
            "postgres_backup_service_settings.try_get_system_config",
            return_value=mock_get_config,
        ):
            backup_system = MagicMock()
            backup_system.backup_interval_hours = 24
            backup_system.max_backups = 10

            from postgres_backup_service_settings import get_auto_backup_settings

            result = get_auto_backup_settings(backup_system)
            assert result["enabled"] is False
            assert result["interval_hours"] == 12
            assert result["max_backups"] == 5

    def test_get_settings_uses_defaults_for_invalid_values(self):
        mock_get_config = MagicMock(
            side_effect=lambda key, default: {
                "auto_backup_enabled": "invalid",
                "auto_backup_interval_hours": "invalid",
                "auto_backup_max_backups": "invalid",
            }.get(key, default)
        )
        with patch(
            "postgres_backup_service_settings.try_get_system_config",
            return_value=mock_get_config,
        ):
            backup_system = MagicMock()
            backup_system.backup_interval_hours = 24
            backup_system.max_backups = 10

            from postgres_backup_service_settings import get_auto_backup_settings

            result = get_auto_backup_settings(backup_system)
            assert result["enabled"] is False
            assert result["interval_hours"] == 24
            assert result["max_backups"] == 10


class TestResolveBackupSettingsUpdate:
    def test_resolve_with_settings_dict(self):
        from postgres_backup_service_settings import resolve_backup_settings_update

        current = {"enabled": True, "interval_hours": 24, "max_backups": 10}
        settings = {"enabled": False, "interval_hours": 12, "max_backups": 5}

        result = resolve_backup_settings_update(
            current,
            settings=settings,
            enabled=None,
            interval_hours=None,
            max_backups=None,
        )
        assert result["enabled"] is False
        assert result["interval_hours"] == 12
        assert result["max_backups"] == 5

    def test_resolve_with_kwarg_enabled(self):
        from postgres_backup_service_settings import resolve_backup_settings_update

        current = {"enabled": True, "interval_hours": 24, "max_backups": 10}

        result = resolve_backup_settings_update(
            current,
            settings=None,
            enabled=False,
            interval_hours=None,
            max_backups=None,
        )
        assert result["enabled"] is False
        assert result["interval_hours"] == 24
        assert result["max_backups"] == 10

    def test_resolve_with_kwarg_interval_hours(self):
        from postgres_backup_service_settings import resolve_backup_settings_update

        current = {"enabled": True, "interval_hours": 24, "max_backups": 10}

        result = resolve_backup_settings_update(
            current,
            settings=None,
            enabled=None,
            interval_hours=12,
            max_backups=None,
        )
        assert result["interval_hours"] == 12

    def test_resolve_with_kwarg_max_backups(self):
        from postgres_backup_service_settings import resolve_backup_settings_update

        current = {"enabled": True, "interval_hours": 24, "max_backups": 10}

        result = resolve_backup_settings_update(
            current,
            settings=None,
            enabled=None,
            interval_hours=None,
            max_backups=5,
        )
        assert result["max_backups"] == 5

    def test_resolve_enforces_minimum_interval(self):
        from postgres_backup_service_settings import resolve_backup_settings_update

        current = {"enabled": True, "interval_hours": 24, "max_backups": 10}

        result = resolve_backup_settings_update(
            current,
            settings=None,
            enabled=None,
            interval_hours=0,
            max_backups=None,
        )
        assert result["interval_hours"] == 1

    def test_resolve_enforces_minimum_max_backups(self):
        from postgres_backup_service_settings import resolve_backup_settings_update

        current = {"enabled": True, "interval_hours": 24, "max_backups": 10}

        result = resolve_backup_settings_update(
            current,
            settings=None,
            enabled=None,
            interval_hours=None,
            max_backups=0,
        )
        assert result["max_backups"] == 1


class TestApplyBackupSettings:
    def test_apply_disables_running_backup(self):
        from postgres_backup_service_settings import apply_backup_settings

        backup_system = MagicMock()
        backup_system.is_running = True
        backup_system.backup_interval_hours = 24
        backup_system.max_backups = 10
        stop_fn = MagicMock()
        start_fn = MagicMock()

        settings = {"enabled": False, "interval_hours": 24, "max_backups": 10}
        result = apply_backup_settings(
            backup_system, settings, stop_fn, start_fn
        )

        assert result is True
        stop_fn.assert_called_once()
        start_fn.assert_not_called()

    def test_apply_enables_stopped_backup(self):
        from postgres_backup_service_settings import apply_backup_settings

        backup_system = MagicMock()
        backup_system.is_running = False
        backup_system.backup_interval_hours = 24
        backup_system.max_backups = 10
        stop_fn = MagicMock()
        start_fn = MagicMock()

        settings = {"enabled": True, "interval_hours": 24, "max_backups": 10}
        result = apply_backup_settings(
            backup_system, settings, stop_fn, start_fn
        )

        assert result is True
        start_fn.assert_called_once()
        stop_fn.assert_not_called()

    def test_apply_restarts_on_interval_change(self):
        from postgres_backup_service_settings import apply_backup_settings

        backup_system = MagicMock()
        backup_system.is_running = True
        backup_system.backup_interval_hours = 24
        backup_system.max_backups = 10
        stop_fn = MagicMock()
        start_fn = MagicMock()

        settings = {"enabled": True, "interval_hours": 12, "max_backups": 10}
        result = apply_backup_settings(
            backup_system, settings, stop_fn, start_fn
        )

        assert result is True
        stop_fn.assert_called_once()
        start_fn.assert_called_once()

    def test_apply_no_change(self):
        from postgres_backup_service_settings import apply_backup_settings

        backup_system = MagicMock()
        backup_system.is_running = True
        backup_system.backup_interval_hours = 24
        backup_system.max_backups = 10
        stop_fn = MagicMock()
        start_fn = MagicMock()

        settings = {"enabled": True, "interval_hours": 24, "max_backups": 10}
        result = apply_backup_settings(
            backup_system, settings, stop_fn, start_fn
        )

        assert result is True
        stop_fn.assert_not_called()
        start_fn.assert_not_called()


class TestUpdateAutoBackupSettings:
    @patch(
        "postgres_backup_service_settings.try_get_system_config",
        return_value=None,
    )
    @patch("postgres_backup_service_settings.persist_backup_settings")
    @patch("postgres_backup_service_settings.apply_backup_settings")
    def test_update_calls_apply(
        self, mock_apply, mock_persist, mock_get_config
    ):
        from postgres_backup_service_settings import update_auto_backup_settings

        backup_system = MagicMock()
        backup_system.is_running = True
        backup_system.backup_interval_hours = 24
        backup_system.max_backups = 10
        stop_fn = MagicMock()
        start_fn = MagicMock()
        mock_apply.return_value = True

        result = update_auto_backup_settings(
            backup_system, stop_fn, start_fn, enabled=False
        )

        assert result is True
        mock_persist.assert_called_once()
        mock_apply.assert_called_once()

    @patch(
        "postgres_backup_service_settings.try_get_system_config",
        return_value=None,
    )
    @patch("postgres_backup_service_settings.persist_backup_settings")
    @patch("postgres_backup_service_settings.apply_backup_settings")
    def test_update_handles_exception(
        self, mock_apply, mock_persist, mock_get_config
    ):
        from postgres_backup_service_settings import update_auto_backup_settings

        backup_system = MagicMock()
        backup_system.is_running = True
        backup_system.backup_interval_hours = 24
        backup_system.max_backups = 10
        stop_fn = MagicMock()
        start_fn = MagicMock()
        mock_apply.side_effect = KeyError("test")

        result = update_auto_backup_settings(
            backup_system, stop_fn, start_fn, enabled=False
        )

        assert result is False
