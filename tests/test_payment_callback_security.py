# -*- coding: utf-8 -*-
"""
支付回调安全验证测试
"""

import pytest
import time
import hashlib
from unittest.mock import patch, MagicMock
from payment_callback_security import (
    PaymentCallbackSecurity,
    verify_payment_callback_security,
    TIMESTAMP_WINDOW_SECONDS,
    NONCE_EXPIRY_SECONDS,
)


class TestValidateTimestamp:
    """测试时间戳验证"""

    def test_validate_timestamp_valid(self):
        """测试有效时间戳（当前时间）"""
        current_time = str(int(time.time()))
        is_valid, message = PaymentCallbackSecurity.validate_timestamp(current_time)
        
        assert is_valid is True
        assert message == ""

    def test_validate_timestamp_within_window_before(self):
        """测试时间戳在窗口内（过去）"""
        timestamp = str(int(time.time()) - 100)  # 100秒前
        is_valid, message = PaymentCallbackSecurity.validate_timestamp(timestamp)
        
        assert is_valid is True
        assert message == ""

    def test_validate_timestamp_within_window_after(self):
        """测试时间戳在窗口内（未来）"""
        timestamp = str(int(time.time()) + 100)  # 100秒后
        is_valid, message = PaymentCallbackSecurity.validate_timestamp(timestamp)
        
        assert is_valid is True
        assert message == ""

    def test_validate_timestamp_expired_before(self):
        """测试过期时间戳（太久之前）"""
        timestamp = str(int(time.time()) - TIMESTAMP_WINDOW_SECONDS - 10)
        is_valid, message = PaymentCallbackSecurity.validate_timestamp(timestamp)
        
        assert is_valid is False
        assert "过期" in message or "时间差" in message

    def test_validate_timestamp_expired_after(self):
        """测试过期时间戳（太久之后）"""
        timestamp = str(int(time.time()) + TIMESTAMP_WINDOW_SECONDS + 10)
        is_valid, message = PaymentCallbackSecurity.validate_timestamp(timestamp)
        
        assert is_valid is False
        assert "过期" in message or "时间差" in message

    def test_validate_timestamp_invalid_format(self):
        """测试无效时间戳格式"""
        is_valid, message = PaymentCallbackSecurity.validate_timestamp("invalid")
        
        assert is_valid is False
        assert "格式无效" in message

    def test_validate_timestamp_empty_string(self):
        """测试空字符串"""
        is_valid, message = PaymentCallbackSecurity.validate_timestamp("")
        
        assert is_valid is False
        assert "格式无效" in message

    def test_validate_timestamp_none(self):
        """测试None值"""
        is_valid, message = PaymentCallbackSecurity.validate_timestamp(None)
        
        assert is_valid is False
        assert "格式无效" in message

    def test_validate_timestamp_at_window_boundary(self):
        """测试时间戳在窗口边界"""
        timestamp = str(int(time.time()) - TIMESTAMP_WINDOW_SECONDS)
        is_valid, message = PaymentCallbackSecurity.validate_timestamp(timestamp)
        
        assert is_valid is True


class TestCheckAndStoreNonce:
    """测试nonce防重放攻击"""

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_check_and_store_nonce_success(self, clean_db):
        """测试成功存储nonce（使用数据库）"""
        nonce = f"test_nonce_{int(time.time() * 1000)}"  # 使用唯一nonce
        order_id = f"test_order_{int(time.time() * 1000)}"
        timestamp = str(int(time.time()))
        
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        
        assert is_valid is True
        assert message == ""

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_check_and_store_nonce_replay_attack(self, clean_db):
        """测试nonce重放攻击检测"""
        unique_id = int(time.time() * 1000)
        nonce = f"replay_nonce_{unique_id}"
        order_id = f"replay_order_{unique_id}"
        timestamp = str(int(time.time()))
        
        # 第一次存储应该成功
        is_valid1, _ = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        assert is_valid1 is True
        
        # 第二次使用相同nonce应该失败（重放攻击）
        is_valid2, message2 = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        assert is_valid2 is False
        assert "重放攻击" in message2 or "已使用" in message2

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_check_and_store_nonce_too_short(self, clean_db):
        """测试nonce长度不足"""
        nonce = "short"  # 长度小于8
        order_id = "test_order_123"
        timestamp = str(int(time.time()))
        
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        
        assert is_valid is False
        assert "长度不足" in message

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_check_and_store_nonce_empty(self, clean_db):
        """测试空nonce"""
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            "", "order123", "1234567890"
        )
        
        assert is_valid is False
        assert "长度不足" in message

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_check_and_store_nonce_none(self, clean_db):
        """测试None nonce"""
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            None, "order123", "1234567890"
        )
        
        assert is_valid is False
        assert "长度不足" in message

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_check_and_store_nonce_different_order(self, clean_db):
        """测试不同订单可以使用相同nonce"""
        unique_id = int(time.time() * 1000)
        nonce = f"diff_order_nonce_{unique_id}"
        timestamp = str(int(time.time()))
        
        # 第一个订单
        is_valid1, _ = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, f"order1_{unique_id}", timestamp
        )
        assert is_valid1 is True
        
        # 第二个订单使用相同nonce应该成功（不同订单）
        is_valid2, _ = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, f"order2_{unique_id}", timestamp
        )
        assert is_valid2 is True

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_check_and_store_nonce_different_timestamp(self, clean_db):
        """测试不同时间戳可以使用相同nonce（相同订单）"""
        unique_id = int(time.time() * 1000)
        nonce = f"diff_timestamp_nonce_{unique_id}"
        order_id = f"diff_timestamp_order_{unique_id}"
        
        timestamp1 = str(int(time.time()))
        timestamp2 = str(int(time.time()) + 1)
        
        # 第一次存储
        is_valid1, _ = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp1
        )
        assert is_valid1 is True
        
        # 不同时间戳可以使用相同nonce
        is_valid2, _ = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp2
        )
        assert is_valid2 is True

    @patch('payment_callback_security.REDIS_AVAILABLE', True)
    @patch('payment_callback_security.get_redis_client')
    def test_check_and_store_nonce_with_redis_success(self, mock_get_redis, clean_db):
        """测试使用Redis存储nonce成功"""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = False  # nonce不存在
        mock_redis.setex = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        unique_id = int(time.time() * 1000)
        nonce = f"redis_nonce_{unique_id}"
        order_id = f"redis_order_{unique_id}"
        timestamp = str(int(time.time()))
        
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        
        assert is_valid is True
        assert message == ""
        assert mock_redis.exists.called
        assert mock_redis.setex.called

    @patch('payment_callback_security.REDIS_AVAILABLE', True)
    @patch('payment_callback_security.get_redis_client')
    def test_check_and_store_nonce_with_redis_replay(self, mock_get_redis, clean_db):
        """测试Redis检测nonce重放攻击"""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = True  # nonce已存在
        mock_get_redis.return_value = mock_redis
        
        nonce = "test_nonce_12345678"
        order_id = "test_order_123"
        timestamp = str(int(time.time()))
        
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        
        assert is_valid is False
        assert "重放攻击" in message or "已使用" in message

    @patch('payment_callback_security.REDIS_AVAILABLE', True)
    @patch('payment_callback_security.get_redis_client')
    def test_check_and_store_nonce_redis_fallback_to_db(self, mock_get_redis, clean_db):
        """测试Redis失败时降级到数据库"""
        # Redis抛出异常
        mock_get_redis.side_effect = ConnectionError("Redis连接失败")
        
        unique_id = int(time.time() * 1000)
        nonce = f"fallback_nonce_{unique_id}"
        order_id = f"fallback_order_{unique_id}"
        timestamp = str(int(time.time()))
        
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        
        # 应该降级到数据库并成功
        assert is_valid is True
        assert message == ""

    @patch('payment_callback_security.REDIS_AVAILABLE', True)
    @patch('payment_callback_security.get_redis_client')
    def test_check_and_store_nonce_redis_none(self, mock_get_redis, clean_db):
        """测试Redis返回None时降级到数据库"""
        mock_get_redis.return_value = None
        
        unique_id = int(time.time() * 1000)
        nonce = f"redis_none_nonce_{unique_id}"
        order_id = f"redis_none_order_{unique_id}"
        timestamp = str(int(time.time()))
        
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        
        # 应该降级到数据库并成功
        assert is_valid is True
        assert message == ""

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    @patch('payment_callback_security.get_db_connection')
    def test_check_and_store_nonce_db_error(self, mock_get_db, clean_db):
        """测试数据库错误处理"""
        mock_get_db.side_effect = OSError("数据库连接失败")
        
        nonce = "test_nonce_12345678"
        order_id = "test_order_123"
        timestamp = str(int(time.time()))
        
        is_valid, message = PaymentCallbackSecurity.check_and_store_nonce(
            nonce, order_id, timestamp
        )
        
        assert is_valid is False
        assert "验证失败" in message


class TestVerifyCallbackSecurity:
    """测试完整回调安全验证"""

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_verify_callback_security_success(self, clean_db):
        """测试完整验证成功"""
        unique_id = int(time.time() * 1000)
        headers = {
            'Wechatpay-Timestamp': str(int(time.time())),
            'Wechatpay-Nonce': f'verify_nonce_{unique_id}'
        }
        order_id = f"verify_order_{unique_id}"
        
        is_valid, message = PaymentCallbackSecurity.verify_callback_security(
            headers, order_id
        )
        
        assert is_valid is True
        assert message == "验证通过"

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_verify_callback_security_missing_timestamp(self, clean_db):
        """测试缺少时间戳"""
        headers = {
            'Wechatpay-Nonce': 'test_nonce_12345678'
        }
        order_id = "test_order_123"
        
        is_valid, message = PaymentCallbackSecurity.verify_callback_security(
            headers, order_id
        )
        
        assert is_valid is False
        assert "缺少时间戳" in message

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_verify_callback_security_missing_nonce(self, clean_db):
        """测试缺少nonce"""
        headers = {
            'Wechatpay-Timestamp': str(int(time.time()))
        }
        order_id = "test_order_123"
        
        is_valid, message = PaymentCallbackSecurity.verify_callback_security(
            headers, order_id
        )
        
        assert is_valid is False
        assert "缺少nonce" in message

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_verify_callback_security_invalid_timestamp(self, clean_db):
        """测试无效时间戳"""
        headers = {
            'Wechatpay-Timestamp': str(int(time.time()) - 1000),
            'Wechatpay-Nonce': 'test_nonce_12345678'
        }
        order_id = "test_order_123"
        
        is_valid, message = PaymentCallbackSecurity.verify_callback_security(
            headers, order_id
        )
        
        assert is_valid is False
        assert "过期" in message or "时间差" in message

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_verify_callback_security_replay_attack(self, clean_db):
        """测试重放攻击检测"""
        unique_id = int(time.time() * 1000)
        timestamp = str(int(time.time()))
        headers = {
            'Wechatpay-Timestamp': timestamp,
            'Wechatpay-Nonce': f'replay_verify_nonce_{unique_id}'
        }
        order_id = f"replay_verify_order_{unique_id}"
        
        # 第一次验证应该成功
        is_valid1, _ = PaymentCallbackSecurity.verify_callback_security(
            headers, order_id
        )
        assert is_valid1 is True
        
        # 第二次使用相同headers应该失败
        is_valid2, message2 = PaymentCallbackSecurity.verify_callback_security(
            headers, order_id
        )
        assert is_valid2 is False
        assert "重放攻击" in message2 or "已使用" in message2


class TestVerifyPaymentCallbackSecurityFunction:
    """测试便捷函数"""

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_verify_payment_callback_security_success(self, clean_db):
        """测试便捷函数成功"""
        unique_id = int(time.time() * 1000)
        headers = {
            'Wechatpay-Timestamp': str(int(time.time())),
            'Wechatpay-Nonce': f'func_nonce_{unique_id}'
        }
        order_id = f"func_order_{unique_id}"
        
        is_valid, message = verify_payment_callback_security(headers, order_id)
        
        assert is_valid is True
        assert message == "验证通过"


class TestCleanupExpiredNonces:
    """测试清理过期nonce"""

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_cleanup_expired_nonces_no_expired(self, clean_db):
        """测试清理过期nonce（无过期记录）"""
        PaymentCallbackSecurity.cleanup_expired_nonces()
        
        # 应该正常执行，不抛出异常
        assert True

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    def test_cleanup_expired_nonces_with_expired(self, clean_db):
        """测试清理过期nonce（有过期记录）"""
        # 创建一个过期的nonce记录
        from db_utils import get_db_connection
        with get_db_connection() as (conn, c):
            c.execute("""
                CREATE TABLE IF NOT EXISTS payment_nonce_log (
                    nonce_hash TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
            """)
            
            # 插入一个已过期的记录
            c.execute("""
                INSERT INTO payment_nonce_log
                (nonce_hash, order_id, nonce, timestamp, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "expired_hash",
                "order123",
                "nonce123",
                "1234567890",
                time.time() - 1000,
                time.time() - 100  # 已过期
            ))
            conn.commit()
        
        # 清理过期记录
        PaymentCallbackSecurity.cleanup_expired_nonces()
        
        # 验证记录已被删除
        with get_db_connection() as (conn, c):
            remaining = c.execute("""
                SELECT COUNT(*) FROM payment_nonce_log
                WHERE nonce_hash = 'expired_hash'
            """).fetchone()[0]
            
            assert remaining == 0

    @patch('payment_callback_security.REDIS_AVAILABLE', True)
    @patch('payment_callback_security.get_redis_client')
    def test_cleanup_expired_nonces_with_redis(self, mock_get_redis, clean_db):
        """测试清理过期nonce（Redis可用）"""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        PaymentCallbackSecurity.cleanup_expired_nonces()
        
        # 应该正常执行，Redis会自动清理，无需手动操作
        assert True

    @patch('payment_callback_security.REDIS_AVAILABLE', True)
    @patch('payment_callback_security.get_redis_client')
    def test_cleanup_expired_nonces_redis_error(self, mock_get_redis, clean_db):
        """测试清理过期nonce（Redis错误）"""
        mock_get_redis.side_effect = ConnectionError("Redis连接失败")
        
        # 应该正常执行，Redis错误不影响数据库清理
        PaymentCallbackSecurity.cleanup_expired_nonces()
        assert True

    @patch('payment_callback_security.REDIS_AVAILABLE', False)
    @patch('payment_callback_security.get_db_connection')
    def test_cleanup_expired_nonces_db_error(self, mock_get_db, clean_db):
        """测试清理过期nonce（数据库错误）"""
        mock_get_db.side_effect = OSError("数据库连接失败")
        
        # 应该捕获异常，不抛出
        try:
            PaymentCallbackSecurity.cleanup_expired_nonces()
            assert True
        except Exception:
            pytest.fail("不应该抛出异常")

