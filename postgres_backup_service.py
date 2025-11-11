"""PostgreSQL 备份服务
提供备份、验证、恢复以及自动调度功能，供后台管理界面调用。
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

import psycopg2

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

# 自动查找并添加 PostgreSQL bin 目录到 PATH（Windows）
if os.name == 'nt':  # Windows
    pg_bin_paths = [
        r"C:\Program Files\PostgreSQL\18\bin",
        r"C:\Program Files\PostgreSQL\17\bin",
        r"C:\Program Files\PostgreSQL\16\bin",
        r"C:\Program Files\PostgreSQL\15\bin",
        r"C:\Program Files\PostgreSQL\14\bin",
    ]
    for pg_bin in pg_bin_paths:
        current_path = os.environ.get("PATH", "")
        if os.path.exists(pg_bin) and pg_bin not in current_path:
            os.environ["PATH"] = current_path + os.pathsep + pg_bin
            logger.info(
                "✅ 已自动添加 PostgreSQL bin 到 PATH: %s", pg_bin
            )
            break


def _load_schedule_module():
    """惰性加载 schedule 模块。"""
    try:  # pragma: no cover - schedule 在运行环境中才需要
        import schedule as _schedule  # type: ignore

        return _schedule
    except ImportError:
        return None


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


class PostgresBackupSystem:
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
        self.backup_dir = backup_dir
        self.backup_interval_hours = max(1, backup_interval_hours)
        self.max_backups = max_backups
        self.backup_thread: Optional[threading.Thread] = None
        self.is_running = False
        self._lock = threading.Lock()

        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # 内部工具
    # ------------------------------------------------------------------ #
    def diagnose(self) -> Dict[str, bool]:
        """诊断备份系统状态"""
        status = {}

        # 检查 pg_dump 是否可用
        try:
            subprocess.run(
                ["pg_dump", "--version"],
                check=True,
                capture_output=True,
                text=True
            )
            status["pg_dump_available"] = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            status["pg_dump_available"] = False

        # 检查备份目录
        status["backup_dir_exists"] = os.path.exists(self.backup_dir)
        status["backup_dir_writable"] = os.access(
            self.backup_dir, os.W_OK
        ) if status["backup_dir_exists"] else False

        # 检查数据库连接
        status["db_connectable"] = False
        try:
            import psycopg2  # type: ignore
            conn = psycopg2.connect(
                host=POSTGRES_CONFIG.get("host", "localhost"),
                port=POSTGRES_CONFIG.get("port", 5432),
                database=POSTGRES_CONFIG.get("database", "postgres"),
                user=POSTGRES_CONFIG.get("user", "postgres"),
                password=POSTGRES_CONFIG.get("password", ""),
            )
            conn.close()
            status["db_connectable"] = True
        except ImportError:
            # psycopg2 未安装
            pass
        except (KeyError, ValueError, TypeError):
            # 配置错误
            pass
        except (OSError, ConnectionError):
            # 网络连接错误
            pass
        except Exception as e:  # noqa: B902
            # 数据库特定错误（OperationalError, DatabaseError 等）
            # 使用宽泛异常是因为 psycopg2 可能未导入，无法直接引用其异常类
            logger.debug("数据库连接检查失败: %s", e)

        return status

    # noinspection PyMethodMayBeStatic
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

        logger.debug("执行 pg_dump: %s", " ".join(cmd))
        subprocess.run(
            cmd,
            check=True,
            env=self._build_env(),
            capture_output=True,
            text=True
        )
        logger.debug("pg_dump 执行成功")

    def _run_pg_restore(self, backup_path: str) -> None:
        cmd = [
            "pg_restore",
            "-h",
            POSTGRES_CONFIG.get("host", "localhost"),
            "-p",
            str(POSTGRES_CONFIG.get("port", 5432)),
            "-U",
            POSTGRES_CONFIG.get("user", "postgres"),
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            POSTGRES_CONFIG.get("database", "postgres"),
            backup_path,
        ]

        options = POSTGRES_CONFIG.get("options")
        if options:
            cmd.extend(["-o", options])

        logger.debug("执行 pg_restore: %s", " ".join(cmd))
        subprocess.run(
            cmd, check=True, env=self._build_env(), capture_output=True
        )

    # noinspection PyMethodMayBeStatic
    def _terminate_active_connections(self) -> None:
        """终止当前数据库的其他连接，避免恢复失败。"""
        logger.info("终止活动连接，准备恢复数据库...")
        dsn = (
            f"host={POSTGRES_CONFIG.get('host', 'localhost')} "
            f"port={POSTGRES_CONFIG.get('port', 5432)} "
            f"dbname=postgres user={POSTGRES_CONFIG.get('user', 'postgres')}"
        )
        password = POSTGRES_CONFIG.get("password", "")
        if password:
            dsn += f" password={password}"
        options = POSTGRES_CONFIG.get("options")
        if options:
            dsn += f" options='{options}'"

        with closing(psycopg2.connect(dsn)) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                    """,
                    (POSTGRES_CONFIG.get("database"),),
                )

    def _filter_backup_files(self) -> List[BackupRecord]:
        records: List[BackupRecord] = []
        for fname in os.listdir(self.backup_dir):
            if not fname.endswith(self.file_extension):
                continue
            if not (
                fname.startswith(self.auto_prefix)
                or fname.startswith(self.manual_prefix)
                or fname.startswith(self.pre_restore_prefix)
            ):
                continue
            file_path = os.path.join(self.backup_dir, fname)
            try:
                size = os.path.getsize(file_path)
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            except OSError:
                continue
            backup_type = "auto"
            if fname.startswith(self.manual_prefix):
                backup_type = "manual"
            elif fname.startswith(self.pre_restore_prefix):
                backup_type = "snapshot"
            records.append(
                {
                    "name": fname,
                    "path": file_path,
                    "size": size,
                    "mtime": mtime,
                    "type": backup_type,
                }
            )
        records.sort(key=lambda item: item["mtime"], reverse=True)
        return records

    # ------------------------------------------------------------------ #
    # 备份 / 验证 / 恢复
    # ------------------------------------------------------------------ #
    def _create_backup(self, prefix: str) -> bool:
        backup_path = self._build_backup_path(prefix)
        try:
            self._run_pg_dump(backup_path)
            if not self.verify_backup(backup_path):
                logger.error("❌ 备份验证失败: %s", os.path.basename(backup_path))
                os.remove(backup_path)
                return False
            self.cleanup_old_backups()
            logger.info("✅ 备份完成: %s", os.path.basename(backup_path))
            return True
        except subprocess.CalledProcessError as dump_exc:
            error_msg = (
                dump_exc.stderr.decode("utf-8", "ignore")
                if isinstance(dump_exc.stderr, bytes)
                else str(dump_exc.stderr or "")
            )
            logger.error(
                "❌ pg_dump 执行失败 (返回码: %d): %s",
                dump_exc.returncode,
                error_msg or "无错误信息"
            )
        except FileNotFoundError as fnf_exc:
            logger.error(
                "❌ 找不到 pg_dump 命令: %s. "
                "请确保 PostgreSQL 已安装并在 PATH 中",
                fnf_exc
            )
        except PermissionError as perm_exc:
            logger.error(
                "❌ 备份文件写入权限错误: %s. "
                "请检查备份目录权限",
                perm_exc
            )
        except Exception as backup_exc:  # noqa: B902
            logger.exception("❌ 备份失败: %s", backup_exc)

        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except OSError:
            logger.warning("无法删除失败的备份文件: %s", backup_path)
        return False

    def create_backup(self) -> bool:
        return self._create_backup(self.auto_prefix)

    def manual_backup(self) -> bool:
        return self._create_backup(self.manual_prefix)

    def verify_backup(self, backup_path: str) -> bool:
        try:
            subprocess.run(
                [
                    "pg_restore",
                    "--list",
                    backup_path,
                ],
                check=True,
                env=self._build_env(),
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as verify_exc:
            logger.error(
                "备份验证失败 (%s): %s",
                os.path.basename(backup_path),
                verify_exc.stderr.decode("utf-8", "ignore"),
            )
            return False

    def cleanup_old_backups(self) -> None:
        try:
            records = self._filter_backup_files()
            # 保留最新的 max_backups 份（不包含 pre_restore 快照）
            regular_backups = [
                item for item in records if item["type"] in {"auto", "manual"}
            ]
            for item in regular_backups[self.max_backups:]:
                try:
                    os.remove(item["path"])
                    logger.info("🗑️ 删除旧备份: %s", item["name"])
                except OSError as del_exc:
                    logger.warning("删除旧备份失败 %s: %s", item["name"], del_exc)
        except Exception as cleanup_exc:  # noqa: B902
            logger.exception("清理旧备份失败: %s", cleanup_exc)

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

    def read_backup_file(self, backup_filename: str) -> bytes:
        path = self.get_backup_file_path(backup_filename)
        with open(path, "rb") as file_obj:
            return file_obj.read()

    def delete_backup(self, backup_filename: str) -> bool:
        backup_path = self.get_backup_file_path(backup_filename)
        if not os.path.exists(backup_path):
            logger.warning("尝试删除不存在的备份文件: %s", backup_filename)
            return False
        try:
            os.remove(backup_path)
            logger.info("🗑️ 已删除备份文件: %s", backup_filename)
            return True
        except OSError as remove_exc:
            logger.error("删除备份文件失败 %s: %s", backup_filename, remove_exc)
            return False

    def restore_from_backup(
        self,
        backup_filename: str,
        *,
        create_snapshot: bool = True,
    ) -> bool:
        backup_path = self.get_backup_file_path(backup_filename)
        if not os.path.exists(backup_path):
            logger.error("备份文件不存在: %s", backup_filename)
            return False

        if not self.verify_backup(backup_path):
            logger.error("备份文件验证失败: %s", backup_filename)
            return False

        if create_snapshot:
            logger.info("在恢复前创建快照备份...")
            if not self._create_backup(self.pre_restore_prefix):
                logger.warning("恢复前快照创建失败，继续恢复流程。")

        try:
            self._terminate_active_connections()
        except Exception as conn_exc:  # noqa: B902
            logger.warning("终止连接时出现异常: %s", conn_exc)

        try:
            self._run_pg_restore(backup_path)
            logger.info("✅ 数据库恢复成功: %s", backup_filename)
            return True
        except subprocess.CalledProcessError as restore_exc:
            logger.error(
                "pg_restore 执行失败: %s",
                restore_exc.stderr.decode("utf-8", "ignore"),
            )
        except Exception as restore_err:  # noqa: B902
            logger.exception("数据库恢复失败: %s", restore_err)
        return False

    # ------------------------------------------------------------------ #
    # 自动备份调度
    # ------------------------------------------------------------------ #
    def start_auto_backup(self) -> None:
        if self.is_running:
            logger.warning("自动备份已在运行中")
            return

        self.is_running = True
        self.create_backup()
        schedule_module = _load_schedule_module()

        def run_with_schedule() -> None:
            if schedule_module is None:
                return
            try:
                schedule_module.clear(  # type: ignore[attr-defined]
                    tag="postgres_backup"
                )
                schedule_module.every(  # type: ignore[attr-defined]
                    self.backup_interval_hours
                ).hours.do(self.create_backup).tag("postgres_backup")
            except Exception as sched_exc:  # noqa: B902
                logger.warning("绑定 schedule 失败，回退到简易调度: %s", sched_exc)
                run_without_schedule()
                return

            while self.is_running:
                try:
                    schedule_module.run_pending()  # type: ignore[attr-defined]
                except Exception as run_exc:  # noqa: B902
                    logger.exception("自动备份调度异常: %s", run_exc)
                time.sleep(60)

        def run_without_schedule() -> None:
            interval = max(1, int(self.backup_interval_hours * 3600))
            next_run = time.time() + interval
            while self.is_running:
                now = time.time()
                if now >= next_run:
                    try:
                        self.create_backup()
                    except Exception as backup_exc:  # noqa: B902
                        logger.exception("自动备份执行失败: %s", backup_exc)
                    next_run = now + interval
                time.sleep(60)

        target = (
            run_with_schedule
            if schedule_module is not None
            else run_without_schedule
        )
        self.backup_thread = threading.Thread(
            target=target,
            daemon=True,
            name="PostgresAutoBackup",
        )
        self.backup_thread.start()
        logger.info(
            "🚀 PostgreSQL 自动备份已启动，每 %s 小时执行一次",
            self.backup_interval_hours
        )

    def stop_auto_backup(self) -> None:
        if not self.is_running:
            return
        self.is_running = False
        if self.backup_thread:
            self.backup_thread.join()
        self.backup_thread = None
        logger.info("⏹️ PostgreSQL 自动备份已停止")


# ---------------------------------------------------------------------- #
# 单例实例 & 对外接口
# ---------------------------------------------------------------------- #

backup_system = PostgresBackupSystem()


def start_backup_service() -> None:
    """启动自动备份服务（若配置允许）。"""
    settings = get_auto_backup_settings()
    if settings["enabled"]:
        backup_system.backup_interval_hours = settings["interval_hours"]
        backup_system.start_auto_backup()
    else:
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
    try:
        from db_utils import get_system_config  # type: ignore
    except ImportError:
        get_system_config = None  # type: ignore

    enabled = True
    interval = backup_system.backup_interval_hours
    max_backups = backup_system.max_backups

    if get_system_config is not None:
        enabled_raw = get_system_config("auto_backup_enabled", "true")
        interval_raw = get_system_config(
            "auto_backup_interval_hours",
            str(interval),
        )
        max_backups_raw = get_system_config(
            "auto_backup_max_backups",
            str(max_backups),
        )
        enabled = str(enabled_raw).lower() == "true"
        try:
            interval_val = int(str(interval_raw))
            if interval_val > 0:
                interval = interval_val
        except (TypeError, ValueError):
            pass
        try:
            max_backups_val = int(str(max_backups_raw))
            if max_backups_val > 0:
                max_backups = max_backups_val
        except (TypeError, ValueError):
            pass

    return {
        "enabled": enabled,
        "interval_hours": interval,
        "max_backups": max_backups,
    }


def update_auto_backup_settings(
    settings: Optional[AutoBackupSettings] = None,
    *,
    enabled: Optional[bool] = None,
    interval_hours: Optional[int] = None,
    max_backups: Optional[int] = None,
) -> bool:
    """更新自动备份配置并实时应用

    可以传递完整的设置字典或单独的关键字参数
    """
    try:
        current = get_auto_backup_settings()

        # 如果传递了字典，从字典中获取值
        if settings is not None:
            new_enabled = settings.get("enabled", current["enabled"])
            new_interval = settings.get(
                "interval_hours",
                current["interval_hours"]
            )
            new_max_backups = settings.get(
                "max_backups",
                current["max_backups"]
            )
        else:
            # 否则从关键字参数获取
            new_enabled = current["enabled"] if enabled is None else enabled
            new_interval = (
                current["interval_hours"]
                if interval_hours is None
                else max(1, interval_hours)
            )
            new_max_backups = (
                current["max_backups"]
                if max_backups is None
                else max(1, max_backups)
            )

        try:
            new_interval = max(1, int(new_interval))
        except (TypeError, ValueError):
            new_interval = current["interval_hours"]

        try:
            new_max_backups = max(1, int(new_max_backups))
        except (TypeError, ValueError):
            new_max_backups = current["max_backups"]

        try:
            from db_utils import set_system_config  # type: ignore
        except ImportError:
            set_system_config = None  # type: ignore

        if set_system_config is not None:
            set_system_config(
                "auto_backup_enabled",
                "true" if new_enabled else "false",
                "是否启用自动备份",
            )
            set_system_config(
                "auto_backup_interval_hours",
                str(new_interval),
                "自动备份间隔（小时）",
            )
            set_system_config(
                "auto_backup_max_backups",
                str(new_max_backups),
                "最多保留备份数量",
            )

        previous_running = backup_system.is_running
        interval_changed = new_interval != backup_system.backup_interval_hours
        backup_system.backup_interval_hours = new_interval
        backup_system.max_backups = new_max_backups

        if not new_enabled and previous_running:
            stop_backup_service()
            return True

        if new_enabled and not previous_running:
            start_backup_service()
            return True

        if new_enabled and interval_changed:
            stop_backup_service()
            start_backup_service()
            return True

        return True
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        logging.error("更新自动备份设置失败: %s", e)
        return False
