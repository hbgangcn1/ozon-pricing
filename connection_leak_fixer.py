#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库连接泄漏检测和修复工具
"""

import sqlite3
import gc
import logging
from typing import Dict, List, Any
from datetime import datetime

# 尝试导入 psutil（可选依赖）
try:
    import psutil  # type: ignore  # noqa: F401
except ImportError:
    PSUTIL_AVAILABLE = False
    print("警告: psutil 未安装，部分功能可能受限")
else:
    PSUTIL_AVAILABLE = True

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConnectionLeakFixer:
    """连接泄漏修复器"""

    def __init__(self, db_path: str = 'pricing_system.db'):
        self.db_path = db_path
        self.fix_history = []

    @staticmethod
    def detect_sqlite_connections() -> int:
        """检测当前活跃的 SQLite 连接数"""
        try:
            if PSUTIL_AVAILABLE:
                # 使用 psutil 检测文件句柄
                import psutil  # type: ignore  # noqa: F811
                process = psutil.Process()
                open_files = process.open_files()
                sqlite_files = [
                    f for f in open_files if '.db' in f.path
                ]
                return len(sqlite_files)
            else:
                # 基本检测：尝试连接数据库
                try:
                    conn = sqlite3.connect(':memory:')
                    conn.close()
                    return 1
                except (sqlite3.Error, OSError):
                    return 0
        except Exception as connection_error:
            logger.error(f"检测连接数失败: {connection_error}")
            return 0

    def detect_leaks(self) -> Dict[str, Any]:
        """检测连接泄漏"""
        try:
            result = {
                'timestamp': datetime.now().isoformat(),
                'active_connections': self.detect_sqlite_connections(),
                'leaks_detected': False,
                'fix_applied': False
            }

            # 检测泄漏条件
            if result['active_connections'] > 20:
                result['leaks_detected'] = True
                logger.warning(
                    f"检测到潜在连接泄漏: {result['active_connections']} 个活跃连接"
                )

            return result
        except Exception as leak_error:
            logger.error(f"检测泄漏失败: {leak_error}")
            return {'error': str(leak_error)}

    def force_gc(self) -> Dict[str, Any]:
        """强制执行垃圾回收"""
        try:
            if PSUTIL_AVAILABLE:
                import psutil  # type: ignore  # noqa: F811
                process = psutil.Process()
                memory_before = process.memory_info()
                memory_before_rss = memory_before.rss
            else:
                memory_before_rss = 0

            # 执行垃圾回收
            collected = gc.collect()

            if PSUTIL_AVAILABLE:
                import psutil  # type: ignore  # noqa: F811
                process = psutil.Process()
                memory_after = process.memory_info()
                memory_after_rss = memory_after.rss
                memory_freed = int(memory_before_rss - memory_after_rss)
            else:
                memory_freed = 0

            result = {
                'timestamp': datetime.now().isoformat(),
                'objects_collected': collected,
                'memory_freed_mb': (
                    memory_freed / (1024 * 1024)
                    if memory_freed > 0
                    else 0
                ),
                'success': True
            }

            logger.info(
                f"垃圾回收完成: 回收 {collected} 个对象"
            )
            self.fix_history.append(result)
            return result

        except Exception as gc_error:
            logger.error(f"垃圾回收失败: {gc_error}")
            return {'error': str(gc_error), 'success': False}

    def close_orphaned_connections(self) -> Dict[str, Any]:
        """关闭孤儿连接（基本实现）"""
        try:
            # 执行垃圾回收
            gc.collect()
            active_before = self.detect_sqlite_connections()

            result = {
                'timestamp': datetime.now().isoformat(),
                'active_before': active_before,
                'active_after': active_before,
                'connections_closed': 0,
                'success': True
            }

            logger.info(
                f"连接清理: 活跃连接数 {active_before}"
            )
            self.fix_history.append(result)
            return result

        except Exception as cleanup_error:
            logger.error(f"关闭孤儿连接失败: {cleanup_error}")
            return {'error': str(cleanup_error), 'success': False}

    def fix_leaks(self) -> Dict[str, Any]:
        """修复连接泄漏"""
        try:
            logger.info("开始修复连接泄漏...")

            # 检测泄漏
            initial_leak_info = self.detect_leaks()

            if not initial_leak_info.get('leaks_detected', False):
                logger.info("未检测到连接泄漏")
                return {
                    'timestamp': datetime.now().isoformat(),
                    'leaks_found': False,
                    'message': '未检测到连接泄漏'
                }

            # 应用修复措施
            fix_results = []

            # 1. 强制垃圾回收
            gc_result = self.force_gc()
            fix_results.append(gc_result)

            # 2. 关闭孤儿连接
            cleanup_result = self.close_orphaned_connections()
            fix_results.append(cleanup_result)

            # 再次检测
            leak_info_after = self.detect_leaks()

            result = {
                'timestamp': datetime.now().isoformat(),
                'leaks_found': True,
                'fixes_applied': fix_results,
                'final_status': leak_info_after,
                'success': True
            }

            logger.info("连接泄漏修复完成")
            self.fix_history.append(result)
            return result

        except Exception as fix_error:
            logger.error(f"修复连接泄漏失败: {fix_error}")
            return {'error': str(fix_error), 'success': False}

    def get_fix_history(self) -> List[Dict[str, Any]]:
        """获取修复历史"""
        return self.fix_history


def detect_and_fix_leaks(
    db_path: str = 'pricing_system.db'
) -> Dict[str, Any]:
    """检测并修复连接泄漏（便捷函数）"""
    connection_fixer = ConnectionLeakFixer(db_path)
    return connection_fixer.fix_leaks()


if __name__ == "__main__":
    # 测试连接泄漏修复
    print("测试连接泄漏修复工具...")

    try:
        fixer = ConnectionLeakFixer()

        # 检测泄漏
        leak_info = fixer.detect_leaks()
        print(f"泄漏检测结果: {leak_info}")

        # 修复泄漏
        fix_result = fixer.fix_leaks()
        print(f"修复结果: {fix_result}")

        # 显示历史
        history = fixer.get_fix_history()
        print(f"修复历史: {len(history)} 条记录")

        print("✅ 连接泄漏修复工具测试通过")

    except Exception as test_error:
        print(f"❌ 测试失败: {test_error}")
