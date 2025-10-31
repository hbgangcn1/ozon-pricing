# -*- coding: utf-8 -*-
"""
部署高优先级问题修复
包括：
1. 数据库连接泄露检测和告警
2. 汇率API依赖风险增强
3. 支付回调处理可靠性增强
"""

import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def deploy_connection_monitoring():
    """部署连接监控增强"""
    logger.info("=" * 60)
    logger.info("部署数据库连接监控增强...")
    try:
        from connection_monitor_enhanced import get_connection_monitor
        monitor = get_connection_monitor()
        if not monitor.monitoring:
            monitor.start_monitoring()
        logger.info("✅ 数据库连接监控已启动")
        return True
    except Exception as e:
        logger.error(f"❌ 部署连接监控失败: {e}")
        return False


def deploy_exchange_rate_monitoring():
    """部署汇率监控增强"""
    logger.info("=" * 60)
    logger.info("部署汇率监控增强...")
    try:
        from exchange_rate_monitor_enhanced import (
            get_exchange_rate_monitor
        )
        monitor = get_exchange_rate_monitor()
        if not monitor.monitoring:
            monitor.start_monitoring()
        logger.info("✅ 汇率监控已启动")
        return True
    except Exception as e:
        logger.error(f"❌ 部署汇率监控失败: {e}")
        return False


def deploy_payment_callback_enhancement():
    """部署支付回调增强"""
    logger.info("=" * 60)
    logger.info("部署支付回调处理增强...")
    try:
        from payment_callback_enhanced import get_payment_callback_monitor
        monitor = get_payment_callback_monitor()
        if not monitor.monitoring:
            monitor.start_monitoring()
        logger.info("✅ 支付回调监控已启动")
        return True
    except Exception as e:
        logger.error(f"❌ 部署支付回调增强失败: {e}")
        return False


def verify_deployment():
    """验证部署结果"""
    logger.info("=" * 60)
    logger.info("验证部署结果...")

    results = {
        'connection_monitoring': False,
        'exchange_rate_monitoring': False,
        'payment_callback_enhancement': False
    }

    # 验证连接监控
    try:
        from connection_monitor_enhanced import get_connection_monitor
        monitor = get_connection_monitor()
        status = monitor.get_monitor_status()
        if status['monitoring']:
            results['connection_monitoring'] = True
            logger.info(f"✅ 连接监控运行中: {status}")
    except Exception as e:
        logger.error(f"❌ 连接监控验证失败: {e}")

    # 验证汇率监控
    try:
        from exchange_rate_monitor_enhanced import (
            get_exchange_rate_monitor
        )
        monitor = get_exchange_rate_monitor()
        status = monitor.get_monitor_status()
        if status['monitoring']:
            results['exchange_rate_monitoring'] = True
            logger.info(f"✅ 汇率监控运行中: {status}")
    except Exception as e:
        logger.error(f"❌ 汇率监控验证失败: {e}")

    # 验证支付回调增强
    try:
        from payment_callback_enhanced import get_payment_callback_monitor
        monitor = get_payment_callback_monitor()
        stats = monitor.get_stats()
        results['payment_callback_enhancement'] = True
        logger.info(f"✅ 支付回调监控运行中: {stats}")
    except Exception as e:
        logger.error(f"❌ 支付回调增强验证失败: {e}")

    return results


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始部署高优先级问题修复")
    logger.info("=" * 60)

    # 部署各项增强
    results = {
        'connection_monitoring': deploy_connection_monitoring(),
        'exchange_rate_monitoring': deploy_exchange_rate_monitoring(),
        'payment_callback_enhancement': deploy_payment_callback_enhancement()
    }

    # 验证部署
    verification = verify_deployment()

    # 汇总结果
    logger.info("=" * 60)
    logger.info("部署结果汇总:")
    logger.info("=" * 60)

    all_success = True
    for component, success in results.items():
        verified = verification.get(component, False)
        status = "✅ 成功" if success else "❌ 失败"
        verify_status = "✅ 已验证" if verified else "⚠️ 未验证"
        logger.info(f"{component}: {status} ({verify_status})")

        if not success or not verified:
            all_success = False

    logger.info("=" * 60)
    if all_success:
        logger.info("🎉 所有高优先级问题修复已成功部署！")
        logger.info("")
        logger.info("部署的功能包括：")
        logger.info("1. ✅ 数据库连接泄露检测和告警系统")
        logger.info("2. ✅ 汇率API多数据源和告警系统")
        logger.info("3. ✅ 支付回调处理可靠性增强（队列监控、重试机制）")
        logger.info("")
        logger.info("这些系统将在后台持续运行，监控相关指标并发送告警。")
        return 0
    else:
        logger.error("⚠️  部分功能部署失败，请检查日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())
