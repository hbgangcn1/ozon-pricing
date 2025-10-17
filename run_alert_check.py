# -*- coding: utf-8 -*-
"""
手动运行告警检查
"""

from alert_manager import alert_manager
from logger_config import logger


def main():
    """主函数"""
    logger.info("手动触发告警检查...")
    
    results = alert_manager.check_all_alerts()
    
    print("\n" + "=" * 60)
    print("告警检查结果:")
    print("=" * 60)
    print(f"配额告警: {results['quota']} 条")
    print(f"订阅告警: {results['subscription']} 条")
    print(f"支付告警: {results['payment']} 条")
    print(f"总计: {sum(results.values())} 条")
    print("=" * 60)
    
    if sum(results.values()) > 0:
        print("\n✅ 已创建告警，请登录管理员后台查看")
    else:
        print("\n✅ 未发现需要告警的情况")


if __name__ == "__main__":
    main()


