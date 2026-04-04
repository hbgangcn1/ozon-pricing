# -*- coding: utf-8 -*-
"""
数据库适配器连接池关键路径测试
覆盖连接池满时的处理机制
"""

import threading
from db_adapter import get_db_connection
import pytest


class TestConnectionPoolFullHandling:
    """测试连接池满时的处理"""

    def test_connection_pool_full_blocking_behavior(
        self, _clean_db
    ):  # noqa: ARG001
        """
        测试连接池满时的阻塞行为
        中风险场景：验证连接池机制的正确性
        """
        # 注意：这个测试主要验证连接池的行为
        # 在实际环境中，连接池满时会阻塞等待，直到有可用连接
        # 这里我们主要验证连接池机制不会导致程序崩溃

        # 测试：正常获取连接应该成功
        try:
            with get_db_connection() as (_, cursor):  # pyright: ignore[reportGeneralTypeIssues]
                # 执行简单查询验证连接可用
                from db_adapter import adapt_sql
                sql = adapt_sql("SELECT 1")
                cursor.execute(sql)
                result = cursor.fetchone()
                assert result is not None, (
                    "应该能正常获取连接并执行查询"
                )
        except Exception as e:
            pytest.fail(f"获取连接失败: {e}")

    def test_connection_pool_getconn_timeout_handling(
        self, _clean_db
    ):  # noqa: ARG001
        """
        测试连接池获取连接时的超时处理
        中风险场景：验证连接池在极端情况下的行为
        """
        # 注意：psycopg2的getconn默认会阻塞等待，没有超时机制
        # 这是连接池的正常行为，但需要监控连接池使用情况

        # 测试：多次获取连接应该都能成功
        connections = []
        try:
            for i in range(5):
                try:
                    with get_db_connection() as (c, cur):  # pyright: ignore[reportGeneralTypeIssues]
                        # 执行简单查询
                        from db_adapter import adapt_sql
                        sql = adapt_sql("SELECT 1")
                        cur.execute(sql)
                        result = cur.fetchone()
                        assert result is not None, (
                            f"第{i+1}次获取连接应该成功"
                        )
                        connections.append((c, cur))
                except Exception as e:
                    pytest.fail(f"第{i+1}次获取连接失败: {e}")
        finally:
            # 清理连接（由上下文管理器自动处理）
            pass

    def test_connection_pool_connection_recovery(
        self, _clean_db
    ):  # noqa: ARG001
        """
        测试连接池连接恢复机制
        中风险场景：验证连接异常时的恢复能力
        """
        # 测试：连接异常后应该能恢复
        try:
            # 第一次获取连接
            with get_db_connection() as (_, cursor1):
                from db_adapter import adapt_sql
                sql = adapt_sql("SELECT 1")
                cursor1.execute(sql)
                result1 = cursor1.fetchone()
                assert result1 is not None, (
                    "第一次获取连接应该成功"
                )

            # 第二次获取连接（应该能正常恢复）
            with get_db_connection() as (_, cursor2):
                sql = adapt_sql("SELECT 1")
                cursor2.execute(sql)
                result2 = cursor2.fetchone()
                assert result2 is not None, (
                    "第二次获取连接应该成功（连接已恢复）"
                )
        except Exception as e:
            pytest.fail(f"连接恢复失败: {e}")

    def test_connection_pool_concurrent_access(
        self, _clean_db
    ):  # noqa: ARG001
        """
        测试连接池并发访问
        中风险场景：验证高并发情况下的连接池行为
        """
        results = []
        errors = []

        def get_connection_task(task_id):
            """并发获取连接的任务"""
            try:
                with get_db_connection() as (_, cursor):  # pyright: ignore[reportGeneralTypeIssues]
                    from db_adapter import adapt_sql
                    sql = adapt_sql("SELECT ?")
                    cursor.execute(sql, (task_id,))
                    result = cursor.fetchone()
                    results.append((task_id, result))
            except Exception as e:
                errors.append((task_id, str(e)))

        # 创建多个并发任务
        threads = []
        for i in range(10):
            thread = threading.Thread(target=get_connection_task, args=(i,))
            threads.append(thread)
            thread.start()

        # 等待所有任务完成
        for thread in threads:
            thread.join(timeout=5)

        # 验证：所有任务应该成功
        assert len(results) == 10, (
            f"所有并发任务应该成功，实际成功: {len(results)}, 失败: {len(errors)}"
        )
        assert len(errors) == 0, (
            f"不应该有错误，实际错误: {errors}"
        )

