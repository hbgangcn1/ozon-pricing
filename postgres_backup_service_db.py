"""PostgreSQL 备份服务数据库相关操作。"""

from __future__ import annotations

import subprocess
import time
from contextlib import closing

import psycopg2
from psycopg2 import sql

from postgres_backup_service_support import POSTGRES_CONFIG, build_postgres_dsn, logger


class PostgresBackupDatabaseMixin:
    """封装备份恢复涉及的数据库操作。"""

    pre_restore_prefix = "pre_restore_backup"

    def _build_env(self) -> dict[str, str]:
        raise NotImplementedError

    def get_backup_file_path(self, backup_filename: str) -> str:
        raise NotImplementedError

    def _create_backup(self, prefix: str) -> bool:
        raise NotImplementedError

    def verify_backup(self, backup_path: str) -> bool:
        raise NotImplementedError

    def _run_pg_restore(self, backup_path: str) -> None:
        self._reset_public_schema()
        cmd = [
            "pg_restore",
            "-h",
            POSTGRES_CONFIG.get("host", "localhost"),
            "-p",
            str(POSTGRES_CONFIG.get("port", 5432)),
            "-U",
            POSTGRES_CONFIG.get("user", "postgres"),
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "--dbname",
            POSTGRES_CONFIG.get("database", "postgres"),
            backup_path,
        ]
        logger.debug("执行 pg_restore: {}", " ".join(cmd))
        result = subprocess.run(
            cmd,
            check=True,
            env=self._build_env(),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stdout:
            logger.debug("pg_restore 输出: {}", result.stdout)
        if result.stderr:
            logger.debug("pg_restore 警告: {}", result.stderr)

    def _reset_public_schema(self) -> None:
        """重置 public schema，并删除额外 schema。"""
        logger.info("正在重置 public schema...")
        try:
            with closing(psycopg2.connect(build_postgres_dsn())) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT schema_name FROM information_schema.schemata
                        WHERE schema_name NOT IN (
                            'public', 'pg_catalog', 'information_schema',
                            'pg_toast', 'pg_temp_1', 'pg_toast_temp_1',
                            'pg_bitmapindex', 'pg_aoseg', 'pg_global'
                        )
                        """
                    )
                    extra_schemas = [row[0] for row in cur.fetchall()]
                    for schema_name in extra_schemas:
                        cur.execute(
                            sql.SQL("DROP SCHEMA {} CASCADE").format(
                                sql.Identifier(schema_name)
                            )
                        )
                        logger.info("  已删除额外 schema: {}", schema_name)

                    cur.execute("DROP SCHEMA public CASCADE")
                    cur.execute("CREATE SCHEMA public")
                    logger.info(
                        "✅ public schema 已重置（清理了 {} 个额外 schema）",
                        len(extra_schemas),
                    )
        except Exception as exc:
            logger.warning("重置 public schema 失败: {}", exc)
            raise

    def _drop_all_foreign_keys(self) -> None:
        """删除所有外键约束，为恢复做准备。"""
        logger.info("正在删除所有外键约束...")
        try:
            with closing(psycopg2.connect(build_postgres_dsn())) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT tc.table_schema, tc.table_name, tc.constraint_name
                        FROM information_schema.table_constraints AS tc
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                          AND tc.table_schema = 'public'
                        ORDER BY tc.table_name, tc.constraint_name
                        """
                    )
                    fk_constraints = cur.fetchall()
                    if not fk_constraints:
                        logger.info("未发现外键约束")
                        return

                    logger.info("发现 {} 个外键约束", len(fk_constraints))
                    dropped_count = 0
                    for schema_name, table_name, constraint_name in fk_constraints:
                        try:
                            cur.execute(
                                sql.SQL(
                                    "ALTER TABLE {} DROP CONSTRAINT IF EXISTS {} "
                                    "CASCADE"
                                ).format(
                                    sql.Identifier(schema_name, table_name),
                                    sql.Identifier(constraint_name),
                                )
                            )
                            dropped_count += 1
                            logger.debug(
                                "已删除外键约束: {}.{}.{}",
                                schema_name,
                                table_name,
                                constraint_name,
                            )
                        except psycopg2.Error as drop_err:
                            logger.warning(
                                "删除外键约束失败 {}.{}.{}: {}",
                                schema_name,
                                table_name,
                                constraint_name,
                                drop_err,
                            )

                    logger.info("✅ 已删除 {} 个外键约束", dropped_count)
        except psycopg2.Error as exc:
            logger.warning("删除外键约束时出现错误: {}", exc)
            raise

    def _drop_sequence_dependencies(self) -> None:
        """删除所有序列默认值依赖，为恢复做准备。"""
        logger.info("正在删除序列的默认值依赖...")
        try:
            with closing(psycopg2.connect(build_postgres_dsn())) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.table_schema, t.table_name, c.column_name,
                               c.column_default
                        FROM information_schema.columns c
                        JOIN information_schema.tables t
                          ON c.table_schema = t.table_schema
                         AND c.table_name = t.table_name
                        WHERE c.table_schema = 'public'
                          AND c.column_default LIKE 'nextval%'
                        ORDER BY t.table_name, c.column_name
                        """
                    )
                    seq_columns = cur.fetchall()
                    if not seq_columns:
                        logger.info("未发现序列依赖")
                        return

                    logger.info("发现 {} 个序列依赖", len(seq_columns))
                    dropped_count = 0
                    for schema_name, table_name, column_name, _ in seq_columns:
                        try:
                            cur.execute(
                                sql.SQL(
                                    "ALTER TABLE {} ALTER COLUMN {} DROP DEFAULT"
                                ).format(
                                    sql.Identifier(schema_name, table_name),
                                    sql.Identifier(column_name),
                                )
                            )
                            dropped_count += 1
                            logger.debug(
                                "已删除序列默认值: {}.{}.{}",
                                schema_name,
                                table_name,
                                column_name,
                            )
                        except psycopg2.Error as drop_err:
                            logger.warning(
                                "删除序列默认值失败 {}.{}.{}: {}",
                                schema_name,
                                table_name,
                                column_name,
                                drop_err,
                            )

                    logger.info("✅ 已删除 {} 个序列依赖", dropped_count)
        except psycopg2.Error as exc:
            logger.warning("删除序列依赖时出现错误: {}", exc)
            raise

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
            from db_adapter import close_connection_pool, init_connection_pool
        except ImportError:
            logger.warning("无法导入连接池管理函数，跳过连接池重新初始化")
            return

        try:
            close_connection_pool()
            time.sleep(2)
            init_connection_pool()
            logger.info("✅ 连接池重新初始化成功")
        except Exception as exc:
            logger.warning("重新初始化连接池时出现错误: {}，但恢复可能已成功", exc)

    def _verify_restored_tables(self) -> None:
        dsn = build_postgres_dsn()
        try:
            with closing(psycopg2.connect(dsn)) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name IN ('users', 'products', 'logistics')
                        ORDER BY table_name
                        """
                    )
                    existing_tables = [row[0] for row in cur.fetchall()]
        except psycopg2.Error as exc:
            logger.warning("数据库连接验证失败: {}，但恢复可能已成功", exc)
            return

        missing_tables = [
            table_name
            for table_name in ["users", "products", "logistics"]
            if table_name not in existing_tables
        ]
        if missing_tables:
            logger.warning("⚠️ 恢复后缺少关键表: {}", ", ".join(missing_tables))
        else:
            logger.info("✅ 关键表验证成功: {}", ", ".join(existing_tables))
        logger.info("✅ 数据库连接验证成功")

    def restore_from_backup(
        self,
        backup_filename: str,
        *,
        create_snapshot: bool = True,
    ) -> bool:
        backup_path = self.get_backup_file_path(backup_filename)
        if not self._prepare_restore(backup_filename, backup_path, create_snapshot):
            return False

        self._terminate_restore_connections()
        for attempt in range(1, 4):
            if self._restore_attempt(backup_path, backup_filename, attempt, 3):
                return True
        return False

    def _prepare_restore(
        self,
        backup_filename: str,
        backup_path: str,
        create_snapshot: bool,
    ) -> bool:
        if not self._validate_restore_backup(backup_filename, backup_path):
            return False
        if create_snapshot:
            logger.info("在恢复前创建快照备份...")
            if not self._create_backup(self.pre_restore_prefix):
                logger.warning("恢复前快照创建失败，继续恢复流程。")
        return True

    def _validate_restore_backup(
        self,
        backup_filename: str,
        backup_path: str,
    ) -> bool:
        if not self.verify_backup(backup_path):
            logger.error("备份文件验证失败: {}", backup_filename)
            return False
        if not backup_path or not self._backup_file_exists(backup_path):
            logger.error("备份文件不存在: {}", backup_filename)
            return False
        return True

    @staticmethod
    def _backup_file_exists(backup_path: str) -> bool:
        try:
            with open(backup_path, "rb"):
                return True
        except OSError:
            return False

    def _terminate_restore_connections(self) -> None:
        try:
            self._terminate_active_connections()
        except Exception as exc:
            logger.warning("终止连接时出现异常: {}", exc)
        time.sleep(1)

    def _restore_attempt(
        self,
        backup_path: str,
        backup_filename: str,
        attempt: int,
        max_retries: int,
    ) -> bool:
        try:
            logger.info("尝试恢复数据库 (第 {}/{} 次)...", attempt, max_retries)
            self._run_pg_restore(backup_path)
            logger.info("✅ 数据库恢复成功: {}", backup_filename)
            self._reinitialize_connection_pool()
            time.sleep(3)
            self._verify_restored_tables()
            return True
        except subprocess.CalledProcessError as exc:
            self._handle_restore_subprocess_error(exc, attempt, max_retries)
        except Exception as exc:
            logger.exception(
                "数据库恢复失败 (第 {}/{} 次): {}",
                attempt,
                max_retries,
                exc,
            )
            self._sleep_before_retry(attempt, max_retries)
        return False

    def _handle_restore_subprocess_error(
        self,
        exc: subprocess.CalledProcessError,
        attempt: int,
        max_retries: int,
    ) -> None:
        error_msg = exc.stderr
        if error_msg and not isinstance(error_msg, str):
            error_msg = error_msg.decode("utf-8", "ignore")
        logger.error(
            "pg_restore 执行失败 (第 {}/{} 次): {}",
            attempt,
            max_retries,
            error_msg or str(exc),
        )
        if attempt >= max_retries:
            logger.error("所有恢复尝试均失败")
            return
        logger.info("等待 2 秒后重试...")
        time.sleep(2)
        try:
            self._terminate_active_connections()
            time.sleep(1)
        except (psycopg2.Error, OSError, ConnectionError) as retry_err:
            logger.debug("重试时终止连接失败: {}，继续恢复流程", retry_err)

    def _sleep_before_retry(
        self,
        attempt: int,
        max_retries: int,
    ) -> None:
        if attempt >= max_retries:
            logger.error("所有恢复尝试均失败")
            return
        logger.info("等待 2 秒后重试...")
        time.sleep(2)
