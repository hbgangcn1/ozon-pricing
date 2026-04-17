"""PostgreSQL 备份服务配置读写辅助。"""

from __future__ import annotations

from typing import Optional

from postgres_backup_service_support import (
    AutoBackupSettings,
    logger,
    parse_positive_int,
    persist_backup_settings,
    try_get_system_config,
)


def get_auto_backup_settings(backup_system) -> AutoBackupSettings:
    get_system_config = try_get_system_config()
    enabled = True
    interval = backup_system.backup_interval_hours
    max_backups = backup_system.max_backups
    if get_system_config is not None:
        enabled = (
            str(get_system_config("auto_backup_enabled", "true")).lower() == "true"
        )
        interval = parse_positive_int(
            get_system_config("auto_backup_interval_hours", str(interval)),
            interval,
        )
        max_backups = parse_positive_int(
            get_system_config("auto_backup_max_backups", str(max_backups)),
            max_backups,
        )
    return {
        "enabled": enabled,
        "interval_hours": interval,
        "max_backups": max_backups,
    }


def update_auto_backup_settings(
    backup_system,
    stop_backup_service,
    start_backup_service,
    settings: Optional[AutoBackupSettings] = None,
    *,
    enabled: Optional[bool] = None,
    interval_hours: Optional[int] = None,
    max_backups: Optional[int] = None,
) -> bool:
    """更新自动备份配置并实时应用。"""
    try:
        current = get_auto_backup_settings(backup_system)
        resolved = resolve_backup_settings_update(
            current,
            settings=settings,
            enabled=enabled,
            interval_hours=interval_hours,
            max_backups=max_backups,
        )
        persist_backup_settings(resolved)
        return apply_backup_settings(
            backup_system,
            resolved,
            stop_backup_service,
            start_backup_service,
        )
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        logger.error("更新自动备份设置失败: {}", exc)
        return False


def resolve_backup_settings_update(
    current: AutoBackupSettings,
    *,
    settings: Optional[AutoBackupSettings],
    enabled: Optional[bool],
    interval_hours: Optional[int],
    max_backups: Optional[int],
) -> AutoBackupSettings:
    if settings is not None:
        new_enabled = settings.get("enabled", current["enabled"])
        new_interval = settings.get("interval_hours", current["interval_hours"])
        new_max_backups = settings.get("max_backups", current["max_backups"])
    else:
        new_enabled = current["enabled"] if enabled is None else enabled
        new_interval = (
            current["interval_hours"]
            if interval_hours is None
            else max(1, interval_hours)
        )
        new_max_backups = (
            current["max_backups"] if max_backups is None else max(1, max_backups)
        )
    return {
        "enabled": bool(new_enabled),
        "interval_hours": parse_positive_int(new_interval, current["interval_hours"]),
        "max_backups": parse_positive_int(new_max_backups, current["max_backups"]),
    }


def apply_backup_settings(
    backup_system,
    settings: AutoBackupSettings,
    stop_backup_service,
    start_backup_service,
) -> bool:
    previous_running = backup_system.is_running
    interval_changed = settings["interval_hours"] != backup_system.backup_interval_hours
    backup_system.backup_interval_hours = settings["interval_hours"]
    backup_system.max_backups = settings["max_backups"]

    if not settings["enabled"] and previous_running:
        stop_backup_service()
        return True
    if settings["enabled"] and not previous_running:
        start_backup_service()
        return True
    if settings["enabled"] and interval_changed:
        stop_backup_service()
        start_backup_service()
    return True
