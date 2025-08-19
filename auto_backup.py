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
                    c.execute(f"SELECT COUNT(*) FROM {table_name}")
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
                if (
                    fname.startswith("auto_backup_")
                    and fname.endswith(".db")
                ):
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
                    (is_auto_backup or is_manual_backup)
                    and fname.endswith(".db")
                ):
                    file_path = os.path.join(self.backup_dir, fname)
                    size = os.path.getsize(file_path)
                    mtime = os.path.getmtime(file_path)
                    backup_files.append(
                        {
                            'name': fname,
                            'size': size,
                            'mtime': datetime.fromtimestamp(mtime),
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

    def restore_from_backup(self, backup_filename):
        """从备份文件恢复数据库"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_filename)

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


def restore_database(backup_filename):
    """恢复数据库"""
    return backup_system.restore_from_backup(backup_filename)


if __name__ == "__main__":
    # 测试备份系统
    print("🧪 测试自动备份系统...")

    # 创建手动备份
    if create_manual_backup():
        print("✅ 手动备份测试成功")
    else:
        print("❌ 手动备份测试失败")

    # 获取备份信息
    stats = get_backup_info()
    if stats:
        print(
            f"📊 备份统计: {stats['count']} 个备份文件，"
            f"总大小: {stats['total_size_mb']} MB",
        )
        print("📋 最新备份文件:")
        for entry in stats['files'][:3]:
            ts = entry['mtime'].strftime('%Y-%m-%d %H:%M:%S')
            print(f"  - {entry['name']} ({ts})")

    print("🎯 备份系统测试完成")
