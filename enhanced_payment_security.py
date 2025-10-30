# -*- coding: utf-8 -*-
"""
增强支付安全系统
解决支付系统安全性问题，加强回调验证和状态同步
"""

import hashlib
import hmac
import json
import time
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# 导入数据库相关模块
try:
    from db_utils import get_db_connection
    from db_adapter import get_db_connection as get_db_connection_adapter
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    get_db_connection = None
    get_db_connection_adapter = None

# 导入微信支付相关模块
try:
    from wechat_pay_v3_api import wechat_pay_v3
    from wechat_pay_config import wechat_config
    WECHAT_PAY_AVAILABLE = True
except ImportError:
    WECHAT_PAY_AVAILABLE = False
    wechat_pay_v3 = None
    wechat_config = None

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaymentStatus(Enum):
    """支付状态枚举"""
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    PARTIAL_REFUNDED = "PARTIAL_REFUNDED"
    EXPIRED = "EXPIRED"


class PaymentEventType(Enum):
    """支付事件类型"""
    PAYMENT_SUCCESS = "PAYMENT.SUCCESS"
    PAYMENT_FAIL = "PAYMENT.FAIL"
    REFUND_SUCCESS = "REFUND.SUCCESS"
    REFUND_FAIL = "REFUND.FAIL"


@dataclass
class PaymentCallbackData:
    """支付回调数据结构"""
    event_type: PaymentEventType
    order_id: str
    transaction_id: str
    amount: int
    status: PaymentStatus
    timestamp: int
    raw_data: Dict[str, Any]
    signature: str
    nonce: str


@dataclass
class PaymentSecurityConfig:
    """支付安全配置"""
    verify_signature: bool = True
    verify_timestamp: bool = True
    timestamp_tolerance: int = 300  # 5分钟
    max_retry_attempts: int = 3
    retry_delay: int = 60  # 1分钟
    enable_duplicate_check: bool = True
    enable_amount_verification: bool = True
    enable_status_sync: bool = True


class PaymentSecurityManager:
    """支付安全管理器"""

    def __init__(self, config: Optional[PaymentSecurityConfig] = None):
        self.config = config or PaymentSecurityConfig()
        self.processed_callbacks = set()  # 已处理回调记录
        self.callback_lock = {}  # 回调处理锁

    def verify_callback_signature(
        self, callback_data: PaymentCallbackData
    ) -> bool:
        """
        验证回调签名

        Args:
            callback_data: 回调数据

        Returns:
            bool: 签名是否有效
        """
        if not self.config.verify_signature:
            return True

        try:
            if not WECHAT_PAY_AVAILABLE:
                logger.warning("微信支付模块不可用，跳过签名验证")
                return True

            # 构建待签名字符串
            timestamp = str(callback_data.timestamp)
            nonce = callback_data.nonce
            body = json.dumps(
                callback_data.raw_data,
                separators=(',', ':'),
                ensure_ascii=False
            )

            # 构建签名串
            sign_str = f"{timestamp}\n{nonce}\n{body}\n"

            # 获取API密钥
            if not WECHAT_PAY_AVAILABLE or wechat_config is None:
                logger.error("微信支付配置不可用")
                return False

            api_key = (getattr(wechat_config, 'api_v3_key', '')
                       if hasattr(wechat_config, 'api_v3_key') else '')
            if not api_key:
                logger.error("微信支付API密钥未配置")
                return False

            # 计算签名
            expected_signature = hmac.new(
                api_key.encode('utf-8'),
                sign_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            # 验证签名
            is_valid = hmac.compare_digest(
                callback_data.signature, expected_signature
            )

            if not is_valid:
                logger.warning(f"支付回调签名验证失败: 订单{callback_data.order_id}")

            return is_valid
        except Exception as e:
            logger.error(f"验证支付回调签名时出错: {e}")
            return False

    def verify_callback_timestamp(
        self, callback_data: PaymentCallbackData
    ) -> bool:
        """
        验证回调时间戳

        Args:
            callback_data: 回调数据

        Returns:
            bool: 时间戳是否有效
        """
        if not self.config.verify_timestamp:
            return True

        try:
            current_time = int(time.time())
            callback_time = callback_data.timestamp

            # 检查时间差
            time_diff = abs(current_time - callback_time)

            if time_diff > self.config.timestamp_tolerance:
                logger.warning(
                    f"支付回调时间戳过期: 订单{callback_data.order_id}, "
                    f"时间差{time_diff}秒"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"验证支付回调时间戳时出错: {e}")
            return False

    def check_duplicate_callback(
        self, callback_data: PaymentCallbackData
    ) -> bool:
        """
        检查重复回调

        Args:
            callback_data: 回调数据

        Returns:
            bool: 是否为重复回调
        """
        if not self.config.enable_duplicate_check:
            return False

        # 生成回调唯一标识
        callback_id = (
            f"{callback_data.order_id}_{callback_data.transaction_id}_"
            f"{callback_data.timestamp}"
        )

        if callback_id in self.processed_callbacks:
            logger.warning(f"检测到重复支付回调: 订单{callback_data.order_id}")
            return True

        # 记录已处理回调
        self.processed_callbacks.add(callback_id)

        # 清理过期记录（保留最近1小时的记录）
        current_time = time.time()
        self.processed_callbacks = {
            cb_id for cb_id in self.processed_callbacks
            if current_time - int(cb_id.split('_')[-1]) < 3600
        }

        return False

    def verify_payment_amount(
        self, callback_data: PaymentCallbackData
    ) -> bool:
        """
        验证支付金额

        Args:
            callback_data: 回调数据

        Returns:
            bool: 金额是否匹配
        """
        if not self.config.enable_amount_verification:
            return True

        try:
            if not DB_AVAILABLE or get_db_connection is None:
                logger.warning("数据库不可用，跳过金额验证")
                return True

            with get_db_connection() as (conn, c):
                # 查询订单金额
                order_data = c.execute("""
                    SELECT amount, status FROM payment_orders
                    WHERE order_id = ?
                """, (callback_data.order_id,)).fetchone()

                if not order_data:
                    logger.error(f"订单不存在: {callback_data.order_id}")
                    return False

                expected_amount, current_status = order_data

                # 验证金额
                if callback_data.amount != expected_amount:
                    logger.error(
                        f"支付金额不匹配: 订单{callback_data.order_id}, "
                        f"期望{expected_amount}, 实际{callback_data.amount}"
                    )
                    return False

                return True
        except Exception as e:
            logger.error(f"验证支付金额时出错: {e}")
            return False

    def process_payment_callback(
        self, callback_data: PaymentCallbackData
    ) -> Tuple[bool, str]:
        """
        处理支付回调

        Args:
            callback_data: 回调数据

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            # 1. 验证签名
            if not self.verify_callback_signature(callback_data):
                return False, "签名验证失败"

            # 2. 验证时间戳
            if not self.verify_callback_timestamp(callback_data):
                return False, "时间戳验证失败"

            # 3. 检查重复回调
            if self.check_duplicate_callback(callback_data):
                return False, "重复回调"

            # 4. 验证金额
            if not self.verify_payment_amount(callback_data):
                return False, "金额验证失败"

            # 5. 更新订单状态
            success, error_msg = PaymentSecurityManager._update_payment_status(
                callback_data
            )
            if not success:
                return False, error_msg

            # 6. 记录回调日志
            PaymentSecurityManager._log_callback_processing(callback_data)

            return True, "处理成功"
        except Exception as e:
            logger.error(f"处理支付回调时出错: {e}")
            return False, f"处理异常: {str(e)}"

    @staticmethod
    def _update_payment_status(
        callback_data: PaymentCallbackData
    ) -> Tuple[bool, str]:
        """
        更新支付状态

        Args:
            callback_data: 回调数据

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            if not DB_AVAILABLE or get_db_connection is None:
                return False, "数据库不可用"

            with get_db_connection() as (conn, c):
                # 检查订单是否存在
                order_exists = c.execute("""
                    SELECT id, status FROM payment_orders WHERE order_id = ?
                """, (callback_data.order_id,)).fetchone()

                if not order_exists:
                    return False, f"订单不存在: {callback_data.order_id}"

                order_id, current_status = order_exists

                # 检查状态是否已更新
                if current_status == callback_data.status.value:
                    logger.info(f"订单状态已是最新: {callback_data.order_id}")
                    return True, "状态已是最新"

                # 更新订单状态
                c.execute("""
                    UPDATE payment_orders
                    SET status = ?, updated_at = ?
                    WHERE order_id = ?
                """, (
                    callback_data.status.value,
                    int(time.time()),
                    callback_data.order_id
                ))

                # 如果是支付成功，更新用户订阅
                if callback_data.status == PaymentStatus.SUCCESS:
                    PaymentSecurityManager._update_user_subscription(
                        callback_data, c
                    )

                conn.commit()
                logger.info(
                    f"订单状态已更新: {callback_data.order_id} -> "
                    f"{callback_data.status.value}"
                )
                return True, "状态更新成功"

        except Exception as e:
            logger.error(f"更新支付状态时出错: {e}")
            return False, f"更新状态失败: {str(e)}"

    @staticmethod
    def _update_user_subscription(callback_data: PaymentCallbackData, cursor):
        """
        更新用户订阅

        Args:
            callback_data: 回调数据
            cursor: 数据库游标
        """
        try:
            # 获取订单信息
            order_data = cursor.execute("""
                SELECT user_id, description, duration FROM payment_orders
                WHERE order_id = ?
            """, (callback_data.order_id,)).fetchone()

            if not order_data:
                logger.error(f"无法获取订单信息: {callback_data.order_id}")
                return

            user_id, description, duration = order_data

            # 解析套餐信息
            plan_code = PaymentSecurityManager._extract_plan_code(description)
            duration_days = PaymentSecurityManager._parse_duration(duration)

            if not plan_code or not duration_days:
                logger.error(f"无法解析套餐信息: {description}")
                return

            # 计算到期时间
            current_time = int(time.time())
            expiry_time = current_time + (duration_days * 24 * 3600)

            # 更新用户订阅
            cursor.execute("""
                UPDATE users
                SET subscription_type = ?, subscription_expires = ?,
                    remaining_calculations = -1, updated_at = ?
                WHERE id = ?
            """, (plan_code, expiry_time, current_time, user_id))

            logger.info(
                f"用户订阅已更新: 用户{user_id}, 套餐{plan_code}, "
                f"到期时间{expiry_time}"
            )

        except Exception as e:
            logger.error(f"更新用户订阅时出错: {e}")

    @staticmethod
    def _extract_plan_code(description: str) -> Optional[str]:
        """从描述中提取套餐代码"""
        # 这里可以根据实际业务逻辑解析套餐代码
        # 示例实现
        if "效率版" in description:
            return "efficiency"
        elif "专业版" in description:
            return "professional"
        elif "企业版" in description:
            return "enterprise"
        else:
            return "efficiency"  # 默认套餐

    @staticmethod
    def _parse_duration(duration: str) -> int:
        """解析订阅时长"""
        if "月" in duration:
            return 30
        elif "年" in duration:
            return 365
        else:
            return 30  # 默认1个月

    @staticmethod
    def _log_callback_processing(callback_data: PaymentCallbackData):
        """记录回调处理日志"""
        try:
            if not DB_AVAILABLE or get_db_connection is None:
                return

            with get_db_connection() as (conn, c):
                c.execute("""
                    INSERT INTO payment_callback_log
                    (order_id, event_type, transaction_id, amount, status,
                     raw_data, processed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    callback_data.order_id,
                    callback_data.event_type.value,
                    callback_data.transaction_id,
                    callback_data.amount,
                    callback_data.status.value,
                    json.dumps(callback_data.raw_data, ensure_ascii=False),
                    int(time.time())
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"记录回调处理日志时出错: {e}")

    def sync_payment_status(self, order_id: str) -> Tuple[bool, str]:
        """
        同步支付状态（主动查询）

        Args:
            order_id: 订单ID

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            if not WECHAT_PAY_AVAILABLE:
                return False, "微信支付模块不可用"

            # 查询订单状态
            order_data = wechat_pay_v3.query_order(order_id)

            if not order_data:
                return False, "查询订单失败"

            # 解析订单状态
            trade_state = order_data.get('trade_state', '')
            transaction_id = order_data.get('transaction_id', '')
            total_amount = order_data.get('total', 0)

            # 映射状态
            status_mapping = {
                'SUCCESS': PaymentStatus.SUCCESS,
                'REFUND': PaymentStatus.REFUNDED,
                'NOTPAY': PaymentStatus.PENDING,
                'CLOSED': PaymentStatus.CANCELLED,
                'REVOKED': PaymentStatus.CANCELLED,
                'USERPAYING': PaymentStatus.PENDING,
                'PAYERROR': PaymentStatus.FAILED,
            }

            status = status_mapping.get(trade_state, PaymentStatus.PENDING)

            # 创建回调数据
            callback_data = PaymentCallbackData(
                event_type=(
                    PaymentEventType.PAYMENT_SUCCESS
                    if status == PaymentStatus.SUCCESS
                    else PaymentEventType.PAYMENT_FAIL
                ),
                order_id=order_id,
                transaction_id=transaction_id,
                amount=total_amount,
                status=status,
                timestamp=int(time.time()),
                raw_data=order_data,
                signature="",  # 主动查询不需要签名
                nonce=""
            )

            # 处理回调
            return self.process_payment_callback(callback_data)

        except Exception as e:
            logger.error(f"同步支付状态时出错: {e}")
            return False, f"同步失败: {str(e)}"

    @staticmethod
    def get_payment_status(order_id: str) -> Optional[Dict[str, Any]]:
        """
        获取支付状态

        Args:
            order_id: 订单ID

        Returns:
            Optional[Dict[str, Any]]: 支付状态信息
        """
        try:
            if not DB_AVAILABLE or get_db_connection is None:
                return None

            with get_db_connection() as (conn, c):
                order_data = c.execute("""
                    SELECT order_id, amount, status, created_at, updated_at,
                           wechat_order_id, description
                    FROM payment_orders
                    WHERE order_id = ?
                """, (order_id,)).fetchone()

                if not order_data:
                    return None

                return {
                    'order_id': order_data[0],
                    'amount': order_data[1],
                    'status': order_data[2],
                    'created_at': order_data[3],
                    'updated_at': order_data[4],
                    'wechat_order_id': order_data[5],
                    'description': order_data[6]
                }

        except Exception as e:
            logger.error(f"获取支付状态时出错: {e}")
            return None

    @staticmethod
    def create_payment_callback_log_table():
        """创建支付回调日志表"""
        try:
            if not DB_AVAILABLE or get_db_connection is None:
                return False

            with get_db_connection() as (conn, c):
                c.execute("""
                    CREATE TABLE IF NOT EXISTS payment_callback_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id VARCHAR(255) NOT NULL,
                        event_type VARCHAR(100) NOT NULL,
                        transaction_id VARCHAR(255),
                        amount INTEGER,
                        status VARCHAR(50),
                        raw_data TEXT,
                        processed_at INTEGER,
                        created_at INTEGER DEFAULT (strftime('%s', 'now'))
                    )
                """)

                # 创建索引
                c.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_payment_callback_log_order_id
                    ON payment_callback_log(order_id)
                """)

                c.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_payment_callback_log_processed_at
                    ON payment_callback_log(processed_at)
                """)

                conn.commit()
                logger.info("支付回调日志表创建成功")
                return True

        except Exception as e:
            logger.error(f"创建支付回调日志表时出错: {e}")
            return False


# 全局安全管理器实例
_security_manager: Optional[PaymentSecurityManager] = None


def get_payment_security_manager() -> PaymentSecurityManager:
    """获取支付安全管理器实例"""
    global _security_manager
    if _security_manager is None:
        _security_manager = PaymentSecurityManager()
        # 创建必要的数据库表
        PaymentSecurityManager.create_payment_callback_log_table()
    return _security_manager


def process_wechat_payment_callback(
    request_data: Dict[str, Any],
    headers: Dict[str, str]
) -> Tuple[bool, str]:
    """
    处理微信支付回调（兼容性函数）

    Args:
        request_data: 请求数据
        headers: 请求头

    Returns:
        Tuple[bool, str]: (是否成功, 错误信息)
    """
    try:
        # 解析回调数据
        event_type = request_data.get('event_type', '')
        resource = request_data.get('resource', {})

        # 解密资源数据（这里需要根据微信支付API实现）
        # 简化实现，实际需要解密
        decrypted_data = resource

        # 构建回调数据
        callback_data = PaymentCallbackData(
            event_type=PaymentEventType(event_type),
            order_id=decrypted_data.get('out_trade_no', ''),
            transaction_id=decrypted_data.get('transaction_id', ''),
            amount=decrypted_data.get('amount', {}).get('total', 0),
            status=(PaymentStatus.SUCCESS if event_type ==
                    PaymentEventType.PAYMENT_SUCCESS.value else
                    PaymentStatus.FAILED),
            timestamp=decrypted_data.get('create_time', int(time.time())),
            raw_data=request_data,
            signature=headers.get('Wechatpay-Signature', ''),
            nonce=headers.get('Wechatpay-Nonce', '')
        )

        # 处理回调
        payment_security_manager = get_payment_security_manager()
        return payment_security_manager.process_payment_callback(callback_data)

    except Exception as e:
        logger.error(f"处理微信支付回调时出错: {e}")
        return False, f"处理回调失败: {str(e)}"


if __name__ == "__main__":
    # 测试支付安全系统
    print("测试支付安全系统...")

    # 创建安全管理器
    security_manager = get_payment_security_manager()

    # 测试配置
    print(f"签名验证: {security_manager.config.verify_signature}")
    print(f"时间戳验证: {security_manager.config.verify_timestamp}")
    print(f"重复检查: {security_manager.config.enable_duplicate_check}")
    # 测试获取支付状态
    print("\n测试获取支付状态:")
    # 这里需要实际的订单ID进行测试
    # status = PaymentSecurityManager.get_payment_status("test_order_123")
    # print(f"支付状态: {status}")

    print("支付安全系统测试完成")
