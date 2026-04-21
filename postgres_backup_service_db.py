"""PostgreSQL 备份服务数据库相关操作。"""

from __future__ import annotations

import subprocess
import sys
import time

import psycopg2
from psycopg2 import sql

import postgres_backup_service_connection as connection_module
import postgres_backup_service_restore as restore_module
import postgres_backup_service_schema_reset as schema_reset_module
from postgres_backup_service_connection import PostgresBackupConnectionMixin
from postgres_backup_service_restore import PostgresBackupRestoreMixin
from postgres_backup_service_schema_reset import PostgresBackupSchemaResetMixin
from postgres_backup_service_support import POSTGRES_CONFIG, build_postgres_dsn, logger

__all__ = [
    "POSTGRES_CONFIG",
    "PostgresBackupDatabaseMixin",
    "build_postgres_dsn",
    "logger",
    "psycopg2",
    "sql",
    "subprocess",
    "time",
]


class _ModuleAttributeProxy:
    def __init__(self, module_name: str, attribute_name: str) -> None:
        self.module_name = module_name
        self.attribute_name = attribute_name

    def __getattr__(self, item):
        target = getattr(sys.modules[self.module_name], self.attribute_name)
        return getattr(target, item)


def _build_postgres_dsn_proxy(database=None):
    return sys.modules[__name__].build_postgres_dsn(database)


for module in (schema_reset_module, connection_module, restore_module):
    setattr(module, "POSTGRES_CONFIG", POSTGRES_CONFIG)
    setattr(module, "build_postgres_dsn", _build_postgres_dsn_proxy)
    setattr(module, "logger", _ModuleAttributeProxy(__name__, "logger"))


class PostgresBackupDatabaseMixin(
    PostgresBackupSchemaResetMixin,
    PostgresBackupConnectionMixin,
    PostgresBackupRestoreMixin,
):
    """封装备份恢复涉及的数据库操作。"""

    pass
