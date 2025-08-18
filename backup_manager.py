"""
备份管理工具
提供备份查看、恢复、清理等功能
"""

import os
import sqlite3
import shutil
from datetime import datetime
try:
    from .auto_backup import AutoBackupSystem
except ImportError:
    from auto_backup import AutoBackupSystem


class BackupManager:
    """备份管理器类"""

    def __init__(self):
        self.backup_dir = "backups"

    def list_backups(self):
        """列出所有备份文件"""
        if not os.path.exists(self.backup_dir):
            print("❌ 备份目录不存在")
            return None

        backup_files = []
        for file in os.listdir(self.backup_dir):
            if file.endswith('.db'):
                file_path = os.path.join(self.backup_dir, file)
                size = os.path.getsize(file_path)
                mtime = os.path.getmtime(file_path)
                backup_files.append({
                    'name': file,
                    'size_mb': round(size / (1024 * 1024), 2),
                    'mtime': datetime.fromtimestamp(mtime),
                    'path': file_path
                })

        # 按时间排序
        backup_files.sort(key=lambda x: x['mtime'], reverse=True)
        return backup_files

    @staticmethod
    def verify_backup(backup_path):
        """验证备份文件"""
        try:
            conn = sqlite3.connect(backup_path)
            try:
                c = conn.cursor()

                # 检查关键表
                tables = ['users', 'products', 'logistics']
                stats = {}

                for table in tables:
                    try:
                        c.execute(f"SELECT COUNT(*) FROM {table}")
                        count = c.fetchone()[0]
                        stats[table] = count
                    except sqlite3.OperationalError:
                        stats[table] = "表不存在"

                return stats
            finally:
                conn.close()

        except (sqlite3.Error, OSError) as e:
            print(f"❌ 备份验证失败: {e}")
            return None


def list_backups():
    """列出所有备份文件"""
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        print("❌ 备份目录不存在")
        return None

    backup_files = []
    for file in os.listdir(backup_dir):
        if file.endswith('.db'):
            file_path = os.path.join(backup_dir, file)
            size = os.path.getsize(file_path)
            mtime = os.path.getmtime(file_path)
            backup_files.append({
                'name': file,
                'size_mb': round(size / (1024 * 1024), 2),
                'mtime': datetime.fromtimestamp(mtime),
                'path': file_path
            })

    # 按时间排序
    backup_files.sort(key=lambda x: x['mtime'], reverse=True)

    print("📋 备份文件列表:")
    print("=" * 80)
    print(f"{'序号':<4} {'文件名':<35} {'大小(MB)':<10} "
          f"{'创建时间':<20}")
    print("-" * 80)

    for i, file in enumerate(backup_files, 1):
        print(
            f"{i:<4} {file['name']:<35} {file['size_mb']:<10} "
            f"{file['mtime'].strftime('%Y-%m-%d %H:%M:%S'):<20}"
        )

    return backup_files


def verify_backup(backup_path):
    """验证备份文件"""
    try:
        conn = sqlite3.connect(backup_path)
        try:
            c = conn.cursor()

            # 检查关键表
            tables = ['users', 'products', 'logistics']
            stats = {}

            for table in tables:
                try:
                    c.execute(f"SELECT COUNT(*) FROM {table}")
                    count = c.fetchone()[0]
                    stats[table] = count
                except sqlite3.OperationalError:
                    stats[table] = "表不存在"

            return stats
        finally:
            conn.close()

    except (sqlite3.Error, OSError) as e:
        print(f"❌ 备份验证失败: {e}")
        return None


def show_backup_details(backup_filename):
    """显示备份文件详细信息"""
    backup_path = os.path.join("backups", backup_filename)

    if not os.path.exists(backup_path):
        print(f"❌ 备份文件不存在: {backup_filename}")
        return

    print(f"📊 备份文件详情: {backup_filename}")
    print("=" * 50)

    # 文件信息
    size = os.path.getsize(backup_path)
    mtime = os.path.getmtime(backup_path)
    print(f"文件大小: {round(size / (1024 * 1024), 2)} MB")
    print(
        f"创建时间: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # 数据库内容统计
    stats = verify_backup(backup_path)
    if stats:
        print("\n📋 数据库内容:")
        for table, count in stats.items():
            print(f"  {table}: {count} 条记录")
    else:
        print("❌ 无法验证备份文件")


def restore_backup(backup_filename, confirm=False):
    """从备份文件恢复数据库"""
    backup_path = os.path.join("backups", backup_filename)

    if not os.path.exists(backup_path):
        print(f"❌ 备份文件不存在: {backup_filename}")
        return False

    if not confirm:
        print(f"⚠️ 警告: 即将从备份文件 {backup_filename} 恢复数据库")
        print("这将覆盖当前数据库中的所有数据！")
        response = input("确认恢复吗？(输入 'yes' 确认): ")
        if response.lower() != 'yes':
            print("❌ 恢复操作已取消")
            return False

    try:
        # 创建当前数据库的备份
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_backup = f"pre_restore_backup_{timestamp}.db"
        shutil.copy2(
            "pricing_system.db",
            os.path.join("backups", current_backup),
        )
        print(f"✅ 已创建当前数据库备份: {current_backup}")

        # 恢复数据库
        shutil.copy2(backup_path, "pricing_system.db")
        print(f"✅ 数据库恢复成功: {backup_filename}")
        return True

    except OSError as e:
        print(f"❌ 数据库恢复失败: {e}")
        return False


def cleanup_backups(keep_count=10):
    """清理旧的备份文件"""
    backup_system = AutoBackupSystem()
    backup_system.max_backups = keep_count
    backup_system.cleanup_old_backups()
    print(f"✅ 已清理旧备份，保留最新 {keep_count} 个备份文件")


def main():
    """主菜单"""
    while True:
        print("\n" + "=" * 50)
        print("💾 备份管理工具")
        print("=" * 50)
        print("1. 查看备份列表")
        print("2. 查看备份详情")
        print("3. 恢复数据库")
        print("4. 清理旧备份")
        print("5. 创建手动备份")
        print("6. 退出")
        print("-" * 50)

        choice = input("请选择操作 (1-6): ").strip()

        if choice == '1':
            list_backups()

        elif choice == '2':
            backup_files = list_backups()
            if backup_files:
                try:
                    index = int(input("请输入备份文件序号: ")) - 1
                    if 0 <= index < len(backup_files):
                        show_backup_details(backup_files[index]['name'])
                    else:
                        print("❌ 无效的序号")
                except ValueError:
                    print("❌ 请输入有效的数字")

        elif choice == '3':
            backup_files = list_backups()
            if backup_files:
                try:
                    index = int(input("请输入要恢复的备份文件序号: ")) - 1
                    if 0 <= index < len(backup_files):
                        restore_backup(backup_files[index]['name'])
                    else:
                        print("❌ 无效的序号")
                except ValueError:
                    print("❌ 请输入有效的数字")

        elif choice == '4':
            try:
                prompt = "请输入要保留的备份文件数量(默认10): "
                keep_count = int(input(prompt) or "10")
                cleanup_backups(keep_count)
            except ValueError:
                print("❌ 请输入有效的数字")

        elif choice == '5':
            backup_system = AutoBackupSystem()
            if backup_system.manual_backup():
                print("✅ 手动备份创建成功")
            else:
                print("❌ 手动备份创建失败")

        elif choice == '6':
            print("👋 再见！")
            break
        else:
            print("❌ 无效的选择，请重新输入")


if __name__ == "__main__":
    main()
