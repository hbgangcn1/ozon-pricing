from __future__ import annotations

from contextlib import closing
from typing import cast

import psycopg2
from psycopg2 import sql

from postgres_backup_service_support import build_postgres_dsn, logger


class PostgresBackupSchemaResetMixin:
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
            logger.debug("检查是否可删除 public schema 失败", exc_info=True)
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
                        db_user = cast(tuple[str], cur.fetchone())[0]
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
            except psycopg2.Error as e:
                logger.debug("DROP TABLE %s 失败: %s", table, e)

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
            except psycopg2.Error as e:
                logger.debug("DROP SEQUENCE %s 失败: %s", row[0], e)

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
            except psycopg2.Error as e:
                logger.debug("DROP TYPE %s 失败: %s", row[0], e)

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
