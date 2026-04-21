from __future__ import annotations

import time
from contextlib import closing

import psycopg2

from postgres_backup_service_support import POSTGRES_CONFIG, build_postgres_dsn, logger


class PostgresBackupConnectionMixin:
    def _count_active_connections(self, cur) -> int:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (POSTGRES_CONFIG.get("database"),),
        )
        result = cur.fetchone()
        return result[0] if result else 0

    def _terminate_active_connections(self) -> None:
        """终止当前数据库的其他连接，避免恢复失败。"""
        logger.info("终止活动连接，准备恢复数据库...")
        try:
            with closing(psycopg2.connect(build_postgres_dsn("postgres"))) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    active_count = self._count_active_connections(cur)
                    logger.info("发现 {} 个活动连接", active_count)
                    if active_count <= 0:
                        return

                    cur.execute(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = %s AND pid <> pg_backend_pid()
                        """,
                        (POSTGRES_CONFIG.get("database"),),
                    )
                    logger.info("已终止 {} 个连接", cur.rowcount)

                    waited = 0.0
                    while waited < 5:
                        time.sleep(0.5)
                        waited += 0.5
                        remaining = self._count_active_connections(cur)
                        if remaining == 0:
                            logger.info("所有连接已关闭")
                            return
                        logger.debug("等待连接关闭... 剩余 {} 个连接", remaining)

                    remaining = self._count_active_connections(cur)
                    if remaining > 0:
                        logger.warning(
                            "仍有 {} 个连接未关闭，继续恢复流程",
                            remaining,
                        )
        except psycopg2.Error as exc:
            if "permission denied" in str(exc).lower():
                logger.warning(
                    "终止连接权限不足: {}，跳过连接终止，继续恢复流程",
                    exc,
                )
                return
            logger.warning("终止连接时出现错误: {}，继续恢复流程", exc)

    def _reinitialize_connection_pool(self) -> None:
        logger.info("正在重新初始化连接池...")
        try:
            from database import engine

            engine.sync_engine.dispose()
            time.sleep(2)
            logger.info("✅ 连接池已 dispose，新请求将自动重建连接")
        except Exception as exc:
            logger.warning(
                "重新初始化连接池时出现错误: {}。"
                "pool_pre_ping 将在下次请求时自动重建连接。",
                exc,
            )
