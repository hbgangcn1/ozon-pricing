# -*- coding: utf-8 -*-
"""
定时任务调度
"""

import schedule
import time
import threading
from alert_manager import alert_manager
from logger_config import logger


def job_alert_check():
    """定时任务：告警检查"""
    logger.info("定时任务开始：告警检查")
    try:
        results = alert_manager.check_all_alerts()
        logger.info(f"定时任务完成：创建 {sum(results.values())} 条告警")
    except Exception as e:
        logger.exception("定时任务异常：告警检查")


def run_scheduler():
    """运行调度器"""
    logger.info("定时任务调度器启动")
    
    # 配置定时任务
    schedule.every(1).hours.do(job_alert_check)  # 每小时执行一次
    
    # 启动时立即执行一次
    logger.info("执行初始告警检查...")
    job_alert_check()
    
    # 持续运行
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


def start_scheduler_thread():
    """启动调度器线程"""
    thread = threading.Thread(
        target=run_scheduler,
        daemon=True,
        name="Scheduler"
    )
    thread.start()
    logger.info("定时任务调度器线程已启动")
    return thread


if __name__ == "__main__":
    # 直接运行调度器
    run_scheduler()


