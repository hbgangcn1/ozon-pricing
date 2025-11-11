"""
自动备份系统
提供定期自动备份、备份验证、自动清理等功能
"""

import os
import sqlite3
import shutil
import time
import threading
from datetime import datetime
from pathlib import Path
import logging
from contextlib import contextmanager
from typing import Optional, TypedDict

# 配置日志


def _setup_logging():
    """设置日志配置，避免模块级配置导致的问题"""
    # 检查是否已经配置过日志
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('backup.log', encoding='utf-8'),
                logging.StreamHandler(),
            ],
        )


# 延迟初始化日志
_setup_logging()


@contextmanager
def backup_db_connection(backup_path):
    """备份数据库连接上下文管理器"""
    conn = None
    try:
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()
        yield conn, cursor
    finally:
        if conn:
            conn.close()


def _load_schedule_module():
    """惰性加载 schedule 模块，缺失时返回 None。

    这样避免模块级常量导致的“不可到达代码”静态分析告警。
    """
    try:  # pragma: no cover - 仅在运行环境存在时加载
        import schedule as _schedule  # type: ignore
        return _schedule
    except ImportError:
        return None


class AutoBackupSystem:
    def __init__(self, db_path="pricing_system.db", backup_dir="backups"):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.backup_interval_hours = 6  # 每6小时备份一次
        self.max_backups = 28  # 保留最近28个备份（一周：7天 × 4次/天）
        self.backup_thread = None
        self.is_running = False

        # 确保备份目录存在
        Path(backup_dir).mkdir(exist_ok=True)

    def create_backup(self):
        """创建数据库备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"auto_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)

            # 复制数据库文件
            shutil.copy2(self.db_path, backup_path)
            # 验证备份
            if self.verify_backup(backup_path):
                logging.info(f"✅ 自动备份成功: {backup_filename}")
                self.cleanup_old_backups()
                return True
            else:
                logging.error(f"❌ 备份验证失败: {backup_filename}")
                os.remove(backup_path)
                return False

        except (OSError, sqlite3.Error) as e:
            logging.error(f"❌ 备份失败: {str(e)}")
            return False

    @staticmethod
    def verify_backup(backup_path):
        """验证备份文件是否有效"""
        try:
            with backup_db_connection(backup_path) as (conn, c):
                # 检查关键表是否存在
                tables = ['users', 'products', 'logistics']
                for table_name in tables:
                    # table_name来自硬编码列表，安全
                    c.execute(  # nosec B608
                        f"SELECT COUNT(*) FROM {table_name}"
                    )
                    record_count = c.fetchone()[0]
                    logging.info(f"备份验证 - {table_name}: {record_count} 条记录")

                return True

        except (sqlite3.Error, OSError) as e:
            logging.error(f"备份验证失败: {str(e)}")
            return False

    def cleanup_old_backups(self):
        """清理旧的备份文件"""
        try:
            backup_files = []
            for fname in os.listdir(self.backup_dir):
                if not fname.endswith(".db"):
                    continue
                if not (
                    fname.startswith("auto_backup_")
                    or fname.startswith("manual_backup_")
                ):
                    continue
                file_path = os.path.join(self.backup_dir, fname)
                backup_files.append(
                    (file_path, os.path.getmtime(file_path))
                )

            # 按修改时间排序，保留最新的
            backup_files.sort(key=lambda x: x[1], reverse=True)

            # 删除多余的备份
            if len(backup_files) > self.max_backups:
                for file_path, _ in backup_files[self.max_backups:]:
                    os.remove(file_path)
                    logging.info(
                        "🗑️ 删除旧备份: %s",
                        os.path.basename(file_path),
                    )

        except (OSError, FileNotFoundError) as e:
            logging.error(f"清理旧备份失败: {str(e)}")

    def get_backup_stats(self):
        """获取备份统计信息"""
        try:
            backup_files = []
            total_size = 0

            for fname in os.listdir(self.backup_dir):
                is_auto_backup = fname.startswith("auto_backup_")
                is_manual_backup = fname.startswith("manual_backup_")
                if (
                    (is_auto_backup or is_manual_backup) and
                    fname.endswith(".db")
                ):
                    file_path = os.path.join(self.backup_dir, fname)
                    size = os.path.getsize(file_path)
                    mtime = os.path.getmtime(file_path)
                    backup_files.append(
                        {
                            'name': fname,
                            'path': file_path,
                            'size': size,
                            'mtime': datetime.fromtimestamp(mtime),
                            'type': 'auto' if is_auto_backup else 'manual',
                        }
                    )
                    total_size += size

            return {
                'count': len(backup_files),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'files': sorted(
                    backup_files,
                    key=lambda x: x['mtime'],
                    reverse=True,
                ),
            }

        except (OSError, FileNotFoundError) as e:
            logging.error(f"获取备份统计失败: {str(e)}")
            return None

    def get_backup_file_path(self, backup_filename: str) -> str:
        """获取备份文件的完整路径"""
        return os.path.join(self.backup_dir, backup_filename)

    def delete_backup(self, backup_filename: str) -> bool:
        """删除指定的备份文件"""
        backup_path = self.get_backup_file_path(backup_filename)
        if not os.path.exists(backup_path):
            logging.warning("尝试删除不存在的备份文件: %s", backup_filename)
            return False
        try:
            os.remove(backup_path)
            logging.info("🗑️ 已删除备份文件: %s", backup_filename)
            return True
        except OSError as exc:
            logging.error("删除备份文件失败 %s: %s", backup_filename, exc)
            return False

    def read_backup_file(self, backup_filename: str) -> bytes:
        """读取备份文件内容"""
        backup_path = self.get_backup_file_path(backup_filename)
        with open(backup_path, "rb") as file_obj:
            return file_obj.read()

    def restore_from_backup(self, backup_filename):
        """从备份文件恢复数据库"""
        try:
            backup_path = self.get_backup_file_path(backup_filename)

            if not os.path.exists(backup_path):
                logging.error(f"备份文件不存在: {backup_filename}")
                return False

            # 验证备份文件
            if not self.verify_backup(backup_path):
                logging.error(f"备份文件验证失败: {backup_filename}")
                return False

            # 创建当前数据库的备份
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_backup = f"pre_restore_backup_{timestamp}.db"
            shutil.copy2(
                self.db_path,
                os.path.join(self.backup_dir, current_backup),
            )
            # 恢复数据库
            shutil.copy2(backup_path, self.db_path)

            logging.info(f"✅ 数据库恢复成功: {backup_filename}")
            return True

        except (OSError, FileNotFoundError, sqlite3.Error) as e:
            logging.error(f"❌ 数据库恢复失败: {str(e)}")
            return False

    def start_auto_backup(self):
        """启动自动备份"""
        if self.is_running:
            logging.warning("自动备份已在运行中")
            return

        self.is_running = True

        # 立即创建一次备份
        self.create_backup()

        sched = _load_schedule_module()

        def run_scheduler_with_schedule():
            # 使用第三方 schedule 库
            while self.is_running:
                try:
                    sched.run_pending()  # type: ignore[union-attr]
                except Exception as sched_exc:
                    logging.exception("调度运行错误: %s", sched_exc)
                time.sleep(60)  # 每分钟检查一次

        def run_scheduler_fallback():
            # 无 schedule 库时的简易回退调度：按间隔轮询执行
            interval = max(1, int(self.backup_interval_hours * 3600))
            next_time = time.time() + interval
            while self.is_running:
                now = time.time()
                if now >= next_time:
                    try:
                        self.create_backup()
                    except Exception as fb_exc:
                        logging.exception("定时备份失败: %s", fb_exc)
                    next_time = now + interval
                time.sleep(60)

        # 设置定时任务（优先使用 schedule；缺失时采用回退）
        if sched is not None:
            try:
                sched.every(self.backup_interval_hours).hours.do(
                    self.create_backup
                )  # type: ignore[union-attr]
            except Exception as bind_exc:
                logging.warning("绑定 schedule 失败，回退到简易调度: %s", bind_exc)
                self.backup_thread = threading.Thread(
                    target=run_scheduler_fallback,
                    daemon=True,
                )
            else:
                self.backup_thread = threading.Thread(
                    target=run_scheduler_with_schedule,
                    daemon=True,
                )
        else:
            logging.warning("未安装 schedule 库，使用简易回退调度")
            self.backup_thread = threading.Thread(
                target=run_scheduler_fallback,
                daemon=True,
            )

        self.backup_thread.start()

        logging.info(
            "🚀 自动备份已启动，每%s小时备份一次",
            self.backup_interval_hours,
        )

    def stop_auto_backup(self):
        """停止自动备份"""
        self.is_running = False
        if self.backup_thread:
            self.backup_thread.join()
        logging.info("⏹️ 自动备份已停止")

    def manual_backup(self):
        """手动创建备份"""
        logging.info("📦 开始手动备份...")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"manual_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)

            # 复制数据库文件
            shutil.copy2(self.db_path, backup_path)
            # 验证备份
            if self.verify_backup(backup_path):
                logging.info(f"✅ 手动备份成功: {backup_filename}")
                self.cleanup_old_backups()
                return True
            else:
                logging.error(f"❌ 手动备份验证失败: {backup_filename}")
                os.remove(backup_path)
                return False

        except (OSError, sqlite3.Error) as e:
            logging.error(f"❌ 手动备份失败: {str(e)}")
            return False


# 全局备份系统实例
backup_system = AutoBackupSystem()


def start_backup_service():
    """启动备份服务"""
    settings = get_auto_backup_settings()
    if not settings['enabled']:
        logging.info("自动备份已禁用，跳过启动。")
        return
    backup_system.backup_interval_hours = settings['interval_hours']
    backup_system.start_auto_backup()


def stop_backup_service():
    """停止备份服务"""
    backup_system.stop_auto_backup()


def create_manual_backup():
    """创建手动备份"""
    return backup_system.manual_backup()


def get_backup_info():
    """获取备份信息"""
    return backup_system.get_backup_stats()


def list_backup_files():
    """列出所有备份文件"""
    stats = get_backup_info()
    if not stats:
        return []
    return stats['files']


def verify_backup_file(backup_filename: str) -> bool:
    """验证指定备份文件"""
    backup_path = backup_system.get_backup_file_path(backup_filename)
    return backup_system.verify_backup(backup_path)


def delete_backup_file(backup_filename: str) -> bool:
    """删除指定备份文件"""
    return backup_system.delete_backup(backup_filename)


def read_backup_file(backup_filename: str) -> bytes:
    """读取备份文件内容"""
    return backup_system.read_backup_file(backup_filename)


# noinspection PyUnusedLocal
def restore_database(backup_filename, create_snapshot=True):
    """恢复数据库

    Args:
        backup_filename: 备份文件名
        create_snapshot: 是否在恢复前创建快照 (仅PostgreSQL支持)

    Note:
        create_snapshot 参数仅在 PostgreSQL 模式下有效。
        在 SQLite 模式下此参数被忽略，保留是为了接口一致性。
        PostgreSQL 模式下，此函数会被运行时替换。
    """
    return backup_system.restore_from_backup(backup_filename)


class AutoBackupSettings(TypedDict):
    enabled: bool
    interval_hours: int
    max_backups: int


def get_auto_backup_settings() -> AutoBackupSettings:
    """获取自动备份配置"""
    try:
        from db_utils import get_system_config  # type: ignore
    except ImportError:
        get_system_config = None  # type: ignore

    enabled = True
    interval = backup_system.backup_interval_hours
    max_backups = backup_system.max_backups

    if get_system_config is not None:
        enabled_raw = get_system_config('auto_backup_enabled', 'true')
        interval_raw = get_system_config(
            'auto_backup_interval_hours',
            str(interval)
        )
        max_backups_raw = get_system_config(
            'auto_backup_max_backups',
            str(max_backups)
        )
        enabled = str(enabled_raw).lower() == 'true'
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

    result: AutoBackupSettings = {
        'enabled': enabled,
        'interval_hours': interval,
        'max_backups': max_backups,
    }
    return result


def update_auto_backup_settings(
    settings: Optional[AutoBackupSettings] = None,
    *,
    enabled: Optional[bool] = None,
    interval_hours: Optional[int] = None,
    max_backups: Optional[int] = None
) -> bool:
    """更新自动备份配置并实时应用

    可以传递完整的设置字典或单独的关键字参数
    """
    try:
        current_settings = get_auto_backup_settings()

        # 如果传递了字典，从字典中获取值
        if settings is not None:
            new_enabled = settings.get('enabled', current_settings['enabled'])
            new_interval = settings.get(
                'interval_hours',
                current_settings['interval_hours']
            )
            new_max_backups = settings.get(
                'max_backups',
                current_settings['max_backups']
            )
        else:
            # 否则从关键字参数获取
            new_enabled = (
                current_settings['enabled'] if enabled is None else enabled
            )
            new_interval = (
                current_settings['interval_hours']
                if interval_hours is None
                else max(1, interval_hours)
            )
            new_max_backups = (
                current_settings['max_backups']
                if max_backups is None
                else max(1, max_backups)
            )

        try:
            new_interval = max(1, int(new_interval))
        except (TypeError, ValueError):
            new_interval = current_settings['interval_hours']

        try:
            new_max_backups = max(1, int(new_max_backups))
        except (TypeError, ValueError):
            new_max_backups = current_settings['max_backups']

        try:
            from db_utils import set_system_config  # type: ignore
        except ImportError:
            set_system_config = None  # type: ignore

        if set_system_config is not None:
            set_system_config(
                'auto_backup_enabled',
                'true' if new_enabled else 'false',
                '是否启用自动备份'
            )
            set_system_config(
                'auto_backup_interval_hours',
                str(new_interval),
                '自动备份间隔（小时）'
            )
            set_system_config(
                'auto_backup_max_backups',
                str(new_max_backups),
                '最多保留备份数量'
            )

        backup_was_running = backup_system.is_running
        restart_required = (
            backup_was_running
            and new_interval != backup_system.backup_interval_hours
        )

        backup_system.backup_interval_hours = new_interval
        backup_system.max_backups = new_max_backups

        if not new_enabled and backup_was_running:
            stop_backup_service()
            return True

        if new_enabled and not backup_was_running:
            start_backup_service()
            return True

        if new_enabled and restart_required:
            stop_backup_service()
            start_backup_service()
            return True

        return True
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        logging.error("更新自动备份设置失败: %s", e)
        return False


try:  # pragma: no cover - 避免导入错误导致初始化失败
    from db_config import DB_TYPE  # type: ignore
except ImportError:  # pragma: no cover
    DB_TYPE = 'sqlite'  # type: ignore


if DB_TYPE == 'postgresql':  # pragma: no cover - 运行时动态切换
    from postgres_backup_service import (  # type: ignore
        backup_system as _pg_backup_system,
        create_manual_backup as _pg_create_manual_backup,
        delete_backup_file as _pg_delete_backup_file,
        get_auto_backup_settings as _pg_get_auto_backup_settings,
        get_backup_info as _pg_get_backup_info,
        list_backup_files as _pg_list_backup_files,
        read_backup_file as _pg_read_backup_file,
        restore_database as _pg_restore_database,
        start_backup_service as _pg_start_backup_service,
        stop_backup_service as _pg_stop_backup_service,
        update_auto_backup_settings as _pg_update_auto_backup_settings,
        verify_backup_file as _pg_verify_backup_file,
    )

    backup_system = _pg_backup_system  # type: ignore
    create_manual_backup = (  # noqa: F811
        _pg_create_manual_backup  # type: ignore
    )
    delete_backup_file = (  # noqa: F811
        _pg_delete_backup_file  # type: ignore
    )
    get_auto_backup_settings = (  # noqa: F811
        _pg_get_auto_backup_settings  # type: ignore
    )
    get_backup_info = _pg_get_backup_info  # type: ignore  # noqa: F811
    list_backup_files = (  # noqa: F811
        _pg_list_backup_files  # type: ignore
    )
    read_backup_file = _pg_read_backup_file  # type: ignore  # noqa: F811
    restore_database = _pg_restore_database  # type: ignore  # noqa: F811
    start_backup_service = (  # noqa: F811
        _pg_start_backup_service  # type: ignore
    )
    stop_backup_service = (  # noqa: F811
        _pg_stop_backup_service  # type: ignore
    )
    update_auto_backup_settings = (  # noqa: F811
        _pg_update_auto_backup_settings  # type: ignore
    )
    verify_backup_file = (  # noqa: F811
        _pg_verify_backup_file  # type: ignore
    )


if __name__ == "__main__":
    # 测试备份系统
    print("🧪 测试自动备份系统...")

    # 创建手动备份
    if create_manual_backup():
        print("✅ 手动备份测试成功")
    else:
        print("❌ 手动备份测试失败")

    # 获取备份信息
    backup_stats = get_backup_info()
    if backup_stats:
        print(
            f"📊 备份统计: {backup_stats['count']} 个备份文件，"
            f"总大小: {backup_stats['total_size_mb']} MB",
        )
        files = backup_stats.get('files')
        if isinstance(files, list):
            print("📋 最新备份文件:")
            for entry in files[:3]:
                ts = entry['mtime'].strftime('%Y-%m-%d %H:%M:%S')
                print(f"  - {entry['name']} ({ts})")

    print("🎯 备份系统测试完成")
