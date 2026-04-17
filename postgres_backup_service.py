"""PostgreSQL 备份服务。"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import psycopg2

from postgres_backup_service_db import PostgresBackupDatabaseMixin
from postgres_backup_service_settings import (
    get_auto_backup_settings as _get_auto_backup_settings,
    update_auto_backup_settings as _update_auto_backup_settings,
)
from postgres_backup_service_support import (
    POSTGRES_CONFIG,
    AutoBackupSettings,
    BackupRecord,
    ensure_postgres_bin_on_path,
    load_schedule_module,
    logger,
)


class PostgresBackupSystem(PostgresBackupDatabaseMixin):
    """PostgreSQL 数据库备份系统。"""

    file_extension = ".dump"
    auto_prefix = "auto_backup"
    manual_prefix = "manual_backup"
    pre_restore_prefix = "pre_restore_backup"

    def __init__(
        self,
        backup_dir: str = "backups/postgres",
        backup_interval_hours: int = 6,
        max_backups: int = 28,
    ) -> None:
        ensure_postgres_bin_on_path()
        self.backup_dir = backup_dir
        self.backup_interval_hours = max(1, backup_interval_hours)
        self.max_backups = max_backups
        self.backup_thread: Optional[threading.Thread] = None
        self.is_running = False
        self._lock = threading.Lock()
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)

    def diagnose(self) -> Dict[str, bool]:
        """诊断备份系统状态。"""
        status = {
            "pg_dump_available": self._is_pg_dump_available(),
            "backup_dir_exists": os.path.exists(self.backup_dir),
            "db_connectable": False,
        }
        status["backup_dir_writable"] = (
            os.access(self.backup_dir, os.W_OK)
            if status["backup_dir_exists"]
            else False
        )
        status["db_connectable"] = self._is_database_connectable()
        return status

    def _is_pg_dump_available(self) -> bool:
        try:
            subprocess.run(
                ["pg_dump", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def _is_database_connectable(self) -> bool:
        try:
            conn = psycopg2.connect(
                host=POSTGRES_CONFIG.get("host", "localhost"),
                port=POSTGRES_CONFIG.get("port", 5432),
                database=POSTGRES_CONFIG.get("database", "postgres"),
                user=POSTGRES_CONFIG.get("user", "postgres"),
                password=POSTGRES_CONFIG.get("password", ""),
            )
            conn.close()
            return True
        except ImportError:
            return False
        except (KeyError, ValueError, TypeError, OSError, ConnectionError):
            return False
        except Exception as exc:  # noqa: B902
            logger.debug("数据库连接检查失败: {}", exc)
            return False

    def _build_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env["PGPASSWORD"] = POSTGRES_CONFIG.get("password", "")
        return env

    def _build_filename(self, prefix: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}{self.file_extension}"

    def _build_backup_path(self, prefix: str) -> str:
        return os.path.join(self.backup_dir, self._build_filename(prefix))

    def _run_pg_dump(self, output_path: str) -> None:
        cmd = [
            "pg_dump",
            "-h",
            POSTGRES_CONFIG.get("host", "localhost"),
            "-p",
            str(POSTGRES_CONFIG.get("port", 5432)),
            "-U",
            POSTGRES_CONFIG.get("user", "postgres"),
            "-F",
            "c",
            "-f",
            output_path,
        ]
        options = POSTGRES_CONFIG.get("options")
        if options:
            cmd.extend(["-o", options])
        cmd.append(POSTGRES_CONFIG.get("database", "postgres"))
        logger.debug("执行 pg_dump: {}", " ".join(cmd))
        subprocess.run(
            cmd,
            check=True,
            env=self._build_env(),
            capture_output=True,
            text=True,
        )
        logger.debug("pg_dump 执行成功")

    def _filter_backup_files(self) -> List[BackupRecord]:
        records: List[BackupRecord] = []
        for filename in os.listdir(self.backup_dir):
            if not self._is_tracked_backup_file(filename):
                continue
            record = self._build_backup_record(filename)
            if record is not None:
                records.append(record)
        records.sort(key=lambda item: item["mtime"], reverse=True)
        return records

    def _is_tracked_backup_file(self, filename: str) -> bool:
        if not filename.endswith(self.file_extension):
            return False
        return filename.startswith(
            (self.auto_prefix, self.manual_prefix, self.pre_restore_prefix)
        )

    def _build_backup_record(self, filename: str) -> Optional[BackupRecord]:
        file_path = os.path.join(self.backup_dir, filename)
        try:
            size = os.path.getsize(file_path)
            mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
        except OSError:
            return None
        return {
            "name": filename,
            "path": file_path,
            "size": size,
            "mtime": mtime,
            "type": self._get_backup_type(filename),
        }

    def _get_backup_type(self, filename: str) -> str:
        if filename.startswith(self.manual_prefix):
            return "manual"
        if filename.startswith(self.pre_restore_prefix):
            return "snapshot"
        return "auto"

    def _create_backup(self, prefix: str) -> bool:
        backup_path = self._build_backup_path(prefix)
        try:
            self._run_pg_dump(backup_path)
            if not self.verify_backup(backup_path):
                logger.error("❌ 备份验证失败: {}", os.path.basename(backup_path))
                os.remove(backup_path)
                return False
            self.cleanup_old_backups()
            logger.info("✅ 备份完成: {}", os.path.basename(backup_path))
            return True
        except subprocess.CalledProcessError as exc:
            error_msg = (
                exc.stderr.decode("utf-8", "ignore")
                if isinstance(exc.stderr, bytes)
                else str(exc.stderr or "")
            )
            logger.error(
                "❌ pg_dump 执行失败 (返回码: {}): {}",
                exc.returncode,
                error_msg or "无错误信息",
            )
        except FileNotFoundError as exc:
            logger.error(
                "❌ 找不到 pg_dump 命令: {}. 请确保 PostgreSQL 已安装并在 PATH 中", exc
            )
        except PermissionError as exc:
            logger.error("❌ 备份文件写入权限错误: {}. 请检查备份目录权限", exc)
        except Exception as exc:  # noqa: B902
            logger.exception("❌ 备份失败: {}", exc)
        self._delete_failed_backup_file(backup_path)
        return False

    def _delete_failed_backup_file(self, backup_path: str) -> None:
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except OSError:
            logger.warning("无法删除失败的备份文件: {}", backup_path)

    def create_backup(self) -> bool:
        return self._create_backup(self.auto_prefix)

    def manual_backup(self) -> bool:
        return self._create_backup(self.manual_prefix)

    def verify_backup(self, backup_path: str) -> bool:
        try:
            subprocess.run(
                ["pg_restore", "--list", backup_path],
                check=True,
                env=self._build_env(),
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as exc:
            stderr = (
                exc.stderr.decode("utf-8", "ignore")
                if isinstance(exc.stderr, bytes)
                else str(exc.stderr or "")
            )
            logger.error("备份验证失败 ({}): {}", os.path.basename(backup_path), stderr)
            return False

    def cleanup_old_backups(self) -> None:
        try:
            records = self._filter_backup_files()
            for item in records[self.max_backups :]:
                try:
                    os.remove(item["path"])
                    logger.info("🗑️ 删除旧备份: {}", item["name"])
                except OSError as exc:
                    logger.warning("删除旧备份失败 {}: {}", item["name"], exc)
        except Exception as exc:  # noqa: B902
            logger.exception("清理旧备份失败: {}", exc)

    def get_backup_stats(self) -> Dict[str, object]:
        records = self._filter_backup_files()
        total_size = sum(item["size"] for item in records)
        return {
            "count": len(records),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files": records,
        }

    def list_backups(self) -> List[BackupRecord]:
        return self._filter_backup_files()

    def get_backup_file_path(self, backup_filename: str) -> str:
        return os.path.join(self.backup_dir, backup_filename)

    def read_backup_file(
        self,
        backup_filename: str,
        max_size_mb: int = 500,
    ) -> bytes:
        path = self.get_backup_file_path(backup_filename)
        file_size = os.path.getsize(path)
        if file_size > max_size_mb * 1024 * 1024:
            raise ValueError(
                f"备份文件过大 ({file_size / 1024 / 1024:.1f}MB)，"
                f"超过 {max_size_mb}MB 限制"
            )
        with open(path, "rb") as file_obj:
            return file_obj.read()

    def delete_backup(self, backup_filename: str) -> bool:
        backup_path = self.get_backup_file_path(backup_filename)
        if not os.path.exists(backup_path):
            logger.warning("尝试删除不存在的备份文件: {}", backup_filename)
            return False
        try:
            os.remove(backup_path)
            logger.info("🗑️ 已删除备份文件: {}", backup_filename)
            return True
        except OSError as exc:
            logger.error("删除备份文件失败 {}: {}", backup_filename, exc)
            return False

    def start_auto_backup(self) -> None:
        if self.is_running:
            logger.warning("自动备份已在运行中")
            return
        self.is_running = True
        self.create_backup()
        target = self._build_auto_backup_target(load_schedule_module())
        self.backup_thread = threading.Thread(
            target=target,
            daemon=True,
            name="PostgresAutoBackup",
        )
        self.backup_thread.start()
        logger.info(
            "🚀 PostgreSQL 自动备份已启动，每 {} 小时执行一次",
            self.backup_interval_hours,
        )

    def _build_auto_backup_target(self, schedule_module):
        if schedule_module is None:
            return self._run_without_schedule
        return lambda: self._run_with_schedule(schedule_module)

    def _run_with_schedule(self, schedule_module) -> None:
        try:
            schedule_module.clear(tag="postgres_backup")  # type: ignore[attr-defined]
            schedule_module.every(self.backup_interval_hours).hours.do(  # type: ignore[attr-defined]
                self.create_backup
            ).tag("postgres_backup")
        except Exception as exc:  # noqa: B902
            logger.warning("绑定 schedule 失败，回退到简易调度: {}", exc)
            self._run_without_schedule()
            return
        while self.is_running:
            try:
                schedule_module.run_pending()  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: B902
                logger.exception("自动备份调度异常: {}", exc)
            time.sleep(60)

    def _run_without_schedule(self) -> None:
        interval = max(1, int(self.backup_interval_hours * 3600))
        next_run = time.time() + interval
        while self.is_running:
            now = time.time()
            if now >= next_run:
                try:
                    self.create_backup()
                except Exception as exc:  # noqa: B902
                    logger.exception("自动备份执行失败: {}", exc)
                next_run = now + interval
            time.sleep(60)

    def stop_auto_backup(self) -> None:
        if not self.is_running:
            return
        self.is_running = False
        if self.backup_thread:
            self.backup_thread.join()
        self.backup_thread = None
        logger.info("⏹️ PostgreSQL 自动备份已停止")


backup_system = PostgresBackupSystem()


def start_backup_service() -> None:
    settings = get_auto_backup_settings()
    if settings["enabled"]:
        backup_system.backup_interval_hours = settings["interval_hours"]
        backup_system.start_auto_backup()
        return
    logger.info("自动备份已禁用，跳过启动。")


def stop_backup_service() -> None:
    backup_system.stop_auto_backup()


def create_manual_backup() -> bool:
    return backup_system.manual_backup()


def get_backup_info() -> Dict[str, object]:
    return backup_system.get_backup_stats()


def list_backup_files() -> List[BackupRecord]:
    return backup_system.list_backups()


def verify_backup_file(backup_filename: str) -> bool:
    backup_path = backup_system.get_backup_file_path(backup_filename)
    return backup_system.verify_backup(backup_path)


def delete_backup_file(backup_filename: str) -> bool:
    return backup_system.delete_backup(backup_filename)


def read_backup_file(backup_filename: str) -> bytes:
    return backup_system.read_backup_file(backup_filename)


def restore_database(
    backup_filename: str,
    *,
    create_snapshot: bool = True,
) -> bool:
    return backup_system.restore_from_backup(
        backup_filename,
        create_snapshot=create_snapshot,
    )


def get_auto_backup_settings() -> AutoBackupSettings:
    return _get_auto_backup_settings(backup_system)


def update_auto_backup_settings(
    settings: Optional[AutoBackupSettings] = None,
    *,
    enabled: Optional[bool] = None,
    interval_hours: Optional[int] = None,
    max_backups: Optional[int] = None,
) -> bool:
    return _update_auto_backup_settings(
        backup_system,
        stop_backup_service,
        start_backup_service,
        settings,
        enabled=enabled,
        interval_hours=interval_hours,
        max_backups=max_backups,
    )
