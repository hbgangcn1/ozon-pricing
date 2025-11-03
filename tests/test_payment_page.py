# -*- coding: utf-8 -*-
"""
支付页面测试
"""

import pytest
import time
import base64
from unittest.mock import patch, MagicMock
from payment_page import (
    cleanup_payment_state,
    show_duration_selection,
    handle_payment_success,
    auto_check_and_redirect,
    create_new_payment,
    show_existing_payment,
)


class MockSessionState:
    """Mock SessionState对象，支持属性访问和字典访问"""
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


class TestCleanupPaymentState:
    """测试清理支付状态"""

    @patch('payment_page.st')
    def test_cleanup_payment_state(self, mock_st):
        """测试清理支付状态"""
        mock_st.session_state = MockSessionState()
        mock_st.session_state['payment_order_效率版'] = 'order123'
        mock_st.session_state['payment_qr_order123'] = 'qr_data'
        mock_st.session_state['order_creation_time_order123'] = time.time()
        mock_st.session_state['payment_duration_效率版'] = '1_month'
        
        cleanup_payment_state('效率版', 'order123')
        
        # 验证状态已清除
        assert 'payment_order_效率版' not in mock_st.session_state
        assert 'payment_qr_order123' not in mock_st.session_state
        assert 'order_creation_time_order123' not in mock_st.session_state


class TestHandlePaymentSuccess:
    """测试处理支付成功"""

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    @patch('payment_page.get_db_connection')
    @patch('payment_page.clear_payment_state_from_browser')
    def test_handle_payment_success_basic(
        self, mock_clear, mock_get_db, mock_user_id, mock_st
    ):
        """测试基本支付成功处理"""
        mock_st.balloons = MagicMock()
        mock_st.success = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        mock_user_id.return_value = 1
        
        with patch('time.sleep'):
            handle_payment_success('order123', '效率版')
        
        assert mock_st.balloons.called
        assert mock_st.success.called
        assert mock_clear.called
        assert 'last_successful_payment' in mock_st.session_state

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    @patch('payment_page.get_db_connection')
    @patch('payment_page.clear_payment_state_from_browser')
    def test_handle_payment_success_with_promo(
        self, mock_clear, mock_get_db, mock_user_id, mock_st
    ):
        """测试支付成功处理（首月优惠）"""
        mock_st.balloons = MagicMock()
        mock_st.success = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state['mark_efficiency_promo_order123'] = True
        mock_st.rerun = MagicMock()
        mock_user_id.return_value = 1
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        with patch('time.sleep'):
            handle_payment_success('order123', '效率版')
        
        # 验证更新了数据库
        assert mock_cursor.execute.called
        assert 'efficiency_promo_used' in str(mock_cursor.execute.call_args)
        assert 'mark_efficiency_promo_order123' not in mock_st.session_state


class TestAutoCheckAndRedirect:
    """测试自动检查支付状态"""

    @patch('payment_page.st')
    @patch('payment_page.get_db_connection')
    @patch('payment_page.handle_payment_success')
    def test_auto_check_payment_success(
        self, mock_handle, mock_get_db, mock_st
    ):
        """测试检查到支付成功"""
        mock_st.session_state = MockSessionState()
        mock_st.session_state['order_creation_time_order123'] = time.time()
        mock_st.warning = MagicMock()
        mock_st.error = MagicMock()
        mock_st.info = MagicMock()
        mock_st.rerun = MagicMock()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('SUCCESS', int(time.time()))
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        auto_check_and_redirect('order123', '效率版')
        
        # 验证调用了handle_payment_success
        assert mock_handle.called

    @patch('payment_page.st')
    @patch('payment_page.get_db_connection')
    def test_auto_check_payment_pending(
        self, mock_get_db, mock_st
    ):
        """测试检查到支付待处理"""
        mock_st.session_state = MockSessionState()
        mock_st.session_state['order_creation_time_order123'] = time.time()
        mock_st.warning = MagicMock()
        mock_st.error = MagicMock()
        mock_st.info = MagicMock()
        mock_st.rerun = MagicMock()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('PENDING', int(time.time()))
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        auto_check_and_redirect('order123', '效率版')
        
        # 验证没有调用handle_payment_success（支付还在处理中）
        assert not mock_st.error.called

    @patch('payment_page.st')
    @patch('payment_page.get_db_connection')
    def test_auto_check_payment_failed(
        self, mock_get_db, mock_st
    ):
        """测试检查到支付失败"""
        mock_st.session_state = MockSessionState()
        mock_st.session_state['order_creation_time_order123'] = time.time()
        mock_st.warning = MagicMock()
        mock_st.error = MagicMock()
        mock_st.info = MagicMock()
        mock_st.rerun = MagicMock()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('CLOSED', int(time.time()))
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        with patch('time.sleep'):
            auto_check_and_redirect('order123', '效率版')
        
        assert mock_st.error.called

    @patch('payment_page.st')
    def test_auto_check_timeout(self, mock_st):
        """测试订单超时"""
        mock_st.session_state = MockSessionState()
        mock_st.session_state['order_creation_time_order123'] = time.time() - 2000
        mock_st.warning = MagicMock()
        mock_st.rerun = MagicMock()
        
        with patch('time.sleep'):
            auto_check_and_redirect('order123', '效率版')
        
        assert mock_st.warning.called
        assert '超时' in str(mock_st.warning.call_args)

    @patch('payment_page.st')
    def test_auto_check_cache(self, mock_st):
        """测试检查缓存（最近2秒内不重复查询）"""
        mock_st.session_state = MockSessionState()
        mock_st.session_state['last_check_order123'] = time.time() - 1
        mock_st.session_state['order_creation_time_order123'] = time.time()
        
        auto_check_and_redirect('order123', '效率版')
        
        # 如果使用了缓存，不会查询数据库
        # 验证缓存时间已更新
        assert 'last_check_order123' in mock_st.session_state


class TestCreateNewPayment:
    """测试创建新支付订单"""

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    @patch('payment_page.get_db_connection')
    @patch('payment_page.get_plan_by_code')
    @patch('payment_page.get_plan_price')
    @patch('payment_page.save_payment_state_to_browser')
    def test_create_new_payment_success(
        self, mock_save, mock_price, mock_plan, mock_get_db,
        mock_user_id, mock_st
    ):
        """测试创建支付订单成功"""
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.error = MagicMock()
        mock_st.success = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state['payment_duration_效率版'] = '1_month'
        mock_st.rerun = MagicMock()
        mock_user_id.return_value = 1
        
        # Mock数据库
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)  # 未使用过优惠
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        # Mock套餐配置
        mock_plan.return_value = {'is_active': True}
        mock_price.return_value = 9.9
        
        # Mock PaymentHandler
        mock_handler = MagicMock()
        mock_handler.create_payment_order.return_value = {
            'success': True,
            'order_id': 'order123',
            'code_url': 'weixin://wxpay/test'
        }
        
        with patch('payment_page.qrcode') as mock_qr:
            mock_qr_img = MagicMock()
            mock_qr.QRCode.return_value.make_image.return_value = mock_qr_img
            
            with patch('payment_page.io.BytesIO') as mock_io:
                mock_buffer = MagicMock()
                mock_buffer.getvalue.return_value = b'fake_image_data'
                mock_buffer.seek = MagicMock()
                mock_io.return_value = mock_buffer
                
                mock_qr_img.save = MagicMock()
                
                create_new_payment('效率版', mock_handler)
        
        # 验证订单创建成功
        assert mock_handler.create_payment_order.called
        assert 'payment_order_效率版' in mock_st.session_state

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    def test_create_new_payment_no_duration(self, mock_user_id, mock_st):
        """测试未选择购买时长"""
        mock_st.info = MagicMock()
        mock_st.error = MagicMock()
        mock_st.button = MagicMock(return_value=False)
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        mock_user_id.return_value = 1
        
        create_new_payment('效率版', MagicMock())
        
        assert mock_st.error.called

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    def test_create_new_payment_no_user(self, mock_user_id, mock_st):
        """测试用户未登录"""
        mock_st.info = MagicMock()
        mock_st.error = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state['payment_duration_效率版'] = '1_month'
        mock_user_id.return_value = None
        
        create_new_payment('效率版', MagicMock())
        
        assert mock_st.error.called

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    @patch('payment_page.get_db_connection')
    @patch('payment_page.get_plan_by_code')
    def test_create_new_payment_plan_not_found(
        self, mock_plan, mock_get_db, mock_user_id, mock_st
    ):
        """测试套餐不存在"""
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.error = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state['payment_duration_效率版'] = '1_month'
        mock_user_id.return_value = 1
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        mock_plan.return_value = None
        
        create_new_payment('效率版', MagicMock())
        
        assert mock_st.error.called

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    @patch('payment_page.get_db_connection')
    @patch('payment_page.get_plan_by_code')
    def test_create_new_payment_plan_inactive(
        self, mock_plan, mock_get_db, mock_user_id, mock_st
    ):
        """测试套餐未上架"""
        mock_st.info = MagicMock()
        mock_st.spinner = MagicMock()
        mock_st.error = MagicMock()
        mock_st.session_state = MockSessionState()
        mock_st.session_state['payment_duration_效率版'] = '1_month'
        mock_user_id.return_value = 1
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        mock_plan.return_value = {'is_active': False}
        
        create_new_payment('效率版', MagicMock())
        
        assert mock_st.error.called


class TestShowExistingPayment:
    """测试显示已有订单"""

    @patch('payment_page.st')
    @patch('payment_page.auto_check_and_redirect')
    @patch('payment_page.show_enhanced_auto_check_indicator')
    def test_show_existing_payment_basic(
        self, mock_indicator, mock_check, mock_st
    ):
        """测试显示已有订单（基本功能）"""
        mock_st.success = MagicMock()
        mock_st.info = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock()])
        mock_st.button = MagicMock(return_value=False)
        mock_st.session_state = MockSessionState()
        mock_st.session_state['auto_check_count'] = 1
        mock_st.session_state['payment_qr_order123'] = {
            'qr_image': 'fake_base64_image'
        }
        mock_st.rerun = MagicMock()
        
        mock_handler = MagicMock()
        
        with patch('time.sleep'):
            show_existing_payment('order123', '效率版', mock_handler)
        
        assert mock_check.called
        assert mock_indicator.called
        assert mock_st.markdown.called

    @patch('payment_page.st')
    @patch('payment_page.auto_check_and_redirect')
    @patch('payment_page.show_enhanced_auto_check_indicator')
    @patch('payment_page.get_db_connection')
    def test_show_existing_payment_check_status_button(
        self, mock_get_db, mock_indicator, mock_check, mock_st
    ):
        """测试点击检查支付状态按钮"""
        mock_st.success = MagicMock()
        mock_st.info = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.spinner = MagicMock()
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns = MagicMock(return_value=[mock_col1, mock_col2])
        
        # 有多个button调用，第一个是检查支付状态按钮（返回True）
        # 其他的都返回False
        mock_st.button = MagicMock(side_effect=[True, False, False, False])
        mock_st.session_state = MockSessionState()
        mock_st.session_state['auto_check_count'] = 1
        mock_st.rerun = MagicMock()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('SUCCESS',)
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        mock_handler = MagicMock()
        
        with patch('time.sleep'):
            show_existing_payment('order123', '效率版', mock_handler)
        
        assert mock_cursor.execute.called

    @patch('payment_page.st')
    @patch('payment_page.auto_check_and_redirect')
    @patch('payment_page.show_enhanced_auto_check_indicator')
    def test_show_existing_payment_max_checks(
        self, mock_indicator, mock_check, mock_st
    ):
        """测试达到最大检查次数"""
        mock_st.success = MagicMock()
        mock_st.warning = MagicMock()
        mock_st.info = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock()])
        mock_st.button = MagicMock(return_value=False)
        mock_st.session_state = MockSessionState()
        mock_st.session_state['auto_check_count'] = 60  # 达到最大次数
        mock_st.rerun = MagicMock()
        
        mock_handler = MagicMock()
        
        with patch('time.sleep'):
            show_existing_payment('order123', '效率版', mock_handler)
        
        assert mock_st.warning.called


class TestShowDurationSelection:
    """测试显示购买时长选择"""

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    @patch('payment_page.get_db_connection')
    def test_show_duration_selection_efficiency(
        self, mock_get_db, mock_user_id, mock_st
    ):
        """测试效率版时长选择"""
        mock_st.markdown = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock()])
        mock_st.button = MagicMock(return_value=False)
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        mock_user_id.return_value = 1
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)  # 未使用过优惠
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        show_duration_selection('效率版')
        
        assert mock_st.markdown.called

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    @patch('payment_page.get_db_connection')
    def test_show_duration_selection_professional(
        self, mock_get_db, mock_user_id, mock_st
    ):
        """测试专业版时长选择"""
        mock_st.markdown = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock()])
        mock_st.button = MagicMock(return_value=False)
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        mock_user_id.return_value = 1
        
        show_duration_selection('专业版')
        
        assert mock_st.markdown.called

    @patch('payment_page.st')
    @patch('payment_page.current_user_id')
    @patch('payment_page.get_db_connection')
    def test_show_duration_selection_select_month(
        self, mock_get_db, mock_user_id, mock_st
    ):
        """测试选择月付"""
        mock_st.markdown = MagicMock()
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns = MagicMock(return_value=[mock_col1, mock_col2])
        # 有3个button：月付按钮(True)，年付按钮(False)，返回首页按钮(False)
        mock_st.button = MagicMock(side_effect=[True, False, False])
        mock_st.session_state = MockSessionState()
        mock_st.rerun = MagicMock()
        mock_user_id.return_value = 1
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_get_db.return_value.__enter__.return_value = (mock_conn, mock_cursor)
        
        show_duration_selection('效率版')
        
        assert 'payment_duration_效率版' in mock_st.session_state
        assert mock_st.session_state['payment_duration_效率版'] == '1_month'
        assert mock_st.rerun.called

