# -*- coding: utf-8 -*-
"""
支付UI模块测试
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from ui_payment import (
    check_payment_status_in_db,
    handle_payment_success,
    monitor_payment_status,
    start_payment_monitoring,
    restore_payment_display,
    create_professional_payment,
    create_efficiency_payment,
    check_and_restore_payment_status,
)


class MockSessionState:
    """Mock SessionState对象"""
    def __init__(self):
        self._data = {}
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._data[key] = value
    
    def __contains__(self, key):
        return key in self._data
    
    def __delitem__(self, key):
        if key in self._data:
            del self._data[key]
    
    def __getattr__(self, name):
        return self._data.get(name)
    
    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            if not hasattr(self, '_data'):
                super().__setattr__('_data', {})
            self._data[name] = value
    
    def keys(self):
        return self._data.keys()
    
    def get(self, key, default=None):
        return self._data.get(key, default)


class TestCheckPaymentStatusInDb:
    """测试检查数据库支付状态"""

    def test_check_payment_status_success(self, clean_db):
        """测试支付成功状态检查"""
        from db_utils import get_db_connection
        import time
        
        order_id = f"test_order_success_{int(time.time() * 1000)}"
        
        # 创建测试订单
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                INSERT INTO payment_orders (order_id, user_id, amount, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, 1, 10000, "test", "SUCCESS", time.time()))
            conn.commit()
        
        result = check_payment_status_in_db(order_id)
        assert result is True

    def test_check_payment_status_paid(self, clean_db):
        """测试PAID状态检查"""
        from db_utils import get_db_connection
        import time
        
        order_id = f"test_order_paid_{int(time.time() * 1000)}"
        
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                INSERT INTO payment_orders (order_id, user_id, amount, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, 1, 10000, "test", "PAID", time.time()))
            conn.commit()
        
        result = check_payment_status_in_db(order_id)
        assert result is True

    def test_check_payment_status_pending(self, clean_db):
        """测试待支付状态检查"""
        from db_utils import get_db_connection
        import time
        
        order_id = f"test_order_pending_{int(time.time() * 1000)}"
        
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                INSERT INTO payment_orders (order_id, user_id, amount, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, 1, 10000, "test", "PENDING", time.time()))
            conn.commit()
        
        result = check_payment_status_in_db(order_id)
        assert result is False

    def test_check_payment_status_not_found(self, clean_db):
        """测试订单不存在"""
        result = check_payment_status_in_db("nonexistent_order")
        assert result is False

    @patch('ui_payment.get_db_connection')
    def test_check_payment_status_db_error(self, mock_get_db, clean_db):
        """测试数据库错误处理"""
        mock_get_db.side_effect = Exception("Database error")
        
        result = check_payment_status_in_db("test_order")
        assert result is False


class TestHandlePaymentSuccess:
    """测试处理支付成功"""

    @patch('ui_payment.st')
    def test_handle_payment_success_basic(self, mock_st):
        """测试基本支付成功处理"""
        mock_st.success = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state.payment_monitoring = {}
        mock_st.session_state['payment_order_test123'] = {}
        mock_st.session_state['payment_qr_test123'] = 'qr_data'
        mock_st.rerun = MagicMock()
        
        with patch('time.sleep'):
            handle_payment_success('test123')
        
        assert mock_st.success.called
        assert 'payment_order_test123' not in mock_st.session_state
        assert 'payment_qr_test123' not in mock_st.session_state
        assert mock_st.session_state['current_page'] == 'subscription'
        assert mock_st.rerun.called


class TestMonitorPaymentStatus:
    """测试监控支付状态"""

    @patch('ui_payment.st')
    @patch('ui_payment.check_payment_status_in_db')
    @patch('ui_payment.handle_payment_success')
    def test_monitor_payment_status_success_in_db(
        self, mock_handle, mock_check_db, mock_st
    ):
        """测试数据库已显示支付成功"""
        mock_check_db.return_value = True
        mock_st.session_state = MockSessionState()
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        
        mock_handler = MagicMock()
        
        monitor_payment_status(mock_handler, 'order123', '效率版')
        
        assert mock_handle.called

    @patch('ui_payment.st')
    @patch('ui_payment.check_payment_status_in_db')
    def test_monitor_payment_status_success_via_api(
        self, mock_check_db, mock_st
    ):
        """测试通过API查询到支付成功"""
        mock_check_db.return_value = False
        mock_st.session_state = MockSessionState()
        mock_st.session_state.payment_monitoring = {
            'order123': {'check_count': 0}
        }
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.success = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.rerun = MagicMock()
        
        mock_handler = MagicMock()
        mock_handler.query_payment_status.return_value = {
            'success': True,
            'status': 'SUCCESS'
        }
        
        with patch('ui_payment.handle_payment_success') as mock_handle:
            with patch('time.sleep'):
                monitor_payment_status(mock_handler, 'order123', '效率版')
            
            assert mock_handle.called

    @patch('ui_payment.st')
    @patch('ui_payment.check_payment_status_in_db')
    def test_monitor_payment_status_failed(self, mock_check_db, mock_st):
        """测试支付失败"""
        mock_check_db.return_value = False
        mock_st.session_state = MockSessionState()
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.error = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        
        mock_handler = MagicMock()
        mock_handler.query_payment_status.return_value = {
            'success': True,
            'status': 'CLOSED'
        }
        
        monitor_payment_status(mock_handler, 'order123', '效率版')
        
        assert mock_st.error.called


class TestStartPaymentMonitoring:
    """测试启动支付监控"""

    @patch('ui_payment.st')
    def test_start_payment_monitoring_success(self, mock_st):
        """测试成功启动支付监控"""
        mock_st.error = MagicMock()
        mock_st.info = MagicMock()
        mock_st.progress = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.session_state = MockSessionState()
        
        mock_handler = MagicMock()
        
        start_payment_monitoring(mock_handler, 'order123', '效率版')
        
        assert 'payment_monitoring' in mock_st.session_state
        assert 'order123' in mock_st.session_state.payment_monitoring

    @patch('ui_payment.st')
    def test_start_payment_monitoring_invalid_order(self, mock_st):
        """测试无效订单ID"""
        mock_st.error = MagicMock()
        mock_st.session_state = MockSessionState()
        
        mock_handler = MagicMock()
        
        start_payment_monitoring(mock_handler, '', '效率版')
        
        assert mock_st.error.called


class TestRestorePaymentDisplay:
    """测试恢复支付显示"""

    @patch('ui_payment.st')
    def test_restore_payment_display_with_order(self, mock_st):
        """测试恢复支付显示（有订单信息）"""
        mock_st.info = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state['payment_order_test123'] = {
            'amount': 10000,
            'description': '测试订单'
        }
        mock_st.session_state['payment_qr_test123'] = 'fake_qr_data'
        mock_st.session_state['payment_status_test123'] = '处理中'
        
        restore_payment_display('test123')
        
        assert mock_st.info.called
        assert mock_st.markdown.called

    @patch('ui_payment.st')
    def test_restore_payment_display_no_order(self, mock_st):
        """测试恢复支付显示（无订单信息）"""
        mock_st.info = MagicMock()
        mock_st.session_state = MockSessionState()
        
        restore_payment_display('test123')
        
        # 至少应该显示默认状态
        assert mock_st.info.called

    @patch('ui_payment.st')
    def test_restore_payment_display_invalid_order(self, mock_st):
        """测试恢复支付显示（无效订单ID）"""
        mock_st.session_state = MockSessionState()
        
        restore_payment_display('')
        
        # 不应该抛出异常


class TestCreateProfessionalPayment:
    """测试创建专业版支付"""

    @patch('ui_payment.st')
    @patch('ui_payment.start_payment_monitoring')
    def test_create_professional_payment_success(
        self, mock_monitor, mock_st
    ):
        """测试成功创建专业版支付"""
        mock_st.info = MagicMock()
        mock_st.success = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state['user_id'] = 1
        
        mock_handler = MagicMock()
        mock_handler.create_payment_order.return_value = {
            'success': True,
            'order_id': 'order123',
            'code_url': 'weixin://wxpay/test'
        }
        
        with patch('qrcode.make') as mock_qr_make:
            mock_qr_img = MagicMock()
            mock_qr_make.return_value = mock_qr_img
            
            with patch('io.BytesIO') as mock_io:
                mock_buffer = MagicMock()
                mock_buffer.getvalue.return_value = b'fake_image'
                mock_buffer.seek = MagicMock()
                mock_io.return_value = mock_buffer
                
                mock_qr_img.save = MagicMock()
                
                with patch('base64.b64encode') as mock_b64:
                    mock_b64.return_value.decode.return_value = 'base64_data'
                    
                    create_professional_payment(mock_handler)
        
        assert mock_handler.create_payment_order.called
        assert 'payment_order_order123' in mock_st.session_state
        assert mock_monitor.called

    @patch('ui_payment.st')
    def test_create_professional_payment_failed(self, mock_st):
        """测试创建专业版支付失败"""
        mock_st.info = MagicMock()
        mock_st.error = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state['user_id'] = 1
        
        mock_handler = MagicMock()
        mock_handler.create_payment_order.return_value = {
            'success': False,
            'message': '创建失败'
        }
        
        create_professional_payment(mock_handler)
        
        assert mock_st.error.called


class TestCreateEfficiencyPayment:
    """测试创建效率版支付"""

    @patch('ui_payment.st')
    @patch('ui_payment.start_payment_monitoring')
    def test_create_efficiency_payment_success(
        self, mock_monitor, mock_st
    ):
        """测试成功创建效率版支付"""
        mock_st.info = MagicMock()
        mock_st.success = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state['user_id'] = 1
        
        mock_handler = MagicMock()
        mock_handler.create_payment_order.return_value = {
            'success': True,
            'order_id': 'order456',
            'code_url': 'weixin://wxpay/test'
        }
        
        with patch('qrcode.make') as mock_qr_make:
            mock_qr_img = MagicMock()
            mock_qr_make.return_value = mock_qr_img
            
            with patch('io.BytesIO') as mock_io:
                mock_buffer = MagicMock()
                mock_buffer.getvalue.return_value = b'fake_image'
                mock_buffer.seek = MagicMock()
                mock_io.return_value = mock_buffer
                
                mock_qr_img.save = MagicMock()
                
                with patch('base64.b64encode') as mock_b64:
                    mock_b64.return_value.decode.return_value = 'base64_data'
                    
                    create_efficiency_payment(mock_handler)
        
        assert mock_handler.create_payment_order.called
        assert 'payment_order_order456' in mock_st.session_state
        assert mock_monitor.called


class TestCheckAndRestorePaymentStatus:
    """测试检查和恢复支付状态"""

    @patch('ui_payment.st')
    @patch('ui_payment.restore_payment_display')
    def test_check_and_restore_payment_status_with_monitoring(
        self, mock_restore, mock_st
    ):
        """测试有正在进行的支付"""
        mock_st.info = MagicMock()
        mock_st.progress = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.session_state = MockSessionState()
        mock_st.session_state.payment_monitoring = {
            'order123': {'check_count': 0}
        }
        
        result = check_and_restore_payment_status()
        
        assert result is True
        assert mock_restore.called

    @patch('ui_payment.st')
    def test_check_and_restore_payment_status_no_monitoring(self, mock_st):
        """测试没有正在进行的支付"""
        mock_st.session_state = MockSessionState()
        mock_st.session_state.payment_monitoring = {}
        
        result = check_and_restore_payment_status()
        
        assert result is False

    @patch('ui_payment.st')
    def test_check_and_restore_payment_status_not_in_state(self, mock_st):
        """测试session_state中没有payment_monitoring"""
        mock_st.session_state = MockSessionState()
        
        result = check_and_restore_payment_status()
        
        assert result is False

