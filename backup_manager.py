"""
备份管理工具
提供备份查看、恢复、清理等功能
"""

import os
import sqlite3
import shutil
from datetime import datetime
from contextlib import contextmanager


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


def create_backup():
    """创建数据库备份"""
    try:
        # 确保备份目录存在
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"manual_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)

        # 复制数据库文件
        shutil.copy2("pricing_system.db", backup_path)

        # 验证备份
        if verify_backup(backup_path):
            print(f"✅ 备份成功: {backup_filename}")
            return backup_filename
        else:
            print(f"❌ 备份验证失败: {backup_filename}")
            os.remove(backup_path)
            return None

    except (OSError, IOError, sqlite3.Error, ValueError) as e:
        print(f"❌ 备份失败: {e}")
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
        with backup_db_connection(backup_path) as (conn, c):
            # 检查关键表
            tables = ['users', 'products', 'logistics']
            stats = {}

            for table_name in tables:
                try:
                    c.execute(f"SELECT COUNT(*) FROM {table_name}")
                    record_count = c.fetchone()[0]
                    stats[table_name] = record_count
                except sqlite3.OperationalError:
                    stats[table_name] = "表不存在"

            return stats

    except (sqlite3.Error, OSError) as e:
        print(f"❌ 备份验证失败: {e}")
        return None


def restore_backup(backup_filename, confirm=None):
    """从备份文件恢复数据库"""
    try:
        backup_dir = "backups"
        backup_path = os.path.join(backup_dir, backup_filename)

        if not os.path.exists(backup_path):
            print(f"❌ 备份文件不存在: {backup_filename}")
            return False

        # 验证备份文件
        if not verify_backup(backup_path):
            print(f"❌ 备份文件验证失败: {backup_filename}")
            return False

        # 如果confirm参数为False，直接返回False（模拟用户取消）
        if confirm is False:
            return False

        # 如果confirm参数为None，询问用户确认
        if confirm is None:
            try:
                user_input = input(
                    f"确认要恢复备份 {backup_filename} 吗？(y/N): "
                ).strip().lower()
                if user_input not in ['y', 'yes']:
                    print("❌ 用户取消恢复操作")
                    return False
            except (EOFError, KeyboardInterrupt):
                print("❌ 用户取消恢复操作")
                return False

        # 创建当前数据库的备份
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_backup = f"pre_restore_backup_{timestamp}.db"
        shutil.copy2(
            "pricing_system.db",
            os.path.join(backup_dir, current_backup)
        )

        # 恢复数据库
        shutil.copy2(backup_path, "pricing_system.db")

        print(f"✅ 数据库恢复成功: {backup_filename}")
        return True

    except (OSError, IOError, sqlite3.Error, ValueError) as e:
        print(f"❌ 数据库恢复失败: {e}")
        return False


def show_backup_details(backup_filename):
    """显示备份文件详细信息"""
    try:
        backup_dir = "backups"
        backup_path = os.path.join(backup_dir, backup_filename)

        if not os.path.exists(backup_path):
            print(f"❌ 备份文件不存在: {backup_filename}")
            return None

        # 获取文件信息
        size = os.path.getsize(backup_path)
        mtime = os.path.getmtime(backup_path)

        # 验证备份
        stats = verify_backup(backup_path)

        print(f"📋 备份文件详情: {backup_filename}")
        size_mb = round(size / (1024 * 1024), 2)
        print(f"📁 文件大小: {size_mb} MB")
        time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"📅 创建时间: {time_str}")

        if stats:
            print("📊 数据库表统计:")
            for table_name, record_count in stats.items():
                print(f"  {table_name}: {record_count}")

        return {
            'name': backup_filename,
            'size_mb': round(size / (1024 * 1024), 2),
            'mtime': datetime.fromtimestamp(mtime),
            'stats': stats
        }

    except (OSError, IOError, sqlite3.Error, ValueError) as e:
        print(f"❌ 获取备份详情失败: {e}")
        return None


def cleanup_backups(keep_count=10):
    """清理旧备份文件，保留指定数量的最新备份"""
    try:
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            print("❌ 备份目录不存在")
            return False

        backup_files = []
        for file in os.listdir(backup_dir):
            if file.endswith('.db'):
                file_path = os.path.join(backup_dir, file)
                mtime = os.path.getmtime(file_path)
                backup_files.append((file, file_path, mtime))

        # 按修改时间排序
        backup_files.sort(key=lambda x: x[2], reverse=True)

        # 删除多余的备份
        if len(backup_files) > keep_count:
            for file, file_path, _ in backup_files[keep_count:]:
                os.remove(file_path)
                print(f"🗑️ 删除旧备份: {file}")

        print(
            f"✅ 清理完成，保留 {min(len(backup_files), keep_count)} 个最新备份"
        )
        return True

    except (OSError, IOError, sqlite3.Error, ValueError) as e:
        print(f"❌ 清理备份失败: {e}")
        return False


def delete_backup(backup_filename):
    """删除备份文件"""
    try:
        backup_dir = "backups"
        backup_path = os.path.join(backup_dir, backup_filename)

        if not os.path.exists(backup_path):
            print(f"❌ 备份文件不存在: {backup_filename}")
            return False

        os.remove(backup_path)
        print(f"✅ 备份文件删除成功: {backup_filename}")
        return True

    except (OSError, IOError, sqlite3.Error, ValueError) as e:
        print(f"❌ 删除备份文件失败: {e}")
        return False


def main():
    """主菜单界面"""
    while True:
        print("\n" + "=" * 50)
        print("📦 备份管理系统")
        print("=" * 50)
        print("1. 列出备份文件")
        print("2. 查看备份详情")
        print("3. 恢复备份")
        print("4. 清理旧备份")
        print("5. 创建新备份")
        print("6. 退出")
        print("-" * 50)

        try:
            choice = input("请选择操作 (1-6): ").strip()

            if choice == "1":
                list_backups()

            elif choice == "2":
                files = list_backups()
                if files:
                    try:
                        index = int(input("请输入备份文件序号: ")) - 1
                        if 0 <= index < len(files):
                            show_backup_details(files[index]['name'])
                        else:
                            print("❌ 无效的序号")
                    except (ValueError, IndexError):
                        print("❌ 无效的输入")

            elif choice == "3":
                files = list_backups()
                if files:
                    try:
                        index = int(input("请输入要恢复的备份文件序号: ")) - 1
                        if 0 <= index < len(files):
                            restore_backup(files[index]['name'])
                        else:
                            print("❌ 无效的序号")
                    except (ValueError, IndexError):
                        print("❌ 无效的输入")

            elif choice == "4":
                try:
                    keep_count = int(input("请输入要保留的备份数量: "))
                    cleanup_backups(keep_count)
                except ValueError:
                    print("❌ 无效的数量")

            elif choice == "5":
                create_backup()

            elif choice == "6":
                print("👋 再见！")
                break

            else:
                print("❌ 无效的选择，请输入 1-6")

        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break


if __name__ == "__main__":
    # 命令行界面
    import sys

    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python backup_manager.py create    # 创建备份")
        print("  python backup_manager.py list      # 列出备份")
        print("  python backup_manager.py verify <filename>  # 验证备份")
        print("  python backup_manager.py restore <filename> # 恢复备份")
        print("  python backup_manager.py delete <filename>  # 删除备份")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create":
        create_backup()
    elif command == "list":
        list_backups()
    elif command == "verify" and len(sys.argv) > 2:
        filename = sys.argv[2]
        result = verify_backup(os.path.join("backups", filename))
        if result:
            print("✅ 备份验证成功:")
            for table, count in result.items():
                print(f"  {table}: {count}")
    elif command == "restore" and len(sys.argv) > 2:
        filename = sys.argv[2]
        restore_backup(filename)
    elif command == "delete" and len(sys.argv) > 2:
        filename = sys.argv[2]
        delete_backup(filename)
    else:
        print("❌ 无效的命令")
        sys.exit(1)
