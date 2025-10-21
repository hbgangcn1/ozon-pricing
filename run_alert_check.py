# -*- coding: utf-8 -*-
"""
手动运行告警检查（已禁用 - alert_manager模块不存在）
"""

# from alert_manager import alert_manager  # alert_manager 模块不存在
from logger_config import logger


def main():
    """主函数"""
    logger.info("告警检查功能已禁用 - alert_manager模块不存在")
    print("\n" + "=" * 60)
    print("⚠️ 告警检查功能已禁用")
    print("=" * 60)
    print("alert_manager 模块不存在")
    print("如需启用此功能，请创建 alert_manager.py 模块")
    print("=" * 60)

    # results = alert_manager.check_all_alerts()
    #
    # print("\n" + "=" * 60)
    # print("告警检查结果:")
    # print("=" * 60)
    # print(f"配额告警: {results['quota']} 条")
    # print(f"订阅告警: {results['subscription']} 条")
    # print(f"支付告警: {results['payment']} 条")
    # print(f"总计: {sum(results.values())} 条")
    # print("=" * 60)
    #
    # if sum(results.values()) > 0:
    #     print("\n✅ 已创建告警，请登录管理员后台查看")
    # else:
    #     print("\n✅ 未发现需要告警的情况")


if __name__ == "__main__":
    main()
