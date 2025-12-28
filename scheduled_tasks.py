# -*- coding: utf-8 -*-
"""
定时任务调度
"""

import schedule
import time
import threading
from datetime import datetime
from logger_config import logger

# 全局变量：确保调度器只启动一次
_scheduler_thread: threading.Thread | None = None
_scheduler_lock = threading.Lock()
_scheduler_started = False


def job_reset_free_calculations():
    """定时任务：重置免费用户每日计算次数"""
    logger.info("定时任务开始：重置免费用户计算次数")
    try:
        from db_utils import reset_free_users_daily_calculations
        affected_rows = reset_free_users_daily_calculations()
        msg = f"定时任务完成：重置了 {affected_rows} 个免费用户的计算次数"
        logger.info(msg)
    except ImportError:
        logger.error(
            "定时任务失败：无法导入 reset_free_users_daily_calculations")
    except (OSError, IOError) as e:
        logger.error(f"定时任务失败：数据库访问错误 - {e}")
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"定时任务失败：数据类型错误 - {e}")
    except Exception as e:  # noinspection PyBroadException
        # 定时任务需要捕获所有异常以确保调度器继续运行
        logger.exception(f"定时任务异常：重置免费用户计算次数 - {e}")


def job_recycle_idle_connections():
    """定时任务：回收空闲数据库连接"""
    logger.debug("定时任务开始：回收空闲数据库连接")
    try:
        from db_utils import monitor_connections
        status = monitor_connections()
        logger.debug(f"连接监控完成：状态={status}")
    except ImportError:
        logger.error("定时任务失败：无法导入 monitor_connections")
    except Exception as e:  # noinspection PyBroadException
        # 定时任务需要捕获所有异常以确保调度器继续运行
        logger.exception(f"定时任务异常：回收空闲连接 - {e}")


def _start_connection_monitor():
    """启动连接监控"""
    try:
        from connection_monitor_enhanced import get_connection_monitor
        monitor = get_connection_monitor()
        if not monitor.monitoring:
            monitor.start_monitoring()
            logger.info("连接监控已启动")
    except ImportError:
        logger.warning("连接监控模块不可用")


def _start_exchange_rate_monitor():
    """启动汇率监控"""
    try:
        from exchange_rate_monitor_enhanced import (
            get_exchange_rate_monitor
        )
        monitor = get_exchange_rate_monitor()
        if not monitor.monitoring:
            monitor.start_monitoring()
            logger.info("汇率监控已启动")
    except ImportError:
        logger.warning("汇率监控模块不可用")


def _start_payment_callback_monitor():
    """启动支付回调监控"""
    try:
        from payment_callback_enhanced import (
            get_payment_callback_monitor
        )
        monitor = get_payment_callback_monitor()
        if not monitor.monitoring:
            monitor.start_monitoring()
            logger.info("支付回调监控已启动")
    except ImportError:
        logger.warning("支付回调监控模块不可用")


def job_start_enhanced_monitors():
    """定时任务：启动增强监控系统"""
    logger.info("定时任务开始：启动增强监控系统")
    try:
        # 启动连接监控
        _start_connection_monitor()

        # 启动汇率监控
        _start_exchange_rate_monitor()

        # 启动支付回调监控
        _start_payment_callback_monitor()

    except Exception as e:
        logger.exception(f"启动增强监控系统失败: {e}")


def run_scheduler():
    """运行调度器"""
    logger.info("定时任务调度器启动")

    # 配置定时任务
    # 每天凌晨0点执行：重置免费用户计算次数
    schedule.every().day.at("00:00").do(job_reset_free_calculations)

    # 每5分钟执行一次：回收空闲数据库连接
    schedule.every(5).minutes.do(job_recycle_idle_connections)

    # 启动时检查是否需要执行重置
    # 如果当前时间已经过了今天的0点，说明今天的重置应该已经执行过了
    # 或者定时任务会在下次0点执行，所以不需要在启动时重置
    current_time = datetime.now()
    today_midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)

    if current_time > today_midnight:
        # 已经过了今天的0点，不需要重置（定时任务会在0点执行）
        logger.info(
            f"当前时间 {current_time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"已过今日0点，跳过启动时重置（定时任务会在0点执行）"
        )
    else:
        # 如果当前时间还没到今天的0点（理论上不应该发生），执行重置
        logger.info("执行初始计算次数重置...")
        job_reset_free_calculations()

    # 启动增强监控系统（启动时执行一次）
    logger.info("启动增强监控系统...")
    job_start_enhanced_monitors()

    # 持续运行
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


def start_scheduler_thread():
    """
    启动调度器线程（带双重保护：全局变量 + 线程锁）
    确保即使 session_state 被重置，也不会重复启动
    """
    global _scheduler_thread, _scheduler_started

    # 第一层保护：检查全局标志
    if _scheduler_started:
        logger.debug("定时任务调度器已启动，跳过重复初始化")
        return _scheduler_thread

    # 第二层保护：使用线程锁确保线程安全
    with _scheduler_lock:
        # 双重检查（Double-Check Locking 模式）
        if _scheduler_started:
            logger.debug("定时任务调度器已启动（锁内检查），跳过重复初始化")
            return _scheduler_thread

        # 检查线程是否还在运行
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            logger.debug("定时任务调度器线程仍在运行，跳过重复初始化")
            _scheduler_started = True
            return _scheduler_thread

        # 启动新线程
        try:
            _scheduler_thread = threading.Thread(
                target=run_scheduler,
                daemon=True,
                name="Scheduler"
            )
            _scheduler_thread.start()
            _scheduler_started = True
            logger.info("✅ 定时任务调度器线程已启动")
            return _scheduler_thread
        except Exception as e:
            logger.error(f"❌ 启动定时任务调度器线程失败: {e}")
            _scheduler_started = False
            _scheduler_thread = None
            raise


if __name__ == "__main__":
    # 直接运行调度器
    run_scheduler()
