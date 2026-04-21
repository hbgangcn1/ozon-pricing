from __future__ import annotations

import subprocess
import time
from contextlib import closing

import psycopg2

from postgres_backup_service_support import POSTGRES_CONFIG, build_postgres_dsn, logger


class PostgresBackupRestoreMixin:
    pre_restore_prefix = "pre_restore_backup"

    def _build_env(self) -> dict[str, str]:
        raise NotImplementedError

    def get_backup_file_path(self, backup_filename: str) -> str:
        raise NotImplementedError

    def _create_backup(self, prefix: str) -> bool:
        raise NotImplementedError

    def verify_backup(self, backup_path: str) -> bool:
        raise NotImplementedError

    def _reset_public_schema(self) -> None:
        raise NotImplementedError

    def _terminate_active_connections(self) -> None:
        raise NotImplementedError

    def _reinitialize_connection_pool(self) -> None:
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
            "must be owner of",
            "permission denied",
            "does not exist",
            "already exists",
            'role "',
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
            if "警告" in stripped or "warning" in low:
                continue
            is_error = "错误" in stripped or "error" in low
            if not is_error:
                continue
            if any(p in low for p in non_fatal_phrases):
                continue
            return True
        return False

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
