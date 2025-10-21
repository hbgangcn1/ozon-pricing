# -*- coding: utf-8 -*-
"""
定时任务调度
"""

import schedule
import time
import threading
from logger_config import logger


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


def run_scheduler():
    """运行调度器"""
    logger.info("定时任务调度器启动")

    # 配置定时任务
    # 每天凌晨0点执行
    schedule.every().day.at("00:00").do(job_reset_free_calculations)

    # 启动时立即执行一次
    logger.info("执行初始计算次数重置...")
    job_reset_free_calculations()

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
