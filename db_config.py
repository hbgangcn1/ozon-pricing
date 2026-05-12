# -*- coding: utf-8 -*-
"""
数据库配置模块
支持SQLite和PostgreSQL双数据库
"""

import os
import logging
from typing import Literal

# 加载.env文件（必须在读取环境变量之前）
try:
    from dotenv import load_dotenv
except ImportError:
    # 如果没有python-dotenv，定义一个占位函数
    def load_dotenv() -> bool:
        return False

# 调用load_dotenv（无论是真实函数还是占位函数）
load_dotenv()

# 数据库类型配置
_db_type_raw = os.getenv('DB_TYPE', 'sqlite').lower()

# 验证并转换为正确的类型
if _db_type_raw not in ('sqlite', 'postgresql'):
    raise ValueError(
        f"无效的 DB_TYPE: {_db_type_raw}. "
        f"必须是 'sqlite' 或 'postgresql'"
    )

DB_TYPE: Literal['sqlite', 'postgresql'] = _db_type_raw

# SQLite配置
SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', 'logistics.db')

# PostgreSQL配置
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'logistics'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', ''),
    'options': os.getenv('POSTGRES_OPTIONS', ''),
}

# 连接池配置
# 生产环境默认 3 gunicorn workers；每个 worker 的连接上限约为
# pool_size + max_overflow。建议单 worker 不超过 30，这样 3 workers
# 总计约 90，给 PostgreSQL 默认 100 connections 留出系统/管理余量。
CONNECTION_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '20'))
CONNECTION_POOL_MAX = int(os.getenv('DB_POOL_MAX', '50'))
CONNECTION_TIMEOUT = int(os.getenv('DB_TIMEOUT', '30'))

# 连接池参数安全验证
if CONNECTION_POOL_SIZE < 1:
    raise ValueError(
        f"DB_POOL_SIZE 必须 >= 1，当前值: {CONNECTION_POOL_SIZE}"
    )
if CONNECTION_POOL_MAX < CONNECTION_POOL_SIZE:
    raise ValueError(
        f"DB_POOL_MAX ({CONNECTION_POOL_MAX}) 必须 >= "
        f"DB_POOL_SIZE ({CONNECTION_POOL_SIZE})"
    )
_pool_overflow = CONNECTION_POOL_MAX - CONNECTION_POOL_SIZE
if CONNECTION_POOL_SIZE + _pool_overflow > 30:
    logging.getLogger(__name__).warning(
        "DB pool per-worker budget is high: pool_size=%s, max_overflow=%s, "
        "per_worker_total=%s; with 3 gunicorn workers this approximates %s total connections",
        CONNECTION_POOL_SIZE,
        _pool_overflow,
        CONNECTION_POOL_SIZE + _pool_overflow,
        (CONNECTION_POOL_SIZE + _pool_overflow) * 3,
    )


def get_db_url() -> str:
    """获取数据库连接URL"""
    if DB_TYPE == 'postgresql':
        cfg = POSTGRES_CONFIG
        password_part = f":{cfg['password']}" if cfg['password'] else ""
        options_part = f"?{cfg['options']}" if cfg['options'] else ""
        return (
            f"postgresql://{cfg['user']}{password_part}@"
            f"{cfg['host']}:{cfg['port']}/{cfg['database']}{options_part}"
        )
    else:
        return f"sqlite:///{SQLITE_DB_PATH}"


def get_db_config() -> dict:
    """获取数据库配置字典。

    生产环境默认 3 个 gunicorn worker；单 worker 的连接预算是
    `pool_size + max_overflow`，总预算约为该值 × 3。
    """
    return {
        'db_type': DB_TYPE,
        'sqlite_path': SQLITE_DB_PATH if DB_TYPE == 'sqlite' else None,
        'postgres_config': POSTGRES_CONFIG if DB_TYPE == 'postgresql' else None,  # noqa: E501
        'pool_size': CONNECTION_POOL_SIZE,
        'pool_max': CONNECTION_POOL_MAX,
        'timeout': CONNECTION_TIMEOUT,
    }
