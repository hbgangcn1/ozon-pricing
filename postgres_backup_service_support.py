"""PostgreSQL 备份服务共享支持代码。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional, TypedDict

try:
    from logger_config import logger  # type: ignore
except ImportError:  # pragma: no cover - 不影响核心功能
    logger = logging.getLogger(__name__)

try:
    from db_config import POSTGRES_CONFIG  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "无法加载 PostgreSQL 配置: db_config.POSTGRES_CONFIG 缺失"
    ) from exc


class BackupRecord(TypedDict):
    name: str
    path: str
    size: int
    mtime: datetime
    type: str


class AutoBackupSettings(TypedDict):
    enabled: bool
    interval_hours: int
    max_backups: int


def ensure_postgres_bin_on_path() -> None:
    """自动查找并添加 PostgreSQL bin 目录到 PATH（Windows）。"""
    if os.name != "nt":
        return

    pg_bin_paths = [
        r"C:\Program Files\PostgreSQL\18\bin",
        r"C:\Program Files\PostgreSQL\17\bin",
        r"C:\Program Files\PostgreSQL\16\bin",
        r"C:\Program Files\PostgreSQL\15\bin",
        r"C:\Program Files\PostgreSQL\14\bin",
    ]
    current_path = os.environ.get("PATH", "")
    for pg_bin in pg_bin_paths:
        if os.path.exists(pg_bin) and pg_bin not in current_path:
            os.environ["PATH"] = current_path + os.pathsep + pg_bin
            logger.info("✅ 已自动添加 PostgreSQL bin 到 PATH: {}", pg_bin)
            return


def load_schedule_module():
    """惰性加载 schedule 模块。"""
    try:  # pragma: no cover - schedule 在运行环境中才需要
        import schedule as _schedule  # type: ignore

        return _schedule
    except ImportError:
        return None


def build_postgres_dsn(database: Optional[str] = None) -> str:
    """基于项目配置构建 psycopg2 DSN。"""
    dsn_parts = [
        f"host={POSTGRES_CONFIG.get('host', 'localhost')}",
        f"port={POSTGRES_CONFIG.get('port', 5432)}",
        f"dbname={database or POSTGRES_CONFIG.get('database', 'postgres')}",
        f"user={POSTGRES_CONFIG.get('user', 'postgres')}",
    ]
    password = POSTGRES_CONFIG.get("password", "")
    if password:
        dsn_parts.append(f"password={password}")
    options = POSTGRES_CONFIG.get("options")
    if options:
        dsn_parts.append(f"options='{options}'")
    return " ".join(dsn_parts)


def try_get_system_config():
    try:
        from db_utils import get_system_config  # type: ignore

        return get_system_config
    except ImportError:
        return None


def parse_positive_int(raw_value, default_value: int) -> int:
    try:
        parsed = int(str(raw_value))
    except (TypeError, ValueError):
        return default_value
    return parsed if parsed > 0 else default_value


def persist_backup_settings(settings: AutoBackupSettings) -> None:
    try:
        from db_utils import set_system_config  # type: ignore
    except ImportError:
        return
    set_system_config(
        "auto_backup_enabled",
        "true" if settings["enabled"] else "false",
        "是否启用自动备份",
    )
    set_system_config(
        "auto_backup_interval_hours",
        str(settings["interval_hours"]),
        "自动备份间隔（小时）",
    )
    set_system_config(
        "auto_backup_max_backups",
        str(settings["max_backups"]),
        "最多保留备份数量",
    )
