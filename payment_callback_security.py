# -*- coding: utf-8 -*-
"""
支付回调安全增强模块
解决高优先级安全问题：支付回调安全性
实现时间戳验证和nonce防重放机制
"""

import time
import hashlib
import logging
from typing import Dict, Tuple

try:
    from .db_utils import get_db_connection
    from .db_adapter import adapt_sql
except ImportError:
    from db_utils import get_db_connection
    try:
        from db_adapter import adapt_sql
    except ImportError:
        def adapt_sql(sql: str) -> str:
            return sql

try:
    from .redis_cache import get_redis_client
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    # 定义占位函数，防止类型检查错误

    def get_redis_client():
        """占位函数，当Redis不可用时返回None"""
        return None

logger = logging.getLogger(__name__)

# 配置常量
TIMESTAMP_WINDOW_SECONDS = 300  # 5分钟时间窗口
NONCE_EXPIRY_SECONDS = 600  # nonce有效期10分钟（大于时间窗口）


class PaymentCallbackSecurity:
    """支付回调安全验证类"""

    @staticmethod
    def validate_timestamp(timestamp: str) -> Tuple[bool, str]:
        """
        验证请求时间戳是否在有效时间窗口内

        Args:
            timestamp: 时间戳字符串

        Returns:
            (is_valid, message): 是否有效，错误消息
        """
        try:
            request_time = int(timestamp)
        except (ValueError, TypeError):
            return False, "时间戳格式无效"

        current_time = int(time.time())
        time_diff = abs(current_time - request_time)

        if time_diff > TIMESTAMP_WINDOW_SECONDS:
            logger.warning(
                f"时间戳验证失败: 时间差 {time_diff}秒 "
                f"超过窗口 {TIMESTAMP_WINDOW_SECONDS}秒"
            )
            return False, (
                f"请求时间戳过期 "
                f"（时间差: {time_diff}秒，允许窗口: "
                f"{TIMESTAMP_WINDOW_SECONDS}秒）"
            )

        return True, ""

    @staticmethod
    def check_and_store_nonce(
        nonce: str,
        order_id: str,
        timestamp: str
    ) -> Tuple[bool, str]:
        """
        检查nonce是否已使用（防重放攻击）
        如果未使用，则存储nonce

        Args:
            nonce: 随机数
            order_id: 订单ID（用于构建唯一键）
            timestamp: 时间戳（用于构建唯一键）

        Returns:
            (is_valid, message): nonce是否有效，错误消息
        """
        if not nonce or len(nonce) < 8:
            return False, "nonce长度不足"

        # 构建唯一键：order_id + nonce + timestamp
        # 这样可以防止同一订单的不同请求使用相同的nonce
        nonce_key = f"payment_nonce:{order_id}:{nonce}:{timestamp}"
        nonce_hash = hashlib.sha256(nonce_key.encode()).hexdigest()

        # 优先使用Redis存储nonce（如果可用）
        if REDIS_AVAILABLE:
            try:
                redis_client = get_redis_client()
                if redis_client is not None:
                    # 检查nonce是否已存在
                    if redis_client.exists(nonce_hash):
                        logger.warning(
                            f"检测到nonce重放攻击: order_id={order_id}, "
                            f"nonce={nonce[:8]}..."
                        )
                        return False, "nonce已使用，疑似重放攻击"

                    # 存储nonce，设置过期时间
                    redis_client.setex(
                        nonce_hash,
                        NONCE_EXPIRY_SECONDS,
                        "1"  # 存储值可以是任意值
                    )
                    return True, ""
            except (
                AttributeError, ConnectionError, OSError, TimeoutError
            ) as e:
                logger.error(f"Redis nonce检查失败: {e}，降级到数据库存储")

        # 降级到数据库存储
        try:
            with get_db_connection() as (conn, c):
                # 创建nonce记录表（如果不存在）
                create_sql = adapt_sql("""
                    CREATE TABLE IF NOT EXISTS payment_nonce_log (
                        nonce_hash TEXT PRIMARY KEY,
                        order_id TEXT NOT NULL,
                        nonce TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                """)
                c.execute(create_sql)

                # 检查nonce是否已存在
                sql = adapt_sql("""
                    SELECT nonce_hash FROM payment_nonce_log
                    WHERE nonce_hash = ? AND expires_at > ?
                """)
                c.execute(sql, (nonce_hash, time.time()))
                existing = c.fetchone()

                if existing:
                    logger.warning(
                        f"检测到nonce重放攻击（数据库）: "
                        f"order_id={order_id}, nonce={nonce[:8]}..."
                    )
                    return False, "nonce已使用，疑似重放攻击"

                # 存储nonce
                current_time = time.time()
                expires_at = current_time + NONCE_EXPIRY_SECONDS
                sql = adapt_sql("""
                    INSERT INTO payment_nonce_log
                    (nonce_hash, order_id, nonce, timestamp,
                     created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """)
                c.execute(
                    sql, (nonce_hash, order_id, nonce, timestamp,
                          current_time, expires_at))
                conn.commit()

                # 清理过期的nonce记录（每100次插入清理一次）
                if hash(nonce_hash) % 100 == 0:
                    sql = adapt_sql("""
                        DELETE FROM payment_nonce_log
                        WHERE expires_at < ?
                    """)
                    c.execute(sql, (time.time(),))
                    conn.commit()

                return True, ""
        except (OSError, RuntimeError, ValueError, TypeError) as e:
            logger.error(f"数据库nonce检查失败: {e}")
            return False, f"nonce验证失败: {str(e)}"

    @staticmethod
    def verify_callback_security(
        headers: Dict[str, str],
        order_id: str
    ) -> Tuple[bool, str]:
        """
        完整的回调安全验证（时间戳 + nonce）

        Args:
            headers: 请求头字典
            order_id: 订单ID

        Returns:
            (is_valid, message): 是否通过验证，错误消息
        """
        # 1. 提取时间戳和nonce
        timestamp = headers.get('Wechatpay-Timestamp', '')
        nonce = headers.get('Wechatpay-Nonce', '')

        if not timestamp:
            return False, "缺少时间戳"

        if not nonce:
            return False, "缺少nonce"

        # 2. 验证时间戳
        is_valid, message = PaymentCallbackSecurity.validate_timestamp(
            timestamp
        )
        if not is_valid:
            return False, message

        # 3. 检查并存储nonce（防重放）
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        if not is_valid:
            return False, message

        return True, "验证通过"

    @staticmethod
    def cleanup_expired_nonces():
        """清理过期的nonce记录（定期任务）"""
        try:
            # 清理数据库中的过期nonce
            with get_db_connection() as (conn, c):
                sql = adapt_sql("""
                    DELETE FROM payment_nonce_log
                    WHERE expires_at < ?
                """)
                c.execute(sql, (time.time(),))
                deleted_count = c.rowcount
                conn.commit()

                if deleted_count > 0:
                    logger.info(f"清理了 {deleted_count} 条过期nonce记录")

            # 清理Redis中的过期nonce（Redis会自动过期，这里只是记录）
            if REDIS_AVAILABLE:
                try:
                    redis_client = get_redis_client()
                    if redis_client is not None:
                        # Redis会自动清理过期的键，无需手动操作
                        pass
                except (
                    AttributeError, ConnectionError, OSError, TimeoutError
                ):
                    # Redis清理错误，忽略（不影响主流程）
                    pass
        except (OSError, RuntimeError, ValueError, TypeError) as e:
            logger.error(f"清理过期nonce失败: {e}")


def verify_payment_callback_security(
    headers: Dict[str, str],
    order_id: str
) -> Tuple[bool, str]:
    """
    验证支付回调安全性的便捷函数

    Args:
        headers: 请求头字典
        order_id: 订单ID

    Returns:
        (is_valid, message): 是否通过验证，错误消息
    """
    return PaymentCallbackSecurity.verify_callback_security(
        headers, order_id
    )
