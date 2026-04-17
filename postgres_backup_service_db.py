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
            "--clean",
            "--if-exists",
            "--dbname",
            POSTGRES_CONFIG.get("database", "postgres"),
            backup_path,
        ]
        logger.debug("执行 pg_restore: {}", " ".join(cmd))
        result = subprocess.run(
            cmd,
            check=False,
            env=self._build_env(),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stdout:
            logger.debug("pg_restore 输出: {}", result.stdout)
        if result.stderr:
            logger.debug("pg_restore 信息: {}", result.stderr)
        if result.returncode != 0:
            if self._has_fatal_restore_error(result.stderr or ""):
                raise subprocess.CalledProcessError(
                    result.returncode,
                    cmd,
                    output=result.stdout,
                    stderr=result.stderr,
                )
            logger.info("pg_restore 完成（有非致命警告，如 --clean 权限问题）")

    @staticmethod
    def _has_fatal_restore_error(stderr: str) -> bool:
        """判断 pg_restore stderr 是否包含致命错误。

        --clean 模式下 DROP 权限/不存在错误属于非致命。
        """
        if not stderr:
            return False
        non_fatal_phrases = (
            # English
            "must be owner of",
            "permission denied",
            "does not exist",
            "already exists",
            'role "',
            # Chinese (PostgreSQL zh_CN locale)
            "必须是",
            "属主",
            "权限不够",
            "不存在",
            "已经存在",
            "已存在",
            "角色",
        )
        for line in stderr.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            low = stripped.lower()
            # Skip warning summary lines (e.g. "警告: 恢复中忽略错误: 1")
            if "警告" in stripped or "warning" in low:
                continue
            is_error = "错误" in stripped or "error" in low
            if not is_error:
                continue
            if any(p in low for p in non_fatal_phrases):
                continue
            return True
        return False

    @staticmethod
    def _can_drop_public_schema(cur) -> bool:
        try:
            cur.execute("SELECT current_user")
            current_user = cur.fetchone()[0]

            cur.execute(
                "SELECT rolsuper FROM pg_roles WHERE rolname = %s",
                (current_user,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return True

            cur.execute(
                "SELECT pg_get_userbyid(nspowner) "
                "FROM pg_namespace WHERE nspname = 'public'"
            )
            owner_row = cur.fetchone()
            if owner_row and owner_row[0] == current_user:
                return True

            return False
        except Exception:
            return False

    def _reset_public_schema(self) -> None:
        """重置 public schema，并删除额外 schema。

        owner/superuser → DROP/CREATE；否则 → DROP OWNED BY fallback。
        """
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

                    if self._can_drop_public_schema(cur):
                        cur.execute("DROP SCHEMA public CASCADE")
                        cur.execute("CREATE SCHEMA public")
                        logger.info(
                            "✅ public schema 已重置"
                            "（DROP/CREATE，清理了 {} 个额外 schema）",
                            len(extra_schemas),
                        )
                    else:
                        cur.execute("SELECT current_user")
                        db_user = cur.fetchone()[0]
                        cur.execute(
                            sql.SQL("DROP OWNED BY {} CASCADE").format(
                                sql.Identifier(db_user)
                            )
                        )
                        remaining = self._cleanup_remaining_objects(
                            cur,
                        )
                        logger.info(
                            "✅ public schema 已清理"
                            "（DROP OWNED BY {} + 对象清理，"
                            "清理了 {} 个额外 schema）",
                            db_user,
                            len(extra_schemas),
                        )
                        if remaining > 0:
                            logger.warning(
                                "⚠️ 仍有 {} 个表无法清理，pg_restore --clean 将尝试处理",
                                remaining,
                            )
        except Exception as exc:
            logger.warning("重置 public schema 失败: {}", exc)
            raise

    @staticmethod
    def _cleanup_remaining_objects(cur) -> int:
        """清理 public schema 中 DROP OWNED BY 未能删除的残留对象。

        对每个表先尝试 DROP，失败则尝试 TRUNCATE（清空数据以便
        pg_restore 的 COPY 不会因主键冲突而失败）。

        Returns:
            未能完全清理（既无法 DROP 也无法 TRUNCATE）的表数量。
        """
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        tables = [row[0] for row in cur.fetchall()]
        if not tables:
            return 0

        logger.info(
            "DROP OWNED BY 后仍有 {} 个表，逐个清理...",
            len(tables),
        )

        dropped = 0
        truncated = 0
        failed = 0
        for table in tables:
            try:
                cur.execute(
                    sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
                        sql.Identifier(table)
                    )
                )
                dropped += 1
                continue
            except psycopg2.Error:
                pass

            try:
                cur.execute(
                    sql.SQL("TRUNCATE TABLE {} CASCADE").format(sql.Identifier(table))
                )
                truncated += 1
            except psycopg2.Error:
                failed += 1
                logger.debug("  无法清理表 {}", table)

        cur.execute(
            "SELECT sequence_name "
            "FROM information_schema.sequences "
            "WHERE sequence_schema = 'public'"
        )
        for row in cur.fetchall():
            try:
                cur.execute(
                    sql.SQL("DROP SEQUENCE IF EXISTS {} CASCADE").format(
                        sql.Identifier(row[0])
                    )
                )
            except psycopg2.Error:
                pass

        cur.execute(
            "SELECT typname FROM pg_type t "
            "JOIN pg_namespace n ON t.typnamespace = n.oid "
            "WHERE n.nspname = 'public' "
            "AND t.typtype IN ('e', 'c')"
        )
        for row in cur.fetchall():
            try:
                cur.execute(
                    sql.SQL("DROP TYPE IF EXISTS {} CASCADE").format(
                        sql.Identifier(row[0])
                    )
                )
            except psycopg2.Error:
                pass

        logger.info(
            "  对象清理: 删除 {} 个表, 清空 {} 个表, 失败 {} 个表",
            dropped,
            truncated,
            failed,
        )
        return failed

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
            msg = "恢复后缺少关键表: {}".format(
                ", ".join(missing_tables),
            )
            logger.error("❌ {}", msg)
            raise RuntimeError(msg)
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
